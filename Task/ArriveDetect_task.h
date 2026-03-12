#ifndef __ArriveDetect_task_h__
#define __ArriveDetect_task_h__
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"
#include  "task_create.h"
extern void arrive_detect_task(void *pvParameters);
void send_play_specified_command(uint8_t index);
uint8_t deal_arrive(void);
#endif
