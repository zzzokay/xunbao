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
#include "gray.h"
#include <stdio.h>

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
    LineTrackMode_e     track_mode;
    uint8_t             target_speed;

    // 游龙防护算法相关变量（从 map 剥离出来）
    int16_t             anti_snake_err_count;
    uint8_t             anti_snake_flag;

    // 丢线保护
    int16_t             line_lost_count;      // 连续丢线计数（每5ms +1）
    uint8_t             line_lost_enabled;    // 1=使能，0=关闭

    // 横滚角超限保护
    uint8_t             roll_protect_enabled; // 1=使能，0=关闭

    // 堵转保护
    uint8_t             stall_protect_enabled; // 1=使能
    int16_t             stall_count[4];        // 每电机独立计数器 (L0/L1/R0/R1)

    // 翘头保护
    uint8_t             wheelie_protect_enabled; // 1=翘头保护使能
    uint8_t             wheelie_protect_active; // 1=翘头保护激活中（正在降加速度）
    float               saved_Cincrement;       // 保存的循迹加速度
} ChassisState_t;

static ChassisState_t chassis = {0};

/* 巡线PID按当前实际速度阶梯选择（速度→PID参数映射表，与各速度档一致）
 * 规则：只有当前实际速度 ≤ 某档速度，才采样该档PID（尽量向上取高速档的低Kp）。
 * 即取所有满足 档速 ≥ 当前速度 的档中速度最低的一档；当前速度超过最高档时用最高档。
 * 高速→低速减速过程中 PID 随实际速度逐级下调：减速前期一直保持高速低Kp，实际速度真正降到
 * 某档以下才换更高Kp —— 既不减速期套用低速高Kp(12/15→15.0)导致摇摆，也不晚切导致不跟线 */
typedef struct {
    uint8_t  speed;        /* 阶梯速度（编码器每5ms计数） */
    float    kp, ki, kd;
} LinePidStep_t;

static const LinePidStep_t line_pid_steps[] = {
    { 75, 3.5f, 0, 200 },   /* SPEED5 */
    { 70, 3.5f, 0, 200 },   /* SPEED4 */
    { 60, 4.0f, 0, 120 },   /* SPEED3 */
    { 55, 5.0f, 0, 150 },   /* SPEED25 */
    { 45, 6.5f, 0, 110 },   /* SPEED2 */
    { 36, 7.5f, 0, 100 },    /* SPEED1 */
    { 25, 9.0f, 0, 80 },    /* SPEED0 */
    { 20, 12.0f, 0, 70 },
    { 15, 15.0f, 0, 60 },
    { 12, 15.0f, 0, 60 },
};
#define LINE_PID_STEP_NUM  (sizeof(line_pid_steps)/sizeof(line_pid_steps[0]))

/* 角度归一化工具：将角度归约到 (-180, 180] */
static inline float normalize_angle(float a)
{
    while (a > 180.0f)  a -= 360.0f;
    while (a <= -180.0f) a += 360.0f;
    return a;
}

/* ========================================================================= */
/* -------------------------- 暴露给 Map 的高级指令 -------------------------- */
/* ========================================================================= */

void Chassis_Init(void)
{
    PIDMode = is_No;
    chassis.track_mode = TRACK_ALL;
    chassis.target_speed=0;
    chassis.anti_snake_err_count = 0;
    chassis.anti_snake_flag = 0;
    chassis.line_lost_count = 0;
    chassis.line_lost_enabled = 0;
    chassis.roll_protect_enabled = 0;
    chassis.wheelie_protect_enabled = 0;
    chassis.wheelie_protect_active = 0;

    motor_all.Lspeed = 0;
	motor_all.Rspeed = 0;
    motor_all.Cspeed = 0;
  
    motor_all.Gspeed = 0;
	motor_all.encoder_avg = 0;
	motor_all.GyroG_speedMax = 100;	// 自平衡左右偏差最大值10000
	motor_all.GyroT_speedMax = 25;  	// 自转最大速度34//--->5760 //35
	motor_all.Line_speedMax = 50;		// 巡线差速最大值
	motor_all.Cincrement = 0.7;	   	// 循迹加速度 0.5
	motor_all.CDOWNincrement = 0.7;	//循迹减速0.5
    motor_all.Gincrement = 0.7;	   	// 陀螺仪加速度0.5
    motor_all.GDOWNincrement=0.7;	// 陀螺仪减速度0.5


    TC_speed = 0;
    TG_speed = 0;
    PIDMode = is_No;
    LEFT_RIGHT_LINE = 0;
    MOTOR_PWM_MAX = 5000;
    
	ScanerMode_Switch(RF);
    //Chassis_EnableStallProtection(); // 激活堵转保护标志
    Chassis_EnableLineLostProtection();// 激活丢线保护标志
	Chassis_EnableRollProtection(); // 激活翻滚保护标志
    motor_init();
    pid_init();
}

#define TEMP_PWM_MAX 8500 //TODO调试用

/*模式转换函数*/
/*
 * 功能：在不同PID模式之间的切换
 * 参数：mode - 目标模式
 * 模式说明：
 * is_Turn  - 转弯模式（包含小车需要转弯，如90度、360度）
 * is_Line  - 巡线模式（预判路径偏向或偏右，可移动）
 * is_Gyro  - 陀螺仪模式（可指定角度）
 * is_Free  - 自由模式（取消pid计算，设置速度为ccr）
 * is_No    - 无模式（取消所有任务，停止与驱动）
 */
void Chassis_SetMode(uint8_t mode)
{
	if (PIDMode == mode)  // 若目标模式与当前模式相同则不执行切换
		return;
    if(mode == is_Line && PIDMode == is_Gyro) {
       motor_all.Cspeed = motor_all.Gspeed;
    }
    else if(mode == is_Gyro && PIDMode == is_Line) {
        motor_all.Gspeed = motor_all.Cspeed;
    }

	switch (mode)
	{
		case is_Line:  // 巡线模式
		case is_Gyro:  // 陀螺仪模式 //处理放在motortask
        {
            MOTOR_PWM_MAX = TEMP_PWM_MAX;  // 调整PWM最大值，确保稳定性
            break;
        }
        case is_Turn:  // 转弯模式//处理放在motortask
		{
			MOTOR_PWM_MAX = 5000;  // 减小PWM最大值，确保转弯稳定性。
			break;
		}
		case is_Free:  // 自由模式 //直接设置PWM，不使用PID
        case is_No:
		{
			MOTOR_PWM_MAX = TEMP_PWM_MAX;
			line_pid_obj = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			gyroT_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
			gyroG_pid = (struct P_pid_obj){0, 0, 0, 0, 0, 0, 0};
            motor_all.Cspeed = 0;
            motor_all.Gspeed = 0;
			TG_speed = 0;
			TC_speed = 0;
			break;
		}
	}

	PIDMode = mode;  // 更新当前模式

	// 离开巡线模式时清除游龙状态（覆盖所有切换路径）
	if (mode != is_Line)
	{
		chassis.anti_snake_err_count = 0;
		chassis.anti_snake_flag = 0;
		chassis.line_lost_count = 0;
		// 不清 line_lost_enabled，转弯后回到巡线时保护仍然生效

		// 清零巡线历史，避免陈旧数据干扰回到巡线后的判断
		Scaner_ClearLineData();

			// 离开巡线时清零堵转计数，避免旧模式残留数据干扰新模式
			for (int i = 0; i < 4; i++)
			{
				chassis.stall_count[i] = 0;
			}
	}
}

void Chassis_SetTargetSpeed(float speed)
{
    chassis.target_speed = (uint8_t)(fabsf(speed)+0.5f); // 四舍五入取整（保留给游龙恢复等使用）
    if(PIDMode == is_Line)
    {
        motor_all.Cspeed = speed;
        Chassis_RestoreLinePid();  // 清除可能残留的游龙/巡线转向临时覆盖
        // 注意：line_pid_param 不在此设置，由 motor_task 每5ms 按当前实际速度查阶梯表实时选择
    }
    else if (PIDMode == is_Gyro)
    {
        motor_all.Gspeed = speed;
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
        case TRACK_NEAR_CENTER:
            LEFT_RIGHT_LINE = TRACK_NEAR_CENTER;//中心跟踪
            break;
        default:
            LEFT_RIGHT_LINE = TRACK_ALL;
            break;
    }
}

void Chassis_SetGyroAngle_Go(float TargetAngle)
{
    angle.AngleG = normalize_angle(TargetAngle);
}

void Chassis_SetGyroAngle_Turn(float TargetAngle)
{
    angle.AngleT = normalize_angle(TargetAngle);
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
void Chassis_DisableAntiSnake(void)
{
    chassis.anti_snake_flag = 0;
    chassis.anti_snake_err_count = 0;
}

void Chassis_EnableLineLostProtection(void)
{
    chassis.line_lost_enabled = 1;
    chassis.line_lost_count = 0;
}

void Chassis_DisableLineLostProtection(void)
{
    chassis.line_lost_enabled = 0;
    chassis.line_lost_count = 0;
}

void Chassis_EnableRollProtection(void)
{
    chassis.roll_protect_enabled = 1;
}

void Chassis_DisableRollProtection(void)
{
    chassis.roll_protect_enabled = 0;
}

void Chassis_EnableStallProtection(void)
{
    chassis.stall_protect_enabled = 1;
    for (int i = 0; i < 4; i++)
    {
        chassis.stall_count[i] = 0;
    }
}

void Chassis_DisableStallProtection(void)
{
    chassis.stall_protect_enabled = 0;
    for (int i = 0; i < 4; i++)
    {
        chassis.stall_count[i] = 0;
    }
}

static void chassis_restore_Cincrement(void)
{
    chassis.wheelie_protect_active = 0;
    motor_all.Cincrement = chassis.saved_Cincrement;
}

void Chassis_EnableWheelieProtection(void)
{
    chassis.wheelie_protect_enabled = 1;
    if (chassis.wheelie_protect_active)
        chassis_restore_Cincrement();
}

void Chassis_DisableWheelieProtection(void)
{
    chassis.wheelie_protect_enabled = 0;
    if (chassis.wheelie_protect_active)
        chassis_restore_Cincrement();
}

void Chassis_Brake(void)//更安全的急刹
{
    float original_CDOWNincrement = motor_all.CDOWNincrement;
    motor_all.CDOWNincrement = 2.0; // 增加减速加速度，快速降速
	Chassis_SetTargetSpeed(0);
	vTaskDelay(200);
    motor_all.CDOWNincrement = original_CDOWNincrement;
    CarBrake(); // 调用原有的底层急刹
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
static  void Chassis_TurnToAngle_Blocking(float target_angle, float origin_angle, float wait_ratio)
{
    // 调用实际控制（如果需要发送给底层状态机的话）
    while (fabsf(need2turn(target_angle, getAngleZ())) > 2.0f)
    {
        vTaskDelay(2); // RTOS 延时交出 CPU 权限
        Cross_getline(&Cross_Scaner);
        if (Cross_Scaner.lineNum == 1 && ((Cross_Scaner.detail & 0x180) != 0) &&
            (fabsf(need2turn(target_angle, getAngleZ())) < fabsf(need2turn(target_angle, origin_angle)) * wait_ratio))
        {
            break;
        }
    
    }
}

static float saved_line_kp = 0.0f;
static float saved_line_ki = 0.0f;
static float saved_line_kd = 0.0f;
static float saved_Line_speedMax = 0.0f;
static uint8_t line_pid_override_active = 0;

static struct PID_param saved_gyroT_pid_param = {0};
static float saved_GyroT_speedMax = 0.0f;

static uint8_t turn_pid_override_active = 0;

static struct PID_param saved_gyroG_pid_param = {0};
static float saved_GyroG_speedMax = 0.0f;
static uint8_t gyro_pid_override_active = 0;

void Chassis_DriveDistance_Blocking(uint8_t mode, float distance, float speed, float aim, uint8_t edge_ignore)
{
    scaner_set.EdgeIgnore = edge_ignore;
    Chassis_ClearMileage();
    Chassis_MotorControl(mode, speed, speed, aim);
    Want2Go(distance);
    scaner_set.EdgeIgnore = 0;
}

void Chassis_OverrideLinePid(float kp, float ki, float kd, float speed)
{
    if (!line_pid_override_active)
    {
        saved_line_kp = line_pid_param.kp;
        saved_line_ki = line_pid_param.ki;
        saved_line_kd = line_pid_param.kd;
        saved_Line_speedMax = motor_all.Line_speedMax;
        line_pid_override_active = 1;
    }
    line_pid_param.kp = kp;
    line_pid_param.ki = ki;
    line_pid_param.kd = kd;
    motor_all.Line_speedMax = speed;
}

void Chassis_RestoreLinePid(void)
{
    if (line_pid_override_active)
    {
        line_pid_param.kp = saved_line_kp;
        line_pid_param.ki = saved_line_ki;
        line_pid_param.kd = saved_line_kd;
        motor_all.Line_speedMax = saved_Line_speedMax;
        line_pid_override_active = 0;
    }
}

/* 巡线PID按当前实际速度阶梯选择：放在 motor_task 5ms 循环中调用
 * 规则：只有当前实际速度 ≤ 某档速度才采样该档PID（尽量向上取高速档低Kp）。
 * 即取所有满足 档速 ≥ 当前速度 的档中速度最低的一档；当前速度超过最高档时用最高档。
 * 游龙等临时覆盖(Chassis_OverrideLinePid)生效时优先级更高，不在此覆盖 */
void Chassis_UpdateLinePidBySpeed(void)
{
    if (PIDMode != is_Line)
        return;
    if (line_pid_override_active)
        return;

    float cur = fabsf(motor_all.encoder_avg);
    const LinePidStep_t *pick = NULL;
    /* 表为降序(75→12)：从低速档往上找，第一个 档速 ≥ 当前速度 的档即为所求（速度最低的一档） */
    for (uint8_t i = LINE_PID_STEP_NUM; i > 0; i--)
    {
        const LinePidStep_t *step = &line_pid_steps[i - 1];
        if ((float)step->speed >= cur)
        {
            pick = step;
            break;
        }
    }
    if (pick == NULL)
        pick = &line_pid_steps[0];  // 当前速度超过最高档(75)，用最高档

    if (line_pid_param.kp != pick->kp || line_pid_param.ki != pick->ki || line_pid_param.kd != pick->kd)
    {
        line_pid_param.kp = pick->kp;
        line_pid_param.ki = pick->ki;
        line_pid_param.kd = pick->kd;
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

void Chassis_Turn_By_LeftLine_Blocking(float target_angle, float current_angle, float different_speed)
{
    Chassis_OverrideLinePid(70.0f, 0.0f, 5.0f, different_speed);//最后一个是差速最大值
    
    Chassis_SetTrackMode(TRACK_LEFT_EDGE); // 设置左边缘跟踪，忽略右侧

    Chassis_TurnToAngle_Blocking(target_angle, current_angle, 0.25f);
    
    Chassis_SetTrackMode(TRACK_ALL); // 恢复默认模式，重新检测左右两侧

    Chassis_RestoreLinePid();

}
void Chassis_Turn_By_RightLine_Blocking(float target_angle, float current_angle, float different_speed)
{
    Chassis_OverrideLinePid(70.0f, 0.0f, 5.0f, different_speed);

    Chassis_SetTrackMode(TRACK_RIGHT_EDGE); // 设置右边缘跟踪，忽略左侧

    Chassis_TurnToAngle_Blocking(target_angle, current_angle, 0.25f);
    
    Chassis_SetTrackMode(TRACK_ALL); // 恢复默认模式，重新检测左右两侧

    Chassis_RestoreLinePid();

}
//用之前先停车，turn_speed_max 控制转弯最大角速度（传入 Chassis_OverrideTurnPid）
void Chassis_Turn_By_StopGyro_Blocking(float target_angle, float current_angle, float turn_speed_max)
{
    //如果没停车
    if(fabsf(motor_all.Lspeed) > 1.0f || fabsf(motor_all.Rspeed) > 1.0f)
    {
        Chassis_Brake(); // 先停车，确保转弯稳定
    }
    Chassis_OverrideTurnPid(6.0f, 0.0f, 90.0f, turn_speed_max);


    Chassis_SetGyroAngle_Turn(target_angle);

    Chassis_SetMode(is_Turn);//进入转弯模式

    Chassis_TurnToAngle_Blocking(target_angle, current_angle, 0.01f);

    Chassis_RestoreTurnPid();
}

void Chassis_Turn360_Blocking(void)
{
    if(fabsf(motor_all.Lspeed) > 1.0f || fabsf(motor_all.Rspeed) > 1.0f)
    {
        Chassis_Brake();
    }

    Turn_Angle360();

    CarBrake();
}

void Chassis_Turn_By_Gyro_Blocking(float target_angle, float current_angle, float turn_speed_max)
{

    Chassis_OverrideGyroPid(12.0f, 0.0f, 180.0f, turn_speed_max); //左转还是右转
    //直接转相对角度
    float target_g = normalize_angle(getAngleZ() + need2turn(current_angle, target_angle));
    Chassis_SetGyroAngle_Go(target_g);

    Chassis_SetMode(is_Gyro); // 进入陀螺仪转弯模式

    Chassis_TurnToAngle_Blocking(target_g, current_angle, 0.05f);

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

/* ========= 翘头保护阈值 ========= */
#define WHEELIE_PITCH_THRESHOLD      7.0f    /* pitch > basic_p + 8° 视为翘头 */
#define WHEELIE_CINCREMENT_REDUCED   0.05f   /* 翘头保护时的加速度 */

#define LINE_LOST_THRESHOLD  80   // 80 * 5ms = 0.4秒

/* ========= 堵转保护阈值 ========= */
#define STALL_SPEED_RATIO         180      /* output > target * 80 视为异常（25→2000） */
#define STALL_COUNT_THRESHOLD      5      /* 连续超限 5 周期 (25ms) 触发 */
#define STALL_PWM_ABSOLUTE_MAX  8000    /* 硬上限：任何 output 超此值立即死停 */

// 在 motor_task.c 的 while(1) 中调用：Chassis_Periodic_Update_5ms();
void Chassis_Periodic_Update_5ms(void)
{
    /* ========= 横滚角超限保护 ========= */
    // 如果车身倾斜过大（imu.roll 与标定值 basic_r 相差 > 40°），直接死停
    if (chassis.roll_protect_enabled && fabsf(imu.roll - basic_r) > 40.0f)
    {
        CarBrake();
        send_play_specified_command(31);    
        //printf("ROLL OVER! roll=%.1f basic_r=%.1f, emergency stop!\n", imu.roll, basic_r);
        while (1);
    }

    /* ========= 游龙防抖自适应 PID 算法 ========= */
    // 将原 map.c 的游龙检测剥离进真正的电机循环反馈，5ms 检测一次，真正发挥自适应作用

    if (PIDMode == is_Line)
    {
        /* ========= 翘头保护：pitch 过高时抑制加速度 ========= */
        if (chassis.wheelie_protect_enabled)
        {
            float pitch_dev = imu.pitch - basic_p;
            if (pitch_dev > WHEELIE_PITCH_THRESHOLD)
            {
                if (!chassis.wheelie_protect_active)
                {
                    chassis.wheelie_protect_active = 1;
                    chassis.saved_Cincrement = motor_all.Cincrement;
                    motor_all.Cincrement = WHEELIE_CINCREMENT_REDUCED;
                }
            }
            else
            {
                if (chassis.wheelie_protect_active)
                {
                    chassis.wheelie_protect_active = 0;
                    motor_all.Cincrement = chassis.saved_Cincrement;
                }
            }
        }

        // 由于 5ms 循环非常紧凑，不要在这里调用可能会阻塞的 Cross_getline(&Cross_Scaner) 等指令
        // 直接使用全局已解析好的巡线偏移状态（如 Scaner.detail）
        if (chassis.anti_snake_flag == 1)
        {
            // motor_all.Cspeed 减半已放到高速上设置，在底层此处：如果发现大偏移加计时
            // 通过 Scaner.detail 直接检测偏离特征
            if(fabsf(Scaner.error) > 1.0f ) // 偏移过大 (使用 Scaner.detail 避免重复获取耗时)fabsf(Scaner.error) > 1.2f
            {
                chassis.anti_snake_err_count++; 
            }
            else // 回正后迅速衰减警戒值
            {
                if(chassis.anti_snake_err_count < 300) 
                    chassis.anti_snake_err_count -= 10;
            }
            
            // 警戒解除
            if(chassis.anti_snake_err_count <= 0 || chassis.anti_snake_err_count >= 300 )
            {
                chassis.anti_snake_flag = 0;
                chassis.anti_snake_err_count=0;
                // 让 motor_all.Cspeed 恢复全速 (可以封装为 Chassis_SetTargetSpeed)
                Chassis_RestoreLinePid(); // 恢复 PID 参数
                motor_all.Cspeed = chassis.target_speed; // 利用备份的当前速度值恢复
            }
        }
        
        // 游龙检测命中，强压 PID 系数阻止摇摆
        if (chassis.anti_snake_err_count)
        {
            if(chassis.anti_snake_err_count==1)send_play_specified_command(33);
            motor_all.Cspeed = 15; // 直接减半速度，增强稳定
            Chassis_OverrideLinePid(18, 0, 100, motor_all.Cspeed); // 直接覆盖当前速度限制，确保稳定性

        }

        /* ========= 丢线保护 ========= */
        if (chassis.line_lost_enabled)
        {
            if (Scaner_IsLineLost())
            {
                chassis.line_lost_count++;
                if (chassis.line_lost_count >= LINE_LOST_THRESHOLD)
                {
                    chassis.line_lost_count = 0;
                    chassis.line_lost_enabled = 0;  // 一次性触发
                    
                    CarBrake(); // 紧急刹车
                    send_play_specified_command(30);
                    //printf("Line lost! Emergency brake activated.\n");
                    while(1){};
                    return;
                }
            }
            else
            {
                chassis.line_lost_count = 0;
            }
        }
    }

    /* ========= PWM 超限保护 (所有模式生效) ========= */
    if (chassis.stall_protect_enabled)
    {
        if (fabsf(motor_L0.output) > (float)STALL_PWM_ABSOLUTE_MAX ||
            fabsf(motor_L1.output) > (float)STALL_PWM_ABSOLUTE_MAX ||
            fabsf(motor_R0.output) > (float)STALL_PWM_ABSOLUTE_MAX ||
            fabsf(motor_R1.output) > (float)STALL_PWM_ABSOLUTE_MAX)
        {
            chassis.stall_protect_enabled = 0;
            CarBrake();
            send_play_specified_command(33);
            while (1);
        }
    }

    /* ========= 堵转保护  ========= */
    if (chassis.stall_protect_enabled && PIDMode != is_Free)
    {
        struct I_pid_obj *motors[4] = { &motor_L0, &motor_L1, &motor_R0, &motor_R1 };

        for (int i = 0; i < 4; i++)
        {
            float out = fabsf(motors[i]->output);
            float tgt = fabsf(motors[i]->target);

            if (tgt > 10.0f && out > tgt * STALL_SPEED_RATIO)
            {
                chassis.stall_count[i]++;
            }
            else if (chassis.stall_count[i] > 0)
            {
                chassis.stall_count[i]--;
            }

            if (chassis.stall_count[i] >= STALL_COUNT_THRESHOLD)
            {
                chassis.stall_protect_enabled = 0;
                CarBrake();
                send_play_specified_command(33);
                while (1);
            }
        }
    }
}
    /* ========= 其他需要随底层反馈刷新的控制变量 ========= */
/*自定义距离前进*/
void Want2Go(float Dis)
{
	float num = motor_all.Distance;
	while (fabsf(motor_all.Distance - num) < Dis)
		vTaskDelay(2);
}



/**
 * @brief: 开环刹车，适合低速瞬间刹停
 * @return {*}
 */
void CarBrake(void)
{
	// 开环
	Chassis_SetMode(is_Free);
    motor_all.Lspeed = 0;
    motor_all.Rspeed = 0;
	motor_set_pwm(1, 0); //设置 4 个电机的 PWM=0
	motor_set_pwm(2, 0);
	motor_set_pwm(3, 0);
	motor_set_pwm(4, 0);
	motor_pid_clear();

    // 等待所有电机编码器归零（确认物理停止），每 2ms 检查一次
    uint32_t brake_timeout = 0; // 超时计数，约 600ms 后强制退出
    while ((motor_L0.measure != 0 || motor_L1.measure != 0 ||
            motor_R0.measure != 0 || motor_R1.measure != 0) && brake_timeout < 300)
    {
        vTaskDelay(2);
        brake_timeout++;
    }
    vTaskDelay(100); // 确保完全停止
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
	//buzzer_on();
	while(1)
	{
		Chassis_Brake();
		vTaskDelay(2);
	}
}

/*红外+扫描仪陀螺仪角度修正*/
void Chassis_CorrectByInfrared(float correct_angle, float multiplier, float K)
{
    get_Infrared();
	Cross_getline(&Cross_Scaner);	// 陀螺仪模式下 Scaner 不更新，主动拍快照
	if ((infrared.head_left == 0 && infrared.head_right == 1) )
		angle.AngleG += correct_angle;
    else if ((infrared.head_left == 1 && infrared.head_right == 0) )
        angle.AngleG -= correct_angle;
    else if ((Cross_Scaner.detail & 0X0003))
        angle.AngleG += correct_angle * multiplier;
    else if ((Cross_Scaner.detail & 0XC000))
		angle.AngleG -= correct_angle * multiplier;
    else if ((Cross_Scaner.detail & 0X00FF))
        angle.AngleG += correct_angle * multiplier*K;
    else if ((Cross_Scaner.detail & 0XFF00))
        angle.AngleG -= correct_angle * multiplier*K;
}

/**
 * @brief 一键自检：架车在黑毯上时持续监测陀螺仪/灰度/循迹板
 * @note 每 200×5ms=1 秒检测一次，状态变化时才打印，安静时无输出
 * @note 放入 main_task 的 while(1) 循环中持续调用
 */
void Chassis_SelfCheck(void)
{
    static uint8_t last_error = 0;      // 0=无错误，非0=上次错误位图
    static float last_angle = 0.0f;     // 上次角度采样
    static uint8_t angle_ready = 0;     // 角度采样是否就绪（首次跳过）
    static uint32_t tick = 0;           // 周期计数器
	static float curr_angle;
    tick++;
    if (tick < 20) return;             // 每1秒检测一次 (5ms × 200)
    tick = 0;

    uint8_t error_now = 0;

    /* ---------- 1. 陀螺仪漂移检查 ---------- */
    {
        
		curr_angle= getAngleZ();
        if (angle_ready)
        {
            float diff = curr_angle - last_angle;
            // 处理 ±180° 边界
            if (diff > 180.0f) diff -= 360.0f;
            else if (diff < -180.0f) diff += 360.0f;
            if (((diff >= 0) ? diff : -diff) > 1.0f)
                error_now |= 0x01;
        }
        else
        {
            angle_ready = 1;             // 首次只记录，不判断
        }
        last_angle = curr_angle;
       // printf("%.2f\r\n", curr_angle);
       //打印所有初始角度
       //printf("%.2f,%.2f,%.2f\r\n", imu.yaw, imu.pitch, imu.roll);
    }

    /* ---------- 2. 灰度传感器检查 ---------- */
    {
        ScanerMode_Switch(Gray);
        vTaskDelay(2);                  // 让 ADC 采样
        for (uint8_t i = 0; i < 4; i++)
        {
            if (AD_Value_Gray[i] >= 500)
            {
                error_now |= 0x02;
                break;
            }
        }
       printf("%d,%d,%d,%d\r\n", AD_Value_Gray[0], AD_Value_Gray[1], AD_Value_Gray[2], AD_Value_Gray[3]);
    }

    /* ---------- 3. 循迹板检查 ---------- */
    {
        Cross_getline(&Cross_Scaner);
        if (Cross_Scaner.detail != 0)
            error_now |= 0x04;
        //printf_byte("%04X\r\n", Cross_Scaner.detail);
    }

    /* ---------- 报告：状态变化时才打印 ---------- */
    if (error_now != last_error)
    {
        if (error_now == 0)
        {
           // printf("[SELFCHECK] OK - 所有异常已恢复\r\n");
        }
        else
        {
           // printf("[SELFCHECK] FAIL -");
            // if (error_now & 0x01) send_play_specified_command(33);//陀螺仪（偏移）
            // if (error_now & 0x02) send_play_specified_command(31);//灰度（过高）
            // if (error_now & 0x04) send_play_specified_command(30);//循迹板（检测到线）
           // printf("\r\n");
        }
        last_error = error_now;
    }
}