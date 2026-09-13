#include "map.h"//跑特点路线开关在这里面
#include "barrier.h"
#include "sys.h"
#include "math.h"
#include "chassis_api.h"
#include "stdio.h"

/* 最短路径规划器（新增）：见 nav_planner.h；数据/图在 map_message.h（NavEdgeTbl 单数据源） */
#include "nav_planner.h"



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
volatile uint8_t nav_token = 0;		//按一下跑一个节点调试：信号量/票计数（按键累积，每跑一条边-1）
/* arrive_method：定义在 Task/ArriveDetect_task.c（由它写），声明在 map.h；本文件只读，不要在此定义（会 L6200E） */
			   
				

/******************************************************************************/


#if MAP_DEBUG
//u8 route[100] = {N4, N3,P3, N3, N4, N5,N6,P4,N6,0XFF};

//u8 route[100] = {N4, B2,N1,P1, N1, B1, N2,P2,0XFF};
//u8 route[100] = { B5,N19,C6, B7, N22, B6,N20,P8,0XFF};
//u8 route[100] = {C9,0XFF};
//u8 route[100] = {N20,P8,N20, 0XFF};
//u8 route[100] = {B2,N1,P1, 0XFF};
//u8 route[100] = {N11,N12,N13,P5,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,0XFF};
//u8 route[100] = {N12,N11,N10,0XFF};
//u8 route[100] = {N13,P5,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,0XFF};
//u8 route[100] = {N11, 0XFF};
//u8 route[100] = {B1,N2,P2, 0XFF};
u8 route[100] = {B9,N7,P6,N7,B8,N9, 0XFF};
//u8 route[100] = {B2,N1,P1, N1, B1, N2, P2, 0XFF};
//u8 route[100] = {C7,C8,B11,C4,N20,P8,0XFF};
//u8 route[100] = {B11,C8,C7,B10,N14,0XFF};
//u8 route[100] = {N19,C6,B7,N22,C9,P7,0XFF};
//u8 route[100] = {C6,N19,B5,N18, 0XFF};
//u8 route[100] = {B3, N2, P2, 0XFF};
#else 
u8 route[100] = {B1, N1,P1, N1, B2, N4, N5,0XFF};  //初始路径
#endif

/************************************************************    *地图路径*    **********************************************************************************************************************************************88 */
/* door*route 已移至 mission_planner.c（门回程业务逻辑相关）*/

/* rout_57/58/67/68 已删除 - USE_PLANNER_ROUTE=1 时由规划器动态生成 */

/*******************************************************************************************************************************************************************************************************************************************************/

 
/*地图初始化*/

static void nav_planner_setup(void)
{
    static uint8_t s_nav_ready = 0;
    if (!s_nav_ready) {
        nav_init(NavEdgeTbl, NAV_EDGE_COUNT, 54);   /* 统一构建执行层 + 规划层数据 */
        s_nav_ready = 1;
    }
}

void mapInit()
{
    nav_planner_setup();
    /* 规划层边禁用复位：一场/一轮开始时所有边默认可通行。
       门回程会用 nav_set_edge_blocked() 封闭门区，二轮必须从这里放开。 */
    nav_clear_blocked();
#if USE_PLANNER_ROUTE
    /* 用最短路径算法重算第一轮初始路线：起点N2 → 必经过P1(扫码) → 终点N5。
     * 验证：nav_build_route({N2,P1,N5}) 输出 == 现有 route[] = {B1,N1,P1,N1,B2,N4,N5} */
    {
        static const u8 wp_base[] = {N2, P1, N5};   /* 起点N2 → 必经过P1(扫码) → 终点N5 */
        nav_build_route(route, sizeof(route), wp_base, sizeof(wp_base)/sizeof(wp_base[0]));
    }
#endif
	map = (struct Map_State){0,0};
    nodes = (Nodes){0};	
	cross_event = 0;       //起始点   
#if MAP_DEBUG
    /* 最短路径调试：只写 config.h 的 FIRST_POINT / VIA_POINT / END_POINT，规划器自动生成路线，
     * 不再需要手写 route[]/SECOND_POINT。
     * VIA_POINT = 0 表示不用途径点（退化为 FIRST_POINT->END_POINT 两点）。
     * wp   = [FIRST_POINT, (VIA_POINT), END_POINT]
     * path = [FIRST_POINT, ..., (VIA_POINT), ..., END_POINT, 0xFF]；车从 FIRST_POINT 出发：
     *   firstNode(nowNode) = path[1]（第一跳）
     *   route = [path[2], ..., END_POINT, 0xFF]（path[1] 已在 nowNode，route 从 path[2] 起，避免与 nowNode 重复） */
    nodes.lastNode.nodenum = FIRST_POINT;  //起始点
    {
        u8 wp[3];              /* 最多三个必经点：起点 + 途径点 + 终点 */
        u8 nwp = 0;
        u8 via = (u8)VIA_POINT;   /* 途径点编号；0=不用途径点（用局部变量比较，避免常量比较告警） */
        u8 path[NAV_MAX_PATH];
        uint8_t n;
        wp[nwp++] = FIRST_POINT;                 /* 起点 */
        if (via != 0u) wp[nwp++] = via;          /* 途径点：0=不用（S1=0 不能用） */
        wp[nwp++] = END_POINT;                   /* 终点 */
        /* n = 节点数 + 1（末尾写入了 0xFF 哨兵）；n==0 表示某一段不可达(配置错误) */
        n = nav_plan_waypoints(path, sizeof(path), wp, nwp);
        if (n < 3) return;   /* 至少要有 起点 + 第一跳 + 0xFF；不足则起终点相同/不可达，直接返回不规划 */
        {
            u8 idx = getNextConnectNode(FIRST_POINT, path[1]);   /* 第一跳(从 FIRST_POINT 出发) */
            if (idx == ROUTE_NOT_FOUND) return;   /* 兜底：起始连接错误，Route_Error_Stop 已死停车 */
            nodes.nowNode = Node[idx];
        }
        {
            uint8_t j = 0;
            /* i+1 < n ：跳过末尾 0xFF（下面统一补），只拷 path[2]..path[n-2] */
            for (uint8_t i = 2; i + 1 < n && j < (uint8_t)sizeof(route); i++) route[j++] = path[i];
            if (j < (uint8_t)sizeof(route)) route[j++] = 0xFF;
        }
    }
#else
    {
        u8 idx = getNextConnectNode(P2, N2);  //起始目标点
        if (idx == ROUTE_NOT_FOUND) return;   /* 兜底：起始连接错误，Route_Error_Stop 已死停车 */
        nodes.nowNode = Node[idx];
    }
#endif
	/* 兜底：0xFF=路线结束哨兵，不查连接（否则 getNextConnectNode 会误判失败而停车） */
	if (route[map.point] != 0xFF)
		nodes.nextNode = Node[getNextConnectNode(nodes.nowNode.nodenum, route[map.point])];
	map.point++;
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
 * 
 * 兜底（2026 防跑飞）：查不到连接（节点写错/连接表漏配）时不再返回 0（Node[0]=S1 会带车跑飞），
 * 而是打印错误并直接死停车（Route_Error_Stop 内部 while(1)，不会返回）。
 * 注意：调用方在 route 指向 0xFF（路线结束哨兵）时必须自行跳过本函数，勿把 0xFF 传入。
 */
u8 getNextConnectNode(u8 nownode,u8 nextnode) 
{
	/* 兜底：节点编号越界（连接表只覆盖 0~53）*/
	if (nownode >= 54)
	{
		Route_Error_Stop(nownode, nextnode);
		return ROUTE_NOT_FOUND;
	}
	unsigned char rest = ConnectionNum[nownode];	//获取当前节点的连接数
	unsigned char addr = Address[nownode];		//得到首地址
	int i = 0;
	for (i = 0; i < rest; i++) 
	{
		if(Node[addr].nodenum == nextnode)		//返回目标地址	
			return addr;
		addr++;
	}
	/* 兜底：找不到连接（节点写错/连接表漏配）→ 直接停车，防止小车跑飞 */
	Route_Error_Stop(nownode, nextnode);
	return ROUTE_NOT_FOUND;
}

/* 兜底停车：查找路线失败直接死停车（打印出错节点对，方便定位写错的节点） */
void Route_Error_Stop(u8 from, u8 to)
{
	printf("ROUTE ERROR: no connection %d -> %d, STOP!\r\n", from, to);
	CarBrake_Stop();   /* 卡死停车：内部 while(1) 持续刹车，不返回 */
    send_play_specified_command(33);   /* 播报“路线错误” */
}



/* ============ 转弯前补偿距离：实测表 + "能算就算"公式 ============
 * 背景与验证见 project_reference.md §14、项目讲解文档/转弯补偿_能算就算方案.md
 *
 * 结论：这一列历史上同时表达了两件事 ——
 *   ① 真·转弯几何 Δ = L(1-cosφ) + d(判据)（L = 旋转中心→传感器板中心纵向距离 ≈19cm）
 *   ② 段长补偿（step 太短时车被 0.7*step 里程门槛提前放行，补偿实际在补段长，跟几何无关）
 * 所以对①用公式算、对②保留原值。
 *
 * 三层：
 *   Tier1  实测表命中                                  → 用实测值
 *   Tier2  平地 + 入边 step>=20 + 转弯100°~178°        → 用公式；但若表里也有且 |公式-实测|>5cm → 落回实测值
 *   Tier3  都不命中                                    → 默认 19（原行为）
 */

/* 判据 → 该判据的固有检测滞后 d（cm）。由 8 条"平地+大角度"实测反解得出（L 取 19）。 */
#define TURN_D_CRIGHT   ( 11.0f)   /* 右斜线（右起2/3灯）—— 最晚触发，滞后最大 */
#define TURN_D_CLEFT    ( -4.0f)
#define TURN_D_DLEFT    ( -5.0f)
#define TURN_D_DEFAULT  ( -4.0f)
#define TURN_L_PIVOT    ( 19.0f)   /* 旋转中心→传感器板中心 纵向距离 */
#define TURN_GATE_CM    (  5.0f)   /* 5cm 闸门：公式与实测差超过它就不用公式 */

/* 表1：停车原地转前的前进距离（实测值，三元组 → cm）
 * 2026-09-12 清掉 4 条"调车时调了但永远不会执行"的条目：
 *   B3→N2→P2=24、N8→N3→P3=18 → 实际转弯只有 -30°/35°，走"陀螺不停车转"分支（见表2）
 *   N2→N8→N10=15            → 边表里没有 N2→N8 这条边
 *   N13→N18→B5=60           → 原代码里整行被 // 注释掉（同一三元组现由 Tier2 公式给出 28.9）
 * ⚠️ 只能收"真正会走停车转分支"的三元组：分支判定 = (STOPTURN && |转弯|>30) || |转弯|>=90 */
static const struct { u8 last, now, next; float dist; } kTurnTbl[] = {
	{ B9, N7, P6, 25 },
	{ P6, N7, B8, 20 },
	{ C4, N20, P8, 35 },
	{ N20, C4, B11, 25 },
	{ N3, N4, B2, 30 },
	{ P8, N20, C4, 30 },
	{ N8, N5, N4, 36 },
	{ N5, N8, N12, 20 },
	{ N8, N3, N4, 30 },
	{ N4, N3, N8, 20 },
	{ B8, N9, C3, 0 },
    { B11, C4, N20, 19 },
	{ N10, N9, B9, 48 },
	{ B2, N1, P1, 25 },
};
/* 编译期护栏：kTurnTbl 里的节点号不能超过实际建表的节点数（写错节点号只会在车上才发现）。
 * 50 = map.h 里 enum MapNode 的真实成员数（C1/C2 是注释状态不占编号），
 * 也就是 mapInit() 里 nav_init(NavEdgeTbl, NAV_EDGE_COUNT, 54) 那个 54 的宽松上界之下。
 * 以后增删节点，这里和 nav_init 的节点数一起改。 */
#define MAP_NODE_LIMIT   50
typedef char kTurnTbl_node_check[
	((B9  < MAP_NODE_LIMIT) && (N7  < MAP_NODE_LIMIT) && (P6  < MAP_NODE_LIMIT) &&
	 (C4  < MAP_NODE_LIMIT) && (N20 < MAP_NODE_LIMIT) && (P8  < MAP_NODE_LIMIT) &&
	 (B11 < MAP_NODE_LIMIT) && (N3  < MAP_NODE_LIMIT) && (N4  < MAP_NODE_LIMIT) &&
	 (B2  < MAP_NODE_LIMIT) && (N8  < MAP_NODE_LIMIT) && (N5  < MAP_NODE_LIMIT) &&
	 (N12 < MAP_NODE_LIMIT) && (N9  < MAP_NODE_LIMIT) && (B8  < MAP_NODE_LIMIT) &&
	 (C3  < MAP_NODE_LIMIT) && (N10 < MAP_NODE_LIMIT) && (N1  < MAP_NODE_LIMIT) &&
	 (P1  < MAP_NODE_LIMIT)) ? 1 : -1];

/* 在 Node[] 里按节点号找条目。
 * ⚠️ 不能用 getNextConnectNode()：它返回的是"连接表下标"（Address[from] 起的偏移），
 *    不是 Node[] 下标 —— 只有目标节点恰好是 from 的第一个连接时才凑巧相等。 */
static const NODE *Node_Lookup(u8 nodenum)
{
	u8 i;
	for (i = 0; i < NAV_MAX_NODES; i++)
	{
		if (Node[i].nodenum == nodenum)
			return &Node[i];
	}
	return &Node[0];
}

/* 获取对应节点的原地转弯前的前进距离判断 */
static float GetForwardDistanceBeforeTurn(u8 last, u8 now, u8 next)
{
	u8    found = 0;
	float meas  = 19.0f;                 /* 默认值（原 return 19 的语义） */
	u8    i;

	for (i = 0; i < (u8)(sizeof(kTurnTbl) / sizeof(kTurnTbl[0])); i++)
	{
		if (kTurnTbl[i].last == last && kTurnTbl[i].now == now && kTurnTbl[i].next == next)
		{
			meas  = kTurnTbl[i].dist;
			found = 1;
			break;
		}
	}

#if TURN_CALC_ENABLE
	/* ---- Tier2：能算就算 ----
	 * ⚠️ 用启动时由边表建好的 Node[] 里的原始数据，不能读 nodes.nowNode.step/function：
	 *    door_set_pass_node() 会在跑的过程中把 step 改成 72/50/36、function 改成 NONE。 */
	{
		const NODE *in = Node_Lookup(last);      /* "last→now" 这条入边的原始属性 */
		float phi = fabsf(need2turn(nodes.nowNode.angle, nodes.nextNode.angle));

		if ((in->function == NONE || in->function == DOOR) &&
			in->step >= 20 &&
			phi >= 100.0f && phi < 178.0f)
		{
			float d = TURN_D_DEFAULT;
			if      (arrive_method == ARRIVE_CRIGHT) d = TURN_D_CRIGHT;
			else if (arrive_method == ARRIVE_CLEFT)  d = TURN_D_CLEFT;
			else if (arrive_method == ARRIVE_DLEFT)  d = TURN_D_DLEFT;
			/* cosf：M7 只有单精度 FPU，别用 double 的 cos */
			float calc = TURN_L_PIVOT * (1.0f - cosf(phi * (3.14159265f / 180.0f))) + d;

			/* 5cm 闸门：表里有实测值且公式与它差太多 → 放弃公式，用实测值 */
			if (!found || fabsf(calc - meas) <= TURN_GATE_CM)
				return calc;
		}
	}
#endif

	if (found)
		return meas;
	return 19;
}

/* 获取对应节点的陀螺仪不停车转弯前的前进距离判断 */
static float GetForwardDistanceBeforeGyroTurn(u8 last, u8 now, u8 next)
{
	if (last == B2 && now == N4 && next == N5)return 8; 
	if (last == B3 && now == N2 && next == P2) return 18;
    if (last == B2 && now == N1 && next == P1) return 18;
	if (last == P3 && now == N3 && next == N8) return 6;
    if (last == C4 && now == N20 && next == B6) return 24;
	if (last == N3 && now == N4 && next == B3) return 12;
    if (last == N5 && now == N12 && next == N11) return 5;
    if (last == N8 && now == N12 && next == N13) return 5;
    if (last == N4 && now == N5 && next == N12) return 6;
	if (last == N8 && now == N3 && next == P3) return 24;
	if (last == P1 && now == N1 && next == B2)return 3; 
	return 0; // 默认不前进，走原逻辑未修改
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
    NAV_STEP_PREP_ARRIVE,  // 2  70% 降速准备到达
    NAV_STEP_NEAR_END      // 3  后半段：障碍 + 到达检测
};

/* ============================ Navigation() 子函数 =================================== */

#define STRAIGHT_ANGLE_THRESH  5.0f   /* 判定"直穿节点"的角差阈值(°) */

/* 判断当前节点是否"直穿"：进入与离开本节点的期望方位角几乎相同（本节点不转弯）。
 * 用于决定是否开启长直线陀螺仪阻尼补偿（只在确知是直线段时叠加，别处关闭）。 */
static uint8_t Nav_IsStraightThrough(void)
{
    /* 首个边 lastNode 未初始化(0)，跳过：仅影响是否加小阻尼，宁可不加 */
    if (nodes.lastNode.nodenum == 0)
        return 0;
    if ((fabsf(need2turn(nodes.nowNode.angle, nodes.nextNode.angle)) < STRAIGHT_ANGLE_THRESH 
            && nodes.nowNode.speed >= SPEED1 
            && nodes.nowNode.step >=30)
        ||nodes.nowNode.step >=90)
        return 1;
    return 0;
}

static void Nav_SegmentInit(void)
{
    //路程初始化
    Chassis_ClearMileage();
    //循迹中心
    Chassis_SetCatchSensorNum(0);
    //设置忽略边缘
    Chassis_SetEdgeIgnore(0);
    // 根据当前边的 flag 设置循迹模式
    if ((nodes.nowNode.flag & NEAR_CENTER) == NEAR_CENTER)
        Chassis_SetTrackMode(TRACK_NEAR_CENTER);
    else if ((nodes.nowNode.flag & LEFT_LINE) == LEFT_LINE)
        Chassis_SetTrackMode(TRACK_LEFT_EDGE);
    else if ((nodes.nowNode.flag & RIGHT_LINE) == RIGHT_LINE)
        Chassis_SetTrackMode(TRACK_RIGHT_EDGE);
    else
        Chassis_SetTrackMode(TRACK_NEAR_CENTER);
    // 长直线陀螺仪阻尼补偿：直穿段开，其它关（先设标志再进 is_Line，避免首帧误加）
    if (Nav_IsStraightThrough())
        Chassis_EnableLineGyroComp(LINE_GYRO_COMP_KD);
    else
        Chassis_DisableLineGyroComp();
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
        Chassis_SetTargetSpeed(SPEED0);
    }

    if(nodes.nowNode.nodenum == N14 && nodes.nextNode.nodenum == C3)
    {
        Chassis_SetTargetSpeed(SPEED1);
    }
    if(nodes.nowNode.function !=NONE && nodes.nowNode.speed >= SPEED0)
    {
        Chassis_SetTargetSpeed(SPEED0);
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
        /* 平台类障碍(UpStage/UpStageHome/BSoutPole)内部已完成180°转身并下坡回到坡底，
           实际朝向已对准 return 边(nextNode.angle)，此处不应再走补偿距离+原地转弯
           —— 否则会在"下了平台还没到下一节点"时突然停车转弯。
           ⚠️ 依赖 barrier.c 中 Stage/Stage_Home/South_Pole 结束时保留 nodes.nowNode.function
              （不再清 0），该判断才能命中。 */
        if ((fabsf(need2turn(getAngleZ(), nodes.nextNode.angle)) < 10.0f)
            ||(fabsf(need2turn(nodes.nowNode.angle, nodes.nextNode.angle)) < 10.0f)
            || (nodes.nowNode.flag & NOTURN) == NOTURN
            ||  nodes.nowNode.function == UpStage
            ||  nodes.nowNode.function == UpStageHome
            ||  nodes.nowNode.function == BSoutPole)
        {
             /* 无需转弯，直接直行通过 */
             if(Nav_IsStraightThrough())
             Chassis_DriveDistance_Blocking(is_Line, 15, nodes.nowNode.speed, 0, 6);
             
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
            || (fabsf(need2turn(nodes.nowNode.angle, nodes.nextNode.angle)) >= 90.0f )
            )
                
            {
                //走补偿距离然后停下
                float forwardDist = GetForwardDistanceBeforeTurn(nodes.lastNode.nodenum, nodes.nowNode.nodenum, nodes.nextNode.nodenum);
                Chassis_DriveDistance_Blocking(is_Gyro, forwardDist, Stop_T_Speed, getAngleZ(), 0);
                CarBrake();
                //转弯
                Chassis_Turn_By_StopGyro_Blocking(nodes.nextNode.angle, getAngleZ(), 35.0f);
            }
            //陀螺仪不停车转弯
            else
            {
                //走补偿距离
                float forwardDist = GetForwardDistanceBeforeGyroTurn(nodes.lastNode.nodenum, nodes.nowNode.nodenum, nodes.nextNode.nodenum);
                Chassis_DriveDistance_Blocking(is_Gyro, forwardDist, Gyro_Speed, getAngleZ(), 0);
                //转弯
                Chassis_Turn_By_Gyro_Blocking(nodes.nextNode.angle, getAngleZ(), 40.0f);
            }
        }

        /* 节点切换 */
        nodes.lastNode = nodes.nowNode;
        nodes.nowNode = nodes.nextNode;
        /* 兜底：0xFF=路线结束哨兵，不查连接（否则 getNextConnectNode 会误判失败而停车） */
        if (route[map.point] != 0xFF)
            nodes.nextNode = Node[getNextConnectNode(nodes.nowNode.nodenum, route[map.point])];
        map.point++;
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
    cross_event &= ~CROSS_EVENT_DOOR;
    if (route[map.point] != 0xFF)
        nodes.nextNode = Node[getNextConnectNode(nodes.nowNode.nodenum, route[map.point])];
    map.point++;
       
}
/* ============================ Navigation()本体 =================================== */
void Navigation(void)
{
    static uint8_t nav_step = 0;

#if STEP_DEBUG
    /* --- 按一下跑一个节点：等票门控（每跑一条边=一个节点，扣1票；无票则停） --- */
    {
        static uint8_t nav_idle_braked = 0;
        /* 仅在“新边开始”处门控；路线结束哨兵(0xFF)不在这里拦，交给原逻辑收尾 */
        if ((nav_step == NAV_STEP_INIT) && (route[map.point] != 0xFF))
        {
            if (nav_token == 0)
            {
                /* 无票：停车等票（自由轮，方便抱放）。只刹一次，避免每周期重刹 */
                if (!nav_idle_braked)
                {
                    Chassis_MotorControl(is_Free, 0, 0, 0);
                    nav_idle_braked = 1;
                }
                return;
            }
            nav_token--;           /* 有票：扣1张票，放行本条边 */
            nav_idle_braked = 0;
        }
    }
#endif

    switch (nav_step)
    {
    case NAV_STEP_INIT:
        printf("Current Node: %d\n", nodes.nowNode.nodenum);
        Nav_SegmentInit();
        nav_step = NAV_STEP_MID_SWITCH;
        break;

    case NAV_STEP_MID_SWITCH:
        if (fabsf(Chassis_GetMileage()) >= 0.5f * nodes.nowNode.step)
        {
            Nav_MidSwitch();
            nav_step = NAV_STEP_PREP_ARRIVE;
        }
        break;

    case NAV_STEP_PREP_ARRIVE:
        if (fabsf(Chassis_GetMileage()) >= 0.6f * nodes.nowNode.step)
        {
            Nav_PrepareArrival();//减速
        }
        if(map.routetime == 2 && (nodes.nowNode.nodenum == N8 ||nodes.nowNode.nodenum == N5 ||
                                    nodes.nowNode.nodenum == N3||  nodes.nowNode.nodenum == N12 ||
                                    nodes.nowNode.nodenum == N10))
        {
            if (fabsf(Chassis_GetMileage()) >= 0.8f * nodes.nowNode.step)
            {
                nav_step = NAV_STEP_NEAR_END;
            }     
        }
        else 
        {
            if (fabsf(Chassis_GetMileage()) >= 0.7f * nodes.nowNode.step)
            nav_step = NAV_STEP_NEAR_END;
        }
        break;

    case NAV_STEP_NEAR_END:
        Nav_NearEnd();
        nav_step = NAV_STEP_INIT;
        break;

    default:
        break;
    }

    /* ---- 到达节点：转弯 + 节点推进 ---- */
    if ((cross_event & CROSS_EVENT_ARRIVED) == CROSS_EVENT_ARRIVED)
        Nav_TurnAndAdvance();

    /* ---- 后处理：门结果（红灯/绿灯）---- */
    if (cross_event & CROSS_EVENT_DOOR)
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
		case BLBS       : Barrier_WavedPlate(70);	    		break;			//短波动板 速度：调试 80//85
		case BLBL	    : Barrier_WavedPlate(35);	  			break;			//长波动板 速度：调试	//180
		case DOOR	    : door();		                 	  	break;			//门
		case BHM        : Barrier_HighMountain();				break;    		//高山
		case UpStageHome	: Stage_Home();	                		break;
		default:				                        		break;		
	}
}
