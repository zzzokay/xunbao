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


/*===== 独立调试开关 =====*/
#define MAIN_DEBUG 0


uint8_t test_flag = 6;
float temp_speed=25;
#if MAIN_DEBUG


#endif                          

/*主任务*/
void main_task(void *pvParameters)
{
	portTickType xLastWakeTime;
	xLastWakeTime = xTaskGetTickCount();

#if MAIN_DEBUG
	Chassis_MotorControl(is_No, 0, 0, 0);
	/*调试模式：跳过传感器初始化，只做基本的地图加载*/
	IMU_CalibrateZero(&basic_y, &basic_p, &basic_r);
	vTaskDelay(100);
	mpuZreset(get_latest_yaw(), nodesr.nowNode.angle); // 用稳定后的实际角度计算补偿
	
	/*等待挡板*/
	while (Infrared_ahead == 0)
		vTaskDelay(5);

	/*等待移除挡板*/
	while(Infrared_ahead == 1)
		vTaskDelay(5);
	ScanerMode_Switch(Gray);
#else
	/*正常模式：完整初始化流程*/
	mapInit();
	zhunbei(); // 启动流程（红外等待、IMU校准）
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
			Chassis_DriveDistance_Blocking(is_Line,100,-36,0,0);
			CarBrake();
			test_flag = 0;
		}
		if (test_flag == 2)
		{
			Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+180, getAngleZ());
			Chassis_Brake();
			test_flag = 0;
		}
		if (test_flag == 3)
		{
			//Barrier_Hill();
			//Sword_Mountain();
			QQB_1();
			CarBrake();
			test_flag = 0;
		}
		if(test_flag == 4)
		{
			// Gray_GetLine();
			// float correct_angle = Gray_GetCorrectAngle(1);
			// printf(" %.2f\n", correct_angle);
			RampCtrl_Blocking(RAMP_ASCEND, UpDownStage_Speed_low, getAngleZ(),
				basic_p+5, UpDownStage_Speed_low, basic_p+15, UpDownStage_Speed_low, basic_p+5, 0.09,10);
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
		/*调试模式下不执行 Cross()，避免无传感器跑飞*/
#else
		/*========== 正常运行模式 ==========*/

		/*二轮处理*/
//		if(map.routetime == 1)
//		{
//			map.routetime = 2;
//			get_newroute();

//			// 陀螺仪角度复位，采样10次取平均值
//			IMU_CalibrateZero(&basic_y, &basic_p, &basic_r);
//			mpuZreset(basic_y, nodesr.nowNode.angle); // 把此时角度变为此结点角度
//			zhunbei();

//			encoder_clear(); // 路程记录清零
//			Motor_Control(is_Line, SPEED0, SPEED0, 0);
//		}

		if(map.routetime == 0)
			Cross();
#endif

		vTaskDelayUntil(&xLastWakeTime, (5/portTICK_RATE_MS));
	}
}
