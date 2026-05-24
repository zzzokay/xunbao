#include "gray.h"
#include "delay.h"
#include "main_task.h"
#include "pid.h"
#include "string.h"
#include "chassis_api.h"
#include "scaner.h"
#include "adc.h"
#include "stdio.h"

uint8_t ScanerMode = RF;        //当前循迹模式
uint16_t AD_Value_Gray[4];//定义一个数组

void Gray_Open(void)
{
	HAL_ADC_Start_DMA(&hadc2,(uint32_t *)AD_Value_Gray, 4);
}

void Gray_Close(void)
{
	HAL_DMA_Abort(&hdma_adc2);
	HAL_ADC_Stop(&hadc2);
}
#define THRESHOLD 500  // 设置阈值
#define SENSOR_NUM 8  // 4 路灰度传感器

/*切换循迹模式*/
void ScanerMode_Switch(uint8_t mode)
{
    // 切换模式时清零 line_data，避免旧模式数据污染新模式
    for (int i = 0; i < HISTORY_SIZE; i++)
    {
        line_data[i].pos = 0.0f;
        line_data[i].error = 0.0f;
        line_data[i].truth = TRUTH_ALL_ERR; // 初始状态
    }

    if(mode == RF)
    {
        ScanerMode = RF;
		 // 停止 DMA
		Gray_Close();
        for (uint8_t i = 0; i < 16; i++)
        {
            line_weight[i] = line_weight_default[i];
        }
    }
    else if(mode == Gray)
    {
        ScanerMode = Gray;
		Gray_Open();
    }

}

/*SDA模式转换*/
void I2C_Judge(uint8_t id,uint8_t judgement)
{
    uint16_t Pin;
    if(id == LEFT)
        Pin = GPIO_PIN_13;
    else
        Pin = GPIO_PIN_8;
    GPIO_InitTypeDef GPIO_InitStruct;
	if(judgement == out)             //输出模式
	{
        GPIO_InitStruct.Pin = Pin;
        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
        GPIO_InitStruct.Pull = GPIO_PULLUP;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
		HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);
	}else if(judgement == in)       //输入模式
	{
        GPIO_InitStruct.Pin = Pin;
        GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
		GPIO_InitStruct.Pull =GPIO_PULLUP;
		GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
		HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);
	}
}

/*
启动I2C 当SCL处于高电平时SDA由高电平改为低电平，拉低SDA
(0：启动失败；1：启动成功)
*/
uint8_t I2C_Start(uint8_t id)
{
	I2C_Judge(id,out);                  //输出模式
    if(id == LEFT)
    {
        LEFT_SDA_H; // 拉高SDA
        delay_us(5);
        LEFT_SCL_H; // 拉高SCL
        delay_us(5);
        if (!LEFT_SDA_read)
            return 0; // 如果SDA低电平则总线忙，退出
        LEFT_SDA_L;        // SCL处于高电平时，拉低SDA
        delay_us(5);
        if (LEFT_SDA_read)
            return 0; // 如果SDA高电平则总线出错，退出
        LEFT_SCL_L;        // 拉低SCL
        delay_us(5);
    }
    else if(id == RIGHT)
    {
        RIGHT_SDA_H; // 拉高SDA
        delay_us(5);
        RIGHT_SCL_H; // 拉高SCL
        delay_us(5);
        if (!RIGHT_SDA_read)
            return 0; // 如果SDA低电平则总线忙，退出
        RIGHT_SDA_L;   // SCL处于高电平时，拉低SDA
        delay_us(5);
        if (RIGHT_SDA_read)
            return 0; // 如果SDA高电平则总线出错，退出
        RIGHT_SCL_L;   // 拉低SCL
        delay_us(5);
    }
	
	return 1;                      //成功开启I2C通信
}

/*
停止I2C 当SCL为高电平时，SDA由低电平改为高电平，拉高SDA
*/
void I2C_Stop(uint8_t id)
{
    if(id == LEFT)
    {
        I2C_Judge(id,out);
        LEFT_SDA_L; // 拉低SDA
        LEFT_SCL_L; // 拉低SCL
        delay_us(5);
        LEFT_SCL_H; // 拉高SCL
        delay_us(5);
        LEFT_SDA_H; // 当SCL处于高电平期间，SDA由低电平变成高电平
    }
    else if(id == RIGHT)
    {
        I2C_Judge(id,out);
        RIGHT_SDA_L; // 拉低SDA
        RIGHT_SCL_L; // 拉低SCL
        delay_us(5);
        RIGHT_SCL_H; // 拉高SCL
        delay_us(5);
        RIGHT_SDA_H; // 当SCL处于高电平期间，SDA由低电平变成高电平
    }
}

/*
I2C发送应答信号 从机接收到数据后，向主机发送低电平信号
先准备SDA电平状态，在SCL高电平时，主机采样SDA
入口参数ack(0：ACK；1：NAk)
*/
void I2C_SendACK(uint8_t id,uint8_t i)
{
    if(id == LEFT)
    {
        LEFT_SCL_L;
        I2C_Judge(id, out);
        if (i == no)
        {
            LEFT_SDA_H; // 不应答
        }
        else
        {
            LEFT_SDA_L; // 应答
        }
        delay_us(5);
        LEFT_SCL_H; // 拉高SCL
        delay_us(5);
        LEFT_SCL_L;
    }
    else if(id == RIGHT)
    {
        RIGHT_SCL_L;
        I2C_Judge(id, out);
        if (i == no)
        {
            RIGHT_SDA_H; // 不应答
        }
        else
        {
            RIGHT_SDA_L; // 应答
        }
        delay_us(5);
        RIGHT_SCL_H; // 拉高SCL
        delay_us(5);
        RIGHT_SCL_L;
    }
}

/*
当主机发送数据后，等待从机应答
先释放SDA，让从机使用，然后采集SDA状态
*/
uint8_t I2C_WaitAck(uint8_t id)
{
	uint16_t i = 0;
	I2C_Judge(id,in);
    if(id == LEFT)
    {
        LEFT_SDA_H; // 释放（拉高）SDA
        delay_us(5);
        LEFT_SCL_H; // 拉高SCL采样
        delay_us(5);
        while (LEFT_SDA_read) // 等待SDA拉低
        {
            i++;
            if (i == 500)
            {
                break;
            }
        }
        if (LEFT_SDA_read) // 再次判断SDA是否拉低
        {
            LEFT_SCL_L;
            return RESET; // 应答失败，返回0
        }
        LEFT_SCL_L;
    }
    else
    {
        RIGHT_SDA_H; // 释放（拉高）SDA
        delay_us(5);
        RIGHT_SCL_H; // 拉高SCL采样
        delay_us(5);
        while (RIGHT_SDA_read) // 等待SDA拉低
        {
            i++;
            if (i == 500)
            {
                break;
            }
        }
        if (RIGHT_SDA_read) // 再次判断SDA是否拉低
        {
            RIGHT_SCL_L;
            return RESET; // 应答失败，返回0
        }
        RIGHT_SCL_L;
    }

    delay_us(5);
    return SET;                    //应答成功，返回1
}

/*
向I2C总线发送一个字节(8 bit)数据
当SCL为低电平时，准备好SDA，SCL高电平时，从机采样SDA
*/
void I2C_SendByte(uint8_t id,uint8_t data)
{
	uint8_t i;
	I2C_Judge(id,out);
    if(id == LEFT)
    {
        LEFT_SCL_L;                  // 拉低SCL，给SDA准备
        for (i = 0; i < 8; i++) // 8位计时器
        {
            if (data & 0x80) // SDA准备（0x80为一个字节）,如果第八位是高电平
            {
                LEFT_SDA_H;
            }
            else
            {
                LEFT_SDA_L;
            }
            delay_us(5);
            LEFT_SCL_H; // 拉高SCL，给从机采样
            delay_us(5);
            LEFT_SCL_L; // 拉低SCL，给SDA做准备
            delay_us(5);
            data <<= 1; // 移出数据的最高位
        }
    }
    else
    {
        RIGHT_SCL_L;             // 拉低SCL，给SDA准备
        for (i = 0; i < 8; i++) // 8位计时器
        {
            if (data & 0x80) // SDA准备（0x80为一个字节）,如果第八位是高电平
            {
                RIGHT_SDA_H;
            }
            else
            {
                RIGHT_SDA_L;
            }
            delay_us(5);
            RIGHT_SCL_H; // 拉高SCL，给从机采样
            delay_us(5);
            RIGHT_SCL_L; // 拉低SCL，给SDA做准备
            delay_us(5);
            data <<= 1; // 移出数据的最高位
        }
    }
}

/*
从I2C总线中接收一个字节数据
*/
uint8_t I2C_ReceiveByte(uint8_t id)
{
	uint8_t i,data;
	I2C_Judge(id,in);
    if(id == LEFT)
    {
        LEFT_SDA_H; // 释放SDA，给从机使用
        delay_us(5);
        for (i = 0; i < 8; i++) // 8位计数器
        {
            data <<= 1;
            LEFT_SCL_H;        // 拉高SCL，采样从机SDA
            if (LEFT_SDA_read) // 读数据
            {
                data |= 0x01;
            }
            delay_us(5);
            LEFT_SCL_L; // 拉低SCL，处理数据
            delay_us(5);
        }
    }
    else
    {
        RIGHT_SDA_H; // 释放SDA，给从机使用
        delay_us(5);
        for (i = 0; i < 8; i++) // 8位计数器
        {
            data <<= 1;
            RIGHT_SCL_H;        // 拉高SCL，采样从机SDA
            if (RIGHT_SDA_read) // 读数据
            {
                data |= 0x01;
            }
            delay_us(5);
            RIGHT_SCL_L; // 拉低SCL，处理数据
            delay_us(5);
        }
    }
	
	return data;
}

/*
向I2C写入一个字节数据
Slave_Address：设备地址
REG_Address：寄存器地址
*/
/*
uint8_t I2C_WriteByte(uint8_t id,uint8_t SA,uint8_t RA,uint8_t data)
{
	I2C_Judge(id,out);
	if(I2C_Start(id) == 0)         //起始信号 
	{
		I2C_Stop(id);
		return RESET;
	}
	I2C_SendByte(id,SA);            //发送设备地址
	if(!I2C_WaitAck(id))
	{
		I2C_Stop(id);
		return RESET;
	}
	I2C_SendByte(id,RA);            //发送寄存器地址
	if(!I2C_WaitAck(id))
	{
		I2C_Stop(id);
		return RESET;
	}
	I2C_SendByte(id,data);          //发送数据
	if(!I2C_WaitAck(id))
	{
		I2C_Stop(id);
		return RESET;
	}
	I2C_Stop(id);                  //停止信号
	return SET;
}
*/

/*
从I2C设备中读取一个字节数据
*/
//uint8_t I2C_ReadByte(uint8_t id,uint8_t SA,uint8_t RA,uint8_t *REG_data,uint8_t length)
//{
//	I2C_Judge(id,in);
//	if(I2C_Start(id) == 0)         //起始信号 
//	{
//		I2C_Stop(id);
//		return RESET;
//	}
//	I2C_SendByte(id,SA);            //发送设备地址
//	if(!I2C_WaitAck(id))
//	{
//		I2C_Stop(id);
//		return RESET;
//	}
//	I2C_SendByte(id,RA);            //发送寄存器地址
//	if(!I2C_WaitAck(id))
//	{
//		I2C_Stop(id);
//		return RESET;
//	}
//	if(I2C_Start(id) == 0)         //起始信号 
//	{
//		I2C_Stop(id);
//		return RESET;
//	}
//	I2C_SendByte(id,SA+1);          //发送设备地址（读）
//	if(!I2C_WaitAck(id))
//	{
//		I2C_Stop(id);
//		return RESET;
//	}
//	while(length-1)
//	{
//		*REG_data++ = I2C_ReceiveByte(id);  //读出寄存器数据
//		I2C_SendACK(id,0);          //应答
//		length--;
//	}
//	*REG_data = I2C_ReceiveByte(id);
//	I2C_SendACK(id,no);              //发送停止传输信号
//	I2C_Stop(id);                  //停止信号
//	// vTaskDelay(10);
//	return SET;
//}

/*灰度快速读值*/
uint8_t I2C_ReadOnce(uint8_t id, uint8_t SA, uint8_t RA, uint8_t *REG_data, uint8_t length)
{
    I2C_Judge(id, in);
    if (I2C_Start(id) == 0) // 起始信号
    {
        I2C_Stop(id);
        return RESET;
    }
    I2C_SendByte(id, SA + 1); // 发送设备地址（读）
    if (!I2C_WaitAck(id))
    {
        I2C_Stop(id);
        return RESET;
    }
    while (length - 1)
    {
        *REG_data++ = I2C_ReceiveByte(id); // 读出寄存器数据
        I2C_SendACK(id, 0);                // 应答
        length--;
    }
    *REG_data = I2C_ReceiveByte(id);
    I2C_SendACK(id, no); // 发送停止传输信号
    I2C_Stop(id);        // 停止信号
    // vTaskDelay(10);
    return SET;
}

/*灰度获取一次二进制循线值*/
uint8_t Gray_GetLine(void)
{

	*/
	 // 通过判断 ADC 值与阈值的大小来设置对应位的数据
	uint8_t data = 0;  // 初始化为 00000000
    for (int i = 0; i < 4; i++)
    {
        if (AD_Value_Gray[i] < THRESHOLD)  // 如果传感器值大于阈值，认为该传感器检测到黑线
        {
            data |= (1 << (5 - i));  // 将对应的 bit 位设为 1
        }
        else
        {
            data &= ~(1 << (5 - i));  // 否则设为 0
        }
    }
	// 输出调试数据，可以根据实际需要移除
//    printf("data: %02X\r\n", data);
		printf("%d,%d,%d,%d\r\n",AD_Value_Gray[0],AD_Value_Gray[1],AD_Value_Gray[2],AD_Value_Gray[3]);
    return data;
}	

// 假设 scaner.detail 存储了 4 路传感器的二进制数据
void Calculate_Error(volatile SCANER *scaner) {
    float error = 0.0f;  // 用于存储误差值
    uint8_t lednum_tmp = 0;  // 灯数（用来计算平均误差）

    // 获取传感器二进制值并计算误差
    for (uint8_t i = 0; i < SENSOR_NUM; i++) {
        if ((scaner->detail_gray & (0x1 << (SENSOR_NUM-1-i)))) {  // 检测到黑线（传感器值为 1）
            lednum_tmp++;  // 记录有效的传感器数量
            // 根据传感器的位置和权重计算误差
            error += ((scaner->detail_gray >> (SENSOR_NUM - 1 - i)) & 0x01) * lineG_weight_default[i];
        }
    }
	
    // 如果有有效的传感器数据，计算误差的平均值
    if (lednum_tmp > 0) {
        error /= (float)lednum_tmp;  // 取有效传感器数据的平均误差
    }

    // 将误差值存储到 Scaner.error
    scaner->gray_error = error;

    // 无需更新错误信息部分，移除 Update_line_data 函数调用
    // Update_line_data(NO_error, scaner->error, scaner->error);
}
