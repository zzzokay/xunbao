每次用cubemx生成后
1、main.c里面注释下面这一段
//void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
//{
//  /* USER CODE BEGIN Callback 0 */
//  /* USER CODE END Callback 0 */
//  if (htim->Instance == TIM14)
//  {
//    HAL_IncTick();
//  }
//  /* USER CODE BEGIN Callback 1 */

//  /* USER CODE END Callback 1 */
//}

2、stm32f7xx_it.c里面注释一些定义冲突的中断