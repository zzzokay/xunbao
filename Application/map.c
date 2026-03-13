#include "map.h"
#include "barrier.h"
#include "sys.h"
#include "usart.h"
#include "QR.h"
#include "delay.h"
#include "scaner.h"
#include "imu.h"
#include "turn.h"
#include "speed_ctrl.h"
#include "motor_task.h"
#include "bsp_linefollower.h"
#include "math.h"
#include "bsp_buzzer.h"
#include "motor_task.h"
#include "encoder.h"
#include "uart.h"
#include "openmv.h"
#include "motor.h"
#include "scaner.h"
#include "task_create.h"

/******************  记录地图状态和小车状态的全局变量  *************************/
                                           
struct Map_State map = {0,0};   //point //routine                               
NODESR nodesr;  	//包含flag运作中间变量
								/*	flag 0位：1编码器清零请求，0清零完毕
									flag 1位：启动路口判断
									flag 2位：是否到达路口
									flag 3位：arrive里temp清零
									flag 4位：Z轴置零
									flag 5位：路线处理复位 打到门
									flag 6位：没有门
									flag 7位：红灯*/
					// 以及lastnode nownode nextnode 三个结构体，每个结构体包含以下内容：
								/* u8 nodenum;     //结点名称
									 u32  flag;	     //结点标志位
									 float angle;	   //角度	
									 u16	step;		   //线长
									 float speed;	   //寻线速度
									 u8 function;    //结点函数 */   
											
						
/******************************************************************************/


/******************************  标志位  ***************************************/

uint8_t Turn_Flag = 0;//转弯
uint8_t Change_Route = 0;//改变路线
uint8_t mul2sing = 0, sing2mul = 0;//（路口判断）
uint8_t ErrorTimes[2] = {0};	//游龙判定计数位

/******************************************************************************/


uint8_t isAllRoute = 1;    /*是否全程（手动设置）*/
u8 route[100] = {B1, N1, P1, N1, B2, N4, N5, N6, P4, N6, N5, N12, 0XFF};  //启动时的初始路线
/*测试*/
//uint8_t isAllRoute = 0;
//u8 route[100] = {N4,B2,N1,P1,0XFF};
//u8 route[100] = {B3,N2,P2,0XFF};

//uint8_t isAllRoute = 1;
//u8 route[100] = {B1, N1, P1, N1, B2, N4, N5, N12 ,0XFF};
 
 
/***************珠峰***************/
//u8 route[100] = {P7,N20,0XFF};
//u8 route[100] = {B6,N20,P7,N20,C4,C8,C7,N14,C3,N9,B9,N7,P5,N7,B8,N9,N10,0XFF};//长测试
/***************刀山***************/
//u8 route[100] = {B6,N20,0XFF};

/***************跷跷板***************/
//u8 route[100] = {B9,N7,P5,N7,B8,N9,C3,N14,0XFF};
/***************转弯楼梯***************/
// u8 route[100] = {N12,N16,N18,B5,N19,C6,B7,N22,B6,N20,P7,N20,0XFF};
 
 /**************转弯楼梯反方向*********/
// u8 route[100] = {N22,B7,C6,N19,B5,N18,N16,N12,N13,0XFF};

/************************************************************    *地图路线*    **********************************************************************************************************************************************88 */
/*D2、D3红，衔接去看D4*/
u8 door1route[100] = {N4, N3, N8, 0XFF};
/*D2红 D3绿*/
u8 door2route[100] = {N12, N13, P6, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8,0xFF};
/*D2绿*/
u8 door3_1route[50] = {N13, P6, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8,0xFF};
	
/*D2红 D3红 D4绿*/
u8 door4route[100] = {N12, N13, P6, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8, C9, N22, B6, N20, P7, N20, C4, C8, C7, N14, C3, N9, B9, N7, P5, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N8, N3, N4, B3, N2, P2, 0XFF};
/*D2红 D3黄，衔接去看D5*/
u8 door5route[100] = {N12, N13, P6, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8, C9, N22, B6, N20, P7, N20, C4, C8, C7, N14, C3, N9, B9, N7, P5, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, 0XFF};
/*D5绿*/
u8 door6route[100] = {N4, B3, N2, P2, 0XFF};
/*D2红 D3黄 D5红*/
u8 door7route[100] = {N8, N3, N4, B3, N2, P2, 0xFF};
/*D2黄 D5红 D4绿*/
u8 door8route[100] = {N4, B3, N2, P2, 0XFF};
/*D2红 D3红 D4黄 D5必绿*/
u8 door9route[100] = {N12, N13, P6, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8, C9, N22, B6, N20, P7, N20, C4, C8, C7, N14, C3, N9, B9, N7, P5, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, N4, B3, N2, P2, 0XFF}; // 没去P3
/*D2红 D3黄，衔接去看D5*/
u8 door10route[100] = {N12, N13, P6, N13, N12, N16, N18, B5, N19, C6, B7, N22, C9, P8, C9, N22, B6, N20, P7, N20, C4, C8, C7, N14, C3, N9, B9, N7, P5, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, 0XFF}; // N3截至，没回家，没P3
/*D2黄 D5红 D4红*/
u8 door11route[100] = {N5, N4,B3, N2, P2, 0XFF};
/*D2黄*/
u8 door12route[100] = {N13, P6, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P8, C9, N22, B6, N20, P7, N20, C4, C8, C7, N14, C3, N9, B9, N7, P5, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, 0XFF};

	
/*平台5和平台7*/
u8 rout_57[50] = {N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P8,C9, 0XFF};
/*平台5和平台8*/
u8 rout_58[50] = {N13,P6,N13,N12,N16,N18,B5,N19,C6,B7,N22,B6,N20,P7,N20,0XFF};
/*平台6和平台8*/
u8 rout_68[50] = {N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,P7,N20, 0XFF};
/*平台6和平台7*/
u8 rout_67[50] = {N9,B9,N7,P5,N7,B8,N9,C3,N14,C7,C8,C4,N20,B6,N22,C9,P8,C9, 0XFF};

/*******************************************************************************************************************************************************************************************************************************************************/

 
/*地图初始化*/
void mapInit()
{
	map.routetime = 0;
	map.point = 0;
	nodesr.flag = 0;
	// /***************测试***************/
	
//	 nodesr.lastNode.nodenum = N10;
//	 nodesr.nextNode.nodenum = B9;
//   nodesr.nowNode = Node[getNextConnectNode(N10, N9)];//跷跷板
	
//	 nodesr.lastNode.nodenum = C9;
//	 nodesr.nextNode.nodenum = B6;	
//	 nodesr.nowNode = Node[getNextConnectNode(C9, N22)];//长珠峰
	
	
	//nodesr.lastNode = Node[getNextConnectNode(N6, P4)];
//	nodesr.nowNode = Node[getNextConnectNode(N5, N4)];
	
	
//	nodesr.nowNode = Node[getNextConnectNode(C4, N20)];//珠峰
	//nodesr.nowNode = Node[getNextConnectNode( B7, N22)];//刀山
//	 nodesr.nowNode = Node[getNextConnectNode(N10, N9)];//跷跷板
//	nodesr.nowNode = Node[getNextConnectNode(P8, C9)];//转弯楼梯反方向	
	/***************出家***************/
	nodesr.nowNode.nodenum = N2;        //起始(目标)   		//N2
	nodesr.nowNode.angle = 0;           //起始角度   	//0
	nodesr.nowNode.function = NONE;        //起始函数   	//1
	nodesr.nowNode.speed = SPEED1;
	nodesr.nowNode.step= 10;            //长度
	nodesr.nowNode.flag = CLEFT|RIGHT_LINE;
	nodesr.nextNode = Node[getNextConnectNode(nodesr.nowNode.nodenum, route[map.point++])];
}

/*第二次出发初始化*/
void mapInit1(void)
{
	map.point = 0;
	nodesr.flag = 0;
	nodesr.nowNode.nodenum = N2;				//起始点   		
	nodesr.nowNode.angle = 0;					  //起始角度   	
	nodesr.nowNode.function = NONE;				//起始函数   	
	nodesr.nowNode.speed = SPEED0;				
	nodesr.nowNode.step= 2;					                   
	nodesr.nowNode.flag = CLEFT|RIGHT_LINE;		
}
	
/*
 * 获取从当前节点到目标节点的连接关系在Node数组中的索引
 * 
 * 参数说明：
 * - nownode：当前目标节点编号
 * - nextnode：下一个目标节点编号
 * 工作原理：
 * 1. 从Address数组获取当前节点连接关系的起始索引
 * 2. 从ConnectionNum数组获取当前节点的相邻节点数量
 * 3. 遍历找到并返回其索引
 */
u8 getNextConnectNode(u8 nownode,u8 nextnode) 
{
	unsigned char rest = ConnectionNum[nownode];	//这个结点相邻的结点数
	unsigned char addr = Address[nownode];			//得到结点的addr
	int i = 0;
	for (i = 0; i < rest; i++) 
	{
		if(Node[addr].nodenum == nextnode)			//返回结点地址	
			return addr;
		addr++;
	}
	return 0;
}

	/**-------------------------------------------------Cross函数 - 机器人导航核心函数---------------------------------------------------------------------------------------------------------------------------
 * 
 * 
 * 功能：
 * - 控制机器人按照route数组定义的路线行驶
 * - 处理节点间的循迹、转弯、速度控制等逻辑
 * - 执行节点的特殊功能（如爬坡、过桥、打门等）
 * - 管理跑图状态，支持多次跑图
 * 
 * 工作流程：
 * 1. 初始化路线（map.point == 0时）
 * 2. 节点前段循迹处理（Near2end == 0）
 * 3. 节点后端处理（Near2end == 1）
 * 4. 路口处理与节点更新
 * 5. 处理特殊情况

 * 注意：
 * route里面存的是节点名，Node存的才是结构体，给nextnode赋值要用到查找下标函数getNextConnectNode（）
 * 每次路程都指的是节点之间的路程（不是全程）
 * 路口：每段路程终点
 * nodesr.nowNode是小车这一小段路程的终点，小车始终在nowNode和lastNode之间。
 * 当小车碰到nowNode时，nowNode变为lastnode，nextnode变为nowNode。
 * 前70%的主要任务都是通过全局变量控制电机任务循迹
 * 走过70%后唤醒节点检查任务，检查任务将路口标志位置1，回到Cross函数继续执行
 * 区分nodesr.flag和nodesr.nowNode.flag
 * nodesr.flag：记录小车当前状态
 * nodesr.nowNode.flag：地图事先写好的标志，用于指导小车行为

 * 关键状态变量：
 * - map.point：路线数组的当前索引
 * - map.routetime：跑图次数
 * - nodesr：包含当前、上一个和下一个节点信息
 */
void Cross(void)
{
	static uint8_t half_times = 0;		   //是否完成半程
	static uint8_t Near2end = 0;		  //是否靠近结尾跑完70%   （现在0代表没跑完70%）
	static uint8_t select_PID_Para = 0;//是否选择了PID参数

	/*位于起点处理 - 路线开始时的初始化*/
	 /***************执行测试路线（调试时使用）******************/
	if(map.point == 0)
	{  		 	
		if (isAllRoute == 0) 
			motor_all.Cspeed = nodesr.nowNode.speed; //测试路线时，速度为设置速度	
	}
 	/**********************************************************/
	
	
	/*节点前段循迹处理 - 主要是循迹行驶逻辑*/
	if(Near2end == 0)
	{
		//特殊结点设置速率（长直线，前进四！）
		if ((nodesr.lastNode.nodenum == N4 && nodesr.nowNode.nodenum == N5 && nodesr.nextNode.nodenum == N6) ||
			(nodesr.lastNode.nodenum == N5 && nodesr.nowNode.nodenum == N6 && nodesr.nextNode.nodenum == P4) ||
			(nodesr.lastNode.nodenum == N5 && nodesr.nowNode.nodenum == N4 && nodesr.nextNode.nodenum == N3) ||
			(nodesr.lastNode.nodenum == P3 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == N4))
			{	
				nodesr.nowNode.speed = SPEED4;
				motor_all.Cspeed = nodesr.nowNode.speed;
			}
		 /*根据速度给不同的PID参数*/	 
		 if(select_PID_Para == 0)
		 {
		 		select_speed(); 
		 		select_PID_Para =1;
		 }
		//循迹
		pid_mode_switch(is_Line);
		 		
		 /*前段路程处理 - 还没走完50%路程*/ 
					
		    if(fabsf(motor_all.Distance) < 0.5f*nodesr.nowNode.step && half_times == 0)
			{	
				//如果角度变化并排除特殊情况	
				if (nodesr.nowNode.angle != nodesr.lastNode.angle && nodesr.nowNode.nodenum != C4 && nodesr.nowNode.nodenum != P8)   //如果角度变化并排除特殊情况
				{			
					Cross_getline();       //获取循迹传感器状态，该函数会填充 Cross_Scaner 结构体
					
					if(ErrorTimes[1]==0)        
					{
						motor_all.Cspeed = nodesr.nowNode.speed / 1.5f;  //一开始先让速度变小一点
						if(Cross_Scaner.detail & 0xFC3F) //如果偏移过大
						{
							ErrorTimes[0]++; //标记，用于更改PID参数
						}
						else //车身回正后加5马上使ErrorTimes[0] >= 10恢复原速度
						{
							ErrorTimes[0]+=5;
						}
						if(ErrorTimes[0] >= 10)
						{
							ErrorTimes[0] = 0;
							ErrorTimes[1] = 1;
							motor_all.Cspeed = nodesr.nowNode.speed;
						}
					}
					if(ErrorTimes[0])//如果游龙，通过修改 PID 参数来快速抑制抖动、稳定车身
					{
						line_pid_param.kp = 12;
						line_pid_param.ki = 0;
						line_pid_param.kd = 200;//200
					}												
			  }
			}			
			        
			/*走过50%路程，点间循迹模式切换*/
			if(fabsf(motor_all.Distance) >= 0.5f*nodesr.nowNode.step && half_times == 0)
			{
						if((nodesr.nowNode.flag & Temp_L) == Temp_L)
						{
							LEFT_RIGHT_LINE = 1;
						}
						else if((nodesr.nowNode.flag & Temp_R) == Temp_R)
						{
							LEFT_RIGHT_LINE = 2;
						}
						else if((nodesr.nowNode.flag & Temp_LiuShui) == Temp_LiuShui)
						{
							LEFT_RIGHT_LINE = 3;
						}
						half_times = 1;
			}
			/*节点间后段处理 - 走完70%路程*/
			else if(fabsf(motor_all.Distance) >= 0.7f*nodesr.nowNode.step )
			{
						Near2end = 1;

						if ((fabs(need2turn(getAngleZ(), nodesr.nextNode.angle)) < 10) || (fabs(need2turn(nodesr.nowNode.angle, nodesr.nextNode.angle)) < 10) || (nodesr.nowNode.flag & NOTURN) == NOTURN)
							motor_all.Cspeed = nodesr.nowNode.speed;	//如果角度较小不用减速
						else   //减速
						{
							/*返回低速PID参数*/
							line_pid_param.kp = 12;
							line_pid_param.ki = 0;
							line_pid_param.kd = 400;
							motor_all.Cspeed = Gyro_Speed;//25
						}
						
						if(nodesr.lastNode.nodenum == C7 && nodesr.nowNode.nodenum == N14 && nodesr.nextNode.nodenum == C3)   //特殊结点速度选择
							motor_all.Cspeed = SPEED1;
						
						/*归零游龙保护和速度选择*/
						ErrorTimes[0] = ErrorTimes[1] = 0;
						select_PID_Para = 0;
			}

			
	}
	/*路线结尾处理*/
	else if(Near2end == 1)
	{			// 执行当前节点功能（如爬坡、过桥、打门等）,执行完会给nodesr.flag|0x40
				map_function(nodesr.nowNode.function);
				
				/*判断路口 - 还没到路口且不是全白也不是多条变一条*/
				if((nodesr.flag&0x04)!=0x04 && (nodesr.flag&0x80)!=0x80 && (nodesr.flag&0x20)!=0x20)
				{
					/*唤醒到达检测任务，确认是否到达路口*/
				   xTaskNotifyGive(xHandle_ArriveDetect);
				
					// 阻塞自己，等待任务完成后唤醒
					ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
					
					// 回家上坡前减速
					if(nodesr.nowNode.nodenum == N2 && nodesr.nextNode.nodenum == P2)
						Motor_Control(is_Line,nodesr.nowNode.speed*0.9f,nodesr.nowNode.speed*0.9f,0);
				}		
	}
				
	/*车辆位置校准,转弯处理与节点更新 - 当到达路口时执行*/
	if((nodesr.flag&0x04)==0x04)
	{
		nodesr.flag&=~0x04;//	清除到达路口标志，确保这段逻辑只执行一次

		/*不是路线末端 - 0xFF表示路线结束，只有不是路线末端时才执行后续逻辑*/
		if(route[map.point-1] != 0xFF)// route[map.point-1]=>nodesr.nextNode
		{ 
			// 不需要转弯的情况，直接更新节点
			if ((fabs(need2turn(getAngleZ(),nodesr.nextNode.angle))<10) ||//当前角度与目标角度差小于10°
				(fabs(need2turn(nodesr.nowNode.angle,nodesr.nextNode.angle))<10)//角度差小于10° 
				||(nodesr.nowNode.flag&NOTURN)==NOTURN//当前节点标志位不需要转
				||(nodesr.nowNode.nodenum==S1)//当前特殊节点S1S2
				||(nodesr.nowNode.nodenum==S2)
				||(route[map.point-3]==S3)//前3个节点是特殊节点（S3、S4、S5）
				||(route[map.point-3]==S4)
				||(route[map.point-3]==S5)
				||(isStage == 1))
			{		
			
				if ((nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == P3) ||
					(nodesr.nowNode.nodenum == N4 && nodesr.nextNode.nodenum == N3) ||
					(nodesr.nowNode.nodenum == N4 && nodesr.nextNode.nodenum == N5))
				{
					// 使用陀螺仪模式行驶一段距离
					Motor_Control(is_Gyro, nodesr.nextNode.speed, nodesr.nextNode.speed, getAngleZ());
					Want2Go(20);  // 前进20个单位距离
					// 切回循迹模式继续行驶
					Motor_Control(is_Line, nodesr.nextNode.speed, nodesr.nextNode.speed, 0);
				}
				else if (nodesr.nowNode.nodenum == N13 && nodesr.nextNode.nodenum == P6) 
				{
					scaner_set.EdgeIgnore = 6;//忽略6个边缘
					Want2Go(20);//前进20个单位距离/
					scaner_set.EdgeIgnore = 0;
				}
				else if (nodesr.nowNode.nodenum == N1 && nodesr.nextNode.nodenum == P1)
				{
					scaner_set.EdgeIgnore = 6;//忽略6个边缘
					Want2Go(20);//20
					scaner_set.EdgeIgnore = 0;
				}
				else if ((nodesr.lastNode.nodenum == P3 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == N4)||
					 (nodesr.lastNode.nodenum == P4 && nodesr.nowNode.nodenum == N6 && nodesr.nextNode.nodenum == N5))
				{
					scaner_set.EdgeIgnore = 7;
					Want2Go(20);
					scaner_set.EdgeIgnore = 0;
				}
				else if ((nodesr.nowNode.nodenum == N13 && nodesr.nextNode.nodenum == N12)||(nodesr.nowNode.nodenum == N12 && nodesr.nextNode.nodenum == N13))
				{
					scaner_set.EdgeIgnore = 7;
					Want2Go(20);
					scaner_set.EdgeIgnore = 0;
				}
				else if ((nodesr.nowNode.nodenum == P6 && nodesr.nextNode.nodenum == N13)||(nodesr.nowNode.nodenum == N13 && nodesr.nextNode.nodenum == P6))
				{
					scaner_set.EdgeIgnore = 7;
					Want2Go(25);
					scaner_set.EdgeIgnore = 0;
				}
				else
				{
					scaner_set.EdgeIgnore = 7;
					Want2Go(10);
					scaner_set.EdgeIgnore = 0;
				}
			}
			
			/*需要转弯的情况 - 根据节点标志位选择不同转弯方式*/
			else
			{	
				//左循迹加大kp的转弯，适用于小角度
				if(nodesr.nowNode.flag&L_follow)			
				{
					float original_line_pid = line_pid_param.kp;
					float max = line_pid_param.outputMax;
					line_pid_param.kp = 70;   //大幅增大比例系数，提高对偏差的响应速度
					line_pid_param.ki = 0;
					line_pid_param.kd = 5;
					line_pid_param.outputMax = 0.75f*motor_all.Cspeed;//差速不能太大
					nodesr.nowNode.flag|=LEFT_LINE;//作用 ：在循迹过程中，从左侧开始循迹，忽略右侧白线干扰
					angle.AngleG = nodesr.nextNode.angle;
					while(fabs(need2turn(angle.AngleG,getAngleZ()))>4)
					{
						vTaskDelay(2);
						getline_error();
						if(Scaner.lineNum==1&&((Scaner.detail&0x3C0)!=0)&&(fabsf(need2turn(angle.AngleG,getAngleZ())) < fabsf(need2turn(angle.AngleG,nodesr.nowNode.angle))*0.25f))
							break;
					}
					nodesr.nowNode.flag&=(~LEFT_LINE);		//取消左循迹标志位
					line_pid_param.kp = original_line_pid;  //恢复正常
					line_pid_param.outputMax =  max;
				}
				//右循迹加大kp的转弯，适用于小角度
				else if(nodesr.nowNode.flag&R_follow)		
				{
					float original_line_pid = line_pid_param.kp;
					float max = line_pid_param.outputMax;
					float num=motor_all.Distance;
					line_pid_param.kp = 70;
					line_pid_param.ki = 0;
					line_pid_param.kd = 5;
					line_pid_param.outputMax = 0.75f*motor_all.Cspeed;
					nodesr.nowNode.flag|=RIGHT_LINE;
					angle.AngleG = nodesr.nextNode.angle;
					while(fabs(need2turn(angle.AngleG,getAngleZ()))>4)
					{
						vTaskDelay(2);
						getline_error();
						if(Scaner.lineNum==1&&((Scaner.detail&0x3C0)!=0)&&(fabsf(need2turn(angle.AngleG,getAngleZ()))<fabs(need2turn(angle.AngleG,nodesr.nowNode.angle))*0.25f))
						{  
							break;
						}
					}
					nodesr.nowNode.flag&=(~RIGHT_LINE);		//取消右循迹标志位
					line_pid_param.kp = original_line_pid;  //恢复正常
					line_pid_param.outputMax =  max;
				}
				/*原地转 （左右轮反向）- 当需要大角度转弯*/	
				else if((nodesr.nowNode.flag&STOPTURN) || (fabsf(need2turn(nodesr.nowNode.angle,nodesr.nextNode.angle))>90))
				{
						
						// 原地转需要先往前走一段，保证车在节点上再转
						motor_all.Gspeed = Stop_T_Speed;
						angle.AngleG = getAngleZ();
						pid_mode_switch(is_Gyro);//切换到陀螺仪模式
						if (nodesr.lastNode.nodenum == P8 && nodesr.nowNode.nodenum == C9 && nodesr.nextNode.nodenum == N22)
							Want2Go(28);
						else if (nodesr.lastNode.nodenum == S1 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == P3)
							Want2Go(15);
						else if (nodesr.lastNode.nodenum == C8 && nodesr.nowNode.nodenum == C7 && nodesr.nextNode.nodenum == N14)
							Want2Go(20);
						else if (nodesr.lastNode.nodenum == C9 && nodesr.nowNode.nodenum == N22 && nodesr.nextNode.nodenum == B6)
							Want2Go(20);
						else if (nodesr.lastNode.nodenum == B3 && nodesr.nowNode.nodenum == N2 && nodesr.nextNode.nodenum == P2)
							Want2Go(30);
						else if (nodesr.lastNode.nodenum == B9 && nodesr.nowNode.nodenum == N7 && nodesr.nextNode.nodenum == P5)
							Want2Go(18);
						else if (nodesr.lastNode.nodenum == P5 && nodesr.nowNode.nodenum == N7 && nodesr.nextNode.nodenum == B8)
							Want2Go(25);
						else if (nodesr.lastNode.nodenum == P7 && nodesr.nowNode.nodenum == N20 && nodesr.nextNode.nodenum == C4)
							Want2Go(30);
						else if (nodesr.lastNode.nodenum == N8 && nodesr.nowNode.nodenum == N5 && nodesr.nextNode.nodenum == N4)
							Want2Go(30);
						else if (nodesr.lastNode.nodenum == N8 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == P3)
							Want2Go(15);
						else if (nodesr.lastNode.nodenum == N8 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == N4)
							Want2Go(20);
						else if (nodesr.lastNode.nodenum == N9 && nodesr.nowNode.nodenum == N10 && nodesr.nextNode.nodenum == N8)
							Want2Go(26);
						else if (nodesr.lastNode.nodenum == N20 && nodesr.nowNode.nodenum == C4 && nodesr.nextNode.nodenum == C8)
							Want2Go(25);
						else if (nodesr.lastNode.nodenum == C3 && nodesr.nowNode.nodenum == N9 && nodesr.nextNode.nodenum == B9)
							Want2Go(45);
						else if (nodesr.nowNode.nodenum == N20 && nodesr.nextNode.nodenum == P7)
							Want2Go(30);
						else if (nodesr.lastNode.nodenum == N10 &&nodesr.nowNode.nodenum == N9 && nodesr.nextNode.nodenum == B9)
							Want2Go(40);
						else if (nodesr.lastNode.nodenum == B8 &&nodesr.nowNode.nodenum == N9 && nodesr.nextNode.nodenum == N10)
							Want2Go(25);
						else
							Want2Go(20);
						
						CarBrake();//刹车
						vTaskDelay(100);//100ms
						
						struct PID_param origin_param = gyroT_pid_param;
						char oriGmax = motor_all.GyroT_speedMax;

						if(nodesr.lastNode.nodenum == B3 && nodesr.nowNode.nodenum == N2 && nodesr.nextNode.nodenum == P2)
						{
							gyroT_pid_param.kp = 2.0; // 1.8
							gyroT_pid_param.ki = 0;
							gyroT_pid_param.kd = 20.0;
							motor_all.GyroG_speedMax = 9;
						}		
						else
						{
							motor_all.GyroT_speedMax = 20;
							gyroT_pid_param.kp = 6.5f; // 5.0f
							gyroT_pid_param.ki = 0;	   // 0
							gyroT_pid_param.kd = 70;
						}

						angle.AngleT = nodesr.nextNode.angle;
						pid_mode_switch(is_Turn);//这里才开始转弯
						while(fabs(need2turn(angle.AngleT,getAngleZ()))>2)
						{
							vTaskDelay(2);
							Cross_getline();
							if(Cross_Scaner.lineNum==1&&((Cross_Scaner.detail&0x180)!=0)&&(fabs(need2turn(angle.AngleT,getAngleZ()))<fabs(need2turn(angle.AngleT,nodesr.nowNode.angle))*0.15f))
								break;
						}

						motor_all.GyroT_speedMax = oriGmax;
						gyroT_pid_param = origin_param;
				}
				/*陀螺仪差速转弯- 适用于中小角度转弯*/
				else
				{
						/*参数调整*/
						struct PID_param origin_parm=gyroG_pid_param;
						float origin_speedMax = motor_all.GyroG_speedMax;
						
						gyroG_pid_param.kp = 12;//9
						gyroG_pid_param.ki = 0;
						gyroG_pid_param.kd = 180;//140
						if (need2turn(nodesr.nowNode.angle, nodesr.nextNode.angle) > 0) //左转
							motor_all.GyroG_speedMax = 30; //39
						else
							motor_all.GyroG_speedMax = 39;
						
				
						mpuZreset(get_latest_yaw(), nodesr.nowNode.angle);


						/*前进一段距离*/
						Motor_Control(is_Gyro, Gyro_Speed, Gyro_Speed, nodesr.nowNode.angle);

						if ((nodesr.lastNode.nodenum == B2 && nodesr.nowNode.nodenum == N4 && nodesr.nextNode.nodenum == N5) ||
							(nodesr.lastNode.nodenum == B6 && nodesr.nowNode.nodenum == N20 && nodesr.nextNode.nodenum == C4) ||
						    (nodesr.lastNode.nodenum == C4 && nodesr.nowNode.nodenum == N20 && nodesr.nextNode.nodenum == B6) ||
							(nodesr.lastNode.nodenum == B2 && nodesr.nowNode.nodenum == N1 && nodesr.nextNode.nodenum == P1))
							Want2Go(9);
						else if (nodesr.lastNode.nodenum == B3 && nodesr.nowNode.nodenum == N2 && nodesr.nextNode.nodenum == P2)
							Want2Go(15);
						else if (nodesr.lastNode.nodenum == P3 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == N8)
							Want2Go(5);
						else if (nodesr.lastNode.nodenum == P8 && nodesr.nowNode.nodenum == C9 && nodesr.nextNode.nodenum == N22)
							Want2Go(3);
						else if (nodesr.lastNode.nodenum == S1 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == N8)
							Want2Go(8);
						else if (nodesr.lastNode.nodenum == N3 && nodesr.nowNode.nodenum == N4 && nodesr.nextNode.nodenum == B3)
							Want2Go(15);
						else if (nodesr.lastNode.nodenum == N5 && nodesr.nowNode.nodenum == N12 && nodesr.nextNode.nodenum == N13)
							Want2Go(3);
						else if (nodesr.lastNode.nodenum == N5 && nodesr.nowNode.nodenum == N6 && nodesr.nextNode.nodenum == S2)
							Want2Go(12);
						else if (nodesr.lastNode.nodenum == N8 && nodesr.nowNode.nodenum == N12 && nodesr.nextNode.nodenum == N13)
							Want2Go(4);
						else if (nodesr.lastNode.nodenum == N8 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == P3)
							Want2Go(20);
						else if (nodesr.lastNode.nodenum == N8 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == S1)
							Want2Go(30);
						else if (nodesr.lastNode.nodenum == N9 && nodesr.nowNode.nodenum == N10 && nodesr.nextNode.nodenum == N8)
							Want2Go(4);
						else if (nodesr.lastNode.nodenum == N10 && nodesr.nowNode.nodenum == N3 && nodesr.nextNode.nodenum == S1)
							Want2Go(4);
						else if (nodesr.lastNode.nodenum == N15 && nodesr.nowNode.nodenum == N10 && nodesr.nextNode.nodenum == N8)
							Want2Go(5);
						else if (nodesr.lastNode.nodenum == C7 && nodesr.nowNode.nodenum == C8 && nodesr.nextNode.nodenum == C4)
							Want2Go(15);
						
						//计算AngleG的意义：不管当前getAngleZ()能不能和nodesr.nowNode.angle重合，直接转相对角度
						angle.AngleG = getAngleZ() + need2turn(nodesr.nowNode.angle, nodesr.nextNode.angle);
						if(angle.AngleG>180)
							angle.AngleG -= 360;
						else if(angle.AngleG<=-180)
							angle.AngleG += 360;
						while(fabsf(need2turn(getAngleZ(),angle.AngleG)) > 4)
						{
							vTaskDelay(2);
							Cross_getline();
							if(Cross_Scaner.lineNum == 1 && (Cross_Scaner.detail&0x3C0) && (fabs(need2turn(angle.AngleG,getAngleZ()))<fabs(need2turn(angle.AngleG,nodesr.nowNode.angle))*0.1f))
								break;
						}

						gyroG_pid = (struct P_pid_obj){0,0,0,0,0,0,0};
						gyroG_pid_param=origin_parm;
						motor_all.GyroG_speedMax=origin_speedMax;
				}
				
			}

			/*转完后进入循迹模式，更新结点，清空编码器值*/
				// 恢复节点前段处理模式
				Near2end=0;
				isStage = 0;
				motor_all.CDOWNincrement = 0.6;  // 设置速度下降增量
				half_times = 0;  // 重置半程标志
				buzzer_off();  // 关闭蜂鸣器
				
				// 切换回循迹模式，准备下一段行驶
				pid_mode_switch(is_Line);
				
				// 更新节点关系：

				nodesr.lastNode = nodesr.nowNode;
				nodesr.nowNode = nodesr.nextNode;
				motor_all.Cspeed = nodesr.nowNode.speed;  // 设置新的速度
				nodesr.nextNode = Node[getNextConnectNode(nodesr.nowNode.nodenum, route[map.point++])];
				
				// 特定节点组合的特殊设置
				if(nodesr.nowNode.nodenum == N9 && nodesr.nextNode.nodenum == N10)
					scaner_set.CatchsensorNum = line_weight[7];  // 设置线权重
				else
					scaner_set.CatchsensorNum = 0;
				
				// 重置各种标志位和计数器，准备下一段行驶
				scaner_set.EdgeIgnore = 0;
				encoder_clear();  // 清空编码器值
				LEFT_RIGHT_LINE = 0;  // 重置循迹模式
				mul2sing = 0;
				sing2mul = 0;
				nodesr.flag&=~0x04;  // 清除到达路口标志
			}
		else if(route[map.point-1] == 0xFF)// route[map.point-1]=>nodesr.nextNode
		{	
			// 停止小车，重置各种状态
			motor_all.Cspeed = 0;
			motor_all.Gspeed = 0;
			LEFT_RIGHT_LINE = 0;
			CarBrake();  // 刹车
			vTaskDelay(2);
			Near2end=0;  // 重置标志位
			map.routetime += 1;  // 跑图次数加1
		}
	}	
		
	/*看到红灯的处理 - 特殊情况处理*/
	if(nodesr.flag&0x20)
	{		
		scaner_set.CatchsensorNum = 0;  // 重置传感器捕获数量
		Near2end=0;  // 切换回节点前段处理模式
		
		// 更新节点关系，跳过当前红灯节点
		nodesr.lastNode = nodesr.nowNode;
		nodesr.nextNode = Node[getNextConnectNode(nodesr.nowNode.nodenum, route[map.point++])];  // 获取新的下一个节点
		
		nodesr.flag&=~0x20;  // 清除红灯标志
		motor_all.Cspeed = SPEED25;  // 设置新的速度
		pid_mode_switch(is_Line);  // 切换回循迹模式
	}

	/*看到非红灯的处理 - 特殊情况处理*/
	if(nodesr.flag&0x80)  // 如果打到门是开着的
	{
		scaner_set.CatchsensorNum = 0;  // 重置传感器捕获数量
		Near2end=0;  // 切换回节点前段处理模式
		
		// 获取新的下一个节点
		nodesr.nextNode = Node[getNextConnectNode(nodesr.nowNode.nodenum, route[map.point++])];
		
		nodesr.flag&=~0x80;  // 清除非红灯标志
		encoder_clear();  // 清空编码器值
		motor_all.Cspeed = SPEED3;  // 设置新的速度
		pid_mode_switch(is_Line);  // 切换回循迹模式
	}
}

void select_speed(void)
{
	switch ((int)nodesr.nowNode.speed) 
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
/*函数选择*/
void map_function(u8 fun)
{
	switch(fun)
	{
		case 0:break;
		case 1:break;												                            //寻线
		case UpStage    : Stage();					  						break;			//平台
		case Bridge  	: Barrier_Bridge();									break;			//长桥
		case Hill	    : Barrier_Hill();									break;			//楼梯
		case SM         : Sword_Mountain();									break;			//刀山
		case View	    : view();					   						break;			//景点 后转
		case View1      : view1();					  						break;			//景点 直退
		case BACK       : back();					  					    break; 
		case BSoutPole	: South_Pole();			         					break;			//南极
		case QQB	    : QQB_1();					         				break;			//跷跷板
		case BLBS       : Barrier_WavedPlate(87);	   						break;			//短减速板 速度，长度 80//85
		case BLBL	    : Barrier_WavedPlate(160);	 						break;			//长减速板 速度，长度	//180
		case DOOR	    : door();					                  		break;			//打门
		case BHM        : Barrier_HighMountain(Mount_Speed);				break;	    //上珠峰
		//case IGNORE       :ignore_node(); 			break;  		          //忽略该节点
		case UNDER      : undermou();			                			break;
		//case Special_node :Special_Node();			break;
		case UpStageP2	: Stage_P2();				               			break;
		default:									                        break;		
	}
}
