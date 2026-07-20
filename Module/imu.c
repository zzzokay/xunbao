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

float basic_p = 0;
float basic_y = 0;
float basic_r = 0;

uint8_t imu_rx_len=0;

//当前imu数据解析 纯靠 串口空闲中断 检测 发送的间断 来区分 每一帧，如果是没有间断的陀螺仪，就不能用此方法
#define BUFFER_SIZE 33//15//0-10 11-21 22-32
uint8_t imu_rx_buf[BUFFER_SIZE] = {0};

void imu_receive_init(void)
{
	//陀螺仪互斥量创建
	imu_mutex = xSemaphoreCreateMutex();
	if (imu_mutex == NULL) {
		// 创建失败，系统异常处理
		buzzer_on();
		delay_ms(2000);
	}
	HAL_UART_Receive_DMA(&huart3,imu_rx_buf,BUFFER_SIZE);//单独这一条并不会触发USART3_IRQHandler
	__HAL_UART_ENABLE_IT(&huart3, UART_IT_IDLE);//启动了空闲中断才可能进入USART3_IRQHandler(没配置接收中断RXNE，不会接收一个字节触发一次)
	//HAL_UARTEx_ReceiveToIdle_DMA(&IMU_UART, imu_rx_buf, BUFFER_SIZE);//同样会开启DMA和空闲中断，但会在HAL_UART_IRQHandler里杀死DMA，导致下一次接收失败
	//注：只要开启DMA就默认开启DMA中断，在过半中断和完成中断里会调用event callback函数
}

void USART3_IRQHandler(void)//该中断只有串口空闲（idle），或串口错误时(ORE接收溢出),FE,NE（帧错误）)进入
{
	uint32_t flag_idle = 0;
	
	flag_idle = __HAL_UART_GET_FLAG(&IMU_UART,UART_FLAG_IDLE); 
	if((flag_idle != RESET))
	{ 
		__HAL_UART_CLEAR_IDLEFLAG(&IMU_UART);

		HAL_UART_DMAStop(&IMU_UART); 
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
	
	HAL_UART_Receive_DMA(&IMU_UART,imu_rx_buf,BUFFER_SIZE);//不放在if((flag_idle != RESET))里防止错误触发中断直接杀死传输
	__HAL_UART_ENABLE_IT(&IMU_UART, UART_IT_IDLE);
	HAL_UART_IRQHandler(&IMU_UART);//不建议删除，内部清除错误标志位，删了就得手动置位
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
