/*
 * IMU driver.
 *
 * IMU_USE_JY62 == 1: JY62 0x55 protocol over USART3 DMA + IDLE plus a
 *                    FreeRTOS queue task.
 * IMU_USE_JY62 == 0: original USART3 DMA + IDLE parser.
 */
#include "imu.h"
#include "usart.h"
#include "main.h"
#include "queue.h"
#include "string.h"

#if !IMU_USE_JY62
#include "filter.h"
#include "bsp_buzzer.h"
#include "delay.h"
#endif

struct Imu imu;
struct Imu imu_shared_data;
SemaphoreHandle_t imu_mutex;

float basic_p = 0;
float basic_y = 0;
float basic_r = 0;

#if IMU_USE_JY62
#define JY62_FRAME_LEN      11U
#define JY62_DMA_LEN        33U
#define JY62_HEADER         0x55U
#define JY62_FRAME_ANGLE    0x53U

/* JY62 sign convention from the reference driver. Flip these macros if the
 * module is mounted in a different orientation. */
#define JY62_ROLL_SIGN      1.0f
#define JY62_PITCH_SIGN     1.0f
#define JY62_YAW_SIGN       1.0f

typedef struct
{
	uint8_t receive_buffer[JY62_FRAME_LEN];
} JY62_package;

static JY62_package JY62_uart1 = {0};
static uint8_t JY62_dma_buf[JY62_DMA_LEN] = {0};
static uint8_t JY62_rx_buf[JY62_DMA_LEN] = {0};
static uint8_t JY62_rx_len = 0;
static QueueHandle_t JY62_queue = NULL;

static uint8_t JY62_frame_valid(const uint8_t *frame)
{
	uint8_t sum = 0;

	for (uint8_t i = 0; i < JY62_FRAME_LEN - 1U; i++)
	{
		sum += frame[i];
	}

	return (frame[0] == JY62_HEADER) &&
		   (sum == frame[JY62_FRAME_LEN - 1U]);
}

static float JY62_raw_to_angle(int16_t raw)
{
	return (float)raw * (180.0f / 32768.0f);
}

static void JY62_deal(JY62_package *pkg)
{
	const uint8_t *frame = pkg->receive_buffer;

	if (!JY62_frame_valid(frame))
	{
		return;
	}

	if (frame[1] == JY62_FRAME_ANGLE)
	{
		int16_t raw_roll  = (int16_t)(((uint16_t)frame[3] << 8U) | frame[2]);
		int16_t raw_pitch = (int16_t)(((uint16_t)frame[5] << 8U) | frame[4]);
		int16_t raw_yaw   = (int16_t)(((uint16_t)frame[7] << 8U) | frame[6]);
		float yaw;

		imu.roll  = JY62_ROLL_SIGN * JY62_raw_to_angle(raw_roll);
		imu.pitch = JY62_PITCH_SIGN * JY62_raw_to_angle(raw_pitch);

		yaw = JY62_YAW_SIGN * JY62_raw_to_angle(raw_yaw);
		if (yaw > 180.0f)
		{
			yaw -= 360.0f;
		}
		else if (yaw <= -180.0f)
		{
			yaw += 360.0f;
		}

		imu.yaw = yaw - basic_y;
		if (imu.yaw > 180.0f)
		{
			imu.yaw -= 360.0f;
		}
		else if (imu.yaw <= -180.0f)
		{
			imu.yaw += 360.0f;
		}
	}
}

static void JY62_QueueReceiveTask(void *pvParameters)
{
	JY62_package copy;

	(void)pvParameters;

	for (;;)
	{
		if (xQueueReceive(JY62_queue, &copy, portMAX_DELAY) == pdTRUE)
		{
			JY62_deal(&copy);

			if (imu_mutex != NULL &&
				xSemaphoreTake(imu_mutex, portMAX_DELAY) == pdTRUE)
			{
				imu_shared_data = imu;
				xSemaphoreGive(imu_mutex);
			}
		}

		vTaskDelay(pdMS_TO_TICKS(10));
	}
}

void IMU_RxIdleHandler(uint16_t Size)
{
	BaseType_t higher_priority_task_woken = pdFALSE;

	if (HAL_UARTEx_GetRxEventType(&IMU_UART) == HAL_UART_RXEVENT_HT)
	{
		/* Half-transfer: DMA is still writing to the buffer, leave it alone. */
		return;
	}

	if (Size == 0U)
	{
		HAL_UARTEx_ReceiveToIdle_DMA(&IMU_UART, JY62_dma_buf, JY62_DMA_LEN);
		return;
	}

	if (JY62_rx_len + Size > JY62_DMA_LEN)
	{
		JY62_rx_len = 0U;
	}

	memcpy(&JY62_rx_buf[JY62_rx_len], JY62_dma_buf, Size);
	JY62_rx_len += (uint8_t)Size;

	while (JY62_rx_len >= JY62_FRAME_LEN)
	{
		if (JY62_rx_buf[0] != JY62_HEADER)
		{
			memmove(JY62_rx_buf, &JY62_rx_buf[1], JY62_rx_len - 1U);
			JY62_rx_len -= 1U;
			continue;
		}

		if (JY62_frame_valid(JY62_rx_buf))
		{
			memcpy(JY62_uart1.receive_buffer, JY62_rx_buf, JY62_FRAME_LEN);
			if (JY62_queue != NULL)
			{
				xQueueOverwriteFromISR(JY62_queue, &JY62_uart1,
									   &higher_priority_task_woken);
			}
			memmove(JY62_rx_buf, &JY62_rx_buf[JY62_FRAME_LEN],
					JY62_rx_len - JY62_FRAME_LEN);
			JY62_rx_len -= JY62_FRAME_LEN;
		}
		else
		{
			/* False 0x55 header: drop one byte and keep searching. */
			memmove(JY62_rx_buf, &JY62_rx_buf[1], JY62_rx_len - 1U);
			JY62_rx_len -= 1U;
		}
	}

	memset(JY62_dma_buf, 0, sizeof(JY62_dma_buf));
	HAL_UARTEx_ReceiveToIdle_DMA(&IMU_UART, JY62_dma_buf, JY62_DMA_LEN);

	portYIELD_FROM_ISR(higher_priority_task_woken);
}
#else
#define BUFFER_SIZE 33

static uint8_t imu_rx_len = 0;
static uint8_t imu_rx_buf[BUFFER_SIZE] = {0};
#endif

#if IMU_USE_JY62
void imu_receive_init(void)
{
	imu_mutex = xSemaphoreCreateMutex();
	if (imu_mutex == NULL)
	{
		/* FreeRTOS heap exhausted; stay here so the fault is visible. */
		for (;;)
		{
		}
	}

	JY62_queue = xQueueCreate(1, sizeof(JY62_package));
	if (JY62_queue != NULL)
	{
		xTaskCreate(JY62_QueueReceiveTask, "JY62_rx", 256, NULL, 3, NULL);
	}

	memset(&JY62_uart1, 0, sizeof(JY62_uart1));
	memset(JY62_dma_buf, 0, sizeof(JY62_dma_buf));
	memset(JY62_rx_buf, 0, sizeof(JY62_rx_buf));
	JY62_rx_len = 0U;

	__HAL_UART_CLEAR_OREFLAG(&IMU_UART);
	HAL_UARTEx_ReceiveToIdle_DMA(&IMU_UART, JY62_dma_buf, JY62_DMA_LEN);
}
#else
void imu_receive_init(void)
{
	imu_mutex = xSemaphoreCreateMutex();
	if (imu_mutex == NULL)
	{
		buzzer_on();
		delay_ms(2000);
	}

	HAL_UART_Receive_DMA(&IMU_UART, imu_rx_buf, BUFFER_SIZE);
	__HAL_UART_ENABLE_IT(&IMU_UART, UART_IT_IDLE);
}
#endif

#if IMU_USE_JY62
void USART3_IRQHandler(void)
{
	if (__HAL_UART_GET_FLAG(&IMU_UART, UART_FLAG_ORE) != RESET)
	{
		__HAL_UART_CLEAR_OREFLAG(&IMU_UART);
	}

	HAL_UART_IRQHandler(&IMU_UART);
}
#else
void USART3_IRQHandler(void)
{
	uint32_t flag_idle = 0;

	flag_idle = __HAL_UART_GET_FLAG(&IMU_UART, UART_FLAG_IDLE);
	if (flag_idle != RESET)
	{
		__HAL_UART_CLEAR_IDLEFLAG(&IMU_UART);

		HAL_UART_DMAStop(&IMU_UART);
		uint32_t temp = __HAL_DMA_GET_COUNTER(&hdma_usart3_rx);
		imu_rx_len = BUFFER_SIZE - temp;

		if (imu_rx_buf[0] == 0x55)
		{
			uint8_t sum = 0;
			for (uint8_t i = 0; i < 10; i++)
			{
				sum += imu_rx_buf[i];
			}

			if (sum == imu_rx_buf[10])
			{
				if (imu_rx_buf[2] == 0x01)
				{
					imu.roll   = 180.0 * (short)((imu_rx_buf[5] << 8) | imu_rx_buf[4]) / 32768.0;
					imu.yaw    = 180.0 * (short)((imu_rx_buf[9] << 8) | imu_rx_buf[8]) / 32768.0;
					imu.pitch  = -180.0 * (short)((imu_rx_buf[7] << 8) | imu_rx_buf[6]) / 32768.0;

					imu.yaw -= basic_y;

					if (filter_Open)
					{
						imu.pitch = filter(imu.pitch);
						imu.roll  = filter(imu.roll);
						imu.yaw   = filter(imu.yaw);
					}

					BaseType_t xHigherPriorityTaskWoken = pdFALSE;
					if (imu_mutex != NULL &&
						xSemaphoreTakeFromISR(imu_mutex, &xHigherPriorityTaskWoken) == pdTRUE)
					{
						imu_shared_data = imu;
						xSemaphoreGiveFromISR(imu_mutex, &xHigherPriorityTaskWoken);
					}
					portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
				}
			}
		}

		memset(imu_rx_buf, 0, imu_rx_len);
		imu_rx_len = 0;
	}

	HAL_UART_Receive_DMA(&IMU_UART, imu_rx_buf, BUFFER_SIZE);
	__HAL_UART_ENABLE_IT(&IMU_UART, UART_IT_IDLE);
	HAL_UART_IRQHandler(&IMU_UART);
}
#endif

#if IMU_USE_JY62
void IMU_Reinit(void)
{
	HAL_NVIC_DisableIRQ(USART3_IRQn);
	HAL_UART_DMAStop(&IMU_UART);

	memset(&JY62_uart1, 0, sizeof(JY62_uart1));
	memset(JY62_dma_buf, 0, sizeof(JY62_dma_buf));
	memset(JY62_rx_buf, 0, sizeof(JY62_rx_buf));
	JY62_rx_len = 0U;

	__HAL_UART_CLEAR_OREFLAG(&IMU_UART);
	__HAL_UART_CLEAR_NEFLAG(&IMU_UART);
	__HAL_UART_CLEAR_FEFLAG(&IMU_UART);
	HAL_UARTEx_ReceiveToIdle_DMA(&IMU_UART, JY62_dma_buf, JY62_DMA_LEN);

	HAL_NVIC_EnableIRQ(USART3_IRQn);
}
#else
void IMU_Reinit(void)
{
	HAL_NVIC_DisableIRQ(USART3_IRQn);
	HAL_UART_DMAStop(&IMU_UART);

	__HAL_UART_CLEAR_OREFLAG(&IMU_UART);
	__HAL_UART_CLEAR_NEFLAG(&IMU_UART);
	__HAL_UART_CLEAR_FEFLAG(&IMU_UART);

	memset(imu_rx_buf, 0, sizeof(imu_rx_buf));
	imu_rx_len = 0;

	HAL_UART_Receive_DMA(&IMU_UART, imu_rx_buf, BUFFER_SIZE);
	__HAL_UART_ENABLE_IT(&IMU_UART, UART_IT_IDLE);
	HAL_NVIC_EnableIRQ(USART3_IRQn);
}
#endif

void IMU_CalibrateZero(float *yaw_out, float *pitch_out, float *roll_out)
{
	float sum_yaw = 0;
	float sum_pitch = 0;
	float sum_roll = 0;
	struct Imu imu_copy;

	for (uint8_t i = 0; i < 10; i++)
	{
		vTaskDelay(pdMS_TO_TICKS(20));

		if (imu_mutex != NULL &&
			xSemaphoreTake(imu_mutex, portMAX_DELAY) == pdTRUE)
		{
			imu_copy = imu_shared_data;
			xSemaphoreGive(imu_mutex);
		}
		else
		{
			continue;
		}

		sum_yaw   += imu_copy.yaw;
		sum_pitch += imu_copy.pitch;
		sum_roll  += imu_copy.roll;
	}

	if (yaw_out)   *yaw_out   = sum_yaw / 10.0f;
	if (pitch_out) *pitch_out = sum_pitch / 10.0f;
	if (roll_out)  *roll_out  = sum_roll / 10.0f;
}

float get_latest_yaw(void)
{
	struct Imu temp;

	if (imu_mutex != NULL)
	{
		xSemaphoreTake(imu_mutex, portMAX_DELAY);
		temp = imu_shared_data;
		xSemaphoreGive(imu_mutex);
		return temp.yaw;
	}

	return 0;
}

uint8_t IMU_IsDataActive(void)
{
	struct Imu temp;

	if (imu_mutex == NULL)
	{
		return 0;
	}
	if (xSemaphoreTake(imu_mutex, 20) != pdTRUE)
	{
		return 0;
	}

	temp = imu_shared_data;
	xSemaphoreGive(imu_mutex);

	return (temp.yaw != 0.0f) || (temp.pitch != 0.0f) || (temp.roll != 0.0f);
}

uint8_t IMU_WaitData(uint32_t timeout_ms)
{
	uint32_t waited = 0;

	while (waited < timeout_ms)
	{
		if (IMU_IsDataActive())
		{
			return 1;
		}
		vTaskDelay(pdMS_TO_TICKS(50));
		waited += 50;
	}

	return 0;
}
