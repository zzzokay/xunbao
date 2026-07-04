#ifndef __CHASSIS_API_H
#define __CHASSIS_API_H

#include "stdint.h"
#include "motor_task.h"
#include "pid.h"
#include "turn.h"

/* ==========================================================
 * 彻底解耦设计：底盘控制 API 中间件 (Chassis API Layer)
 * 职责：对上（map.c）提供高级小车行为接口，对下（motor_task.c）管理具体的PID和游龙等底层控制算法
 * ========================================================== */
#define SPEED0	25
#define SPEED1	36
#define SPEED2	45
#define SPEED25	55
#define SPEED3	60
#define SPEED4	70
#define SPEED5  75
/* 循迹边界模式 */
typedef enum {
    TRACK_ALL = 0,        // 正常双边循迹
    TRACK_LEFT_EDGE,         // 左单边循迹 (忽略右侧)
    TRACK_RIGHT_EDGE,        // 右单边循迹 (忽略左侧)
    TRACK_NEAR_CENTER            // 中心就近跟踪（离中心最近的连续亮灯段）
} LineTrackMode_e;

// 底盘状态结构体
struct Motors
{
	float Lspeed,Rspeed;		//速度
	float Cspeed;				//寻迹速度
	float Gspeed;				//自平衡速度
	float GyroT_speedMax;		//转弯最大速度
	float GyroG_speedMax;		//自平衡最大速度
	float Line_speedMax;		//巡线差速最大值
	
	float encoder_avg;			//编码器读数 
	float Distance;				//路程
	
	float Cincrement;			//循迹加速度
	float CDOWNincrement;  		//循迹减速
	float Gincrement;			//陀螺仪加速度  
	float GDOWNincrement;	    //陀螺仪减速

};




extern volatile struct Motors motor_all;
extern float TC_speed, TG_speed;

void gradual_cal(float *gradual, float target, float increment1, float increment2);
void CarBrake(void);
void CarBrake_Stop(void);


/* ===================== 提供给 map.c 的高级调用接口 ===================== */

/**
 * @brief 初始化底盘状态
 */
void Chassis_Init(void);

/**
 * @brief 设置底盘工作模式（循迹、陀螺仪、转弯、停车等）
 */
void Chassis_SetMode(uint8_t mode);

/**
 * @brief 设定底盘目标速度
 */
void Chassis_SetTargetSpeed(float speed);

/**
 * @brief 设定边缘循迹模式（如靠左、靠右）
 */
void Chassis_SetTrackMode(LineTrackMode_e mode);

/**
 * @brief 设定陀螺仪直行目标角度
 */
void Chassis_SetGyroAngle_Go(float angle);

/**
 * @brief 设定转弯目标角度
 */
void Chassis_SetGyroAngle_Turn(float angle);


/**
 * @brief 统一的底盘运动控制入口
 */
void Chassis_MotorControl(uint8_t target_mode, float LSPEED, float RSPEED, float aim);

/**
 * @brief 开启游龙防护逻辑
 */
void Chassis_EnableAntiSnake(void);

/**
 * @brief 开启丢线保护
 * 当 line_data[] 全部无效持续 LINE_LOST_THRESHOLD 个周期后调用 Chassis_Brake()
 * 一次性触发后自动禁用
 */
void Chassis_EnableLineLostProtection(void);

/**
 * @brief 关闭丢线保护并重置计数器
 */
void Chassis_DisableLineLostProtection(void);

/**
 * @brief 使能横滚角超限保护（imu.roll 与 basic_r 偏差 > 40° 时死停）
 */
void Chassis_EnableRollProtection(void);

/**
 * @brief 关闭横滚角超限保护
 */
void Chassis_DisableRollProtection(void);

/**
 * @brief 使能堵转保护（output 饱和或跳变时刹车）
 */
void Chassis_EnableStallProtection(void);

/**
 * @brief 关闭堵转保护
 */
void Chassis_DisableStallProtection(void);

/**
 * @brief 刹车制动
 */
void Chassis_Brake(void);

/**
 * @brief 清除累计里程计
 */
void Chassis_ClearMileage(void);

/**
 * @brief 获取当前累计里程（基于纯编码器底层换算）
 */
float Chassis_GetMileage(void);



/**
 * @brief 临时模式行驶：切换模式、行驶固定距离、退出后恢复巡线并清零边缘忽略
 */
void Chassis_DriveDistance_Blocking(uint8_t mode, float distance, float speed, float aim, uint8_t edge_ignore);

/**
 * @brief 临时替换循迹 PID 参数，主要用于左右巡线加权转弯场景
 * @note 通过 API 封装，避免 map.c 直接访问底层 line_pid_param
 */
void Chassis_OverrideLinePid(float kp, float ki, float kd, float outputMax);

/**
 * @brief 临时覆盖原地转弯 PID 参数，并可同时覆盖转弯最大速度
 */
void Chassis_OverrideTurnPid(float kp, float ki, float kd, float turnSpeedMax);

/**
 * @brief 恢复先前保存的循迹 PID 参数
 */
void Chassis_RestoreLinePid(void);

/**
 * @brief 直接设置陀螺仪转弯模式的最大速度
 */
void Chassis_SetGyroTSpeed(float speed);

/**
 * @brief 恢复原先的原地转弯 PID 参数
 */
void Chassis_RestoreTurnPid(void);

/**
 * @brief 临时覆盖陀螺仪直行 PID 参数
 */
void Chassis_OverrideGyroPid(float kp, float ki, float kd, float gyroSpeedMax);

/**
 * @brief 恢复原先的陀螺仪直行 PID 参数
 */
void Chassis_RestoreGyroPid(void);

void Chassis_Turn_By_StopGyro_Blocking(float target_angle, float current_angle);

void Chassis_Turn360_Blocking(void);

void Chassis_Turn_By_Gyro_Blocking(float target_angle, float current_angle);

void Chassis_SetCatchSensorNum(uint8_t num);

void Chassis_Turn_By_LeftLine_Blocking(float target_angle, float current_angle, float speed);

void Chassis_Turn_By_RightLine_Blocking(float target_angle, float current_angle, float speed);

void Chassis_SetEdgeIgnore(uint8_t num);

/**
 * @brief 红外+扫描仪陀螺仪角度修正
 * 检测到单侧红外或扫描仪偏移时，调整陀螺仪目标角度
 * @param correct_angle 修正角度（度）
 * @param multiplier 左偏修正倍率（左修正 = correct_angle * multiplier）
 * @param K 右偏修正倍率（右修正 = correct_angle * K / correct_angle * multiplier * K）
 */
void Chassis_CorrectByInfrared(float correct_angle, float multiplier, float K);
/* ===================== 提供给 motor_task.c 的底层刷新接口 ===================== */

/**
 * @brief 必须置于 motor_task 的 5ms 循环中
 * @note 内部包含了原先塞在 map.c 里的“游龙保护算法”、PID自适应调节
 */
void Chassis_Periodic_Update_5ms(void);

void Want2Go(float Dis);

/**
 * @brief 一键自检：架车在黑毯上时持续监测陀螺仪/灰度/循迹板状态
 * @note 放入 main_task 的 while(1) 循环中持续调用，每1秒检测一次
 * @note 状态变化时才输出，安静时无输出
 */
void Chassis_SelfCheck(void);

#endif /* __CHASSIS_API_H */
