#include "main_task.h"
#include "uart.h"
#include "imu.h"
#include "uart.h"
#include "turn.h"
#include "map.h"
#include "barrier.h"
#include "bsp_buzzer.h"
#include "bsp_linefollower.h"
#include "scaner.h"
#include "encoder.h"
#include "barrier.h"
#include "motor_task.h"
#include "openmv.h"
#include "math.h"
#include "barrier.h"
#include "sin_generate.h"
#include "gray.h"
#include "QR.h"
#include "K210.h"
#include "scaner.h"
#include "motor.h"
#include "chassis_api.h"
#include "Rudder_control.h"

/*===== 独立调试开关 =====*/
#define MAIN_DEBUG 1


uint8_t test_flag = 1; //调试模式选择：0=关闭，1=循迹测试，2=陀螺测试，3=障碍物测试，4=坡道测试，5=红外测试，6=灰度测试，7=十字路口测试，8=一键自检，9=机器人动作测试
float temp_speed=25;
#if MAIN_DEBUG
/*地图初始化*/
void mapInit13()
{   
	map = (struct Map_State){0,0};
    nodes = (Nodes){0};	
	cross_event = 0;       //起始点
    nodes.nowNode = Node[getNextConnectNode(N13, P5)];  //起始目标点
	nodes.nextNode.nodenum = 0xff;
}
#endif

/*===== 周期耗时测量(调试用): DWT 周期计数器 @216MHz =====*/
static void timing_dwt_init(void)
{
	CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk; // 使能 TRACE 才能访问 DWT
	DWT->LAR = 0xC5ACCE55;                          // 解锁 DWT（Cortex-M7 软件写被锁，缺此行则 CYCCNT 恒为 0）
	DWT->CYCCNT = 0;
	DWT->CTRL  |= DWT_CTRL_CYCCNTENA_Msk;           // 使能周期计数器
}

/*主任务*/
void main_task(void *pvParameters)
{
	portTickType xLastWakeTime;
	xLastWakeTime = xTaskGetTickCount();
	timing_dwt_init();   // 周期耗时测量: 开启 DWT 周期计数器

#if MAIN_DEBUG
	/*调试模式：跳过传感器初始化，只做基本的地图加载*/
	mapInit13();
	IMU_CalibrateZero(&basic_y, &basic_p, &basic_r);
	vTaskDelay(100);
	mpuZreset(get_latest_yaw(), nodes.nowNode.angle); // 用稳定后的实际角度计算补偿

	/*等待挡板*/
	if (test_flag != 10 && test_flag != 11 && test_flag != 12 && test_flag != 8 )
	{
		while (Infrared_ahead == 0)
			vTaskDelay(5);

		while (Infrared_ahead == 1)
			vTaskDelay(5);
	}
	//ScanerMode_Switch(Gray);
#else
	/*正常模式：完整初始化流程*/
	mapInit();
	IMU_CalibrateZero(&basic_y, &basic_p, &basic_r);
	vTaskDelay(100);
	mpuZreset(get_latest_yaw(), nodes.nowNode.angle); // 用稳定后的实际角度计算补偿
	#if SKIP_ROUND1
	/* 跳过第一轮直接进第二轮：预设门状态（决定 get_newroute() 选哪条二轮路线）+
	   置 routetime=1，让首个主循环周期走"二轮处理"分支（get_newroute()+zhunbei()） */
	door_pass[0] = CAN_PASS; /* D2 */
	door_pass[1] = NO_PASS;  /* D3 */
	door_pass[2] = NO_PASS;  /* D4 */
	door_pass[3] = NO_PASS;  /* D5 */
	door_pass[4] = NO_PASS;  /* D1 */
	treasure = 5; /* 预设宝物平台编号 = 5 */
	map.routetime = 1;
	#elif !MAP_DEBUG
	zhunbei(); // 启动流程（红外等待）
	#else
		while (Infrared_ahead == 0)
			vTaskDelay(5);

		while (Infrared_ahead == 1)
			vTaskDelay(5);
	#endif
	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
#endif

	while (1)
	{
		uint32_t cyc_t0 = DWT->CYCCNT;   // 本周期起点(用于测主任务耗时)

#if MAIN_DEBUG
		/*========== 调试模式：debug_test_item 控制 ==========*/
		if (test_flag == 1)
		{

			//ScanerMode_Switch(RF);
			Chassis_SetTrackMode(TRACK_NEAR_CENTER);
			//Chassis_OverrideLinePid(30, 0, 200, 30);
			Chassis_DriveDistance_Blocking(is_No,200,15,0,0);
			//Chassis_DriveDistance_Blocking(is_Line, 360, 15, 0, 0);
			//Chassis_DriveDistance_Blocking(is_Line, 120, 45, 0, 0);
			//Chassis_DriveDistance_Blocking(is_Line, 120, 70, 0, 0);
			//Chassis_DriveDistance_Blocking(is_Line, 120, 45, 0, 0);
			//Chassis_DriveDistance_Blocking(is_Line, 120, 15, 0, 0);  
			//Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+180, getAngleZ(),20.0f);
			//Chassis_MotorControl(is_Line, 20, 20, 0);
			//CarBrake();
			vTaskDelay(2000);
			test_flag=0;
			
		}
		if (test_flag == 2)
		{
			//Chassis_OverrideGyroPid(2,0,10,50);
			//Chassis_OverrideTurnPid(6.0f, 0.0f, 90.0f, 30.0f);
			//Chassis_MotorControl(is_No,2,-2,0);
			//vTaskDelay(3000);
			//Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+180, getAngleZ());
			//Chassis_RestoreTurnPid();
			Chassis_DriveDistance_Blocking(is_Gyro, 60, -SPEED2, getAngleZ(), 0);
			Chassis_Brake();
            //Chassis_Turn_By_Gyro_Blocking(getAngleZ()+90, getAngleZ());
			//CarBrake();
			//Chassis_Brake();
			test_flag = 0;
		}
		if (test_flag == 3)
		{
			//Barrier_Hill();
			//Sword_Mountain();
			//Chassis_Turn_By_StopGyro_Blocking(getAngleZ()-160, getAngleZ(), 20.0f);
			//Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
			//QQB_1();
			//Barrier_HighMountain();
			Stage();
			CarBrake();
			test_flag = 0;
		}
		if(test_flag == 4)
		{
			// Gray_GetLine();
			// float correct_angle = Gray_GetCorrectAngle(1);
			// printf(" %.2f\n", correct_angle);
			Chassis_OverrideGyroPid(7,0,10,50);
			//RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, getAngleZ(),basic_p+5, UpDownStage_Speed_low, basic_p+15, UpDownStage_Speed_low, basic_p+5, 0.03f,10,0);
		}
		if(test_flag == 5)
		{
			get_Infrared();
		}
		if(test_flag == 6)//灰度测试
		{
			Gray_GetLine();
				// Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+90, getAngleZ());
		}
		if(test_flag == 7)
		{
			Cross_getline(&Cross_Scaner);
		}
		if(test_flag == 8)
		{
			/* 一键自检：架车在黑毯上持续监测（每1秒检测，状态变化才打印） */
			Chassis_SelfCheck();
			//vTaskDelay(100);
		}

		if(test_flag == 9)
		{
			Robot_Work(BODY, UP); 	//人站起来
			vTaskDelay(800);
			Robot_Work(LARM, UP);		// 左手举起
			vTaskDelay(100);
			Robot_Work(RARM, UP);		//右手举起
			vTaskDelay(100);


			vTaskDelay(1000);
			Robot_Work(LARM, DOWN);		//左手放下
			vTaskDelay(100);
			Robot_Work(RARM, DOWN);		//右手放下
			vTaskDelay(100);

			Robot_Work(CAMERA, HEAD_RIGHT);		//左手放下
			vTaskDelay(1000);
			Robot_Work(CAMERA, HEAD_LEFT);		//右手放下
			vTaskDelay(1000);
			Robot_Work(CAMERA, HEAD_MID);		//右手放下
			vTaskDelay(1000);
			vTaskDelay(1000);
		}

		if(test_flag == 10)//测试摄像头颜色
		{


			printf("1");
			uint8_t pass_state = Door_ReadPass_Test();
			printf("Door pass state = %d\r\n", pass_state);
			vTaskDelay(1000);

				// test_flag =0;
		}
		if(test_flag == 11)//测试摄像头数字
		{
			uint8_t ocr_ok;

			/* WaitFor_OCR只接收QR指定平台的数据，这里模拟到达P5 */
//				test_flag = 0;              // 只测试一次，防止主循环重复进入
			nodes.nowNode.nodenum = P5;
			flag_clue_stage_A = 5;
			K210_Rece = 0;
			Clue_Num = 0;

			Robot_Work(CAMERA, HEAD_MID);
			vTaskDelay(300);

			printf("OCR test start\r\n");
			ocr_ok = WaitFor_OCR();
			if (ocr_ok == OCR_SCAN_SUCCESS)
				printf("OCR success: clue_A=%d\r\n", flag_clue_A);
			else if (ocr_ok == OCR_SCAN_FAILED)
				printf("OCR timeout or invalid result\r\n");
		}
		
		
		
		if(test_flag == 12)//测试摄像头扫二维码
		{
//			uint8_t cmd = 0x11;  // QR模式指令码
//       		HAL_UART_Transmit(&huart6, &cmd, 1, 100);
//			printf("3");


			uint8_t qr_ok;

			//test_flag = 0;              // 只测试一次，防止主循环重复进入
			get_cude = 0;
			flag_line_clue = 0;
			flag_clue_stage_A = 0;
			flag_clue_stage_B = 0;

			Robot_Work(CAMERA, HEAD_MID);
			vTaskDelay(300);

			printf("QR test start\r\n");
			qr_ok = WaitFor_QR();
			if (qr_ok)
			{
				printf("QR success: line=%d, stageA=%d, stageB=%d\r\n",
					flag_line_clue, flag_clue_stage_A, flag_clue_stage_B);
			}
			else
			{
				printf("QR timeout or invalid result\r\n");
			}
			
			
					vTaskDelay(2000);
	
		}
		if(test_flag == 13)
		{
			Navigation();
		}
		/*调试模式下不执行 Navigation()，避免无传感器跑飞*/
#else
		/*========== 正常运行模式 ==========*/

		/*二轮处理*/
		if(map.routetime == 1)
		{			
			get_newroute();   /* 内部会 mapInit() 把 routetime 清回 0 */
			map.routetime = 2;/* 必须在 get_newroute 之后置：二轮全程 routetime=2，
			                     不触发一轮的 P7/P8 treasure 改路（保留完整巡游），
			                     且二轮跑完 routetime→3 即停，不再重启二轮 */
			zhunbei();
		}

		if(map.routetime == 0||map.routetime == 2)
			Navigation();
#endif

		/*===== 主任务耗时测量(调试用): loop=单周期耗时(含阻塞µs); max=历史最大 =====*/
		// {
		// 	static uint32_t max_us = 0;
		// 	static uint16_t m_cnt = 0;
		// 	uint32_t us = (DWT->CYCCNT - cyc_t0) / 216u;
		// 	if (us > max_us) max_us = us;
		// 	if (++m_cnt >= 100) // 500ms 打印一次
		// 	{
		// 		m_cnt = 0;
		// 		printf("MAIN loop=%luus max=%luus\r\n", (unsigned long)us, (unsigned long)max_us);
		// 	}
		// }

		vTaskDelayUntil(&xLastWakeTime, (5/portTICK_RATE_MS));
	}
}
