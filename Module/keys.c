#include "keys.h"


struct keys key[KEY_NUM] = {0};

void key_scan(void)
{
//按键扫描TIM6设置20ms一次回调

		key[0].pin_sta = HAL_GPIO_ReadPin(GPIOB,GPIO_PIN_12);
//		key[1].pin_sta = HAL_GPIO_ReadPin(GPIOB,GPIO_PIN_1);	
//		key[2].pin_sta = HAL_GPIO_ReadPin(GPIOB,GPIO_PIN_2);
//		key[3].pin_sta = HAL_GPIO_ReadPin(GPIOA,GPIO_PIN_0);


		for(int i = 0;i<KEY_NUM;i++)
		{
			
				switch(key[i].single_flag)
				{
					case 0:
					{
						if(key[i].pin_sta == 0) key[i].single_flag = 1;//第一次检测引脚是否置0
						key[i].long_flag = 0;
					}
					break;	
					case 1:
					{		

						if(key[i].pin_sta == 0) 
						{
							key[i].single_flag = 2;
						
						}
						else 
						{
							key[i].single_flag = 0;
						}
						//第二次检验（即10ms后）引脚若还是0，意味着确实按下
					}
					break;
					case 2:
					{
						key[i].long_flag ++;

						if(key[i].pin_sta == 1) //第三次检验引脚若是1表示按键松开
						{
							if(key[i].long_flag >= 80)
							{
								key[i].mode = 2;
								key[i].single_flag = 0;
								break;

							}							
							key[i].mode = 1;
							key[i].single_flag = 0;
						}
					}
					break;
				
				}	
		}
	
	
}






