/*
 * @Rudder_control.c
 * @Description: 
 * @Version: 1.0.0
 * @Author: 
 * @Date: 2023-09-13 20:33:36
 * @LastEditTime: 2023-09-15 16:28:07
 */
#include "Rudder_control.h"
#include "usart.h"
#include "uart.h"


UART_HandleTypeDef Rudder;

#define GET_LOW_BYTE(A) ((uint8_t)(A))
//宏函数 获得A的低八位
#define GET_HIGH_BYTE(A) ((uint8_t)((A) >> 8))
//宏函数 获得A的高八位

uint8_t LobotTxBuf[128];  //发送缓存


/*初始化Rudder*/
void Rudder_Init(uint32_t bound)
{
	Rudder.Instance = USART6;
	Rudder.Init.BaudRate = bound;				   	// 波特率
	Rudder.Init.WordLength = UART_WORDLENGTH_8B; 	// 字长为8位数据格式
	Rudder.Init.StopBits = UART_STOPBITS_1;	   	// 一个停止位
	Rudder.Init.Parity = UART_PARITY_NONE;	   		// 无奇偶校验位
	Rudder.Init.HwFlowCtl = UART_HWCONTROL_NONE; 	// 无硬件流控
	Rudder.Init.Mode = UART_MODE_TX_RX;		   	// 收发模式
	HAL_UART_Init(&Rudder);					   	// HAL_UART_Init()会使能UART3
	__HAL_UART_ENABLE_IT(&Rudder, UART_IT_RXNE);
}



/*
	舵机控制
		Rudder_control(170, 4);	//机器人站立
		Rudder_control(310, 4);	//机器人躺下//310
		Rudder_control(360, 1); //右手举起
		Rudder_control(130, 1); //右手放下
		Rudder_control(150, 2); //左手举起
		Rudder_control(380, 2); //左手放下
		Rudder_control(380, 3); //头
*/


/*机器人动作*/
void Robot_Work(uint8_t id,uint8_t aim)//70-500
{
	if(id == BODY)  //身体
	{
		if(aim == UP)
			{moveServo(2, 1600, 500); //1号舵机至500位置
			vTaskDelay(2);}
		else
			{moveServo(2, 940, 500); //1号舵机至500位置
			vTaskDelay(2);}
	}
	else if(id == RARM)   //右臂
	{
		if (aim == UP)
			{moveServo(14, 2500, 200); 
			vTaskDelay(2);}
		else
			{moveServo(14, 1005, 200); 
			vTaskDelay(2);}
	}
	else if(id == LARM)   //左臂
	{
		if (aim == UP)
			{moveServo(15, 500, 200); 
			vTaskDelay(2);}
		else
			{moveServo(15, 1885, 200); 
			vTaskDelay(2);}
	}
	else if(id == HEAD)   
	{
		//头上下
		if (aim == UP)
			{moveServo(1, 1150, 300); 
			vTaskDelay(2);}
		else if(aim == DOWN)
			{moveServo(1, 815, 100); 
			vTaskDelay(2);}
		//头左右：头往左转，角度增大
		if (aim == HEAD_MID)
			{moveServo(0, 1500, 200);
			vTaskDelay(200);}
		else if (aim == HEAD_LEFT)
			{moveServo(0, 2200, 200);
			vTaskDelay(200);}
		else if (aim == HEAD_RIGHT)
			{moveServo(0, 500, 200);
			vTaskDelay(200);}
	}
	else if(id == PIG)   
	{
		//PIG左右摇摆
		if (aim == HEAD_LEFT)
			{moveServo(12, 1150, 300); 
			vTaskDelay(200);}
		else if(aim == HEAD_RIGHT)
			{moveServo(12, 500, 300); 
			vTaskDelay(200);}
	}
}


/*********************************************************************************
 * Function:  moveServo
 * Description： 控制单个舵机转动
 * Parameters:   sevoID:舵机ID，Position:目标位置,Time:转动时间
                    舵机ID取值:0<=舵机ID<=31,Time取值: Time > 0
 * Return:       无返回
 * Others:
 **********************************************************************************/
void moveServo(uint8_t servoID, uint16_t Position, uint16_t Time)
{
	if (servoID > 31 || !(Time > 0)) {  //舵机ID不能打于31,可根据对应控制板修改
		return;
	}
	LobotTxBuf[0] = LobotTxBuf[1] = FRAME_HEADER;    //填充帧头
	LobotTxBuf[2] = 8;
	LobotTxBuf[3] = CMD_SERVO_MOVE;           //数据长度=要控制舵机数*3+5，此处=1*3+5//填充舵机移动指令
	LobotTxBuf[4] = 1;                        //要控制的舵机个数
	LobotTxBuf[5] = GET_LOW_BYTE(Time);       //取得时间的低八位
	LobotTxBuf[6] = GET_HIGH_BYTE(Time);      //取得时间的高八位
	LobotTxBuf[7] = servoID;                  //舵机ID
	LobotTxBuf[8] = GET_LOW_BYTE(Position);   //取得目标位置的低八位
	LobotTxBuf[9] = GET_HIGH_BYTE(Position);  //取得目标位置的高八位

   HAL_UART_Transmit(&Rudder, LobotTxBuf, 10, HAL_MAX_DELAY);
}





