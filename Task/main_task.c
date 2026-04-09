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

		/*二轮处理*/
		if(map.routetime == 1)
		{
			map.routetime = 2;
			get_newroute();

			// 陀螺仪角度复位，采样10次取平均值
			IMU_CalibrateZero(&basic_y,&basic_p);
			mpuZreset(basic_y, nodesr.nowNode.angle); // 把此时角度变为此结点角度
			zhunbei();

			encoder_clear(); // 路程记录清零
			Motor_Control(is_Line, SPEED0, SPEED0, 0);
		}
		
		
		if(1)
		{
			motor_all.Cincrement = 0.05;
			pid_mode_switch(is_Line);
			motor_all.Cspeed = 10;
			MOTOR_PWM_MAX = 7000;
			test_flag=0;
//			LEFT_RIGHT_LINE=1; 
			
//		motor_set_pwm(4, 1000);  // 右后轮
//		motor_set_pwm(1, 1000);  // 左前轮
//		motor_set_pwm(2, 1000);  // 左后轮
//		motor_set_pwm(3, 1000);  // 右前轮

//		TIM12->CCR1 = 0; TIM12->CCR2 = 1000;
//			motor_set_pwm_R0(4,1000);
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
