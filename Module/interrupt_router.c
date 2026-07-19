#include "interrupt_router.h"
#include "usart.h"
#include "imu.h"
#include "Rec_usart.h"

/**
 * @brief HAL UART idle-line DMA event callback (overrides weak default).
 *        根据 UART 实例将事件路由到对应模块的处理函数。
 */
void HAL_UARTEx_RxEventCallback(UART_HandleTypeDef *huart, uint16_t Size)
{
    if (huart == &IMU_UART)
    {
        IMU_RxIdleHandler(Size);
    }
    else if (huart == &UART)    /* huart4 — 调试串口命令 */
    {
        RecUsart_RxIdleHandler(Size);
    }
}
