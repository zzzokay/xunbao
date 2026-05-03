#include "Rec_usart.h"
#include "pid.h"
#include "stdio.h"
#include "command.h"
#include "dma.h"


#define BUFFER_SIZE_rec  64

uint8_t Rx_data[BUFFER_SIZE_rec];
static uint8_t command[64];

#define GET_LOW_BYTE(A) ((uint8_t)(A))

#define GET_HIGH_BYTE(A) ((uint8_t)((A) >> 8))


extern DMA_HandleTypeDef hdma_uart4_rx;
extern uint8_t test_flag ;

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
		//HAL_UART_Transmit_DMA(&UART,Rx_data,Size); 
		HAL_UARTEx_ReceiveToIdle_DMA(&UART,Rx_data,sizeof(Rx_data));
		__HAL_DMA_DISABLE_IT(&hdma_uart4_rx,DMA_IT_HT);
	}
}
static uint8_t parse_cmd_field(const char* src, char* dst, uint8_t max_len)
{
	uint8_t i = 0;
	while(*src && *src != ',' && *src != ']' && i < max_len - 1)
	{
		dst[i++] = *src++;
	}
	dst[i] = '\0';
	return i;
}

void get_PIDdata()
{
	char dev[10], param[10], value[10];
	uint8_t length = Command_GetCommand(command);
	static float temp_kp = 0, temp_ki = 0, temp_kd = 0;
	// 解析命令格式：[dev,param,value]
	//printf("Received command\r\n");
	if(length > 0)
	{
		char* p = (char*)command;
		if(*p == '[') p++;
		p += parse_cmd_field(p, dev, 10);
		if(*p == ',') p++;
		p += parse_cmd_field(p, param, 10);
		if(*p == ',') p++;
		parse_cmd_field(p, value, 10);

		
		printf("CMD: [%s][%s][%s]\r\n", dev, param, value);
		 if(strcmp(dev,"slider")==0)
		 {
		 	if(strcmp(param,"kp")==0){temp_kp = atof(value);}
		 	if(strcmp(param,"ki")==0){temp_ki = atof(value);}
		 	if(strcmp(param,"kd")==0){temp_kd = atof(value);}
			if(strcmp(param,"target")==0)
		 	{  
		 		
		 		motor_all.Cspeed = atof(value);
				
		 	}
		 	if(strcmp(param,"turn")==0)
		 	{
				
		 		test_flag=2;
		 	}
		 	if(strcmp(param,"go")==0)
		 	{
			
				test_flag=1;
		 		line_pid_param.kp = temp_kp;
		 		line_pid_param.ki = temp_ki;
		 		line_pid_param.kd = temp_kd;
		 	}
		 }

		memset(dev,0,sizeof(dev));
		memset(param,0,sizeof(param));
		memset(value,0,sizeof(value));
		memset(command, 0, sizeof(command));
	}
}






