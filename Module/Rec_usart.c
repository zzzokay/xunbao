#include "Rec_usart.h"
#include "pid.h"
#include "stdio.h"
#include "command.h"
#include "dma.h"

#define BUFFER_SIZE_rec  10

uint8_t Rx_data[BUFFER_SIZE_rec];
uint8_t command[30];

#define LINE_SPEED_MAX 68
#define CAR_ALINE_SPEED_MAX 50


#define GET_LOW_BYTE(A) ((uint8_t)(A))
//�꺯�� ���A�ĵͰ�λ
#define GET_HIGH_BYTE(A) ((uint8_t)((A) >> 8))
//�꺯�� ���A�ĸ߰�λ

extern DMA_HandleTypeDef hdma_uart4_rx;

volatile int center_x =50;
volatile int center_y =50;

#define HISTORY_SIZE 5
volatile uint16_t last_center_y[HISTORY_SIZE];

uint8_t S_recData;
volatile uint8_t start_flag =0;//��ذ��ϵİ������Ƴ������еı�־λ


volatile uint8_t recv_flag =0;//���ձ�־λ

void Rec_usart_init(void)
{
	 HAL_UARTEx_ReceiveToIdle_DMA(&UART,Rx_data,BUFFER_SIZE_rec);
	 __HAL_DMA_DISABLE_IT(&hdma_uart4_rx,DMA_IT_HT);
}
	

void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t Size)
{
	if(huart==&UART)
	{
		Command_Write(Rx_data,Size);
		HAL_UART_Transmit_DMA(&UART,Rx_data,Size);
		HAL_UARTEx_ReceiveToIdle_DMA(&UART,Rx_data,sizeof(Rx_data));
		__HAL_DMA_DISABLE_IT(&hdma_uart4_rx,DMA_IT_HT);
	}
}
void get_PIDdata()
{
	 char dev[10],param[10],value[10];
	 uint8_t length=Command_GetCommand(command);
		if(length>0)
		{ 
			sscanf((char*)command,"[%[^,],%[^,],%[^]]",dev,param,value);
			if(strcmp(dev,"slider")==0)
			{ 
				if(strcmp(param,"kp")==0){MOTOR_PID_PARAM.kp = atof(value);}
				if(strcmp(param,"ki")==0){MOTOR_PID_PARAM.ki = atof(value);}	
				if(strcmp(param,"kd")==0){MOTOR_PID_PARAM.kd = atof(value);}
				if(strcmp(param,"target")==0)
				{
					motor_all.Cspeed = atof(value);
				}
			}

			memset(dev,0,sizeof(dev));
			memset(param,0,sizeof(param));
			memset(value,0,sizeof(value));
			memset(command, 0, sizeof(command));
			}
		

}






