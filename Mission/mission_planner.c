/*
 * mission_planner.c - 任务规划器
 *
 * 职责：根据比赛规则（QR码、门颜色、宝物位置）动态决定路线
 *
 * 数据依赖：
 *   - 全局状态：door_pass[], treasure, flag_line_clue, flag_clue_stage_A/B
 *   - 地图数据：route[], nodes, map (from map.h)
 *   - 预定义路线：door*route[] (from map.c)
 *
 * 调用关系：
 *   barrier.c (door/Stage等) → mission_planner (本模块) → nav_planner (最短路算法)
 */

#include "mission_planner.h"
#include "map.h"
#include "nav_planner.h"
#include "chassis_api.h"
#include "barrier.h"
#include "stdio.h"

/* ==================== 外部依赖 ==================== */
extern uint8_t door_pass[5];              // 门通行状态（barrier.c）
extern uint8_t treasure;                  // 宝物平台编号（barrier.c）
extern volatile uint8_t flag_line_clue;   // QR百位（barrier.c）
extern volatile uint8_t flag_clue_stage_A;// QR十位（barrier.c）
extern volatile uint8_t flag_clue_stage_B;// QR个位（barrier.c）
extern u8 route[100];                     // 全局路线数组（map.c）
extern Nodes nodes;                       // 当前节点状态（map.c）
extern struct Map_State map;              // 地图状态（map.c）

/* 门操作函数（barrier.c）*/
extern NODE door_set_pass_node(uint8_t a, uint8_t b, uint16_t step, float speed);

/* ==================== 门回程：仍保留的手写路线 ==================== */
/* D2 关 + D3 关 时"从 N4 去撞 D4 读灯"（barrier.c 的 DOOR_D3 NO_PASS 分支加载）。
   它是"去下一扇门"而非回程，且只有 2 个节点，故未纳入下面 route_return_home() 的规划器方案。 */
u8 door1route[100] = {N3, N8, 0XFF};                     // D2关D3关，去D4

/* ==================== 门区边表（规划层禁用用） ==================== */
/* 门区 8 条通行边（4 对 × 2 方向），与 Clear_door() 操作的是同一组边。
   回程时全部禁用，防止最短路又拐回门区、或在门口穿门掉头。 */
static const u8 door_zone[8][2] = {
	{N5, N12}, {N12, N5}, {N5, N8}, {N8, N5},
	{N3, N8},  {N8, N3},  {N3, N10}, {N10, N3},
};

/* ==================== 内部辅助函数 ==================== */

/**
 * @brief 加载路线到 route[] 指定位置
 * @param offset 起始偏移量
 * @param src 源路线数组（以 0xFF 结尾）
 */
void load_route_at(uint8_t offset, const u8* src)
{
	for(uint8_t i = 0; i < 50; i++)
	{
		route[offset + i] = src[i];
		if(src[i] == 0xFF)
			break;
	}
}

/**
 * @brief 使用规划器生成路线并写入 route[]
 * @param offset route[] 起始偏移
 * @param waypoints 必经点数组
 * @param waypoint_count 必经点数量
 * @return 1=成功, 0=失败(已 CarBrake_Stop)
 * @note  不受 USE_PLANNER_ROUTE 开关影响：门回程（route_return_home）恒用规划器，
 *        因为穷举数组正是"规划器不知道哪扇门能过"的产物，见 _check_door_perm.py。
 */
static uint8_t plan_route_at(uint8_t offset, const u8 *waypoints, uint8_t waypoint_count)
{
	uint8_t written;

	if (offset >= sizeof(route))
	{
		CarBrake_Stop();
		return 0;
	}

	written = nav_build_route(&route[offset], (uint8_t)(sizeof(route) - offset),
		waypoints, waypoint_count);
	if (written == 0)
	{
		route[offset] = 0xFF;
		CarBrake_Stop();
		return 0;
	}
	return 1;
}

#if USE_PLANNER_ROUTE
/**
 * @brief P7/P8 得到宝物编号后规划回程（含宝物平台）
 * @param start 起点（P7 或 P8）
 * @return 1=成功, 0=失败
 */
static uint8_t plan_treasure_return(uint8_t start)
{
	u8 wp[10];
	uint8_t n = 0;
	uint8_t target;

	switch (treasure)
	{
	case 2: target = P1; break;
	case 3: target = P3; break;
	case 4: target = P4; break;
	case 5: target = P5; break;
	case 6: target = P6; break;
	default:
		CarBrake_Stop();
		return 0;
	}

	wp[n++] = start;

	/* 特殊平台处理：P5 是 N13 支路，P6 经 N7/N9 支路（跷跷板单向由图约束）*/
	if (treasure == 5)
	{
		wp[n++] = P5;
	}
	else if (treasure == 6)
	{
		wp[n++] = P6;
	}

	/* 根据门状态选择回程路径 */
	if (door_pass[0] == CAN_PASS)
	{
		wp[n++] = N12;
		wp[n++] = N5;
	}
	else if (door_pass[1] == CAN_PASS)
	{
		wp[n++] = N12;
		wp[n++] = N8;
		wp[n++] = N5;
	}
	else if (door_pass[2] == CAN_PASS)
	{
		wp[n++] = N12;
		wp[n++] = N8;
		wp[n++] = N3;
	}
	else if (door_pass[0] == ONE_WAY_PASS || door_pass[1] == ONE_WAY_PASS ||
		door_pass[2] == ONE_WAY_PASS)
	{
		/* 回程需经 D5；该门仍由 door() 在 N10->N3 上读取和处理 */
		wp[n++] = N10;
		wp[n++] = N3;
	}
	else
	{
		CarBrake_Stop();
		return 0;
	}

	/* 添加非特殊平台的宝物目标 */
	if (treasure != 5 && treasure != 6)
		wp[n++] = target;
	wp[n++] = P2;

	/* 交接（stageAB 段不再写尾锚点 C9/N20 后必须做）：
	 * 本函数只在宝物平台上被调用，而 stageAB 段现在以平台本身为终点。
	 * 到达平台那一刻 nodes.nextNode 会停在"进平台那条边"，若不修正：
	 *   ① 推进时 nodes.nowNode = nodes.nextNode 会错位 → 下一步 getNextConnectNode 找不到边 → Route_Error_Stop 死停车；
	 *   ② Stage_Correct() 拿 nodes.nextNode.angle 当行驶航向，会反向 180°。
	 * 所以这里显式把 nextNode 对齐到"出平台第一跳"（= 本段重规划后的第一个目标）。
	 * 证据：scripts/validate/_check_wp_east.py + 状态机仿真（删尾锚点不补交接 = 4/4 场次死停车）。 */
	if (plan_route_at(map.point - 1, wp, n) == 0)
		return 0;
	if (map.point > 0)
	{
		u8 first = route[map.point - 1];
		if (first != 0xFF)
			nodes.nextNode = Node[getNextConnectNode(start, first)];
	}
	return 1;
}
#endif

/**
 * @brief 判断门是否可通行（CAN_PASS 或 ONE_WAY_PASS）
 */
static uint8_t Can_Pass(uint8_t c)
{
	return c == CAN_PASS || c == ONE_WAY_PASS;
}

/**
 * @brief 拼接第二轮路线（pre + entry + tour + tail）
 * @note  仅 USE_PLANNER_ROUTE=0 的手工兜底分支使用，=1 时不参与编译
 */
#if !USE_PLANNER_ROUTE
static void build_round2_route(const u8 *pre, const u8 *entry, const u8 *tour, const u8 *tail)
{
	uint8_t i, n = 0;
	for (i = 0; pre[i] != 0XFF; i++)	route[n++] = pre[i];
	for (i = 0; entry[i] != 0XFF; i++)	route[n++] = entry[i];
	for (i = 0; tour[i] != 0XFF; i++)	route[n++] = tour[i];
	for (i = 0; tail[i] != 0XFF; i++)	route[n++] = tail[i];
	route[n] = 0XFF;
}
#endif /* !USE_PLANNER_ROUTE */

/* ==================== 公共 API 实现 ==================== */

void update_route_at_P1(void)
{
	if(flag_line_clue == 3)
	{
		const u8 r[] = {B1, N1, P1, N1, B2, N4, N3, P3, N3, N4, N5, N12, 0XFF};
		load_route_at(0, r);
	}
	else if(flag_line_clue == 4)
	{
		const u8 r[] = {B1, N1, P1, N1, B2, N4, N5, N6, P4, N6, N5, N12, 0XFF};
		load_route_at(0, r);
	}
	else if(flag_line_clue == 0)
	{
		// 跳过 P3/P4，直接去门区
		const u8 r[] = {B1, N1, P1, N1, B2, N4, N5, N12, 0XFF};
		load_route_at(0, r);
	}
}

/* ==================== 门回程：规划层方案（替代原来的 12 条手写穷举） ====================
 * 原理：回程之所以原先要写死路线，是因为"规划器不知道哪扇门此刻不能走"，会穿门/在门口掉头。
 *       现在先把【整个门区 8 条边】在规划层禁用（门区是单向/禁行约束的集中地，回程不再进去），
 *       再用一句 wp={当前节点,[宝物平台],P2} 让最短路自己算回家路。
 * 例外：door_2 那一种情形（D5 黑、D3 蓝已用尽）必须从 N8 经 D4 退回 N3 重读 D4，
 *       所以额外放行 N8→N3 —— 这是这条路上唯一允许穿的门。
 * 等价性：12 种 (入口 × 宝物) 组合已由 scripts/validate/_check_door_perm.py 证明与
 *         改造前的手写穷举路线逐字一致（golden 取自改造前的 git 快照）。
 * ================================================================================ */

/* 门区 8 条边全部设为"规划时不可通行" */
static void door_block_all(void)
{
	for (u8 i = 0; i < 8; i++)
		nav_set_edge_blocked(door_zone[i][0], door_zone[i][1], 1);
}

/**
 * @brief 门回程：封闭门区后，用最短路从当前(内侧)节点回家（必要时先绕去宝物平台）
 * @param allow_N8_N3 1=额外放行 N8→N3（door_2：退回去重读 D4）
 */
static void route_return_home(uint8_t allow_N8_N3)
{
	u8 wp[3];
	uint8_t n = 0;

	door_block_all();
	if (allow_N8_N3)
		nav_set_edge_blocked(N8, N3, 0);

	wp[n++] = nodes.nowNode.nodenum;      /* 调用前已由 door_retreat/door_set_pass_node 置为 N3 / N8 / N5 */
	if (treasure == 2)       wp[n++] = P1;
	else if (treasure == 3)  wp[n++] = P3;
	else if (treasure == 4)  wp[n++] = P4;
	/* 宝物在 P5/P6 时本轮已到过，回程直接回家 */
	wp[n++] = P2;

	(void)plan_route_at(0, wp, n);
}

void update_route_by_door_1(void)
{
	route_return_home(0);      /* D5 绿：nowNode 已到 N3 */
}

void update_route_by_door_2(void)
{
	route_return_home(1);      /* D5 黑 + D3 蓝：nowNode 退到 N8，须经 D4 退回 N3 重读 D4 */
}

void update_route_by_door_3(void)
{
	route_return_home(0);      /* D4 回程绿：nowNode 已到 N3 */
}

void update_route_by_door_4(void)
{
	route_return_home(0);      /* D4 回程黑：nowNode 退到 N5 */
}

void update_route_at_door_for_stageAB(void)
{
#if USE_PLANNER_ROUTE
	/* 过门后只要 P 平台本身：环上节点、以及平台出口锚点(C9/N20)全部交给最短路自动选。
	 * 平台出口锚点原先靠"路线里还有下一跳"给 nodes.nextNode 兜底；现在改成
	 * plan_treasure_return() 里显式把 nextNode 对齐到"出平台第一跳"（见该函数注释）。 */
	if (flag_clue_stage_A == 5 && flag_clue_stage_B == 7)
	{
		u8 wp[] = {nodes.nowNode.nodenum, P5, P7};
		(void)plan_route_at(0, wp, sizeof(wp) / sizeof(wp[0]));
	}
	else if (flag_clue_stage_A == 5 && flag_clue_stage_B == 8)
	{
		u8 wp[] = {nodes.nowNode.nodenum, P5, P8};
		(void)plan_route_at(0, wp, sizeof(wp) / sizeof(wp[0]));
	}
	else if (flag_clue_stage_A == 6 && flag_clue_stage_B == 7)
	{
		u8 wp[] = {nodes.nowNode.nodenum, P6, P7};
		(void)plan_route_at(0, wp, sizeof(wp) / sizeof(wp[0]));
	}
	else if (flag_clue_stage_A == 6 && flag_clue_stage_B == 8)
	{
		u8 wp[] = {nodes.nowNode.nodenum, P6, P8};
		(void)plan_route_at(0, wp, sizeof(wp) / sizeof(wp[0]));
	}
	else
		CarBrake_Stop();
	return;
#endif
#if !USE_PLANNER_ROUTE
	/* ⚠️ 以下 USE_PLANNER_ROUTE=0 的手工兜底分支暂时不参与编译：
	   rout_57/58/67/68 已从 map.c 删除（改由规划器动态生成），切回 0 前需先恢复这些路线数组 */
	// 按线索平台组合选择路线
	if (flag_clue_stage_A == 5 && flag_clue_stage_B == 7)
	{
		if(Can_Pass(door_pass[0]))
			load_route_at(0, rout_57);
		else if(Can_Pass(door_pass[1]) || Can_Pass(door_pass[2]))
		{
			route[0] = N12;
			load_route_at(1, rout_57);
		}
	}
	else if (flag_clue_stage_A == 5 && flag_clue_stage_B == 8)
	{
		if(Can_Pass(door_pass[0]))
			load_route_at(0, rout_58);
		else if(Can_Pass(door_pass[1]) || Can_Pass(door_pass[2]))
		{
			route[0] = N12;
			load_route_at(1, rout_58);
		}
	}
	else if (flag_clue_stage_A == 6 && flag_clue_stage_B == 7)
	{
		if(Can_Pass(door_pass[0]))
		{
			route[0] = N11;
			route[1] = N10;
			load_route_at(2, rout_67);
		}
		else if(Can_Pass(door_pass[1]) || Can_Pass(door_pass[2]))
		{
			route[0] = N10;
			load_route_at(1, rout_67);
		}
	}
	else if (flag_clue_stage_A == 6 && flag_clue_stage_B == 8)
	{
		if(Can_Pass(door_pass[0]))
		{
			route[0] = N11;
			route[1] = N10;
			load_route_at(2, rout_68);
		}
		else if(Can_Pass(door_pass[1]) || Can_Pass(door_pass[2]))
		{
			route[0] = N10;
			load_route_at(1, rout_68);
		}
	}
#endif /* !USE_PLANNER_ROUTE */
}

void update_route_at_P7_for_treasure(void)
{
#if USE_PLANNER_ROUTE
	(void)plan_treasure_return(P7);
#endif
	/* USE_PLANNER_ROUTE=0 时的手工路线已注释（见 barrier.c 原始版本）*/
}

void update_route_at_P8_for_treasure(void)
{
#if USE_PLANNER_ROUTE
	printf("treasure%d\r\n",treasure);
	(void)plan_treasure_return(P8);
#endif
	/* USE_PLANNER_ROUTE=0 时的手工路线已注释（见 barrier.c 原始版本）*/
}

void Clear_door(void)
{
	nav_clear_blocked();    /* 规划层同步放行：二轮起所有门区边恢复可通行 */
	door_set_pass_node(N5, N12, DOOR_LEN_N5N12, SPEED4);
	door_set_pass_node(N12, N5, DOOR_LEN_N5N12, SPEED4);
	door_set_pass_node(N5, N8, DOOR_LEN_N5N8, SPEED4);
	door_set_pass_node(N8, N5, DOOR_LEN_N5N8, SPEED4);
	door_set_pass_node(N3, N8, DOOR_LEN_N3N8, SPEED4);
	door_set_pass_node(N8, N3, DOOR_LEN_N3N8, SPEED4);
	door_set_pass_node(N3, N10, DOOR_LEN_N3N10, SPEED4);
	door_set_pass_node(N10, N3, DOOR_LEN_N3N10, SPEED4);
}

void get_newroute(void)
{
	extern void mapInit(void);  /* 前向声明 */

	const u8 r[] = {B1, N1, P1, 0XFF};
	load_route_at(0, r);
	mapInit();
	// 全部放行通行
	Clear_door();

#if USE_PLANNER_ROUTE
	{
		u8 wp[24];
		uint8_t n = 0;
		uint8_t p6_first = (treasure == 6);

		/* 第一轮已回到 P2；第二轮固定完成 P1/P3/P4，再按门状态进入东区 */
		wp[n++] = N2;
		wp[n++] = P1;
		wp[n++] = P3;
		wp[n++] = P4;
		wp[n++] = N5;

		/* 进门：只留"真正要过的那扇门"；环上入口(N8 之后的 N12、N3 之后的 N8)由最短路自动选
		 * ——实测与写全 N 锚点逐字节相同，见 scripts/validate/_check_wp_east.py */
		if (Can_Pass(door_pass[0]))
		{
			wp[n++] = N12;
		}
		else if (Can_Pass(door_pass[1]))
		{
			wp[n++] = N8;
		}
		else if (Can_Pass(door_pass[2]))
		{
			wp[n++] = N3;
			if (p6_first) wp[n++] = N8;   /* 宝物=P6 逆时针时，这两个门节点都要保留 */
		}
		else
		{
			CarBrake_Stop();
			return;
		}

		/* 巡游：只写 P5~P8，顺时针/逆时针由顺序决定（其余 N 全部交给最短路） */
		if (p6_first)
		{
			/* 逆时针：P6 -> P8 -> P7 -> P5 */
			wp[n++] = P6;
			wp[n++] = P8;
			wp[n++] = P7;
			wp[n++] = P5;
		}
		else
		{
			/* 顺时针：P5 -> P7 -> P8 -> P6 */
			wp[n++] = P5;
			wp[n++] = P7;
			wp[n++] = P8;
			wp[n++] = P6;
		}

		/* 回程：只留"要过的那扇门"；⚠️ N8,N5 里的 N5 必须保留
		 * （删掉后规划器会改走 N8->N3 穿 D4 出西侧，实测路线会变） */
		if (door_pass[0] == CAN_PASS)
		{
			wp[n++] = N5;
		}
		else if (door_pass[0] == ONE_WAY_PASS && door_pass[3] == CAN_PASS)
		{
			wp[n++] = N10;               /* 原 N10,N3：N3 冗余 */
		}
		else if (door_pass[0] == ONE_WAY_PASS && door_pass[3] == NO_PASS && door_pass[2] == CAN_PASS)
		{
			wp[n++] = N8;                /* 原 N8,N3：N3 冗余 */
		}
		else if (door_pass[0] == ONE_WAY_PASS && door_pass[3] == NO_PASS && door_pass[2] == NO_PASS)
		{
			wp[n++] = N8;
			wp[n++] = N5;                /* ⚠️ 不可删 */
		}
		else if (door_pass[0] == NO_PASS && door_pass[1] == CAN_PASS)
		{
			wp[n++] = N8;
			wp[n++] = N5;                /* ⚠️ 不可删 */
		}
		else if (door_pass[0] == NO_PASS && door_pass[1] == ONE_WAY_PASS && door_pass[3] == CAN_PASS)
		{
			wp[n++] = N10;               /* 原 N10,N3：N3 冗余 */
		}
		else if (door_pass[0] == NO_PASS && door_pass[1] == ONE_WAY_PASS && door_pass[3] == NO_PASS)
		{
			wp[n++] = N8;                /* 原 N8,N3：N3 冗余 */
		}
		else if (door_pass[0] == NO_PASS && door_pass[1] == NO_PASS && door_pass[2] == CAN_PASS)
		{
			wp[n++] = N8;                /* 原 N8,N3：N3 冗余 */
		}
		else if (door_pass[0] == NO_PASS && door_pass[1] == NO_PASS && door_pass[2] == ONE_WAY_PASS)
		{
			wp[n++] = N10;               /* 原 N10,N3：N3 冗余 */
		}
		else
		{
			CarBrake_Stop();
			return;
		}

		wp[n++] = P2;
		(void)plan_route_at(0, wp, n);
		return;
	}
#endif

#if !USE_PLANNER_ROUTE
	/* USE_PLANNER_ROUTE=0 时的手工拼接路线（兜底）：数组都在本文件内，不依赖已删除的 rout_* */
	// 公共段：P1→P3→P4（到N5岔口）
	const u8 pre[]  = {B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N6,P4,N6,N5,0XFF};
	// 东区巡游：P5→P7→P8→P6
	const u8 tour[] = {N13,P5,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10,0XFF};
	// 宝藏=P6：先深入去P6，再P8→P7→P5绕回（终点改为N12，避开N11刀山）
	const u8 tour_p6[] = {N9,B9,N7,P6,N7,B8,N9,C3,N14,B10,C7,C8,B11,C4,N20,P8,N20,B6,N22,C9,P7,C9,N22,B7,C6,N19,B5,N18,N16,N12,N13,P5,N13,N12,0XFF};
	const u8 *use_tour = (treasure == 6) ? tour_p6 : tour;

	// 进东区路径选择（根据门状态和宝物位置）
	const u8 entry_D2_p6[]   = {N12,N11,N10,0XFF};
	const u8 entry_D2[]      = {N12,0XFF};
	const u8 entry_D3_p6[]   = {N8,N10,0XFF};
	const u8 entry_D3[]      = {N8,N12,0XFF};
	const u8 entry_far_p6[]  = {N4,N3,N8,N10,0XFF};
	const u8 entry_far[]     = {N4,N3,N8,N12,0XFF};
	const u8 *use_entry_D2  = (treasure == 6) ? entry_D2_p6  : entry_D2;
	const u8 *use_entry_D3  = (treasure == 6) ? entry_D3_p6  : entry_D3;
	const u8 *use_entry_far = (treasure == 6) ? entry_far_p6 : entry_far;

	// 出东区回家路径（根据门状态）
	const u8 tail_D2[] = {N5,N4,B3,N2,P2,0XFF};
	const u8 tail_D3[] = {N8,N5,N4,B3,N2,P2,0XFF};
	const u8 tail_D3_D5_blue[] = {N10,N3,N4,B3,N2,P2,0XFF};
	const u8 tail_far[] = {N3,N4,B3,N2,P2,0XFF};

	// 根据门状态组装完整路线
	if (door_pass[0] == CAN_PASS)
	{
		build_round2_route(pre, use_entry_D2, use_tour, tail_D2);
	}
	else if (door_pass[1] == CAN_PASS)
	{
		build_round2_route(pre, use_entry_D3, use_tour, tail_D3);
	}
	else if (door_pass[2] == CAN_PASS)
	{
		build_round2_route(pre, use_entry_far, use_tour, tail_far);
	}
	else if ((door_pass[0] == ONE_WAY_PASS || door_pass[1] == ONE_WAY_PASS) &&
		door_pass[3] == NO_PASS)
	{
		build_round2_route(pre, use_entry_D3, use_tour, tail_D3);
	}
	else if ((door_pass[0] == ONE_WAY_PASS || door_pass[1] == ONE_WAY_PASS) &&
		door_pass[3] == CAN_PASS)
	{
		build_round2_route(pre, use_entry_far, use_tour, tail_D3_D5_blue);
	}
	else if (door_pass[2] == ONE_WAY_PASS && door_pass[3] == CAN_PASS)
	{
		build_round2_route(pre, use_entry_far, use_tour, tail_D3_D5_blue);
	}
	else if (door_pass[2] == ONE_WAY_PASS && door_pass[3] == NO_PASS)
	{
		build_round2_route(pre, use_entry_far, use_tour, tail_far);
	}
	else
	{
		CarBrake_Stop();
	}
#endif /* !USE_PLANNER_ROUTE */
}
