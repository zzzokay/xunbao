#ifndef __CONFIG_H
#define __CONFIG_H

/* =====================================================================
 * 全局配置（集中管理）
 * 所有「开关」与「场地参数」都在这里改；其它文件只 #include "config.h"
 * 即可拿到这些宏。改完重新编译即可。
 * ===================================================================== */

 /* ===================== 调试开关 ===================== */
#define MAP_DEBUG      0        
#define STEP_DEBUG     0
#define MAIN_DEBUG     0
#define DEBUG          0        //摄像头

/* ===================== 转弯前补偿距离"能算就算" =====================
 * 1 = 距离由Δ = 19*(1-cosφ) + d(判据) 算出，而不是吃默认值 19；    
 *     但若该三元组已有实测值且公式与它相差 >5cm，则仍用实测值（5cm 闸门，自保护）。
 * 0 = 完全保持原行为（只用实测表 + 默认值）。*/
#define TURN_CALC_ENABLE   0


/* ===================== 直立景点巡回 S1/S2（View1 通道）=====================
 * 1 = 一轮【取宝之后】的回家腿顺路绕近的那个景点（宝物 P3->S1、P4->S2）；
 *     二轮去 P3/P4 时固定两个都绕。
 * 0 = 完全不进 S1/S2*/
#define UPRIGHT_TOUR_ENABLE  0

/* ===================== 路线生成 ===================== */
#define USE_PLANNER_ROUTE  1
#define SKIP_ROUND1        0

/* ===================== 地图起始/目标 & 按键合并窗口 ===================== */
/* 调试（MAP_DEBUG=1）时，只需改这三个节点名：程序用最短路径算法自动生成 起始点->[途径点]->目标点 的路线 */
#define FIRST_POINT   P4
#define VIA_POINT     P3     /* 调试途径点（MapNode 枚举名）；填 0 = 不用途径点（退化成两点路线）。
                               注意 S1=0，故 S1 不能当途径点；要途经 S1 请改用别的调试方式 */
#define END_POINT     P4
#define NAV_TOKEN_WINDOW_MS  2000


/* ===================== 场地选择 =====================
 * FIELD_COMP   = 比赛场地（当前默认数据，与原先完全一致）
 * FIELD_SCHOOL = 学校场地（实测值填入下方对应块的 TODO）
 * 切换场地：只改 USE_FIELD 这一行，重新编译即可。
 */
#define FIELD_COMP     0
#define FIELD_SCHOOL   1
#ifndef USE_FIELD
#define USE_FIELD      FIELD_SCHOOL
#endif

/* ===== 楼梯/山区段长度（单位 cm，按"起点→目标"方向命名）=====
 * 双向同长：B5—N19、B5—N18、B7—C6、B7—N22 这 4 段楼梯/山地，两个方向共用同一宏（取物理真实长度，即两向中较大的那个）。
 * map_message.c 的正反向边都用下面的宏，避免同段两个方向长度不一致。
 * 派生约束（两套共用，块外自动算）：B7C6 = B5N19 + 20；N18B5 = N22B7 - 20 */
#if USE_FIELD == FIELD_SCHOOL
    /* —— 学校场地实测值（TODO: 填入实测数字）—— */
    #define LEN_N22B7   90
    #define LEN_B5N19   150
#else
    /* —— 比赛场地（现状）—— */
    #define LEN_N22B7   200
    #define LEN_B5N19   72
#endif
#define LEN_N18B5   (LEN_N22B7 - 20)
//#define LEN_N18B5   100     /* N18B5 = 180 */
#define LEN_B7C6    LEN_B5N19 + 20

/* ===== 红绿灯门区段：全长（door_set_pass_node 用全长；map_message 中 DOOR 条目用 全长/2）===== */
#if USE_FIELD == FIELD_SCHOOL
    /* —— 学校场地实测值（TODO）—— */
    #define DOOR_LEN_N5N12  170
    #define DOOR_LEN_N5N8   170
    #define DOOR_LEN_N8N10  170
    #define DOOR_LEN_N3N10  170
    #define DOOR_LEN_N3N8   170
    #define DOOR_LEN_N8N12  170
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
    #define DOOR_RETREAT_N5N8   63
    #define DOOR_RETREAT_N5N4   67
    #define DOOR_RETREAT_N10N8  90
    #define DOOR_RETREAT_N8N5   65
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
    #define ANGLE_N3N8   145
    #define ANGLE_N5N8   35
#else
    /* —— 比赛场地（现状）—— */
    #define ANGLE_N3N8   145
    #define ANGLE_N5N8   35
#endif
/* 派生（两套共用，块外自动算） */
#define ANGLE_N8N12  ANGLE_N3N8
#define ANGLE_N8N10  ANGLE_N5N8

#define ANGLE_REV(a)  (((a) >= 0) ? ((a) - 180) : ((a) + 180))
#define ANGLE_N8N3   ANGLE_REV(ANGLE_N3N8)
#define ANGLE_N8N5   ANGLE_REV(ANGLE_N5N8)
#define ANGLE_N12N8  ANGLE_REV(ANGLE_N8N12)
#define ANGLE_N10N8  ANGLE_REV(ANGLE_N8N10)

/* ===== OCR 读数字：摄像头（舵机0）左右摆角 =====
 * 1500 = 正中；数值越大越往左（Rudder_control.c 的 HEAD_LEFT=2250 / HEAD_RIGHT=770）。
 * WaitFor_OCR() 每轮按「右 → 左 → 中」三档扫描，摆角分两组：
 *   FAR  = 车在基准位（还没前进）
 *   NEAR = 已前进 4cm 靠近号码板之后（近处同一横向偏差对应更大偏角） */
#define OCR_HEAD_MID         1500
#define OCR_HEAD_FAR_RIGHT   1350
#define OCR_HEAD_FAR_LEFT    1650
#define OCR_HEAD_NEAR_RIGHT  1300
#define OCR_HEAD_NEAR_LEFT   1700


/* ===================== 底盘长度标定 =====================
 * LEN_SCALE = 每 1 个"代码长度单位"对应的厘米数。
 * 实测：车走 100 代码单位 ≈ 120cm  → LEN_SCALE = 120/100 = 1.2。
 */
#define LEN_SCALE  1.2f

#endif /* __CONFIG_H */
