#ifndef __imu_h__
#define __imu_h__
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"

struct Imu
{
	float yaw; //偏航角(绕Z轴)
	float roll; //横滚角:物体绕前后轴（X轴）
	float pitch; //俯仰角：物体绕左右轴（Y轴）

	float compensateZ; //Z轴补偿值
	float compensatePitch; //俯仰角补偿值
};
extern SemaphoreHandle_t imu_mutex;
extern struct Imu imu_shared_data;
extern struct Imu imu;

extern float basic_p;
extern float basic_y;
void gyro_init(uint32_t bound);
void imu_receive_init(void);
void IMU_CalibrateZero(float* yaw_out, float* pitch_out);
float get_latest_yaw(void);
#endif
