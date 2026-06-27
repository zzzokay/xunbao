#include "openmv.h"
#include "usart.h"
#include "math.h"
#include "stdio.h"
#include "uart.h"
#include "K210.h"
#include "Rudder_control.h"

#include "Rudder_control.h"



uint8_t Color_Left, Color_Right;
uint8_t COLOR_flag=0;//为1就是看左边，为2就是看右边



/*打开右MV*/
void Open_COLOR_R()
{
	open_COLOR_R_mode_sign=1;
	COLOR_flag = 2;
	uint8_t cmd[] = {0x33};
	uint8_t retry = 5;
	
//	while(retry--) {
	while(1) {
			HAL_UART_Transmit(&huart5, cmd, sizeof(cmd), 100);
			HAL_Delay(20);
			if(	open_COLOR_R_mode_sign==0)  break;
			HAL_Delay(30);
	}
}



/*打开左MV*/
void Open_COLOR_L()
{
	COLOR_flag = 1;
	uint8_t cmd[] = {0x33};
	uint8_t retry = 5;
	open_COLOR_L_mode_sign=1;
//	while(retry--) {
	while(1) {
			HAL_UART_Transmit(&huart5, cmd, sizeof(cmd), 100);
			HAL_Delay(20);
			if(open_COLOR_L_mode_sign==0) break;
			HAL_Delay(30);
	}
}






