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

/*主任务*/
void main_task(void *pvParameters)
{
	portTickType xLastWakeTime;
	xLastWakeTime = xTaskGetTickCount();   //获取系统节拍、
//	zhunbei(); // 启动流程//注意有挡板 会卡在这
	encoder_clear(); // 路程记录清零
//	Motor_Control(is_Line, SPEED0, SPEED0, 0);
	
	
	uint8_t test_flag =1;
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
		
		
 		if(test_flag)
 		{
			Chassis_DriveDistance_Blocking(is_Line,20,20,0,0);
			Chassis_SetTargetSpeed(0);
			vTaskDelay(500);
			Chassis_Brake();
 			test_flag=0;

		}			
//		/*节点间处理*/
//		Cross();
//		
//		/*二轮结束处理*/
//		if(map.routetime==3)
//			CarBrake_Stop();
	
		
		
		vTaskDelayUntil(&xLastWakeTime, (5/portTICK_RATE_MS));//绝对休眠5ms // INCLUDE_vTaskDelayUntil 1
	}
}
