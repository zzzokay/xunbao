/**
 * @file motor_task.c
 * @brief 电机驱动任务实现
 * 外部由maintask通过全局变量motor_all.Cspeed和motor_all.Gspeed传入目标速度，内部通过PID计算输出PWM值
 *
 * 速度映射到执行流程：
 * 	 1. 目标实控小车目标速度，gradual_cal()将目标小车速度进行->实控小车目标速度，motor_all.Cspeed->TC_speed。
 *	 2. 外环（转弯）(Go_Line()、Go_Angle())
 *   	 	- 巡线模式：输入为路径偏差，输出为速度差(Fspeed)
 *   		- 陀螺仪模式：输入为角度偏差，输出为速度差(GGspeed)
 *    	 	- 外环差值+实控小车目标速度为左右速度差值(TC_speed-FSpeed=motor_all.Lspeed/TC_speed+FSpeed=motor_all.Rspeed)
 *	 3. 内环差值换算为驱动板给定(handle_target_speed()):(motor_all.Lspeed->motor_L0.target)
 * 	 4. 内环PID(handle_pid_control())
 *  	  	- 输入：目标速度(motor_L0.target)
 *    		- 输出：增量式PID
 *    		- 输出：PWM值
 *
 */

#include "motor_task.h"
#include "encoder.h"
#include "motor.h"
#include "uart.h"
#include "speed_ctrl.h"
#include "pid.h"
#include "turn.h"
#include "scaner.h"
#include "bsp_linefollower.h"
#include "sin_generate.h"
#include "bsp_buzzer.h"
#include "openmv.h"
#include "map.h"
#include "QR.h"
#include "delay.h"
#include "bsp_led.h"
#include "math.h"
#include "barrier.h"
#include "K210.h"
#include "gray.h"
#include "Rec_usart.h"
#include "chassis_api.h"

/*全局变量定义区*/
TaskHandle_t motor_handler;       // 任务句柄
volatile uint8_t PIDMode;         // 当前PID模式
uint8_t Nosmall = 1;
int MOTOR_PWM_MAX = 9800;         // 最大PWM设定值
uint8_t open_qiang_jiao = 0;      // 墙角模式标志


/*主控制任务主体*/
/*
 * 功能：周期5ms的巡线闭环
 * 执行频率：每5ms执行一次
 */
void motor_task(void *pvParameters)
{
	portTickType xLastWakeTime;
	xLastWakeTime = xTaskGetTickCount();   	// 获取系统节拍

	// 初始化底盘API
	Chassis_Init();

	while (1)
	{
		//pid参数接口
		get_PIDdata();

		/*2. 获取电机速度，内核实数值及路程累计*/
		handle_motor_speed();

		/*3. 模式切换逻辑 - 确保模式切换平滑过渡*/
		handle_mode_switch(PIDMode);

		// 处理巡线模式
		handle_line_mode();  

		// 处理转弯模式
		handle_turn_mode();   

		// 处理陀螺仪模式
		handle_gyro_mode();   

		/*5. 处理目标速度 基于内环目标值计算*/
		handle_target_speed();

		/*6. 执行PID计算和电机驱动*/
		handle_pid_control();

		/*7. 底盘API周期更新 - 调用防游龙算法*/
		Chassis_Periodic_Update_5ms();

		// 调试信息（被注释掉的部分）
		/*陀螺仪模式*/ ///printf("Gyro:%.2f LSP:%.2f RSP:%.2f L0:%.2f L1:%.2f R0:%.2f R1:%.2f\r\n", imu.yaw,motor_all.Lspeed,motor_all.Rspeed,motor_L0.output,motor_L1.output,motor_R0.output,motor_R1.output);
		/*巡线值*/ printf_byte(Scaner.detail);
		/*左速度和右速度*///printf("Lspeed:%.2f Rspeed:%.2f\r\n", motor_all.Lspeed, motor_all.Rspeed);
		/*当前角度信息*/// printf("yaw:%.2f\troll:%.2f\tpitch:%.2f\tbasic:%.2f\r\n", imu.yaw, imu.roll, imu.pitch, basic_p);
		/*当前目的节点*/ //printf("%d\r\n",nodesr.nowNode.nodenum);
		/*巡线错误*/ //printf("前%d 左%d 右%d\r\n", Infrared_ahead, infrared.head_left, infrared.head_right);

		/*编码器测量值*/// printf("L0:%.1f,L1:%.1f,R0:%.1f,R1:%.1f,TargetL:%.1f,TargetR:%.1f\r\n", motor_L0.measure, motor_L1.measure, motor_R0.measure, motor_R1.measure ,motor_all.Lspeed, motor_all.Rspeed);
		/*编码器目标值*///printf("L0tar:%.2f\tL1tar:%.2f\tR0tar:%.2f\tR1tar:%.2f\r\n", motor_L0.target, motor_L1.target, motor_R0.target, motor_R1.target);
		/*编码器PID*/// printf("LSP:%.2f RSP:%.2f L0:%.2f L1:%.2f R0:%.2f R1:%.2f\r\n", motor_all.Lspeed,motor_all.Rspeed,motor_L0.output,motor_L1.output,motor_R0.output,motor_R1.output);

		/*打印识别结果*/ //printf("%d\r\n", Clue_Num);
		vTaskDelayUntil(&xLastWakeTime, (5 / portTICK_RATE_MS)); // 周期5ms，确保执行频率稳定
	}
}

/*处理电机速度及路程累计*/
/*
 * 功能：
 * 1. 获取编码器数值，计算电机速度
 * 2. 计算平均速度
 * 3. 累计行驶路程
 * 路程累计公式：
 * Distance = (编码器平均值 * 轮子直径 * π) / (编码器每圈脉冲数 * 减速比)
 * 参数中：
 * - 轮子直径：10.4cm
 * - 编码器每圈脉冲数：5720
 * - 减速比：0.362
 */
void handle_motor_speed(void)
{
	get_motor_speed();  // 获取编码器数值，计算电机速度

	// 计算四个电机平均速度
	motor_all.encoder_avg = (motor_L0.measure + motor_L1.measure + motor_R0.measure + motor_R1.measure) / 4;

	// 计算并累计行驶路程
	motor_all.Distance += ((motor_all.encoder_avg * 10.4f * PI)/5720.0f)/0.362f;
}



/*处理巡线模式主体*/
/*
 * 主要流程：
 * 1. 获取巡线error
 * 2. 计算平均速度
 * 3. 执行巡线任务
 */
void handle_line_mode(void)
{
	if (PIDMode == is_Line)
	{
		/* 获取巡线error - 显式传入循迹对象与参数 */
		getline_error_ex(&Scaner, scaner_set.EdgeIgnore, LEFT_RIGHT_LINE);

		// 平滑速度
		gradual_cal(&TC_speed, motor_all.Cspeed, motor_all.Cincrement, motor_all.CDOWNincrement);

		// 执行巡线任务
		Go_Line(TC_speed, &motor_all);
	}
	else
		motor_all.Cspeed = 0;  // 非巡线模式时，清除巡线速度
}

/*处理转弯模式主体*/
/*
 * 模式分类：
 * 1. 360度转圈
 * 2. 平台辅助转向（包含上桥下桥等）
 * 3. 普通角度转弯
 */
void handle_turn_mode(void)
{
	if (PIDMode == is_Turn)
	{
		if (Turn360_Flag)
		{
			Turn360Step();  // 执行360度转圈任务
		}
		// 平台辅助
		else if (nodesr.nowNode.function == UpStage || nodesr.nowNode.function == BSoutPole || nodesr.nowNode.function == BHM)
		{
			if (Stage_turn_Angle(angle.AngleT))  // 执行平台转弯
				gyroT_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0};  // 清零转弯PID
		}
		// 普通角度
		else if (Turn_Angle(angle.AngleT))  // 执行普通转弯
			gyroT_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0};  // 清零转弯PID
	}
}

/*处理陀螺仪模式主体*/
/*
 * 主要流程：
 * 1. 计算平均速度
 * 2. 按指定角度执行给定强 gyro
 */
void handle_gyro_mode(void)
{
	if (PIDMode == is_Gyro)
	{
		// 获取陀螺仪传感器数值用于判断完成：

		// 计算平均速度，左右电机速度和给减速速度，
		gradual_cal(&TG_speed, motor_all.Gspeed, motor_all.Gincrement, motor_all.GDOWNincrement);

		// 按指定角度执行给定强 gyro
		Go_Angle(angle.AngleG, TG_speed, &motor_all);
	}
	else
		motor_all.Gspeed = 0;  // 非陀螺仪模式时，清除陀螺仪给速
}

/*处理模式切换逻辑*/
/*
 * 功能：处理巡线和陀螺仪模式之间的切换
 * 通过记录前后 PIDMode，在函数内部完成巡线/陀螺仪状态迁移
 */
void handle_mode_switch(uint8_t target_mode)
{
	static uint8_t last_pid_mode = is_No;
	uint8_t current_pid_mode = target_mode;

	if (current_pid_mode != last_pid_mode)
	{
		/* 只在巡线/陀螺仪互切时迁移状态，避免外部再额外打标志 */
		if (last_pid_mode == is_Gyro && current_pid_mode == is_Line)
		{
			line_pid_obj = gyroG_pid;
			TC_speed = TG_speed;
			motor_all.Cspeed = motor_all.Gspeed;  // 将陀螺仪给速直接赋值给巡线给速，确保切换平滑
			gyroG_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			TG_speed = 0;
			motor_all.Gspeed = 0;// 清除陀螺仪模式的PID状态
		}
		else if (last_pid_mode == is_Line && current_pid_mode == is_Gyro)
		{
			gyroG_pid = line_pid_obj;
			TG_speed = TC_speed;
			motor_all.Gspeed = motor_all.Cspeed;  // 将巡线给速直接赋值给陀螺仪给速，确保切换平滑
			line_pid_obj = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			TC_speed = 0;
			motor_all.Cspeed = 0;
		}

		last_pid_mode = current_pid_mode;
	}
	
}

/*处理指示灯主体*/
/*
 * 功能：处理LED灯的闪烁任务状态指示
 * 闪烁频率：约2Hz，每100次循环切换一次状态，约0.5秒）
 */
void handle_led_mouse(void)
{
	static uint8_t mouse = 0;  		  	// 小车状态计数
	mouse++;
	if (mouse > 100)  // 每100次循环，约0.5秒）切换一次
	{
		mouse = 0;
		LED_C1_Toggle();  // 切换LED状态
	}
}

/*处理目标速度主体*/
/*
 * 功能：根据当前模式和路径节点设定的目标速度
 * 逻辑说明：
 * 1. 流水巡线模式：DownLiuShui == 1时，降低当前速度
 * 2. 普通模式：设置四个电机的目标速度
 */
void handle_target_speed(void)
{
	if(DownLiuShui)  // 流水巡线模式
	{
		// 前方速度超过流水阈值，强制先稳定
		motor_L0.target = motor_all.Lspeed * LiuShuiRate;
		motor_L1.target = motor_all.Lspeed;
		motor_R0.target = motor_all.Rspeed * LiuShuiRate;
		motor_R1.target = motor_all.Rspeed;
	}
	else  // 普通模式
	{
		// 四个电机设置同的目标速度
		motor_L0.target = motor_L1.target = motor_all.Lspeed;
		motor_R0.target = motor_R1.target = motor_all.Rspeed;
	}
}



/*获取编码器计数值*/
/*
 * 功能：获取编码器数值，计算电机速度
 * 执行流程：
 * 1. 获取四个定时器的计数值
 * 2. 计算差值作为本次获取的准
 * 3. 根据方向系数校正电机速度
 *
 * 引脚对应关系：
 * TIM1 -> 左前轮
 * TIM2 -> 左后轮
 * TIM3 -> 右前轮
 * TIM5 -> 右后轮
 */
void get_motor_speed()
{
	static uint16_t last_cnt[4] = {0};
	uint16_t curr_cnt[4];

	// 获取此刻计数值
	curr_cnt[0] = TIM1->CNT;
	curr_cnt[1] = TIM2->CNT;
	curr_cnt[2] = TIM3->CNT;
	curr_cnt[3] = TIM5->CNT;

	// 计算差值作为本次值，使用uint16_t自然溢出特性
	Speed[0] = (int16_t)(curr_cnt[0] - last_cnt[0]);
	Speed[1] = (int16_t)(curr_cnt[1] - last_cnt[1]);
	Speed[2] = (int16_t)(curr_cnt[2] - last_cnt[2]);
	Speed[3] = (int16_t)(curr_cnt[3] - last_cnt[3]);

	// 更新上次值
	for(int i=0; i<4; i++) last_cnt[i] = curr_cnt[i];

	// 计算电机速度，测量值及方向校正
	motor_L0.measure = (float)Speed[0];  // 左前轮
	motor_L1.measure = (float)Speed[1];  // 左后轮
	motor_R0.measure = -(float)Speed[2];  // 右前轮
	motor_R1.measure = -(float)Speed[3];  // 右后轮

}

/*处理PID计算和电机驱动*/
/*
 * 功能：执行增量式PID计算并输出PWM信号
 * 执行条件：强驱动模式（PIDMode != is_Free）
 * 主要流程：
 * 1. 计算四个电机PID驱动
 * 2. 设置驱动PWM值
 */
void handle_pid_control(void)
{
	if (PIDMode != is_Free)  // 非强驱动模式时执行PID计算
	{
		/*PID计算*/
		incremental_PID(&motor_L0, &motor_pid_paramL0);  // 左前轮
		incremental_PID(&motor_L1, &motor_pid_paramL1);  // 左后轮
		incremental_PID(&motor_R0, &motor_pid_paramR0);  // 右前轮
		incremental_PID(&motor_R1, &motor_pid_paramR1);  // 右后轮

		/*设置驱动PWM值*/
		//motor_set_pwm(1, (int32_t)motor_L0.output);  // 左前轮
		//motor_set_pwm(2, (int32_t)motor_L1.output);  // 左后轮
 		//motor_set_pwm(3, (int32_t)motor_R0.output);  // 右前轮
		//motor_set_pwm(4, (int32_t)motor_R1.output);  // 右后轮
	}
}

/*创建电机任务*/
/*
 * 功能：创建电机控制任务
 * 参数说明：
 * - 创建任务：motor_task
 * - 任务名称："motor_task"
 * - 栈空间大小：motor_size，默认设置为512。
 * - 优先级：motor_task_priority，默认设置为10。
 * - 任务句柄：motor_handler
 */
void motor_task_create(void)
{
	xTaskCreate((TaskFunction_t)motor_task,  	  // 任务函数
			(const char *)"motor_task",  	  // 任务名称
			(uint32_t)motor_size,  	  // 任务栈大小
			(void *)NULL,  		  // 传递给任务函数的参数指针
			(UBaseType_t)motor_task_priority, // 任务优先级
			(TaskHandle_t *)&motor_handler);  // 任务句柄
}