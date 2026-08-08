#include "map.h"
#include "barrier.h"
#include "sys.h"
#include "math.h"
#include "chassis_api.h"
#include "stdio.h"

/* 从 task_create.h 迁入，避免 map.c 越层包含 */
extern TaskHandle_t xHandle_ArriveDetect;

/******************  记录地图状态和小车状态的全局变量  *************************/
                                            
struct Map_State map = {0,0};   //point //routine
Nodes nodes;   	//当前边的三个点
			// 分别lastnode nownode nextnode 三个结构体变量,每个结构体存储对应节点数据
			/* u8 nodenum;     //节点编号
				 u32  flag;     //节点标志位
				 float angle;   //角度	
				 u16	step;       //步长
				 float speed;   //运行速度
				 u8 function;    //节点功能 */


volatile uint8_t cross_event = 0;	//运行时阶段/事件标志，全局变量，供节点检查和导航之间交流
			   
				

/******************************************************************************/



//u8 route[100] = {B1, N1, P1, N1, B2, N4, N5, N6, P4, N6, N5, N12, 0XFF};  //调试时的初始路径
u8 route[100] = {B1, N1,P1, N1, B2, N4, N5,0XFF};  //初始路径


/************************************************************    *地图路径*    **********************************************************************************************************************************************88 */
/*D2关D3关，去D4*/
u8 door1route[100] = {N3, N8, 0XFF};
/*D2开 D3开*/
u8 door2route[100] = {N12, N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P7,0xFF};
/*D2开*/
u8 door3_1route[50] = {N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P7,0xFF};
	
/*D2开 D3开 D4开*/
u8 door4route[100] = {N12, N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P7, C9, N22, B6, N20, P8, N20, C4, C8, C7, N14, C3, N9, B9, N7, P6, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N8, N3, N4, B3, N2, P2, 0XFF};
/*D2开 D3关，暂时去掉D5*/
u8 door5route[100] = {N12, N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P7, C9, N22, B6, N20, P8, N20, C4, C8, C7, N14, C3, N9, B9, N7, P6, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, 0XFF};
/*D5开*/
u8 door6route[100] = {N4, B3, N2, P2, 0XFF};
/*D2开 D3开 D5开*/
u8 door7route[100] = {N8, N3, N4, B3, N2, P2, 0xFF};
/*D2开 D5开 D4开*/
u8 door8route[100] = {N4, B3, N2, P2, 0XFF};
/*D2开 D3开 D4开 D5开全*/
u8 door9route[100] = {N12, N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P7, C9, N22, B6, N20, P8, N20, C4, C8, C7, N14, C3, N9, B9, N7, P6, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, N4, B3, N2, P2, 0XFF}; // 没去P3
/*D2开 D3关，暂时去掉D5*/
u8 door10route[100] = {N12, N13, P5, N13, N12, N16, N18, B5, N19, C6, B7, N22, C9, P7, C9, N22, B6, N20, P8, N20, C4, C8, C7, N14, C3, N9, B9, N7, P6, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, 0XFF}; // N3前没写，没P3
/*D2开 D5开 D4开*/
u8 door11route[100] = {N5, N4,B3, N2, P2, 0XFF};
/*D2开*/
u8 door12route[100] = {N13, P5, N13, N12, N16 /*, S5, N16*/, N18, B5, N19, C6, B7, N22, C9, P7, C9, N22, B6, N20, P8, N20, C4, C8, C7, N14, C3, N9, B9, N7, P6, N7, B8, N9, N10 /*, N15, S4, N15, N10*/, N3, 0XFF};
/*平台5到平台7*/
u8 rout_57[50] = {N13,P5,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9, 0XFF};
/*平台5到平台8*/
u8 rout_58[50] = {N13,P5,N13,N12,N16,N18,B5,N19,C6,B7,N22,B6,N20,P8,N20,0XFF};
/*平台6到平台8*/
u8 rout_68[50] = {N9,B9,N7,P6,N7,B8,N9,C3,N14,C7,C8,C4,N20,P8,N20, 0XFF};
/*平台6到平台7*/
u8 rout_67[50] = {N9,B9,N7,P6,N7,B8,N9,C3,N14,C7,C8,C4,N20,B6,N22,C9,P7,C9, 0XFF};

/*******************************************************************************************************************************************************************************************************************************************************/

 
/*地图初始化*/
void mapInit()
{
	map = (struct Map_State){0,0};
    nodes = (Nodes){0};	
	cross_event = 0;       //起始点
    nodes.nowNode = Node[getNextConnectNode(P2, N2)];  //起始目标点
	nodes.nextNode = Node[getNextConnectNode(nodes.nowNode.nodenum, route[map.point++])];
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
	if (last == S1 && now == N3 && next == P3) return 15.0f;
	if (last == C9 && now == N22 && next == B6) return 20.0f;
	if (last == B3 && now == N2 && next == P2) return 20.0f;
	if (last == B9 && now == N7 && next == P6) return 15.0f;
	if (last == P6 && now == N7 && next == B8) return 15.0f;
	if (last == C4 && now == N20 && next == P8) return 20.0f;
    if (last == N3 && now == N4 && next == B2) return 20.0f;
    if (last == P8 && now == N20 && next == C4) return 25.0f;
	if (last == N8 && now == N5 && next == N4) return 30.0f;
	if (last == N8 && now == N3 && next == P3) return 15.0f;
	if (last == N8 && now == N3 && next == N4) return 20.0f;
	if (last == B8 && now == N9 && next == C3) return 0.0f;
    if (last == N14 && now == C3 && next == N9) return 0.0f;
	if (last == N10 && now == N9 && next == B9) return 40.0f;
	if (last == B8 && now == N9 && next == N10) return 25.0f;
	if (last == N5 && now == N8 && next == N12) return 5.0f;
	return 15.0f;
}

/* 获取对应节点的陀螺仪不停车转弯前的前进距离判断 */
static float GetForwardDistanceBeforeGyroTurn(u8 last, u8 now, u8 next)
{
	if (last == B2 && now == N4 && next == N5)return 7.0f; 
	if (last == B3 && now == N2 && next == P2) return 15.0f;
    if (last == B2 && now == N1 && next == P1) return 15.0f;
	if (last == P3 && now == N3 && next == N8) return 5.0f;

	if (last == N3 && now == N4 && next == B3) return 10.0f;
    if (last == N8 && now == N12 && next == N13) return 0.0f;

	if (last == N8 && now == N3 && next == P3) return 20.0f;
	if (last == N8 && now == N3 && next == S1) return 0.0f;
	if (last == P1 && now == N1 && next == B2)return 0.0f; 
	return 0.0f; // 默认不前进，走原逻辑未修改
}

/* 获取对应节点的特定直线路径加速判断 */
static void Check_And_Apply_SpeedUp(void)
{
	if ((nodes.lastNode.nodenum == N4 && nodes.nowNode.nodenum == N5 && nodes.nextNode.nodenum == N6) ||
		(nodes.lastNode.nodenum == N5 && nodes.nowNode.nodenum == N6 && nodes.nextNode.nodenum == P4) ||
		(nodes.lastNode.nodenum == N5 && nodes.nowNode.nodenum == N4 && nodes.nextNode.nodenum == N3) ||
		(nodes.lastNode.nodenum == P3 && nodes.nowNode.nodenum == N3 && nodes.nextNode.nodenum == N4))
	{	
		nodes.nowNode.speed = SPEED4;
		Chassis_SetTargetSpeed(nodes.nowNode.speed);
	}
}


	/**-------------------------------------------------Navigation函数 - 整个流程的核心---------------------------------------------------------------------------------------------------------------------------
 *
 *
 * 功能：
 * - 解析路径序列 route（点编号数组）并按序执行边动作
 * - 处理每条边的巡线、转弯、速度切换等逻辑
 * - 执行点的特殊功能（如爬坡、过桥等）
 * - 管理图状态和支持多轮竞赛
 *
 * 执行流程（每条边的处理）：
 * 1. 边初始化
 * 2. 边的前半段处理
 * 3. 边的后半段处理
 * 4. 到达目标点后的切换处理
 * 5. 点的特殊功能处理

 * 注意：
 * route 数组存储的是点的编号，Node 数组是点结构体数组，取邻接点要用下标函数 getNextConnectNode
 * 每条边都连接两个点
 * nodes.nowNode 是当前边的终点（目标点），lastNode 是起点，nextNode 是下一条边的终点
 * 到达 nowNode 时：小车滑动，nowNode → lastNode，nextNode → nowNode
 * 边的前 70% 进行巡线
 * 超过 70% 时触发终点检查
 * 需要区分 nodes.nowNode.flag 和 nodes.nowNode.function
 * nodes.nowNode.flag 是地图文件写入的边属性标志（巡线边、转弯方向等）
 * nodes.nowNode.function 是点特殊功能（爬坡、过桥等）

 * 关键状态变量：
 * - map.point：route 数组的当前索引（当前目标点在序列中的位置）
 * - map.routetime：图遍历轮次
 * - nodes：当前边的三个节点（lastNode/nowNode/nextNode）
 */
enum {                     // nav_step 取值，NAV 是 Navigation（导航）的缩写。
    NAV_STEP_INIT,         // 0  段初始化（清里程、设模式）
    NAV_STEP_MID_SWITCH,   // 1  过半切换巡线模式
    NAV_STEP_PREP_ARRIVE   // 2  70% 降速准备到达
};

/* ============================ Navigation() 子函数 =================================== */

static void Nav_SegmentInit(void)
{
    //路程初始化
    Chassis_ClearMileage();
    //循迹中心
    Chassis_SetCatchSensorNum(0);
    //设置忽略边缘
    Chassis_SetEdgeIgnore(0);

    // 根据当前边的 flag 设置循迹模式
    if ((nodes.nowNode.flag & LEFT_LINE) == LEFT_LINE)
        Chassis_SetTrackMode(TRACK_LEFT_EDGE);
    else if ((nodes.nowNode.flag & RIGHT_LINE) == RIGHT_LINE)
        Chassis_SetTrackMode(TRACK_RIGHT_EDGE);
    else if ((nodes.nowNode.flag & NEAR_CENTER) == NEAR_CENTER)
        Chassis_SetTrackMode(TRACK_NEAR_CENTER);
    else
        Chassis_SetTrackMode(TRACK_ALL);
    // 设置当前边的模式和目标速度
    Chassis_SetMode(is_Line);
    Chassis_SetTargetSpeed(nodes.nowNode.speed);
    //根据地图硬编码
    Check_And_Apply_SpeedUp();
    Chassis_EnableAntiSnake();//游龙保护
    Chassis_EnableWheelieProtection();//翘头保护
}

static void Nav_MidSwitch(void)
{
    if ((nodes.nowNode.flag & Temp_L) == Temp_L)
        Chassis_SetTrackMode(TRACK_LEFT_EDGE);
    else if ((nodes.nowNode.flag & Temp_R) == Temp_R)
        Chassis_SetTrackMode(TRACK_RIGHT_EDGE);
    else if ((nodes.nowNode.flag & TEMP_NEAR_CENTER) == TEMP_NEAR_CENTER)
        Chassis_SetTrackMode(TRACK_NEAR_CENTER);
}

static void Nav_PrepareArrival(void)
{
    if ((fabsf(need2turn(getAngleZ(), nodes.nextNode.angle)) < 10.0f) ||
        (fabsf(need2turn(nodes.nowNode.angle, nodes.nextNode.angle)) < 10.0f) ||
        (nodes.nowNode.flag & NOTURN) == NOTURN)
    {
        /* 角度差小，保持原速，不操作 */
    }
    else//
    {
        Chassis_SetTargetSpeed(Gyro_Speed);
    }

    if(nodes.nowNode.nodenum == N14 && nodes.nextNode.nodenum == C3)
    {
        Chassis_SetTargetSpeed(SPEED1);
    }

}

static void Nav_NearEnd(void)
{
    map_function(nodes.nowNode.function);

    /* 尚未到达且无障碍结果时，通知 ArriveDetect_task 检测到达 */
    if ((cross_event & CROSS_EVENT_ARRIVED) != CROSS_EVENT_ARRIVED &&
        (cross_event & CROSS_EVENT_DOOR) != CROSS_EVENT_DOOR)
    {
        xTaskNotifyGive(xHandle_ArriveDetect);
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    }
}

static void Nav_TurnAndAdvance(void)
{
    cross_event &= ~CROSS_EVENT_ARRIVED;
    // Chassis_DisableStallProtection();  // 堵转保护已停用
    if (route[map.point - 1] != 0xFF)
    {
        /* 无需转弯，直接直行通过 */
        if ((fabsf(need2turn(getAngleZ(), nodes.nextNode.angle)) < 10.0f) ||
            (nodes.nowNode.flag & NOTURN) == NOTURN)
        {
             /* 无需转弯，直接直行通过 */
        }
        else/* 转弯 */
        {
            //循迹转弯（未用到）
            // if (nodes.nowNode.flag & L_follow)
            // {
            //     Chassis_Turn_By_LeftLine_Blocking(nodes.nextNode.angle, nodes.nowNode.angle, 0.75f * nodes.nowNode.speed);
            // }
            // else if (nodes.nowNode.flag & R_follow)
            // {
            //     Chassis_Turn_By_RightLine_Blocking(nodes.nextNode.angle, nodes.nowNode.angle, 0.75f * nodes.nowNode.speed);
            // }
            //原地转弯
            if ((nodes.nowNode.flag & STOPTURN && fabsf(need2turn(getAngleZ(), nodes.nextNode.angle)) > 30.0f)
            || (fabsf(need2turn(nodes.nowNode.angle, nodes.nextNode.angle)) > 90.0f)
            || nodes.nextNode.function == SM  && fabsf(need2turn(getAngleZ(), nodes.nextNode.angle)) > 30.0f
            || ((nodes.nowNode.function == UpStage || nodes.nowNode.function == UpStageHome)&& fabsf(need2turn(getAngleZ(), nodes.nextNode.angle)) > 15.0f))
                
            {
                //走补偿距离然后停下
                float forwardDist = GetForwardDistanceBeforeTurn(nodes.lastNode.nodenum, nodes.nowNode.nodenum, nodes.nextNode.nodenum);
                Chassis_DriveDistance_Blocking(is_Gyro, forwardDist, Stop_T_Speed, getAngleZ(), 0);
                CarBrake();
                //转弯
                Chassis_Turn_By_StopGyro_Blocking(nodes.nextNode.angle, getAngleZ(), 30.0f);
            }
            //陀螺仪不停车转弯
            else
            {
                //走补偿距离
                float forwardDist = GetForwardDistanceBeforeGyroTurn(nodes.lastNode.nodenum, nodes.nowNode.nodenum, nodes.nextNode.nodenum);
                Chassis_DriveDistance_Blocking(is_Gyro, forwardDist, Gyro_Speed, getAngleZ(), 0);
                //转弯
                Chassis_Turn_By_Gyro_Blocking(nodes.nextNode.angle, getAngleZ(), 50.0f);
            }
        }

        /* 节点切换 */
        nodes.lastNode = nodes.nowNode;
        nodes.nowNode = nodes.nextNode;
        nodes.nextNode = Node[getNextConnectNode(nodes.nowNode.nodenum, route[map.point++])];
        cross_event &= ~CROSS_EVENT_ARRIVED;
    }
    else if (route[map.point - 1] == 0xFF)
    {
        CarBrake();
        map.routetime += 1;
    }
}

static void Nav_PostProcess(void)
{
    if (cross_event & CROSS_EVENT_DOOR)
    {
        if (route[map.point] != 0xFF)
            nodes.nextNode = Node[getNextConnectNode(nodes.nowNode.nodenum, route[map.point])];
        map.point++;
        cross_event &= ~CROSS_EVENT_DOOR;
    }
}
/* ============================ Navigation()本体 =================================== */
void Navigation(void)
{
    static uint8_t nav_step = 0;
    static uint8_t near_end = 0;

    /* ---- 前半段：巡线行驶 ---- */
    if (near_end == 0)
    {
        if (nav_step == NAV_STEP_INIT)
        {
			//打印当前节点
			printf("Current Node: %d\n", nodes.nowNode.nodenum);
            Nav_SegmentInit();
            nav_step = NAV_STEP_MID_SWITCH;
        }

        if (fabsf(Chassis_GetMileage()) >= 0.5f * nodes.nowNode.step && nav_step == NAV_STEP_MID_SWITCH)
        {
            Nav_MidSwitch();
            nav_step = NAV_STEP_PREP_ARRIVE;
        }

        if (fabsf(Chassis_GetMileage()) >= 0.7f * nodes.nowNode.step && nav_step == NAV_STEP_PREP_ARRIVE)
        {
            Nav_PrepareArrival();
            near_end = 1;
        }
    }
    /* ---- 后半段：障碍 + 到达检测 ---- */
    else if (near_end == 1)
    {
        Nav_NearEnd();
        near_end = 0;
        nav_step = NAV_STEP_INIT;
    }

    /* ---- 到达节点：转弯 + 节点推进 ---- */
    if ((cross_event & CROSS_EVENT_ARRIVED) == CROSS_EVENT_ARRIVED)
        Nav_TurnAndAdvance();

    /* ---- 后处理：门结果（红灯/绿灯）---- */
    Nav_PostProcess();
}

/*功能选择*///执行阻塞函数
void map_function(u8 fun)
{
	switch(fun)
	{
		case 0:break;
		case NONE: 												break;			//寻找
		case UpStage    : Stage();			   					break;			//平台
		case Bridge   	: Barrier_Bridge();						break;			//过桥
		case Hill	    : Barrier_Hill();						break;			//山地
		case SM         : Sword_Mountain();						break;			//假山
		case BSoutPole	: South_Pole();	          				break;			//南极
		case QQB	    : QQB_1();	          					break;			//跷跷板
		case BLBS       : Barrier_WavedPlate(45);	    		break;			//短波动板 速度：调试 80//85
		case BLBL	    : Barrier_WavedPlate(90);	  			break;			//长波动板 速度：调试	//180
		case DOOR	    : door();		                 	  	break;			//门
		case BHM        : Barrier_HighMountain();				break;    		//高山
		case UpStageHome	: Stage_Home();	                		break;
		default:				                        		break;		
	}
}
