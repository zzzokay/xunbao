#ifndef __MISSION_PLANNER_H
#define __MISSION_PLANNER_H

#include "sys.h"

/*
 * 任务规划器 - Mission Planner
 *
 * 职责：根据比赛规则（QR码、门颜色、宝物位置）动态决定路线
 *
 * 调用关系：
 *   barrier.c (Stage/door等) → mission_planner (update_route_*) → nav_planner (最短路)
 *
 * 核心函数：
 *   - update_route_at_P1()：QR码读取后根据百位数决定先去P3还是P4
 *   - update_route_by_door_*()：根据门颜色组合决定回程路线
 *   - update_route_at_door_for_stageAB()：门后根据平台线索决定A/B平台路线
 *   - update_route_at_P7/P8_for_treasure()：根据宝物位置规划回程
 *   - get_newroute()：第二轮完整路线规划
 */

/* ==================== 第一轮路线更新（QR码分流） ==================== */

/**
 * @brief QR码读取后根据百位数更新路线
 *
 * 规则：
 *   - flag_line_clue == 3 → 先去 P3
 *   - flag_line_clue == 4 → 先去 P4
 *   - flag_line_clue == 0 → 跳过 P3/P4，直接去门区
 */
void update_route_at_P1(void);

/* ==================== 门后路线更新（根据门颜色组合） ==================== */

/**
 * @brief D2/D3/D4/D5读取后的回程路线更新
 *
 * 根据 treasure（宝物平台编号）和门的颜色组合决定回程路线：
 *   - treasure = 2 → 回 P1
 *   - treasure = 3 → 回 P3
 *   - treasure = 4 → 回 P4
 *   - treasure = 5/6 → 回 P5/P6（远端平台）
 *
 * 各函数对应不同的门状态：
 *   - update_route_by_door_1()：D2关，D3关 → 从D4回
 *   - update_route_by_door_2()：D2开，D3开 → 从D5回（黑灯后重读D4）
 *   - update_route_by_door_3()：D2关，D3开 → 从D4回
 *   - update_route_by_door_4()：D2开，D3关 → 从D5回
 */
void update_route_by_door_1(void);
void update_route_by_door_2(void);
void update_route_by_door_3(void);
void update_route_by_door_4(void);

/* ==================== 门后平台路线（根据线索） ==================== */

/**
 * @brief 门后根据平台线索更新A/B平台路线
 *
 * 规则：
 *   - flag_clue_stage_A + flag_clue_stage_B → 决定去哪两个平台
 *   - 5 → P5，6 → P6，7 → P7，8 → P8
 *   - 例：5+7 → P5和P7
 */
void update_route_at_door_for_stageAB(void);

/* ==================== 宝物回程路线 ==================== */

/**
 * @brief P7/P8发现宝物后的回程路线
 *
 * 根据当前位置和门的通行状态规划回家路线
 */
void update_route_at_P7_for_treasure(void);
void update_route_at_P8_for_treasure(void);

/* ==================== 第二轮路线规划 ==================== */

/**
 * @brief 第二轮完整路线规划
 *
 * 策略：
 *   - 重新初始化地图
 *   - 清除所有门限制（Clear_door）
 *   - 按顺序巡游所有未访问的平台
 *   - 使用规划器生成最优路线（USE_PLANNER_ROUTE=1时）
 */
void get_newroute(void);

/**
 * @brief 清除所有门的通行限制（第二轮用）
 *
 * 将所有门区段恢复为正常通行（无DOOR功能，高速通过）
 */
void Clear_door(void);

/* ==================== 工具函数（供 barrier.c 使用） ==================== */

/**
 * @brief 加载预定义路线到 route[]
 * @param offset route[] 起始偏移
 * @param src 源路线数组（以 0xFF 结尾）
 */
void load_route_at(uint8_t offset, const u8* src);

#endif
