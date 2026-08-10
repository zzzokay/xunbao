#ifndef __imu_h__
#define __imu_h__

#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include "main.h"
#include "cmsis_os.h"

/*
 * Driver switch:
 *   IMU_USE_JY62 = 1 -> JY62 0x55 protocol, USART3 DMA + IDLE + FreeRTOS queue
 *   IMU_USE_JY62 = 0 -> original USART3 DMA + IDLE driver
 */
#ifndef IMU_USE_JY62
#define IMU_USE_JY62 0
#endif

struct Imu
{
	float yaw;
	float roll;
	float pitch;
	float compensateZ;
	float compensatePitch;
};

extern SemaphoreHandle_t imu_mutex;
extern struct Imu imu_shared_data;
extern struct Imu imu;

extern float basic_p;
extern float basic_y;
extern float basic_r;

#define IMU_UART huart3

void imu_receive_init(void);
void IMU_CalibrateZero(float *yaw_out, float *pitch_out, float *roll_out);
float get_latest_yaw(void);
void IMU_RxIdleHandler(uint16_t Size);

/* IMU data-active check and serial recovery */
uint8_t IMU_IsDataActive(void);
uint8_t IMU_WaitData(uint32_t timeout_ms);
void IMU_Reinit(void);

#endif
