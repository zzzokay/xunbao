#include "K210.h"
#include "stdio.h"
#include "barrier.h"
#include "usart.h"
#include "map.h"
#include "string.h"
#include "QR.h"
#include "openmv.h"
//#include "Rudder_control.h"



volatile uint8_t Clue_Num = 0;
volatile uint8_t K210_Rece = 0;
uint8_t K210_RxTemp_L = 0;
volatile uint8_t Maxicam_Rx = 0;

//切换成功标志位（由USART6接收中断更新）
volatile uint8_t open_QR_mode_sign=2;
volatile uint8_t open_OCR_mode_sign=2;
volatile uint8_t open_COLOR_L_mode_sign=2;
volatile uint8_t open_COLOR_R_mode_sign=2;

#define REQUIRED_CONSECUTIVE 3  // 需要连续相同的次数


/*使能Maxicam*/
void Maxicam_Enable(void)
{
	HAL_UART_Receive_IT(&huart6, (uint8_t *)&Maxicam_Rx, 1);
}

/* 打开QR模式（带0x94确认）*/
void open_QR_mode(void)
{
    uint8_t cmd = 0x11;  // QR模式指令码
    uint8_t retry = 3;//有限次数的确认
    open_QR_mode_sign = 1;
    while(retry--) {
        // 发送指令
        HAL_UART_Transmit(&huart6, &cmd, 1, 100);
			  HAL_Delay(20);
        if(open_QR_mode_sign == 0) break;
        HAL_Delay(30); // 短间隔重试
    }

}

/* 打开OCR模式（带0x94确认）*/
void open_OCR_mode(void)
{
    uint8_t cmd[] = {0x22};
    uint8_t retry = 3;
		open_OCR_mode_sign=1;
    
    while(retry--) {
				HAL_UART_Transmit(&huart6, cmd, sizeof(cmd), 100);
				HAL_Delay(20);
        if(open_OCR_mode_sign==0) break;       
        HAL_Delay(30);
    }
}


/* 关闭设备（带0x94确认）*/
void close_Maxicam(void)
{
    uint8_t cmd = 0x66;
    HAL_UART_Transmit(&huart6, &cmd, 1, 100);
    HAL_UART_Transmit(&huart6, &cmd, 1, 100);
    HAL_UART_Transmit(&huart6, &cmd, 1, 100);
	HAL_UART_Transmit(&huart6, &cmd, 1, 100);
}

// QR码数据统计函数
void Process_QR_Data(uint8_t line, uint8_t stageA, uint8_t stageB) {
    static uint8_t last_line = 0, last_A = 0, last_B = 0;
    static uint8_t consecutive_count = 0;
    
    // 检查是否与上次相同
    if(line == last_line && stageA == last_A && stageB == last_B) {
        consecutive_count++;
    } else {
        consecutive_count = 1;
        last_line = line;
        last_A = stageA;
        last_B = stageB;
    }
    
    // 达到连续次数要求
    if(consecutive_count >= REQUIRED_CONSECUTIVE) {
        flag_line_clue = line;
        flag_clue_stage_A = stageA;
        flag_clue_stage_B = stageB;
//        buzzer_flag = 1;
        get_cude = 1;
        close_Maxicam();
        consecutive_count = 0; // 重置计数
    }
}

// OCR数据统计函数
void Process_OCR_Data(uint8_t ocr_value) {
    static uint8_t last_value = 0;
    static uint8_t consecutive_count = 0;
  		if(ocr_value<=6 && ocr_value>=0)	
			{
					// 检查是否与上次相同
					if(ocr_value == last_value) {
							consecutive_count++;
					} else {
							consecutive_count = 1;
							last_value = ocr_value;
					}
					
					// 达到连续次数要求
					if(consecutive_count >= REQUIRED_CONSECUTIVE) {
							Clue_Num = last_value;
							K210_Rece = 1;
				//			close_Maxicam();
							consecutive_count = 0; // 重置计数
							ocr_value=0;
							last_value = 0;
					}
			}
}

// 颜色数据统计
void Process_COLOR_Data(uint8_t color_value) {
    static uint8_t last_color = 0;       // 记录上一次识别的颜色值
    static uint8_t consecutive_count = 0; // 连续识别相同颜色的次数
		
			// 检查当前颜色值是否与上一次相同
			if (color_value == last_color) {
					consecutive_count++;  // 连续相同，计数递增
			} else {
					consecutive_count = 1; // 不同，重置计数为1
					last_color = color_value; // 更新上次颜色值
			}

			if (consecutive_count >= REQUIRED_CONSECUTIVE) {
					if (COLOR_flag == 1) {
							Color_Left = color_value;  
					} else if (COLOR_flag == 2) {
							Color_Right = color_value; 
					}
					COLOR_flag = 0;
					close_Maxicam(); 
					consecutive_count = 0; // 重置计数，准备下一次识别

			}
		
		
}

/*
 * 逐字节解析MaixCam数据，由HAL_UART_RxCpltCallback()调用。
 * QR:    0x01 0x01 + 3字节ASCII数字 + 0x0A
 * OCR:   0x02 0x02 + 1字节ASCII数字 + 0x0A
 * COLOR: 0x03 0x03 + 1字节ASCII数字 + 0x0A
 */
void Maxicam_ProcessRxByte(uint8_t rx_byte)
{
    static uint8_t flag = 0;
    static uint8_t frame_type = 0;
    static uint8_t data_buffer[3];
    static uint8_t data_index = 0;

    /* 模式切换确认字节不参与帧解析 */
    if (rx_byte == 0x94)
    {
        if (open_QR_mode_sign == 1)
            open_QR_mode_sign = 0;
        if (open_OCR_mode_sign == 1)
            open_OCR_mode_sign = 0;
        if (open_COLOR_L_mode_sign == 1)
            open_COLOR_L_mode_sign = 0;
        if (open_COLOR_R_mode_sign == 1)
            open_COLOR_R_mode_sign = 0;

        flag = 0;
        frame_type = 0;
        data_index = 0;
        return;
    }

    if (flag == 0)
    {
        if (rx_byte >= 0x01 && rx_byte <= 0x03)
        {
            frame_type = rx_byte;
            flag = 1;
        }
        return;
    }

    if (flag == 1)
    {
        if (rx_byte == frame_type)
        {
            flag = 2;
            data_index = 0;
            memset(data_buffer, 0, sizeof(data_buffer));
        }
        else
        {
            flag = 0;
            frame_type = 0;
        }
        return;
    }

    if (rx_byte != 0x0A)
    {
        if (data_index < sizeof(data_buffer))
            data_buffer[data_index++] = rx_byte;
        else
        {
            flag = 0;
            frame_type = 0;
            data_index = 0;
        }
        return;
    }

    if (frame_type == 1 && data_index == 3 &&
        data_buffer[0] >= '0' && data_buffer[0] <= '9' &&
        data_buffer[1] >= '0' && data_buffer[1] <= '9' &&
        data_buffer[2] >= '0' && data_buffer[2] <= '9')
    {
        Process_QR_Data(data_buffer[0] - '0', data_buffer[1] - '0', data_buffer[2] - '0');
    }
    else if (frame_type == 2 && data_index == 1 &&
             data_buffer[0] >= '0' && data_buffer[0] <= '6')
    {
        /* QR数字与当前实际平台一致时才接收OCR线索 */
        if ((nodes.nowNode.nodenum == P5 && flag_clue_stage_A == 5) ||
            (nodes.nowNode.nodenum == P6 && flag_clue_stage_A == 6) ||
            (nodes.nowNode.nodenum == P7 && flag_clue_stage_B == 7) ||
            (nodes.nowNode.nodenum == P8 && flag_clue_stage_B == 8))
        {
            Process_OCR_Data(data_buffer[0] - '0');
        }
    }
    else if (frame_type == 3 && data_index == 1 &&
             data_buffer[0] >= '1' && data_buffer[0] <= '3')
    {
        Process_COLOR_Data(data_buffer[0] - '0');
    }

    flag = 0;
    frame_type = 0;
    data_index = 0;
}



/*左K210接收中断*/
//void USART2_IRQHandler(void)
//{
//	HAL_UART_IRQHandler(&huart2);

//	static uint8_t flag = 0;
//	if (K210_RxTemp_L == 0xff && flag == 0)
//		flag = 1;
//	else if (K210_RxTemp_L == 0xff && flag == 1)
//		flag = 2;
//	else if (flag == 2 && K210_RxTemp_L != 0xff && K210_RxTemp_L != 0x0a)
//	{
//		Clue_Num = K210_RxTemp_L;
//		if ((nodesr.nowNode.nodenum == P1 && (K210_RxTemp_L == 3 || K210_RxTemp_L == 4)) ||
//			(nodesr.nowNode.nodenum == P3 && (K210_RxTemp_L == 5 || K210_RxTemp_L == 6)) ||
//			(nodesr.nowNode.nodenum == P4 && (K210_RxTemp_L == 5 || K210_RxTemp_L == 6)) ||
//			(nodesr.nowNode.nodenum == P5 && (K210_RxTemp_L == 7 || K210_RxTemp_L == 8)) ||
//			(nodesr.nowNode.nodenum == P6 && (K210_RxTemp_L == 7 || K210_RxTemp_L == 8)))
//		{
//			Clue_Num = K210_RxTemp_L;
//			K210_Rece = 1;
//			flag = 0;
//			close_K210();
//		}
//	}

//	HAL_UART_Receive_IT(&huart2, &K210_RxTemp_L, 1);
//}
