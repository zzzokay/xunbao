#include "chassis_api.h"
#include "motor_task.h"
#include "sys.h"
#include "scaner.h"
#include "bsp_linefollower.h"
#include "math.h"
#include "encoder.h"
#include "delay.h"
#include "pid.h"
#include "turn.h"
#include "motor.h"

/* 
 * ==========================================================
 * Chassis API (底盘解耦中间层) 实现
 * 将具体的 PID、游龙检测、编码器计算、状态量封存在这里，不对 map.c 开放
 * map.c 只能发“高级指令”，不修底层参数
 * ==========================================================
 */
//对motortask暴露的全局变量，控制核心
volatile struct Motors motor_all = {0};  // 电机状态结构体
float TC_speed = 0, TG_speed = 0;

// 底盘内部的状态缓存（不对外暴露，保护数据）
typedef struct {
    //以下主要是记录底盘状态的变量，不直接参与控制，不是全局变量
    uint8_t            PID_mode;
    LineTrackMode_e     track_mode;
    uint8_t             target_speed; 
    
    // 游龙防护算法相关变量（从 map 剥离出来）
    uint8_t             anti_snake_err_count;
    uint8_t             anti_snake_flag;
} ChassisState_t;

static ChassisState_t chassis = {0};

/* ========================================================================= */
/* -------------------------- 暴露给 Map 的高级指令 -------------------------- */
/* ========================================================================= */

void Chassis_Init(void)
{
    chassis.PID_mode = is_No;
    chassis.track_mode = TRACK_ALL;
    chassis.target_speed=0;
    chassis.anti_snake_err_count = 0;
    chassis.anti_snake_flag = 0;

    motor_all.Lspeed = 0;   
	motor_all.Rspeed = 0;
    motor_all.Cspeed = 0;
    //motor_all.Cspeed = 50;
    motor_all.Gspeed = 0;
	motor_all.encoder_avg = 0;
	motor_all.GyroG_speedMax = 100;	// 自平衡左右偏差最大值10000
	motor_all.GyroT_speedMax = 25;  	// 自转最大速度34//--->5760 //35
	motor_all.Cincrement = 0.5;	   	// 循迹加速度 0.5
	motor_all.CDOWNincrement = 0.5;	//循迹减速0.5
    motor_all.Gincrement = 0.5;	   	// 非循迹加速度0.5
    motor_all.GDOWNincrement=0.5;	// 非循迹减速0.5


    TC_speed = 0;
    //TC_speed = 50;
    TG_speed = 0;
    //PIDMode = is_No;
    LEFT_RIGHT_LINE = 0;
    MOTOR_PWM_MAX = 5000;

    motor_init();
    pid_init();
}

void Chassis_SetMode(uint8_t mode)
{
    chassis.PID_mode = mode;
    // 映射到底层具体模式
    pid_mode_switch(mode);

    if (mode != is_Line)
    {
        chassis.anti_snake_err_count = 0;
        chassis.anti_snake_flag = 0;
    }
}

void Chassis_SetTargetSpeed(float speed)
{
    chassis.target_speed = (uint8_t)(speed+0.5f); // 四舍五入取整
    if(PIDMode == is_Line)
    {
        motor_all.Cspeed = chassis.target_speed;
        switch (chassis.target_speed) 
			{
				case SPEED4:
					line_pid_param.kp = 4.0;//5.0
					line_pid_param.ki = 0;//0
					line_pid_param.kd = 300;//260
					break;		
				case SPEED3:
					line_pid_param.kp = 7;//8.0
					line_pid_param.ki = 0;//0
					line_pid_param.kd = 300;//300
					break;
					
				case SPEED2:
					line_pid_param.kp = 7.0;//8.0
					line_pid_param.ki = 0.008;//0.008
					line_pid_param.kd = 400;//400
					break;		
				case SPEED0:
				case SPEED1:
					line_pid_param.kp = 7.0;//6.0
					line_pid_param.ki = 0;//0
					line_pid_param.kd = 350;//300
					break;
				default:
					break;
			}
    }
    else if (PIDMode == is_Gyro)
    {
        motor_all.Gspeed = chassis.target_speed;
    }
}

void Chassis_SetTrackMode(LineTrackMode_e mode)
{
    chassis.track_mode = mode;
    switch (mode)
    {
        case TRACK_ALL:
            LEFT_RIGHT_LINE = TRACK_ALL;//默认模式（没有主动区分）
            break;
        case TRACK_LEFT_EDGE:
            LEFT_RIGHT_LINE = TRACK_LEFT_EDGE;//左边缘跟踪（忽略右侧）
            break;
        case TRACK_RIGHT_EDGE:
            LEFT_RIGHT_LINE = TRACK_RIGHT_EDGE;//右边缘跟踪（忽略左侧）
            break;
        case TRACK_LIUSHUI:
            LEFT_RIGHT_LINE = TRACK_LIUSHUI;//中心跟踪
            break;
        default:
            LEFT_RIGHT_LINE = TRACK_ALL;
            break;
    }
}

void Chassis_SetGyroAngle_Go(float TargetAngle)//可考虑设为静态函数
{
    if(TargetAngle > 180.0f)
        TargetAngle -= 360.0f;
    else if(TargetAngle <= -180.0f)
        TargetAngle += 360.0f;
    angle.AngleG = TargetAngle;
}

void Chassis_SetGyroAngle_Turn(float TargetAngle)
{
     if(TargetAngle > 180.0f)
        TargetAngle -= 360.0f;
    else if(TargetAngle <= -180.0f)
        TargetAngle += 360.0f;
    angle.AngleT = TargetAngle;
}


void Chassis_MotorControl(uint8_t target_mode, float LSPEED, float RSPEED, float aim)
{
    switch (target_mode)
    {
        case is_Turn:
            Turn_Angle_Relative(aim);
            break;

        case is_Line:
            scaner_set.CatchsensorNum = aim;
            Chassis_SetMode(is_Line);
            if (fabsf(LSPEED - RSPEED) > 1.0f)
                Chassis_SetTargetSpeed(0);
            else
                Chassis_SetTargetSpeed(LSPEED);
            break;

        case is_Gyro:
            Chassis_SetGyroAngle_Go(aim);
            Chassis_SetMode(is_Gyro);
            if (fabsf(LSPEED - RSPEED) > 1.0f)
                Chassis_SetTargetSpeed(0);
            else
                Chassis_SetTargetSpeed(LSPEED);
            break;

        case is_Free:
            Chassis_SetMode(is_Free);
            motor_set_pwm(1, (int32_t)LSPEED);
            motor_set_pwm(2, (int32_t)LSPEED);
            motor_set_pwm(3, (int32_t)RSPEED);
            motor_set_pwm(4, (int32_t)RSPEED);
            break;

        case is_No:
            Chassis_SetMode(is_No);
            motor_all.Lspeed = LSPEED;
            motor_all.Rspeed = RSPEED;
            break;

        default:
            break;
    }
}

void Chassis_EnableAntiSnake(void)
{
    chassis.anti_snake_flag = 1;
    chassis.anti_snake_err_count = 0;
}

void Chassis_Brake(void)//更安全的急刹
{
    Chassis_SetTargetSpeed(0);
    vTaskDelay(100);//100ms
    chassis.PID_mode = is_Free;
    CarBrake(); // 调用原有的底层急刹
    vTaskDelay(100);//100ms
}

void Chassis_ClearMileage(void)
{
    motor_all.Distance = 0;
}

float Chassis_GetMileage(void)
{
    return motor_all.Distance; // 获取距离
}

// 封装等待逻辑，避免 map.c 到处都是 while(fabsf) 循环
void Chassis_TurnToAngle_Blocking(float target_angle, float origin_angle, float wait_ratio)
{
    // 调用实际控制（如果需要发送给底层状态机的话）
    while (fabsf(need2turn(target_angle, getAngleZ())) > 3.0f)
    {
        vTaskDelay(2); // RTOS 延时交出 CPU 权限
        Cross_getline();
        if (Cross_Scaner.lineNum == 1 && ((Cross_Scaner.detail & 0x3C0) != 0) &&
            (fabsf(need2turn(target_angle, getAngleZ())) < fabsf(need2turn(target_angle, origin_angle)) * wait_ratio))
        {
            break;
        }
    
    }
}

static float saved_line_kp = 0.0f;
static float saved_line_ki = 0.0f;
static float saved_line_kd = 0.0f;
static float saved_line_outputMax = 0.0f;
static uint8_t line_pid_override_active = 0;

static struct PID_param saved_gyroT_pid_param = {0};
static float saved_GyroT_speedMax = 0.0f;

static uint8_t turn_pid_override_active = 0;

static struct PID_param saved_gyroG_pid_param = {0};
static float saved_GyroG_speedMax = 0.0f;
static uint8_t gyro_pid_override_active = 0;

void Chassis_MoveDistance_Blocking(float distance)
{
    float num = motor_all.Distance;
	while (fabsf(motor_all.Distance - num) < distance)
	    {vTaskDelay(2); }
}

void Chassis_DriveDistance_Blocking(uint8_t mode, float distance, float speed, float aim, uint8_t edge_ignore)
{
    scaner_set.EdgeIgnore = edge_ignore;
    Chassis_MotorControl(mode, speed, speed, aim);
    Chassis_MoveDistance_Blocking(distance);
    Chassis_MotorControl(is_Line, speed, speed, 0.0f);
    scaner_set.EdgeIgnore = 0;
}

void Chassis_OverrideLinePid(float kp, float ki, float kd, float speed)
{
    if (!line_pid_override_active)
    {
        saved_line_kp = line_pid_param.kp;
        saved_line_ki = line_pid_param.ki;
        saved_line_kd = line_pid_param.kd;
        line_pid_param.outputMax = speed; // 备份当前的输出限制，方便恢复
        line_pid_override_active = 1;
    }
    line_pid_param.kp = kp;
    line_pid_param.ki = ki;
    line_pid_param.kd = kd;
}

void Chassis_RestoreLinePid(void)
{
    if (line_pid_override_active)
    {
        line_pid_param.kp = saved_line_kp;
        line_pid_param.ki = saved_line_ki;
        line_pid_param.kd = saved_line_kd;
        line_pid_param.outputMax = saved_line_outputMax;
        line_pid_override_active = 0;
    }
}

void Chassis_OverrideTurnPid(float kp, float ki, float kd, float turnSpeedMax)
{
    if (!turn_pid_override_active)
    {
        saved_gyroT_pid_param = gyroT_pid_param;
        saved_GyroT_speedMax = motor_all.GyroT_speedMax;   
        turn_pid_override_active = 1;
    }
    gyroT_pid_param.kp = kp;
    gyroT_pid_param.ki = ki;
    gyroT_pid_param.kd = kd;
    motor_all.GyroT_speedMax = turnSpeedMax;
}


void Chassis_RestoreTurnPid(void)
{
    if (turn_pid_override_active)
    {
        gyroT_pid_param = saved_gyroT_pid_param;
        motor_all.GyroT_speedMax = saved_GyroT_speedMax;
        motor_all.GyroG_speedMax = saved_GyroG_speedMax;
        turn_pid_override_active = 0;
    }
}

void Chassis_OverrideGyroPid(float kp, float ki, float kd, float gyroSpeedMax)
{
    if (!gyro_pid_override_active)
    {
        saved_gyroG_pid_param = gyroG_pid_param;
        saved_GyroG_speedMax = motor_all.GyroG_speedMax;
        gyro_pid_override_active = 1;
    }
    gyroG_pid_param.kp = kp;
    gyroG_pid_param.ki = ki;
    gyroG_pid_param.kd = kd;
    motor_all.GyroG_speedMax = gyroSpeedMax;
}
// 这里没有单独的 RestoreGyroPid，因为陀螺仪模式和转弯模式共用 gyroG_pid_param 和 GyroG_speedMax
void Chassis_RestoreGyroPid(void)
{
    if (gyro_pid_override_active)
    {
        gyroG_pid_param = saved_gyroG_pid_param;
        motor_all.GyroG_speedMax = saved_GyroG_speedMax;
        gyro_pid_override_active = 0;
    }
}

void Chassis_Turn_By_LeftLine_Blocking(float target_angle, float current_angle, float speed)
{
    Chassis_OverrideLinePid(70.0f, 0.0f, 5.0f, speed);//最后一个是差速最大值
    
    Chassis_SetTrackMode(TRACK_LEFT_EDGE); // 设置左边缘跟踪，忽略右侧

    Chassis_TurnToAngle_Blocking(target_angle, current_angle, 0.25f);
    
    Chassis_SetTrackMode(TRACK_ALL); // 恢复默认模式，重新检测左右两侧

    Chassis_RestoreLinePid();

}
void Chassis_Turn_By_RightLine_Blocking(float target_angle, float current_angle, float speed)
{
    Chassis_OverrideLinePid(70.0f, 0.0f, 5.0f, speed);

    Chassis_SetTrackMode(TRACK_RIGHT_EDGE); // 设置右边缘跟踪，忽略左侧

    Chassis_TurnToAngle_Blocking(target_angle, current_angle, 0.25f);
    
    Chassis_SetTrackMode(TRACK_ALL); // 恢复默认模式，重新检测左右两侧

    Chassis_RestoreLinePid();

}
//用之前先停车
void Chassis_Turn_By_StopGyro_Blocking(float target_angle, float current_angle)
{
		
    Chassis_SetGyroAngle_Turn(target_angle);

    Chassis_SetMode(is_Turn);//进入转弯模式			

    Chassis_TurnToAngle_Blocking(target_angle, current_angle, 0.15f);

}

void Chassis_Turn_By_Gyro_Blocking(float target_angle, float current_angle)
{
   
    Chassis_OverrideGyroPid(12.0f, 0.0f, 180.0f, need2turn(target_angle, current_angle) > 0 ? 30.0f : 39.0f); //左转还是右转
    //直接转相对角度
    float target_g = getAngleZ() + need2turn(current_angle, target_angle);
    if(target_g > 180.0f)
        target_g -= 360.0f;
    else if(target_g <= -180.0f)
        target_g += 360.0f;
    Chassis_SetGyroAngle_Go(target_g);

    Chassis_SetMode(is_Gyro); // 进入陀螺仪转弯模式

    Chassis_TurnToAngle_Blocking(target_g, current_angle, 0.1f);

    Chassis_RestoreGyroPid();

}

void Chassis_SetCatchSensorNum(uint8_t num)
{
    scaner_set.CatchsensorNum = num;
}

void Chassis_SetEdgeIgnore(uint8_t num)
{
    scaner_set.EdgeIgnore = num;
}
/* ========================================================================= */
/* -------------------------- 提供给 Motor_Task 刷新的 ---------------------- */
/* ========================================================================= */

// 在 motor_task.c 的 while(1) 中调用：Chassis_Periodic_Update_5ms();
void Chassis_Periodic_Update_5ms(void)
{
    /* ========= 游龙防抖自适应 PID 算法 ========= */
    // 将原 map.c 的游龙检测剥离进真正的电机循环反馈，5ms 检测一次，真正发挥自适应作用
    
    if (chassis.PID_mode == is_Line) 
    {
        // 由于 5ms 循环非常紧凑，不要在这里调用可能会阻塞的 Cross_getline() 等指令
        // 直接使用全局已解析好的巡线偏移状态（如 Scaner.detail） 
        if (chassis.anti_snake_flag == 1)        
        {
            // motor_all.Cspeed 减半已放到高速上设置，在底层此处：如果发现大偏移加计时
            // 通过 Scaner.detail 直接检测偏离特征
            if(Scaner.detail & 0xFC3F) // 偏移过大 (使用 Scaner.detail 避免重复获取耗时)
            {
                chassis.anti_snake_err_count++; 
            }
            else // 回正后迅速衰减警戒值
            {
                if(chassis.anti_snake_err_count < 10) 
                    chassis.anti_snake_err_count += 5;
            }
            
            // 警戒解除
            if(chassis.anti_snake_err_count >= 10)
            {
                chassis.anti_snake_err_count = 0;
                chassis.anti_snake_flag = 0;
                // 让 motor_all.Cspeed 恢复全速 (可以封装为 Chassis_SetTargetSpeed)
                motor_all.Cspeed = chassis.target_speed; // 利用备份的当前速度值恢复
            }
        }
        
        // 游龙检测命中，强压 PID 系数阻止摇摆
        if (chassis.anti_snake_err_count)
        {
            line_pid_param.kp = 12.0f;
            line_pid_param.ki = 0.0f;
            line_pid_param.kd = 200.0f;
            motor_all.Cspeed = chassis.target_speed / 2; // 直接减半速度，增强稳定性
        }
    }
}   
    /* ========= 其他需要随底层反馈刷新的控制变量 ========= */
/*模式转换函数*/
/*
 * 功能：在不同PID模式之间的切换
 * 参数：target_mode - 目标模式
 * 模式说明：
 * is_Turn  - 转弯模式（包含小车需要转弯，如90度、360度）
 * is_Line  - 巡线模式（预判路径偏向或偏右，可移动）
 * is_Gyro  - 陀螺仪模式（可指定角度）
 * is_Free  - 自由模式（取消pid计算，设置速度为ccr）
 * is_No    - 无模式（取消所有任务，停止与驱动）
 */
#define TEMP_PWM_MAX 5000 //调试用

void pid_mode_switch(uint8_t target_mode)
{
	if (PIDMode == target_mode)  // 若目标模式与当前模式相同则不执行切换
		return;


    // 转弯模式下切换，清零转弯PID状态，避免残留影响后续操作
    if(PIDMode == is_Turn)
    {
        gyroT_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0};  // 清零转弯PID
				
    }
	switch (target_mode)
	{
		
		case is_Line:  // 巡线模式
		case is_Gyro:  // 陀螺仪模式
		case is_Free:  // 自由模式
		{
			MOTOR_PWM_MAX = TEMP_PWM_MAX;  // 恢复PWM最大值9800
			break;
		}
        case is_No:
		{
			MOTOR_PWM_MAX = 9800;
			line_pid_obj = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			gyroT_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			gyroG_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			TG_speed = 0;
			TC_speed = 0;
			break;
		}
        case is_Turn:  // 转弯模式
		{
			MOTOR_PWM_MAX = 5000;  // 减小PWM最大值，确保转弯稳定性。
			// 清除所有PID状态
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

/*自定义距离前进*/
void Want2Go(float Dis)
{
	float num = motor_all.Distance;
	while (fabsf(motor_all.Distance - num) < Dis)
		vTaskDelay(2);
}



/**
 * @brief: 刹车制动
 * @return {*}
 */
void CarBrake(void)
{
	// 开环
	pid_mode_switch(is_Free);
	motor_set_pwm(1, 0); //设置 4 个电机的 PWM=0
	motor_set_pwm(2, 0);
	motor_set_pwm(3, 0);
	motor_set_pwm(4, 0);

	motor_pid_clear();
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
		Chassis_Brake();
		vTaskDelay(2);
	}
}