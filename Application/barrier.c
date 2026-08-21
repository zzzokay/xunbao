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

#define DEBUG 1

/*==============================================================================
 *  目录 / Table of Contents   按 Ctrl+F 搜索函数名、Ctrl+D快速跳转
 *
 *  工具函数          Stage_HasTreasure / Stage_CollectTreasure
 *                    GyroStableReset / Stage_DetectedRamp
 *                    RampCtrl_Blocking / Stage_Action
 * 					  Stage_Correct/Arrived_Stage
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
 *                    update_route_by_door_1~4 / update_route_at_door_for_stageAB
 *  第二轮路线规划    get_newroute
 *  OCR 读数字        WaitFor_OCR
 *  QR 码读取         WaitFor_QR
 *  启动流程          zhunbei
 *  路线连接          Connect
 *============================================================================*/



/*===== 调试：预设5个门颜色，door() 自动读取 =====*/
//uint8_t door_pass[5] = {ONE_WAY_PASS, CAN_PASS, NO_PASS, NO_PASS, NO_PASS};
uint8_t door_pass[5] = {0, 0, 0, 0, 0};
#if DEBUG
uint8_t debug_door_pass[5] = {ONE_WAY_PASS, CAN_PASS, NO_PASS, NO_PASS, NO_PASS}; // 0:D2、1:D3、2:D4、3:D5、4:D1
volatile uint8_t flag_line_clue    = 0;
volatile uint8_t flag_clue_stage_A = 5;
volatile uint8_t flag_clue_stage_B = 7;
// OCR 线索：P5/P6读clue_A，P7/P8读clue_B，treasure=clue_A+clue_B → 宝物平台编号
uint8_t flag_clue_A       = 2;
uint8_t flag_clue_B       = 0;
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
								//       Stage_HasTreasure() → Stage () 判断当前平台是否是宝物平台

volatile uint8_t get_cude = 0;
uint8_t head_right_left = 0;

/* MaixCam识别较慢：每轮保持模式的最长等待时间（FreeRTOS tick） */
#define MAIXCAM_QR_WAIT_TICKS     800U  /* 1000 × 3ms ≈ 2.4s */
#define MAIXCAM_OCR_WAIT_TICKS    800U  /* 1500 × 3ms ≈ 2.4s */
#define MAIXCAM_COLOR_WAIT_TICKS  1000U  /* 2000 × 2ms ≈ 4.0s */

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
	Robot_Work(RARM, UP);		//右手举起
	vTaskDelay(500);
	send_play_specified_command(9);
	Chassis_Turn360_Blocking();
	Robot_Work(LARM, DOWN);		//左手放下
	Robot_Work(RARM, DOWN);		//右手放下


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
	while(1){
	Cross_getline(&Cross_Scaner);
	if(fabsf(Chassis_GetMileage()) >= distance||
		//imu.pitch >= Begin_up + 4 ||
		Cross_Scaner.ledNum >= 7 ||
		Cross_Scaner.lineNum >= 4 
	 ){
		send_play_specified_command(36);
		return 1;}
	vTaskDelay(1);
	}
	
}

static void Stage_Correct(){
	uint8_t state =0;
	uint8_t state2_retry = 0;  // case2 无线形重试计数，防卡死
	uint16_t break_time = 0;	// case2 无线形重试计数，防卡死
	Chassis_DriveDistance_Blocking(is_Gyro, 5, -GoStage_Speed, getAngleZ(), 0);
	Chassis_MotorControl(is_Gyro, GoStage_Speed, GoStage_Speed, getAngleZ());
	while(state!=3)
	{
		Cross_getline(&Cross_Scaner);
		switch (state)
		{
		case 0:
			if(++break_time>700)state = 3;	// 超时退出
			if((Cross_Scaner.ledNum>=15))
			{
				state = 1;
			}
			break;  
		case 1:
			if((Cross_Scaner.ledNum<15))
			{
				state = 2;
				vTaskDelay(5);
				CarBrake();
			}
			break;
		case 2:
			//vTaskDelay(1000);
			Cross_getline(&Cross_Scaner);
			if(Cross_Scaner.detail & 0xE000)
			{
				send_play_specified_command(33);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -GoStage_Speed, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+30, getAngleZ(), 20.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 12, GoStage_Speed, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ()-30, getAngleZ(), 20.0f);
				state = 3;
			}
			else if(Cross_Scaner.detail & 0x0007)
			{
				send_play_specified_command(33);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -GoStage_Speed, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ()-30, getAngleZ(), 20.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 12 , GoStage_Speed, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+30, getAngleZ(), 20.0f);
				state = 3;
			}
			else if(Cross_Scaner.detail & 0x1800)
			{
				send_play_specified_command(33);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -GoStage_Speed, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+15, getAngleZ(), 20.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 12, GoStage_Speed, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ()-15, getAngleZ(), 20.0f);
				state = 3;
			}
			else if(Cross_Scaner.detail & 0x0018)
			{
				send_play_specified_command(33);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -GoStage_Speed, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ()-15, getAngleZ(), 20.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 12, GoStage_Speed, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+15, getAngleZ(), 20.0f);
				state = 3;
			}
			else
			{
				state = 3;
			}
			break;
		}	
		vTaskDelay(1);
	}
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
	vTaskDelay(300);
	Robot_Work(RARM, UP);
	vTaskDelay(200);
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
	Robot_Work(RARM, DOWN);
}

static void Stage_Action(float oringinal_angle)
{
	uint8_t stage_state = 0;
	uint8_t again_required = 0;
	float now_angle = 0;

	while(stage_state!=4){
		//撞击
		if (stage_state == 0 || again_required)
		{
			if(again_required){Chassis_DriveDistance_Blocking(is_Gyro,40,GoStage_Speed,getAngleZ(),0);
				//Chassis_DriveDistance_Blocking(is_Free, 8,2000, 0, 0);
				}
			else {Chassis_DriveDistance_Blocking(is_Gyro,40,GoStage_Speed,oringinal_angle,0);
				//Chassis_DriveDistance_Blocking(is_Free, 8,2000, 0, 0);
				}
			CarBrake();
			
			mpuZreset(get_latest_yaw(), nodes.nowNode.angle);
	
			Chassis_DriveDistance_Blocking(is_Gyro,6,-GoStage_Speed,getAngleZ(),0);

			//后退一段距离
			
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
		if((stage_state==2 || again_required )&& treasure == 0)
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
		if(stage_state == 3 || treasure )
		{
			Arrived_Stage();
			stage_state = 4;
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
		STAGE_DESCEND,  // 下坡：RampCtrl_Blocking 处理
		STAGE_DONE       // 清标志，结束
	} state = STAGE_ASCEND;

	uint8_t sub_stage = 0;
	
	float oringinal_angle = 0;
	Chassis_EnableAntiSnake();
	Chassis_MotorControl(is_Line, 15, 15, 0);//25
	Chassis_OverrideLinePid(24, 0, 140, 30);
	Chassis_ClearMileage();

	while (state != STAGE_DONE)
	{
		switch (state)
		{
		case STAGE_ASCEND:
			if (Stage_DetectedRamp(40))
			{
				Chassis_RestoreLinePid();
				oringinal_angle = getAngleZ();
				RampCtrl_Blocking(RAMP_ASCEND, 15, oringinal_angle,
					Begin_up, UpDownStage_Speed_low, up_pitch, UpDownStage_Speed_low, After_up, 0.08, 20.0f, 0.0f);

				Chassis_MotorControl(is_Gyro, GoStage_Speed, GoStage_Speed, oringinal_angle);
				state = STAGE_TOP;
			}
			break;

		case STAGE_TOP:
			Robot_Work(BODY, UP); 	//人站起来
			Stage_Action(oringinal_angle);

			if(Stage_HasTreasure())
				Stage_CollectTreasure();
			if(nodes.nowNode.nodenum != P3 && nodes.nowNode.nodenum != P4 && nodes.nowNode.nodenum != P5)
				Stage_Correct();

			Robot_Work(BODY, DOWN); 	//人躺下
			state = STAGE_DESCEND;
			break;

		case STAGE_DESCEND:
			oringinal_angle = getAngleZ();
			
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, getAngleZ(),
				Begin_down, UpDownStage_Speed_low, down_pitch, UpDownStage_Speed_high, After_down-8, 0.1, 15.0f, 40.0f);

			Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
			state = STAGE_DONE;
			break;
		default:
			break;
		}
		vTaskDelay(2);
	}

	/* 保留 nodes.nowNode.function=UpStage：map.c Nav_TurnAndAdvance 靠它跳过
	   "下平台后的补偿距离+原地转弯"（平台内部已180°转身+下坡回到坡底，朝向已对准 return 边） */
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

	Chassis_MotorControl(is_Line,15, 15, 0);
	Chassis_ClearMileage();

	while (state != P2_DONE)
	{
		switch (state)
		{
		case P2_ASCEND:
			if (Stage_DetectedRamp(36))
			{
				oringinal_angle = getAngleZ();
				//回家恢复原形
				Robot_Work(LARM, DOWN);		//左手放下		
				Robot_Work(RARM, DOWN);		//右手放下
				Robot_Work(BODY, UP);		//人站起来
				vTaskDelay(100);
				Robot_Work(CAMERA,HEAD_MID);
				RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, oringinal_angle,
					Begin_up, UpDownStage_Speed_low, up_pitch, UpDownStage_Speed_low, After_up, 0.05, 10.0f, 0.0f);

				Chassis_MotorControl(is_Gyro, GoStage_Speed, GoStage_Speed, oringinal_angle);			
				state = P2_TOP;
			}
			break;

		case P2_TOP:
			Chassis_DriveDistance_Blocking(is_Gyro, 18, GoStage_Speed, getAngleZ(), 0);
			CarBrake();
	

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

	
	/* 保留 nodes.nowNode.function=UpStageHome：map.c Nav_TurnAndAdvance 靠它跳过
	   "返程上平台后的补偿距离+原地转弯" */
	cross_event |= CROSS_EVENT_ARRIVED;	// 到达路口
}

/*长桥*/
/** 桥面修正参数 */
#define BRIDGE_CENTERED_THRESHOLD   30      // 连续无红外信号次数（~20-100ms）
#define BRIDGE_EMERGENCY_ANGLE      4.5f    // 巡线板最外侧扫到红线时的硬跳角度
#define BRIDGE_EMERGENCY_ANGLE_2       2.0f   // 巡线板最外侧扫到红线时的硬跳速度

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
	Chassis_EnableAntiSnake();
	Chassis_MotorControl(is_Line, 15, 15, 0);
	Chassis_OverrideLinePid(30, 0, 170, 30);
	Chassis_ClearMileage();
	uint16_t is_emergency = 0;
	while (state != BRIDGE_DONE)
	{
		switch (state)
		{
		case BRIDGE_APPROACH:
			GyroStableReset(40, &origin_angle);

			if (Stage_DetectedRamp(48))//检测到桥
			{
				Chassis_RestoreLinePid();
				if(origin_angle == 0)origin_angle = getAngleZ();				
				state = BRIDGE_ASCEND;
			}
			break;

		case BRIDGE_ASCEND://上桥
			//上桥上一半
			RampCtrl_Blocking(RAMP_ASCEND, 15, origin_angle,
				Begin_up, 15, up_pitch, UpDownStage_Speed_low, up_pitch+20, 0, 10.0f, 0.0f);
			//加一点修正
			Chassis_ClearMileage();
	
			while (fabsf(Chassis_GetMileage()) < 18)
			{		
				Chassis_CorrectByInfrared(0.07f, 1.0f, 0.0f);
				vTaskDelay(5);
			}
			//上桥结束检测
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, getAngleZ(),
				0, UpDownStage_Speed_low, 0, UpDownStage_Speed_low, After_up, 0, 10.0f, 24);

			Chassis_ClearMileage();
			state = BRIDGE_ON_BRIDGE_TOP;
			break;

		case BRIDGE_ON_BRIDGE_TOP:
		
			
			Cross_getline(&Cross_Scaner);	// 桥上为陀螺仪模式，Scaner 不更新，主动拍快照
			float mileage_br = fabsf(Chassis_GetMileage());

			//第1层：巡线板最外侧紧急处理
			if (Cross_Scaner.detail & 0x7800)
			{
				if(is_emergency < 500)is_emergency++;
				if(is_emergency == 10 || is_emergency == 400)
				{
					centered_samples = 0;
					send_play_specified_command(33);
					if(is_emergency == 10)
					angle.AngleG = getAngleZ() - BRIDGE_EMERGENCY_ANGLE;
					else	
						angle.AngleG = getAngleZ() - BRIDGE_EMERGENCY_ANGLE_2;
					Chassis_SetTargetSpeed(UpDownStage_Speed_low);
				}
			}

			else if (Cross_Scaner.detail & 0x007E)
			{
				if(is_emergency < 500)is_emergency++;
				if(is_emergency == 10 || is_emergency == 400)
				{
					centered_samples = 0;
					send_play_specified_command(33);
					if(is_emergency == 10)
						angle.AngleG = getAngleZ() + BRIDGE_EMERGENCY_ANGLE;
					else
						angle.AngleG = getAngleZ() + BRIDGE_EMERGENCY_ANGLE_2;
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
					if(TG_speed<=20.0f){
						Chassis_CorrectByInfrared(0.05f, 1.5f, 1.5f);
					}
					else{Chassis_CorrectByInfrared(0.02f, 1.3f, 1.0f);}
					
					Chassis_SetTargetSpeed(SPEED1);
				}
			}
			// 距离退出（保险兜底）
			
			if (mileage_br >= 78)
			{
				centered_samples = 0;
				state = BRIDGE_ON_BRIDGE;
			}
			else if (mileage_br >= 72)
			{
				Chassis_SetTargetSpeed(UpDownStage_Speed_low);
				Chassis_CorrectByInfrared(0.05f, 1.5f, 1.5f);
			}
			break;
		

		case BRIDGE_ON_BRIDGE:

			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, getAngleZ(),
				Begin_down, UpDownStage_Speed_low, down_pitch, SPEED0, down_pitch-20,0, 0, 0.0f);//下坡下一半

			//加一点修正
			Chassis_ClearMileage();
			get_Infrared();
			while (fabsf(Chassis_GetMileage()) < 18)
			{	
				Chassis_CorrectByInfrared(0.04f, 1.0f, 1.0f);
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
	Chassis_EnableAntiSnake();
	Chassis_MotorControl(is_Line, 15, 15, 0);
	Chassis_OverrideLinePid(30, 0, 180, 30);
	//vTaskDelay(10);//刚进入is_line,scanner可能还没数据，先等motortask
	Chassis_OverrideGyroPid(7,0,80,50);//上坡陀螺参数，增加kp和kd提高陀螺响应，防止上坡时姿态失稳
	Chassis_ClearMileage();
	while (state != HILL_DONE)
	{
		switch (state)
		{
		case HILL_APPROACH:
			GyroStableReset(50, &origin_angle);
				
			if (Stage_DetectedRamp(60.0f))
			{
				Chassis_RestoreLinePid();
				if (origin_angle == 0) origin_angle = getAngleZ();
 			
				Chassis_MotorControl(is_Gyro, 15, 15, origin_angle);
			
				state = HILL_ASCEND;
			}
			break;

		case HILL_ASCEND:
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, origin_angle,
				basic_p+5, UpDownStage_Speed_low, basic_p+15, UpDownStage_Speed_low, basic_p+5, 0.1f, 10.0f, 0.0f);
	
			state = HILL_DESCEND;
			break;

		case HILL_DESCEND:
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, getAngleZ(),
				basic_p, UpDownStage_Speed_high, basic_p-10, UpDownStage_Speed_high, basic_p-3, 0.1f, 15.0f, 42);
  
			state = HILL_DONE;
			break;

		default:
			Chassis_MotorControl(is_Line, SPEED1, SPEED1, 0);
			state = HILL_DONE;
			break;
		}
		vTaskDelay(2);
	}
	Chassis_RestoreGyroPid();
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

		SM_DONE
	} state = SM_APPROACH;

	float recorded_angle = 0;
	uint8_t angle_recorded = 0,is_up = 0;
	uint16_t approach_timeout = 0;
	Chassis_EnableAntiSnake();
	Chassis_MotorControl(is_Line, 15, 15, 0);
	Chassis_OverrideLinePid(30, 0, 180, 30);
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
			if (Cross_Scaner.ledNum >= 5 )
			{
				if (!angle_recorded)
					recorded_angle = getAngleZ();
				send_play_specified_command(36);
				Chassis_RestoreLinePid();
				Chassis_MotorControl(is_Gyro, 15 , 15 , recorded_angle);
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
			if(fabsf(Chassis_GetMileage()) < 18 ){
				Sword_CorrectByScanner(0.05f);
			}
			else if(fabsf(Chassis_GetMileage()) >= 18&&fabsf(Chassis_GetMileage()) < 66)
			{			
				Chassis_MotorControl(is_Free, 2500, 2500, 0);
			}
			else
			{
				Chassis_MotorControl(is_Gyro, Gyro_Speed , Gyro_Speed , recorded_angle);
			}

			Cross_getline(&Cross_Scaner);
			// 平台走完 or pitch 变负（开始下坡）
			if (fabsf(Chassis_GetMileage()) > 80 || imu.pitch < After_down|| Cross_Scaner.ledNum <= 3)
			{
				state = SM_DONE;
			}
			break;

		}
		vTaskDelay(1);
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
	Chassis_EnableAntiSnake();
	Chassis_MotorControl(is_Line, 15, 15, 0);
	Chassis_OverrideLinePid(30, 0, 180, 30);
	Chassis_SetTrackMode(TRACK_NEAR_CENTER);
	Chassis_ClearMileage();
	while (state != HM_DONE)
	{
		switch (state)
		{
		case HM_APPROACH:

			if (Stage_DetectedRamp(36))
			{
				Chassis_RestoreLinePid();
				state = HM_ASCEND_1;
			}
			break;

		case HM_ASCEND_1:
			//让车抬起后马上退出
			RampCtrl_Blocking(RAMP_ASCEND, 15, getAngleZ(),
				Begin_up, 15, up_pitch, 20, up_pitch+30, 0.07f, 10.0f, 24);
			//用循迹走
			Chassis_DriveDistance_Blocking(is_Line, 42, 20, 0, 0);
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
			RampCtrl_Blocking(RAMP_ASCEND, 20, getAngleZ(),
				Begin_up, 20, up_pitch, 20, up_pitch+30, 0.07f, 10.0f, 24);
			Chassis_DriveDistance_Blocking(is_Line, 42, 20, 0, 0);
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, getAngleZ(),
				Begin_up, UpDownStage_Speed_low, up_pitch, UpDownStage_Speed_low, After_up, 0.07f, 10.0f, 0.0f);
			state = HM_IMPACT;
			break;

		case HM_IMPACT:
			Robot_Work(BODY, UP); 	//人站起来
			//平台动作
			Stage_Action(getAngleZ());

			if (treasure == 0)
			{
				treasure = flag_clue_A + flag_clue_B;
			}
			if (map.routetime == 0 && flag_clue_stage_B == 8)
				update_route_at_P8_for_treasure();
			Stage_Correct();

			Robot_Work(BODY, DOWN); 	//人坐下
			origin_angle = getAngleZ();
			sub_stage = 0;
			state = HM_DESCEND_1;
			break;

		case HM_DESCEND_1:
			//Chassis_DriveDistance_Blocking(is_Free, 10, 500, 0, 0);
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, origin_angle,
				Begin_down, UpDownStage_Speed_low, down_pitch, 20, down_pitch-30, 0.07f, 10.0f, 0.0f);
			Chassis_DriveDistance_Blocking(is_Line, 48, 20, 0, 0);
			RampCtrl_Blocking(RAMP_DESCEND, 20, origin_angle,
				Begin_down, 20, down_pitch, 20, After_down, 0.07f, 10.0f, 0.0f);
			state = HM_DESCEND_FLAT;
			break;

		case HM_DESCEND_FLAT:
			Chassis_MotorControl(is_Gyro, UpDownStage_Speed_low-2, UpDownStage_Speed_low-2, origin_angle);
			if (imu.pitch <= Begin_down)
			{
				state = HM_DESCEND_2;
			}
			break;

		case HM_DESCEND_2:
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, origin_angle,
				Begin_down, UpDownStage_Speed_low, down_pitch, 20, down_pitch-30, 0.07f, 10.0f, 0.0f);
			Chassis_DriveDistance_Blocking(is_Line, 48, 20, 0, 0);
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

/*波浪板 — 状态机版本*/
void Barrier_WavedPlate(float lenght)
{
	enum {
		WP_APPROACH,   // 巡线接近，Stage_DetectedRamp 检测波浪板入口
		WP_DRIVE,      // RampCtrl_Blocking 用不可能俯仰角直走 lenght 距离
		WP_DONE        // 清理收尾
	} state = WP_APPROACH;
	Chassis_EnableAntiSnake();
	Chassis_MotorControl(is_Line, 15, 15, 0);
	Chassis_OverrideLinePid(24, 0, 140, 30);
	Chassis_OverrideGyroPid(4, 0, 50, 50);
	Chassis_ClearMileage();

	while (state != WP_DONE)
	{
		switch (state)
		{
		case WP_APPROACH:
			if (Stage_DetectedRamp(60))
			{
				Chassis_RestoreLinePid();
				//buzzer_on();
				state = WP_DRIVE;
			}
			break;

		case WP_DRIVE:
			// 俯仰角阈值设 100（不可能达到），只靠 max_distance=lenght 退出
			RampCtrl_Blocking(RAMP_ASCEND, BL_Speed, getAngleZ(),
				100, BL_Speed, 100, BL_Speed, 100, 0.05f, 0, lenght);
			//buzzer_off();
			state = WP_DONE;
			break;

		default:
			Chassis_RestoreGyroPid();
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

	Chassis_OverrideGyroPid(4, 0, 50, 50);
	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
	Chassis_ClearMileage();

	while (state != SP_DONE)
	{
		switch (state)
		{
		case SP_APPROACH:
			if (Stage_DetectedRamp(36))
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
			if (map.routetime == 0 && flag_clue_stage_B == 7)
				update_route_at_P7_for_treasure();
				
			Stage_Correct();
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
	/* 保留 nodes.nowNode.function=BSoutPole：map.c Nav_TurnAndAdvance 靠它跳过
	   "下南极后的补偿距离+原地转弯"（南极内部已180°转身+下坡回到坡底，朝向已对准 return 边） */
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
				{ const u8 r[] = {N22,B6,N20,C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
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
				{ const u8 r[] = {N22,B6,N20,P8,N20,C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
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
				{ const u8 r[] = {N22,B6,N20,P8,N20,C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
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
				{ const u8 r[] = {N22,B6,N20,C4,B11,C8,C7,B10,N14,C3,N9,N10,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {N22,B6,N20,C4,B11,C8,C7,B10,N14,C3,N9,N10,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N11,N10,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {N22,B6,N20,C4,B11,C8,C7,B10,N14,C3,N9,N10,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
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
				{ const u8 r[] = {N22,B6,N20,C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
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
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N11,N12,N5,N4,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N11,N12,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N11,N12,N13,P5,N13,N12,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N11,N12,N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
		}
	}
	if(treasure != 0&&door_pass[1] == CAN_PASS)//D3绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N8,N5,N4,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N8,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N11,N12,N13,P5,N13,N12,N8,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N8,N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	     }
    }
	if(treasure != 0&&door_pass[2] == CAN_PASS)//D4绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N8,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N8,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N11,N12,N13,P5,N13,N12,N8,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N8,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	    }
	}
	if(treasure != 0&&((door_pass[0] == ONE_WAY_PASS)||(door_pass[1] == ONE_WAY_PASS)))//D2D3蓝灯(单相通过)
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N11,N10,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			default:

                break;	
	    }
	}
	if(treasure != 0&&door_pass[2] == ONE_WAY_PASS)//D4蓝灯(单相)D5必绿
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N3,P3,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 4:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 5:
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N11,N10,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 6:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF}; load_route_at(map.point, r); break; }
			case 2:
				{ const u8 r[] = {C4,B11,C8,C7,B10,N14,C3,N9,N10,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; load_route_at(map.point, r); break; }
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
			//改变小车循迹中心，根据实际情况硬补偿
			Chassis_SetCatchSensorNum(line_weight_default[CENTER]);
			//改变循迹模式为左边循迹
			Chassis_SetTrackMode(TRACK_LEFT_EDGE);
			
			//改变电机控制模式为巡线模式
			Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
			Chassis_OverrideLinePid(17,0.01f,50,30);

			//等待小车行驶10cm后，改变循迹模式为中间循迹
			Chassis_ClearMileage();
			while(Chassis_GetMileage() < 60)vTaskDelay(2);	
			Chassis_SetTrackMode(TRACK_NEAR_CENTER);
			Chassis_ClearMileage();
			
			state = QQB_WAIT_PITCH;
			break;

		case QQB_WAIT_PITCH:
			
			Cross_getline(&Cross_Scaner);
			//防止循迹受到旁边红线的干扰
			//if(imu.pitch>=After_up ||Cross_Scaner.ledNum>=4||Cross_Scaner.lineNum>=2)Chassis_SetEdgeIgnore(4);
			//等待对其
			if ((imu.yaw >=65&&imu.yaw <=115)||(imu.yaw <=-65&&imu.yaw >=-115)
			)
			{		
				Chassis_OverrideGyroPid(4, 0, 70, 5);  
				Chassis_MotorControl(is_Gyro, 15, 15, getAngleZ()>0?90:-90);
				Chassis_CorrectByInfrared(0.05f, 1.5f, 1.5f);	
			}
			//等待小车爬上跷跷板，俯仰角大于 up_pitch 进入下一状态
			if(imu.pitch> basic_p+25)
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
			
			//优先级最高：俯仰角过大（车头抬起过高）→ 退车重试；触发后本轮回车完毕即break，不再走紧急避障
			if(imu.pitch>55+basic_p){
				Chassis_DriveDistance_Blocking(is_Gyro, 15, -SPEED0, getAngleZ(), 0);
				CarBrake();
				vTaskDelay(500);
				state = QQB_WAIT_PITCH;
				break;
			}

			//第1层：巡线板最外侧紧急处理（与上方pitch>55互斥，一次只退一个）
			if ((Cross_Scaner.detail & 0x1C00)&&is_emergency==1)
			{	
				is_emergency++;
				send_play_specified_command(33);
				send_play_specified_command(33);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 20, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 12, -SPEED0, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() - 20, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 23, SPEED0, getAngleZ(), 0);
			}
			else if ((Cross_Scaner.detail & 0x0038)&&is_emergency==1)
			{			
				is_emergency++;
				send_play_specified_command(33);
				send_play_specified_command(33);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() - 20, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 12, -SPEED0, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 20, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 23, SPEED0, getAngleZ(), 0);
			}
			else if ((Cross_Scaner.detail & 0xF000)&&is_emergency==1)
			{	
				is_emergency++;
				send_play_specified_command(33);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 10, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 12, -SPEED0, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() - 10, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 23, SPEED0, getAngleZ(), 0);
				
			}
			else if ((Cross_Scaner.detail & 0x000F)&&is_emergency==1)
			{			
				is_emergency++;
				send_play_specified_command(33);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() - 10, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 12, -SPEED0, getAngleZ(), 0);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 10, getAngleZ(), 15.0f);
				Chassis_DriveDistance_Blocking(is_Gyro, 23, SPEED0, getAngleZ(), 0);
				
			}
			else if(is_emergency){
			is_emergency=0;
			Chassis_MotorControl(is_Gyro, 15, 15, getAngleZ()>0?90:-90);
			Chassis_ClearMileage();
			}

			if(is_emergency==0)Chassis_CorrectByInfrared(0.05f, 1.5f, 1.5f);

			if(Chassis_GetMileage() > 48 && is_emergency == 0)
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
			if(break_cnt > 500){Chassis_DriveDistance_Blocking(is_Gyro, 5, 8,getAngleZ()>0?90:-90, 0);break_cnt=0;}

			if(p < up_pitch&&seen_negative==0){CarBrake(); break_cnt = 0;} 
			if (p < After_down)seen_negative = 1;	
			if (seen_negative==1)
			{ 

				vTaskDelay(300);	
				while(imu.pitch <= basic_p-40){vTaskDelay(2);}	
				vTaskDelay(100);
				//Chassis_Turn_By_StopGyro_Blocking(getAngleZ()>0?90:-90, getAngleZ(), 15.0f);
				Chassis_RestoreGyroPid();
				Chassis_MotorControl(is_Gyro, 15, 15, getAngleZ());	
				while(imu.pitch <= basic_p-10){vTaskDelay(2);}
				Chassis_Turn_By_Gyro_Blocking(getAngleZ()>0?150:-50, getAngleZ(), 25.0f);	
				seen_negative=2;				
			}
			if(seen_negative==2)
			{			
				if(p > After_down) 
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
	uint8_t dis = getAngleZ()>0?(uint8_t)(60):(uint8_t)(48);
	while(Chassis_GetMileage() < dis)vTaskDelay(2);

	float angle = getAngleZ();
	if(angle<0&&angle>-20){
	Chassis_MotorControl(is_Gyro, 15, 15,0);
	while(getAngleZ() < -5){Chassis_CorrectByInfrared(0.05f, 1.5f, 1.5f);vTaskDelay(2);	}
	}

	Chassis_RestoreLinePid();
	
	nodes.nowNode.function = 0;
	cross_event |= CROSS_EVENT_ARRIVED;
	
}

/* 门状态枚举，Door_ReadPass 在下方使用到，须在其之前定义 */
enum DoorState {
	DOOR_D2 = 0,   // 看D2
	DOOR_D3,        // 看D3
	DOOR_D4,        // 看D4
	DOOR_D5_BACK,   // 看D5
	DOOR_D4_BACK    // 看D4回退
};

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
static void door_retreat(uint8_t a, uint8_t b, float dis)
{
	Chassis_DriveDistance_Blocking(is_Gyro, dis, -SPEED2, getAngleZ(), 0);
	/* lastNode 保持真实来向（不再被覆盖）：D2黑退→D3 时 lastNode 应为 N5，由 door() 状态判定精确匹配 */
	nodes.nowNode = Node[getNextConnectNode(a, b)];
	Chassis_Brake();
	Chassis_Turn_By_StopGyro_Blocking(nodes.nowNode.angle, getAngleZ(), 30.0f);
}
/*看红绿灯 — 状态机*/
void door()
{
	enum DoorState state = DOOR_D2;	/* 兜底，防未初始化 */

	if(nodes.lastNode.nodenum == N5 && nodes.nowNode.nodenum == N12){state = DOOR_D2;}
	else if(nodes.lastNode.nodenum == N5 && nodes.nowNode.nodenum == N8){state = DOOR_D3;}
	else if(nodes.lastNode.nodenum == N3 && nodes.nowNode.nodenum == N8){state = DOOR_D4;}
	else if(nodes.lastNode.nodenum == N8 && nodes.nowNode.nodenum == N3){state = DOOR_D4_BACK;}	/* 回家过D4: N8→N3 */
	else if(nodes.lastNode.nodenum == N10 && nodes.nowNode.nodenum == N3){state = DOOR_D5_BACK;}	/* 回家过D5: N10→N3 */


	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);

	while (Scaner.ledNum < 8)
		vTaskDelay(2);

	if(state != DOOR_D5_BACK && state != DOOR_D4_BACK)
	{
		CarBrake();
		Chassis_Turn_By_StopGyro_Blocking(nodes.nowNode.angle, getAngleZ(), 30.0f);
		Robot_Work(CAMERA, HEAD_RIGHT);
   		vTaskDelay(500);
	}
	else
	{
		Chassis_DriveDistance_Blocking(is_Line, 28, 15, 0, 0);
		CarBrake();
		Robot_Work(CAMERA, HEAD_LEFT);
   		vTaskDelay(500);
	}
	
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
			door_retreat(N5, N8, DOOR_RETREAT_N5N8);
			cross_event |= CROSS_EVENT_DOOR;
			
		}
		else if (door_pass[0] == CAN_PASS)
		{
			send_play_specified_command(8);
			door_set_pass_node(N5, N12, DOOR_LEN_N5N12, SPEED4);
			door_set_pass_node(N12, N5, DOOR_LEN_N5N12, SPEED4);
			nodes.nowNode = Node[getNextConnectNode(N5, N12)];
			nodes.nowNode.step = 72;
			nodes.nowNode.speed = SPEED4;
			update_route_at_door_for_stageAB();
			cross_event |= CROSS_EVENT_DOOR;
		
		}
		else // ONE_WAY_PASS
		{
			send_play_specified_command(10);
			door_set_pass_node(N5, N12, DOOR_LEN_N5N12, SPEED4);
			nodes.nowNode = Node[getNextConnectNode(N5, N12)];
			nodes.nowNode.flag = DLEFT | DRIGHT | CRIGHT | LEFT_LINE;
			nodes.nowNode.step = 72;
			nodes.nowNode.speed = SPEED4;
			update_route_at_door_for_stageAB();
			cross_event |= CROSS_EVENT_DOOR;
			
		}
		break;

	case DOOR_D3:
		door_pass[1] = pass_state;
		if (door_pass[1] == NO_PASS)
		{
			send_play_specified_command(11);
			door_retreat(N5, N4, DOOR_RETREAT_N5N4);
			load_route_at(0, door1route);
			cross_event |= CROSS_EVENT_DOOR;
			
		}
		else // CAN_PASS 或 ONE_WAY_PASS
		{
			door_set_pass_node(N5, N8, DOOR_LEN_N5N8, SPEED3);
			nodes.nowNode = Node[getNextConnectNode(N5, N8)];
			nodes.nowNode.step = 50;
			nodes.nowNode.speed = SPEED4;
			update_route_at_door_for_stageAB();

			if (door_pass[1] == CAN_PASS)
			{
				door_set_pass_node(N8, N5, DOOR_LEN_N5N8, SPEED3);
				send_play_specified_command(8);
			
			}
			else // ONE_WAY_PASS
			{
				send_play_specified_command(10);
			
			}
			cross_event |= CROSS_EVENT_DOOR;
		}
		break;

	case DOOR_D4:
		door_pass[2] = pass_state;
		if (door_pass[2] == CAN_PASS)
		{
			send_play_specified_command(8);
			door_set_pass_node(N8, N3, DOOR_LEN_N3N8, SPEED3);
		}
		else if (door_pass[2] == NO_PASS)
		{
			// 兜底：D4读不到时停车，避免被当成蓝灯
			CarBrake_Stop();
		}
		else // ONE_WAY_PASS
		{
			send_play_specified_command(10);
			door_set_pass_node(N10, N3, DOOR_LEN_N3N10, SPEED3);
		}
		door_set_pass_node(N3, N8, DOOR_LEN_N3N8, SPEED3);
		nodes.nowNode = Node[getNextConnectNode(N3, N8)];
		nodes.nowNode.step = 72;
		nodes.nowNode.speed = SPEED4;
		update_route_at_door_for_stageAB();
		cross_event |= CROSS_EVENT_DOOR;
		
		break;

	case DOOR_D5_BACK:
		
		door_pass[3] = pass_state;
		if (door_pass[3] == CAN_PASS)
		{
			send_play_specified_command(8);
			door_set_pass_node(N10, N3, DOOR_LEN_N3N10, SPEED3);
			nodes.nowNode = Node[getNextConnectNode(N10, N3)];
			nodes.nowNode.step = 36;
			nodes.nowNode.speed = SPEED3;
			cross_event |= CROSS_EVENT_DOOR;
			update_route_by_door_1();
			
		}
		else // NO_PASS，蓝灯(单相)已经被消耗
		{
			send_play_specified_command(11);
			if (door_pass[0] == ONE_WAY_PASS)
			{
				/* 公共初始化已把 map.point=0、route[0]=0xFF，
				   这里直接写 route[0]=N3：Nav_PostProcess 会用
				   getNextConnectNode(N8, N3) 解析出 D4 门边(N8→N3)，再次触发 door() */
				route[0] = N3;
				door_retreat(N10, N8, DOOR_RETREAT_N10N8);
				cross_event |= CROSS_EVENT_DOOR;
		
			}
			else if (door_pass[0] == NO_PASS && door_pass[1] == ONE_WAY_PASS)
			{
				door_retreat(N10, N8, DOOR_RETREAT_N10N8);
				door_set_pass_node(N3, N8, DOOR_LEN_N3N8, SPEED3);
				door_set_pass_node(N8, N3, DOOR_LEN_N3N8, SPEED3);
				update_route_by_door_2();
				cross_event |= CROSS_EVENT_DOOR;
		
			}
		}
		break;

	case DOOR_D4_BACK:
		door_pass[2] = pass_state;
		if (door_pass[2] == CAN_PASS)
		{
			send_play_specified_command(8);
			door_set_pass_node(N3, N8, DOOR_LEN_N3N8, SPEED3);
			door_set_pass_node(N8, N3, DOOR_LEN_N3N8, SPEED3);
			nodes.nowNode = Node[getNextConnectNode(N8, N3)];
			nodes.nowNode.step = 36;
			nodes.nowNode.speed = SPEED3;
			nodes.nowNode.function = NONE;
			cross_event |= CROSS_EVENT_DOOR;
			update_route_by_door_3();
			motor_pid_clear();
		}
		else // NO_PASS
		{
			send_play_specified_command(11);
			/* 必须先改 Node[] 再 door_retreat 拷贝 nowNode：
			   N8→N5 边原定义为 SPEED0+DOOR，若 retreat 先拷贝，nowNode 会拿到旧值，
			   导致 N8→N5 段慢走且快到 N5 时二次触发 door()（lastNode=N8,nowNode=N5 无匹配分支→乱转）。
			   放行 D3 门后 N8→N5 应作为普通可通行边（NONE）直接回家 */
			door_set_pass_node(N8, N5, DOOR_LEN_N5N8, SPEED3);
			door_set_pass_node(N5, N8, DOOR_LEN_N5N8, SPEED3);
			door_retreat(N8, N5, DOOR_RETREAT_N8N5);
			nodes.nowNode.function = NONE;   // 保险：确保 N8→N5 段不再触发 )
			cross_event |= CROSS_EVENT_DOOR;
			update_route_by_door_4();
		}
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

void update_route_at_door_for_stageAB(void)
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

/*第二轮路线规划：走所有平台(P1~P8)后回家(P2)  */
/*拼接第二轮路线：pre+entry+tour+tail 写入 route[]，0XFF 结尾*/
static void build_round2_route(const u8 *pre, const u8 *entry, const u8 *tour, const u8 *tail)
{
	uint8_t i, n = 0;
	for (i = 0; pre[i] != 0XFF; i++)	route[n++] = pre[i];
	for (i = 0; entry[i] != 0XFF; i++)	route[n++] = entry[i];
	for (i = 0; tour[i] != 0XFF; i++)	route[n++] = tour[i];
	for (i = 0; tail[i] != 0XFF; i++)	route[n++] = tail[i];
	route[n] = 0XFF;
}

void get_newroute(void)
{
	const u8 r[] = {B1, N1, P1, 0XFF};
	load_route_at(0, r);
	mapInit();
	//全部运行通行
	door_set_pass_node(N5, N12, DOOR_LEN_N5N12, SPEED4);
	door_set_pass_node(N12, N5, DOOR_LEN_N5N12, SPEED4);
	door_set_pass_node(N5, N8, DOOR_LEN_N5N8, SPEED4);
	door_set_pass_node(N8, N5, DOOR_LEN_N5N8, SPEED4);
	door_set_pass_node(N3, N8, DOOR_LEN_N3N8, SPEED4);
	door_set_pass_node(N8, N3, DOOR_LEN_N3N8, SPEED4);
	door_set_pass_node(N3, N10, DOOR_LEN_N3N10, SPEED4);
	door_set_pass_node(N10, N3, DOOR_LEN_N3N10, SPEED4);

	//公共段：P1→P3→P4（到N5岔口）；东区巡游：P5→P7→P8→P6
	const u8 pre[]  = {B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N6,P4,N6,N5,0XFF};
	const u8 tour[] = {N13,P5,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,0XFF};
	// 宝藏=P6：车已在N10时先深入去P6，再P8→P7→P5绕回（终点改为N12，回程走N12→N8直连出东区，避开N11刀山）
	const u8 tour_p6[] = {N9,B9,N7,P6,N7,B8,N9,C3,N14,B10,C7,C8,B11,C4,N20,P8,N20,B6,N22,C9,P7,C9,N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,0XFF};
	const u8 *use_tour = (treasure == 6) ? tour_p6 : tour;

	//进东区终点按宝藏选：P6经N10（更近，且免走N12→N11刀山），其余经N12（去P5近）
	//D2进(N5→N12)：P6=N5→N12→N11→N10（D2门必经，已最优）；D3进(N5→N8)/最外进(N3→N8)：P6=N8→N10直达
	const u8 entry_D2_p6[]   = {N12,N11,N10,0XFF};
	const u8 entry_D2[]      = {N12,0XFF};
	const u8 entry_D3_p6[]   = {N8,N10,0XFF};
	const u8 entry_D3[]      = {N8,N12,0XFF};
	const u8 entry_far_p6[]  = {N4,N3,N8,N10,0XFF};
	const u8 entry_far[]     = {N4,N3,N8,N12,0XFF};
	const u8 *use_entry_D2  = (treasure == 6) ? entry_D2_p6  : entry_D2;
	const u8 *use_entry_D3  = (treasure == 6) ? entry_D3_p6  : entry_D3;
	const u8 *use_entry_far = (treasure == 6) ? entry_far_p6 : entry_far;

	//回程终点按宝藏选：P6=tour已止于N12（回程走N12→N8直连，避开N11刀山；或D2门直回N12→N5）
	//其余=tour止于N10，tail原样（分支3/4/5/7/8的tail本以N8开头，P6/NP6通用，不用改）
	const u8 tail_p6_D2[] = {N5,N4,B3,N2,P2,0XFF};
	const u8 tail_p6_D5[] = {N11,N10,N3,N4,B3,N2,P2,0XFF};

	if(door_pass[0]==CAN_PASS)//D2可双向：进N5→N12，回N12→N5
	{
		const u8 tail[]  = {N11,N12,N5,N4,B3,N2,P2,0XFF};
		build_round2_route(pre, use_entry_D2, use_tour, (treasure == 6) ? tail_p6_D2 : tail);
	}
	else if(door_pass[0]==ONE_WAY_PASS && door_pass[3]==CAN_PASS)//D2单向进，回D5(N10→N3)
	{
		const u8 tail[]  = {N3,N4,B3,N2,P2,0XFF};
		build_round2_route(pre, use_entry_D2, use_tour, (treasure == 6) ? tail_p6_D5 : tail);
	}
	else if(door_pass[0]==ONE_WAY_PASS && door_pass[3]==NO_PASS && door_pass[2]==CAN_PASS)//回D4(N8→N3)
	{
		const u8 tail[]  = {N8,N3,N4,B3,N2,P2,0XFF};
		build_round2_route(pre, use_entry_D2, use_tour, tail);
	}
	else if(door_pass[0]==ONE_WAY_PASS && door_pass[3]==NO_PASS && door_pass[2]==NO_PASS)//回D3(N8→N5)
	{
		const u8 tail[]  = {N8,N5,N4,B3,N2,P2,0XFF};
		build_round2_route(pre, use_entry_D2, use_tour, tail);
	}
	else if(door_pass[0]==NO_PASS && door_pass[1]==CAN_PASS)//D3双向：进N5→N8，回N8→N5
	{
		const u8 tail[]  = {N8,N5,N4,B3,N2,P2,0XFF};
		build_round2_route(pre, use_entry_D3, use_tour, tail);
	}
	else if(door_pass[0]==NO_PASS && door_pass[1]==ONE_WAY_PASS && door_pass[3]==CAN_PASS)//D3单向进，回D5(N10→N3)
	{
		const u8 tail[]  = {N3,N4,B3,N2,P2,0XFF};
		build_round2_route(pre, use_entry_D3, use_tour, (treasure == 6) ? tail_p6_D5 : tail);
	}
	else if(door_pass[0]==NO_PASS && door_pass[1]==ONE_WAY_PASS && door_pass[3]==NO_PASS)//D3单向进，回D4(N8→N3)
	{
		const u8 tail[]  = {N8,N3,N4,B3,N2,P2,0XFF};
		build_round2_route(pre, use_entry_D3, use_tour, tail);
	}
	else if(door_pass[0]==NO_PASS && door_pass[1]==NO_PASS && door_pass[2]==CAN_PASS)//从最外面进(N3→N8)，回D4
	{
		const u8 tail[]  = {N8,N3,N4,B3,N2,P2,0XFF};
		build_round2_route(pre, use_entry_far, use_tour, tail);
	}
	else if(door_pass[0]==NO_PASS && door_pass[1]==NO_PASS && door_pass[2]==ONE_WAY_PASS)//从最外面进，回D5(N10→N3)
	{
		const u8 tail[]  = {N3,N4,B3,N2,P2,0XFF};
		build_round2_route(pre, use_entry_far, use_tour, (treasure == 6) ? tail_p6_D5 : tail);
	}
	else
		CarBrake_Stop();
}

/*maixcam读数字*/
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
	uint8_t retry=0;

	is_clue_A_stage = ((nodes.nowNode.nodenum == P5  ||
		nodes.nowNode.nodenum == P6 )&& treasure==0);
	is_clue_B_stage = ((nodes.nowNode.nodenum == P7  ||
		(nodes.nowNode.nodenum == P8 )) && treasure==0);

	/* 已采集过 → 直接视为成功，避免重复扫描 */
	if ((is_clue_A_stage && clue_A_collected) || (is_clue_B_stage && clue_B_collected))
		return OCR_SCAN_SUCCESS;

	/* 不在二维码指定的平台 → 不读取 */
	if (!is_clue_A_stage && !is_clue_B_stage)
		return OCR_SCAN_FAILED;

	K210_Rece = 0;
	Clue_Num = 0;

	for (retry = 0; retry < 6; retry++)
	{
		uint16_t timeout = 0;
		/* 每轮开始时立即发送0x22，不能先空等 */
		open_OCR_mode();

		/* MaixCam识别较慢，保持OCR模式约2.4秒；收到有效结果立即退出 */
		while (!K210_Rece && timeout < MAIXCAM_OCR_WAIT_TICKS)
		{
			vTaskDelay(3);
			timeout++;
		}

		if (K210_Rece){
			if(retry >=2 && retry <=4){
				Chassis_DriveDistance_Blocking(is_Gyro, 4, -SPEED0, getAngleZ(), 0);
				CarBrake();
			}
			if(retry >=5){
				Chassis_DriveDistance_Blocking(is_Gyro, 4, SPEED0, getAngleZ(), 0);
				CarBrake();
			}
			break;
		}

		/* 本轮失败，关闭任务并调整摄像头/车位后再试 */
		close_Maxicam();
		if(retry==2)
		{
			Chassis_DriveDistance_Blocking(is_Gyro, 4, SPEED0, getAngleZ(), 0);
			CarBrake();
		}
		if(retry==5)
		{
			Chassis_DriveDistance_Blocking(is_Gyro, 7, -SPEED0, getAngleZ(), 0);
			CarBrake();
		}
		if ((retry & 1U) == 0)
		{moveServo(0, 1330, 1000);
		head_right_left=1;}
			
		else
			{moveServo(0, 1610, 1000);head_right_left=2;}
		vTaskDelay(1200);
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
		
		send_play_specified_command(16 + flag_clue_A);
		vTaskDelay(1500);
		
	}
	else
	{
		flag_clue_B = clue_value;
		clue_B_collected = 1;
		send_play_specified_command(23 + flag_clue_B);
		vTaskDelay(1500);
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
		else {Chassis_DriveDistance_Blocking(is_Gyro, 4, -SPEED0, getAngleZ(), 0);CarBrake();
			vTaskDelay(2000);
		}
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
	Robot_Work(CAMERA,HEAD_MID); //摄像头复位
	Robot_Work(BODY, UP); 	//人站起来
	Robot_Work(LARM, DOWN);		//左手放下
	Robot_Work(RARM, DOWN);		//右手放下
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
	Robot_Work(RARM, UP);		//右手举起
	vTaskDelay(500);
	Robot_Work(LARM, DOWN);		//左手放下
	Robot_Work(RARM, DOWN);		//右手放下
	vTaskDelay(500);
	Robot_Work(BODY, DOWN);		//人躺下

	//if(map.routetime==2)Stage_Correct();

	RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, getAngleZ(),
				Begin_down, UpDownStage_Speed_low, down_pitch, UpDownStage_Speed_high, After_down-10, 0.04, 10.0f, 0.0f);
		/*下桥完毕*/
		//printf("Finished crossing the bridge\n");
}






