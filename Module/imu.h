#ifndef __imu_h__
#define __imu_h__
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"

struct Imu
{
	float yaw; //Æ«º½½Ç(ÈÆZÖá)
	float roll; //ºá¹ö½Ç:ÎïÌåÈÆÇ°ºóÖá£¨XÖá£©
	float pitch; //¸©Ñö½Ç£ºÎïÌåÈÆ×óÓÒÖá£¨YÖá£©

	float compensateZ; //ZÖá²¹³¥Öµ
	float compensatePitch; //¸©Ñö½Ç²¹³¥Öµ
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
