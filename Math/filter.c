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
 * @brief: �����Сֵ+����ƽ���˲�
 * @param {float} angle
 * @return {*}
 */
float filter(float angle)
{
    static uint8_t index = 0;
    static uint8_t count = 0;         // ��¼���ݵ�����
    static float temp_angle[8];
    float max, min, sum = 0;
    
    // д��������
    temp_angle[index] = angle;
    index = (index + 1) % 8;
    if (count < 8) count++;
    
    // �����ܺ�
    for (uint8_t i = 0; i < count; i++) {
        sum += temp_angle[i];
    }
    
    // ��ʼ���׶Σ����ݵ㲻��8����
    if (count < 8) {
        return sum / count;
    }
    
    // �����˲����Ƴ����ֵ����Сֵ��
    max = temp_angle[0];
    min = temp_angle[0];
    
    for (uint8_t i = 1; i < 8; i++) {
        if (temp_angle[i] > max) max = temp_angle[i];
        if (temp_angle[i] < min) min = temp_angle[i];
    }
    
    return (sum - max - min) / 6;
}

/**
 * @brief: ����ٶȻ��������˲�����������ţ�
 * @param {float*} speed �����ǰ�ٶȵ�ָ�룬�˲���ֱ���޸ĸ�ֵ
 * @param {uint8_t} motor_id ������ (0~3)
 */
void filter_motor_speed(float *speed, uint8_t motor_id)
{
    if (motor_id >= 4) return;
    
    static float speed_buf[4][4] = {0}; // 4�������ÿ���洢4����ʷ����
    static uint8_t index[4] = {0};      // 4������ĵ�ǰ����д��λ��
    static uint8_t count[4] = {0};      // ��ǰ����������
    
    float sum = 0.0f;                   // ��ֹ���ȶ�ʧʹ��float
    float max, min;
    
    // д��������
    speed_buf[motor_id][index[motor_id]] = *speed;
    index[motor_id] = (index[motor_id] + 1) % 4;
    if (count[motor_id] < 4) count[motor_id]++;
    
    // �����ܺ�
    
    for (uint8_t i = 0; i < count[motor_id]; i++) {
        sum += speed_buf[motor_id][i];
    }
    // ��ʼ���׶Σ����ݵ㲻��4����
    if (count[motor_id] < 4) {
        *speed = sum / count[motor_id];
        return;
    }
    
    // �����˲����Ƴ����ֵ����Сֵ�������ƽ����
    max = speed_buf[motor_id][0];
    min = speed_buf[motor_id][0];
    
    for (uint8_t i = 1; i < 4; i++) {
        if (speed_buf[motor_id][i] > max) max = speed_buf[motor_id][i];
        if (speed_buf[motor_id][i] < min) min = speed_buf[motor_id][i];
    }
    
    *speed = (sum - max - min) / 2.0f;
}
