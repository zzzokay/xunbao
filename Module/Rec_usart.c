#include "Rec_usart.h"
#include "pid.h"
#include "stdio.h"
uint8_t Rx_data[30];
#define LINE_SPEED_MAX 68
#define CAR_ALINE_SPEED_MAX 50


#define GET_LOW_BYTE(A) ((uint8_t)(A))
//宏函数 获得A的低八位
#define GET_HIGH_BYTE(A) ((uint8_t)((A) >> 8))
//宏函数 获得A的高八位



volatile int center_x =50;
volatile int center_y =50;

#define HISTORY_SIZE 5
volatile uint16_t last_center_y[HISTORY_SIZE];

uint8_t S_recData;
volatile uint8_t start_flag =0;//舵控板上的按键控制程序运行的标志位


volatile uint8_t recv_flag =0;//接收标志位

void Rec_usart_init(void)
{
	
	 HAL_UART_Receive_IT(&huart4,Rx_data,BUFFER_SIZE_rec);

}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
	if(huart==&huart4)
	{
	   recv_flag=1;
		 HAL_UART_Receive_IT(&huart4,Rx_data,BUFFER_SIZE_rec);
		//HAL_UART_Receive_IT(&huart4,Rx_data,1);
	}

}	


void get_PIDdata()
{
	// uint8_t length=Command_GetCommand(command);
	// 	if(length>0)
	// 	{ 
	// 		sscanf((char*)command,"[%[^,],%[^,],%[^]]",dev,param,value);
	// 		if(strcmp(dev,"slider")==0)
	// 		{ 
	// 			if(strcmp(param,"kp")==0){kp=atof(value);}
	// 			if(strcmp(param,"ki")==0){ki=atof(value);}	
	// 			if(strcmp(param,"kd")==0){kd=atof(value);}
	// 			if(strcmp(param,"target")==0){target_speed=atof(value);}
	// 		}
	// 		// motor_pid.Kp = kp;     
	// 		// motor_pid.Ki = ki;      
	// 		// motor_pid.Kd = kd;      
	// 		// motor_pid.Target = target_speed; 
			
			
	// 		memset(dev,0,sizeof(dev));
	// 		memset(param,0,sizeof(param));
	// 		memset(value,0,sizeof(value));
	// 		memset(command, 0, sizeof(command));
	// 	}
	if(recv_flag == 1)
	{
		printf("Received\n");
		recv_flag = 0;
	}
	//else{printf("waiting...\n");}



}


// //入参：字符串数组(存储ascii码数组)的地址 ; 字符串数组的长度
// void get_PIDdata(uint8_t *data, uint16_t size)
// {
// 	if(recv_end_flag==1)
// 	{
// 		printf("1");
//  	int startIdx,endIdx;		//定义有效数据的起始索引和结束索引
// 	char valueStr[30] = {0}; 	//定义有效数据对应的字符串
// 	float rec_data;				//
	
// 	if(data[size-1] == '!')		//当最后一位为字符'!'(说明下，==进行判断时，两端都必须是数值，也即左侧会解析为数值(uint8_t数组的值)，右侧也会解析为数值(字符'!'对应的ascii值)
// 	{
// 		//找到 '=' 的索引
// 		for(int i=0;i<size;i++)
// 		{
// 			if(data[i] == '=')
// 			{
// 				startIdx = i + 1;	//找到有效数据起始索引
// 				break;
// 			}
// 		}
// 		//找到 '!' 的索引
// 		for (int i = startIdx; i < size; i++)
//         {
//             if (data[i] == '!')
//             {
//                 endIdx = i;		//找到有效数据结束索引
//                 break;
//             }
//         }
// 		//提取 '='与'!'之间的数值
// 		if (startIdx > 0 && endIdx > startIdx)
// 		{
// 			strncpy(valueStr, (char*)&data[startIdx], endIdx - startIdx);	//将有效数据长度的字符从data源字符串中拷贝到valueStr字符串中
// 			valueStr[endIdx - startIdx] = '\0';	//将valueStr字符串尾部补上'\0'，作为字符串结束标志
// 			rec_data = atof(valueStr);		//将字符串转换为浮点数("2.32"-->2.32)
// 		}
		
				
// 		// 设置左右电机的PID参数
// 		if (data[0] == 'P' && data[1] == 'L'&& data[2] == '1')
// 		{
// 			motor_pid_paramL1.kp = rec_data;
// //			printf("L0_KP = %.3f\n", motor_pid_paramL1.kp);
// 		}
// 		else if (data[0] == 'I' && data[1] == 'L'&& data[2] == '1')
// 		{
// 			motor_pid_paramL1.ki = rec_data;
// 			printf("L1_KI = %.3f\n", motor_pid_paramL1.ki);
// 		}
// 		else if (data[0] == 'D' && data[1] == 'L'&& data[2] == '1')
// 		{
// 			motor_pid_paramL0.kd = rec_data;
// 			printf("L0_Kd = %.3f\n", motor_pid_paramL0.kd);
// 		}
		
// 		else if (data[0] == 'P' && data[1] == 'R'&& data[2] == '0')
// 		{
// 			motor_pid_paramR0.kp = rec_data;
// 			printf("R0_Kp = %.3f\n", motor_pid_paramR0.kp);
// 		}
// 		else if (data[0] == 'I' && data[1] == 'R'&& data[2] == '0')
// 		{
// 			motor_pid_paramR0.ki = rec_data;
// 			printf("R0_Ki = %.3f\n", motor_pid_paramR0.ki);
// 		}
// 		else if (data[0] == 'D' && data[1] == 'R'&& data[2] == '0')
// 		{
// 			motor_pid_paramR0.kd = rec_data;
// 			printf("R0_Kd = %.3f\n", motor_pid_paramR0.kd);
// 		}
		
// 		else	if (data[0] == 'P' && data[1] == 'L'&& data[2] == '1')
// 		{
// 			motor_pid_paramL1.kp = rec_data;
// 			printf("L1_KP = %.3f\n", motor_pid_paramL1.kp);
// 		}
// 		else if (data[0] == 'I' && data[1] == 'L'&& data[2] == '1')
// 		{
// 			motor_pid_paramL1.ki = rec_data;
// 			printf("L1_KI = %.3f\n", motor_pid_paramL1.ki);
// 		}
// 		else if (data[0] == 'D' && data[1] == 'L'&& data[2] == '1')
// 		{
// 			motor_pid_paramL1.kd = rec_data;
// 			printf("L1_Kd = %.3f\n", motor_pid_paramL1.kd);
// 		}
		
// 		else if (data[0] == 'P' && data[1] == 'R'&& data[2] == '1')
// 		{
// 			motor_pid_paramR1.kp = rec_data;
// 			printf("R1_Kp = %.3f\n", motor_pid_paramR1.kp);
// 		}
// 		else if (data[0] == 'I' && data[1] == 'R'&& data[2] == '1')
// 		{
// 			motor_pid_paramR1.ki = rec_data;
// 			printf("R1_Ki = %.3f\n", motor_pid_paramR1.ki);
// 		}
// 		else if (data[0] == 'D' && data[1] == 'R'&& data[2] == '1')
// 		{
// 			motor_pid_paramR1.kd = rec_data;
// 			printf("R1_Kd = %.3f\n", motor_pid_paramR1.kd);
// 		}
		
		
// 		else if (data[0] == 'T' && data[1] == 'A'&& data[2] == 'R'&& data[3] == 'L')
// 		{
// 			motor_all.Lspeed = rec_data;
// 			printf("targetL = %.3f\n", motor_all.Lspeed);
// 		}
// 		else if (data[0] == 'T' && data[1] == 'A'&& data[2] == 'R'&& data[3] == 'R')
// 		{
// 			motor_all.Rspeed = rec_data;
// 			printf("targetR = %.3f\n", motor_all.Rspeed);
// 		}

// 	}
	
// 		HAL_UART_Receive_DMA(&huart5,R_data,30);

// 		recv_end_flag =0;
// 	}
// }







