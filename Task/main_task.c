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
#include "ArriveDetect_task.h"


/*===== 独立调试开关 =====*/
#define MAIN_DEBUG 0 

													   
uint8_t test_flag = 3;
float temp_speed=25;



#if MAIN_DEBUG
static void voice_test_all(void)
{
	for (uint8_t i = 1; i <= 33; i++)
	{
		send_play_specified_command(i);
		vTaskDelay(2000);
	}
}

#endif                          

/*主任务*/
void main_task(void *pvParameters)
{
	portTickType xLastWakeTime;
	xLastWakeTime = xTaskGetTickCount();

#if MAIN_DEBUG
	Chassis_MotorControl(is_No, 0, 0, 0);
	/*调试模式：跳过传感器初始化，只做基本的地图加载*/
	IMU_Calibrate_Yaw(0);
	
	/*等待挡板*/                           
	while (Infrared_ahead == 0)
	vTaskDelay(5);

	/*等待移除挡板*/
	while(Infrared_ahead == 1)
		vTaskDelay(5);
	//voice_test_all(); // 依次播报 1-33，检查语音卡
	//ScanerMode_Switch(Gray);
#else
	/*正常模式：完整初始化流程*/
	
	mapInit();
	IMU_Calibrate_Yaw(0);
	zhunbei(); // 启动流程（红外等待）
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
			Chassis_DriveDistance_Blocking(is_Line, 40, 20, 0, 0);
			CarBrake();
			test_flag = 0;
		}
		if (test_flag == 2)
		{
			//Chassis_OverrideTurnPid(6.0f, 0.0f, 90.0f, 30.0f);
			//Chassis_MotorControl(is_No,2,-2,0);
			//vTaskDelay(3000);
			//Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+180, getAngleZ()); 
			//Chassis_RestoreTurnPid();
			//Chassis_DriveDistance_Blocking(is_Gyro, 20, Gyro_Speed, getAngleZ(), 0);
            //Chassis_Turn_By_Gyro_Blocking(getAngleZ()+90, getAngleZ());
			CarBrake();
			//Chassis_Brake();
			test_flag = 0;
		}
		if (test_flag == 3)
		{
			//Barrier_Hill();
			//Sword_Mountain();
			Chassis_Turn_By_StopGyro_Blocking(getAngleZ()-160, getAngleZ(), 20.0f);
			Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
			QQB_1();
			//Barrier_HighMountain();
			CarBrake();
			test_flag = 0;
		}
		if(test_flag == 4)
		{
			// Gray_GetLine();
			// float correct_angle = Gray_GetCorrectAngle(1);
			// printf(" %.2f\n", correct_angle);
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
