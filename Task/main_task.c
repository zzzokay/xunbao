#include "main_task.h"
#include "rudder_control.h"
#include "uart.h"
#include "imu.h"
#include "uart.h"
#include "turn.h"
#include "map.h"
#include "barrier.h"
#include "bsp_buzzer.h"
#include "bsp_linefollower.h"
#include "scaner.h"
#include "speed_ctrl.h"
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
uint8_t test_flag =0;
float temp_speed=25;
/*主任务*/
void main_task(void *pvParameters)
{
	portTickType xLastWakeTime;
	xLastWakeTime = xTaskGetTickCount();   //获取系统节拍、
	mapInit();
	zhunbei(); // 启动流程//注意有挡板 会卡在这
	Chassis_MotorControl(is_Line, SPEED0, SPEED0, 0);
	printf("Preparation complete, waiting for start signal...\n");
	//IMU_CalibrateZero(&basic_y,&basic_p);
	//vTaskDelay(100);
	//mpuZreset(get_latest_yaw(), nodesr.nowNode.angle); 
	//vTaskDelay(1000);
	
	
	while (1)
	{

		// /*二轮处理*/
		// if(map.routetime == 1)
		// {
		// 	map.routetime = 2;
		// 	get_newroute();

		// 	// 陀螺仪角度复位，采样10次取平均值
		// 	IMU_CalibrateZero(&basic_y,&basic_p);
		// 	mpuZreset(basic_y, nodesr.nowNode.angle); // 把此时角度变为此结点角度
		// 	zhunbei();

		// 	encoder_clear(); // 路程记录清零
		// 	Motor_Control(is_Line, SPEED0, SPEED0, 0);
		// }
		
		
 		if(test_flag==1)
 		{
			     
			// Chassis_EnableLineLostProtection();
			// Chassis_SetTrackMode(TRACK_LIUSHUI);
			// ////直线循迹
			// Chassis_DriveDistance_Blocking(is_Line,200,temp_speed,0,0);
			// Chassis_Brake();
 			
			//Chassis_DriveDistance_Blocking(is_Gyro,2,-12,getAngleZ(),0);
			//CarBrake();
			//Chassis_Brake();
			////偏左循迹
			// Chassis_SetTrackMode(TRACK_LEFT_EDGE);
			// Chassis_DriveDistance_Blocking(is_Line,50,25,0,0);
			// Chassis_Brake();
			
			
			////偏右循迹
			// Chassis_SetTrackMode(TRACK_RIGHT_EDGE);
			// Chassis_DriveDistance_Blocking(is_Line,50,25,0,0);
			// Chassis_Brake();
		

			////流水循迹
			 
			// Chassis_DriveDistance_Blocking(is_Line,50,25,0,0);
			// Chassis_Brake();
		
			
			////固定角度直行
			//Chassis_DriveDistance_Blocking(is_Gyro,100,20,getAngleZ(),0);
			// Chassis_SetMode(is_Gyro);
			// Chassis_SetGyroAngle_Go(getAngleZ());
			// Chassis_SetTargetSpeed(25);
			// vTaskDelay(5000);
			// Chassis_Brake();


			////固定角度转弯			 
			//Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+90, getAngleZ());
			
			
			////循迹转向
			//Chassis_SetMode(is_Gyro);
			//Chassis_SetTargetSpeed(15);
			//Chassis_Turn_By_Gyro_Blocking(getAngleZ()+90, getAngleZ());
			//Chassis_Brake();
			//Turn_Angle360();
			test_flag=0;
		}			
		if(test_flag==2)
		{
			//转180度
			Chassis_Turn_By_StopGyro_Blocking(getAngleZ()+180, getAngleZ());
			Chassis_Brake();
			test_flag=0;
		}
		if(test_flag==3)
		{
		//过桥
		Barrier_Bridge();
		test_flag=0;
		}
		
//		/*节点间处理*/
		if(map.routetime == 0)
			Cross();
//		
//		/*二轮结束处理*/
//		if(map.routetime==3)
//			CarBrake_Stop();
	
		
		
		vTaskDelayUntil(&xLastWakeTime, (5/portTICK_RATE_MS));//绝对休眠5ms // INCLUDE_vTaskDelayUntil 1
	}
}
