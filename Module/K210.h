#ifndef __K210_h__
#define __K210_h__
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"
#include "sys.h"
#include "usart.h"

extern uint8_t K210_Rece;
extern uint8_t Clue_Num;

//切换成功标志位
extern uint8_t open_QR_mode_sign;
extern uint8_t open_OCR_mode_sign;
extern uint8_t open_COLOR_L_mode_sign;
extern uint8_t open_COLOR_R_mode_sign;

void Maxicam_Enable(void);
void open_QR_mode(void);
void open_OCR_mode(void);
void close_Maxicam(void);
#endif
