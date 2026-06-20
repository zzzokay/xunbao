#include "map.h"
#include "barrier.h"
#include "sys.h"
#include "usart.h"
#include "QR.h"
#include "delay.h"
#include "scaner.h"
#include "imu.h"
#include "turn.h"
#include "motor_task.h"
#include "bsp_linefollower.h"
#include "math.h"
#include "bsp_buzzer.h"
#include "encoder.h"
#include "uart.h"
#include "openmv.h"
#include "motor.h"
#include "task_create.h"
#include "chassis_api.h"

/******************  记录地图状态和小车状态的全局变量  *************************/
                                            
struct Map_State map = {0,0};   //point //routine                                
NODESR nodesr;   	//节点flag和各个节点信息
				/*	flag 0位为1表示需要转弯0表示直行
					flag 1位为是否路径判断
					flag 2位为是否到达节点
					flag 3位为arrive和temp标志
					flag 4位为Z轴校正
					flag 5位为路径计算起点标志 
					flag 6位为有没有
					flag 7位为记录*/
			// 分别lastnode nownode nextnode 三个结构体变量,每个结构体存储对应节点数据
			/* u8 nodenum;     //节点编号
				 u32  flag;     //节点标志位
				 float angle;   //角度	
				 u16	step;       //步长
				 float speed;   //运行速度
				 u8 function;    //节点功能 */   
				

/******************************************************************************/



uint8_t isAllRoute = 1;    /*是否全图,选择路径*/
//u8 route[100] = {B1, N1, P1, N1, B2, N4, N5, N6, P4, N6, N5, N12, 0XFF};  //调试时的初始路径
u8 route[100] = {B1, N1,P1, N1,B2,0XFF};  //调试时的初始路径

/*简单*/
//uint8_t isAllRoute = 0;
//u8 route[100] = {N4,B2,N1,P1,0XFF};
//u8 route[100] = {B3,N2,P2,0XFF};

//uint8_t isAllRoute = 1;
//u8 route[100] = {B1, N1, P1, N1, B2, N4, N5, N12 ,0XFF};
 
 
/***************任务***************/
//u8 route[100] = {P7,N20,0XFF};
//u8 route[100] = {B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,0XFF};//任务二
/***************假山***************/
//u8 route[100] = {B6,N20,0XFF};

/***************跷跷板***************/
//u8 route[100] = {B9,N7,P6,N7,B8,N9,C3,N14,0XFF};
/***************旋转平台***************/
// u8 route[100] = {N12,N16,N18,B5,N19,C6,B7,N22,B6,N20,P7,N20,0XFF};
 
 /**************旋转平台波动板*************/
// u8 route[100] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,0XFF};

/************************************************************    *地图路径*    **********************************************************************************************************************************************88 */
/*D2关D3关，去D4*/
u8 door1route[100] = {N3, N8, 0XFF};
/*D2开 D3开*/
u8 door2route[100] = {N12, N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8,0xFF};
/*D2开*/
u8 door3_1route[50] = {N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8,0xFF};
	
/*D2开 D3开 D4开*/
u8 door4route[100] = {N12, N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8, C9, N22, B6, N20, P7, N20, C4, C8, C7, N14, C3, N9, B9, N7, P6, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N8, N3, N4, B3, N2, P2, 0XFF};
/*D2开 D3关，暂时去掉D5*/
u8 door5route[100] = {N12, N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8, C9, N22, B6, N20, P7, N20, C4, C8, C7, N14, C3, N9, B9, N7, P6, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, 0XFF};
/*D5开*/
u8 door6route[100] = {N4, B3, N2, P2, 0XFF};
/*D2开 D3开 D5开*/
u8 door7route[100] = {N8, N3, N4, B3, N2, P2, 0xFF};
/*D2开 D5开 D4开*/
u8 door8route[100] = {N4, B3, N2, P2, 0XFF};
/*D2开 D3开 D4开 D5开全*/
u8 door9route[100] = {N12, N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8, C9, N22, B6, N20, P7, N20, C4, C8, C7, N14, C3, N9, B9, N7, P6, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, N4, B3, N2, P2, 0XFF}; // 没去P3
/*D2开 D3关，暂时去掉D5*/
u8 door10route[100] = {N12, N13, P5, N13, N12, N16, N18, B5, N19, C6, B7, N22, C9, P8, C9, N22, B6, N20, P7, N20, C4, C8, C7, N14, C3, N9, B9, N7, P6, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, 0XFF}; // N3前没写，没P3
/*D2开 D5开 D4开*/
u8 door11route[100] = {N5, N4,B3, N2, P2, 0XFF};
/*D2开*/
u8 door12route[100] = {N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8, C9, N22, B6, N20, P7, N20, C4, C8, C7, N14, C3, N9, B9, N7, P6, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, 0XFF};

	
/*平台5到平台7*/
u8 rout_57[50] = {N13,P5,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9, 0XFF};
/*平台5到平台8*/
u8 rout_58[50] = {N13,P5,N13,N12,N16,N18,B5,N19,C6,B7,N22,B6,N20,P7,N20,0XFF};
/*平台6到平台8*/
u8 rout_68[50] = {N9,B9,N7,P6,N7,B8,N9,C3,N14,C7,C8,C4,N20,P7,N20, 0XFF};
/*平台6到平台7*/
u8 rout_67[50] = {N9,B9,N7,P6,N7,B8,N9,C3,N14,C7,C8,C4,N20,B6,N22,C9,P8,C9, 0XFF};

/*******************************************************************************************************************************************************************************************************************************************************/

 
/*地图初始化*/
void mapInit()
{
	map.routetime = 0;
	map.point = 0;
	nodesr.flag = 0;
	// /***************任务***************/
	
//	nodesr.lastNode.nodenum = N10;
//	nodesr.nextNode.nodenum = B9;
//  nodesr.nowNode = Node[getNextConnectNode(N10, N9)];//跷跷板
	
//	nodesr.lastNode.nodenum = C9;
//	nodesr.nextNode.nodenum = B6; 	
//	nodesr.nowNode = Node[getNextConnectNode(C9, N22)];//任务二
	
	
	//nodesr.lastNode = Node[getNextConnectNode(N6, P4)];
//	nodesr.nowNode = Node[getNextConnectNode(N5, N4)];
	
	
//	nodesr.nowNode = Node[getNextConnectNode(C4, N20)];//任务
	//nodesr.nowNode = Node[getNextConnectNode( B7, N22)];//假山
//	nodesr.nowNode = Node[getNextConnectNode(N10, N9)];//跷跷板
//	nodesr.nowNode = Node[getNextConnectNode(P8, C9)];//旋转平台波动板	
	/***************简单***************/
	nodesr.nowNode.nodenum = N2;        //起点(终点)    		//N2
	nodesr.nowNode.angle = 0;           //起始角度    	//0
	nodesr.nowNode.function = NONE;        //起始功能    	//1
	nodesr.nowNode.speed = SPEED1;
	nodesr.nowNode.step= 10;            //步长
	nodesr.nowNode.flag = CLEFT|RIGHT_LINE;
	nodesr.nextNode = Node[getNextConnectNode(nodesr.nowNode.nodenum, route[map.point++])];
}

/*第二轮竞赛初始化*/
void mapInit1(void)
{
	map.point = 0;
	nodesr.flag = 0;
	nodesr.nowNode.nodenum = N2;                //起始点    		
	nodesr.nowNode.angle = 0;                      //起始角度    	
	nodesr.nowNode.function = NONE;                //起始功能    	
	nodesr.nowNode.speed = SPEED0;                
	nodesr.nowNode.step= 2;                           
	nodesr.nowNode.flag = CLEFT|RIGHT_LINE;        
}
	
/*
 * 获取从当前节点到目标节点的连接关系在Node数组中的下标
 * 
 * 函数说明
 * - nownode：当前目标节点编号
 * - nextnode：下一个目标节点编号
 * 实现原理
 * 1. 从Address数组获取当前节点的连接关系起始地址
 * 2. 从ConnectionNum数组获取当前节点的连接节点数量
 * 3. 循环查找目标连接节点
 */
u8 getNextConnectNode(u8 nownode,u8 nextnode) 
{
	unsigned char rest = ConnectionNum[nownode];	//获取当前节点的连接数
	unsigned char addr = Address[nownode];		//得到首地址
	int i = 0;
	for (i = 0; i < rest; i++) 
	{
		if(Node[addr].nodenum == nextnode)		//返回目标地址	
			return addr;
		addr++;
	}
	return 0;
}



/* 获取对应节点的原地转弯前的前进距离判断 */
static float GetForwardDistanceBeforeTurn(u8 last, u8 now, u8 next)
{
	if (last == P8 && now == C9 && next == N22) return 28.0f;
	if (last == S1 && now == N3 && next == P3) return 15.0f;
	if (last == C8 && now == C7 && next == N14) return 20.0f;
	if (last == C9 && now == N22 && next == B6) return 20.0f;
	if (last == B3 && now == N2 && next == P2) return 30.0f;
	if (last == B9 && now == N7 && next == P6) return 18.0f;
	if (last == P6 && now == N7 && next == B8) return 25.0f;
	if (last == P7 && now == N20 && next == C4) return 30.0f;
	if (last == N8 && now == N5 && next == N4) return 30.0f;
	if (last == N8 && now == N3 && next == P3) return 15.0f;
	if (last == N8 && now == N3 && next == N4) return 20.0f;
	if (last == N9 && now == N10 && next == N8) return 26.0f;
	if (last == N20 && now == C4 && next == C8) return 25.0f;
	if (last == C3 && now == N9 && next == B9) return 45.0f;
	if (now == N20 && next == P7) return 30.0f;
	if (last == N10 && now == N9 && next == B9) return 40.0f;
	if (last == B8 && now == N9 && next == N10) return 25.0f;
	return 20.0f;
}

/* 获取对应节点的陀螺仪不停车转弯前的前进距离判断 */
static float GetForwardDistanceBeforeGyroTurn(u8 last, u8 now, u8 next)
{
	if (last == B2 && now == N4 && next == N5)return 7.0f; 
	if((last == B6 && now == N20 && next == C4) ||
		(last == C4 && now == N20 && next == B6) ||
		(last == B2 && now == N1 && next == P1)) return 5.0f;
	if (last == B3 && now == N2 && next == P2) return 15.0f;
	if (last == P3 && now == N3 && next == N8) return 5.0f;
	if (last == P8 && now == C9 && next == N22) return 3.0f;
	if (last == S1 && now == N3 && next == N8) return 8.0f;
	if (last == N3 && now == N4 && next == B3) return 15.0f;
	if (last == N5 && now == N12 && next == N13) return 3.0f;
	if (last == N5 && now == N6 && next == S2) return 12.0f;
	if (last == N8 && now == N12 && next == N13) return 4.0f;
	if (last == N8 && now == N3 && next == P3) return 20.0f;
	if (last == N8 && now == N3 && next == S1) return 30.0f;
	if (last == N9 && now == N10 && next == N8) return 4.0f;
	if (last == N10 && now == N3 && next == S1) return 4.0f;
	if (last == N15 && now == N10 && next == N8) return 5.0f;
	if (last == C7 && now == C8 && next == C4) return 15.0f;
	if (last == P1 && now == N1 && next == B2)return 4.0f; 
	return 0.0f; // 默认不前进，走原逻辑未修改
}

/* 获取对应节点的特定直线路径加速判断 */
static void Check_And_Apply_SpeedUp(void)
{
	if ((nodesr.lastNode.nodenum == N4 && nodesr.nowNode.nodenum == N5 && nodesr.nextNode.nodenum == N6) ||
		(nodesr.lastNode.nodenum == N5 && nodesr.nowNode.nodenum == N6 && nodesr.nextNode.nodenum == P4) ||
		(nodesr.lastNode.nodenum == N5 && nodesr.nowNode.nodenum == N4 && nodesr.nextNode.nodenum == N3) ||
		(nodesr.lastNode.nodenum == P3 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == N4))
	{	
		nodesr.nowNode.speed = SPEED4;
		Chassis_SetTargetSpeed(nodesr.nowNode.speed);
	}
}

/* 无需转弯时的特例直行处理 */
static void Handle_NoTurn_StraightPath(void)
{
	if ((nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == P3) ||
		(nodesr.nowNode.nodenum == N4 && nodesr.nextNode.nodenum == N3) ||
		(nodesr.nowNode.nodenum == N4 && nodesr.nextNode.nodenum == N5))
	{
		Chassis_DriveDistance_Blocking(is_Gyro, 20.0f, nodesr.nextNode.speed, getAngleZ(), 0);
	}
	else if (nodesr.nowNode.nodenum == N13 && nodesr.nextNode.nodenum == P5) 
	{
		Chassis_DriveDistance_Blocking(is_Line, 20.0f, nodesr.nextNode.speed, 0.0f, 6);
	}
	else if (nodesr.nowNode.nodenum == N1 && nodesr.nextNode.nodenum == P1)
	{
		Chassis_DriveDistance_Blocking(is_Line, 20.0f, nodesr.nextNode.speed, 0.0f, 6);
	}
	else if ((nodesr.lastNode.nodenum == P3 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == N4)||
			(nodesr.lastNode.nodenum == P4 && nodesr.nowNode.nodenum == N6 && nodesr.nextNode.nodenum == N5))
	{
		Chassis_DriveDistance_Blocking(is_Line, 20.0f, nodesr.nextNode.speed, 0.0f, 7);
	}
	else if ((nodesr.nowNode.nodenum == N13 && nodesr.nextNode.nodenum == N12)||(nodesr.nowNode.nodenum == N12 && nodesr.nextNode.nodenum == N13))
	{
		Chassis_DriveDistance_Blocking(is_Line, 20.0f, nodesr.nextNode.speed, 0.0f, 7);
	}
	else if ((nodesr.nowNode.nodenum == P5 && nodesr.nextNode.nodenum == N13)||(nodesr.nowNode.nodenum == N13 && nodesr.nextNode.nodenum == P5))
	{
		Chassis_DriveDistance_Blocking(is_Line, 25.0f, nodesr.nextNode.speed, 0.0f, 7);
	}
	else
	{
		Chassis_DriveDistance_Blocking(is_Line, 10.0f, nodesr.nextNode.speed, 0.0f, 7);
	}
}



	/**-------------------------------------------------Cross函数 - 整个流程的核心---------------------------------------------------------------------------------------------------------------------------
 * 
 * 
 * 功能：
 * - 解析路径数组route并执行相应的路径动作
 * - 处理节点的巡线、转弯、速度切换等逻辑
 * - 执行节点的特殊功能（如爬坡、过桥等）
 * - 管理地图状态和支持多轮竞赛
 * 
 * 执行流程：
 * 1. 初始化路径（map.point == 0时）
 * 2. 节点前半段处理（is_near_end == 0时）
 * 3. 节点后半段处理（is_near_end == 1时）
 * 4. 路径点切换节点处理
 * 5. 特殊功能处理

 * 注意：
 * route数组存储的是节点编号，Node数组是结构体数组，取nextnode的值要用到数组下标函数getNextConnectNode
 * 每段路径都指的是两个节点之间的路径
 * nodesr.nowNode是小车这一小段路径的终点，lastNode是起点，nextNode是下一个路径的终点
 * 当小车到达nowNode时，nowNode成为lastnode，nextNode成为nowNode。
 * 前70%路径要进行巡线
 * 超过70%时触发节点终点检查
 * 需要区分nodesr.flag和nodesr.nowNode.flag
 * nodesr.flag记录小车当前状态
 * nodesr.nowNode.flag是事先地图文件写入的标志，用于指导小车行为

 * 关键状态变量：
 * - map.point：路径数组的当前索引
 * - map.routetime：地图运行次数
 * - nodesr：包含当前、上一个、下一个节点的信息
 */
void Cross(void)
{
	static uint8_t route_state = 0;           //是否过半程
	static uint8_t is_near_end = 0;          //是否接近终点超过70%   默认为0表示没超过70%

	/*坐标计算处理 - 路径开始时的初始化*/
	 /***************执行简单路径，调试时使用******************/
	if(map.point == 0)
	{	   	
		if (isAllRoute == 0) 
			Chassis_SetTargetSpeed(nodesr.nowNode.speed); // 设定初始速度	
	}
  	/**********************************************************/

	/*前半段 - 执行巡线*/
	if(is_near_end == 0)
	{		
			if(route_state == 0)//路径开始
			{		
				//打印当前路径信息：开始
				////printf("Starting new path\n");
					//清零里程
					Chassis_ClearMileage();
					 
					//寻迹中心目标值
					if(nodesr.nowNode.nodenum == N9 && nodesr.nextNode.nodenum == N10)
						Chassis_SetCatchSensorNum(line_weight[7]);  
					else
						Chassis_SetCatchSensorNum(0);

					//忽略边缘
					Chassis_SetEdgeIgnore(0);
				
					//设置寻线实际值方式
					if((nodesr.nowNode.flag & LEFT_LINE) == LEFT_LINE){	
						Chassis_SetTrackMode(TRACK_LEFT_EDGE);}

					else if((nodesr.nowNode.flag & RIGHT_LINE) == RIGHT_LINE){
						Chassis_SetTrackMode(TRACK_RIGHT_EDGE);}

					else if((nodesr.nowNode.flag & LiuShui) == LiuShui){
						Chassis_SetTrackMode(TRACK_LIUSHUI);}

					else{
						Chassis_SetTrackMode(TRACK_ALL);}
					route_state=1;//TODO:标志位可以优化
					

			}		
		 /*前方路径判断 - 未超过50%路径*/ 				
		    if( route_state == 1)
			{	

				//printf("In the first half of the path\n");
					//巡线
					Chassis_SetMode(is_Line);	
					
					//设置当前节点的目标速度
					Chassis_SetTargetSpeed(nodesr.nowNode.speed);
					
					//检测并应用直线路径加速（特定长直线加速）
					Check_And_Apply_SpeedUp();

					
					// 防游龙算法已移至底盘API
					Chassis_EnableAntiSnake(); // 激活游龙防护标志
					Chassis_EnableLineLostProtection();// 激活丢线保护标志
					Chassis_EnableRollProtection(); // 激活翻滚保护标志

					route_state = 2; // 标记已过半程，确保该处理只执行一次
			}		        
			
			/*过半50%路径，执行巡线模式切换*/
			if(fabsf(Chassis_GetMileage()) >= 0.5f*nodesr.nowNode.step && route_state == 2)
			{
				//打印：走完一半路径，切换巡线模式
					//printf("Passed 50%% of the path, switching line following mode\n");
					if((nodesr.nowNode.flag & Temp_L) == Temp_L)
					{
						Chassis_SetTrackMode(TRACK_LEFT_EDGE);
					}
					else if((nodesr.nowNode.flag & Temp_R) == Temp_R)
					{
						Chassis_SetTrackMode(TRACK_RIGHT_EDGE);
					}
					else if((nodesr.nowNode.flag & Temp_LiuShui) == Temp_LiuShui)
					{
						Chassis_SetTrackMode(TRACK_LIUSHUI);
					}
					route_state = 3; // 标记已完成巡线模式切换，确保该处理只执行一次
			}
			/*节点后半段 - 超过70%路径*/
			if(fabsf(Chassis_GetMileage()) >= 0.7f*nodesr.nowNode.step && route_state == 3 )
			{
					
				//printf("Passed 70%% of the path, preparing for node endpoint check\n");
					if ((fabsf(need2turn(getAngleZ(), nodesr.nextNode.angle)) < 10.0f) || (fabsf(need2turn(nodesr.nowNode.angle, nodesr.nextNode.angle)) < 10.0f) || (nodesr.nowNode.flag & NOTURN) == NOTURN)
					{}//角度差小，保持原速	

					//大角度
					else  {Chassis_SetTargetSpeed(Gyro_Speed);}//25低速转弯速度


					//特殊速度选择
					if(nodesr.lastNode.nodenum == C7 && nodesr.nowNode.nodenum == N14 && nodesr.nextNode.nodenum == C3)   
					{Chassis_SetTargetSpeed(SPEED1);}	
					
					is_near_end = 1;
			}

		
	}
	/*路径终点处理*/
	else if(is_near_end == 1)
	{ 		
		//打印：接近路径终点，执行到达检查
			//printf("Approaching path endpoint, executing arrival check\n");
				//关闭巡线，进入坐标计算
			// 执行当前节点功能，如爬坡、过桥等,执行完后nodesr.flag|0x40（跳过到达检查）
			map_function(nodesr.nowNode.function);
			
			/*如果还没到达*/
			if((nodesr.flag&0x04)!=0x04 && (nodesr.flag&0x80)!=0x80 && (nodesr.flag&0x20)!=0x20)
			{
				/*发送通知给任务判断是否到达路径点*/
					//TODO: 这里可以优化为直接调用函数而不是通知任务，减少延迟
					xTaskNotifyGive(xHandle_ArriveDetect);
				
					// 阻塞自己等待任务完成信号
					ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
					
					// 回家上坡前减速
					if(nodesr.nowNode.nodenum == N2 && nodesr.nextNode.nodenum == P2)
					{Chassis_SetTargetSpeed(nodesr.nowNode.speed*0.9f);}
			}	
			is_near_end = 0; 
			route_state = 0; 
			
	}			
	/*坐标计算处理,转弯完成切换节点 - 路径点时执行*/
	if((nodesr.flag&0x04)==0x04)
	{
		nodesr.flag&=~0x04;//	清除路径点标志，确保该处理只执行一次

		// DEBUG: 打印route相关值
		//printf("[DEBUG] map.point=%d, route[point-1]=0x%02X, route[point]=0x%02X, nowNode=%d, nextNode=%d\n",
		//	map.point, route[map.point-1], route[map.point], nodesr.nowNode.nodenum, nodesr.nextNode.nodenum);                           
		//节点刷新衔接处理
		if(route[map.point-1] != 0xFF)// route[map.point-1]=>nodesr.nextNode	/*判断路径终点 - 0xFF表示路径结束，只有执行完路径终点时才执行该处理*/
		{ 

			// 无需转弯，直接进入下节点
			if ((fabsf(need2turn(getAngleZ(),nodesr.nextNode.angle))<10.0f) ||//当前角度与目标角度差小于10度
				(fabsf(need2turn(nodesr.nowNode.angle,nodesr.nextNode.angle))<10.0f)//角度差小于10度 
				||(nodesr.nowNode.flag&NOTURN)==NOTURN//当前节点标志位无需转弯
				||(nodesr.nowNode.nodenum==S1)//当前为特殊节点S1S2
				||(nodesr.nowNode.nodenum==S2)
				||(route[map.point-3]==S3)//前3个节点为特殊节点（S3、S4、S5等）
				||(route[map.point-3]==S4)
				||(route[map.point-3]==S5)
				||(isStage == 1))
			{		
				Handle_NoTurn_StraightPath();
			}
			
			/*需要转弯处理 - 根据节点标志位选择不同转弯方式*/
			else
			{	
				//左巡线加强kp的转弯，适用于小角度
				if(nodesr.nowNode.flag&L_follow)			
				{
						Chassis_Turn_By_LeftLine_Blocking(nodesr.nextNode.angle, nodesr.nowNode.angle ,0.75f * nodesr.nowNode.speed); // 转弯后继续左巡线，过弯后可能会有一段偏差，继续左巡线可以更快回正
						
				}
				//右巡线加强kp的转弯，适用于小角度
				else if(nodesr.nowNode.flag&R_follow)			
				{
						Chassis_Turn_By_RightLine_Blocking(nodesr.nextNode.angle, nodesr.nowNode.angle, 0.75f * nodesr.nowNode.speed);
						
				}
				/*原点转 停车转弯- 适用于大角度转弯*/	
				else if((nodesr.nowNode.flag&STOPTURN) || (fabsf(need2turn(nodesr.nowNode.angle,nodesr.nextNode.angle))>90.0f))
				{
						
						// 前进一段距离，确保在节点处转弯
						float forwardDist =GetForwardDistanceBeforeTurn(nodesr.lastNode.nodenum, nodesr.nowNode.nodenum, nodesr.nextNode.nodenum);	
						Chassis_DriveDistance_Blocking(is_Gyro, forwardDist, Stop_T_Speed, getAngleZ(), 0); 	

						CarBrake(); // 急刹，确保转弯时车完全停稳
						
						if(nodesr.lastNode.nodenum == B3 && nodesr.nowNode.nodenum == N2 && nodesr.nextNode.nodenum == P2)
						{
							Chassis_OverrideTurnPid(2.0f, 0.0f, 20.0f, 9.0f);
						}
						else
						{
							Chassis_OverrideTurnPid(6.5f, 0.0f, 70.0f, 20.0f);
						}


						Chassis_Turn_By_StopGyro_Blocking(nodesr.nextNode.angle,  getAngleZ()); // 转到目标角度后可能有一段偏差，继续陀螺转可以更快回正

						Chassis_RestoreTurnPid();
					}
				/*陀螺仪不停车转弯- 适用于中小角度转弯*/
				else
				{
						
						float forwardDist = GetForwardDistanceBeforeGyroTurn(nodesr.lastNode.nodenum, nodesr.nowNode.nodenum, nodesr.nextNode.nodenum);
						
						Chassis_DriveDistance_Blocking(is_Gyro, forwardDist, Gyro_Speed, getAngleZ(), 0); // 前进一段距离，确保在节点处转弯	

						Chassis_Turn_By_Gyro_Blocking(nodesr.nextNode.angle, getAngleZ());

					}
				
			}

			/*转弯完成切换巡线模式，进入下节点，清除相关值*/
				isStage = 0;
				buzzer_off();  // 关闭蜂鸣器
							
				// 切换节点关系
				nodesr.lastNode = nodesr.nowNode;
				nodesr.nowNode = nodesr.nextNode;
				// DEBUG: 打印即将读取的route值
				//printf("[DEBUG] switching node, reading route[%d]=0x%02X\n", map.point, route[map.point]);
				nodesr.nextNode = Node[getNextConnectNode(nodesr.nowNode.nodenum, route[map.point++])];
			
				nodesr.flag&=~0x04;  // 清除路径点标志
			}
		else if(route[map.point-1] == 0xFF)// route[map.point-1]=>nodesr.nextNode
		{	
			// 停止小车并设置相关状态
			//printf("Reached final destination, stopping chassis\n");
			CarBrake();//TODO
			//Chassis_Brake();  // 急刹
			vTaskDelay(2);
			map.routetime += 1;  // 地图运行次数+1	
		}
	}	
	
	/*看到红灯*/
	if(nodesr.flag&0x20)
	{
		 // 获取新的下一个节点（带0xFF保护，防止空读越界）
		if (route[map.point] != 0xFF) {
			nodesr.nextNode = Node[getNextConnectNode(nodesr.nowNode.nodenum, route[map.point])];
		}
		map.point++;
		nodesr.flag&=~0x20;  // 清除旋转平台标志
	}

	/*看到非红灯*/
	if(nodesr.flag&0x80)  // 检测到标志
	{		
		// 获取新的下一个节点（带0xFF保护，防止空读越界）
		if (route[map.point] != 0xFF){
			nodesr.nextNode = Node[getNextConnectNode(nodesr.nowNode.nodenum, route[map.point])];
		}
			//疑问：为什么这里不更新lastNode和nowNode？（原来是Door内部更新）
		map.point++ ;
		nodesr.flag&=~0x80;  // 清除标志
	}
}


/*功能选择*/
void map_function(u8 fun)
{
	switch(fun)
	{
		case 0:break;
		case 1:break;							                            //寻找
		case UpStage    : Stage();			   					break;			//平台
		case Bridge   	: Barrier_Bridge();					break;			//过桥
		case Hill	    : Barrier_Hill();					break;			//山地
		case SM         : Sword_Mountain();					break;			//假山
		case View	    : view();		    				break;			//观望 旋转
		case View1      : view1();		   				break;			//观望 直行
		case BACK       : back();		   			    break; 
		case BSoutPole	: South_Pole();	          		break;			//南极
		case QQB	    : QQB_1();	          		break;			//跷跷板
		case BLBS       : Barrier_WavedPlate(87);	    		break;			//蓝波动板 速度：调试 80//85
		case BLBL	    : Barrier_WavedPlate(160);	  		break;			//红波动板 速度：调试	//180
		case DOOR	    : door();		                   	break;			//开门
		case BHM        : Barrier_HighMountain(Mount_Speed);		break;    //高山
		//case IGNORE       :ignore_node(); 	break;   	          //忽略该节点
		case UNDER      : undermou();	                 	break;
		//case Special_node :Special_Node();	break;
		case UpStageP2	: Stage_P2();	                	break;
		default:				                        break;		
	}
}