#ifndef __keys_H
#define __keys_H

#include "main.h"
#include "tim.h"
//#include "servo.h"
//#include "stdio.h"
//#include "usart.h"

#define KEY_NUM 1

struct keys
{
	uint8_t mode;
	uint8_t pin_sta;
	uint8_t single_flag;
	uint8_t long_flag;
	uint8_t double_flag;
	uint8_t count;
	
};


extern struct keys key[KEY_NUM];
void key_scan(void);

#endif
