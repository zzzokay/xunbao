#include "turn.h"
#include "imu.h"
#include "pid.h"
#include "chassis_api.h"
#include "math.h"
#include "map.h"
#include "motor_task.h"
#include "uart.h"
#include "motor.h"
#include "scaner.h"
#include "openmv.h"
#include "encoder.h"
#include "motor_task.h"
#include "bsp_buzzer.h"


volatile struct Angle angle = {0, 0};
uint8_t Turn360_Flag = 0;

uint8_t gryo_turn=0;


/*计算两角度夹角*/
float need2turn(float nowangle, float targetangle)
{
	float need2Turn;
	need2Turn = targetangle - nowangle; // 实际所需转的角度
	if (need2Turn > 180)
	{
		need2Turn -= 360;
	}
	else if (need2Turn <= -180)
	{
		need2Turn += 360;
	}

	return need2Turn;
}

/*计算一次补正值*/
void mpuZreset(float sensorangle, float referangle)
{
	imu.compensateZ = need2turn(sensorangle, referangle);
}

/*返回瞬时测量值+补正值*/
float getAngleZ(void)
{
	float targetangle;
	targetangle = get_latest_yaw() + imu.compensateZ;

	if (targetangle > 180)
		targetangle -= 360;
	else if (targetangle <= -180)
		targetangle += 360;

	return targetangle;
}

/*原地转（内部基函数，right_ratio 控制左右电机速比，平台转弯用 1.3 补偿阻力）*/
static uint8_t Turn_Angle_Base(float Angle, float right_ratio)
{
	static uint8_t inited = 0;
	float GTspeed;
	float now_angle;

	if (Angle > 180)
		Angle -= 360;
	else if (Angle < -180)
		Angle += 360;

	now_angle = getAngleZ();
	gyroT_pid.measure = need2turn(now_angle, Angle);
	gyroT_pid.target = 0;

	if (fabsf(gyroT_pid.measure) < 1.0f)
	{
		motor_all.Lspeed = motor_all.Rspeed = 0;
		gyroT_pid.integral = 0;
		gyroT_pid.output = 0;
		return 1;
	}

	GTspeed = positional_PID(&gyroT_pid, &gyroT_pid_param);

	// 死区补偿：输出太小但误差仍存在时，强制最小输出克服摩擦
	if (fabsf(GTspeed) < 5.0f && fabsf(gyroT_pid.measure) > 1.0f)
	{
		GTspeed += (GTspeed > 0) ? 5.0f : -5.0f;
	}

	if (GTspeed >= motor_all.GyroT_speedMax)
		GTspeed = motor_all.GyroT_speedMax;
	else if (GTspeed <= -motor_all.GyroT_speedMax)
		GTspeed = -motor_all.GyroT_speedMax;
	//打印转速和当前角度误差
	if(inited++ % 10 == 0)
	printf("Turn_Angle_Base GTspeed: %.2f, Angle Error: %.2f\n", GTspeed, gyroT_pid.measure);
	motor_all.Lspeed = GTspeed;
	motor_all.Rspeed = -GTspeed * right_ratio;
	return 0;
}

/*平台转（右电机 x1.3 补偿平台阻力）*/
uint8_t Stage_turn_Angle(float Angle)
{
	return Turn_Angle_Base(Angle, 1.3f);
}


/*闭环转圈*/
void Turn_Angle_Relative(float Angle1) // 左180到右-180,速度必须是正的，
{
	float Turn_Angle_Before = 0, Turn_Angle_Targe = 0;

	Turn_Angle_Before = getAngleZ();			   // 读取当前的角度//@@@@@
	Turn_Angle_Targe = Turn_Angle_Before + Angle1; // 目标角度设为绝对坐标
	/*******************如果存在临界状态，把目标角度转化为绝对坐标******180 0 -180*************/
	if (Turn_Angle_Targe > 180)
	{
		Turn_Angle_Targe = Turn_Angle_Targe - 360;
	}
	else if (Turn_Angle_Targe < -180)
	{
		Turn_Angle_Targe = Turn_Angle_Targe + 360;
	}

	angle.AngleT = Turn_Angle_Targe;
	pid_mode_switch(is_Turn); // 进入转弯
}

/*陀螺仪原地转（左右对称）*/
uint8_t Turn_Angle(float Angle)
{
	return Turn_Angle_Base(Angle, 1.0f);
}




/*将给的角度转为360°制*/
float Change360Angle(float Angle)
{
	if (Angle < 0)
		Angle = 360 - fabs(Angle);//360
	return Angle;
}

/*单步360°转（梯形速度曲线：加速→全速→减速→到位停）*/
static float turn360_accumulated = 0;   // 已转过的累计角度
static float turn360_prev_yaw = 0;      // 上一次的 yaw 值

#define TURN360_FULL_SPEED   25.0f   // 全速阶段速度
#define TURN360_MIN_SPEED     8.0f   // 起步/终点最低速度（克服摩擦）
#define TURN360_ACCEL_END    30.0f   // 加速阶段结束角度
#define TURN360_DECEL_START 300.0f   // 开始减速的角度
#define TURN360_STOP_ANGLE  358.0f   // 到位判定角度

uint8_t Turn360Step(void)
{
	// 累加 5ms 内转过的角度
	float curr_yaw = get_latest_yaw();
	float delta = curr_yaw - turn360_prev_yaw;
	turn360_prev_yaw = curr_yaw;

	// 处理 ±180° 边界回绕（例：-179° → 180° 实际只转了 1°）
	if (delta > 180.0f)  delta -= 360.0f;
	if (delta < -180.0f) delta += 360.0f;

	turn360_accumulated += delta;

	float turned = fabsf(turn360_accumulated);  // 已转角度（取绝对值）

	// 到位判定
	if (turned >= TURN360_STOP_ANGLE)
	{
		motor_all.Lspeed = motor_all.Rspeed = 0;
		Turn360_Flag = 0;
		return 1;
	}

	// 梯形速度曲线
	float GTspeed;
	if (turned < TURN360_ACCEL_END)
	{
		// 加速阶段：MIN_SPEED → FULL_SPEED
		float ratio = turned / TURN360_ACCEL_END;
		GTspeed = TURN360_MIN_SPEED + (TURN360_FULL_SPEED - TURN360_MIN_SPEED) * ratio;
	}
	else if (turned < TURN360_DECEL_START)
	{
		// 全速阶段
		GTspeed = TURN360_FULL_SPEED;
	}
	else
	{
		// 减速阶段：FULL_SPEED → MIN_SPEED
		float ratio = (TURN360_STOP_ANGLE - turned) / (TURN360_STOP_ANGLE - TURN360_DECEL_START);
		GTspeed = TURN360_MIN_SPEED + (TURN360_FULL_SPEED - TURN360_MIN_SPEED) * ratio;
	}
	//打印转速和已转角度
	//printf("Turn360 GTspeed: %.2f, Turned: %.2f\n", GTspeed, turned);
	// 顺时针：左轮正、右轮负
	motor_all.Lspeed =  GTspeed;
	motor_all.Rspeed = -GTspeed;

	return 0;
}

/*原地360（简化版，去掉 MustBeZero 脉冲机制）*/
void Turn_Angle360(void)
{
	turn360_prev_yaw = get_latest_yaw();
	turn360_accumulated = 0;
	Turn360_Flag = 1;
	pid_mode_switch(is_Turn);
	while(Turn360_Flag)
		vTaskDelay(2);
}

/*自平衡走*/
uint8_t Go_Angle(float angle_want, float speed,volatile struct Motors *motor)//TODO:返回值无定义，可以改
{
	float GGspeed, now_angle;

	now_angle = getAngleZ();

	gyroG_pid.measure = need2turn(now_angle, angle_want);
	gyroG_pid.target = 0;

	GGspeed = positional_PID(&gyroG_pid, &gyroG_pid_param);

	GGspeed = GGspeed * fabsf(speed)/ 50;

	if (GGspeed >= motor->GyroG_speedMax)
	{
		GGspeed = motor->GyroG_speedMax;
	}
	else if (GGspeed <= -motor->GyroG_speedMax)
	{
		GGspeed = -motor->GyroG_speedMax;
	}

	motor->Lspeed = speed + GGspeed;
	motor->Rspeed = speed - GGspeed;

	return 1;
}

/*开环转*/
void FreeTurn(float Angle, float L, float R)
{
	pid_mode_switch(is_Free);
	if (Turn360_Flag == 1)
	{
		motor_set_pwm(1, -L);
		motor_set_pwm(2, -L);
		motor_set_pwm(3, R);
		motor_set_pwm(4, R);
		while (fabsf(Angle - getAngleZ()) > 5) // 如果角度相差12一直转
		{
			vTaskDelay(2);
		}
	}
	else
	{
		if (need2turn(getAngleZ(), Angle) > 0) // 逆时针转
		{
			while (fabsf(Angle - getAngleZ()) > 20) // 如果角度相差12一直转//20//30
			{
				motor_set_pwm(1, -L);
				motor_set_pwm(2, -L);
				motor_set_pwm(3, R);
				motor_set_pwm(4, R);
				if (nodesr.nowNode.function != UpStage && nodesr.nowNode.function != BSoutPole && nodesr.nowNode.function != BHM)
				{
					getline_error();
					if (Scaner.lineNum == 1 && ((Scaner.detail & 0x7E0) != 0) && (fabs(need2turn(nodesr.nextNode.angle, getAngleZ())) < fabs(need2turn(nodesr.nextNode.angle, nodesr.nowNode.angle)) * 0.3f))
					{
						break;
					}
				}
			}
			//		}
		}
		if (need2turn(getAngleZ(), Angle) < 0) // 顺时针转
		{
			while (fabsf(Angle - getAngleZ()) > 20) // 如果角度相差12一直转
			{
				motor_set_pwm(1, L);
				motor_set_pwm(2, L);
				motor_set_pwm(3, -R);
				motor_set_pwm(4, -R);
				if (nodesr.nowNode.function != UpStage && nodesr.nowNode.function != BSoutPole && nodesr.nowNode.function != BHM)
				{
					getline_error();
					if (Scaner.lineNum == 1 && ((Scaner.detail & 0x7E0) != 0) && (fabs(need2turn(nodesr.nextNode.angle, getAngleZ())) < fabs(need2turn(nodesr.nextNode.angle, nodesr.nowNode.angle)) * 0.3f))
					{
						break;
					}
				}
			}
		}
	}
}


