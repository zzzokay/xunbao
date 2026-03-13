#include "speed_ctrl.h"
#include "motor_task.h"
#include "pid.h"
#include "motor.h"
#include "bsp_buzzer.h"



volatile struct Motors motor_all = {
	.Lspeed = 0,
	.Rspeed = 0,
	.encoder_avg = 0,
	.GyroG_speedMax = 100, 	// 自平衡左右偏差最大值10000
	.GyroT_speedMax = 25,  	// 自转最大速度34//--->5760 //35
	.Cincrement = 0.9,	   	// 循迹加速度 0.3
	.CDOWNincrement = 0.75,	//循迹减速0.5
	.Gincrement = 0.6,	   	// 非循迹加速度0.5
	.GDOWNincrement=0.7,
	.is_UP = false,
	.is_DOWM = false,
};

float TC_speed = 0, TG_speed = 0, TP_speed = 0, TCO_speed = 0;

/**
 * @brief:
 * @return {*}
 */
void CarBrake(void)
{
	// 闭环
	// pid_mode_switch(is_No);
	// motor_all.Lspeed = motor_all.Rspeed = 0;

	// 开环
	pid_mode_switch(is_Free);
	motor_set_pwm(1, 0); //设置 4 个电机的 PWM=0
	motor_set_pwm(2, 0);
	motor_set_pwm(3, 0);
	motor_set_pwm(4, 0);

	motor_pid_clear();
	TC_speed = 0;
}

/**
 * @brief: 以一次函数缓慢加速或者缓慢停止
 * @param {Gradual} *gradual
 * @param {float} target
 * @param {float} increment
 * @return {*}
 */
void gradual_cal(float *gradual, float target, float increment1, float increment2)
{
	if (*gradual < target)
	{
		*gradual += increment1;
		if (*gradual > target)
			*gradual = target;
	}
	else if (*gradual > target)
	{
		*gradual -= increment2;
		if (*gradual < target)
			*gradual = target;
	}
}

/*卡死停车*/
void CarBrake_Stop(void)
{
	buzzer_on();
	while(1)
	{
		CarBrake();
		vTaskDelay(2);
	}
}
