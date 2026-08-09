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
 *                    RampCtrl_Blocking / Stage_Action
 *  平台              Stage( / Stage_Home
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
 *  红绿灯            Door_ReadPass / door_set_pass_node
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
uint8_t door_pass[5] = {0, 0, 0, 0, 0};
#if DEBUG
uint8_t debug_door_pass[5] = {NO_PASS, NO_PASS, CAN_PASS, ONE_WAY_PASS, NO_PASS}; // 0:D2、1:D3、2:D4、3:D5、4:D1
volatile uint8_t flag_line_clue    = 0;
volatile uint8_t flag_clue_stage_A = 5;
volatile uint8_t flag_clue_stage_B = 8;
// OCR 线索：P5/P6读clue_A，P7/P8读clue_B，treasure=clue_A+clue_B → 宝物平台编号
uint8_t flag_clue_A       = 1;
uint8_t flag_clue_B       = 1;
#else
volatile uint8_t flag_line_clue    = 0;
volatile uint8_t flag_clue_stage_A = 0;
volatile uint8_t flag_clue_stage_B = 0;
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

volatile uint8_t get_cude = 0;

/* MaixCam识别较慢：每轮保持模式的最长等待时间（FreeRTOS tick） */
#define MAIXCAM_QR_WAIT_TICKS     1500U  /* 1500 × 3ms ≈ 4.5s */
#define MAIXCAM_OCR_WAIT_TICKS    1500U  /* 1500 × 3ms ≈ 4.5s */
#define MAIXCAM_COLOR_WAIT_TICKS  2000U  /* 2000 × 2ms ≈ 4.0s */

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
	//找到宝物举起双臂
	CarBrake();
	Robot_Work(BODY, UP); 	//人站起来
	vTaskDelay(800);
	Robot_Work(LARM, UP);		// 左手举起
	vTaskDelay(100);
	Robot_Work(RARM, UP);		//右手举起
	vTaskDelay(100);

	send_play_specified_command(9);
	Chassis_Turn360_Blocking();

	vTaskDelay(500);
	Robot_Work(LARM, DOWN);		//左手放下
	vTaskDelay(100);
	Robot_Work(RARM, DOWN);		//右手放下
	vTaskDelay(100);

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

static void Arrived_Stage(void)
{
	Robot_Work(LARM, UP);
	vTaskDelay(100);
	Robot_Work(RARM, UP);
	vTaskDelay(100);
	/* 播报到达X号平台，规则要求转身180度后再播报 */
	switch (nodes.nowNode.nodenum)
	{
	case P1: send_play_specified_command(5); break;
	case P3: send_play_specified_command(4); break;
	case P4: send_play_specified_command(3); break;
	case P5: send_play_specified_command(2); break;
	case P6: send_play_specified_command(1); break;
	case P7: send_play_specified_command(12); break;
	case P8: send_play_specified_command(14); break;
	default: break;
	}
	Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 180, getAngleZ(), 20.0f);
	Robot_Work(LARM, DOWN);
	vTaskDelay(100);
	Robot_Work(RARM, DOWN);
	vTaskDelay(100);
}

static void Stage_Action(float oringinal_angle)
{
	uint8_t stage_state = 0;
	uint8_t again_required = 0;

	while(stage_state!=4){
		//撞击
		if (stage_state == 0 || again_required)
		{
			if(again_required)Chassis_DriveDistance_Blocking(is_Gyro,20,GoStage_Speed,getAngleZ(),0);
			else Chassis_DriveDistance_Blocking(is_Gyro,29,GoStage_Speed,oringinal_angle,0);
			CarBrake();
			mpuZreset(get_latest_yaw(), nodes.nowNode.angle);
			//后退一段距离
			Chassis_DriveDistance_Blocking(is_Gyro,10,-GoStage_Speed,getAngleZ(),0);
			CarBrake();
			if(stage_state == 0)stage_state = 1;
		}
		//扭摄像头
		if(stage_state == 1 && treasure == 0 )
		{
			Robot_Work(CAMERA, HEAD_MID);
			vTaskDelay(300);	
			stage_state = 2;
		}
		//扫描
		if(stage_state==2 || again_required)
		{
			//等待二维码
			if (nodes.nowNode.nodenum == P1 && treasure == 0)
			{
				if(WaitFor_QR()){
					update_route_at_P1();
					stage_state = 3;
					again_required = 0;
				}
				else{//再撞再扫描
					again_required = 1;
				}
			}
			//等待数字
			else if (treasure == 0 && (nodes.nowNode.nodenum == P5 || nodes.nowNode.nodenum == P6 ||
				nodes.nowNode.nodenum == P7 || nodes.nowNode.nodenum == P8))
			{
				if(WaitFor_OCR()){
					stage_state = 3;
					again_required = 0;
				}
				else{
					again_required = 1;
				}
			}
			else stage_state = 3;
		}
		if(stage_state == 3)
		{
			Arrived_Stage();
		}
		vTaskDelay(2);
	}
}

/*平台 - 不包括P2*/
void Stage(void)
{
	enum {
		STAGE_ASCEND,    // 上坡：RampCtrl_Blocking 处理
		STAGE_TOP,       // 桥面行驶+站起+撞击
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
			Robot_Work(BODY, UP); 	//人站起来
			Stage_Action(oringinal_angle);

			if(Stage_HasTreasure())
				Stage_CollectTreasure();

			Robot_Work(BODY, DOWN); 	//人躺下
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

/*平台 - Home（返程上台阶回家） */
void Stage_Home(void)
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
	
			// //回家恢复原形
			// Robot_Work(LARM, DOWN);		//左手放下
			// vTaskDelay(100);
			// Robot_Work(RARM, DOWN);		//右手放下
			// vTaskDelay(100);
			// Robot_Work(BODY, DOWN);		//人躺下
			// vTaskDelay(100);
			// Robot_Work(CAMERA,HEAD_MID);
			// vTaskDelay(100);
			// Robot_Work(CAMERA,UP);

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
			GyroStableReset(40, &origin_angle);

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
				Chassis_CorrectByInfrared(0.07f, 1.5f, 1.5f);
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
						Chassis_CorrectByInfrared(0.04f, 1.5f, 1.0f);
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
	
	Chassis_MotorControl(is_Line, 15, 15, 0);
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
				//Chassis_MotorControl(is_Free, 1500, 1500, 0);
			}
			else
			{
				Chassis_MotorControl(is_Gyro, Gyro_Speed , Gyro_Speed , recorded_angle);
			}


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
			Robot_Work(BODY, UP); 	//人站起来
			//平台动作
			Stage_Action(getAngleZ());

			if (treasure == 0)	{
				treasure = flag_clue_A + flag_clue_B;	
			}
			if(map.routetime == 0){
				update_route_at_P8_for_treasure();
			}
			Robot_Work(BODY, DOWN); 	//人坐下
			origin_angle = getAngleZ();
			sub_stage = 0;
			state = HM_DESCEND_1;
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
		Scaner_Update();
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
			Robot_Work(BODY, UP);
			//平台动作
			Stage_Action(getAngleZ());

			if (treasure == 0)
				treasure = flag_clue_A + flag_clue_B;
			if (map.routetime == 0)
				update_route_at_P7_for_treasure();

			Robot_Work(BODY, DOWN);
			state = SP_DESCEND;
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
	if(treasure != 0&&door_pass[0] == CAN_PASS)//D2绿灯
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
	if(treasure != 0&&door_pass[1] == CAN_PASS)//D3绿灯
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
				{ const u8 r[] = {N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	     }
    }
	if(treasure != 0&&door_pass[2] == CAN_PASS)//D4绿灯
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
				{ const u8 r[] = {N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	    }
	}
	if(treasure != 0&&((door_pass[0] == ONE_WAY_PASS)||(door_pass[1] == ONE_WAY_PASS)))//D2D3蓝灯(单相通过)
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
	if(treasure != 0&&door_pass[2] == ONE_WAY_PASS)//D4蓝灯(单相)D5必绿
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
	printf("treasure%d\r\n",treasure);
	if(treasure != 0&&door_pass[0] == CAN_PASS)//D2绿灯
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
	if(treasure != 0&&door_pass[1] == CAN_PASS)//D3绿灯
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
	if(treasure != 0&&door_pass[2] == CAN_PASS)//D4绿灯
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
	if(treasure != 0&&((door_pass[0] == ONE_WAY_PASS)||(door_pass[1] == ONE_WAY_PASS)))//D2D3蓝灯(单相通过)
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
	if(treasure != 0&&door_pass[2] == ONE_WAY_PASS)//D4蓝灯(单相)D5必绿
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
#define CENTER 7
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
			Chassis_SetCatchSensorNum(line_weight_default[CENTER]);
			//改变循迹模式为左边循迹
			Chassis_SetTrackMode(TRACK_LEFT_EDGE);
			
			//改变电机控制模式为巡线模式
			Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
			Chassis_OverrideLinePid(17,0.01f,50,30);

			//等待小车行驶10cm后，改变循迹模式为中间循迹
			Chassis_ClearMileage();
			while(Chassis_GetMileage() < 40)vTaskDelay(2);	
			Chassis_SetTrackMode(TRACK_NEAR_CENTER);
			Chassis_ClearMileage();
			
			state = QQB_WAIT_PITCH;
			break;

		case QQB_WAIT_PITCH:
			
			Cross_getline(&Cross_Scaner);
			//防止循迹受到旁边红线的干扰
			//if(imu.pitch>=After_up ||Cross_Scaner.ledNum>=4||Cross_Scaner.lineNum>=2)Chassis_SetEdgeIgnore(4);
			//等待对其
			if ((imu.yaw >=70&&imu.yaw <=110)||(imu.yaw <=-70&&imu.yaw >=-110)||Cross_Scaner.ledNum>=4||Cross_Scaner.lineNum>=2)
			{	
				send_play_specified_command(7);	
				Chassis_OverrideGyroPid(4, 0, 70, 5);  
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
			if ((Cross_Scaner.detail & 0x1C00)&&is_emergency==1)
			{	
				is_emergency++;
				send_play_specified_command(33);
				send_play_specified_command(33);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 20, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -SPEED0, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() - 20, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 18, SPEED0, getAngleZ(), 0);
			}
			else if ((Cross_Scaner.detail & 0x0038)&&is_emergency==1)
			{			
				is_emergency++;
				send_play_specified_command(33);
				send_play_specified_command(33);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() - 20, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -SPEED0, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 20, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 18, SPEED0, getAngleZ(), 0);
			}
			else if ((Cross_Scaner.detail & 0xF000)&&is_emergency==1)
			{	
				is_emergency++;
				send_play_specified_command(33);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 10, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -SPEED0, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() - 10, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 18, SPEED0, getAngleZ(), 0);
				
			}
			else if ((Cross_Scaner.detail & 0x000F)&&is_emergency==1)
			{			
				is_emergency++;
				send_play_specified_command(33);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() - 10, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -SPEED0, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 10, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 18, SPEED0, getAngleZ(), 0);
				
			}
			else if(is_emergency){
			is_emergency=0;
			Chassis_MotorControl(is_Gyro, 15, 15, getAngleZ()>0?90:-90);
			Chassis_ClearMileage();
			}

			if(is_emergency==0)Chassis_CorrectByInfrared(0.05f, 1.5f, 1.5f);

			if(imu.pitch>55){
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -SPEED0, getAngleZ(), 0);
				CarBrake();
				vTaskDelay(500);
				state = QQB_WAIT_PITCH;
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
				vTaskDelay(300);	
				Chassis_RestoreGyroPid();
				Chassis_MotorControl(is_Gyro, 15, 15, getAngleZ());	
				Chassis_Turn_By_Gyro_Blocking(getAngleZ()>0?145:-45, getAngleZ(), 20.0f);	
				seen_negative=2;				
			}
			if(seen_negative==2)
			{			
				if(p > After_down-10) 
				{	
						
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
	Chassis_SetCatchSensorNum(line_weight_default[13]);
	Chassis_SetTrackMode(TRACK_LEFT_EDGE);
	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
	Chassis_OverrideLinePid(17,0.02f,50,30);
	Chassis_ClearMileage();
	uint8_t dis = getAngleZ()>0?60:35;
	while(Chassis_GetMileage() < dis)vTaskDelay(2);
	Chassis_RestoreLinePid();
	
	nodes.nowNode.function = 0;
	cross_event |= CROSS_EVENT_ARRIVED;
	
}

/* 真实定义在下方，先声明后供测试入口调用 */
static uint8_t Door_ReadPass(uint8_t door_state);

uint8_t Door_ReadPass_Test(void)
{
    return Door_ReadPass(0);   // 测试 D2
}


/*读门灯通行状态（0=超时/未设置, 1=绿=能过, 2=蓝=单相通过, 3=黑=不能过）*/
static uint8_t Door_ReadPass(uint8_t door_state)
{
#if DEBUG
	static const uint8_t state_to_idx[] = {0, 1, 2, 3, 2}; // D2→0, D3→1, D4→2, D5→3, D4_AGAIN→2
	return debug_door_pass[state_to_idx[door_state]];
#else
	/* TODO: 读取真实左右颜色传感器
	 *   maixcam→ UART6_RX 读取颜色值
	 *   返回值：1=Green, 2=Yellow, 3=Red, 0=未读到
	 */

   uint8_t retry;
    uint8_t color = 0;

    (void)door_state;

    /*
     * 只有一个 MaixCam，摄像头通过0号舵机向左看灯。
     * Robot_Work() 内部已经包含约200 tick的等待。
     */
    Robot_Work(CAMERA, HEAD_RIGHT);
    vTaskDelay(500);

    for (retry = 0; retry < 3; retry++)
    {
        uint32_t timeout = 0;

        /*
         * 清除上次识别结果，避免误用旧颜色。
         */
        Color_Left = 0;

        /*
         * 发送0x33并等待MaixCam返回0x94。
         */
        Open_COLOR_L();

        /*
         * 等待Process_COLOR_Data()连续收到3次相同颜色，
         * 然后写入Color_Left。MaixCam识别较慢，单轮保持4秒。
         */
        while (Color_Left == 0 && timeout < MAIXCAM_COLOR_WAIT_TICKS)
        {
            vTaskDelay(2);
            timeout++;
        }

        color = Color_Left;

        if (color == CAN_PASS ||
            color == ONE_WAY_PASS ||
            color == NO_PASS)
        {
            /*
             * Process_COLOR_Data()识别成功后已调用
             * close_Maxicam()，可以直接返回。
             */
            return color;
        }

        /*
         * 本轮超时：重新尝试。
         */
        vTaskDelay(50);
    }

    /*
     * 连续3次识别失败。
     */
    close_Maxicam();
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

/*红绿灯辅助：NO_PASS(不能过)后退+转头+重定向到目标节点*/
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
	uint8_t pass_state = Door_ReadPass(state);
	if (pass_state == 0)
	{
		// 兜底：摄像头读不到颜色时按“不能通过”处理
		pass_state = NO_PASS;
	}

	/*公共初始化*/
	map.point = 0;
	route[0] = 0xFF;

	switch (state)
	{
	case DOOR_D2:


		door_pass[0] = pass_state;
		//打印灯信息
		printf("DOOR_D2:%d",door_pass[0]);
		if (door_pass[0] == NO_PASS)
		{
			send_play_specified_command(11);
			door_retreat(N5, N8);
			cross_event |= CROSS_EVENT_DOOR;
			state = DOOR_D3;
		}
		else if (door_pass[0] == CAN_PASS)
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
		else // ONE_WAY_PASS
		{
			send_play_specified_command(10);
			door_set_pass_node(N5, N12, 140, SPEED4);
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
		door_pass[1] = pass_state;
		if (door_pass[1] == NO_PASS)
		{
			send_play_specified_command(11);
			door_retreat(N5, N4);
			load_route_at(0, door1route);
			cross_event |= CROSS_EVENT_DOOR;
			state = DOOR_D4;
		}
		else // CAN_PASS 或 ONE_WAY_PASS
		{
			door_set_pass_node(N5, N8, 120, SPEED3);
			nodes.nowNode = Node[getNextConnectNode(N5, N8)];
			nodes.nowNode.step = 60;
			nodes.nowNode.speed = SPEED4;
			update_route_at_door_for_clue();

			if (door_pass[1] == CAN_PASS)
			{
				door_set_pass_node(N8, N5, 120, SPEED3);
				send_play_specified_command(8);
				state = DOOR_D2;
			}
			else // ONE_WAY_PASS
			{
				send_play_specified_command(10);
				state = DOOR_D5_BACK;
			}
			cross_event |= CROSS_EVENT_DOOR;
		}
		break;

	case DOOR_D4:
		door_pass[2] = pass_state;
		if (door_pass[2] == CAN_PASS)
		{
			send_play_specified_command(8);
			door_set_pass_node(N8, N3, 140, SPEED3);
		}
		else if (door_pass[2] == NO_PASS)
		{
			// 兜底：D4读不到时停车，避免被当成蓝灯
			CarBrake_Stop();
		}
		else // ONE_WAY_PASS
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
		door_pass[3] = pass_state;
		if (door_pass[3] == CAN_PASS)
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
		else // NO_PASS，蓝灯(单相)已经被消耗
		{
			send_play_specified_command(11);
			if (door_pass[0] == ONE_WAY_PASS)
			{
				map.point -= 1;
				route[map.point] = N3;
				door_retreat(N10, N8);
				cross_event |= CROSS_EVENT_DOOR;
				state = DOOR_D4_BACK;
			}
			else if (door_pass[0] == NO_PASS && door_pass[1] == ONE_WAY_PASS)
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
		door_pass[2] = pass_state;
		if (door_pass[2] == CAN_PASS)
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
		else // NO_PASS
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
static uint8_t Can_Pass(uint8_t c) { return c == CAN_PASS || c == ONE_WAY_PASS; }

void update_route_at_door_for_clue(void)
{
	// 按线索平台组合选择路线
	if (flag_clue_stage_A == 5 && flag_clue_stage_B == 7)
	{
		if(Can_Pass(door_pass[0]))
			load_route_at(0, rout_57);
		else if(Can_Pass(door_pass[1]) || Can_Pass(door_pass[2]))
		{
			route[0] = N12;
			load_route_at(1, rout_57);
		}
	}
	else if (flag_clue_stage_A == 5 && flag_clue_stage_B == 8)
	{
		if(Can_Pass(door_pass[0]))
			load_route_at(0, rout_58);
		else if(Can_Pass(door_pass[1]) || Can_Pass(door_pass[2]))
		{
			route[0] = N12;
			load_route_at(1, rout_58);
		}
	}
	else if (flag_clue_stage_A == 6 && flag_clue_stage_B == 7)
	{
		if(Can_Pass(door_pass[0]))
		{
			route[0] = N11;
			route[1] = N10;
			load_route_at(2, rout_67);
		}
		else if(Can_Pass(door_pass[1]) || Can_Pass(door_pass[2]))
		{
			route[0] = N10;
			load_route_at(1, rout_67);
		}
	}
	else if (flag_clue_stage_A == 6 && flag_clue_stage_B == 8)
	{
		if(Can_Pass(door_pass[0]))
		{
			route[0] = N11;
			route[1] = N10;
			load_route_at(2, rout_68);
		}
		else if(Can_Pass(door_pass[1]) || Can_Pass(door_pass[2]))
		{
			route[0] = N10;
			load_route_at(1, rout_68);
		}
	}
}

/*第二轮路线规划*/
void get_newroute(void)
{
	mapInit();
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

	if(door_pass[0]==CAN_PASS)//第一个门开
	{
		Node[getNextConnectNode(P3, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6:
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P8,N20,B6,N22,C9,P7,C9,N22,B7,C6,N19,B5,N18,N16,N12,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
		
	}
	else if(door_pass[0]==ONE_WAY_PASS && door_pass[3]==CAN_PASS)
	{
		Node[getNextConnectNode(S1, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6:
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P8,N20,B6,N22,C9,P7,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(door_pass[0]==ONE_WAY_PASS && door_pass[3]==NO_PASS && door_pass[2]==CAN_PASS)
	{
		Node[getNextConnectNode(S1, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6:
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P8,N20,B6,N22,C9,P7,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	} 
	else if(door_pass[0]==ONE_WAY_PASS && door_pass[3]==NO_PASS && door_pass[2]==NO_PASS)
	{
		Node[getNextConnectNode(P3, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6:
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P8,N20,B6,N22,C9,P7,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(door_pass[0]==NO_PASS && door_pass[1]==CAN_PASS)
	{
		Node[getNextConnectNode(P3, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6: 									//可不过刀山		
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P8,N20,B6,N22,C9,P7,C9,N22,B7,C6,N19,B5,N18,N16,N12,N8,N5,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(door_pass[0]==NO_PASS && door_pass[1]==ONE_WAY_PASS && door_pass[3]==CAN_PASS)
	{
		Node[getNextConnectNode(S1, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6: 									//可不过刀山		
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P8,N20,B6,N22,C9,P7,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(door_pass[0]==NO_PASS && door_pass[1]==ONE_WAY_PASS && door_pass[3]==NO_PASS)//D4绿
	{
		Node[getNextConnectNode(S1, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6: 									//可不过刀山		
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N8,N12,N13,P6,N13,N12,N11,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P8,N20,B6,N22,C9,P7,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(door_pass[0]==NO_PASS && door_pass[1]==NO_PASS && door_pass[2]==CAN_PASS)//从最外面出去吧
	{
		Node[getNextConnectNode(P3, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6: 									//可不过刀山		
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P8,N20,B6,N22,C9,P7,C9,N22,B7,C6,N19,B5,N18,N16,N12,N8,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_5[i];
					if(temp_5[i]==0xff)
						break;
				}
				break;
		}
	}
	else if(door_pass[0]==NO_PASS && door_pass[1]==NO_PASS && door_pass[2]==ONE_WAY_PASS)//从最外面出去吧
	{
		Node[getNextConnectNode(P3, N3)].flag |= STOPTURN;
		switch(treasure)
		{
			case 2:
				u8 temp_1[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_1[i];
					if(temp_1[i]==0xff)
						break;
				}
				break;
			case 3:
				u8 temp_2[100]={B1,N1,P1,N1,B2,N4,N3,P3,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_2[i];
					if(temp_2[i]==0xff)
						break;
				}
				break;
			case 4:
				u8 temp_3[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_3[i];
					if(temp_3[i]==0xff)
						break;
				}
				break;
			case 5:
				u8 temp_4[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N12,N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF};
					for(int i=0;i<100;i++)
				{
					route[i]=temp_4[i];
					if(temp_4[i]==0xff)
						break;
				}
				break;
			case 6: 									//可不过刀山		
				u8 temp_5[100]={B1,N1,P1,N1,B2,N4,N5,N6,P4,N6,N5,N4,N3,N8,N10,N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P8,N20,B6,N22,C9,P7,C9,N22,B7,C6,N19,B5,N18,N16,N12,N11,N10,N3,N4,B3,N2,P2,0XFF};
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

/* MaixCam读取数字线索：成功返回OCR_SCAN_SUCCESS，超时或平台不匹配返回OCR_SCAN_FAILED */
uint8_t WaitFor_OCR(void)
{
#if DEBUG
	return OCR_SCAN_SUCCESS;
#else
	static uint8_t clue_A_collected = 0;
	static uint8_t clue_B_collected = 0;
	uint8_t is_clue_A_stage;
	uint8_t is_clue_B_stage;
	uint8_t clue_value;

	is_clue_A_stage = ((nodes.nowNode.nodenum == P5 && flag_clue_stage_A == 5) ||
		(nodes.nowNode.nodenum == P6 && flag_clue_stage_A == 6));
	is_clue_B_stage = ((nodes.nowNode.nodenum == P7 && flag_clue_stage_B == 7) ||
		(nodes.nowNode.nodenum == P8 && flag_clue_stage_B == 8));

	/* 已采集过 → 直接视为成功，避免重复扫描 */
	if ((is_clue_A_stage && clue_A_collected) || (is_clue_B_stage && clue_B_collected))
		return OCR_SCAN_SUCCESS;

	/* 不在二维码指定的平台 → 不读取 */
	if (!is_clue_A_stage && !is_clue_B_stage)
		return OCR_SCAN_FAILED;

	K210_Rece = 0;
	Clue_Num = 0;

	for (uint8_t retry = 0; retry < 2; retry++)
	{
		uint16_t timeout = 0;
		/* 每轮开始时立即发送0x22，不能先空等 */
		open_OCR_mode();

		/* MaixCam识别较慢，保持OCR模式约4.5秒；收到有效结果立即退出 */
		while (!K210_Rece && timeout < MAIXCAM_OCR_WAIT_TICKS)
		{
			vTaskDelay(3);
			timeout++;
		}

		if (K210_Rece )
			break;

		/* 本轮失败，关闭任务并调整摄像头/车位后再试 */
		close_Maxicam();
		if ((retry & 1U) == 0)
			moveServo(0, 1610, 1000);
		else
			moveServo(0, 1330, 1000);
		vTaskDelay(1200);

		Chassis_DriveDistance_Blocking(is_Gyro, 3, SPEED0, getAngleZ(), 0);
		CarBrake();
		Chassis_ClearMileage();
	}

	/* 失败时不得保存Clue_Num，也不得置采集完成标志 */
	if (K210_Rece == 0)
	{
		close_Maxicam();
		Clue_Num = 0;
		return OCR_SCAN_FAILED;
	}

	/* 必须先保存成功结果，再清接收标志 */
	clue_value = Clue_Num;
	K210_Rece = 0;
	Clue_Num = 0;
	close_Maxicam();

	if (is_clue_A_stage)
	{
		flag_clue_A = clue_value;
		clue_A_collected = 1;
		if (flag_clue_A == 0)
			send_play_specified_command(29);
		else
			send_play_specified_command(22 + flag_clue_A);
			vTaskDelay(1000);
	}
	else
	{
		flag_clue_B = clue_value;
		clue_B_collected = 1;
		send_play_specified_command(16 + flag_clue_B);
		vTaskDelay(1000);
	}
	return OCR_SCAN_SUCCESS;
#endif
}

/* MaixCam读取二维码：成功返回1，连续超时返回0 */
uint8_t WaitFor_QR(void)
{
#if DEBUG
	return 1;
#else
	uint8_t retry;
	for (retry = 0; retry < 2; retry++)
	{
		uint16_t timeout = 0;
		/* 每轮重试都重新发送0x11并等待0x94确认 */
		open_QR_mode();

		/* 阻塞等待,最长保持QR模式约4.5秒；收到有效结果立即退出 */
		while (!get_cude && timeout < MAIXCAM_QR_WAIT_TICKS)
		{
			vTaskDelay(3);
			timeout++;
		}

		if (get_cude)
			return 1;
		else Chassis_DriveDistance_Blocking(is_Gyro, 3, -SPEED0, getAngleZ(), 0);
		/*
		 * 未及时收到QR结果时直接重新发送0x11。
		 * 不在这里移动小车：Want2Go()依赖里程更新，架车测试时会永久阻塞，
		 * 导致后续重试和main_task外层循环都无法执行。
		 * 也不发送0x66，保持MaixCam处于QR模式等待下一次启动命令。
		 */
	}

	/* 全部重试失败后返回0再撞一次 */
	close_Maxicam();
	return 0;
#endif
}

//int i=0;
uint16_t AD_Value[4];//定义一个数组
/*启动流程*/
void zhunbei(void)
{
	/*停车*/
	Chassis_MotorControl(is_No, 0, 0, 0);

	/*机器人动作*/
	Robot_Work(BODY, UP); 	//人站起来
	vTaskDelay(1000);
	Robot_Work(MIKU, HEAD_LEFT); //转头
	vTaskDelay(500);
	Robot_Work(MIKU, HEAD_RIGHT);
	vTaskDelay(500);

	/*等待挡板*/
	while (Infrared_ahead == 0)
		vTaskDelay(5);

	/*等待移除挡板*/
	while(Infrared_ahead == 1)
		vTaskDelay(5);

	
	/**************转弯测试***************/
	/*播报语音*/
		
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
	Robot_Work(CAMERA,HEAD_MID);
	vTaskDelay(100);
	Robot_Work(CAMERA,UP);
	

	RampCtrl_Blocking(RAMP_DESCEND, GoStage_Speed, getAngleZ(),
				Begin_down, GoStage_Speed, down_pitch, UpDownStage_Speed_high, After_down-10, 0.04, 10.0f, 0.0f);
		/*下桥完毕*/
		//printf("Finished crossing the bridge\n");
}






