#include "interrupt_router.h"
#include "usart.h"
#include "imu.h"
#include "Rec_usart.h"

/**
 * @brief HAL UART idle-line DMA event callback (overrides weak default).
 *        Routes the event to the matching module.
 */
void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t Size)
{
#if IMU_USE_JY62
    if (huart == &IMU_UART)    /* USART3 JY62 DMA + IDLE */
    {
        IMU_RxIdleHandler(Size);
        return;
    }
#endif

    if (huart == &UART)        /* huart4 debug command UART */
    {
        RecUsart_RxIdleHandler(Size);
    }
}
