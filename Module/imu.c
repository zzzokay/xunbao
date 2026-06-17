/*
 * @File: imu_task.c
 * @Description: 
 * @Version: 1.0.0
 * @Author: 
 * @Date: 2023-09-13 20:33:36
 * @LastEditTime: 2023-09-15 15:37:05
 */
#include "imu.h"
#include "usart.h"
#include "main.h"
#include "uart.h"
#include "usart.h"
#include "stdio.h"
#include "string.h"
#include "filter.h"
#include "motor_task.h"
#include "bsp_buzzer.h"
#include "delay.h"
struct Imu imu;
struct Imu imu_shared_data;
SemaphoreHandle_t imu_mutex;

UART_HandleTypeDef gyro;//UART句柄
float basic_p = 0;
float basic_y = 0;
float basic_r = 0;

void gyro_init(uint32_t bound)
{ 
 //UART 初始化设置
 gyro.Instance=USART3;         //USART2
 gyro.Init.BaudRate=bound;        //波特率
 gyro.Init.WordLength=UART_WORDLENGTH_8B;   //字长为8位数据格式
 gyro.Init.StopBits=UART_STOPBITS_1;     //一个停止位
 gyro.Init.Parity=UART_PARITY_NONE;      //无奇偶校验位
 gyro.Init.HwFlowCtl=UART_HWCONTROL_NONE;   //无硬件流控
 gyro.Init.Mode=UART_MODE_TX_RX;      //收发模式
 HAL_UART_Init(&gyro);         //HAL_UART_Init()会使能UART3
// __HAL_UART_ENABLE_IT(&gyro, UART_IT_RXNE);
}

#define BUFFER_SIZE 33//15//0-10 11-21 22-32
uint8_t imu_rx_buf[BUFFER_SIZE] = {0};
uint8_t imu_rx_len = 0;
float roll,pitch,yaw;

void imu_receive_init(void)
{
	//陀螺仪互斥量创建
	imu_mutex = xSemaphoreCreateMutex();
	if (imu_mutex == NULL) {
		// 创建失败，系统异常处理
		buzzer_on();
		delay_ms(2000);
	}
	HAL_UART_Receive_DMA(&huart3,imu_rx_buf,BUFFER_SIZE);
	__HAL_UART_ENABLE_IT(&huart3, UART_IT_IDLE);

}

void USART3_IRQHandler(void)
{
	uint32_t flag_idle = 0;
	
	flag_idle = __HAL_UART_GET_FLAG(&huart3,UART_FLAG_IDLE); 
	if((flag_idle != RESET))
	{ 
		__HAL_UART_CLEAR_IDLEFLAG(&huart3);

		HAL_UART_DMAStop(&huart3); 
		uint32_t temp = __HAL_DMA_GET_COUNTER(&hdma_usart3_rx);   
		imu_rx_len = BUFFER_SIZE - temp; 
	
		if(imu_rx_buf[0] == 0x55)
		{
			uint8_t sum = 0;
			for (int i=0; i<10; i++)
				sum += imu_rx_buf[i];
			if (sum == imu_rx_buf[10])
			{
				if (imu_rx_buf[2] == 0X01)
				{
					imu.roll   =  180.0 * (short) ((imu_rx_buf[5]<<8)|imu_rx_buf[4])/32768.0; 					
					imu.yaw    =  180.0 * (short) ((imu_rx_buf[9]<<8)|imu_rx_buf[8])/32768.0;
					imu.pitch  =  -180.0 * (short) ((imu_rx_buf[7]<<8)|imu_rx_buf[6])/32768.0;//上下(正为上)

					imu.yaw -= basic_y;
					
					if (filter_Open)
					{
						imu.pitch  = filter(imu.pitch);
						imu.roll   = filter(imu.roll);
						imu.yaw    = filter(imu.yaw);
					}
					// 临界区写入共享数据
					BaseType_t xHigherPriorityTaskWoken = pdFALSE;
					if (imu_mutex != NULL) {
						if (xSemaphoreTakeFromISR(imu_mutex, &xHigherPriorityTaskWoken) == pdTRUE) {//从 ISR（中断服务程序）中尝试“获取”这个互斥锁
							imu_shared_data = imu;
							xSemaphoreGiveFromISR(imu_mutex, &xHigherPriorityTaskWoken);//xSemaphoreGiveFromISR() 中把 xHigherPriorityTaskWoken 设置为了 pdTRUE
							                                                            //如果有任务阻塞在等这个锁，那现在它可以被唤醒了
						}
						portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
					}
					
				}
			}
		}
		memset(imu_rx_buf,0,imu_rx_len);
		imu_rx_len = 0;
	}
	HAL_UART_Receive_DMA(&huart3,imu_rx_buf,BUFFER_SIZE);
	HAL_UART_IRQHandler(&huart3);
}


void IMU_CalibrateZero(float* yaw_out, float* pitch_out, float* roll_out)
{
    float sum_yaw = 0;
    float sum_pitch = 0;
    float sum_roll = 0;
    struct Imu imu_copy;

    for (uint8_t i = 0; i < 10; i++)
    {
        vTaskDelay(pdMS_TO_TICKS(20));

        if (imu_mutex != NULL && xSemaphoreTake(imu_mutex, portMAX_DELAY) == pdTRUE)
        {
            imu_copy = imu_shared_data;
            xSemaphoreGive(imu_mutex);
        }
        else
        {
            continue; // 获取失败则跳过该次
        }

        sum_yaw   += imu_copy.yaw;
        sum_pitch += imu_copy.pitch;
        sum_roll  += imu_copy.roll;
    }

    float avg_yaw   = sum_yaw / 10.0f;
    float avg_pitch = sum_pitch / 10.0f;
    float avg_roll  = sum_roll / 10.0f;

    if (yaw_out)   *yaw_out   = avg_yaw;
    if (pitch_out) *pitch_out = avg_pitch;
    if (roll_out)  *roll_out  = avg_roll;

}
// 新增一个获取最新yaw的函数，封装锁逻辑
float get_latest_yaw(void)
{
    struct Imu temp;

    if (imu_mutex != NULL) {
        /*阻塞等待锁（中断仅持有几微秒，代价可忽略）*/
        xSemaphoreTake(imu_mutex, portMAX_DELAY);
        temp = imu_shared_data;
        xSemaphoreGive(imu_mutex);
        return temp.yaw;
    }
    return 0;
}
/*原中断*/
//void USART3_IRQHandler(void)
//{
//	uint32_t flag_idle = 0;
//	
//	flag_idle = __HAL_UART_GET_FLAG(&huart3,UART_FLAG_IDLE); 
//	if((flag_idle != RESET))
//	{ 
//		__HAL_UART_CLEAR_IDLEFLAG(&huart3);

//		HAL_UART_DMAStop(&huart3); 
//		uint32_t temp = __HAL_DMA_GET_COUNTER(&hdma_usart3_rx);   
//		imu_rx_len = BUFFER_SIZE - temp; 
//	
////	if(imu_rx_buf[0] == 0x55 && imu_rx_buf[1] == 0x51)
////	{
////		memset(imu_rx_buf,0,imu_rx_len);
////		imu_rx_len = 0;
////	}
////	else if(imu_rx_buf[0] == 0x55 && imu_rx_buf[1] == 0x52)
////	{
////		memset(imu_rx_buf,0,imu_rx_len);
////		imu_rx_len = 0;
////	}
//		if(imu_rx_buf[22] == 0x55)
//		{
//			uint8_t sum = 0;
//			for (int i=22; i<33; i++)
//				sum += imu_rx_buf[i];
////			if (sum == imu_rx_buf[32])
////			{
//				if (imu_rx_buf[23] == 0X53)
//				{
//					imu.roll   = 180.0 * (short) ((imu_rx_buf[25]<<8)|imu_rx_buf[24])/32768.0;  
//					imu.pitch  = 180.0 * (short) ((imu_rx_buf[27]<<8)|imu_rx_buf[26])/32768.0;//上下(正为上)
//					imu.yaw    = 180.0 * (short) ((imu_rx_buf[29]<<8)|imu_rx_buf[28])/32768.0;
//					if(filter_Open)
//					{
//						imu.pitch  = filter(imu.pitch);
//						imu.roll   = filter(imu.roll);
//						imu.yaw    = filter(imu.yaw);
//					}
////					printf("roll=%f,pitch=%f,yaw=%f \r\n",imu.roll,imu.pitch,imu.yaw);
//				}
////			}
//		}
//		memset(imu_rx_buf,0,imu_rx_len);
//		imu_rx_len = 0;
//	}
//	HAL_UART_Receive_DMA(&huart3,imu_rx_buf,BUFFER_SIZE);
//	HAL_UART_IRQHandler(&huart3);
//}
