/*
 * @File filter.c
 * @Description: 
 * @Version: 2.0.0
 * @Author: 
 * @Date: 2026-04-18 
 */
#include "filter.h"

uint8_t filter_Open = 0;

/**
 * @brief: 最大最小值+滑动平均滤波
 * @param {float} angle
 * @return {*}
 */
float filter(float angle)
{
    static uint8_t index = 0;
    static uint8_t count = 0;         // 记录数据点数量
    static float temp_angle[8];
    float max, min, sum = 0;
    
    // 写入新数据
    temp_angle[index] = angle;
    index = (index + 1) % 8;
    if (count < 8) count++;
    
    // 计算总和
    for (uint8_t i = 0; i < count; i++) {
        sum += temp_angle[i];
    }
    
    // 初始化阶段（数据点不足8个）
    if (count < 8) {
        return sum / count;
    }
    
    // 正常滤波（移除最大值和最小值）
    max = temp_angle[0];
    min = temp_angle[0];
    
    for (uint8_t i = 1; i < 8; i++) {
        if (temp_angle[i] > max) max = temp_angle[i];
        if (temp_angle[i] < min) min = temp_angle[i];
    }
    
    return (sum - max - min) / 6;
}

/**
 * @brief: 电机速度滑动窗口滤波（防脉冲干扰）
 * @param {float*} speed 电机当前速度的指针，滤波后直接修改该值
 * @param {uint8_t} motor_id 电机编号 (0~3)
 */
void filter_motor_speed(float *speed, uint8_t motor_id)
{
    if (motor_id >= 4) return;
    
    static float speed_buf[4][4] = {0}; // 4个电机，每个存储4个历史数据
    static uint8_t index[4] = {0};      // 4个电机的当前数据写入位置
    static uint8_t count[4] = {0};      // 当前已有数据量
    
    float sum = 0.0f;                   // 防止精度丢失使用float
    float max, min;
    
    // 写入新数据
    speed_buf[motor_id][index[motor_id]] = *speed;
    index[motor_id] = (index[motor_id] + 1) % 4;
    if (count[motor_id] < 4) count[motor_id]++;
    
    // 计算总和
    for (uint8_t i = 0; i < count[motor_id]; i++) {
        sum += speed_buf[motor_id][i];
    }
    
    // 初始化阶段（数据点不足4个）
    if (count[motor_id] < 4) {
        *speed = sum / count[motor_id];
        return;
    }
    
    // // 正常滤波（移除最大值和最小值后的算术平均）
    // max = speed_buf[motor_id][0];
    // min = speed_buf[motor_id][0];
    
    // for (uint8_t i = 1; i < 4; i++) {
    //     if (speed_buf[motor_id][i] > max) max = speed_buf[motor_id][i];
    //     if (speed_buf[motor_id][i] < min) min = speed_buf[motor_id][i];
    // }
    
    *speed = (sum - max - min) / 4.0f;
}
