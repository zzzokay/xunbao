#ifndef __K210_h__
#define __K210_h__
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"
#include "sys.h"
#include "usart.h"

extern volatile uint8_t K210_Rece;
extern volatile uint8_t Clue_Num;
extern volatile uint8_t Maxicam_Rx;

/* 帧/颜色诊断计数（只增，不参与判据） */
extern volatile uint32_t Maxicam_RxBytes;
extern volatile uint32_t Maxicam_F3;
extern volatile uint32_t Maxicam_F3Mask;
extern volatile uint32_t Maxicam_ColorWrites;
extern volatile uint32_t Maxicam_Resends;

//切换成功标志位
extern volatile uint8_t open_QR_mode_sign;
extern volatile uint8_t open_OCR_mode_sign;
extern volatile uint8_t open_COLOR_L_mode_sign;
extern volatile uint8_t open_COLOR_R_mode_sign;

void Maxicam_Enable(void);
void Maxicam_ProcessRxByte(uint8_t rx_byte);
uint8_t Maxicam_WaitWithResend(volatile uint8_t *flag, void (*open_fn)(void),
                               uint16_t wait_ticks, uint8_t resend_blocks,
                               uint16_t *elapsed_out);
void open_QR_mode(void);
void open_OCR_mode(void);
void close_Maxicam(void);
void Reset_Process_State(void);
#endif
