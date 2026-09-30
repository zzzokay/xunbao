#include "openmv.h"
#include "usart.h"
#include "math.h"
#include "stdio.h"
#include "uart.h"
#include "K210.h"
#include "Rudder_control.h"

#include "Rudder_control.h"



volatile uint8_t Color_Left, Color_Right;
volatile uint8_t COLOR_flag=0;//为1就是看左边，为2就是看右边



/*打开右MV*/
void Open_COLOR_R()
{
	open_COLOR_R_mode_sign=1;
	COLOR_flag = 2;
	uint8_t cmd[] = {0x33};
	uint8_t retry = MAXICAM_OPEN_RETRY;
	uint8_t try_idx = 0;
	Maxicam_WaitMode = 4;
	while(retry--) {
		try_idx++;
		HAL_UART_Transmit(&huart6, cmd, sizeof(cmd), 100);
		/* 满1字节后HAL会自动关闭本口接收；若本次发送把它错过，这里补回来（幂等，已在接收则返回BUSY） */
		HAL_UART_Receive_IT(&huart6, (uint8_t *)&Maxicam_Rx, 1);
		HAL_Delay(20);
		if(	open_COLOR_R_mode_sign==0)  break;
		HAL_Delay(30);
	}
	Maxicam_WaitMode = 0;
	printf("[MODE] COL_R %s try=%u ack=%u n=%lu\r\n",
	       (open_COLOR_R_mode_sign == 0) ? "ok" : "FAIL",
	       (unsigned)try_idx, Maxicam_AckMode, (unsigned long)Maxicam_AckCount);
}



/*打开左MV*/
void Open_COLOR_L()
{
	COLOR_flag = 1;
	uint8_t cmd[] = {0x33};
	open_COLOR_L_mode_sign=1;
	uint8_t retry = MAXICAM_OPEN_RETRY;
	uint8_t try_idx = 0;
	Maxicam_WaitMode = 3;
	while(retry--) {
		try_idx++;
		HAL_UART_Transmit(&huart6, cmd, sizeof(cmd), 100);
		/* 满1字节后HAL会自动关闭本口接收；若本次发送把它错过，这里补回来（幂等，已在接收则返回BUSY） */
		HAL_UART_Receive_IT(&huart6, (uint8_t *)&Maxicam_Rx, 1);
		HAL_Delay(20);
		if(open_COLOR_L_mode_sign == 0) break;
		HAL_Delay(30);
	}
	Maxicam_WaitMode = 0;
	printf("[MODE] COL_L %s try=%u ack=%u n=%lu\r\n",
	       (open_COLOR_L_mode_sign == 0) ? "ok" : "FAIL",
	       (unsigned)try_idx, Maxicam_AckMode, (unsigned long)Maxicam_AckCount);
}






