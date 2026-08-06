#include "barrier.h"
#include "sys.h"
#include "delay.h"
#include "motor.h"
#include "pid.h"
#include "imu.h"
#include "scaner.h"
#include "turn.h"
#include "map.h"
#include "motor_task.h"
#include "chassis_api.h"
#include "ArriveDetect_task.h"
#include "pid.h"
#include "math.h"
#include "bsp_buzzer.h"
#include "bsp_led.h"
#include "gray.h"
#include "stdio.h"
#include "motor_task.h"
#include "QR.h"
#include "motion.h"
#include "bsp_linefollower.h"
#include "openmv.h"
#include "Rudder_control.h"
#include "encoder.h"
#include "filter.h"
#include "K210.h"
#include "string.h"
#include "adc.h"
#include "gray.h"
#include "chassis_api.h"



/*==============================================================================
 *  目录 / Table of Contents   按 Ctrl+F 搜索函数名快速跳转
 *
 *  工具函数          Stage_HasTreasure / Stage_CollectTreasure
 *                    GyroStableReset / Stage_DetectedRamp
 *                    RampCtrl_Blocking / Stage_ScanAndRead
 *  平台              Stage( / Stage_P2
 *  长桥              Barrier_Bridge
 *  楼梯              Barrier_Hill
 *  刀山              Sword_CorrectByScanner / Sword_Mountain
 *  珠峰              Barrier_HighMountain
 *  直立景点          view / view1 / back
 *  波浪板            Barrier_WavedPlate
 *  南极              South_Pole
 *  路线更新（宝物）  load_route_at
 *                    update_route_at_P7_for_treasure / _8
 *  跷跷板            QQB_1
 *  红绿灯            Door_ReadColor / door_set_pass_node
 *                    door_retreat / door(
 *  路线更新（门/QR） update_route_at_P1
 *                    update_route_by_door_1~4 / update_route_at_door_for_clue
 *  第二轮路线规划    get_newroute
 *  OCR 读数字        WaitFor_OCR
 *  QR 码读取         WaitFor_QR
 *  启动流程          zhunbei
 *  路线连接          Connect
 *============================================================================*/



/*===== 调试：预设5个门颜色，door() 自动读取 =====*/
uint8_t color_flag[5] = {0, 0, 0, 0, 0};
#if DEBUG
uint8_t debug_color_flag[5] = {Red, Green, Yellow, Yellow, Red}; // 0:D2、1:D3、2:D4、3:D5、4:D1
uint8_t flag_line_clue    = 0;
uint8_t flag_clue_stage_A = 5;
uint8_t flag_clue_stage_B = 8;
// OCR 线索：P5/P6读clue_A，P7/P8读clue_B，treasure=clue_A+clue_B → 宝物平台编号
uint8_t flag_clue_A       = 1;
uint8_t flag_clue_B       = 2;
#else
uint8_t flag_line_clue    = 0;
uint8_t flag_clue_stage_A = 0;
uint8_t flag_clue_stage_B = 0;
// OCR 线索：P5/P6读clue_A，P7/P8读clue_B，treasure=clue_A+clue_B → 宝物平台编号
uint8_t flag_clue_A       = 0;
uint8_t flag_clue_B       = 0;
#endif

/*===== 导航标志位（无摄像头时手动预设）=====*/
// QR 码三位数：百位→flag_line_clue，十位→flag_clue_stage_A，个位→flag_clue_stage_B
// 例：QR 码 458 → flag_line_clue=4, flag_clue_stage_A=5, flag_clue_stage_B=8

uint8_t treasure = 0;			// 宝物平台编号 = flag_clue_A + flag_clue_B，自动计算
								// 调用：update_route_at_P7_for_treasure/8() → door() 确定宝物平台后回家路线
								//       Stage_HasTreasure() → Stage() 判断当前平台是否是宝物平台

uint8_t get_cude = 0;

static uint8_t Stage_HasTreasure(void)
{
	return ((nodes.nowNode.nodenum == P1 && treasure == 2) ||
		(nodes.nowNode.nodenum == P3 && treasure == 3) ||
		(nodes.nowNode.nodenum == P4 && treasure == 4) ||
		(nodes.nowNode.nodenum == P5 && treasure == 5) ||
		(nodes.nowNode.nodenum == P6 && treasure == 6));
}

static void Stage_CollectTreasure(void)
{
	CarBrake();
	send_play_specified_command(9);
	Chassis_Turn360_Blocking();
}

/**
 * @brief 巡线稳定时重置陀螺仪（连续N次中间巡线检测到线后执行mpuZreset）
 * @param required    连续稳定次数阈值
 * @param reset_angle 输出：重置时的角度
 * @return 1=已重置, 0=未达到条件
 */
static uint8_t GyroStableReset(uint8_t required, float *reset_angle)
{
	static uint8_t stable_times = 0;

	Cross_getline(&Cross_Scaner);
	if ((Cross_Scaner.detail & 0X0180) == 0X0180)
	{
		stable_times++;
		if (stable_times >= required)
		{
			*reset_angle = getAngleZ();
			stable_times = 0;
			send_play_specified_command(32);
			return 1;
		}
	}
	else
	{
		stable_times = 0;
	}
	return 0;
}

static uint8_t Stage_DetectedRamp(float distance)
{
	return (fabsf(Chassis_GetMileage()) >= distance||
		imu.pitch >= 10.0f ||
		Scaner.ledNum >= 4 ||
		Scaner.lineNum >= 2 ||
		Scaner.lineNum == 0 ||
		Scaner.ledNum == 0);
}

void RampCtrl_Blocking(RampDir_t dir, float init_speed, float angle,
                       float thresh1, float speed1,
                       float thresh2, float speed2,
                       float done_thresh, float GrayCorrectAngle,
                       float max_correction, float max_distance)
{
	enum { RAMP_INIT, RAMP_PHASE1, RAMP_PHASE2 }
	state = RAMP_INIT;

	if (GrayCorrectAngle!=0) Gray_Open();
	if (max_distance > 0) Chassis_ClearMileage();

	const float ramp_base_angle = angle;	// 初始朝向，用于修正限幅
	Chassis_MotorControl(is_Gyro, init_speed, init_speed, angle);
	while (1)
	{
		float pitch = imu.pitch;

		if (GrayCorrectAngle!=0)
		{
			angle += Gray_GetCorrectAngle(GrayCorrectAngle);
			// 限幅：累积修正不超过 ±max_correction，避免平移误触累加成偏角
			float drift = angle - ramp_base_angle;
			if (drift > max_correction) angle = ramp_base_angle + max_correction;
			if (drift < -max_correction) angle = ramp_base_angle - max_correction;
		}
		if (dir == RAMP_ASCEND)
		{
			switch (state)
			{
			case RAMP_INIT:
				Chassis_SetGyroAngle_Go(angle);
				if (pitch >= thresh1) {
					Chassis_SetTargetSpeed(speed1);
					state = RAMP_PHASE1;
				}
				break;
			case RAMP_PHASE1:
				Chassis_SetGyroAngle_Go(angle);
				if (pitch >= thresh2) {
					Chassis_SetTargetSpeed(speed2);
					state = RAMP_PHASE2;
				}
				break;
			case RAMP_PHASE2: 
				Chassis_SetGyroAngle_Go(angle);
				if (pitch <= done_thresh) {
					
					if (GrayCorrectAngle!=0) Gray_Close();
					return;
				}
				break;
			}
		}
		else /* RAMP_DESCEND */
		{
			switch (state)
			{
			case RAMP_INIT:
				Chassis_SetGyroAngle_Go(angle);
				if (pitch <= thresh1) {
					Chassis_SetTargetSpeed(speed1);
					state = RAMP_PHASE1;
				}
				break;
			case RAMP_PHASE1:
				Chassis_SetGyroAngle_Go(angle);
				if (pitch <= thresh2) {
					Chassis_SetTargetSpeed(speed2);
					state = RAMP_PHASE2;
				}
				break;
			case RAMP_PHASE2:
				Chassis_SetGyroAngle_Go(angle);
				if (pitch >= done_thresh) {
					if (GrayCorrectAngle!=0) Gray_Close();
					return;
				}
				break;
			}
		}
		// 距离超限保护：超过指定距离仍未达到俯仰角阈值则强制退出
		if (max_distance > 0 && fabsf(Chassis_GetMileage()) >= max_distance)
		{
			if (GrayCorrectAngle!=0) Gray_Close();
			return;
		}
		vTaskDelay(5);
	}
}

static void Stage_ScanAndRead(void)
{
	// 平台动作
	switch (nodes.nowNode.nodenum)
	{
	case P1: send_play_specified_command(5); break;
	case P3: send_play_specified_command(4); break;
	case P4: send_play_specified_command(3); break;
	case P5: send_play_specified_command(1); break;
	case P6: send_play_specified_command(2); break;
	default: break;
	}
	//Arrived_Stage();
	//vTaskDelay(500);

	// 宝物线索：由标志位计算
	if (treasure == 0)
		treasure = flag_clue_A + flag_clue_B;

	// P1 路线更新
	if (nodes.nowNode.nodenum == P1)
		update_route_at_P1();
}

/*平台 - 不包括P2*/
void Stage(void)
{
	enum {
		STAGE_ASCEND,    // 上坡：RampCtrl_Blocking 处理
		STAGE_TOP,       // 桥面行驶+站起+撞击
		STAGE_SCAN,      // 后退+OCR/QR+转身180°
		STAGE_TREASURE,  // 下坡：RampCtrl_Blocking 处理
		STAGE_DONE       // 清标志，结束
	} state = STAGE_ASCEND;

	uint8_t sub_stage = 0;
	
	float oringinal_angle = 0;
	
	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);//25
	Chassis_ClearMileage();

	while (state != STAGE_DONE)
	{
		switch (state)
		{
		case STAGE_ASCEND:
			if (Stage_DetectedRamp(20.0f))
			{
				oringinal_angle = getAngleZ();
				RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_high, oringinal_angle,
					Begin_up, UpDownStage_Speed_low, up_pitch, UpDownStage_Speed_low, After_up, 0.1, 10.0f, 0.0f);

				Chassis_MotorControl(is_Gyro, GoStage_Speed, GoStage_Speed, oringinal_angle);
				state = STAGE_TOP;
			}
			break;

		case STAGE_TOP:
			if (sub_stage == 0)
			{
				Chassis_DisableStallProtection();
				Chassis_DriveDistance_Blocking(is_Gyro,27,GoStage_Speed,oringinal_angle,0);
				CarBrake();
				sub_stage = 1;
				
			}
			else if(sub_stage == 1)
			{		
				mpuZreset(get_latest_yaw(), nodes.nowNode.angle);
				// 后退一段距离
				Chassis_DriveDistance_Blocking(is_Gyro,10,-GoStage_Speed,getAngleZ(),0);
				CarBrake();
				sub_stage=0;
				state = STAGE_SCAN;
			}
			break;

		case STAGE_SCAN:
			// P1 路线更新：根据 flag_line_clue 标志位决定去 P3/P4 或跳过
			if (nodes.nowNode.nodenum == P1 && treasure == 0)
				update_route_at_P1();

			if(Stage_HasTreasure())
				Stage_CollectTreasure();

			// 转身180
			Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+180, getAngleZ(), 20.0f);
			Chassis_EnableStallProtection();
			state = STAGE_TREASURE;
			break;

		case STAGE_TREASURE:
			oringinal_angle = getAngleZ();
			
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, getAngleZ(),
				Begin_down, UpDownStage_Speed_low, down_pitch, UpDownStage_Speed_high, After_down-8, 0.1, 10.0f, 0.0f);

			Chassis_MotorControl(is_Line, SPEED1, SPEED1, 0);
			state = STAGE_DONE;
			break;
		default:
			break;
		}
		vTaskDelay(2);
	}

	nodes.nowNode.function = 0;
	cross_event |= CROSS_EVENT_ARRIVED;
}

/*平台 - P2 — 状态机版本，与 Stage() 格式一致 */
void Stage_P2(void)
{
	enum {
		P2_ASCEND,   // 上坡：Stage_DetectedRamp → RampCtrl_Blocking
		P2_TOP,      // 平台行驶+刹车+Backtimes判断
		P2_TURN,     // 转180°
		P2_DONE      // 清理收尾
	} state = P2_ASCEND;

	//static uint8_t Backtimes = 0; // 回来次数 - 为1时代表第二轮回家
	float oringinal_angle = 0;

	Chassis_MotorControl(is_Line,UpDownStage_Speed_high, UpDownStage_Speed_high, 0);
	Chassis_ClearMileage();

	while (state != P2_DONE)
	{
		switch (state)
		{
		case P2_ASCEND:
			if (Stage_DetectedRamp(20.0f))
			{
				oringinal_angle = getAngleZ();
				RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_high, oringinal_angle,
					Begin_up, UpDownStage_Speed_low, up_pitch, UpDownStage_Speed_low, After_up, 0.05, 10.0f, 0.0f);

				Chassis_MotorControl(is_Gyro, GoStage_Speed, GoStage_Speed, oringinal_angle);			
				state = P2_TOP;
			}
			break;

		case P2_TOP:
			Chassis_DriveDistance_Blocking(is_Gyro, 15, GoStage_Speed, getAngleZ(), 0);
			CarBrake();
			vTaskDelay(200);
			state = P2_TURN;
			break;

		case P2_TURN:
			Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 180, getAngleZ(),20.0f);
			CarBrake();
			state = P2_DONE;
			break;

		default:
			break;
		}
		vTaskDelay(2);
	}

	
	nodes.nowNode.function = 0;	// 清除障碍标志
	cross_event |= CROSS_EVENT_ARRIVED;	// 到达路口
}

/*长桥*/
/** 桥面修正参数 */
#define BRIDGE_CENTERED_THRESHOLD   30      // 连续无红外信号次数（~20-100ms）
#define BRIDGE_EMERGENCY_ANGLE      5.0f    // 巡线板最外侧扫到红线时的硬跳角度

void Barrier_Bridge(void)
{
	enum {
		BRIDGE_APPROACH,    // 近桥：寻迹前进，检测到桥条件后切换
		BRIDGE_ASCEND,      // 上桥：RampCtrl_Blocking 处理上坡
		BRIDGE_ON_BRIDGE_TOP, // 桥面连续修正+加速
		BRIDGE_ON_BRIDGE,   // 桥上+下坡：RampCtrl_Blocking 处理下坡
		BRIDGE_DONE         // 完成
	} state = BRIDGE_APPROACH;

	int centered_samples = 0;
	float origin_angle = 0.0f;

	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
	Chassis_ClearMileage();
	static uint8_t is_emergency = 0;
	while (state != BRIDGE_DONE)
	{
		switch (state)
		{
		case BRIDGE_APPROACH:
			GyroStableReset(50, &origin_angle);

			if (Stage_DetectedRamp(15.0f))//检测到桥
			{
				if(origin_angle == 0)origin_angle = getAngleZ();				
				Chassis_MotorControl(is_Gyro, SPEED0, SPEED0, origin_angle);
				state = BRIDGE_ASCEND;
			}
			break;

		case BRIDGE_ASCEND://上桥
			//上桥上一半
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_high, origin_angle,
				Begin_up, UpDownStage_Speed_high, up_pitch-5, UpDownStage_Speed_low, up_pitch+20, 0, 10.0f, 0.0f);
			//加一点修正
			Chassis_ClearMileage();
	
			while (fabsf(Chassis_GetMileage()) < 15)
			{		
				Chassis_CorrectByInfrared(0.07f, 2.0f, 2.0f);
				vTaskDelay(5);
			}
			//上桥结束检测
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, getAngleZ(),
				0, UpDownStage_Speed_low, 0, UpDownStage_Speed_low, After_up, 0, 10.0f, 0.0f);

			Chassis_ClearMileage();
			state = BRIDGE_ON_BRIDGE_TOP;
			break;

		case BRIDGE_ON_BRIDGE_TOP:
		
			
			Cross_getline(&Cross_Scaner);	// 桥上为陀螺仪模式，Scaner 不更新，主动拍快照
			float mileage_br = fabsf(Chassis_GetMileage());

			//第1层：巡线板最外侧紧急处理
			if (Cross_Scaner.detail & 0x7800)
			{
				if(is_emergency<=10)is_emergency++;
				if(is_emergency == 10)
				{
					centered_samples = 0;
					send_play_specified_command(33);
					angle.AngleG = getAngleZ() - BRIDGE_EMERGENCY_ANGLE;
					Chassis_SetTargetSpeed(UpDownStage_Speed_low);
				}
			}

			else if (Cross_Scaner.detail & 0x007E)
			{
				if(is_emergency<=10)is_emergency++;
				if(is_emergency == 10)
				{
					centered_samples = 0;
					send_play_specified_command(33);
					angle.AngleG = getAngleZ() + BRIDGE_EMERGENCY_ANGLE;
					Chassis_SetTargetSpeed(UpDownStage_Speed_low);
				}
			}
			else
			{
				is_emergency = 0;
				// 第2层+第3层：红外修正和居中检测
				get_Infrared();
				if (infrared.head_left == 0 && infrared.head_right == 0)
				{
					centered_samples++;
					if (centered_samples >= BRIDGE_CENTERED_THRESHOLD)
						Chassis_SetTargetSpeed(SPEED2);
					else
						Chassis_SetTargetSpeed(SPEED1);
				}
				else
				{
					centered_samples = 0;
					if(mileage_br<=15.0f){
						Chassis_CorrectByInfrared(0.05f, 1.5f, 1.0f);
					}
					else{Chassis_CorrectByInfrared(0.03f, 1.5f, 1.0f);}
					
					Chassis_SetTargetSpeed(SPEED1);
				}
			}
			// 距离退出（保险兜底）
			
			if (mileage_br >= 75)
			{
				centered_samples = 0;
				state = BRIDGE_ON_BRIDGE;
			}
			else if (mileage_br >= 70)
			{
				Chassis_SetTargetSpeed(UpDownStage_Speed_low);
			}
			break;
		

		case BRIDGE_ON_BRIDGE:

			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, getAngleZ(),
				Begin_down, UpDownStage_Speed_low, down_pitch+5, SPEED0, down_pitch-20,0, 0, 0.0f);//下坡下一半

			//加一点修正
			Chassis_ClearMileage();
			get_Infrared();
			while (fabsf(Chassis_GetMileage()) < 15)
			{	
				Chassis_CorrectByInfrared(0.05f, 2.0f, 1.0f);
				vTaskDelay(5);
			}

			//下坡结束检测
			RampCtrl_Blocking(RAMP_DESCEND, SPEED0, getAngleZ(),
				0, SPEED0, 0, SPEED0, After_down,0, 0, 0.0f);

			Chassis_MotorControl(is_Line, SPEED1, SPEED1, 0);
			nodes.nowNode.function = 0;
			cross_event |= CROSS_EVENT_ARRIVED;
			state = BRIDGE_DONE;
			break;

		default:
			state = BRIDGE_DONE;
			break;
		}
		vTaskDelay(2);
	}
}

/*楼梯*/
void Barrier_Hill(void)
{
	enum {
		HILL_APPROACH,   // 接近：寻迹+陀螺仪校准，检测坡道
		HILL_ASCEND,     // 上坡：灰度修正
		HILL_DESCEND,    // 下坡：灰度修正
		HILL_DONE        // 完成
	} state = HILL_APPROACH;

	float origin_angle = 0.0f;

	Chassis_MotorControl(is_Line, 15, 15, 0);
	//vTaskDelay(10);//刚进入is_line,scanner可能还没数据，先等motortask
	Chassis_OverrideGyroPid(4,0,70,50);//上坡陀螺参数，增加kp和kd提高陀螺响应，防止上坡时姿态失稳
	Chassis_ClearMileage();
	while (state != HILL_DONE)
	{
		switch (state)
		{
		case HILL_APPROACH:
			GyroStableReset(50, &origin_angle);
				
			if (Stage_DetectedRamp(15.0f))
			{
				if (origin_angle == 0) origin_angle = getAngleZ();
 			
				Chassis_MotorControl(is_Gyro, 15, 15, origin_angle);
			
				state = HILL_ASCEND;
			}
			break;

		case HILL_ASCEND:
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, origin_angle,
				basic_p+5, UpDownStage_Speed_low, basic_p+15, UpDownStage_Speed_low, basic_p+5, 0.10, 15.0f, 0.0f);
	
			state = HILL_DESCEND;
			break;

		case HILL_DESCEND:
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, origin_angle,
				basic_p, UpDownStage_Speed_low, basic_p-10, UpDownStage_Speed_low, basic_p-3, 0.10, 15.0f, 35.0f);
  
			state = HILL_DONE;
			break;

		default:
			Chassis_MotorControl(is_Line, SPEED1, SPEED1, 0);
			Chassis_RestoreGyroPid();
			state = HILL_DONE;
			break;
		}
		vTaskDelay(2);
	}
	nodes.nowNode.function = 0; 	// 清除障碍标志
	cross_event |= CROSS_EVENT_ARRIVED;		 	// 到达路口
}

/* 刀山专属定中修正：检测左/右起第3、4个传感器触碰红线 */
static void Sword_CorrectByScanner(float correct_angle)
{
	Cross_getline(&Cross_Scaner);

	// 偏右 → 向左修
	if (Cross_Scaner.detail & 0x00F0)
		angle.AngleG += correct_angle;
	// 偏左 → 向右修
	else if (Cross_Scaner.detail & 0x0F00)
		angle.AngleG -= correct_angle;
}

/*刀山 — */
void Sword_Mountain(void)
{
	enum {
		SM_APPROACH,	// 0. 低速巡线接近，定中录角
		SM_CLIMB_UP,	// 1. 上坡（陀螺仪 + 循迹板修正）
		SM_ON_TOP,		// 2. 平台行驶（陀螺仪 + 循迹板修正）
		SM_DESCEND,		// 3. 下坡（陀螺仪 + 循迹板修正）
		SM_DONE
	} state = SM_APPROACH;

	float recorded_angle = 0;
	uint8_t angle_recorded = 0,is_up = 0;
	uint16_t approach_timeout = 0;

	/* 初始：低速强巡线，忽略两侧红线 */
	
	Chassis_MotorControl(is_Line, 15, 15, 0);
	Chassis_OverrideLinePid(25.0f,0, 150.0f, 7);
	Chassis_OverrideGyroPid(4, 0, 70, 5);
	//buzzer_on();

	while (state != SM_DONE)
	{
		switch (state)
		{
		case SM_APPROACH:
		{
			// 连续 50 次中心传感器确认 → 记录角度
			if (!angle_recorded)
			{
				if(GyroStableReset(100, &recorded_angle))
				{
					angle_recorded = 1;
				}
			}

			// 检测到刀山
			Cross_getline(&Cross_Scaner);
			if (Cross_Scaner.ledNum > 3)
			{
				if (!angle_recorded)
					recorded_angle = getAngleZ();

				Chassis_MotorControl(is_Gyro, Gyro_Speed , Gyro_Speed , recorded_angle);
				Chassis_ClearMileage();
				state = SM_CLIMB_UP;
				break;
			}
			break;
		}

		case SM_CLIMB_UP:
			// pitch 回落 or 超时 → 到顶
			if (imu.pitch >= After_up)
			{
				is_up = 1;
			}
			if (is_up && imu.pitch < After_up )
			{
				state = SM_ON_TOP;
			}
			break;

		case SM_ON_TOP:
			if(fabsf(Chassis_GetMileage()) < 15.0f ){
				//Sword_CorrectByScanner(0.05f);
			}
			else if(fabsf(Chassis_GetMileage()) >= 15.0f&&fabsf(Chassis_GetMileage()) < 45.0f)
			{
				Chassis_MotorControl(is_No, Gyro_Speed, Gyro_Speed, 0);
			}
			else
			{
				Chassis_MotorControl(is_Gyro, Gyro_Speed , Gyro_Speed , recorded_angle);
			}

			// if(fabsf(Chassis_GetMileage()) >= 15.0f&&fabsf(getAngleZ() - recorded_angle)>5)
			// {
			// 	float yaw=getAngleZ();
			// 	CarBrake();
			// 	Chassis_DriveDistance_Blocking(is_Gyro,5,-Gyro_Speed,yaw,0);
			// 	Chassis_Turn_By_StopGyro_Blocking(recorded_angle,yaw,10);
			// 	Chassis_DriveDistance_Blocking(is_Gyro,10,-Gyro_Speed,yaw,0);
			// }

			// 平台走完 or pitch 变负（开始下坡）
			if (fabsf(Chassis_GetMileage()) > 70.0f || imu.pitch < After_down)
			{
				state = SM_DESCEND;
			}
			break;

		case SM_DESCEND:

			// pitch 回升 or 超时 → 到底
			if (fabsf(Chassis_GetMileage()) > 70.0f ||imu.pitch >= After_down)
			{
				state = SM_DONE;
			}
			
			break;		
		}
		vTaskDelay(2);
	}

	/* 收尾 */
	Chassis_RestoreLinePid();
	Chassis_RestoreGyroPid();
	Chassis_MotorControl(is_Line, SPEED1, SPEED1, 0);
	nodes.nowNode.function = 0;
	cross_event |= CROSS_EVENT_ARRIVED;
}

/*珠峰 */
void Barrier_HighMountain(void)
{
	enum {
		HM_APPROACH,      // 巡线接近，检测坡底
		HM_ASCEND_1,      // 第一段上坡：RampCtrl_Blocking
		HM_FLAT,          // 中间平地：陀螺仪直走
		HM_ASCEND_2,      // 第二段上坡：RampCtrl_Blocking
		HM_IMPACT,        // 撞挡板 + 后退 + 转身 + 宝物
		HM_DESCEND_1,     // 第一段下坡：RampCtrl_Blocking
		HM_DESCEND_FLAT,  // 下坡中间平地：陀螺仪直走
		HM_DESCEND_2,     // 第二段下坡：RampCtrl_Blocking
		HM_DONE
	} state = HM_APPROACH;

	float origin_angle = 0.0f;
	uint8_t sub_stage = 0;

	Chassis_OverrideGyroPid(4, 0, 70, 10);
	Chassis_MotorControl(is_Line, 15, 15, 0);
	Chassis_ClearMileage();

	while (state != HM_DONE)
	{
		switch (state)
		{
		case HM_APPROACH:
			if (Stage_DetectedRamp(30.0f))
			{
				state = HM_ASCEND_1;
			}
			break;

		case HM_ASCEND_1:
			//让车抬起后马上退出
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_high, getAngleZ(),
				Begin_up, UpDownStage_Speed_high, up_pitch, 20, up_pitch+30, 0.07f, 10.0f, 20.0f);
			//用循迹走
			Chassis_DriveDistance_Blocking(is_Line, 45, 20, 0, 0);
			//检测上坡结束
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, getAngleZ(),
				Begin_up, UpDownStage_Speed_low, up_pitch, UpDownStage_Speed_low, After_up, 0.07f, 10.0f, 0.0f);
			state = HM_FLAT;
			break;

		case HM_FLAT:
			Chassis_MotorControl(is_Gyro,UpDownStage_Speed_high , UpDownStage_Speed_high, getAngleZ());
			if (imu.pitch >= Begin_up)
			{
				state = HM_ASCEND_2;
			}
			break;

		case HM_ASCEND_2:
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_high, getAngleZ(),
				Begin_up, UpDownStage_Speed_high, up_pitch, 20, up_pitch+30, 0.07f, 10.0f, 20.0f);
			Chassis_DriveDistance_Blocking(is_Line, 45, 20, 0, 0);
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, getAngleZ(),
				Begin_up, UpDownStage_Speed_low, up_pitch, UpDownStage_Speed_low, After_up, 0.07f, 10.0f, 0.0f);
			state = HM_IMPACT;
			break;

		case HM_IMPACT:
			if (sub_stage == 0)
			{
				Chassis_DriveDistance_Blocking(is_Gyro, 27, GoStage_Speed, getAngleZ(), 0);
				CarBrake();
				sub_stage = 1;
			}
			else if (sub_stage == 1)
			{
				mpuZreset(get_latest_yaw(), nodes.nowNode.angle);
				vTaskDelay(100);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -GoStage_Speed, getAngleZ(), 0);
				CarBrake();
				// 宝物线索：由标志位计算，不依赖摄像头
				if (treasure == 0)
					treasure = flag_clue_A + flag_clue_B;
				if (map.routetime == 0)
					update_route_at_P8_for_treasure();

				send_play_specified_command(12);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 180, getAngleZ(), 20.0f);
				origin_angle = getAngleZ();
				sub_stage = 0;
				state = HM_DESCEND_1;
			}
			break;

		case HM_DESCEND_1:
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, origin_angle,
				Begin_down, UpDownStage_Speed_low, down_pitch, 20, down_pitch-30, 0.07f, 10.0f, 30.0f);
			Chassis_DriveDistance_Blocking(is_Line, 40, 20, 0, 0);
			RampCtrl_Blocking(RAMP_DESCEND, 20, origin_angle,
				Begin_down, 20, down_pitch, 20, After_down, 0.07f, 10.0f, 0.0f);
			state = HM_DESCEND_FLAT;
			break;

		case HM_DESCEND_FLAT:
			Chassis_MotorControl(is_Gyro, UpDownStage_Speed_low, UpDownStage_Speed_low, origin_angle);
			if (imu.pitch <= Begin_down)
			{
				state = HM_DESCEND_2;
			}
			break;

		case HM_DESCEND_2:
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, origin_angle,
				Begin_down, UpDownStage_Speed_low, down_pitch, 20, down_pitch-30, 0.07f, 10.0f, 20.0f);
			Chassis_DriveDistance_Blocking(is_Line, 40, 20, 0, 0);
			RampCtrl_Blocking(RAMP_DESCEND, 20, origin_angle,
				Begin_down, 20, down_pitch, 20, After_down, 0.07f, 10.0f, 0.0f);
			state = HM_DONE;
			break;

		default:
			state = HM_DONE;
			break;
		}
		vTaskDelay(2);
	}

	Chassis_RestoreGyroPid();
	nodes.nowNode.function = 0;
	cross_event |= CROSS_EVENT_ARRIVED;
}


/*长直立景点*/
void view(void)
{
	motor_all.Cspeed = Low_Speed;
	float origin_c = motor_all.Cincrement;

	while (Infrared_ahead == 0) // 撞挡板
		vTaskDelay(5);
	
	Want2Go(10);
	Chassis_ClearMileage();
	send_play_specified_command(6);
	CarBrake();
	vTaskDelay(100);
	
	mpuZreset(get_latest_yaw(), nodes.nowNode.angle);  //陀螺仪校正
	Chassis_ClearMileage();
	Chassis_MotorControl(is_Free,-2000,-2000,0);
	Want2Go(7.5);
	CarBrake();
	vTaskDelay(100);
	Turn_Angle_Relative(179);
	while (fabs(angle.AngleT - getAngleZ()) > 2)
		vTaskDelay(2);
	CarBrake();
	vTaskDelay(100);
	motor_pid_clear();
	
	motor_all.Cincrement = 0.05;
	motor_all.Cspeed = nodes.nowNode.speed;
	Chassis_SetMode(is_Line);
		
	nodes.nowNode.function = NONE;
	motor_all.Cincrement = origin_c;
	cross_event |= CROSS_EVENT_ARRIVED; // 到达路口
}

/*短直立景点*/
void view1()
{
	motor_all.Cspeed = Gyro_Speed;

	/*撞挡板*/
	while (Infrared_ahead == 0)
		vTaskDelay(5);
	Want2Go(10);
	send_play_specified_command(6);
	CarBrake();
	vTaskDelay(200);

	nodes.nowNode.function = 0;
	cross_event |= CROSS_EVENT_ARRIVED; // 到达路口
}

/*退短直立景点 - 红外检测*/
void back(void)
{
	/*后退一段距离*/
	Chassis_MotorControl(is_Free, -2000, -2000, 0);
	if(nodes.lastNode.nodenum == S5)
		Want2Go(20);
	else if(nodes.lastNode.nodenum == S4)
		Want2Go(10);
	Chassis_ClearMileage();
	CarBrake();
	vTaskDelay(100);

	Turn_Angle_Relative(need2turn(getAngleZ(), nodes.nextNode.angle));
	while (fabs(need2turn(getAngleZ(), nodes.nextNode.angle)) > 2)
	{
		vTaskDelay(2);
		getline_error();
		if (Scaner.lineNum == 1 && ((Scaner.detail & 0x180) != 0) && (fabs(need2turn(angle.AngleT, getAngleZ())) < fabs(need2turn(angle.AngleT, nodes.nowNode.angle)) * 0.15f))
			break;
	}
	Chassis_MotorControl(is_Line, 28, 28, 0);

	nodes.nowNode.function = 0;
	cross_event |= CROSS_EVENT_ARRIVED; // 到达路口
}

/*波浪板 — 状态机版本*/
void Barrier_WavedPlate(float lenght)
{
	enum {
		WP_APPROACH,   // 巡线接近，Stage_DetectedRamp 检测波浪板入口
		WP_DRIVE,      // RampCtrl_Blocking 用不可能俯仰角直走 lenght 距离
		WP_DONE        // 清理收尾
	} state = WP_APPROACH;

	Chassis_MotorControl(is_Line, 15, 15, 0);
	Chassis_ClearMileage();

	while (state != WP_DONE)
	{
		switch (state)
		{
		case WP_APPROACH:
			if (Stage_DetectedRamp(30.0f))
			{
				//buzzer_on();
				state = WP_DRIVE;
			}
			break;

		case WP_DRIVE:
			// 俯仰角阈值设 100（不可能达到），只靠 max_distance=lenght 退出
			RampCtrl_Blocking(RAMP_ASCEND, BL_Speed, getAngleZ(),
				100, BL_Speed, 100, BL_Speed, 100, 0, 0, lenght);
			//buzzer_off();
			state = WP_DONE;
			break;

		default:
			state = WP_DONE;
			break;
		}
		vTaskDelay(2);
	}

	/*出板清理*/
	nodes.nowNode.function = 0;
	cross_event |= CROSS_EVENT_ARRIVED;
}

/*南极*/
void South_Pole(void)
{	
	enum {
		SP_APPROACH,   // 巡线接近，检测坡底
		SP_ASCEND,     // RampCtrl_Blocking 上坡 + 灰度修正
		SP_IMPACT,     // 撞挡板 + 后退 + 转身（同 Stage STAGE_TOP+SCAN）
		SP_DESCEND,    // RampCtrl_Blocking 下坡 + 灰度修正
		SP_DONE
	} state = SP_APPROACH;

	float origin_angle = 0.0f;
	uint8_t sub_stage = 0;

	Chassis_OverrideGyroPid(4, 0, 70, 50);
	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
	Chassis_ClearMileage();

	while (state != SP_DONE)
	{
		switch (state)
		{
		case SP_APPROACH:
			if (Stage_DetectedRamp(10.0f))
			{
				origin_angle = getAngleZ();
				state = SP_ASCEND;
			}
			break;

		case SP_ASCEND:
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_high, origin_angle,
				Begin_up, UpDownStage_Speed_high, up_pitch, UpDownStage_Speed_low, After_up, 0.05f, 10.0f, 0.0f);
			state = SP_IMPACT;
			break;

		case SP_IMPACT:
			if (sub_stage == 0)
			{
				Chassis_DisableStallProtection();
				Chassis_DriveDistance_Blocking(is_Gyro, 27, GoStage_Speed, origin_angle, 0);
				CarBrake();
				sub_stage = 1;
			}
			else if (sub_stage == 1)
			{
				mpuZreset(get_latest_yaw(), nodes.nowNode.angle);
				vTaskDelay(100);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -GoStage_Speed, getAngleZ(), 0);
				CarBrake();
				// if (treasure == 0)
				// 	treasure = flag_clue_A + flag_clue_B;
				// if (map.routetime == 0 && flag_clue_stage_B == 7)
				// 	update_route_at_P7_for_treasure();
				send_play_specified_command(12);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 180, getAngleZ(), 20.0f);
				Chassis_DisableStallProtection();
				sub_stage = 0;
				state = SP_DESCEND;
			}
			break;

		case SP_DESCEND:
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, getAngleZ(),
				Begin_down, UpDownStage_Speed_low, down_pitch, UpDownStage_Speed_high, After_down, 0.04f, 10.0f, 0.0f);
			Chassis_MotorControl(is_Line, SPEED1, SPEED1, 0);
			state = SP_DONE;
			break;

		default:
			state = SP_DONE;
			break;
		}
		vTaskDelay(2);
	}

	Chassis_RestoreGyroPid();
	nodes.nowNode.function = 0;
	cross_event |= CROSS_EVENT_ARRIVED;
}


/** 从 route[offset] 开始复制 src[]，遇 0xFF 终止 */
static void load_route_at(uint8_t offset, const u8* src)
{
	for(uint8_t i = 0; i < 50; i++)
	{
		route[offset + i] = src[i];
		if(src[i] == 0xFF)
			break;
	}
}

void update_route_at_P7_for_treasure(void)
{
	//map.point = 1;
	if(treasure != 0&&color_flag[0] == Green)//D2绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N5,N4,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
		}
	}
	if(treasure != 0&&color_flag[1] == Green)//D3绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N5,N4,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N8,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	     }
    }
	if(treasure != 0&&color_flag[2] == Green)//D4绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N8,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	    }
	}
	if(treasure != 0&&((color_flag[0] == Yellow)||(color_flag[1] == Yellow)))//D2D3黄灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N11,N10,N3,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	    }
	}
	if(treasure != 0&&color_flag[2] == Yellow)//D4黄灯D5必绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,C5,N15,N10,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,C5,N15,N10,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N11,N10,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,C5,N15,N10,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	    }
	}
}
void update_route_at_P8_for_treasure(void)
{
	if(treasure != 0&&color_flag[0] == Green)//D2绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N11,N12,N5,N4,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N11,N12,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N11,N12,N13,P5,N13,N12,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N11,N12,N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
		}
	}
	if(treasure != 0&&color_flag[1] == Green)//D3绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N5,N4,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N11,N12,N13,P5,N13,N12,N8,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	     }
    }
	if(treasure != 0&&color_flag[2] == Green)//D4绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N11,N12,N13,P5,N13,N12,N8,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	    }
	}
	if(treasure != 0&&((color_flag[0] == Yellow)||(color_flag[1] == Yellow)))//D2D3黄灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N11,N10,N3,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	    }
	}
	if(treasure != 0&&color_flag[2] == Yellow)//D4黄灯D5必绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N11,N10,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	    }
	}
}
/*跷跷板*/
void QQB_1(void)
{
	enum {
		QQB_INIT,
		QQB_WAIT_PITCH,
		QQB_GYRO,
		QQB_WAIT,
		QQB_RECOVERY,
		QQB_DONE
	} state = QQB_INIT;

	uint8_t is_emergency = 0;
	uint8_t seen_negative = 0;
	uint16_t break_cnt = 0;
	while(state!=QQB_DONE){
		switch (state)
		{
		case QQB_INIT:
			send_play_specified_command(7);
			//改变小车循迹中心，根据实际情况硬补偿
			//Chassis_SetCatchSensorNum(line_weight_default[7]);
			//改变循迹模式为左边循迹
			Chassis_SetTrackMode(TRACK_LEFT_EDGE);
			
			//改变电机控制模式为巡线模式
			Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
			Chassis_OverrideLinePid(15,0.01,50,25);

			//等待小车行驶10cm后，改变循迹模式为中间循迹
			Chassis_ClearMileage();
			while(Chassis_GetMileage() < 40)vTaskDelay(2);	
			Chassis_SetTrackMode(TRACK_NEAR_CENTER);
			Chassis_ClearMileage();
			
			state = QQB_WAIT_PITCH;
			break;

		case QQB_WAIT_PITCH:
			//防止循迹受到旁边红线的干扰
			if(Chassis_GetMileage() > 10 &&imu.pitch>=After_up)Chassis_SetEdgeIgnore(4);
			//等待对其
			if ((imu.yaw >=88&&imu.yaw <=92)||(imu.yaw <=-88&&imu.yaw >=-92))
			{		
				Chassis_OverrideGyroPid(4, 0, 70, 10);  
				Chassis_MotorControl(is_Gyro, 15, 15, getAngleZ()>0?90:-90);
				Chassis_CorrectByInfrared(0.05f, 1.5f, 1.5f);	
			}
			//等待小车爬上跷跷板，俯仰角大于 up_pitch 进入下一状态
			if(imu.pitch>up_pitch)
			{
				Chassis_ClearMileage();	
				CarBrake();	
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ()>0?90:-90, getAngleZ(), 30.0f);
				is_emergency=1;
				Cross_getline(&Cross_Scaner);				
				state = QQB_GYRO;
			}
			break;

		case QQB_GYRO:
		{
			
			//第1层：巡线板最外侧紧急处理
			if ((Cross_Scaner.detail & 0x3C00)&&is_emergency==1)
			{	
				is_emergency++;
				send_play_specified_command(33);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 15, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -SPEED0, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() - 15, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 18, SPEED0, getAngleZ(), 0);
			}
			else if ((Cross_Scaner.detail & 0x003C)&&is_emergency==1)
			{			
				is_emergency++;
				send_play_specified_command(33);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() - 15, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -SPEED0, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 15, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 18, SPEED0, getAngleZ(), 0);
			}
			else if ((Cross_Scaner.detail & 0xF000)&&is_emergency==1)
			{	
				is_emergency++;
				send_play_specified_command(33);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() - 8, getAngleZ(), 10.0f);
			}
			else if ((Cross_Scaner.detail & 0x000F)&&is_emergency==1)
			{			
				is_emergency++;
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 8, getAngleZ(), 10.0f);
			}
			else if(is_emergency){
			is_emergency=0;
			Chassis_MotorControl(is_Gyro, 15, 15, getAngleZ()>0?90:-90);
			Chassis_ClearMileage();
			}

			if(is_emergency==0)Chassis_CorrectByInfrared(0.05f, 1.5f, 1.5f);

			if(imu.pitch>70){
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -SPEED0, getAngleZ(), 0);
				Chassis_DriveDistance_Blocking(is_Gyro, 5, SPEED0, getAngleZ(), 0);
			}

			if(Chassis_GetMileage() > 40 && is_emergency == 0)
			{
				CarBrake();
				state = QQB_WAIT;		
				break;
			}
			break;
		}
		case QQB_WAIT:
			{
			Chassis_CorrectByInfrared(0.05f, 1.5f, 1.5f);
			float p = imu.pitch;
			if(p> up_pitch)break_cnt++;
			if(break_cnt > 500){Chassis_DriveDistance_Blocking(is_Gyro, 5, 10,getAngleZ()>0?90:-90, 0);break_cnt=0;}

			if(p < up_pitch&&seen_negative==0){CarBrake(); break_cnt = 0;} 
			if (p < After_down)seen_negative = 1;	
			if (seen_negative==1)
			{ 
				Chassis_MotorControl(is_Gyro, 15, 15, getAngleZ());		
				seen_negative=2;				
			}
			if(seen_negative==2)
			{			
				if(p > After_down-5) 
				{	
					Chassis_RestoreGyroPid();
					Chassis_MotorControl(is_Gyro, 15, 15, getAngleZ());	
					Chassis_Turn_By_Gyro_Blocking(getAngleZ()>0?140:-40, getAngleZ(), 40.0f);	
					state = QQB_RECOVERY;
				}	
			}
					
			break;
			}
		case QQB_RECOVERY:

			state = QQB_DONE;
			break;

		}  
		vTaskDelay(2);
	}  
	Chassis_SetEdgeIgnore(0);
	Chassis_SetCatchSensorNum(line_weight_default[12]);
	Chassis_SetTrackMode(TRACK_LEFT_EDGE);
	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
	Chassis_OverrideLinePid(16,0.03f,50,30);
	Chassis_ClearMileage();
	uint8_t dis = getAngleZ()>0?60:35;
	while(Chassis_GetMileage() < dis)vTaskDelay(2);
	Chassis_RestoreLinePid();
	
	nodes.nowNode.function = 0;
	cross_event |= CROSS_EVENT_ARRIVED;
	
}

/*读颜色传感器，返回颜色值（0=超时/未设置, 1=绿, 2=黄, 3=红）*/
static uint8_t Door_ReadColor(uint8_t door_state)
{
	static const uint8_t state_to_idx[] = {0, 1, 2, 3, 2}; // D2→0, D3→1, D4→2, D5→3, D4_AGAIN→2
#if DEBUG
	return debug_color_flag[state_to_idx[door_state]];
#else
	/* TODO: 读取真实左右颜色传感器
	 *   左传感器 → UART4_RX (PC11) 读取颜色值
	 *   右传感器 → UART5_RX (PD2) 读取颜色值
	 *   返回值：1=Green, 2=Yellow, 3=Red, 0=未读到
	 */
	return 0;
#endif
}

/*红绿灯辅助：配置节点直接通行（设 function=NONE + speed + step）*/
static void door_set_pass_node(uint8_t a, uint8_t b, uint16_t step, float speed)
{
	uint8_t idx = getNextConnectNode(a, b);
	Node[idx].function = NONE;
	Node[idx].speed = speed;
	Node[idx].step = step;
}

/*红绿灯辅助：红灯后退+转头+重定向到目标节点*/
static void door_retreat(uint8_t a, uint8_t b)
{
	Chassis_DriveDistance_Blocking(is_Gyro, 50, -SPEED2, getAngleZ(), 0);
	nodes.lastNode = nodes.nowNode;
	nodes.nowNode = Node[getNextConnectNode(a, b)];
	Chassis_Brake();
	Chassis_Turn_By_StopGyro_Blocking(nodes.nowNode.angle, getAngleZ(), 30.0f);
}

/*看红绿灯 — 状态机*/
void door()
{
	enum DoorState {
		DOOR_D2 = 0,   // 看D2
		DOOR_D3,        // 看D3
		DOOR_D4,        // 看D4
		DOOR_D5_BACK,   // 看D5
		DOOR_D4_BACK    // 看D4回退
	};
	static enum DoorState state = DOOR_D2;

	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
	while (Scaner.ledNum < 8)
		vTaskDelay(2);

	CarBrake();
	Chassis_Turn_By_StopGyro_Blocking(nodes.nowNode.angle, getAngleZ(), 30.0f);
	vTaskDelay(500);
	uint8_t door_color = Door_ReadColor(state);

	/*公共初始化*/
	map.point = 0;
	route[0] = 0xFF;

	switch (state)
	{
	case DOOR_D2:
		color_flag[0] = door_color;
		if (color_flag[0] == Red)
		{
			send_play_specified_command(11);
			door_retreat(N5, N8);
			cross_event |= CROSS_EVENT_DOOR;
			state = DOOR_D3;
		}
		else if (color_flag[0] == Green)
		{
			send_play_specified_command(8);
			door_set_pass_node(N5, N12, 140, SPEED4);
			door_set_pass_node(N12, N5, 140, SPEED4);
			nodes.nowNode = Node[getNextConnectNode(N5, N12)];
			nodes.nowNode.step = 60;
			nodes.nowNode.speed = SPEED4;
			update_route_at_door_for_clue();
			cross_event |= CROSS_EVENT_DOOR;
			state = DOOR_D2;
		}
		else // Yellow
		{
			send_play_specified_command(10);
			door_set_pass_node(N5, N12, 140, SPEED3);
			nodes.nowNode = Node[getNextConnectNode(N5, N12)];
			nodes.nowNode.flag = DLEFT | DRIGHT | CRIGHT | LEFT_LINE;
			nodes.nowNode.step = 60;
			nodes.nowNode.speed = SPEED4;
			update_route_at_door_for_clue();
			cross_event |= CROSS_EVENT_DOOR;
			state = DOOR_D5_BACK;
		}
		break;

	case DOOR_D3:
		color_flag[1] = door_color;
		if (color_flag[1] == Red)
		{
			send_play_specified_command(11);
			door_retreat(N5, N4);
			load_route_at(0, door1route);
			cross_event |= CROSS_EVENT_DOOR;
			state = DOOR_D4;
		}
		else // Green 或 Yellow
		{
			door_set_pass_node(N5, N8, 120, SPEED3);
			nodes.nowNode = Node[getNextConnectNode(N5, N8)];
			nodes.nowNode.step = 60;
			nodes.nowNode.speed = SPEED4;
			update_route_at_door_for_clue();

			if (color_flag[1] == Green)
			{
				door_set_pass_node(N8, N5, 120, SPEED3);
				send_play_specified_command(8);
				state = DOOR_D2;
			}
			else // Yellow
			{
				send_play_specified_command(10);
				state = DOOR_D5_BACK;
			}
			cross_event |= CROSS_EVENT_DOOR;
		}
		break;

	case DOOR_D4:
		color_flag[2] = door_color;
		if (color_flag[2] == Green)
		{
			send_play_specified_command(8);
			door_set_pass_node(N8, N3, 140, SPEED3);
		}
		else // Yellow
		{
			send_play_specified_command(10);
			door_set_pass_node(N10, N3, 140, SPEED3);
		}
		door_set_pass_node(N3, N8, 120, SPEED3);
		nodes.nowNode = Node[getNextConnectNode(N3, N8)];
		nodes.nowNode.step = 60;
		nodes.nowNode.speed = SPEED4;
		update_route_at_door_for_clue();
		cross_event |= CROSS_EVENT_DOOR;
		state = DOOR_D2;
		break;

	case DOOR_D5_BACK:
		color_flag[3] = door_color;
		if (color_flag[3] == Green)
		{
			send_play_specified_command(8);
			door_set_pass_node(N10, N3, 140, SPEED3);
			nodes.nowNode = Node[getNextConnectNode(N10, N3)];
			nodes.nowNode.step = 30;
			nodes.nowNode.speed = SPEED3;
			cross_event |= CROSS_EVENT_DOOR;
			update_route_by_door_1();
			state = DOOR_D2;
		}
		else // Red
		{
			send_play_specified_command(11);
			if (color_flag[0] == Yellow)
			{
				map.point -= 1;
				route[map.point] = N3;
				door_retreat(N10, N8);
				cross_event |= CROSS_EVENT_DOOR;
				state = DOOR_D4_BACK;
			}
			else if (color_flag[0] == Red && color_flag[1] == Yellow)
			{
				door_retreat(N10, N8);
				door_set_pass_node(N3, N8, 120, SPEED3);
				door_set_pass_node(N8, N3, 120, SPEED3);
				update_route_by_door_2();
				cross_event |= CROSS_EVENT_DOOR;
				state = DOOR_D2;
			}
		}
		break;

	case DOOR_D4_BACK:
		color_flag[2] = door_color;
		if (color_flag[2] == Green)
		{
			send_play_specified_command(8);
			door_set_pass_node(N3, N8, 120, SPEED3);
			door_set_pass_node(N8, N3, 120, SPEED3);
			nodes.nowNode = Node[getNextConnectNode(N8, N3)];
			nodes.nowNode.step = 30;
			nodes.nowNode.speed = SPEED3;
			nodes.nowNode.function = NONE;
			cross_event |= CROSS_EVENT_DOOR;
			update_route_by_door_3();
			motor_pid_clear();
		}
		else // Red
		{
			send_play_specified_command(11);
			door_retreat(N8, N5);
			door_set_pass_node(N8, N5, 140, SPEED3);
			door_set_pass_node(N5, N8, 140, SPEED3);
			cross_event |= CROSS_EVENT_DOOR;
			update_route_by_door_4();
		}
		state = DOOR_D2;
		break;
	}
}


void update_route_at_P1(void)
{
	if(flag_line_clue == 3)
	{
		const u8 r[] = {B1, N1, P1, N1, B2, N4, N3, P3, N3, N4, N5, N12, 0XFF};
		load_route_at(0, r);
	}
	else if(flag_line_clue == 4)
	{
		const u8 r[] = {B1, N1, P1, N1, B2, N4, N5, N6, P4, N6, N5, N12, 0XFF};
		load_route_at(0, r);
	}
	else if(flag_line_clue == 0)
	{
		// 跳过 P3/P4，直接去门区
		const u8 r[] = {B1, N1, P1, N1, B2, N4, N5, N12, 0XFF};
		load_route_at(0, r);
	}

}


void update_route_by_door_1(void)
{
	if(treasure ==5||treasure == 6)
		load_route_at(0, door6route);
	if(treasure ==3)
	{
		const u8 r[] = {P3,N3,N4,B3,N2,P2,0xFF};
		load_route_at(0, r);
	}
	if(treasure ==4)
	{
		const u8 r[] = {N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0xFF};
		load_route_at(0, r);
	}
	if(treasure ==2)
	{
		const u8 r[] = {N4,B2,N1,P1,N1,B1,N2,P2,0xFF};
		load_route_at(0, r);
	}
}
void update_route_by_door_2(void)
{
	if(treasure ==5||treasure == 6)
		load_route_at(0, door7route);
	if(treasure ==3)
	{
		const u8 r[] = {N3,P3,N3,N4,B3,N2,P2,0xFF};
		load_route_at(0, r);
	}
	if(treasure ==4)
	{
		const u8 r[] = {N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0xFF};
		load_route_at(0, r);
	}
	if(treasure ==2)
	{
		const u8 r[] = {N3,N4,B2,N1,P1,N1,B1,N2,P2,0xFF};
		load_route_at(0, r);
	}
}
void update_route_by_door_3(void)
{
	if(treasure ==5||treasure == 6)
		load_route_at(0, door8route);
	if(treasure ==3)
	{
		const u8 r[] = {P3,N3,N4,B3,N2,P2,0xFF};
		load_route_at(0, r);
	}
	if(treasure ==4)
	{
		const u8 r[] = {N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0xFF};
		load_route_at(0, r);
	}
	if(treasure ==2)
	{
		const u8 r[] = {N4,B2,N1,P1,N1,B1,N2,P2,0xFF};
		load_route_at(0, r);
	}
}
void update_route_by_door_4(void)
{
	if(treasure ==5||treasure == 6)
		load_route_at(0, door11route);
	if(treasure ==3)
	{
		const u8 r[] = {N4,N3,P3,N3,N4,B3,N2,P2,0xFF};
		load_route_at(0, r);
	}
	if(treasure ==4)
	{
		const u8 r[] = {N6,P4,N6,N5,N4,B3,N2,P2,0xFF};
		load_route_at(0, r);
	}
	if(treasure ==2)
	{
		const u8 r[] = {N4,B2,N1,P1,N1,B1,N2,P2,0xFF};
		load_route_at(0, r);
	}
}
static uint8_t Can_Pass(uint8_t c) { return c == Green || c == Yellow; }

void update_route_at_door_for_clue(void)
{
	// 按线索平台组合选择路线
	if (flag_clue_stage_A == 5 && flag_clue_stage_B == 7)
	{
		if(Can_Pass(color_flag[0]))
			load_route_at(0, rout_57);
		else if(Can_Pass(color_flag[1]) || Can_Pass(color_flag[2]))
		{
			route[0] = N12;
			load_route_at(1, rout_57);
		}
	}
	else if (flag_clue_stage_A == 5 && flag_clue_stage_B == 8)
	{
		if(Can_Pass(color_flag[0]))
			load_route_at(0, rout_58);
		else if(Can_Pass(color_flag[1]) || Can_Pass(color_flag[2]))
		{
			route[0] = N12;
			load_route_at(1, rout_58);
		}
	}
	else if (flag_clue_stage_A == 6 && flag_clue_stage_B == 7)
	{
		if(Can_Pass(color_flag[0]))
		{
			route[0] = N11;
			route[1] = N10;
			load_route_at(2, rout_67);
		}
		else if(Can_Pass(color_flag[1]) || Can_Pass(color_flag[2]))
		{
			route[0] = N10;
			load_route_at(1, rout_67);
		}
	}
	else if (flag_clue_stage_A == 6 && flag_clue_stage_B == 8)
	{
		if(Can_Pass(color_flag[0]))
		{
			route[0] = N11;
			route[1] = N10;
			load_route_at(2, rout_68);
		}
		else if(Can_Pass(color_flag[1]) || Can_Pass(color_flag[2]))
		{
			route[0] = N10;
			load_route_at(1, rout_68);
		}
	}
}

/*第二轮路线规划*/
void get_newroute(void)
{
	mapInit1();
	map.point = 0;
	for (int i = 0; i < 126; i++)
	{
		if (Node[i].function == DOOR)
		{
			Node[i].function = NONE;
			Node[i].step *= 2;
			Node[i].speed = SPEED3;
		}
	}

	if(color_flag[0]==Green)//第一个门开
	{
		Node[getNextConnectNode(P3, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6:
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P7,N20,B6,N22,C9,P8,C9,N22,B7,C6,N19,B5,N18,N16,N12,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
		
	}
	else if(color_flag[0]==Yellow && color_flag[3]==Green)
	{
		Node[getNextConnectNode(S1, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6:
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P7,N20,B6,N22,C9,P8,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(color_flag[0]==Yellow && color_flag[3]==Red && color_flag[2]==Green)
	{
		Node[getNextConnectNode(S1, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6:
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P7,N20,B6,N22,C9,P8,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	} 
	else if(color_flag[0]==Yellow && color_flag[3]==Red && color_flag[2]==Red)
	{
		Node[getNextConnectNode(P3, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6:
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P7,N20,B6,N22,C9,P8,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(color_flag[0]==Red && color_flag[1]==Green)
	{
		Node[getNextConnectNode(P3, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6: 									//可不过刀山		
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P7,N20,B6,N22,C9,P8,C9,N22,B7,C6,N19,B5,N18,N16,N12,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(color_flag[0]==Red && color_flag[1]==Yellow && color_flag[3]==Green)
	{
		Node[getNextConnectNode(S1, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6: 									//可不过刀山		
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P7,N20,B6,N22,C9,P8,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(color_flag[0]==Red && color_flag[1]==Yellow && color_flag[3]==Red)//D4绿
	{
		Node[getNextConnectNode(S1, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6: 									//可不过刀山		
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P7,N20,B6,N22,C9,P8,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(color_flag[0]==Red && color_flag[1]==Red && color_flag[2]==Green)//从最外面出去吧
	{
		Node[getNextConnectNode(P3, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6: 									//可不过刀山		
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P7,N20,B6,N22,C9,P8,C9,N22,B7,C6,N19,B5,N18,N16,N12,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(color_flag[0]==Red && color_flag[1]==Red && color_flag[2]==Yellow)//从最外面出去吧
	{
		Node[getNextConnectNode(P3, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9,N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6: 									//可不过刀山		
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P7,N20,B6,N22,C9,P8,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else
		CarBrake_Stop();
}

/*K210读数字*/
uint8_t WaitFor_OCR(void)
{
	static uint8_t No2Tra = 0;
	static uint8_t No3Tra = 0;

	if (((nodes.nowNode.nodenum == P5 || nodes.nowNode.nodenum == P5) && No2Tra == 1) ||
		((nodes.nowNode.nodenum == P7 || nodes.nowNode.nodenum == P8) && No3Tra == 1))
		return 0;

	/*等待看完*/
	uint16_t break_times = 0;
	uint8_t ReturnFlag = 0;

	while (K210_Rece == 0)
	{
		//buzzer_on();
		vTaskDelay(3);
		break_times++;
		
		if (break_times >= 600)//500
		{	
//			Chassis_MotorControl(is_No, -3, -3, 0);
			moveServo(0, 1610, 1000);//头向左摆一点
			vTaskDelay(2000);
			moveServo(0, 1330, 1000);//头向右摆一点
			vTaskDelay(2000);
//			Want2Go(1);
			
			CarBrake();
			Chassis_ClearMileage();
			open_OCR_mode();
			break_times = 0;
			ReturnFlag++;
			if(ReturnFlag==1||ReturnFlag==3)
			{
				Chassis_MotorControl(is_No, 5, 5, 0);
				Want2Go(3);	
				CarBrake();
				Chassis_ClearMileage();
			}
			if(ReturnFlag==2||ReturnFlag==4)
			{
				Chassis_MotorControl(is_No, 5, 5, 0);
				Want2Go(3);	
				CarBrake();
				Chassis_ClearMileage();
			}
			if(ReturnFlag > 4)
			{
				break;
			}
		}

	}

	K210_Rece = 0;
	/*记录宝藏*/
	if (nodes.nowNode.nodenum == P1)
	{
		Clue_Num = 0;
	}
	else if (nodes.nowNode.nodenum == P3 || nodes.nowNode.nodenum == P4)
	{
		Clue_Num = 0;
	}
	else if (nodes.nowNode.nodenum == P5 || nodes.nowNode.nodenum == P6)
	{
		No2Tra = 1;
		HAL_UART_AbortReceive_IT(&huart5);
		close_Maxicam();
		Maxicam_Enable();
		flag_clue_A = Clue_Num;
		K210_Rece = 0;
		if (flag_clue_A == 0)
			send_play_specified_command(29);
		else
			send_play_specified_command(22+flag_clue_A);
//		for(uint8_t i = 0;i<clue_A;i++)
//		{
//			buzzer_on();
//			vTaskDelay(500);
//			buzzer_off();
//			vTaskDelay(500);
//		}
		Clue_Num = 0;
	}
	else if (nodes.nowNode.nodenum == P7 || nodes.nowNode.nodenum == P8)
	{
		No3Tra = 1;
		HAL_UART_AbortReceive_IT(&huart5);
		close_Maxicam();
		Maxicam_Enable();
		flag_clue_B = Clue_Num;
		K210_Rece = 0;
		send_play_specified_command(16+flag_clue_B);
//		for(uint8_t i = 0;i<clue_B;i++)
//		{
//			buzzer_on();
//			vTaskDelay(500);
//			buzzer_off();
//			vTaskDelay(500);
//		}
		treasure = flag_clue_A+flag_clue_B;//获取宝物平台位置
		Clue_Num = 0;
	}

	/*关闭Maxicam*/
	close_Maxicam();
	buzzer_on();
	vTaskDelay(100);
	buzzer_off();
	return 0;
}

uint8_t WaitFor_QR(void)
{
	/*等待看完*/
	uint16_t break_times = 0;
	uint8_t ReturnFlag = 0;
	
	while (get_cude == 0)
	{
		vTaskDelay(3);
		break_times++;
		if (break_times >= 500)//500
		{
			Chassis_MotorControl(is_No, -3, -3, 0);
			Want2Go(5);
			CarBrake();
			Chassis_ClearMileage();
			break_times = 0;
			ReturnFlag++;
			if(ReturnFlag > 3)
			{				
				return 0;
			}
				
		}
	
	}
//	if (nodes.nowNode.nodenum == P1)
//	{
//		flag_clue_stage_A = (QR_code/10)%10;//获取十位上的数字
//		flag_clue_stage_B = QR_code%10;//获取个位上数字
//	}
	return 0;
}
	
//int i=0;
uint16_t AD_Value[4];//定义一个数组
/*启动流程*/
void zhunbei(void)
{

	/*停车*/
	Chassis_MotorControl(is_No, 0, 0, 0);

//	/*机器人动作*/
//	Robot_Work(BODY, UP); 	//人站起来
//	vTaskDelay(1000);
//	Robot_Work(PIG, HEAD_LEFT); //转头
//	vTaskDelay(500);		
//	Robot_Work(PIG, HEAD_RIGHT); 	
//	vTaskDelay(500);
//	/*蜂鸣器提示初始化完成 - 调试用*/
//	buzzer_on();
//	
//	// i = HAL_GPIO_ReadPin(GPIOC,GPIO_PIN_13);
//	vTaskDelay(100);
//	buzzer_off();

//	close_Maxicam();
	IMU_CalibrateZero(&basic_y, &basic_p, &basic_r);
	vTaskDelay(100);
	mpuZreset(get_latest_yaw(), nodes.nowNode.angle); // 用稳定后的实际角度计算补偿
	vTaskDelay(100);
	/*等待挡板*/
	while (Infrared_ahead == 0)
		vTaskDelay(5);

	/*等待移除挡板*/
	while(Infrared_ahead == 1)
		vTaskDelay(5);

	
	/**************转弯测试***************/
	/*播报语音*/
	
	Chassis_SelfCheck();	
	send_play_specified_command(7);
	/*机器人动作*/
	Robot_Work(LARM, UP);		// 左手举起
	vTaskDelay(100);
	Robot_Work(RARM, UP);		//右手举起
	vTaskDelay(500);
	Robot_Work(LARM, DOWN);		//左手放下
	vTaskDelay(100);
	Robot_Work(RARM, DOWN);		//右手放下
	vTaskDelay(100);
	Robot_Work(BODY, DOWN);		//人躺下
	vTaskDelay(100);
	Robot_Work(HEAD,HEAD_MID);
	vTaskDelay(100);
	Robot_Work(HEAD,UP);
	

	RampCtrl_Blocking(RAMP_DESCEND, GoStage_Speed, getAngleZ(),
				Begin_down, GoStage_Speed, down_pitch, UpDownStage_Speed_high, After_down-10, 0.04, 10.0f, 0.0f);
		/*下桥完毕*/
		//printf("Finished crossing the bridge\n");
}






