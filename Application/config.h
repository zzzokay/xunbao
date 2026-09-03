#ifndef __CONFIG_H
#define __CONFIG_H

/* =====================================================================
 * 全局配置（集中管理）
 * 所有「开关」与「场地参数」都在这里改；其它文件只 #include "config.h"
 * 即可拿到这些宏。改完重新编译即可。
 * ===================================================================== */

 /* ===================== 调试开关 ===================== */
#define MAP_DEBUG      0   /* 1=打印地图调试信息 */
#define STEP_DEBUG     0   /* 1=按一下跑一个节点调试；正式比赛必须改回0 */
#define MAIN_DEBUG     0   /* 1=主任务跑调试分支(test_flag)，不会执行 Navigation()；正式比赛必须改回0 */
#define DEBUG          0   /* 1=门颜色走 debug_door_pass 预设(barrier.c)；0=走真实颜色传感器 */

/* ===================== 路线生成 ===================== */
#define USE_PLANNER_ROUTE  1   /* 1=由最短路径算法生成路线；0=沿用现有路线数组 */
#define SKIP_ROUND1        0   /* 1=跳过第一轮直接进第二轮（调试用） */

/* ===================== 地图起始/目标 & 按键合并窗口 ===================== */
/* 调试（MAP_DEBUG=1）时，只需改这两个节点名：程序用最短路径算法自动生成 起始点->目标点 的路线 */
#define FIRST_POINT   N10    /* 调试起始点（MapNode 枚举名） */
#define END_POINT     N9     /* 调试目标点（最优路径终点；不用再手写路线 / 不用 SECOND_POINT） */
#define NAV_TOKEN_WINDOW_MS  2000   /* 按键连按合并窗口(ms)：窗口内按几次=几张票 */


/* ===================== 场地选择 =====================
 * FIELD_COMP   = 比赛场地（当前默认数据，与原先完全一致）
 * FIELD_SCHOOL = 学校场地（实测值填入下方对应块的 TODO）
 * 切换场地：只改 USE_FIELD 这一行，重新编译即可。
 */
#define FIELD_COMP     0
#define FIELD_SCHOOL   1
#define USE_FIELD      FIELD_SCHOOL   /* <=== 切换场地改这一行 */

/* ===== 楼梯/山区段长度（单位 cm，按"起点→目标"方向命名）=====
 * 派生约束（两套共用，块外自动算）：
 *   B5N19 与 B7C6 长度相同；N18B5 比 N22B7 短 20 */
#if USE_FIELD == FIELD_SCHOOL
    /* —— 学校场地实测值（TODO: 填入实测数字）—— */
    #define LEN_N22B7   200   /* TODO(学校) */
    #define LEN_B5N19   72    /* TODO(学校) */
#else
    /* —— 比赛场地（现状）—— */
    #define LEN_N22B7   200
    #define LEN_B5N19   72
#endif
//#define LEN_N18B5   (LEN_N22B7 - 20)      /* N18B5 = 180 */
#define LEN_N18B5   100     /* N18B5 = 180 */
#define LEN_B7C6    LEN_B5N19             /* B7C6 = B5N19 = 72 */

/* ===== 红绿灯门区段：全长（door_set_pass_node 用全长；map_message 中 DOOR 条目用 全长/2）===== */
#if USE_FIELD == FIELD_SCHOOL
    /* —— 学校场地实测值（TODO）—— */
    #define DOOR_LEN_N5N12  180   /* TODO(学校) */
    #define DOOR_LEN_N5N8   190   /* TODO(学校) */
    #define DOOR_LEN_N8N10  190   /* TODO(学校) */
    #define DOOR_LEN_N3N10  180   /* TODO(学校) */
    #define DOOR_LEN_N3N8   190   /* TODO(学校) */
    #define DOOR_LEN_N8N12  190   /* TODO(学校) */
#else
    /* —— 比赛场地（现状）—— */
    #define DOOR_LEN_N5N12  220
    #define DOOR_LEN_N5N8   200
    #define DOOR_LEN_N8N10  200
    #define DOOR_LEN_N3N10  220
    #define DOOR_LEN_N3N8   200
    #define DOOR_LEN_N8N12  200
#endif

/* ===== door_retreat 后退距离（与路段全长无关，按”起点→目标”方向命名）===== */
#if USE_FIELD == FIELD_SCHOOL
    /* —— 学校场地实测值（TODO）—— */
    #define DOOR_RETREAT_N5N8   67   /* TODO(学校) */
    #define DOOR_RETREAT_N5N4   67   /* TODO(学校) */
    #define DOOR_RETREAT_N10N8  90  /* TODO(学校) */
    #define DOOR_RETREAT_N8N5   65   /* TODO(学校) */
#else
    /* —— 比赛场地（现状）—— */
    #define DOOR_RETREAT_N5N8   85
    #define DOOR_RETREAT_N5N4   85
    #define DOOR_RETREAT_N10N8  100
    #define DOOR_RETREAT_N8N5   75
#endif

/* ===== 门区段角度基准量（与 DOOR_LEN_* 同名段，按”起点→目标”命名，范围 -180~+180）
 * 正向基准：N3→N8 / N5→N8；门两侧平行，N8→N12=N3N8、N8→N10=N5N8
 * 反向：加 180 或减 180，结果保持在 [-180, 180]  ===== */
#if USE_FIELD == FIELD_SCHOOL
    /* —— 学校场地实测值（TODO）—— */
    #define ANGLE_N3N8   145   /* TODO(学校) */
    #define ANGLE_N5N8   35    /* TODO(学校) */
#else
    /* —— 比赛场地（现状）—— */
    #define ANGLE_N3N8   145
    #define ANGLE_N5N8   35
#endif
/* 派生（两套共用，块外自动算） */
#define ANGLE_N8N12  ANGLE_N3N8
#define ANGLE_N8N10  ANGLE_N5N8

#define ANGLE_REV(a)  (((a) >= 0) ? ((a) - 180) : ((a) + 180))
#define ANGLE_N8N3   ANGLE_REV(ANGLE_N3N8)   /* = -35 */
#define ANGLE_N8N5   ANGLE_REV(ANGLE_N5N8)   /* = -145 */
#define ANGLE_N12N8  ANGLE_REV(ANGLE_N8N12)  /* = -35 */
#define ANGLE_N10N8  ANGLE_REV(ANGLE_N8N10)  /* = -145 */


/* ===================== 底盘长度标定 =====================
 * LEN_SCALE = 每 1 个"代码长度单位"对应的厘米数。
 * 实测：车走 100 代码单位 ≈ 120cm  → LEN_SCALE = 120/100 = 1.2。
 * 各处距离阈值已按 cm=round(代码单位×LEN_SCALE) 内联为整数厘米，只有
 * motor_task.c 的里程公式(运行时连续累加)才用本宏做比例补偿。
 * 重新标定：改这里 + 重算各处内联值(见 project_reference.md §7.4)。
 */
#define LEN_SCALE  1.2f

#endif /* __CONFIG_H */
