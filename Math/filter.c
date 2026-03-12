/*
 * @File filter.c
 * @Description: 
 * @Version: 1.0.0
 * @Author: 
 * @Date: 2023-09-13 20:33:34
 * @LastEditTime: 2023-09-15 15:44:07
 */
#include "filter.h"

uint8_t filter_Open = 0;

/**
 * @brief: 最大最小值+滑动平均滤波
 * @param {float} angle
 * @return {*}
 */
float filter(float angle) //
{
	uint8_t i = 0;
	uint8_t j = 0;
	uint8_t k = 0;
	uint8_t m;
	static uint8_t first_flag = 0; //首次运行标志（0=前8次初始化，1=正常滤波）
	float max, min; //当前窗口内的最大值和最小值
	float angle_output, temp_angle[8]; //滤波后的输出值、存储最近8个采样值的数组
	float sum = 0; //当前窗口内数据的总和
	if (!first_flag) // 前八次记录
	{
		temp_angle[i++] = angle;
		sum += angle;
		angle_output = angle;
		if (i == 8) //已记录8个值后进入正常滤波
		{ // 找出最大值和最小值
			max = temp_angle[0];
			min = temp_angle[0];
			for (m = 7; m != 0; m--)
			{
				if (temp_angle[m] > max)
				{
					max = temp_angle[m];
				}
				else if (temp_angle[m] < min)
				{
					min = temp_angle[m];
				}
			}
			angle_output = (sum - max - min) / 6;
			first_flag = 1;
			sum = 0;
		}
	}
	else //正常滤波
	{
		temp_angle[j++] = angle;
		if (j == 8)
			j = 0;
		max = temp_angle[0];
		min = temp_angle[0];
		sum = temp_angle[0];
		for (k = 7; k != 0; k--)
		{
			if (temp_angle[k] > max)
			{
				max = temp_angle[k];
			}
			else if (temp_angle[k] < min)
			{
				min = temp_angle[k];
			}
			sum += temp_angle[k];
		}
		angle_output = (sum - min - max) / 6;
	}

	return angle_output;
}
