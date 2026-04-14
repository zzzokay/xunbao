# xunbao
4.14（张东骏）
加入command.c作为调试串口缓存区
发现：每次mx生成完都要注释掉main的定时器中断回调，和stm32f7xx.....里的USART3_IRQHandler(void)
删掉了stm32....里的void UART5_IRQHandler(void)的标志位判定，改用hal自带的api，HAL_UARTEx_ReceiveToIdle_IT
加入串口1，4，7
测试：串口5发送正常，但无法进入中断handler;     使用串口7甚至无法发送？
    串口4发送成功；    无法进入中断，仍然接收不成功？    改用HAL_UART_Receive_IT；   依然接收不成功？疑似杜邦线问题？（发现：中断里没重新调用）
    蜂鸣档测完，杜邦线正常
    成功了：改变了串口，改变了api；
    oka发现了就是串口问题，现在改回 HAL_UART_Receive_IT(&huart4,Rx_data,BUFFER_SIZE_rec) 可以正常收发
    再试一次串口7。。。。坏了