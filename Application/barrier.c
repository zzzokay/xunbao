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
#include "pid.h"
#include "math.h"
#include "bsp_buzzer.h"
#include "bsp_led.h"
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
uint8_t treasure = 0;				 // 宝藏
uint8_t value;							 // openmv接口
uint8_t DownLiuShui = 0;				 // 流水下坡标志位
float 	LiuShuiRate = LiuShuiRate_Default; // 流水下坡前轮速度倍率
uint8_t special_arrive = 0;

uint16_t QR_code = 0;
uint8_t line_clue = 4;//3
uint8_t clue_A_stage = 5;//5
uint8_t clue_B_stage = 8;//8
uint8_t clue_A = 0;
uint8_t clue_B = 0;
uint8_t get_cude = 0;
uint8_t get_a = 0;
uint8_t get_b = 0;



/*平台 - 不包括P2*/
void Stage(void)
{
	/*参数调整*/
	isStage = 1;
	struct PID_param origin_param1 = gyroG_pid_param;
	struct PID_param origin_param2 = line_pid_param;
	uint32_t add_time = 0 ;
	uint8_t getZ = 0;
	float get_angle = 0;
	float sum_angle = 0;
	float back_angle = 0;
	uint16_t break_time = 0;
	uint8_t P5_flag=0;

	gyroG_pid_param.kp = 3.5;	//4.5
	gyroG_pid_param.ki = 0;
	gyroG_pid_param.kd = 30;
	
//	line_pid_param.kp = 12*2;
//	line_pid_param.ki = 0;
//	line_pid_param.kd = 400;
//	
	select_speed_stage();
//  if(nodesr.nowNode.nodenum == P3 )
//	{
//		line_pid_param.kp = 6.0;
//		line_pid_param.ki = 0;
//		line_pid_param.kd = 260;
//	}
//	 if(nodesr.nowNode.nodenum == P4 )
//	{
//		line_pid_param.kp = 6.0;
//		line_pid_param.ki = 0;
//		line_pid_param.kd = 260;
//	}
	
	/*设置起始模式速度*/
	Chassis_ClearMileage();
//	//改成灰度循迹
	if(nodesr.nowNode.nodenum == P1||nodesr.nowNode.nodenum == P5)
		{
			line_pid_param.kp = 30.0;//50.0
			line_pid_param.ki = 0;
			line_pid_param.kd = 250;
			ScanerMode_Switch(Gray);
		}
	if(nodesr.nowNode.nodenum == P3)
	{
		open_qiang_jiao = 1;
		Chassis_MotorControl(is_Line,UpStage_Speed-10,UpStage_Speed-10,0);
	}else
	{
		Chassis_MotorControl(is_Line,UpStage_Speed-5,UpStage_Speed-5,0);//UpStage_Speed-5
	}
	scaner_set.EdgeIgnore = 2;//3
//	Cross_getline(&Cross_Scaner);
//	if ((Cross_Scaner.detail & 0x180) == 0x180)
//		mpuZreset(imu.yaw, getAngleZ());

	
	uint8_t breakflag = 0;
	

	while (imu.pitch < (basic_p + 8))
	{
		Cross_getline(&Cross_Scaner);
		if (((nodesr.nowNode.nodenum == P1||nodesr.nowNode.nodenum == P5)&&(Scaner.detail_gray & 0x18))||((Cross_Scaner.detail & 0x180) == 0x180))
		{
			mpuZreset(get_latest_yaw(), getAngleZ());
			angle.AngleG = getAngleZ();
			buzzer_on();
			getZ = 1;
		}
		vTaskDelay(2);
	}
/*********************改****************************/
//	while (imu.pitch < (basic_p + 8))
//	{
//		Cross_getline(&Cross_Scaner);
//		if ((Cross_Scaner.detail & 0x180) == 0x180)
//		{
//			mpuZreset(get_latest_yaw(), getAngleZ());
//			angle.AngleG = getAngleZ();
//			buzzer_off();
//			getZ = 1;
//		}
//		if(nodesr.nowNode.nodenum == P5 && P5_flag==0 )
//		{
//			Chassis_ClearMileage();
//			//CarBrake();
//			motor_all.Cspeed = UpStage_Speed-15;
//			vTaskDelay(70);
//				/*循迹矫正*/
//			gyroG_pid_param.kp = 1.5;//8
//			gyroG_pid_param.ki = 0.004;
//			gyroG_pid_param.kd = 20;
//			
//			if(Cross_Scaner.detail & 0xFF)
//			Chassis_MotorControl(is_Gyro, UpStage_Speed-15, UpStage_Speed-15, getAngleZ()-10);
//		  else if(Cross_Scaner.detail & 0xFF00)
//			Chassis_MotorControl(is_Gyro, UpStage_Speed-15, UpStage_Speed-15, getAngleZ()+10);
//				
//			while (fabs(need2turn(getAngleZ(), angle.AngleG)) > 5 )
//			{
//				break_time++;
//				Cross_getline(&Cross_Scaner);
//				if ((Cross_Scaner.detail & 0x180) == 0x180) 
//				{
//					mpuZreset(get_latest_yaw(), getAngleZ());
//					angle.AngleG = getAngleZ();
//					buzzer_off();
//					getZ = 1;
//					buzzer_on();
//					break;
//				}
//				if (break_time > 500) 
//				{
//					break;
//				}
//				vTaskDelay(2);
//			}
//			//原来参数
//			gyroG_pid_param.kp = 3.5;	//4.5
//			gyroG_pid_param.ki = 0;
//			gyroG_pid_param.kd = 30;
//			Chassis_MotorControl(is_Line,UpStage_Speed-5,UpStage_Speed-5,0);//UpStage_Speed-5
//			P5_flag = 1;
//		}
//		vTaskDelay(2);
//	}
/***************************************************/
	if(getZ == 0)
	{
		if(nodesr.nowNode.nodenum == P1)
		{
			angle.AngleG = nodesr.nowNode.angle;
		}
		else
		{
				for(add_time;add_time<5;add_time++)
			{
				get_angle = getAngleZ();
				sum_angle += get_angle;
			}
			angle.AngleG = sum_angle/add_time;
  }
	}


	while (1)
	{
		Cross_getline(&Cross_Scaner);

		if (Cross_Scaner.ledNum > 5 || Cross_Scaner.lineNum >= 2)
		{
			breakflag++;
			if (breakflag >= 3)	//3
				break;
		}
		
		vTaskDelay(2);
	}
	scaner_set.EdgeIgnore = 0;
	line_pid_param = origin_param2;
	buzzer_on();
	/*设置自平衡速度*/
	Robot_Work(BODY, UP); 	// 人站起来

	/*设置自平衡速度*/	
	Chassis_MotorControl(is_Gyro,GoStage_Speed,GoStage_Speed,angle.AngleG);
	Chassis_ClearMileage();
	
	/*检测挡板*/
	while (Infrared_ahead == 0)
		vTaskDelay(5);
	
	buzzer_off();
	
	motor_all.Gspeed = IMPACT_SPEED;
	Want2Go(17);
	
	Chassis_MotorControl(is_Free,-1500,-1500,0);
	Want2Go(0.5);
	
	Chassis_ClearMileage();
	K210_Rece = 0;
	open_OCR_mode();
	CarBrake();
	ScanerMode_Switch(RF);//切回激光循迹
	vTaskDelay(500);
	mpuZreset(get_latest_yaw(), nodesr.nowNode.angle); 		//陀螺仪校正
	back_angle = getAngleZ();//转身后的目标角度

//	mpuZreset(imu.yaw, nodesr.nowNode.angle); 		//陀螺仪校正

	/*后退一段距离*/
	Chassis_MotorControl(is_Free,-1500,-1500,0);
	Want2Go(1);//3
	Chassis_ClearMileage();
	CarBrake();
	vTaskDelay(100);

	/*平台动作*/
	switch (nodesr.nowNode.nodenum)
	{
	case P1:	//2
		send_play_specified_command(5);
		break;
	case P3:	//3
		send_play_specified_command(4);
		break;
	case P4:	//4
		send_play_specified_command(3);
		break;
	case P5:	//6
		send_play_specified_command(1);
		break;
	case P6:	//5
		send_play_specified_command(2);
		break;
	default:
		break;
	}
	Arrived_Stage();
	vTaskDelay(500);
	
	
		/*扫描二维码获取平台以及线索点*/
//	if(treasure == 0 &&nodesr.nowNode.nodenum != P1)
	if(treasure == 0 &&(nodesr.nowNode.nodenum == P5 ||nodesr.nowNode.nodenum == P6 ||nodesr.nowNode.nodenum == P7 ||nodesr.nowNode.nodenum == P8))
		WaitFor_OCR();
	
	if(nodesr.nowNode.nodenum == P1 && get_cude == 0)
	{
		open_QR_mode();//切换至二维码识别模式
		WaitFor_QR();
		update_route_for_stage34();//选择去四号平台还是三号平台
	}
///*扫描二维码获取平台以及线索点*/
//	if(treasure == 0 &&nodesr.nowNode.nodenum != P1&&map.routetime==0)
//		WaitFor_OCR();
//	
//	if(nodesr.nowNode.nodenum == P1 && get_cude == 0&& map.routetime==0)
//		WaitFor_QR();
	
	
	/*转身*/
	Turn_Angle_Relative(179);
	while (fabs(angle.AngleT - getAngleZ()) > 2)
		vTaskDelay(2);

	CarBrake();
	vTaskDelay(100);

	/*发现宝藏流程*/
	//宝物只在2到6号平台
	if ((nodesr.nowNode.nodenum == P1 && treasure == 2)||
		(nodesr.nowNode.nodenum == P3 && treasure == 3) ||
		(nodesr.nowNode.nodenum == P4 && treasure == 4) ||
		(nodesr.nowNode.nodenum == P5 && treasure == 6) ||
		(nodesr.nowNode.nodenum == P6 && treasure == 5))
	{
		
		Chassis_MotorControl(is_No, FORWARD_SPEED, FORWARD_SPEED, 0);
		Want2Go(5);
		CarBrake();
		Chassis_ClearMileage();
		
		motor_pid_clear();
		Robot_Work(LARM, UP);
		//vTaskDelay(500);
		Robot_Work(RARM, UP);
		send_play_specified_command(9);
		Turn_Angle360();
		Robot_Work(LARM, DOWN);
		//vTaskDelay(500);
		Robot_Work(RARM, DOWN);
	}
	

	motor_pid_clear();
	
	/*下平台*/
//	line_pid_param.kp = 20;
//	line_pid_param.ki = 0;
//	line_pid_param.kd = 300;
	Chassis_MotorControl(is_Line, Rubbish_Speed-2, Rubbish_Speed-2, 0);
	while (imu.pitch > basic_p - 8)
		vTaskDelay(2);
	
	
	if ((nodesr.nowNode.nodenum == P1 && treasure == 2)||
	(nodesr.nowNode.nodenum == P3 && treasure == 3) ||
	(nodesr.nowNode.nodenum == P4 && treasure == 4) ||
	(nodesr.nowNode.nodenum == P5 && treasure == 6) ||
	(nodesr.nowNode.nodenum == P6 && treasure == 5))
	{
		Chassis_MotorControl(is_Gyro, Rubbish_Speed, Rubbish_Speed, getAngleZ());
	}
	else
	{
		Chassis_MotorControl(is_Gyro, Rubbish_Speed, Rubbish_Speed, back_angle-180.0);//back_angle-180.0gyroG_pid_param = origin_param1;
	}
	LiuShuiRate = LiuShuiRate_ST;
	DownLiuShui = 1;
	while (imu.pitch < After_down)
		vTaskDelay(2);
	LiuShuiRate = LiuShuiRate_Default;
	DownLiuShui = 0;
	/*下完平台*/
	//Want2Go(30);//一直巡线，下平台的固定距离	
	Chassis_ClearMileage();
	Chassis_MotorControl(is_Line, Rubbish_Speed, Rubbish_Speed, 0);
	if(nodesr.nowNode.nodenum==P5)
		Want2Go(2);
	else
		Want2Go(10);																																																																																																																																																																																																																																																																																																																																																																																																							
	Robot_Work(BODY,DOWN);		 		// 人躺下
	line_pid_param = origin_param2;
	nodesr.nowNode.function = 0;		// 清除障碍标志
	nodesr.flag |= 0x04;		 		// 到达路口
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
void Barrier_Bridge(void)
{
	//打印：执行过桥流程
	printf("Executing bridge crossing procedure\n");
	Chassis_MotorControl(is_Line, GoStage_Speed, GoStage_Speed, 0);
	Chassis_ClearMileage();
	static uint8_t stable_times = 0;
	while (fabsf(Chassis_GetMileage()) < 25)
	{
		Cross_getline(&Cross_Scaner);
		
		if((Cross_Scaner.detail & 0X0180) == 0X0180)		//如果在最中间位置
		{
			stable_times++;
			if (stable_times>= 5)		//如果连续多次检测到在最中间位置，认为检测稳定，进行陀螺仪校正
			{
			mpuZreset(get_latest_yaw(), nodesr.nowNode.angle);     	//获取补偿角Z;
			printf("gyro reset\n");
			}
			else
			{
				stable_times = 0;
			}		
		}
			
		if (Scaner.ledNum >= 4 || Scaner.lineNum >= 2 || Scaner.lineNum == 0 || Scaner.ledNum == 0)
			break;
		vTaskDelay(2);
	}
	//Chassis_Brake();
	//打印：检测到桥，准备上桥
	printf("Bridge detected, preparing to ascend\n");

 // 	/*准备上桥*/
  	Chassis_MotorControl(is_Gyro, GoStage_Speed, GoStage_Speed, getAngleZ());
 	//还没上桥
  	while (imu.pitch < Up_pitch)
 		vTaskDelay(2);
	
 	//打印：上坡中，等待到达桥顶
 	printf("On ramp, waiting for bridge top\n");
  	while (imu.pitch > After_up)
  	{
     	vTaskDelay(2);
  	}

 	//Chassis_Brake();
 	//打印：已到达桥上，准备过桥
 	printf("At bridge, preparing to cross\n");

 	Chassis_ClearMileage();
 	//姿态校准
	//打印angle.AngleG,getAngleZ()，imu.yaw，nodesr.nowNode.angle
	
 	get_Infrared();
  	while (infrared.head_left == 1 || infrared.head_right == 1)
  	{
		
 		Chassis_CorrectByInfrared(0.1f);
  		vTaskDelay(2);
 	}
	
 	//姿态校准完成退出循环

	Chassis_Brake();
// 	//加速
// 	Chassis_MotorControl(is_Gyro, SPEED0, SPEED0, getAngleZ());
// 	while(fabsf(Chassis_GetMileage()) < 80)
// 	{	
// 		Chassis_CorrectByInfrared(2.7f);
// 		vTaskDelay(2);
//  	}
// 	//加速完定距离退出循环

// 	Chassis_MotorControl(is_Gyro, GoStage_Speed, GoStage_Speed, getAngleZ());
// 	//车还在桥上
// 	while (imu.pitch > basic_p - 5)
// 	{
// 		Chassis_CorrectByInfrared(2.7f);
// 		vTaskDelay(2);
// 	}
// 	//车检测到下坡跳出循环
	
// 	while(imu.pitch < basic_p - 15)
// 	{
// 		Chassis_CorrectByInfrared(2.7f);
// 		vTaskDelay(2);
// 	}	
// 	//车检测到地面跳出循环

// 	Chassis_MotorControl(is_Line, Rubbish_Speed, Rubbish_Speed, 0);
// 	nodesr.nowNode.function = 0;
// 	nodesr.flag |= 0X04;// 到达路口 

}

/*楼梯*/
void Barrier_Hill(void)
{
	struct PID_param origin_param1 = line_pid_param;
	motor_all.Cspeed = Gyro_Speed;
	infrare_open = 1;
	uint16_t break_times = 0;
	while (infrared.head_left == 1 && infrared.head_right == 1)
	{
		break_times++;
		if(break_times > 1000)
			break;
		Cross_getline(&Cross_Scaner);
		if ((Cross_Scaner.detail & 0X180) == 0X180)
			mpuZreset(get_latest_yaw(), nodesr.nowNode.angle);
		vTaskDelay(2);
	}

	line_pid_param.kp = 20;
	line_pid_param.ki = 0.004;
	line_pid_param.kd = 0;
	scaner_set.EdgeIgnore = 3;
	Chassis_MotorControl(is_Line, 12, 12, 0);
	/*平地*/
	while (imu.pitch < basic_p + 8)
	{
		//CGChange(GoStage_Speed);
		
		vTaskDelay(2);
	}
	/*平地->上平台*/
	buzzer_on();
	while (imu.pitch > basic_p - 8)
	{
//		CGChange(GoStage_Speed);
		vTaskDelay(2);
	}
	/*下平台*/
	while (imu.pitch < basic_p - 5)
	{
//		CGChange(GoStage_Speed);
		vTaskDelay(2);
	}
	/*下完平台到平地*/
	buzzer_off();
	scaner_set.EdgeIgnore = 0;
	Chassis_MotorControl(is_Line, Rubbish_Speed+6, Rubbish_Speed+6, 0);
	Want2Go(10);					// 往前走一点防止弹射起步
	Chassis_ClearMileage();
	nodesr.nowNode.function = 0; 	// 清除障碍标志
	line_pid_param = origin_param1;
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
	while(imu.pitch < Up_pitch)
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
	// while (imu.pitch < Up_pitch)
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
	K210_Rece = 0;
	open_OCR_mode();
	CarBrake();
	vTaskDelay(250);
	mpuZreset(get_latest_yaw(), nodesr.nowNode.angle); // 陀螺仪校正
	//Arrived_Stage();
		//获取宝物线索B
	if(treasure == 0 && map.routetime==0)
		WaitFor_OCR();
	
	//如果宝物线索B在平台8,已经拿完所有线索重新规划路线
	if(map.routetime == 0&&map.routetime==0)
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
	float num = 0;
	uint8_t getZ = 0;
	float origin_turnM = motor_all.GyroT_speedMax;
	struct PID_param origin_param = line_pid_param;
	struct PID_param origin_param1 = gyroG_pid_param;
	
	uint32_t add_time = 0 ;
	float get_angle = 0;
	float sum_angle = 0;
	
	motor_all.GyroT_speedMax = 25;
	gyroG_pid_param.kp = 0.5;
	gyroG_pid_param.ki = 0;
	gyroG_pid_param.kd = 0.5;
	
	
	/*等待识别到坡*/
	Chassis_ClearMileage();
	num = motor_all.Distance;
	while (fabsf(motor_all.Distance - num) < 150)//80
	{
		vTaskDelay(2);
		if((Scaner.detail & 0X180) == 0X180)
		{
			angle.AngleG = getAngleZ();
			getZ = 1;
		}
		if (Scaner.ledNum >= 4 || Scaner.lineNum >= 2)
			break;
	}
	if(getZ == 0)
		angle.AngleG = nodesr.nowNode.angle;
	
	line_pid_param.kp = 17;//18
	line_pid_param.ki = 0;
	line_pid_param.kd = 400;//25
	
	Chassis_ClearMileage();	
	/*等待开始上坡*/
	Chassis_MotorControl(is_Gyro, Low_Speed, Low_Speed, angle.AngleG);
	num = motor_all.Distance;
	while (fabsf(motor_all.Distance - num) < 40)
	{
		if (imu.pitch > basic_p + 10)
			break;
		vTaskDelay(2);
	}
	/*开始上坡*/
	Chassis_MotorControl(is_Line, Mount_Speed-7, Mount_Speed-7, 0);
	Robot_Work(BODY, UP);
	Chassis_ClearMileage();
	buzzer_on();
	getZ = 0;
	num = motor_all.Distance;
	add_time = 0 ;
	get_angle = 0;
	sum_angle = 0;
	while (fabsf(motor_all.Distance - num) < 180)//fabsf(motor_all.Distance - num) < 140
	{
		vTaskDelay(2);
		if(((Scaner.detail & 0X180) == 0X180)&&add_time<10)
		{
//			add_time++;
//			get_angle = getAngleZ();
//			sum_angle = sum_angle + get_angle;
			angle.AngleG = getAngleZ();
			getZ = 1;
		}
		if(Scaner.ledNum >= 10 && (fabsf(motor_all.Distance - num) > 80))
			break;
	}
//	angle.AngleG = sum_angle/add_time;
//	add_time = 0 ;
//	get_angle = 0;
//	sum_angle = 0;
	
	/*上坡结束*/
	buzzer_off();
	if(getZ == 0)
		angle.AngleG = nodesr.nowNode.angle;
	
	gyroG_pid_param.kp = 3;//4.5
	gyroG_pid_param.ki = 0;
	gyroG_pid_param.kd = 0;
	Chassis_MotorControl(is_Gyro, IMPACT_SPEED-5, IMPACT_SPEED-5, angle.AngleG);

	/*撞挡板*/
	while (Infrared_ahead == 0)
		vTaskDelay(5);
	Want2Go(17);
	Chassis_MotorControl(is_Free,-1500,-1500,0);
	Want2Go(0.5);
	
	Chassis_ClearMileage();
  K210_Rece = 0;
	open_OCR_mode();
	CarBrake();
	vTaskDelay(200);
	mpuZreset(get_latest_yaw(), nodesr.nowNode.angle); // 陀螺仪校正
	//Arrived_Stage();

	
	/*后退一段距离*/
	num = motor_all.Distance;
	Chassis_MotorControl(is_Free, -2000, -2000, 0);
	while (fabsf(motor_all.Distance - num) < 4.5) //5.0f
		vTaskDelay(2);
	Chassis_ClearMileage();
	send_play_specified_command(12);
	CarBrake();
	Arrived_Stage();
	//vTaskDelay(500);
	
	/*扫描二维码获取平台以及线索点*/
		//获取宝物线索B，若已知线索则不开
	if(treasure == 0 &&map.routetime==0)
		WaitFor_OCR();
	
	//如果宝物线索B在平台7,已经拿完所有线索重新规划路线
	if(map.routetime == 0&&map.routetime==0)
	{
		//buzzer_off();
		update_rout_by_treasure_7();
	}
	
	/*180°转*/
	Turn_Angle_Relative(179);
	while (fabs(angle.AngleT - getAngleZ()) > 2)
		vTaskDelay(5);
	motor_pid_clear();

//	/*宝藏*/
//	if (treasure[2] == 7)
//	{
//		Robot_Work(LARM, UP);
//		Robot_Work(RARM, UP);
//		send_play_specified_command(9);
//		Turn_Angle360();
//		Robot_Work(LARM, DOWN);
//		Robot_Work(RARM, DOWN);
//	}

	/*开始下坡*/
	buzzer_on();
	Robot_Work(BODY, DOWN);
	Chassis_MotorControl(is_Gyro, Rubbish_Speed - 5, Rubbish_Speed - 5, 0);

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
	line_pid_param.kp = 35;
	line_pid_param.ki = 0;
	line_pid_param.kd = 1.5;
	Chassis_MotorControl(is_Line, Old_M_Speed, Old_M_Speed, 0);
	/*前进一小段*/
	Chassis_ClearMileage();
	Want2Go(40);

	/*切换循迹，开始下坡*/
	line_pid_param.kp = 12*2;
	line_pid_param.ki = 0;
	line_pid_param.kd = 400;
	Chassis_MotorControl(is_Line, UnderMou_Speed, UnderMou_Speed, 0);
	while (imu.pitch < After_down)
		vTaskDelay(2);
	/*下坡结束*/

	buzzer_off();
	line_pid_param = origin_param;
	gyroG_pid_param = origin_param1;
	motor_all.GyroT_speedMax = origin_turnM;
	nodesr.nowNode.function = 0;
	nodesr.flag |= 0x04; // 到达路口
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
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P6,N13,N12,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
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
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P6,N13,N12,N8,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
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
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P6,N13,N12,N8,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
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
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P6,N13,N12,N11,N10,N3,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,0XFF}; copy_route(r); break; }
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
				{ const u8 r[] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,P6,N13,N12,N11,N10,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {N22,B6,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
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
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N13,P6,N13,N12,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N11,N12,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
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
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N10,N11,N12,N13,P6,N13,N12,N8,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N5,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
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
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,N10,N11,N12,N13,P6,N13,N12,N8,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N8,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
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
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N13,P6,N13,N12,N11,N10,N3,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,0XFF}; copy_route(r); break; }
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
				{ const u8 r[] = {B6,N22,B7,C6,N19,B5,N18,N16,N12,N13,P6,N13,N12,N11,N10,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
			case 6:
				{ const u8 r[] = {C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,N3,N4,B3,N2,P2,0XFF}; copy_route(r); break; }
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
//	 while(imu.pitch < Down_pitch+6)
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
	while(imu.pitch > Down_pitch+6)
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

/*看灯*/
void door()
{
	static uint8_t flag = 0;
	static uint8_t wait_cnt = 0;
	buzzer_on();

	if (flag <= 10) // 去
			{
				Robot_Work(HEAD,HEAD_RIGHT);
			}
			else
			{
				Robot_Work(HEAD,HEAD_LEFT);
			}
	
	while (1)
	{
		/*走到灯前*/
		if (Scaner.ledNum >= 8)
		{
			buzzer_off();
			Chassis_MotorControl(is_No, 0, 0, 0);
			/*判断开哪边的MV*/
			Color_Right = Color_Left = 0;
			if (flag <= 10) // 去
			{
				Open_COLOR_R();}
			else
			{
				Open_COLOR_L();}

			/*等看完灯*/
			uint16_t outtime = 0;

//			 if (nodesr.nowNode.nodenum == N12)
//			 	Color_Right = Red;
//			 if (nodesr.nowNode.nodenum == N3)
//			 	Color_Right = Green;
			
			while (Color_Right == 0 && Color_Left == 0)
			{
				outtime++;
				if (outtime >= 750)
					break;
				vTaskDelay(2);
			}

			/*第一次看灯 - 看D2*/
			if (flag == 0)
			{
				while (1)
				{
					/*红灯 - 回去准备看D3*/
					if (Color_Right == Red)
					{
						color_flag[0] = Color_Right;
						send_play_specified_command(11);
						map.point = 0;
						route[map.point] = N8;

						Turn_Angle_Relative(181);
						while (fabs(angle.AngleT - getAngleZ()) > 2)
						{
							getline_error();
							if (Scaner.lineNum == 1 && ((Scaner.detail & 0x3C0)) != 0 && (fabs(need2turn(angle.AngleT, getAngleZ())) < 27))
							{
								break;
							}
							vTaskDelay(2);
						}

						nodesr.nowNode = Node[getNextConnectNode(N12, N5)];
						nodesr.nowNode.step = 70;	
						nodesr.nowNode.flag = STOPTURN | DRIGHT | DLEFT;
						nodesr.nowNode.speed = SPEED4;
						
						motor_all.Cspeed = nodesr.nowNode.speed;
						pid_mode_switch(is_Line);
						nodesr.flag |= 0x20;
						flag = 1;
						close_Maxicam();
						//看完头回正
						Robot_Work(HEAD,HEAD_MID);
						return;
					}
					/*绿灯 - 继续前进*/
					else if (Color_Right == Green)
					{
						color_flag[0] = Color_Right;
						send_play_specified_command(8);
						map.point = 0;
						nodesr.nowNode = Node[getNextConnectNode(N5, N12)]; // 重新设置nowNode
						nodesr.nowNode.flag = DLEFT | DRIGHT | LEFT_LINE;
						nodesr.nowNode.step = 120 /*100*/;
						nodesr.nowNode.speed = SPEED2;
						nodesr.nowNode.function = NONE;
						//更新路径
						update_route_by_QR();
						
						motor_all.Cspeed = nodesr.nowNode.speed;
						
						pid_mode_switch(is_Line);
						line_pid_obj = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
						TC_speed = 0;
						
						nodesr.flag |= 0x80;
						flag = 0;	//确定路线
						close_Maxicam();
						//看完头回正
						Robot_Work(HEAD,HEAD_MID);
						return;
					}
					/*黄灯 - 继续前进，需要看D5*/
					else if (Color_Right == Yellow)
					{
						send_play_specified_command(10);
						color_flag[0] = Color_Right;
						map.point = 0;
						nodesr.nowNode = Node[getNextConnectNode(N5, N12)]; // 重新设置nowNode
						nodesr.nowNode.flag = DLEFT |DRIGHT|CRIGHT|MUL2SING|LEFT_LINE;
						nodesr.nowNode.step = 120;//90
						nodesr.nowNode.speed = SPEED2;
						nodesr.nowNode.function = NONE;
						//更新路径
						update_route_by_QR();
						
						line_pid_obj = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
						TC_speed = 0;
						
						motor_all.Cspeed = nodesr.nowNode.speed;
						pid_mode_switch(is_Line);
						nodesr.flag |= 0x80;
						flag = 11;	//需要看D5
						close_Maxicam();
						//看完头回正
						Robot_Work(HEAD,HEAD_MID);
						return;
					}
					/*错误*/
					else
					{
						CarBrake();
					}
					vTaskDelay(2);

					/*超时还没看完灯就再开一次*/
					wait_cnt++;
					if (wait_cnt == 50)
					{
						wait_cnt = 0;
						Open_COLOR_R();
					}
				}
			}
			/*第二次看灯 - D2红,看D3*/
			if (flag == 1)
			{
				while (1)
				{
					/*红灯 - 回去*/
					if (Color_Right == Red)
					{
						color_flag[1] = Color_Right;
						send_play_specified_command(11);
						map.point = 0;
						Turn_Angle_Relative(181);
						while (fabs(angle.AngleT - getAngleZ()) > 2)
						{
							vTaskDelay(2);
						}
						
						nodesr.nowNode = Node[getNextConnectNode(N8, N5)]; // 重新设置nowNode
						nodesr.nowNode.flag |= CLEFT | CRIGHT;
						nodesr.nowNode.step = 70;
						nodesr.nowNode.speed = SPEED4;
						nodesr.nowNode.function = NONE;
						
						for(uint8_t i = 0;i<100;i++)
						{
							route[i] = door1route[i];
							if(door1route[i]==0xff)
							{
								break;
							}
						}
						//route_reset(1);
						motor_all.Cspeed = nodesr.nowNode.speed;
						pid_mode_switch(is_Line);
						nodesr.flag |= 0x20;
						flag = 2;
						close_Maxicam();
						//看完头回正
						Robot_Work(HEAD,HEAD_MID);
						return;
					}
					/*非红灯 - 继续走*/
					else if (Color_Right == Green | Color_Right == Yellow)
					{
						nodesr.nowNode = Node[getNextConnectNode(N5, N8)]; // 重新设置nowNode
						nodesr.nowNode.flag = DLEFT | LEFT_LINE | DRIGHT;
						nodesr.nowNode.step = 60;//60
						nodesr.nowNode.speed = SPEED2;
						nodesr.nowNode.function = NONE;
						map.point = 0;
						if (Color_Right == Green)
						{
							color_flag[1] = Color_Right;
							send_play_specified_command(8);
							Node[getNextConnectNode(N8, N5)].function = NONE;
							Node[getNextConnectNode(N8, N5)].speed = SPEED4;
							Node[getNextConnectNode(N8, N5)].step = 150;
							
							//更新路径
							update_route_by_QR();
							
							flag = 0;	//确定路线
						}
						else if (Color_Right == Yellow)
						{
							color_flag[1] = Color_Right;
							send_play_specified_command(10);
							nodesr.flag |= 0x80;
							
							//更新路径
							update_route_by_QR();
							
							flag = 11;	//要看D5
						}
						Chassis_MotorControl(is_Line, nodesr.nowNode.speed, nodesr.nowNode.speed, 0);
						close_Maxicam();
						nodesr.flag |= 0x80;
						//看完头回正
						Robot_Work(HEAD,HEAD_MID);
						return;
					}
					else
						CarBrake();
					vTaskDelay(2);
					wait_cnt++;
					if (wait_cnt == 50)
					{
						wait_cnt = 0;
						Open_COLOR_R();
					}
				}
			}
			/*第三次看灯 - D2红,D3红,看D4*/
			if (flag == 2)
			{
				flag = 0;
				while (1)
				{
					/*绿灯 - 继续前进*/
					if (Color_Right == Green)
					{
						send_play_specified_command(8);
						color_flag[2] = Color_Right;
			
						Node[getNextConnectNode(N8, N3)].function = NONE;
						Node[getNextConnectNode(N8, N3)].speed = SPEED4;
						Node[getNextConnectNode(N8, N3)].step = 140;
						
						//更新路径
						update_route_by_QR();
						
						//route_reset(4);
						close_Maxicam();
						break;
					}
					/*黄灯 - 继续前进*/
					//则D5必为绿色
					else if (Color_Right == Yellow)
					{
						send_play_specified_command(10);
						color_flag[2] = Color_Right;
						Node[getNextConnectNode(N10, N3)].function = NONE;		//D5必定绿，不用看
						Node[getNextConnectNode(N10, N3)].speed = SPEED4;//SPEED4
						Node[getNextConnectNode(N10, N3)].step = 200;
						
						//更新路径
						update_route_by_QR();
						
						//route_reset(9);
						close_Maxicam();
						break;
					}
					else
					{
						CarBrake();
					}
					vTaskDelay(2);
					wait_cnt++;
					if (wait_cnt == 50)
					{
						wait_cnt = 0;
						Open_COLOR_R();
					}
				}
				map.point = 0;
				nodesr.nowNode = Node[getNextConnectNode(N3, N8)]; // 重新设置nowNode
				nodesr.nowNode.flag = DLEFT | DRIGHT;
				nodesr.nowNode.step = 60;
				nodesr.nowNode.speed = SPEED3;
				nodesr.nowNode.function = NONE;
				nodesr.flag |= 0x80;
				
				motor_all.Cspeed = nodesr.nowNode.speed;
				pid_mode_switch(is_Line);
				nodesr.nowNode.function = 1;
				//看完头回正
				Robot_Work(HEAD,HEAD_MID);
				return;
			}
			/*看D5 - 两种情况：1.D2黄 2.D2红 D3黄*/
			if (flag == 11)
			{
				while (1)
				{
					/*绿灯 - 继续前进*/
					if (Color_Left == Green)
					{
						send_play_specified_command(8);
						color_flag[3] = Color_Left;
						map.point = 0;
						nodesr.nowNode = Node[getNextConnectNode(N10, N3)]; // 重新设置nowNode
						nodesr.nowNode.flag = DRIGHT | RIGHT_LINE;
						nodesr.nowNode.step = 65;
						nodesr.nowNode.speed = SPEED4;
						nodesr.nowNode.function = NONE;
						nodesr.flag |= 0x80;
						update_route_by_door_1();
						
						break;
					}
					/*红灯 - 返回看情况*/
					else if (Color_Left == Red)
					{
						send_play_specified_command(11);
						color_flag[3] = Color_Left;
						
						/*D2黄，D5红，去看D4*/
						if (color_flag[0] == Yellow)
						{
							map.point -= 2;
							route[map.point] = N8;
							route[map.point + 1] = N3;

							Turn_Angle_Relative(181);
							while (fabs(angle.AngleT - getAngleZ()) > 2)
							{
								vTaskDelay(2);
							}

							nodesr.nowNode = Node[getNextConnectNode(N3, N10)];
							nodesr.nowNode.step = 70;
							nodesr.nowNode.flag = DRIGHT | DLEFT;
							nodesr.nowNode.speed = SPEED3;
							flag = 12;
						}
						/*D2红，D3黄，D5红，剩下的必定都是绿*/
						else if ((color_flag[0] == Red) && (color_flag[1] == Yellow))
						{
							Turn_Angle_Relative(181);
							while (fabs(angle.AngleT - getAngleZ()) > 2)
							{
								vTaskDelay(2);
							}

							map.point = 0;
							nodesr.nowNode = Node[getNextConnectNode(N3, N10)]; // 重新设置nowNode
							nodesr.nowNode.flag = DLEFT | DRIGHT;
							nodesr.nowNode.step = 70;
							nodesr.nowNode.speed = SPEED3;
							nodesr.nowNode.function = NONE;
							
							Node[getNextConnectNode(N8, N3)].function = NONE;
							Node[getNextConnectNode(N8, N3)].speed = SPEED4;
							Node[getNextConnectNode(N8, N3)].step = 150;
							
							update_route_by_door_2();
							//route_reset(7);
							flag = 0;
						}
						nodesr.flag |= 0x20;
						break;
					}
					else
					{
						CarBrake();
					}
					vTaskDelay(2);
					wait_cnt++;
					if (wait_cnt == 50)
					{
						wait_cnt = 0;
						Open_COLOR_L();
					}
				}
				
				close_Maxicam();
				pid_mode_switch(is_Line);
				motor_all.Cspeed = nodesr.nowNode.speed;
				nodesr.nowNode.function = 1;
				//看完头回正
				Robot_Work(HEAD,HEAD_MID);
				return;
			}
			/*看D4 - D2黄，D5红，需要看D4确认*/
			if (flag == 12)
			{
				while (1)
				{
					/*绿灯 - 继续前进*/
					if (Color_Left == Green)
					{
						send_play_specified_command(8);
						color_flag[2] = Color_Left;
						map.point = 0;
						nodesr.nowNode = Node[getNextConnectNode(N8, N3)]; // 重新设置nowNode
						nodesr.nowNode.flag = LEFT_LINE | MUL2MUL | STOPTURN;
						nodesr.nowNode.step = 10;
						nodesr.nowNode.speed = SPEED3;
						nodesr.nowNode.function = 1;
						nodesr.flag |= 0x80;
						
						update_route_by_door_3();
						//route_reset(8);
						motor_pid_clear();
						break;
					}
					/*红灯 - 剩下的都是绿灯*/
					else if (Color_Left == Red)
					{
						send_play_specified_command(11);
						color_flag[2] = Color_Left;
						Turn_Angle_Relative(181); //	转到当前结点方向
						while (fabs(angle.AngleT - getAngleZ()) > 2)
						{
							vTaskDelay(2);
						}

						Node[getNextConnectNode(N8, N5)].function = NONE;
						Node[getNextConnectNode(N8, N5)].speed = SPEED4;
						Node[getNextConnectNode(N8, N5)].step = 150;
						
						map.point = 0;
						nodesr.nowNode = Node[getNextConnectNode(N3, N8)];
						nodesr.nowNode.flag = STOPTURN | CLEFT | CRIGHT | DRIGHT | DLEFT;
						nodesr.nowNode.speed = SPEED3;
						motor_all.Cspeed = nodesr.nowNode.speed;

						update_route_by_door_4();
						//route_reset(11);
						nodesr.flag |= 0x20;
						close_Maxicam();
						break;
					}
					else
					{
						CarBrake();
					}
					vTaskDelay(2);
					wait_cnt++;
					if (wait_cnt == 50)
					{
						wait_cnt = 0;
						Open_COLOR_L();
					}
				}
				flag = 0;
				close_Maxicam();
				pid_mode_switch(is_Line);
				motor_all.Cspeed = nodesr.nowNode.speed;
				nodesr.nowNode.function = NONE;
				//看完头回正
				Robot_Work(HEAD,HEAD_MID);
				return;
			}
		}
	}
		//看完头回正
		Robot_Work(HEAD,HEAD_MID);
}

void update_route_for_stage34(void)
{
	//u8 route[100] = {B1, N1, P1, N1, B2, N4, N5, N6, P4, N6, N5, N12, 0XFF};
	if(line_clue == 3)
	{
		u8 route_to_2[15] = {B1, N1, P1, N1, B2, N4, N3, P3, N3, N4, N5, N12, 0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_2[i];
			if(route_to_2[i]==0xff)
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
		u8 route_to_3[15] = {N8,N3,P3,N3,N4,B3,N2,P2,0XFF};
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
		u8 route_to_4[15] = {N8,N3,N4,N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF};
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
		u8 route_to_2[15] = {N8,N3,N4,B2,N1,P1,N1,B1,N2,P2,0XFF};
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
		u8 route_to_3[15] = {N5,N4,N3,P3,N3,N4,B3,N2,P2,0XFF};
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
		u8 route_to_4[15] = {N5,N6,P4,N6,N5,N4,B3,N2,P2,0XFF};
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
		u8 route_to_2[15] = {N5,N4,B2,N1,P1,N1,B1,N2,P2,0XFF};
		for(uint8_t i = 0;i<15;i++)
		{
			route[i] = route_to_2[i];
			if(route_to_2[i]==0xff)
				break;
		}
	}
}
void update_route_by_QR(void)
{
	//若线索在57号平台
	if (clue_A_stage == 5&&clue_B_stage == 7)
	{  
		if(color_flag[1] == Green || color_flag[1] == Yellow||color_flag[2] == Green || color_flag[2] == Yellow)
		{
			route [0] = N12;////////////////////N12
			for(uint8_t i = 1;i<50;i++)
		   {
			route[i] = rout_57[i-1];
			if(rout_57[i-1]==0xff)
				break;
		   }
		}
	    if(color_flag[0] == Green|| color_flag[0] == Yellow)
		{
			for(uint8_t i = 0;i<50;i++)
			 {
				route[i] = rout_57[i];
				if(rout_57[i]==0xff)
					break;
			  }
		 }
	}							
	//若线索在58号平台
	if (clue_A_stage == 5&&clue_B_stage == 8)
	{
		if(color_flag[1] == Green || color_flag[1] == Yellow||color_flag[2] == Green || color_flag[2] == Yellow)
		{
			route [0] = N12;
			for(uint8_t i = 1;i<50;i++)
		   {
			route[i] = rout_58[i-1];
			if(rout_58[i-1]==0xff)
				break;
		   }
		}
	    if(color_flag[0] == Green|| color_flag[0] == Yellow)
		{
			for(uint8_t i = 0;i<50;i++)
			 {
				route[i] = rout_58[i];
				if(rout_58[i]==0xff)
					break;
			  }
		 }
	}
	//若线索在67号平台
	if (clue_A_stage == 6&&clue_B_stage == 7)
	{
		if(color_flag[1] == Green || color_flag[1] == Yellow||color_flag[2] == Green || color_flag[2] == Yellow)
		{
			route[0] = N10;
			for(uint8_t i = 1;i<50;i++)
		   {
			route[i] = rout_67[i-1];
			if(rout_67[i-1]==0xff)
				break;
		   }
		}
	    if(color_flag[0] == Green|| color_flag[0] == Yellow)
		{
			route[0] = N11;
			route[1] = N10;
			for(uint8_t i = 2;i<50;i++)
			 {
				route[i] = rout_67[i-2];
				if(rout_67[i-2]==0xff)
					break;
			  }
		 }
	}
	//若线索在68号平台
	if (clue_A_stage == 6&&clue_B_stage == 8)
	{
		if(color_flag[1] == Green || color_flag[1] == Yellow||color_flag[2] == Green || color_flag[2] == Yellow)
		{
			route[0] = N10;
			for(uint8_t i = 1;i<50;i++)
		   {
			route[i] = rout_68[i-1];
			if(rout_68[i-1]==0xff)
				break;
		   }
		}
	    if(color_flag[0] == Green|| color_flag[0] == Yellow)
		{
			route[0] = N11;
			route[1] = N10;
			for(uint8_t i = 2;i<50;i++)
			 {
				route[i] = rout_68[i-2];
				if(rout_68[i-2]==0xff)
					break;
			  }
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
		clue_A = Clue_Num;
		K210_Rece = 0;
		if (clue_A == 0)
			send_play_specified_command(29);
		else
			send_play_specified_command(22+clue_A);
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
		clue_B = Clue_Num;
		K210_Rece = 0;
		send_play_specified_command(16+clue_B);
//		for(uint8_t i = 0;i<clue_B;i++)
//		{
//			buzzer_on();
//			vTaskDelay(500);
//			buzzer_off();
//			vTaskDelay(500);
//		}
		treasure = clue_A+clue_B;//获取宝物平台位置
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
//		clue_A_stage = (QR_code/10)%10;//获取十位上的数字
//		clue_B_stage = QR_code%10;//获取个位上数字
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

	/*机器人动作*/
	Robot_Work(BODY, UP); 	//人站起来
	vTaskDelay(1000);
	Robot_Work(PIG, HEAD_LEFT); //转头
	vTaskDelay(500);		
	Robot_Work(PIG, HEAD_RIGHT); 	
	vTaskDelay(500);
	/*蜂鸣器提示初始化完成 - 调试用*/
	buzzer_on();
	
	// i = HAL_GPIO_ReadPin(GPIOC,GPIO_PIN_13);
	vTaskDelay(100);
	buzzer_off();

	close_Maxicam();
	IMU_CalibrateZero(&basic_y,&basic_p);
	vTaskDelay(100);
	mpuZreset(get_latest_yaw(), nodesr.nowNode.angle); // 用稳定后的实际角度计算补偿
	
	/*等待挡板*/
	while (Infrared_ahead == 0)
		vTaskDelay(5);

	/*等待移除挡板*/
	while(Infrared_ahead == 1)
		vTaskDelay(5);
//	HAL_ADC_Start(&hadc1);
//	if (HAL_ADC_Start_DMA(&hadc1, (uint32_t *)AD_Value, 4) != HAL_OK)
//	{
//		printf("ADC DMA Start Failed!\r\n");
//	}else
//	{
//		printf("ADC DMA Started\r\n");
//	}
//	line_pid_param.kp = 50.0;//50.0
//	line_pid_param.ki = 0;
//	line_pid_param.kd = 200;
//	ScanerMode_Switch(Gray);
//	vTaskDelay(5);
//	Chassis_MotorControl(is_Line, 12, 12, 0);//12 12
//	Want2Go(100);

	
	/**************转弯测试***************/
	/*播报语音*/
	send_play_specified_command(7);
	
#if DEBUG
	//printf("ADC2:%lu\r\n",AD_Value_Gray[0]);
	//printf("ADC3:%lu\r\n",AD_Value_Gray[1]);
	//printf("ADC14:%lu\r\n",AD_Value_Gray[2]);
	//printf("ADC15:%lu\r\n",AD_Value_Gray[3]);
	//printf("detail:%d\r\n",Scaner.detail_gray);
	//printf("error:%f\r\n",Scaner.gray_error);
	//printf("\r\n");
//	motor_all.Cincrement = 0.9;
//	motor_all.CDOWNincrement = 0.75;
		line_pid_param.kp = 6.0;
		line_pid_param.ki = 0;
		line_pid_param.kd = 260;
	Chassis_MotorControl(is_Line, SPEED4, SPEED4, 0);
	Want2Go(200);

	Chassis_ClearMileage();
	Chassis_MotorControl(is_Line, SPEED1, SPEED1, 0);
	Want2Go(200);
//	line_pid_param.kp = 12;
//	line_pid_param.ki = 0;
//	line_pid_param.kd = 400;
	
	while(1)
		vTaskDelay(5);
	
#endif	

	
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
		Chassis_MotorControl(is_Gyro, Rubbish_Speed, Rubbish_Speed, getAngleZ()); // 设置自平衡及其速度

		LiuShuiRate = LiuShuiRate_BG;
		DownLiuShui = 1;
		/*等待开始下桥*/
		//打印
		printf("Waiting to start bridge crossing\n");
		while (imu.pitch > Down_pitch)	
			vTaskDelay(2);
		/*正在下桥*/
		while (imu.pitch < After_down)
			vTaskDelay(2);
		/*下桥完毕*/
		printf("Finished crossing the bridge\n");
		DownLiuShui = 0;
		LiuShuiRate = LiuShuiRate_Default;
	}
	send_play_specified_command(7);
}

///*保护机制*/
//void Protect(float angle1)
//{
//	int num = 0;
//	int breaktime = 0;
//	char oriT = motor_all.GyroT_speedMax;
//	struct PID_param origin_param = gyroT_pid_param;
//	gyroT_pid_param.kp = 0.5;			// 0.65
//	gyroT_pid_param.ki = 0.0003 /*66*/; // 0.0005
//	gyroT_pid_param.kd = 0;
//	motor_all.GyroT_speedMax = 10;
//	buzzer_on();

//	CarBrake();
//	vTaskDelay(200);

//	Chassis_ClearMileage();
//	pid_mode_switch(is_No);
//	motor_all.Lspeed = motor_all.Rspeed = -8;
//	while (fabsf(motor_all.Distance - num) < 5) // 10
//	{
//		vTaskDelay(2);
//	}

//	CarBrake();
//	vTaskDelay(300);

//	// 保护矫正
//	angle.AngleT = getAngleZ() + angle1;
//	pid_mode_switch(is_Turn);
//	while (fabsf(angle.AngleT - getAngleZ()) > 4)
//	{
//		breaktime++;
//		vTaskDelay(2);
//		if (breaktime >= 500)
//			break;
//	}

//	// 直走
//	pid_mode_switch(is_Gyro);
//	angle.AngleG = getAngleZ();
//	motor_all.Gspeed = 17;

//	motor_all.GyroT_speedMax = oriT;
//	gyroT_pid_param = origin_param;
//	breaktime = 0;
//	buzzer_off();
//}



//void DragonProtection(void) //游龙保护
//{
//		/*游龙判断与保护*/
//			if (nodesr.nowNode.angle != nodesr.lastNode.angle && nodesr.nowNode.nodenum != C4 && nodesr.nowNode.nodenum != P8)
//			{			
//				Cross_getline(&Cross_Scaner);//更新循迹板数据
//				
//				/************* 危险状态检测****************/
//        if (Cross_Scaner.detail & 0xFC3F)  // 0xFC3F = 1111110000111111
//        {
//            ErrorTimes[0]++;       
//            ErrorTimes[1] = 0;     // 安全标志清零
//      
//            
//            //累计5次危险，非常危险
//            if (ErrorTimes[0] >= 5) 
//            {
//           			 motor_all.Cspeed = nodesr.nowNode.speed * 0.67f;//降速
//                 ErrorTimes[0] = 0; 
//            }
//        } 
//				
//				/************* 安全状态检测 ***************/
//			else 
//			{
//				if(Cross_Scaner.detail & 0x0180)
//				{
//					ErrorTimes[1]+=5;
//				}
//				else
//				{
//					ErrorTimes[1]++;
//				}
//				if(ErrorTimes[1]>=20)
//				{
//					if(Cross_Scaner.detail & 0x0180)
//					{
//								angle.AngleG = getAngleZ();
//					}
//					motor_all.Cspeed = nodesr.nowNode.speed;  // 完全恢复速度
//					ErrorTimes[1]=0;
//				}
//			}
//				
//			}
//			
//}


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
