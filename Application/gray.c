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

#define THRESHOLD 1000  // 设置阈值
#define SENSOR_NUM 8  // 4 路灰度传感器
#define DIFF_THRESH 500 // 灰度最大值与其他传感器的最小差值

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

/*灰度获取一次二进制循线值*/
uint8_t Gray_GetLine(void)
{
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
	//printf("%d,%d,%d,%d\r\n",AD_Value_Gray[0],AD_Value_Gray[1],AD_Value_Gray[2],AD_Value_Gray[3]);
    return data;
}

// 坡道灰度角度修正：找最大值，若明显高于其他传感器则输出对应角度
// 返回值：检测到线时返回角度偏移，未检测到返回 0
// AD_Value_Gray[0]=左  [1]=中左  [2]=中右  [3]=右
float Gray_GetCorrectAngle(float base_angle)
{
	uint16_t max_val = 0;
	uint8_t max_idx = 0;

	// 找最大值
	for (uint8_t i = 0; i < 4; i++) {
		if (AD_Value_Gray[i] > max_val) {
			max_val = AD_Value_Gray[i];
			max_idx = i;
		}
	}

	// 判断最大值是否比其他三个都大出阈值
	for (uint8_t i = 0; i < 4; i++) {
		if (i == max_idx) continue;
		if (max_val - AD_Value_Gray[i] < DIFF_THRESH)
			return 0.0f;  // 不够突出，不修正
	}

	// 根据最大值位置输出角度
	switch (max_idx) {
		case 0: return base_angle*1.4;   // 最左 → 偏右，向左修正
		case 1: return base_angle;   // 中左
		case 2: return -base_angle;   // 中右
		case 3: return -base_angle*1.4;   // 最右 → 向右修正
		default: return 0.0f;
	}
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
}
