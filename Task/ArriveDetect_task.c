#include "ArriveDetect_task.h"
#include "scaner.h"
#include "map.h"
#include "usart.h"
#include "imu.h"
#include "turn.h"
#include "stdio.h"

uint8_t  mul2sing = 0 ,sing2mul = 0;
void arrive_detect_task(void *pvParameters)
{
	 while (1)
    {
        // 等待主任务唤醒我
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
		// 每次检测前清除状态
        mul2sing = 0;
        sing2mul = 0;
        // --- 进行节点检测 ---
        Cross_getline();
        while (!deal_arrive())
        {
            vTaskDelay(2);
            Cross_getline();
			if(((nodesr.nowNode.flag&RESTMPUZ) == RESTMPUZ))		//陀螺仪校正
				{
					if((Cross_Scaner.detail & 0X0180) == 0X0180)		//如果在最中间位置
					{	
						mpuZreset(get_latest_yaw(), nodesr.nowNode.angle);     	//获取补偿角Z;
					}
				}
        }

        // 标记到达
        nodesr.flag |= 0x04;

        send_play_specified_command(13); // 播报
        scaner_set.CatchsensorNum = 0;

        // 通知 main_task 可以继续
        xTaskNotifyGive(main_handler); // 或者你也可以保留一个 main_task 的句柄


    }
	
}
/*
	1	六号
	2	五号
	3	四号
	4	三号
	5	二号
	6	直立
	7	准备
	8	绿
	9	宝物
	10	黄
	11	红
	12	七号
	13	路口
	14	八号
	15	错误
	16  A0
	17  A1
	18  A2
	19  A3
	20  A4
	21  A5
	22  A6
	23  B0
	24  B1
	25  B2
	26  B3
	27  B4
	28  B5
	29  B6
*/
void send_play_specified_command(uint8_t index)
{
	// 7E 05 41 00(歌曲高位) 01(歌曲低位) 45(校验和) EF
	uint8_t data[7] = {0x7e, 0x05, 0x41, 0x00, 0x00, 0x00, 0xef};
	data[4] = index;
	uint8_t sum = data[1] ^ data[2] ^ data[3] ^ data[4];
	data[5] = sum;
	for (uint8_t i = 0; i < 7; i++)
	{
		HAL_UART_Transmit(&huart8, &data[i], 1, 0xFFFF);
	}
}

/*判断节点*/
//// GCC/ARMCC 支持内建 popcount
//static inline uint8_t count_bits(uint8_t x) {
//#if defined(__GNUC__) || defined(__ARMCC_VERSION)
//    return __builtin_popcount(x);
//#else
//    // 兼容其他编译器
//    uint8_t count = 0;
//    while (x) {
//        count += x & 1;
//        x >>= 1;
//    }
//    return count;
//#endif
//}

uint8_t deal_arrive()
{				
	register uint8_t lnum = 0, i = 0;
	register uint16_t seed = 0;

	if ((nodesr.nowNode.flag & DLEFT) == DLEFT)  //左半边
	{
		//左边6个灯任意5个亮即可
		if (Cross_Scaner.ledNum>=5)
		{
			seed = 0X8000;
			for (i = 0; i<6; i++)
			{
				if (Cross_Scaner.detail & seed)
					++lnum;
				if (lnum >= 5)
				{
					return 1;
				}
				seed >>= 1;
			}
			lnum = 0;
		}
	}
	if ((nodesr.nowNode.flag & DRIGHT) == DRIGHT)//右半边
	{    	
		if (Cross_Scaner.ledNum >= 5)
		{
			seed = 0X0001;
			for (i = 0; i<6; i++)
			{
				if (Cross_Scaner.detail & seed)
					++lnum;
				if (lnum >= 5)
				{
					return 1;
				}
				seed <<= 1;
			}
			lnum = 0;
		}
	}
	if ((nodesr.nowNode.flag & CLEFT) == CLEFT)//左分岔路
	{
		//左边数起第二、第三个灯任意一个亮即可
		 if( (Cross_Scaner.ledNum>=4&&Cross_Scaner.ledNum<=7) && ((Cross_Scaner.detail&0x4000)|(Cross_Scaner.detail&0x2000)) )//
		 {
			return 1;
		}
	}
	if ((nodesr.nowNode.flag & MCLEFT) == MCLEFT)//左分岔路
	{
		//左边数起第一个灯亮即可
		 if( (Cross_Scaner.ledNum>=4&&Cross_Scaner.ledNum<=7) && (Cross_Scaner.detail&0x8000) )
		{
			return 1;
		}
	}
	if ((nodesr.nowNode.flag & MCRIGHT) == MCRIGHT)//左分岔路
	{
		//右边数起第一个灯亮即可
		 if( (Cross_Scaner.ledNum>=4&&Cross_Scaner.ledNum<=7) && (Cross_Scaner.detail&0x0001) )
		{
			return 1;
		}
	}
	if ((nodesr.nowNode.flag & CRIGHT) == CRIGHT)//右分岔路
	{
		 if( (Cross_Scaner.ledNum>=4&&Cross_Scaner.ledNum<=7) && (Cross_Scaner.detail&0xc) )//右起2和3灯亮
		{
			return 1;
		}
	}
	if ((nodesr.nowNode.flag & MORELED) == MORELED)
	{
		 if( (Cross_Scaner.ledNum>=5) )//5个灯以上亮
		{
			return 1;
		}
	}
	if ((nodesr.nowNode.flag & AWHITE) == AWHITE)//全白
	{
		 if((Cross_Scaner.ledNum>=10&&(Cross_Scaner.detail&0x1FF8)==0x1FF8))
		{
			return 1;
		}
	}
	if ((nodesr.nowNode.flag & MUL2SING) == MUL2SING)//三分岔路
	{
		if (Cross_Scaner.lineNum > 1 && Cross_Scaner.ledNum >= 4)
			++mul2sing;
		if (mul2sing > 4 && Cross_Scaner.lineNum == 1) //线数目由多变成一条
		{
			mul2sing = sing2mul = 0;
			return 1;
		}
	}
	if ((nodesr.nowNode.flag & MUL2MUL) == MUL2MUL)  //线数目由多条变多条
	{
		if (Cross_Scaner.lineNum > 1 && Cross_Scaner.ledNum >= 4)
			++mul2sing;
		if (mul2sing > 4 && (Cross_Scaner.lineNum == 1 || Cross_Scaner.ledNum <=3 ))
			++sing2mul;
		if (sing2mul > 4 && Cross_Scaner.lineNum > 1 && Cross_Scaner.ledNum >= 4)
		{
			mul2sing = sing2mul = 0;
			return 1;
		}
	}
	
	return 0;
}