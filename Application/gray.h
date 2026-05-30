#ifndef _GRAY_H_
#define _GRAY_H_

#include "main.h"
#include "scaner.h"

#define RF          0
#define Gray        1

void Gray_Open(void);
void Gray_Close(void);
uint8_t Gray_GetLine(void);
float Gray_GetCorrectAngle(void);
void Calculate_Error(volatile SCANER *scaner);
void ScanerMode_Switch(uint8_t mode);

extern uint8_t ScanerMode;
extern uint16_t AD_Value_Gray[4];
#endif
