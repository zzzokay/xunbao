#ifndef __Rudder_control_H__
#define __Rudder_control_H__
#include "iic.h"
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"
void Rudder_Init(uint32_t bound);

#define Servo_UART  huart5


#define BODY        0
#define RARM        1
#define LARM        2
#define HEAD        3
#define MIKU        4
#define CAMERA      5

#define UP          0
#define DOWN        1
#define HEAD_MID    2
#define HEAD_LEFT   3
#define HEAD_RIGHT  4


#define FRAME_HEADER 0x55             //帧头
#define CMD_SERVO_MOVE 0x03           //舵机移动指令

void Robot_Work(uint8_t id, uint8_t aim);
void moveServo(uint8_t servoID, uint16_t Position, uint16_t Time);


#endif
