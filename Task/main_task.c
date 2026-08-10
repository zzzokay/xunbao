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
#define MAIN_DEBUG 0


uint8_t test_flag = 1; //调试模式选择：0=关闭，1=循迹测试，2=陀螺测试，3=障碍物测试，4=坡道测试，5=红外测试，6=灰度测试，7=十字路口测试，8=一键自检，9=机器人动作测试
float temp_speed=25;
#if MAIN_DEBUG
/*地图初始化*/
#endif

/*主任务*/
void main_task(void *pvParameters)
{
	portTickType xLastWakeTime;
	xLastWakeTime = xTaskGetTickCount();

#if MAIN_DEBUG
	/*调试模式：跳过传感器初始化，只做基本的地图加载*/
	IMU_CalibrateZero(&basic_y, &basic_p, &basic_r);
	vTaskDelay(100);
	mpuZreset(get_latest_yaw(), nodes.nowNode.angle); // 用稳定后的实际角度计算补偿
	/*等待挡板*/
	if (test_flag != 10 && test_flag != 11 && test_flag != 12 && test_flag != 8 && test_flag != 1)
	{
		while (Infrared_ahead == 0)
			vTaskDelay(5);

		while (Infrared_ahead == 1)
			vTaskDelay(5);
	}
	//send_play_specified_command(7);
#else
	/*正常模式：完整初始化流程*/
	mapInit();
	IMU_CalibrateZero(&basic_y, &basic_p, &basic_r);
	vTaskDelay(100);
	mpuZreset(get_latest_yaw(), nodes.nowNode.angle); // 用稳定后的实际角度计算补偿
 	#if MAP_DEBUG
	#else
	zhunbei(); // 启动流程（红外等待）
 	#endif
	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
#endif

	while (1)
	{

#if MAIN_DEBUG
		/*========== 调试模式：debug_test_item 控制 ==========*/
		if (test_flag == 1)
		{

			//ScanerMode_Switch(RF);
			Chassis_SetTrackMode(TRACK_NEAR_CENTER);
			//Chassis_DriveDistance_Blocking(is_Line,100,20,0,0);
			Chassis_DriveDistance_Blocking(is_Line, 200, 20, 0, 0);
			
			//Chassis_DriveDistance_Blocking(is_Gyro, 200, 36, 0, 0);
			Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+180, getAngleZ(),20.0f);
			CarBrake();
		}
		if (test_flag == 2)
		{
			//Chassis_OverrideTurnPid(6.0f, 0.0f, 90.0f, 30.0f);
			//Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+180, getAngleZ());
			//Chassis_RestoreTurnPid();
			//Chassis_DriveDistance_Blocking(is_Gyro, 20, Gyro_Speed, getAngleZ(), 0);
            //Chassis_Turn_By_Gyro_Blocking(getAngleZ()+90, getAngleZ());
			CarBrake();
			test_flag = 0;
		}
		if (test_flag == 3)
		{
			Barrier_Hill();
			//Sword_Mountain();
			//Chassis_Turn_By_StopGyro_Blocking(getAngleZ()-160, getAngleZ(), 20.0f);
			//Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
			//QQB_1();
			//Barrier_HighMountain();
			CarBrake();
			test_flag = 0;
		}
		if(test_flag == 4)
		{
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, getAngleZ(),
				basic_p+5, UpDownStage_Speed_low, basic_p+15, UpDownStage_Speed_low, basic_p+5, 0.09,10,0);
		}
		if(test_flag == 5)
		{
			get_Infrared();
		}
		if(test_flag == 6)//灰度测试
		{
			Gray_GetLine();
		}
		if(test_flag == 7)
		{
			Cross_getline(&Cross_Scaner);
		}
		if(test_flag == 8)
		{
			/* 一键自检：架车在黑毯上持续监测（每1秒检测，状态变化才打印） */
			Chassis_SelfCheck();
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
		}
		if(test_flag == 11)//测试摄像头数字
		{
			uint8_t ocr_ok;

			/* WaitFor_OCR只接收QR指定平台的数据，这里模拟到达P5 */
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
			uint8_t qr_ok;
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
		/*调试模式下不执行 Navigation()，避免无传感器跑飞*/
#else
		/*========== 正常运行模式 ==========*/

		/*二轮处理*/
		if(map.routetime == 1)
		{
			map.routetime ++;
			get_newroute();
			zhunbei();
		}

		if(map.routetime == 0||map.routetime == 2)
			Navigation();
#endif
		vTaskDelayUntil(&xLastWakeTime, (5/portTICK_RATE_MS));
	}
}
