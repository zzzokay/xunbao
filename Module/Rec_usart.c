#include "Rec_usart.h"
#include "pid.h"
#include "stdio.h"
#include "command.h"
#include "dma.h"


#define BUFFER_SIZE_rec  10

uint8_t Rx_data[BUFFER_SIZE_rec];
uint8_t command[30];

#define GET_LOW_BYTE(A) ((uint8_t)(A))

#define GET_HIGH_BYTE(A) ((uint8_t)((A) >> 8))


extern DMA_HandleTypeDef hdma_uart4_rx;
extern uint8_t test_flag ;
extern struct Line_data line_data[HISTORY_SIZE];

volatile int center_x =50;
volatile int center_y =50;

#define HISTORY_SIZE 5
volatile uint16_t last_center_y[HISTORY_SIZE];

uint8_t S_recData;
volatile uint8_t start_flag =0;


volatile uint8_t recv_flag =0;

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
				if(strcmp(param,"kp")==0){line_pid_param.kp = atof(value);}
				if(strcmp(param,"ki")==0){line_pid_param.ki = atof(value);}	
				if(strcmp(param,"kd")==0){line_pid_param.kd = atof(value);}
				if(strcmp(param,"target")==0)
				{
					test_flag=1;
					//清零line_data
					for (int i = 0; i < HISTORY_SIZE; i++)
					{
						line_data[i].pos = 0.0f;
						line_data[i].error = 0.0f;
						line_data[i].truth = 1; // TRUTH_ALL_ERR，初始状态
					}
					//Chassis_SetTargetSpeed(atof(value));
					
				}
			}

			memset(dev,0,sizeof(dev));
			memset(param,0,sizeof(param));
			memset(value,0,sizeof(value));
			memset(command, 0, sizeof(command));
			}
		

}






