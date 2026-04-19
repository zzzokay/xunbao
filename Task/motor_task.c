/**
 * @file motor_task.c
 * @brief 电机控制任务实现
 * 外部（maintask）通过全局变量motor_all.Cspeed或motor_all.Gspeed设置目标速度，内部通过PID计算输出电机PWM值
 * 
 * 速度映射到电机流程：
 * 
 * 1. 计算实际小车目标速度（gradual_cal()）：目标小车速度渐变->实际小车目标速度（motor_all.Cspeed->TC_speed）
 *
 * 2. 外环（转向）控制(Go_Line()、Go_Angle())
 *    - 循迹模式：输入为路径误差，输出：左右轮速度差(Fspeed)
 *    - 陀螺仪模式：输入为角度偏差，输出：左右轮速度差(GGspeed)
 *    - 外环输出值+实际小车目标速度为内环输入值(TC_speed-FSpeed=motor_all.Lspeed/TC_speed+FSpeed=motor_all.Rspeed)	  
 * 	
 * 3. 内环输入值简单变换（处理流水）(handle_target_speed()):(motor_all.Lspeed->motor_L0.target)	
 *
 * 4. 内环控制(handle_pid_control())
 *    - 输入：轮目标速度(motor_L0.target)
 *    - 处理：位置式PID
 *    - 输出：电机PWM值
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
#include "filter.h"

/*全局变量定义*/
TaskHandle_t motor_handler;       // 电机任务句柄
int dirct[4] ;   // 电机方向系数：[左前, 左后, 右前, 右后]
volatile uint8_t PIDMode;         // 当前PID模式
uint8_t line_gyro_switch = 0;     // 循迹与陀螺仪模式切换标志
uint8_t Nosmall = 1;              
int MOTOR_PWM_MAX = 9800;         // 电机PWM最大值
uint8_t open_qiang_jiao = 0;      // 墙角模式标志


/*电机任务主函数*/
/*
 * 功能：电机控制的主任务循环
 * 执行频率：每5ms执行一次
 */
void motor_task(void *pvParameters)
{
	portTickType xLastWakeTime;
	xLastWakeTime = xTaskGetTickCount();  	// 获取系统节拍
	
	while (1)
	{
		//pid调参接口
		get_PIDdata();

		/*2. 获取电机速度（内环实际值）与路程计算*/
		handle_motor_speed();
		
		/*3. 处理墙角模式 - 在上坡时增强PID响应*/
		handle_qiang_jiao();
		
		/*4. 处理红外传感器 - 检测障碍物*/
		handle_infrared();
	
		/*5. 处理模式切换逻辑 - 确保模式切换平滑过渡*/
		handle_mode_switch();
	
		/*6. 灯鼠控制 - 状态指示*/
		//handle_led_mouse();
	
		/*7. 设置目标速度 （内环目标值）*/
		handle_target_speed();

		/*8. 执行PID计算和电机控制*/
		handle_pid_control();

		// 调试信息输出（注释掉的部分）
//		 /*陀螺仪模式*/ printf("Gyro:%.2f LSP:%.2f RSP:%.2f L0:%.2f L1:%.2f R0:%.2f R1:%.2f\r\n", imu.yaw,motor_all.Lspeed,motor_all.Rspeed,motor_L0.output,motor_L1.output,motor_R0.output,motor_R1.output);
	     /*电机环PID*/// printf("LSP:%.2f RSP:%.2f L0:%.2f L1:%.2f R0:%.2f R1:%.2f\r\n", motor_all.Lspeed,motor_all.Rspeed,motor_L0.output,motor_L1.output,motor_R0.output,motor_R1.output);
		// /*电机环目标值*/ printf("L0tar:%.2f\tL1tar:%.2f\tR0tar:%.2f\tR1tar:%.2f\r\n", motor_L0.target, motor_L1.target, motor_R0.target, motor_R1.target);
		// /*循迹值*/ printf_byte(Scaner.detail);
		// /*陀螺仪读数*/ printf("yaw:%.2f\troll:%.2f\tpitch:%.2f\tbasic:%.2f\r\n", imu.yaw, imu.roll, imu.pitch, basic_p);
		// /*当前目标节点*/ printf("%d\r\n",nodesr.nowNode.nodenum);
		// /*三门大炮*/ printf("前%d 左%d 右%d\r\n", Infrared_ahead, infrared.head_left, infrared.head_right);
		 /*各轮子测量值*/ printf("L0:%.1f,L1:%.1f,R0:%.1f,R1:%.1f,TargetL:%.1f,TargetR:%.1f\r\n", motor_L0.measure, motor_L1.measure, motor_R0.measure, motor_R1.measure ,motor_all.Lspeed, motor_all.Rspeed);
		
		/*电机pid参数,测量值，目标值*/// printf("%.1f, %.1f, %.1f, %.1f, %.1f, %d, %.1f\r\n", MOTOR_PID_PARAM.kp, MOTOR_PID_PARAM.ki, MOTOR_PID_PARAM.kd,  MOTOR.output, MOTOR.measure, -(int)Speed[3], MOTOR.target);
		/*右前与后的测量值，目标值，输出值*///printf("R0:%.1f, R1:%.1f, TargetR:%.1f, OutputR0:%.1f, OutputR1:%.1f\r\n", motor_R0.measure, motor_R1.measure, motor_all.Rspeed, motor_R0.output, motor_R1.output);
		// /*打印识别数字*/ printf("%d\r\n", Clue_Num);

//		 /*各轮子测量值*/ printf("R1:%.1f\r\n",motor_R1.measure);

		vTaskDelayUntil(&xLastWakeTime, (5 / portTICK_RATE_MS)); // 绝对休眠5ms，确保执行频率稳定
	}
}

/*处理电机速度获取和路程计算*/
/*
 * 功能：
 * 1. 读取编码器值计算电机速度
 * 2. 计算平均速度
 * 3. 累计行驶路程
 * 路程计算公式：
 * Distance = (编码器平均值 * 车轮直径 * π) / (编码器每圈脉冲数 * 减速比)
 * 其中：
 * - 车轮直径：10.4cm
 * - 编码器每圈脉冲数：5720
 * - 减速比：0.362
 */
void handle_motor_speed(void)
{
	
	get_motor_speed();  // 读取编码器值并计算电机速度
	
	// 计算四个电机的平均速度
	motor_all.encoder_avg = (motor_L0.measure + motor_L1.measure + motor_R0.measure + motor_R1.measure) / 4;
	
	// 计算并累计行驶路程
	motor_all.Distance += ((motor_all.encoder_avg * 10.4f * PI)/5720.0f)/0.362f;
}

/*处理墙角模式逻辑*/
/*
 * 功能：在上坡时增强PID响应，防止速度过低导致失控
 * 触发条件：
 * 1. 左前轮速度 < 14（电机负载较大）
 * 2. 右后轮速度 < 14（电机负载较大）
 * 3. open_qiang_jiao == 1（在stage函数中设置）
 */
void handle_qiang_jiao(void)
{
	//在 P3 节点上坡时速度变慢，说明了阻力较大。此时增大 kp、kd ，使循迹响应更敏捷、更强力
	if(motor_L0.measure < 14 && motor_R1.measure < 14 && open_qiang_jiao == 1)
	{
		line_pid_param.kp = 35;    // 增大PID比例系数(kp)：从10增加到35
		line_pid_param.ki = 0.004;  // 积分系数
		line_pid_param.kd = 300;    // 增大PID微分系数(kd)：从85增加到300
		open_qiang_jiao = 0;        // 重置墙角模式标志
		//	CarBrake();
	}
}

/*处理红外传感器逻辑*/
/*
 * 功能：读取红外传感器数据，检测障碍物
 * 执行条件：红外传感器开启（infrare_open == 1）
 * 传感器位置：
 * - 右前方：infrared.head_right
 * - 左前方：infrared.head_left
 * 检测结果：检测到障碍物时返回1，否则返回0
 */
void handle_infrared(void)
{
	if(infrare_open)
		get_Infrared();  // 读取红外传感器数据
}

/*处理循迹模式控制*/
/*
 * 主要流程：
 * 1. 获取循迹error
 * 2. 计算平滑速度
 * 3. 执行循迹控制
 */
void handle_line_mode(void)
{
	if (PIDMode == is_Line)
	{
		/* 获取循迹error - （外环PID误差）*/
		getline_error(); 
	
		// 计算平滑速度（考虑加速度和减速度）
		gradual_cal(&TC_speed, motor_all.Cspeed, motor_all.Cincrement, motor_all.CDOWNincrement);
			
		// 执行循迹控制
		//Go_Line(TC_speed, &motor_all);
		 // 调试速度环用
		//motor_all.Lspeed = TC_speed; 
		//motor_all.Rspeed = TC_speed;								
	}
	else
		motor_all.Cspeed = 0;  // 非循迹模式时，重置循迹速度
}

/*处理转弯模式控制*/
/*
 * 处理场景：
 * 1. 360度旋转
 * 2. 平台相关转弯（如上台、下台）
 * 3. 普通角度转弯
 */
void handle_turn_mode(void)
{
	if (PIDMode == is_Turn)
	{
		if (Turn360_Flag)
		{
			Turn360Step();  // 执行360度旋转步骤
		}
		// 平台相关转弯
		else if (nodesr.nowNode.function == UpStage || nodesr.nowNode.function == BSoutPole || nodesr.nowNode.function == BHM)
		{
			if (Stage_turn_Angle(angle.AngleT))  // 执行平台转弯
				gyroT_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0};  // 重置转弯PID
		}
		// 普通角度转弯
		else if (Turn_Angle(angle.AngleT))  // 执行普通转弯
			gyroT_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0};  // 重置转弯PID
	}
}

/*处理陀螺仪模式控制*/
/*
 * 主要流程：
 * 1. 计算平滑速度
 * 2. 以指定角度执行陀螺仪控制
 */
void handle_gyro_mode(void)
{
	if (PIDMode == is_Gyro)
	{
		// 获取陀螺仪测量值（由中断完成）
			
		// 计算平滑速度（考虑加速度和减速度）
		gradual_cal(&TG_speed, motor_all.Gspeed, motor_all.Gincrement, motor_all.GDOWNincrement);
		
		// 以指定角度执行陀螺仪控制
		Go_Angle(angle.AngleG, TG_speed, &motor_all);
	}
	else
		motor_all.Gspeed = 0;  // 非陀螺仪模式时，重置陀螺仪速度
}

/*处理模式切换逻辑*/
/*
 * 功能：处理循迹与陀螺仪模式之间的切换
 * 确保切换过程平滑，避免速度突变和控制振荡
 * 
 * 切换场景：
 * 1. 陀螺仪模式 -> 循迹模式（line_gyro_switch == 1）
 * 2. 循迹模式 -> 陀螺仪模式（line_gyro_switch == 2）
 */
void handle_mode_switch(void)
{
	if (line_gyro_switch == 1)  // 陀螺仪 -> 循迹
	{
		// 状态传递：只传递PID的输出和积分状态，不传递测量值
    	// 测量值将在Go_Line函数中重新设置为Scaner.error
		line_pid_obj = gyroG_pid;
		TC_speed = TG_speed;
		
		// 重置陀螺仪相关状态
		gyroG_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
		TG_speed = 0;
		
		// 清除切换标志
		line_gyro_switch = 0;
	}
	else if (line_gyro_switch == 2)  // 循迹 -> 陀螺仪
	{
		// 状态传递：只传递PID的输出和积分状态，不传递测量值
    	// 测量值将在Go_Line函数中重新设置为Scaner.error
		gyroG_pid = line_pid_obj;
		TG_speed = TC_speed;
		
		// 重置循迹相关状态
		line_pid_obj = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
		TC_speed = 0;
		
		// 清除切换标志
		line_gyro_switch = 0;
	}
	else  // 无模式切换时，执行各模式的控制逻辑（转向环）
	{
		handle_line_mode();   // 处理循迹模式
		handle_turn_mode();   // 处理转弯模式
		handle_gyro_mode();   // 处理陀螺仪模式
	}
}

/*处理灯鼠控制*/
/*
 * 功能：控制LED灯的闪烁，用于状态指示
 * 闪烁频率：约2Hz（每100个周期切换一次状态）
 */
void handle_led_mouse(void)
{
	static uint8_t mouse = 0;  		  	// 小灯鼠计数器
	mouse++;
	if (mouse > 100)  // 每100个周期（约0.5秒）切换一次
	{
		mouse = 0;
		LED_C1_Toggle();  // 切换LED状态
	}
}

/*处理目标速度设置*/
/*
 * 功能：根据当前模式和路况设置电机目标速度
 * 处理场景：
 * 1. 流水下坡模式（DownLiuShui == 1）：调整前轮速度
 * 2. 普通模式：设置四个电机的目标速度
 */
void handle_target_speed(void)
{
	if(DownLiuShui)  // 流水下坡模式
	{
		// 前轮速度乘以流水倍率，增强下坡稳定性
		motor_L0.target = motor_all.Lspeed * LiuShuiRate;
		motor_L1.target = motor_all.Lspeed;
		motor_R0.target = motor_all.Rspeed * LiuShuiRate;
		motor_R1.target = motor_all.Rspeed;
	}
	else  // 普通模式
	{
		// 四个电机设置相同的目标速度
		motor_L0.target = motor_L1.target = motor_all.Lspeed;
		motor_R0.target = motor_R1.target = motor_all.Rspeed;
	}
}



/*模式转换函数*/
/*
 * 功能：在不同PID模式之间切换
 * 参数：target_mode - 目标模式
 * 模式说明：
 * is_Turn  - 转向模式：机器人需要旋转（如90°、360°）
 * is_Line  - 循迹模式：沿预定路径（如黑线）移动
 * is_Gyro  - 陀螺仪模式：走向指定角度
 * is_Free  - 开环模式：取消pid计算，输入速度为ccr
 * is_No    - 空模式：重置所有参数，停止自动控制
 */
void pid_mode_switch(uint8_t target_mode)
{
	if (PIDMode == target_mode)  // 如果目标模式与当前模式相同，不执行切换
		return;
	switch (target_mode)
	{
		case is_Turn:  // 转向模式
		{
			MOTOR_PWM_MAX = 5000;  // 降低PWM最大值，确保转向稳定性
			
			// 重置所有PID状态
			line_pid_obj = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			gyroG_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			gyroT_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			TC_speed = 0;
			TG_speed = 0;
			break;
		}

		case is_Line:  // 循迹模式
		{
			MOTOR_PWM_MAX = 9800;  	// 恢复PWM最大值
			
			if(PIDMode == is_Gyro)   		  // 陀螺仪->循线
				line_gyro_switch = 1;  // 使用标志位进行模式切换，防止在计算过程中被打断
			else if(PIDMode == is_Turn)
				gyroT_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};  // 重置转弯PID
			break;
		}

		case is_Gyro:  // 陀螺仪模式
		{
			MOTOR_PWM_MAX = 9800;  // 恢复PWM最大值
			
			if (PIDMode == is_Line)			// 循线->陀螺仪
				line_gyro_switch = 2;  // 使用标志位进行模式切换，防止在计算过程中被打断
			else if(PIDMode == is_Turn)
				gyroT_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};  // 重置转弯PID
			break;
		}

		case is_Free:  // 开环模式
		{
			MOTOR_PWM_MAX = 9800;  // 恢复PWM最大值
			break;
		}

		case is_No:  // 不使用转向环模式
		{
			MOTOR_PWM_MAX = 9800;  // 恢复PWM最大值
			
			// 重置所有PID状态
			line_pid_obj = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			gyroT_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			gyroG_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			TG_speed = 0;
			TC_speed = 0;
			break;
		}
	}

	PIDMode = target_mode;  // 更新当前模式
}

/*获取编码器测量值*/
/*
 * 功能：读取编码器值并计算电机速度
 * 执行流程：
 * 1. 读取四个定时器的计数
 * 2. 清零计数器，为下一次读取做准备
 * 3. 根据方向系数计算电机速度
 * 
 * 编码器连接：
 * TIM1 -> 左前轮
 * TIM2 -> 左后轮
 * TIM3 -> 右前轮
 * TIM5 -> 右后轮
 */
void get_motor_speed()
{
	// 左前轮
	Speed[0] = (short)TIM1->CNT;//定时器uint16_t（0~65535），short类型int16_t(-32768~32767），使电机反转时定时器cnt具有负数
	TIM1->CNT = 0;
	// 左后轮
	Speed[1] = (short)TIM2->CNT;
	TIM2->CNT = 0;

	// 右前轮
	Speed[2] = (short)TIM5->CNT;
	TIM5->CNT = 0;

	// 右后轮
	Speed[3] = (short)TIM3->CNT;
	TIM3->CNT = 0;

	// 设置方向系数：左边为正，右边为负
	dirct[0] = dirct[1] = 1;     // 左前轮、左后轮
	dirct[2] = dirct[3] = -1;    // 右前轮、右后轮
	
	// 计算电机速度（编码器值 × 方向系数）
	motor_L0.measure = (float)Speed[0] * dirct[0];  // 左前轮
	motor_L1.measure = (float)Speed[1] * dirct[1];  // 左后轮
	motor_R0.measure = (float)Speed[2] * dirct[2];  // 右前轮
	motor_R1.measure = (float)Speed[3] * dirct[3];  // 右后轮

	// 对电机实际速度进行滤波处理，保留小数精度
	filter_motor_speed(&motor_L0.measure, 0);
	filter_motor_speed(&motor_L1.measure, 1);
	filter_motor_speed(&motor_R0.measure, 2);
	filter_motor_speed(&motor_R1.measure, 3);
}

/*处理PID计算和电机控制*/
/*
 * 功能：执行电机PID控制计算并输出PWM信号
 * 执行条件：非开环模式（PIDMode != is_Free）
 * 主要流程：
 * 1. 计算四个电机的PID输出
 * 2. 设置电机PWM值
 */
void handle_pid_control(void)
{
	if (PIDMode != is_Free)  // 非开环模式时执行PID控制
	{
		/*PID计算*/
		incremental_PID(&motor_L0, &motor_pid_paramL0);  // 左前轮
		incremental_PID(&motor_L1, &motor_pid_paramL1);  // 左后轮
		incremental_PID(&motor_R0, &motor_pid_paramR0);  // 右前轮
		incremental_PID(&motor_R1, &motor_pid_paramR1);  // 右后轮

		/*设置电机PWM值*/
		//motor_set_pwm(1, (int32_t)motor_L0.output);  // 左前轮
		//motor_set_pwm(2, (int32_t)motor_L1.output);  // 左后轮
 		//motor_set_pwm(3, (int32_t)motor_R0.output);  // 右前轮
		//motor_set_pwm(4, (int32_t)motor_R1.output);  // 右后轮
	
	}
}

/*创建电机任务*/
/*
 * 功能：创建电机控制任务
 * 任务参数：
 * - 任务函数：motor_task
 * - 任务名称："motor_task"
 * - 堆栈大小：motor_size（定义为512）
 * - 优先级：motor_task_priority（定义为10）
 * - 任务句柄：motor_handler
 */
void motor_task_create(void)
{
	xTaskCreate((TaskFunction_t)motor_task,  	  // 任务函数
			(const char *)"motor_task",  	  // 任务名字
			(uint32_t)motor_size,  	  // 任务堆栈大小
			(void *)NULL,  		  // 传递给任务参数的指针参数
			(UBaseType_t)motor_task_priority, // 任务的优先级
			(TaskHandle_t *)&motor_handler);  // 任务句柄
}

