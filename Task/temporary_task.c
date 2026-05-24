#include "temporary_task.h"
#include "task_create.h"
#include "delay.h"
#include "pid.h"
#include "motor.h"
#include "motor_task.h"
#include "encoder.h"
#include "uart.h"
#include "rudder_control.h"
#include "imu.h"
#include "bsp_led.h"
#include "turn.h"
#include "map.h"
#include "openmv.h"
#include "QR.h"
#include "K210.h"
#include "Gray.h"
#include "FreeRTOS.h"
#include "task.h"
#include "Rec_usart.h"

/*开始任务*/
void Start_task(void *pvParameters)
{	
	user_init();

	taskENTER_CRITICAL(); // 进入临界区
   
	Rec_usart_init();	
	main_task_create(); // 创建主控任务
	motor_task_create();
	create_ArriveDetect_task();//检测结点任务！！不可以挂起suspend	
	
	vTaskDelete(Start_handler); // 删除开始任务

	taskEXIT_CRITICAL();		// 退出临界区
}

/*****************************************************************************
函数名： GET_free_RAM
函数功能：获得任务的剩余堆栈大小 并且打印
形参：该任务的句柄      若传回NULL，则为该任务的堆栈
注意：INCLUDE_uxTaskGetStackHighWaterMark 1    才能使用
*******************************************************************************/
void GET_free_RAM(TaskHandle_t xTask)
{
	printf("RAM = %d\r\n",(int32_t)uxTaskGetStackHighWaterMark(xTask));
	vTaskDelay(500);
}

/*初始化外设，结构体等*/
void user_init(void)
{
//	uart_init(115200); // 初始化重定向串口
	Encoder_init();
//	IIC_Init();
	//Gray_Init();
//	Rudder_Init(9600); // 舵机初始化
	Maxicam_Enable();
	imu_receive_init();
	motor_init();
	
	vTaskDelay(2000);

}
