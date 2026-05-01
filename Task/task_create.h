#ifndef __task_create_h__
#define __task_create_h__
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"
#include "cmsis_os.h"
#include "ArriveDetect_task.h"
//开始任务
extern TaskHandle_t Start_handler ; //定义开始任务句柄
void Start_task(void *pvParameters);//声明任务函数
#define Start_size  256   //任务堆栈大小
#define Start_task_priority 32  //任务优先级


//主控任务
extern TaskHandle_t main_handler ; //定义主控任务句柄
void main_task(void *pvParameters);//声明任务函数
//#define main_size  1024*3  //任务堆栈大小
#define main_size  1024*2  //任务堆栈大小
#define main_task_priority  12//7  //12 //任务优先级12

extern TaskHandle_t xHandle_ArriveDetect;//定义检测节点任务
//void ArriveDetect_task(void *pvParameters);//声明任务函数
#define ArriveDetect_size  512   //任务堆栈大小
#define ArriveDetect_task_priority 10  //任务优先级

void Start_task_create(void);
void main_task_create(void);
void create_ArriveDetect_task(void);
#endif
