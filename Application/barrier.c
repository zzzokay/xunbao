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

#define FORWARD_SPEED 5 //7
#define BACK_SPEED -3 //-15/-7
#define View_BACK_SPEED -20
#define IMPACT_SPEED 16
#define QQB_Speed 9
#define LiuShuiRate_Default	1.6				//默认流水倍率
#define LiuShuiRate_UM		2.1			//珠峰流水倍率//1.82
#define LiuShuiRate_USP		1.65			//南极流水倍率 //1.3 //1.65
#define LiuShuiRate_UB		1.9				//长桥流水倍率 //1.6
#define LiuShuiRate_ST		2.0				//平台流水倍率
#define LiuShuiRate_BG		1.8				//出发流水倍率

uint8_t WavePlateLeft_Flag = 0;
uint8_t WavePlateRight_Flag = 0;
uint8_t color_flag[5] = {0, 0, 0, 0, 0}; // 0:D2、1:D3、2:D4、3:D5、4:D1
uint8_t isStage = 0;

/*===== 调试：预设5个门颜色，door() 自动读取 =====*/
#if DEBUG
// debug_door_colors[0]=D2, [1]=D3, [2]=D4, [3]=D5, [4]=D1
// 值: Green=1, Yellow=2, Red=3, 0=未设置(会超时)

#endif      
uint8_t debug_door_colors[5] = {Red, Red, Green, Green, Yellow};  // D2、D3、D4、D5、D1

/*===== 导航标志位（无摄像头时手动预设）=====*/
// QR 码三位数：百位→flag_line_clue，十位→flag_clue_stage_A，个位→flag_clue_stage_B
// 例：QR 码 458 → flag_line_clue=4, flag_clue_stage_A=5, flag_clue_stage_B=8
uint8_t flag_line_clue    = 0;	// 百位：0=跳过P3/P4直接走门，3=先去P3，4=先去P4
								// 调用：update_route_for_stage34() → Stage() STAGE_SCAN 状态
uint8_t flag_clue_stage_A = 5;	// 十位：5=P5（原P6），6=P6（原P5）
uint8_t flag_clue_stage_B = 7;	// 个位：7=P7（原P8），8=P8（原P7）
								// 调用：update_route_by_QR() → door() 过门后规划路线
// OCR 线索：P5/P6读clue_A，P7/P8读clue_B，treasure=clue_A+clue_B → 宝物平台编号
uint8_t flag_clue_A = 0;		// P5/P6 线索数字
								// 调用：Sword_Mountain() / South_Pole() → treasure 计算
uint8_t flag_clue_B = 0;		// P7/P8 线索数字
								// 调用：Sword_Mountain() / South_Pole() → treasure 计算
uint8_t treasure = 0;			// 宝物平台编号 = flag_clue_A + flag_clue_B，自动计算
								// 调用：update_rout_by_treasure_7/8() → door() 确定宝物平台后回家路线
								//       Stage_HasTreasure() → Stage() 判断当前平台是否是宝物平台

uint8_t value;							 // openmv接口
uint8_t DownLiuShui = 0;				 // 流水下坡标志位
float 	LiuShuiRate = LiuShuiRate_Default; // 流水下坡前轮速度倍率
uint8_t special_arrive = 0;

uint16_t QR_code = 0;
uint8_t get_cude = 0;
uint8_t get_a = 0;
uint8_t get_b = 0;

static uint8_t Stage_HasTreasure(void)
{
	return ((nodesr.nowNode.nodenum == P1 && treasure == 2) ||
		(nodesr.nowNode.nodenum == P3 && treasure == 3) ||
		(nodesr.nowNode.nodenum == P4 && treasure == 4) ||
		(nodesr.nowNode.nodenum == P5 && treasure == 5) ||
		(nodesr.nowNode.nodenum == P6 && treasure == 6));
}

static void Stage_CollectTreasure(void)
{
	Chassis_MotorControl(is_No, FORWARD_SPEED, FORWARD_SPEED, 0);
	Want2Go(5);
	CarBrake();
	Chassis_ClearMileage();
	motor_pid_clear();
	Robot_Work(LARM, UP);
	Robot_Work(RARM, UP);
	send_play_specified_command(9);
	Chassis_Turn360_Blocking();
	Robot_Work(LARM, DOWN);
	Robot_Work(RARM, DOWN);
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
			send_play_specified_command(7);
			printf("gyro reset\n");
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
	return (fabsf(Chassis_GetMileage()) >= distance ||
		Scaner.ledNum >= 4 || Scaner.lineNum >= 2 ||
		Scaner.lineNum == 0 || Scaner.ledNum == 0);
}

void RampCtrl_Blocking(RampDir_t dir, float init_speed, float angle,
                       float thresh1, float speed1,
                       float thresh2, float speed2,
                       float done_thresh, float GrayCorrectAngle,
                       float max_correction)
{
	enum { RAMP_INIT, RAMP_PHASE1, RAMP_PHASE2 }
	state = RAMP_INIT;

	if (GrayCorrectAngle!=0) Gray_Open();

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
		vTaskDelay(5);
	}
}

static void Stage_ScanAndRead(void)
{
	// 平台动作
	switch (nodesr.nowNode.nodenum)
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
	if (nodesr.nowNode.nodenum == P1)
		update_route_for_stage34();
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
	
	isStage = 1;
	float oringinal_angle = 0;
	printf("Executing stage procedure\n");
	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);//25
	Chassis_ClearMileage();

	while (state != STAGE_DONE)
	{
		switch (state)
		{
		case STAGE_ASCEND:
			if (Stage_DetectedRamp(10.0f))
			{
				// init=UpStage_Speed, pitch>=basic_p+5→speed12, pitch>=basic_p+20→speed12, pitch<=basic_p+5→done
				oringinal_angle = getAngleZ();
				RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_high, oringinal_angle,
					Begin_up, UpDownStage_Speed_low, up_pitch, UpDownStage_Speed_low, After_up, 0.03, 10.0f);

				Chassis_MotorControl(is_Gyro, GoStage_Speed, GoStage_Speed, oringinal_angle);
				state = STAGE_TOP;
			}
			break;

		case STAGE_TOP:
			if (sub_stage == 0)
			{

				Chassis_DriveDistance_Blocking(is_Gyro,27,GoStage_Speed,oringinal_angle,0);
				CarBrake();
				sub_stage = 1;
				
			}
			else if(sub_stage == 1)
			{		
				mpuZreset(get_latest_yaw(), nodesr.nowNode.angle);
				// 后退一段距离
				 printf("Chassis_DriveDistance_Blocking\n");
				
				vTaskDelay(100);
				Chassis_DriveDistance_Blocking(is_Gyro,10,-GoStage_Speed,getAngleZ(),0);
				CarBrake();
				sub_stage=0;
				state = STAGE_SCAN;
			}
			break;

		case STAGE_SCAN:
			// P1 路线更新：根据 flag_line_clue 标志位决定去 P3/P4 或跳过
			if (nodesr.nowNode.nodenum == P1)
				update_route_for_stage34();

			// 转身180
			Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+180, getAngleZ());
			printf("turn finish\n");
			state = STAGE_TREASURE;
			break;

		case STAGE_TREASURE:
			printf("Descending platform\n");
			oringinal_angle = getAngleZ();
			// init=UpDownStage_Speed_low(12), pitch<=basic_p-5→speed12, pitch<=basic_p-20→speed20, pitch>=basic_p-5→done
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, getAngleZ(),
				Begin_down, UpDownStage_Speed_low, down_pitch, UpDownStage_Speed_high, After_down-8, 0.05, 10.0f);

			//Chassis_Turn_By_Gyro_Blocking(oringinal_angle, getAngleZ());
		
			Chassis_MotorControl(is_Line, SPEED1, SPEED1, 0);
			printf("stage done\n");
			state = STAGE_DONE;
			break;
		default:
			break;
		}
		vTaskDelay(2);
	}

	nodesr.nowNode.function = 0;
	nodesr.flag |= 0x04;
}

/*平台 - P2*/
void Stage_P2()
{
	/*参数调整*/
	isStage = 1;
	static uint8_t Backtimes = 0; // 回来次数 - 为1时代表第二轮回家
	struct PID_param origin_param1 = gyroG_pid_param;
	
	struct PID_param origin_param2 = line_pid_param;
	/*设置起始模式速度*/
	Chassis_ClearMileage();
	/////////
//	line_pid_param.kp = 30.0;//50.0
//	line_pid_param.ki = 0;
//	line_pid_param.kd = 250;
	line_pid_param.kp = 35;//10
	line_pid_param.ki = 0.004;
	line_pid_param.kd = 300;//85
	ScanerMode_Switch(Gray);
	
	/////////
	
	
	Chassis_MotorControl(is_Line, UpStage_Speed-7, UpStage_Speed-7, 0);

	/*寻找合适的上坡角度*/
	float tempAngle = -1;
	scaner_set.EdgeIgnore = 2;//4
	while (Scaner.ledNum < 8)
	{
				Cross_getline(&Cross_Scaner);
		if( ((Scaner.detail_gray & 0x18)||((Cross_Scaner.detail & 0x180) == 0x180)) && Cross_Scaner.ledNum < 5)
			tempAngle = getAngleZ();
		vTaskDelay(2);
	}
	if(tempAngle == -1)
		tempAngle = getAngleZ();

	/*设置自平衡速度*/
	Chassis_MotorControl(is_Gyro, GoStage_Speed, GoStage_Speed, tempAngle);
	Robot_Work(BODY, UP);														// 人站起来

	/*到平台上*/
	Chassis_ClearMileage();
	Want2Go(75);//60

	/*刹车*/
	CarBrake();
	vTaskDelay(200);

	/*若为第二轮回家*/
	if(Backtimes == 1)
		while(1);
	
	/*转身*/
	Turn_Angle_Relative(179);
	while (fabsf(need2turn(angle.AngleT, getAngleZ())) > 2) // 7
		vTaskDelay(2);

	Backtimes++;
	gyroG_pid_param = origin_param1;
	line_pid_param = origin_param2;
	Chassis_ClearMileage();
	motor_all.Cspeed = 0;
	motor_pid_clear();
	nodesr.nowNode.function = 0; // 清除障碍标志
	nodesr.flag |= 0x04;		 // 到达路口
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
				Begin_up, UpDownStage_Speed_high, up_pitch-5, UpDownStage_Speed_low, up_pitch+20, 0, 10.0f);
			//加一点修正
			Chassis_ClearMileage();
	
			while (fabsf(Chassis_GetMileage()) < 15)
			{		
				Chassis_CorrectByInfrared(0.07f, 1.5f, 1.0f);
				vTaskDelay(5);
			}
			//上桥结束检测
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, getAngleZ(),
				0, UpDownStage_Speed_low, 0, UpDownStage_Speed_low, After_up, 0, 10.0f);

			Chassis_ClearMileage();
			state = BRIDGE_ON_BRIDGE_TOP;
			break;

		case BRIDGE_ON_BRIDGE_TOP:
		
			static uint8_t is_emergency = 0;
				Cross_getline(&Cross_Scaner);	// 桥上为陀螺仪模式，Scaner 不更新，主动拍快照
			//第1层：巡线板最外侧紧急处理
			if (Cross_Scaner.detail & 0xF800)
			{
				is_emergency ++;
				if(is_emergency == 10)
				{
				centered_samples = 0;
				send_play_specified_command(7);
				//angle.AngleG = getAngleZ() - BRIDGE_EMERGENCY_ANGLE;
				Chassis_SetTargetSpeed(UpDownStage_Speed_low);
				}
			}

			else if (Cross_Scaner.detail & 0x007F)
			{
				is_emergency ++;
				if(is_emergency == 10)
				{
				centered_samples = 0;
				send_play_specified_command(7);
				//angle.AngleG = getAngleZ() + BRIDGE_EMERGENCY_ANGLE;
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
					Chassis_CorrectByInfrared(0.03f, 1.0f, 1.0f);
					Chassis_SetTargetSpeed(SPEED1);
				}
			}
			// 距离退出（保险兜底）
			float mileage_br = fabsf(Chassis_GetMileage());
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
				Begin_down, UpDownStage_Speed_low, down_pitch+5, SPEED0, down_pitch-20,0, 10.0f);//下坡下一半

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
				0, SPEED0, 0, SPEED0, After_down,0, 10.0f);

			Chassis_MotorControl(is_Line, SPEED1, SPEED1, 0);
			nodesr.nowNode.function = 0;
			nodesr.flag |= 0X04;
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
				basic_p+5, UpDownStage_Speed_low, basic_p+15, UpDownStage_Speed_low, basic_p+5, 0.1, 10.0f);
	
				printf("Hill ascend complete, preparing to descend\n");
			state = HILL_DESCEND;
			break;

		case HILL_DESCEND:
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, origin_angle,
				basic_p, UpDownStage_Speed_low, basic_p-8, UpDownStage_Speed_low, basic_p-5, 0.10, 10.0f);

				printf("Hill descend complete\n");   
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
	nodesr.nowNode.function = 0; 	// 清除障碍标志
	nodesr.flag |= 0x04;		 	// 到达路口
}

/*刀山*/
void Sword_Mountain(void)
{
	float num;
	uint8_t getZ = 0;
	struct PID_param origin_param = line_pid_param;
	struct PID_param origin_param1 = gyroG_pid_param;
	uint32_t add_time = 0 ;
	float get_angle = 0;
	float sum_angle = 0;
	motor_all.Cspeed = Gyro_Speed - 10;
	line_pid_param.kp = 35;//10
	line_pid_param.ki = 0.004;
	line_pid_param.kd = 300;//85
	
	Chassis_ClearMileage();
//	Want2Go(10);
	
	mpuZreset(get_latest_yaw(), nodesr.nowNode.angle);
	
	scaner_set.EdgeIgnore = 5;//试试看能不能忽略红线

				Cross_getline(&Cross_Scaner);
	buzzer_on();
	while (Cross_Scaner.ledNum <= 3)
	{
				Cross_getline(&Cross_Scaner);
		if((Cross_Scaner.detail & 0X180) == 0X180)
		{
			//mpuZreset(imu.yaw, nodesr.nowNode.angle);		
		/*****************改*****************/
			//再进行一次确认
			vTaskDelay(2);
				Cross_getline(&Cross_Scaner);
			if((Cross_Scaner.detail & 0X180) == 0X180)
			{
				angle.AngleG = getAngleZ();
				buzzer_off();
				getZ = 1;

			}
		/*****************改*****************/			
//			angle.AngleG = getAngleZ();
//			getZ = 1;
		}
		vTaskDelay(2);
	}
	
//	for(add_time;add_time<5;add_time++)
//	{
//		get_angle = getAngleZ();
//		sum_angle += get_angle;
//	}
//	angle.AngleG = sum_angle/5;
	
	if(getZ == 0)
		angle.AngleG = nodesr.nowNode.angle;
	
//	buzzer_on();
	motor_all.Gspeed = Gyro_Speed - 3;
	pid_mode_switch(is_Gyro);
	num = motor_all.Distance;
	while (imu.pitch < After_up) 		// 出循环上刀山
	{
		vTaskDelay(2);
		if (fabsf(motor_all.Distance - num) > 30)
			break;
	}
	scaner_set.EdgeIgnore = 0;//修改回原来忽略的灯
	
	Chassis_ClearMileage();
	num = motor_all.Distance;
	while (imu.pitch > After_down+2) 	// 出循环下刀山
	{
		vTaskDelay(2);
		if (fabsf(motor_all.Distance - num) > 80)
			break;
	}

//	buzzer_off();
	line_pid_param = origin_param;
	gyroG_pid_param = origin_param1;
	nodesr.nowNode.function = 0; 		// 清除障碍标志
	nodesr.flag |= 0x04;		 		// 到达路口
}

/*上珠峰 - 已接下珠峰*/
void Barrier_HighMountain(float speed)
{
	float num = 0;
	uint8_t getZ = 0;
	struct PID_param origin_param1 = gyroG_pid_param;
	float origin_turnM = motor_all.GyroT_speedMax;
	struct PID_param origin_line = line_pid_param;
	//float origin_line = motor_all.

	motor_all.GyroT_speedMax = 25;
	motor_all.Cspeed = Mount_Speed;
	gyroG_pid_param.kp = 4.5;
	gyroG_pid_param.ki = 0;
	gyroG_pid_param.kd = 0;
	
	line_pid_param.kp = 17;//18
	line_pid_param.ki = 0;
	line_pid_param.kd = 400;//25
	scaner_set.EdgeIgnore = 3;
	Chassis_MotorControl(is_Line, Mount_Speed-6, Mount_Speed-6, 0);//Mount_Speed-3, Mount_Speed-3
	/*上坡前*/
	while ((Scaner.ledNum < 3 && Scaner.ledNum > 0) || Scaner.lineNum == 1)
	{
		if ((Scaner.detail & 0X180) == 0X180)
			mpuZreset(get_latest_yaw(), nodesr.nowNode.angle);		//走直了就矫正
	}
	
	/*上坡*/
	//Chassis_MotorControl(is_Gyro, Mount_Speed, Mount_Speed, nodesr.nowNode.angle);
	//Chassis_MotorControl(is_Line, Mount_Speed, Mount_Speed, 0);
	Chassis_ClearMileage();
	while(imu.pitch < Begin_up)
		vTaskDelay(2);
	buzzer_on();
	//Chassis_MotorControl(is_Line, Mount_Speed, Mount_Speed, 0);
	Chassis_ClearMileage();
	num = motor_all.Distance;
	uint32_t add_time = 0 ;
	float get_angle = 0;
	float sum_angle = 0;
	while(Cross_Scaner.ledNum != 0)	/*80*///fabsf(motor_all.Distance - num) < 90
	{
		vTaskDelay(2);
				Cross_getline(&Cross_Scaner);
		if((Scaner.detail & 0X180) == 0X180)
		{
			
			add_time++;
			get_angle = getAngleZ();
			sum_angle += get_angle;
			//angle.AngleG = getAngleZ();
			getZ = 1;
		}	
//		if(Cross_Scaner.ledNum >= 14)//6
//			break;
	}
	if(add_time > 0) angle.AngleG = sum_angle/add_time;
	add_time = 0 ;
	get_angle = 0;
	sum_angle = 0;
//	while(Scaner.ledNum < 10)	/*80*/
//	{
//		vTaskDelay(2);
//		Cross_getline(&Cross_Scaner);
//		buzzer_on();
//		if((Scaner.detail & 0X180) == 0X180)
//		{
//			angle.AngleG = getAngleZ();
//			getZ = 1;
//		}
//		if(Cross_Scaner.ledNum >= 6)
//			break;
//	}
	
	
	buzzer_off();
	if(getZ == 0)
		angle.AngleG = nodesr.nowNode.angle;
	getZ = 0;
	Chassis_MotorControl(is_Gyro, Mount_Speed-5, Mount_Speed-5, angle.AngleG);//Mount_Speed-9, Mount_Speed-9
	while (imu.pitch > After_up)
		vTaskDelay(2);
	/*上完坡到平台*/
	do
	{
		vTaskDelay(2);
		getline_error();
	} while (Scaner.ledNum <= 4);
	do
	{
		vTaskDelay(2);
		getline_error();
	} while (Scaner.ledNum >= 4);
	// while (imu.pitch < Begin_up)
	// 	vTaskDelay(2);

	/*上坡*/
	buzzer_on();
	Robot_Work(BODY, UP);
	scaner_set.EdgeIgnore = 3;
	Chassis_MotorControl(is_Line, Mount_Speed-5, Mount_Speed-5, 0);//Mount_Speed-9, Mount_Speed-9
	Chassis_ClearMileage();
	num = motor_all.Distance;
	Want2Go(20);
	while (Scaner.ledNum < 10)
	{
		vTaskDelay(2);
		if((Scaner.detail & 0X180) == 0X180)
		{
			add_time++;
			get_angle = getAngleZ();
			sum_angle += get_angle;
			//angle.AngleG = getAngleZ();
			getZ = 1;
		}
	}
	if(add_time > 0) angle.AngleG = sum_angle/add_time;
	add_time = 0 ;
	get_angle = 0;
	sum_angle = 0;
	
	if(getZ == 0)
		angle.AngleG = nodesr.nowNode.angle;
	scaner_set.EdgeIgnore = 0;
	buzzer_off();

	/*上完坡,撞挡板*/
	Chassis_MotorControl(is_Gyro, 10, 10, angle.AngleG);
	send_play_specified_command(14);
	while (Infrared_ahead == 0)
		vTaskDelay(5);

	Chassis_ClearMileage();
	Want2Go(17);
	
	Chassis_MotorControl(is_Free,-1500,-1500,0);
	Want2Go(0.5);
	
	Chassis_ClearMileage();
	CarBrake();
	mpuZreset(get_latest_yaw(), nodesr.nowNode.angle); // 陀螺仪校正
	// 宝物线索：由标志位计算，不依赖摄像头
	if(treasure == 0)
		treasure = flag_clue_A + flag_clue_B;
	
	//如果宝物线索B在平台8,已经拿完所有线索重新规划路线
	//只有当P8是最后一个线索平台时才覆盖路线
	if(map.routetime == 0 && flag_clue_stage_B == 8)
		update_rout_by_treasure_8();
	
	
	/*后退*/
	Chassis_ClearMileage();
	Chassis_MotorControl(is_Free,-2000,-2000,0);
	Want2Go(5.5);
	Chassis_ClearMileage();
	CarBrake();
	Arrived_Stage();
	vTaskDelay(800);
	//获取宝物线索B
//	if(treasure == 0 && map.routetime==0)
//		WaitFor_OCR();
//	
//	//如果宝物线索B在平台8,已经拿完所有线索重新规划路线
//	if(map.routetime == 0&&map.routetime==0)
//		update_rout_by_treasure_8();
	
//	if(get_a != 1||get_b != 1)
//	{
//		u8 route_loser[50] = 
//		for(uint8_t i = 0;i<50;i++)
//		{
//			route[map.point+i] = route_loser[i];
//			if(route_loser[i]==0xff)
//				break;
//		}
//	}

  


	/*转180°*/
	Turn_Angle_Relative(170);//179调试角度
	while (fabs(angle.AngleT - getAngleZ()) > 2)
		vTaskDelay(2);

//	Turn_Angle_Relative(5);
//	while (fabs(angle.AngleT - getAngleZ()) > 2)
//		vTaskDelay(2);
	/*宝藏*/
//	if (treasure[2] == 8)
//	{
//		Robot_Work(LARM, UP);
//		Robot_Work(RARM, UP);
//		send_play_specified_command(9);
//		Turn_Angle360();
//		Robot_Work(LARM, DOWN);
//		Robot_Work(RARM, DOWN);
//	}

	Barrier_Down_HighMountain(666.666);
	gyroG_pid_param = origin_param1;
	motor_all.GyroT_speedMax = origin_turnM;
	line_pid_param = origin_line;
	nodesr.nowNode.function = 0; // 清除障碍标志
	nodesr.flag |= 0x04;		 // 到达路口
}

/*下珠峰*/
void Barrier_Down_HighMountain(float speed)
{
	/*掉头之后陀螺仪自平衡*/
	Chassis_MotorControl(is_Gyro, Old_M_Speed, Old_M_Speed, getAngleZ());
	Robot_Work(BODY, DOWN);

	/*扫红线判断是否下坡*/
	do
	{
		vTaskDelay(2);
		getline_error();
	} while (Scaner.ledNum <= 4);
	do
	{
		vTaskDelay(2);
		getline_error();
	} while (Scaner.ledNum >= 4);

	/*前进一小段*/
	Chassis_ClearMileage();
	struct PID_param origin_param = line_pid_param;
	line_pid_param.kp = 35;
	line_pid_param.ki = 0;
	line_pid_param.kd = 1.5;
	Chassis_MotorControl(is_Line, Old_M_Speed, Old_M_Speed, 0);
	Want2Go(25);//35
	
	
	/*切换循迹，开始下坡*/
	line_pid_param.kp = 27;//24
	line_pid_param.ki = 0;
	line_pid_param.kd = 400;//400
	Chassis_MotorControl(is_Line, Rubbish_Speed-4, Rubbish_Speed-4, 0);// Rubbish_Speed-7, Rubbish_Speed-7
	uint8_t getZ1 = 0;
	buzzer_on();
	LiuShuiRate = LiuShuiRate_UM;
	uint32_t add_time = 0 ;
	float get_angle = 0;
	float sum_angle = 0;
	while(Scaner.ledNum < 10)
	{
		getline_error();
		if(((Scaner.detail & 0X180) == 0X180)||((Scaner.detail & 0X100) == 0X100)||((Scaner.detail & 0X80) == 0X80))//Scaner.detail == 0x180 && !getZ1
		{
			getZ1 = 1;
			
//			add_time++;		
//			get_angle = getAngleZ();
//			sum_angle += get_angle;
		
			angle.AngleG = getAngleZ();
		}
		vTaskDelay(2);
	}
	
//	sum_angle = sum_angle/add_time;
//	angle.AngleG = sum_angle;
	add_time = 0 ;
	get_angle = 0;
	sum_angle = 0;
	
	buzzer_off();
	if(!getZ1)
		angle.AngleG = 180;
	LiuShuiRate = LiuShuiRate_Default;
	Chassis_MotorControl(is_Gyro, Rubbish_Speed, Rubbish_Speed, angle.AngleG);
	while (imu.pitch < After_down)
		vTaskDelay(2);
	Chassis_ClearMileage();

	/*下第二个坡*/
	do
	{
		vTaskDelay(2);
		getline_error();
	} while (Scaner.ledNum <= 4);
	//motor_all.Gspeed = Rubbish_Speed;
	do
	{
		vTaskDelay(2);
		getline_error();
	} while (Scaner.ledNum >= 4);
	motor_all.Gspeed = Old_M_Speed;
	/*前进一小段*/
	Chassis_ClearMileage();
	//Want2Go(5);
	line_pid_param.kp = 35;
	line_pid_param.ki = 0;
	line_pid_param.kd = 1.5;
	Chassis_MotorControl(is_Line, Old_M_Speed, Old_M_Speed, 0);
	Want2Go(15);//35

	/*切换循迹，开始下坡*/
	line_pid_param.kp = 24;//12
	line_pid_param.ki = 0;
	line_pid_param.kd = 400;
	Chassis_MotorControl(is_Line, Rubbish_Speed-5, Rubbish_Speed-5, 0);
	uint8_t getZ2 = 0;
	LiuShuiRate = LiuShuiRate_UM;
	
	buzzer_on();
	Chassis_ClearMileage();
	Want2Go(30);
	Chassis_MotorControl(is_Line, Rubbish_Speed+4, Rubbish_Speed+4, 0);
	
	float num = motor_all.Distance;
	while (Scaner.ledNum < 4 && Scaner.ledNum > 0)
	{
		getline_error();
		if ((Scaner.detail & 0X180) == 0X180)//Scaner.detail == 0x180 && !getZ2
		{
			getZ2 = 1;
			add_time++;
			get_angle = getAngleZ();
			sum_angle += get_angle;
			//angle.AngleG = getAngleZ();
		}
//		if(fabsf(motor_all.Distance - num) > 60)
//			break;
		if(imu.pitch > After_down)
			break;
		vTaskDelay(2);
	}
	if(add_time > 0) sum_angle = sum_angle/add_time;
	angle.AngleG = sum_angle;
	add_time = 0 ;
	get_angle = 0;
	sum_angle = 0;
	
	buzzer_off();
	if (!getZ2)
		angle.AngleG = 180;
	LiuShuiRate = LiuShuiRate_Default;
	//Chassis_MotorControl(is_Gyro, Rubbish_Speed+5+5, Rubbish_Speed+5+5, angle.AngleG);
//	while (imu.pitch < After_down)
//		vTaskDelay(2);
	Chassis_MotorControl(is_Line, Rubbish_Speed+5, Rubbish_Speed+5, 0);
	scaner_set.EdgeIgnore = 0;
	line_pid_param = origin_param;
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
	
	mpuZreset(get_latest_yaw(), nodesr.nowNode.angle);  //陀螺仪校正
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
	motor_all.Cspeed = nodesr.nowNode.speed;
	pid_mode_switch(is_Line);
		
	nodesr.nowNode.function = NONE;
	motor_all.Cincrement = origin_c;
	nodesr.flag |= 0x04; // 到达路口
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

	nodesr.nowNode.function = 0;
	nodesr.flag |= 0x04; // 到达路口
}

/*退短直立景点 - 红外检测*/
void back(void)
{
	/*后退一段距离*/
	Chassis_MotorControl(is_Free, -2000, -2000, 0);
	if(nodesr.lastNode.nodenum == S5)
		Want2Go(20);
	else if(nodesr.lastNode.nodenum == S4)
		Want2Go(10);
	Chassis_ClearMileage();
	CarBrake();
	vTaskDelay(100);

	Turn_Angle_Relative(need2turn(getAngleZ(), nodesr.nextNode.angle));
	while (fabs(need2turn(getAngleZ(), nodesr.nextNode.angle)) > 2)
	{
		vTaskDelay(2);
		getline_error();
		if (Scaner.lineNum == 1 && ((Scaner.detail & 0x180) != 0) && (fabs(need2turn(angle.AngleT, getAngleZ())) < fabs(need2turn(angle.AngleT, nodesr.nowNode.angle)) * 0.15f))
			break;
	}
	Chassis_MotorControl(is_Line, 28, 28, 0);

	nodesr.nowNode.function = 0;
	nodesr.flag |= 0x04; // 到达路口
}

/*波浪板*/
void Barrier_WavedPlate(float lenght)
{
	struct PID_param origin_param1 = gyroG_pid_param;
	struct PID_param origin_param = line_pid_param;
	
	/*进板前*/
	Chassis_MotorControl(is_Line, Low_Speed, Low_Speed, 0);
	while (Scaner.ledNum <= 4 || Scaner.lineNum == 1)
	{
				Cross_getline(&Cross_Scaner);
		if((Cross_Scaner.detail & 0x180) == 0x180)
			mpuZreset(get_latest_yaw(),nodesr.nowNode.angle);
		vTaskDelay(2);
	}
	line_pid_param.kp = 35; // 23.5
	line_pid_param.ki = 0;	// 0.004
	line_pid_param.kd = 0;
	/*进板*/
	float num = 0;
	
	/*旧循迹参数*/
	Chassis_MotorControl(is_Line, BL_Speed+2, BL_Speed+2, 0);
	num = motor_all.Distance;
	scaner_set.EdgeIgnore = 3;
	buzzer_on();
	while (fabsf(motor_all.Distance - num) < lenght)
	{
		vTaskDelay(2);
		CGChange(BL_Speed);
	}

	/*出板*/
	WavePlateLeft_Flag = 0;
	WavePlateRight_Flag = 0;
	scaner_set.EdgeIgnore = 0;
	line_pid_param = origin_param;
	nodesr.nowNode.function = 0;
	buzzer_off();
	gyroG_pid_param = origin_param1;
	nodesr.flag |= 0x04; // 到达路口
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
	float origin_turnM = motor_all.GyroT_speedMax;
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
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, origin_angle,
				Begin_up, UpDownStage_Speed_low, up_pitch, UpDownStage_Speed_low, After_up, 0.05f, 10.0f);
			state = SP_IMPACT;
			break;

		case SP_IMPACT:
			if (sub_stage == 0)
			{
				Chassis_DriveDistance_Blocking(is_Gyro, 27, GoStage_Speed, origin_angle, 0);
				CarBrake();
				sub_stage = 1;
			}
			else if (sub_stage == 1)
			{
				mpuZreset(get_latest_yaw(), nodesr.nowNode.angle);
				vTaskDelay(100);
				Chassis_DriveDistance_Blocking(is_Gyro, 10, -GoStage_Speed, getAngleZ(), 0);
				CarBrake();
				// if (treasure == 0)
				// 	treasure = flag_clue_A + flag_clue_B;
				// if (map.routetime == 0 && flag_clue_stage_B == 7)
				// 	update_rout_by_treasure_7();
				send_play_specified_command(12);
				Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 180, getAngleZ());
				sub_stage = 0;
				state = SP_DESCEND;
			}
			break;

		case SP_DESCEND:
			RampCtrl_Blocking(RAMP_DESCEND, UpDownStage_Speed_low, getAngleZ(),
				Begin_down, UpDownStage_Speed_low, down_pitch, UpDownStage_Speed_high, After_down, 0.05f, 10.0f);
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
	motor_all.GyroT_speedMax = origin_turnM;
	nodesr.nowNode.function = 0;
	nodesr.flag |= 0x04;
}


static void copy_route(const u8* src)
{
	for(uint8_t i = 0; i < 50; i++)
	{
		route[map.point + i] = src[i];
		if(src[i] == 0xFF)
			break;
	}
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

void update_rout_by_treasure_7(void)
{
	//map.point = 1;
	if(treasure != 0&&color_flag[0] == Green)//D2绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N5,N4,N3,P3,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 4:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 5:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 2:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; copy_route(r); break; }
			default:

                break;	
		}
	}
	if(treasure != 0&&color_flag[1] == Green)//D3绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N5,N4,N3,P3,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 4:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 5:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N8,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 2:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; copy_route(r); break; }
			default:

                break;	
	     }
    }
	if(treasure != 0&&color_flag[2] == Green)//D4绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N3,P3,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 4:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 5:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N8,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 2:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N8,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; copy_route(r); break; }
			default:

                break;	
	    }
	}
	if(treasure != 0&&((color_flag[0] == Yellow)||(color_flag[1] == Yellow)))//D2D3黄灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; copy_route(r); break; }
			case 4:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; copy_route(r); break; }
			case 5:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N11,N10,N3,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,0XFF}; copy_route(r); break; }
			case 2:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; copy_route(r); break; }
			default:

                break;	
	    }
	}
	if(treasure != 0&&color_flag[2] == Yellow)//D4黄灯D5必绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,C5,N15,N10,N3,P3,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 4:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,C5,N15,N10,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 5:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N11,N10,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 2:
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,C5,N15,N10,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; copy_route(r); break; }
			default:

                break;	
	    }
	}
}
void update_rout_by_treasure_8(void)
{
	if(treasure != 0&&color_flag[0] == Green)//D2绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N5,N4,N3,P3,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 4:
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 5:
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 2:
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; copy_route(r); break; }
			default:

                break;	
		}
	}
	if(treasure != 0&&color_flag[1] == Green)//D3绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N5,N4,N3,P3,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 4:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 5:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N10,N11,N12,N13,P5,N13,N12,N8,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 2:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; copy_route(r); break; }
			default:

                break;	
	     }
    }
	if(treasure != 0&&color_flag[2] == Green)//D4绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N3,P3,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 4:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 5:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N11,N12,N13,P5,N13,N12,N8,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 2:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N8,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; copy_route(r); break; }
			default:

                break;	
	    }
	}
	if(treasure != 0&&((color_flag[0] == Yellow)||(color_flag[1] == Yellow)))//D2D3黄灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; copy_route(r); break; }
			case 4:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; copy_route(r); break; }
			case 5:
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N11,N10,N3,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,0XFF}; copy_route(r); break; }
			case 2:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,0XFF}; copy_route(r); break; }
			default:

                break;	
	    }
	}
	if(treasure != 0&&color_flag[2] == Yellow)//D4黄灯D5必绿灯
	{
		switch (treasure)
		{
			case 3:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,P3,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 4:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 5:
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,N11,N10,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 2:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF}; copy_route(r); break; }
			default:

                break;	
	    }
	}
}
/*跷跷板*/
void QQB_1(void)
{
	//是否开自平衡
	uint8_t gyro_flag;
	uint16_t break_time = 0;
	float num;
	float select_distance = 0;
	struct PID_param origin_param1 = gyroG_pid_param;
	struct PID_param origin_param2 = line_pid_param;
	int timeout = 0;
	gyroG_pid_param.kp = 3.5;
	gyroG_pid_param.ki = 0.004;
	gyroG_pid_param.kd = 0;
	motor_all.Cspeed = Low_Speed;
	pid_mode_switch(is_Line);
	if(nodesr.nowNode.nodenum == B9)
		scaner_set.CatchsensorNum = line_weight_default[8]; // 给予左边权值
	else
		scaner_set.CatchsensorNum = line_weight_default[8]; // 给予左边权值
	infrare_open = 1;

	/*板处理*/
	/*循迹走板前1/4弯弧*/
	if(nodesr.lastNode.nodenum == N7 && nodesr.nowNode.nodenum == B8)
		Want2Go(89);	/*80*/
	else 
		Want2Go(70);	/*80*/
	motor_all.Cspeed = 15; 
	while ((imu.pitch < basic_p + 6))
	{
				Cross_getline(&Cross_Scaner);
		if ((Cross_Scaner.detail & 0x3) == 0x3 ||//0000 0000 0000 0011
			(Cross_Scaner.detail & 0x6) == 0x6 ||//0000 0000 0000 0110
			(Cross_Scaner.detail & 0xC) == 0xC)//0000 0000 0000 1100
			break;
		vTaskDelay(2);
	}
	scaner_set.CatchsensorNum = 0;

	/*陀螺仪转正位置*/
	if (nodesr.nowNode.nodenum == B8)
		Chassis_MotorControl(is_Gyro, QQB_Speed, QQB_Speed, getAngleZ()+4);//+5 
	else
		Chassis_MotorControl(is_Gyro, QQB_Speed, QQB_Speed, getAngleZ()+4);//+6 
	
	while (fabs(need2turn(getAngleZ(), angle.AngleG)) > 4)
	{
		break_time++;
		if (break_time > 500)
			break;
		vTaskDelay(2);
	}
	break_time=0;
	/*板上红外+循迹矫正*/
	gyroG_pid_param.kp = 4;//8
	gyroG_pid_param.ki = 0.004;
	gyroG_pid_param.kd = 0;
	angle.AngleG = getAngleZ();
	motor_all.Gspeed = QQB_Speed;
	if (nodesr.nowNode.nodenum == B8)
		select_distance = 70;//68
	else
		select_distance = 74;//67
	Chassis_ClearMileage();
	num = motor_all.Distance;
	while (fabsf(motor_all.Distance - num) < select_distance/*78*/)
	{
		getline_error();
		if ((infrared.head_left == 1 && infrared.head_right == 0) || (Scaner.detail & 0xF800))
			angle.AngleG = getAngleZ() - 3;
		else if ((infrared.head_left == 0 && infrared.head_right == 1) || (Scaner.detail & 0x7F))
		{
			buzzer_on();
			angle.AngleG = getAngleZ() + 3;
		}
		vTaskDelay(2);
		
	}
//	效果不好
//	 while(imu.pitch < Begin_down+6)
//		{ 
//				Want2Go(10);	
//				CarBrake();
//				vTaskDelay(100);
//		}
//
	buzzer_off();
	scaner_set.EdgeIgnore = 4;
	Chassis_MotorControl(is_Line, 7, 7, 0);
	gyroG_pid_param.kp = 3.5;
	gyroG_pid_param.ki = 0.004;
	gyroG_pid_param.kd = 0;
	vTaskDelay(200);
	CarBrake();
	if (nodesr.nowNode.nodenum == B8)
		vTaskDelay(1000);
	else
		vTaskDelay(1400);
	if (nodesr.nowNode.nodenum == B8)
		Chassis_MotorControl(is_Gyro, QQB_Speed, QQB_Speed, getAngleZ()+9);//+13 
	else
		Chassis_MotorControl(is_Gyro, QQB_Speed, QQB_Speed, getAngleZ()+9);//+13 
	
	while (fabs(need2turn(getAngleZ(), angle.AngleG)) > 5)
	{
		break_time++;
		if (break_time > 500)
			break;
		vTaskDelay(2);
	}
	break_time=0;
	scaner_set.EdgeIgnore = 0;
	
	CarBrake();
	vTaskDelay(700);
				Cross_getline(&Cross_Scaner);	
	/*板中停车等待板砸下*/
	while(1)//一定要去检测gyro_flag
	{	
		buzzer_on();
		vTaskDelay(2);
		timeout ++;
				Cross_getline(&Cross_Scaner);
		if(Cross_Scaner.detail & 0x7FC)
		{
			gyro_flag=0;
			break;
		}
		if(timeout >= 200)
		{
			gyro_flag=1;
			break;
		}
	}
	
	buzzer_off();
	if(gyro_flag==1)
	{
		  	/*循迹矫正*/
			gyroG_pid_param.kp = 1.5;//8
			gyroG_pid_param.ki = 0.004;
			gyroG_pid_param.kd = 20;
			Chassis_MotorControl(is_Gyro, QQB_Speed-5, QQB_Speed-5, getAngleZ()+120);
		
			while (fabs(need2turn(getAngleZ(), angle.AngleG)) > 5 )
			{
				break_time++;
				Cross_getline(&Cross_Scaner);
				if (break_time > 500|| Cross_Scaner.detail &0x7FF )
				{
					line_pid_param.kp = 17;//18
					line_pid_param.ki = 0;
					line_pid_param.kd = 400;//25
					break;
				}
				vTaskDelay(2);
			}
			//原来参数
			gyroG_pid_param.kp = 8;//8
			gyroG_pid_param.ki = 0.004;
			gyroG_pid_param.kd = 0;
	}
	
	

	
	timeout = 0;
//	vTaskDelay(500);
	infrare_open = 0;
	scaner_set.EdgeIgnore = 0;
	
	/*开环转一段，确保能看到线*///暂时不要
	/*板中停车等待板砸下*/
/*	
	while(imu.pitch > Begin_down+6)
	{	
		CarBrake();
		vTaskDelay(2);
		timeout ++;
		if(timeout >= 750)
			break;
	}
	
	float angle1 = getAngleZ();
	Chassis_MotorControl(is_Free, -1500, 1500, 0);

	float needangle = 90;
	if (nodesr.nowNode.nodenum == B8)
	{
		vTaskDelay(500);
		needangle = 70;//50
	}
	else
	{
		vTaskDelay(500);
		needangle = 45;
	}
	//当检测到已完成大部分转向（>60%）且居中时，提前退出
	while ((fabsf(need2turn(getAngleZ(), angle1))) < needangle)
	{
		vTaskDelay(2);
				Cross_getline(&Cross_Scaner);
		if (Cross_Scaner.lineNum == 1 && Cross_Scaner.ledNum >= 2 && (Cross_Scaner.detail & 0x0ff0) && (fabs(need2turn(angle.AngleG, getAngleZ())) < fabs(need2turn(angle.AngleG, needangle) * 0.6f)))//当前航向偏差 小于预期总偏差的60% 时退出
			break;
	}
*/	
	/*两板子给不同速度*/
	scaner_set.CatchsensorNum = 0;
	motor_all.Cspeed = Low_Speed-12;
	
	pid_mode_switch(is_Line);
	gyroG_pid_param = origin_param1;
	line_pid_param = origin_param2;
	nodesr.nowNode.function = 0;
	nodesr.flag |= 0X04;
}

/*读颜色传感器，返回颜色值（0=超时/未设置, 1=绿, 2=黄, 3=红）*/
static uint8_t Door_ReadColor(uint8_t door_state)
{
	/*调试模式：直接从预设数组返回颜色，无需左右传感器*/
	static const uint8_t state_to_idx[] = {0, 1, 2, 3, 2}; // D2→0, D3→1, D4→2, D5→3, D4_AGAIN→2
	return debug_door_colors[state_to_idx[door_state]];

}

/*看红绿灯 — 状态机*/
void door()
{
	//转到定角度
	
	enum DoorState {
		DOOR_D2 = 0,   // 看D2（第一次）
		DOOR_D3,        // 看D3（D2红）
		DOOR_D4,        // 看D4（D2红 D3红）
		DOOR_D5_BACK,        // 看D5（D2黄 或 D2红D3黄）
		DOOR_D4_BACK   // 看D4回退（D2黄 D5红）
	};
	static enum DoorState state = DOOR_D2;
	static uint8_t wait_cnt = 0;

	/*头转向传感器方向*/
	//Robot_Work(HEAD, (state <= DOOR_D4) ? HEAD_RIGHT : HEAD_LEFT);
	//buzzer_on();
	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
	/*等到灯前*/
	while (Scaner.ledNum < 8)
		vTaskDelay(2);

	//buzzer_off();
	CarBrake();

	Chassis_Turn_By_StopGyro_Blocking(nodesr.nowNode.angle, getAngleZ());
	vTaskDelay(500);
	uint8_t door_color;  /*读颜色传感器，直接取回颜色值*/
	door_color = Door_ReadColor(state);

	switch (state)
	{
	/* ============ 看D2 ============ */
	case DOOR_D2:
		color_flag[0] = door_color;
		map.point = 0;
		route[0] = 0xFF;//删除N5,给nodesr.flag |= 0x20;空读，实际不会停车
		if (color_flag[0] == Red)
		{
			send_play_specified_command(11);
			//后退
			Chassis_DriveDistance_Blocking(is_Gyro,55,-SPEED2,getAngleZ(),0);

			nodesr.lastNode = nodesr.nowNode;
			nodesr.nowNode = Node[getNextConnectNode(N5, N8)];

			Chassis_Brake();
			Chassis_Turn_By_StopGyro_Blocking(nodesr.nowNode.angle, getAngleZ());

			nodesr.flag |= 0x20;
			state = DOOR_D3;
		}
		else if (color_flag[0] == Green)
		{
			send_play_specified_command(8);
			Node[getNextConnectNode(N5, N12)].function = NONE;//D2绿灯(允许第二轮直接通过)
			Node[getNextConnectNode(N5, N12)].speed = SPEED3;
			Node[getNextConnectNode(N5, N12)].step = 140;

			nodesr.nowNode = Node[getNextConnectNode(N5, N12)];
			nodesr.nowNode.step = 60;
			nodesr.nowNode.speed = SPEED2;
			//nodesr.nowNode.function = NONE;//D2绿灯(下半段直接走别卡这了)
			update_route_by_QR();


			nodesr.flag |= 0x80;
			state = DOOR_D2;  // 路线确定
		}
		else // Yellow
		{
			send_play_specified_command(10);
			Node[getNextConnectNode(N5, N12)].function = NONE;//D2黄灯(允许第二轮直接通过)
			Node[getNextConnectNode(N5, N12)].speed = SPEED3;
			Node[getNextConnectNode(N5, N12)].step = 140;

			nodesr.nowNode = Node[getNextConnectNode(N5, N12)];//第二轮D2也能直接过
			nodesr.nowNode.flag = DLEFT | DRIGHT | CRIGHT | LEFT_LINE;
			nodesr.nowNode.step = 60;
			nodesr.nowNode.speed = SPEED2;
			//nodesr.nowNode.function = NONE;//D2黄灯(下半段直接走别卡这了)
			//update_route_by_QR();


			nodesr.flag |= 0x80;
			state = DOOR_D5_BACK;  // 还要看D5
		}
		break;

	/* ============ 看D3（D2红） ============ */
	case DOOR_D3:
		color_flag[1] = door_color;
		map.point = 0;
		route[0] = 0xFF;
		if (color_flag[1] == Red)
		{
			send_play_specified_command(11);
			Chassis_DriveDistance_Blocking(is_Gyro,55,-SPEED2,getAngleZ(),0);

			nodesr.lastNode = nodesr.nowNode;
			nodesr.nowNode = Node[getNextConnectNode(N5, N4)];

			Chassis_Brake();
			Chassis_Turn_By_StopGyro_Blocking(nodesr.nowNode.angle, getAngleZ());


			for (uint8_t i = 0; i < 10; i++)
			{
				route[i] = door1route[i];//删除N4
				if (door1route[i] == 0xff) break;//因为没计数量
			}
			nodesr.flag |= 0x20;
			state = DOOR_D4;
		}
		else // Green 或 Yellow
		{
			
			Node[getNextConnectNode(N5, N8)].function = NONE;//D3绿灯或黄灯都能直接过
			Node[getNextConnectNode(N5, N8)].speed = SPEED3;
			Node[getNextConnectNode(N5, N8)].step = 120;

			nodesr.nowNode = Node[getNextConnectNode(N5, N8)];
			nodesr.nowNode.step = 60;
			nodesr.nowNode.speed = SPEED2;
			//nodesr.nowNode.function = NONE;//D3绿灯(下半段直接走别卡这了)
			

			//update_route_by_QR();

			if (color_flag[1] == Green)
			{
				
				Node[getNextConnectNode(N8, N5)].function = NONE;//D3绿灯(允许返程直接通过)
				Node[getNextConnectNode(N8, N5)].speed = SPEED2;
				Node[getNextConnectNode(N8, N5)].step = 120;
				
				send_play_specified_command(8);
				state = DOOR_D2;
			}
			else// Yellow
			{
				send_play_specified_command(10);
				state = DOOR_D5_BACK;
			}
			nodesr.flag |= 0x80;
		}
		break;

	/* ============ 看D4（D2红 D3红）此时D4至少是黄灯，一定能通过 ============ */
	case DOOR_D4:
		color_flag[2] = door_color;
		map.point = 0;
		route[0] = 0xFF;
		if (color_flag[2] == Green)
		{
			send_play_specified_command(8);
			Node[getNextConnectNode(N8, N3)].function = NONE;//D4绿灯(允许返程直接通过)
			Node[getNextConnectNode(N8, N3)].speed = SPEED3;
			Node[getNextConnectNode(N8, N3)].step = 140;
		}
		else // Yellow（D5必定绿）
		{
			send_play_specified_command(10);
			//默认规定Node[getNextConnectNode(N3, N10)].function = NONE;
			Node[getNextConnectNode(N10, N3)].function = NONE;//D5绿灯(允许返程直接通过)
			Node[getNextConnectNode(N10, N3)].speed = SPEED3;
			Node[getNextConnectNode(N10, N3)].step = 140;
		}
		
		

		Node[getNextConnectNode(N3, N8)].function = NONE;//D4(允许第二轮直接通过)
		Node[getNextConnectNode(N3, N8)].speed = SPEED3;
		Node[getNextConnectNode(N3, N8)].step = 120;
		
		nodesr.nowNode = Node[getNextConnectNode(N3, N8)];
		nodesr.nowNode.step = 60;
		nodesr.nowNode.speed = SPEED2;
		//nodesr.nowNode.function = NONE;//D4(下半段直接走别卡这了)
		
		update_route_by_QR();

		nodesr.flag |= 0x80;

		state = DOOR_D2;  // 门检测完成
		break;

	/* ============ 返程看D5（D2黄 或 D2红D3黄|只有返程的时候才看） ============ */
	case DOOR_D5_BACK:
		color_flag[3] = door_color;
		map.point = 0;
		route[0] = 0xFF;
		if (color_flag[3] == Green)
		{
			send_play_specified_command(8);		
			
			Node[getNextConnectNode(N10, N3)].function = NONE;//D5绿灯(允许第二轮返程直接通过)
			Node[getNextConnectNode(N10, N3)].speed = SPEED3;
			Node[getNextConnectNode(N10, N3)].step = 140;
			
			nodesr.nowNode = Node[getNextConnectNode(N10, N3)];
			nodesr.nowNode.step = 65;
			nodesr.nowNode.speed = SPEED2;
			//nodesr.nowNode.function = NONE;//D5绿灯(下半段直接走别卡这了)
		
			nodesr.flag |= 0x80;
			update_route_by_door_1();
			state = DOOR_D2;
		}
		else // Red
		{
			send_play_specified_command(11);

			if (color_flag[0] == Yellow)
			{
				// D2黄 D5红 → 回去看D4
				map.point -= 1;
				route[map.point] = N3;

				Chassis_DriveDistance_Blocking(is_Gyro,55,-SPEED2,getAngleZ(),0);

				nodesr.lastNode = nodesr.nowNode;
				nodesr.nowNode = Node[getNextConnectNode(N10, N8)];

				Chassis_Brake();
				Chassis_Turn_By_StopGyro_Blocking(nodesr.nowNode.angle, getAngleZ());

				nodesr.flag |= 0x20;
				state = DOOR_D4_BACK;
			}
			else if (color_flag[0] == Red && color_flag[1] == Yellow)
			{
				// D2红 D3黄 D5红 → D4,D1必定全绿
				Chassis_DriveDistance_Blocking(is_Gyro,55,-SPEED2,getAngleZ(),0);

				nodesr.lastNode = nodesr.nowNode;
				nodesr.nowNode = Node[getNextConnectNode(N10, N8)];

				Chassis_Brake();
				Chassis_Turn_By_StopGyro_Blocking(nodesr.nowNode.angle, getAngleZ());

				Node[getNextConnectNode(N3, N8)].function = NONE;//D4绿灯(允许第二轮直接通过)
				Node[getNextConnectNode(N3, N8)].speed = SPEED3;
				Node[getNextConnectNode(N3, N8)].step = 120;

				Node[getNextConnectNode(N8, N3)].function = NONE;//D4绿灯(允许返程直接通过)
				Node[getNextConnectNode(N8, N3)].speed = SPEED3;
				Node[getNextConnectNode(N8, N3)].step = 120;

				update_route_by_door_2();//删掉N8
				nodesr.flag |= 0x20;
				state = DOOR_D2;
			}
		}
		break;

	/* ============ 返程看D4（D2黄 D5红） ============ */
	case DOOR_D4_BACK:
		color_flag[2] = door_color;
		map.point = 0;
		route[0] = 0xFF;
		if (color_flag[2] == Green)
		{
			send_play_specified_command(8);

			Node[getNextConnectNode(N3, N8)].function = NONE;//D4绿灯（允许第二轮直接通过）
			Node[getNextConnectNode(N3, N8)].speed = SPEED3;
			Node[getNextConnectNode(N3, N8)].step = 120;

			Node[getNextConnectNode(N8, N3)].function = NONE;//D4绿灯(允许返程直接通过)
			Node[getNextConnectNode(N8, N3)].speed = SPEED3;
			Node[getNextConnectNode(N8, N3)].step = 120;

			nodesr.nowNode = Node[getNextConnectNode(N8, N3)];
			nodesr.nowNode.step = 10;
			nodesr.nowNode.speed = SPEED2;
			nodesr.nowNode.function = NONE;//D4绿灯(下半段直接走别卡这了)
			
			nodesr.flag |= 0x80;
			update_route_by_door_3();
			motor_pid_clear();
		}
		else // Red	D2黄 D4红 D5红 → D1,D3必定全绿
		{
			send_play_specified_command(11);
			Chassis_DriveDistance_Blocking(is_Gyro,55,-SPEED2,getAngleZ(),0);//直接退回N8

			nodesr.lastNode = nodesr.nowNode;
			nodesr.nowNode = Node[getNextConnectNode(N8, N5)];

			Chassis_Brake();
			Chassis_Turn_By_StopGyro_Blocking(nodesr.nowNode.angle, getAngleZ());//转弯准备循迹

			Node[getNextConnectNode(N8, N5)].function = NONE;//D3绿灯
			Node[getNextConnectNode(N8, N5)].speed = SPEED2;
			Node[getNextConnectNode(N8, N5)].step = 140;

			Node[getNextConnectNode(N5, N8)].function = NONE;//D3绿灯
			Node[getNextConnectNode(N5, N8)].speed = SPEED2;
			Node[getNextConnectNode(N5, N8)].step = 140;


			nodesr.flag |= 0x20;
			update_route_by_door_4();//删掉N5
		}
		state = DOOR_D2;  // 门检测完成
		break;
	}

	//close_Maxicam();
	//Robot_Work(HEAD, HEAD_MID);
}

void update_route_for_stage34(void)
{
	if(flag_line_clue == 3)
	{
		u8 route_to_2[15] = {B1, N1, P1, N1, B2, N4, N3, P3, N3, N4, N5, N12, 0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_2[i];
			if(route_to_2[i]==0xff)
				break;
		}
	}
	else if(flag_line_clue == 4)
	{
		u8 route_to_4[15] = {B1, N1, P1, N1, B2, N4, N5, N6, P4, N6, N5, N12, 0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_4[i];
			if(route_to_4[i]==0xff)
				break;
		}
	}
	else if(flag_line_clue == 0)
	{
		// 跳过 P3/P4，直接去门区
		u8 route_skip[10] = {B1, N1, P1, N1, B2, N4, N5, N12, 0XFF};
		for(uint8_t i = 0;i<10;i++)
		{
			route[i] = route_skip[i];
			if(route_skip[i]==0xff)
				break;
		}
	}

}


void update_route_by_door_1(void)
{
	//宝物拿过了，直接回家
	if(treasure ==5||treasure == 6)
	{
		for(uint8_t i = 0;i<100;i++)
		{
			route[i] = door6route[i];
			if(door6route[i]==0xff)
				break;
		}
	
	}
	//去三号平台拿宝物
	if(treasure ==3)
	{
		u8 route_to_3[15] = {P3,N3,N4,B3,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_3[i];
			if(route_to_3[i]==0xff)
				break;
		}
	}
	//去四号平台拿宝物
	if(treasure ==4)
	{
		u8 route_to_4[15] = {N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_4[i];
			if(route_to_4[i]==0xff)
				break;
		}
	}
	//去二号平台拿宝物
	if(treasure ==2)
	{
		u8 route_to_2[15] = {N4,B2,N1,P1,N1,B1,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_2[i];
			if(route_to_2[i]==0xff)
				break;
		}
	}
}
void update_route_by_door_2(void)
{
	//宝物拿过了，直接回家
	if(treasure ==5||treasure == 6)
	{
		
		for(uint8_t i = 0;i<100;i++)
		{
			route[i] = door7route[i];
			if(door7route[i]==0xff)
				break;
		}
	
	}
	//去三号平台拿宝物
	if(treasure ==3)
	{
		u8 route_to_3[15] = {N3,P3,N3,N4,B3,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_3[i];
			if(route_to_3[i]==0xff)
				break;
		}
	}
	//去四号平台拿宝物
	if(treasure ==4)
	{
		u8 route_to_4[15] = {N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_4[i];
			if(route_to_4[i]==0xff)
				break;
		}
	}
	//去二号平台拿宝物
	if(treasure ==2)
	{
		u8 route_to_2[15] = {N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_2[i];
			if(route_to_2[i]==0xff)
				break;
		}
	}
}
void update_route_by_door_3(void)
{
	//宝物拿过了，直接回家
	if(treasure ==5||treasure == 6)
	{
		
		for(uint8_t i = 0;i<100;i++)
		{
			route[i] = door8route[i];
			if(door8route[i]==0xff)
				break;
		}
	
	}
	//去三号平台拿宝物
	if(treasure ==3)
	{
		u8 route_to_3[15] = {P3,N3,N4,B3,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_3[i];
			if(route_to_3[i]==0xff)
				break;
		}
	}
	//去四号平台拿宝物
	if(treasure ==4)
	{
		u8 route_to_4[15] = {N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_4[i];
			if(route_to_4[i]==0xff)
				break;
		}
	}
	//去二号平台拿宝物
	if(treasure ==2)
	{
		u8 route_to_2[15] = {N4,B2,N1,P1,N1,B1,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_2[i];
			if(route_to_2[i]==0xff)
				break;
		}
	}
}
void update_route_by_door_4(void)
{
	//宝物拿过了，直接回家
	if(treasure ==5||treasure == 6)
	{
		
		for(uint8_t i = 0;i<100;i++)
		{
			route[i] = door11route[i];
			if(door11route[i]==0xff)
				break;
		}
	
	}
	//去三号平台拿宝物
	if(treasure ==3)
	{
		u8 route_to_3[15] = {N4,N3,P3,N3,N4,B3,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_3[i];
			if(route_to_3[i]==0xff)
				break;
		}
	}
	//去四号平台拿宝物
	if(treasure ==4)
	{
		u8 route_to_4[15] = {N6,P4,N6,N5,N4,B3,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_4[i];
			if(route_to_4[i]==0xff)
				break;
		}
	}
	//去二号平台拿宝物
	if(treasure ==2)
	{
		u8 route_to_2[15] = {N4,B2,N1,P1,N1,B1,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_2[i];
			if(route_to_2[i]==0xff)
				break;
		}
	}
}
static uint8_t is_green_or_yellow(uint8_t c) { return c == Green || c == Yellow; }

void update_route_by_QR(void)
{
	// 按线索平台组合选择路线
	if (flag_clue_stage_A == 5 && flag_clue_stage_B == 7)
	{
		if(is_green_or_yellow(color_flag[0]))
			load_route_at(0, rout_57);
		else if(is_green_or_yellow(color_flag[1]) || is_green_or_yellow(color_flag[2]))
		{
			route[0] = N12;
			load_route_at(1, rout_57);
		}
	}
	else if (flag_clue_stage_A == 5 && flag_clue_stage_B == 8)
	{
		if(is_green_or_yellow(color_flag[0]))
			load_route_at(0, rout_58);
		else if(is_green_or_yellow(color_flag[1]) || is_green_or_yellow(color_flag[2]))
		{
			route[0] = N12;
			load_route_at(1, rout_58);
		}
	}
	else if (flag_clue_stage_A == 6 && flag_clue_stage_B == 7)
	{
		if(is_green_or_yellow(color_flag[0]))
		{
			route[0] = N11;
			route[1] = N10;
			load_route_at(2, rout_67);
		}
		else if(is_green_or_yellow(color_flag[1]) || is_green_or_yellow(color_flag[2]))
		{
			route[0] = N10;
			load_route_at(1, rout_67);
		}
	}
	else if (flag_clue_stage_A == 6 && flag_clue_stage_B == 8)
	{
		if(is_green_or_yellow(color_flag[0]))
		{
			route[0] = N11;
			route[1] = N10;
			load_route_at(2, rout_68);
		}
		else if(is_green_or_yellow(color_flag[1]) || is_green_or_yellow(color_flag[2]))
		{
			route[0] = N10;
			load_route_at(1, rout_68);
		}
	}
}

///*珠峰下通道处理*/
void undermou(void)
{
	Chassis_ClearMileage();
	motor_all.Cspeed = UnderMou_Speed;//慢一点？
	infrare_open = 1;
	Robot_Work(HEAD,DOWN);
	
	while(infrared.head_left == 1 || infrared.head_right == 1)
		vTaskDelay(2);

	buzzer_on();
	Chassis_ClearMileage();

	if (nodesr.nowNode.nodenum == C8||nodesr.nowNode.nodenum == C7)
	{
		motor_all.Cspeed = Low_Speed;
		Want2Go(50);
	}
	else if (nodesr.nowNode.nodenum == C4||nodesr.nowNode.nodenum == N14)
	{
		motor_all.Cspeed = Low_Speed;
		Want2Go(50);
		motor_all.Cspeed = nodesr.nowNode.speed;
	}

				Cross_getline(&Cross_Scaner);
	while(!deal_arrive())
	{
				Cross_getline(&Cross_Scaner);
		vTaskDelay(2);
	}
	Robot_Work(HEAD,UP);
	nodesr.nowNode.function = 0;
	nodesr.flag |= 0x04; // 到达路口
}

///*忽略节点 - 直接判定到达路口*/
//void ignore_node(void)
//{
//	nodesr.nowNode.function = 0;
//	nodesr.flag |= 0x04; // 到达路口
//}

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

	if (((nodesr.nowNode.nodenum == P5 || nodesr.nowNode.nodenum == P5) && No2Tra == 1) ||
		((nodesr.nowNode.nodenum == P7 || nodesr.nowNode.nodenum == P8) && No3Tra == 1))
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
//			Chassis_MotorControl(is_No, BACK_SPEED, BACK_SPEED, 0);
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
				Chassis_MotorControl(is_No, FORWARD_SPEED, FORWARD_SPEED, 0);
				Want2Go(3);	
				CarBrake();
				Chassis_ClearMileage();
			}
			if(ReturnFlag==2||ReturnFlag==4)
			{
				Chassis_MotorControl(is_No, FORWARD_SPEED, FORWARD_SPEED, 0);
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
	if (nodesr.nowNode.nodenum == P1)
	{
		Clue_Num = 0;
	}
	else if (nodesr.nowNode.nodenum == P3 || nodesr.nowNode.nodenum == P4)
	{
		Clue_Num = 0;
	}
	else if (nodesr.nowNode.nodenum == P5 || nodesr.nowNode.nodenum == P6)
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
	else if (nodesr.nowNode.nodenum == P7 || nodesr.nowNode.nodenum == P8)
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
			Chassis_MotorControl(is_No, BACK_SPEED, BACK_SPEED, 0);
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
//	if (nodesr.nowNode.nodenum == P1)
//	{
//		flag_clue_stage_A = (QR_code/10)%10;//获取十位上的数字
//		flag_clue_stage_B = QR_code%10;//获取个位上数字
//	}
}
	
extern uint8_t isAllRoute;
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
	mpuZreset(get_latest_yaw(), nodesr.nowNode.angle); // 用稳定后的实际角度计算补偿
	vTaskDelay(100);
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
	Robot_Work(HEAD,HEAD_MID);
	vTaskDelay(100);
	Robot_Work(HEAD,UP);


	if(isAllRoute || map.routetime!=0)
	{
		RampCtrl_Blocking(RAMP_DESCEND, GoStage_Speed, getAngleZ(),
				Begin_down, GoStage_Speed, down_pitch, UpDownStage_Speed_high, After_down-10, 0.04, 10.0f);
		/*下桥完毕*/
		printf("Finished crossing the bridge\n");

	}
}



/*与ConnectFirstBack共用*/
void Connect(uint8_t Route[])
{
	static u8 temp = 0, i = 0;
	temp = map.point-1;
	i = 0;
	nodesr.nextNode = Node[getNextConnectNode(nodesr.nowNode.nodenum,Route[0])];
	nodesr.nowNode.angle = nodesr.nextNode.angle;
	while (1)
	{
		route[temp++] = Route[i++]; // 路线连接
		if (Route[i] == 255)
		{
			route[temp] = Route[i];
			break;
		}
	}
}

void select_speed_stage(void)
{
	switch ((int)nodesr.nowNode.speed) 
		{
		case SPEED4:
			line_pid_param.kp = 4.0;//5.0
			line_pid_param.ki = 0;//0
			line_pid_param.kd = 300;//260
			break;
			
		case SPEED3:
			line_pid_param.kp = 6;//8.0
			line_pid_param.ki = 0;//0
			line_pid_param.kd = 300;//300
			break;
			
		case SPEED2:
			line_pid_param.kp = 7.0;//8.0
			line_pid_param.ki = 0.008;//0.008
			line_pid_param.kd = 350;//400
			break;
			
		case SPEED0:
		case SPEED1:
			line_pid_param.kp = 7.0;//6.0
			line_pid_param.ki = 0;//0
			line_pid_param.kd = 350;//300
			break;

	  }
}
/*特殊结点*/
//void Special_Node(void)
//{
//	if (((nodesr.nowNode.flag & DRIGHT) == DRIGHT) & ((nodesr.nowNode.flag & CRIGHT) == CRIGHT) & (nodesr.nowNode.nodenum == N5)) // N4-N5右循迹 左循迹 边缘忽略
//	{																															  // N4-N5
//		nodesr.nowNode.flag &= (~RIGHT_LINE);																					  // 取消右循迹标志位
//		nodesr.nowNode.flag |= LEFT_LINE;																						  // 左循迹
//		while (deal_arrive() != 1)
//		{
//			vTaskDelay(2);
//		}								  // 右分岔
//		nodesr.nowNode.flag &= (~CRIGHT); // 取消右分岔标志位
//		while (deal_arrive() != 1)		  // 右半边天
//		{
//			vTaskDelay(2);
//			scaner_set.EdgeIgnore = 6;
//			special_arrive = 1;
//		}
//	}
//	else if ((nodesr.nowNode.nodenum == N4) & ((nodesr.nowNode.flag & CRIGHT) == CRIGHT)) // N5-N4
//	{
//		float num = 0;
//		nodesr.nowNode.flag &= (~RIGHT_LINE);
//		nodesr.nowNode.flag |= LEFT_LINE; // 左循迹
//		while (deal_arrive() != 1)
//		{
//			vTaskDelay(2);
//		}
//		num = motor_all.Distance;
//		while (fabsf(motor_all.Distance - num) < 10) // 第一个左分岔路口再走10厘米
//		{
//			vTaskDelay(2);
//		}
//		while (deal_arrive() != 1)
//		{
//			vTaskDelay(2);
//		}
//	}
//	else if ((nodesr.nowNode.nodenum == N4) & ((nodesr.nowNode.flag & CLEFT) == CLEFT)) // N3-N4
//	{
//		float num = 0;
//		nodesr.nowNode.flag &= (~LEFT_LINE);
//		nodesr.nowNode.flag |= RIGHT_LINE; // 右循迹
//		while (deal_arrive() != 1)
//		{
//			vTaskDelay(2);
//		}
//		num = motor_all.Distance;
//		while (fabsf(motor_all.Distance - num) < 10) // 第一个左分岔路口再走10厘米
//		{
//			vTaskDelay(2);
//		}
//		while (deal_arrive() != 1)
//		{
//			vTaskDelay(2);
//		}
//	}
//	else if (((nodesr.nowNode.nodenum == N13) & ((nodesr.nowNode.flag & CLEFT) == CLEFT)) & (((nodesr.nowNode.flag & CRIGHT) == CRIGHT) & ((nodesr.nowNode.flag & DLEFT) == DLEFT)) & ((nodesr.nowNode.flag & DRIGHT) == DRIGHT))
//	/*P6-N13*/ {
//		angle.AngleG = getAngleZ();
//		motor_all.Gspeed = 300;
//		pid_mode_switch(is_Gyro);
//	}
//	//	else if(nodesr.nowNode.nodenum==N9&(nodesr.nowNode.flag&CLEFT)==CLEFT)
//	//	{
//	//		float num=0;
//	//		while(!deal_arrive())
//	//		{
//	//			vTaskDelay(2);
//	//		}
//	//		num=motor_all.Distance;
//	//		while(motor_all.Distance-num<65)
//	//		{
//	//			vTaskDelay(2);
//	//		}
//	//		while(!deal_arrive())
//	//		{
//	//			vTaskDelay(2);
//	//		}
//	//	}
//	else
//	{
//		angle.AngleG = nodesr.nowNode.angle;
//		motor_all.Gspeed = 1000;
//		pid_mode_switch(is_Gyro);
//	}
//	//	if(((nodesr.nowNode.flag&CRIGHT)==CRIGHT)&((nodesr.nowNode.flag&CLEFT)==CLEFT))//N5-N6  P4-N6先左循迹后右循迹
//	//	{
//	//		angle.AngleT=getAngleZ();
//	//		pid_mode_switch(is_Gyro);
//	////		nodesr.nowNode.flag|=LEFT_LINE;//左循迹
//	////		while(deal_arrive()!=1)
//	////		{
//	////			vTaskDelay(2);
//	////		}//检测到右分岔
//	////		nodesr.nowNode.flag&=(~CRIGHT);//取消右分岔标志位
//	////		while(deal_arrive()!=1)
//	////		{
//	////			vTaskDelay(2);
//	////		}//检测到左分岔
//	////		nodesr.nowNode.flag&=(~LEFT_LINE);//取消左循迹
//	////		nodesr.nowNode.flag|=RIGHT_LINE;//右循迹
//	////		special_arrive=1;
//	//	}
//}

/*楼梯陀螺仪循迹自切换 - 使用前需在可靠位置mpuZreset*/
void CGChange(float Speed)
{
//	Cross_getline(&Cross_Scaner);
//	if(Cross_Scaner.ledNum >= 4 || Cross_Scaner.ledNum == 0 || Cross_Scaner.lineNum > 1)
//	{
//		Chassis_MotorControl(is_Gyro, Speed, Speed, nodesr.nowNode.angle);
//		//buzzer_off();
//	}
//	else
//	{
		Chassis_MotorControl(is_Line, Speed, Speed, 0);
		//buzzer_on();
//	}
}

int Six2Zero(void)
{
	static int sum = 0;
	while(Infrared_left == 1) //红外亮1s
	{
		sum++;
		vTaskDelay(2);
		if(sum == 500)
		{
			sum = 0;
			return 1;
		}
	}
	sum = 0;
	return 0;
}
