#ifndef _FILTER_H_
#define _FILTER_H_

#include "main.h"

float filter(float angle);
void filter_motor_speed(float *speed, uint8_t motor_id);

extern uint8_t filter_Open;
#endif
