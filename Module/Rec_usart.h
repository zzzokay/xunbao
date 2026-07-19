#ifndef __Rec_usart_h__
#define __Rec_usart_h__


#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "usart.h"
#include "string.h"
#include "stdlib.h"
#include "stm32f7xx_it.h"
#include "math.h"
#include "turn.h"


#define TARGET_CENTER_Y 50
#define UART             huart4
#define MOTOR_PID_PARAM  motor_pid_paramR1
#define MOTOR            motor_R1

void Rec_usart_init(void);
void get_PIDdata();
void RecUsart_RxIdleHandler(uint16_t Size);


#endif
