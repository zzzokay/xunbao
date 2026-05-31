#ifndef __motor_task_h__
#define __motor_task_h__
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"
#include "sys.h"
//开始任务
extern TaskHandle_t motor_handler ; 				//定义开始任务句柄
void motor_task(void *pvParameters);//声明任务函数
#define motor_size  512   					//任务堆栈大小
#define motor_task_priority 10 //7 //10		//任务优先级
#define PI  3.1415926535f
#define is_Front 0
#define is_Back  1
void motor_task_create(void);
extern volatile uint8_t PIDMode;

typedef enum {
	is_No = 0,  //关闭所有操作
	is_Free,   //保留切换前的状态1
	is_Line,   //循迹2
	is_Turn,   //转弯3
	is_Gyro,   //自平衡4
	
};

extern uint8_t open_qiang_jiao;
extern uint8_t Nosmall;
extern int MOTOR_PWM_MAX;
/*----------内部用----------------------*/
void get_motor_speed(void);
void handle_line_error(void);
void handle_motor_speed(void);
void handle_qiang_jiao(void);
void handle_infrared(void);
void handle_line_mode(void);
void handle_turn_mode(void);
void handle_gyro_mode(void);
void handle_mode_switch(uint8_t target_mode);
void handle_led_mouse(void);
void handle_target_speed(void);
void handle_pid_control(void);
void handle_now_mode(uint8_t mode);
#endif
