#ifndef __Rec_usart_h__
#define __Rec_usart_h__


#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "usart.h"
//#include "Motor.h"
#include "string.h"
#include "stdlib.h"
#include "stm32f7xx_it.h"
#include "math.h"
#include "turn.h"


#define TARGET_CENTER_Y 50 
#define UART   				 huart4
#define MOTOR_PID_PARAM		 motor_pid_paramR1
#define MOTOR 				 motor_R1

extern volatile uint16_t last_center_y[5];
extern	volatile uint8_t send_target_flag ;
extern uint8_t S_recData;
extern volatile uint8_t start_flag ;//舵控板上的按键控制程序运行的标志位
//extern int8_t track_line_dir ;//循迹方向


void Rec_usart_init(void);

//入参：字符串数组(存储ascii码数组)的地址 ; 字符串数组的长度
// void get_PIDdata(uint8_t *data, uint16_t size);
void get_PIDdata();


#endif
