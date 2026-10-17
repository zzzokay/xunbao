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


/* ===================== 直立景点（View，N14/N16）触发条件 =====================
 * 1 = 只有"已经拿到宝藏"之后才做直立景点动作（一轮取宝后的回程 + 第二轮）；
 *     一轮去程（还没取宝）经过 N12->N16 / C3->N14 时不做动作，当普通节点直穿。
 * 0 = 恢复旧行为（边表 func=View 就做，含一轮去程）。
 * 依据：一轮去程 N5->N12->N13->P5->N13->N12->N16 会在取宝前经过 N16。
 * 落点与验证见 project_reference.md §11 / README.md §2.14 */
#define UPRIGHT_NEED_TREASURE  1

/* ===================== 直立景点巡回 S1/S2（View1 通道）=====================
 * 1 = 一轮【取宝之后】的回家腿绕"这次会去的 P3/P4"对应的景点：
 *       会去 P3 -> 绕 S1；会去 P4 -> 绕 S2
 *     ⇒ 2026-10-07 起判据**跟着 P3/P4 走**（不再要求"宝物就在 P3/P4"）：
 *       补打卡 P3P4_PUNCH_ENABLE 开着时两个景点都绕；关掉补打卡则自动退回旧行为
 *       （宝物 P3->S1、宝物 P4->S2）。
 *     二轮去 P3/P4 时固定两个都绕。
 * 0 = 完全不进 S1/S2*/
#define UPRIGHT_TOUR_ENABLE  1
/* ===================== 二轮 S1 单独开关（2026-10-17） =====================
 * 1 = 二轮照旧绕 S1（N3 支路）；0 = 二轮不绕 S1（S2 与一轮不受影响）
 * 与 UPRIGHT_TOUR_ENABLE 相乘生效（后者 =0 时二轮本来就不绕）。
 * 上位机镜像：map_model.round2_waypoints(s1=...)；tools/sim_* 自检读本宏。 */
#define ROUND2_S1_ENABLE  0

/* ===================== 一轮回程补打卡 P3/P4 =====================
 * 1 = 一轮【取宝之后】的回家腿，把去程没去的 P3/P4 补上再回家（**缺哪个补哪个**）：
 *     QR 百位=3（去过 P3）只补 P4、=4（去过 P4）只补 P3、
 *     =0（正常固件默认，一轮去程根本不经过 P3/P4）两个都补；
 *     宝物平台正好是它时不重复加（回程本来就要去那儿打卡）。
 *     顺序：与 S1/S2 交错成 **P3 -> S1 -> P4 -> S2**（都在宝物平台之后、P2 之前，
 *           与二轮 get_newroute() 同序）。落点在 mission_planner.c 的共享小函数
 *           append_round1_return_tail()，两个回程函数各调一次。
 * 0 = 完全保持原行为（回程只去宝物平台）。
 * ⚠️ 打开会改掉门回程路线 ⇒ 真实固件走法不再等于 validate/_check_door_perm.py 的 12 条
 *     golden（那条脚本只验"边禁用 + 极简 wp"机制、恒 12/12，看不出本开关）。
 * ⚠️ 改完跑 地图修改上位机/tools/sim_route_bookkeeping.py（自带源码同步自检）。 */
#define P3P4_PUNCH_ENABLE  1

/* ===================== 路线生成 ===================== */
#define USE_PLANNER_ROUTE  1
#define SKIP_ROUND1        1

/* ===================== 第二轮东区巡游顺序（P5~P8 各一次，顺序 = 走法）=====================
 * 巡游顺序由**实际摆放**决定，不一定是默认的「P5→P7→P8→P6」。
 *   CW  组 = 宝物 != 6 时走（默认情况）
 *   CCW 组 = 宝物 == 6 时走
 * 想让车永远按同一条顺序走 ⇒ 把两组填成一样即可（就与宝物值无关了）。
 * 值为 NavEdgeTbl 里的平台节点名（P5/P6/P7/P8），每组 4 个、各出现一次。
 * ⚠️ get_newroute() 用运行期 if 读取，**别改成 #if**（宏名写错会静默当 0，见 README §2.14）；
 *    仅 USE_PLANNER_ROUTE=1 生效。上位机「二轮路线…」可读写这一段。
 * ⚠️ 改完跑 地图修改上位机/tools/trace_rounds.py（仿真手抄镜像会自检源码同步） */
#define ROUND2_CRUISE_CW_1   P5
#define ROUND2_CRUISE_CW_2   P7
#define ROUND2_CRUISE_CW_3   P6
#define ROUND2_CRUISE_CW_4   P8
#define ROUND2_CRUISE_CCW_1  P6
#define ROUND2_CRUISE_CCW_2  P7
#define ROUND2_CRUISE_CCW_3  P5
#define ROUND2_CRUISE_CCW_4  P8

/* ===================== 比赛时间预算（出门分级贪分，2026-10-11） =====================
 * 出门 = 回程到达 N3/N5（route_return_home 重规划时刻）；计时起点 = zhunbei()
 * 两个红外 while 退出（一/二轮各调一次 → 各自 180s）。出门时已用时：
 *   < 2:25 全跑（含 S1/S2）；≥ 2:25 不跑 S1/S2；≥ 2:35 只跑一个平台；≥ 2:40 直接回家
 * 口径：用户原话 2:15 前全跑，2:15~2:25 为缓冲带维持全跑；要提前收景点把
 *   TB_NO_SIGHTS_AT_S 改 135。门控细节见 mission_planner.c 的 round1_tail_tier()。 */
#define TIME_BUDGET_ENABLE   0  /* 总开关：0=完全关闭时间预算（不定档/不计时/不重排），尾段恒为全量 */
#define TB_NO_SIGHTS_AT_S   135  /* 2:15 起不跑 S1/S2 */
#define TB_ONE_PLAT_AT_S    145  /* 2:25 起只跑一个平台 */
#define TB_HOME_ONLY_AT_S   155  /* 2:35 起直接回家 */
#define TB_P1_NO_SIGHTS_AT_S  125  /* 宝物在 P1：2:05 起不跑 S1/S2（比通用 145 提前 10s） */
#define TB_P1_HOME_ONLY_AT_S  135  /* 宝物在 P1：2:15 起直接回家 */

/* ---- 硬截止：到点强制回家（2026-10-16）----
 * 1 = 只要「已用时 ≥ TB_GO_HOME_AT_S」，无论当前节点在哪、正在做什么，剩下的路线立刻压成
 *     [当前节点, P2]：放弃补打卡 P3/P4、放弃景点 S1/S2，必要时连宝物平台也不去。
 *     只在「车已出门（门区 8 条边全禁也能到 P2）」时接管；车还在门东侧时不接管 —— 穿门回家
 *     得靠 door() 状态机（读灯/退回/重读），临时另写一条穿门路线风险更大，而车本来也正朝门走，
 *     出门那一刻 round1_exit_recheck() 会接管（它已有自己的「直接回家」档）。
 * 0 = 完全关闭（默认）：行为与加这段之前一字不差。
 * ⚠️ 与 TIME_BUDGET_ENABLE 独立：那个管「出门分级裁景点」，这个管「硬截止回家」；
 *    两个开关**任一为 1** 都会启动比赛计时器（mission_planner.c 的 Match_Timer_Start）。
 * ⚠️ 一轮二轮都管（二轮计时器由 get_newroute 重置）；要只留一轮，在
 *    round_force_home_check() 里加一句 `if (map.routetime != 0) return;`。 */
#define TB_FORCE_HOME_ENABLE   0     /* 总开关：默认 0（不影响原有逻辑） */
#define TB_GO_HOME_AT_S        165   /* 2:45 起（剩 15s）强制回家 */

/* ===================== 地图起始/目标 & 按键合并窗口 ===================== */
/* 调试（MAP_DEBUG=1）时，只需改这三个节点名：程序用最短路径算法自动生成 起始点->[途径点]->目标点 的路线 */
#define FIRST_POINT   C3
#define VIA_POINT     0     /* 调试途径点（MapNode 枚举名）；填 0 = 不用途径点（退化成两点路线）。
                               注意 S1=0，故 S1 不能当途径点；要途经 S1 请改用别的调试方式 */
#define END_POINT     P8
#define NAV_TOKEN_WINDOW_MS  2000


/* ===================== 场地选择 =====================
 * FIELD_COMP   = 比赛场地（当前默认数据，与原先完全一致）
 * FIELD_SCHOOL = 学校场地（实测值填入下方对应块的 TODO）
 * 切换场地：只改 USE_FIELD_ 这一行，重新编译即可。
 */
#define FIELD_COMP     1
#define FIELD_SCHOOL   0

#ifndef USE_FIELD_
#define USE_FIELD_      FIELD_COMP
#endif

/* ===== 楼梯/山区段长度（单位 cm，按"起点→目标"方向命名）=====
 * 双向同长：B5—N19、B5—N18、B7—C6、B7—N22 这 4 段楼梯/山地，两个方向共用同一宏（取物理真实长度，即两向中较大的那个）。
 * map_message.c 的正反向边都用下面的宏，避免同段两个方向长度不一致。
 * 派生约束（两套共用，块外自动算）：B7C6 = B5N19 + 20；N18B5 = N22B7 - 50 */
#if USE_FIELD_ == FIELD_SCHOOL
    /* —— 学校场地实测值（TODO: 填入实测数字）—— */
    #define LEN_N22B7   100
    #define LEN_B5N19   150
#else
    /* —— 比赛场地（现状）—— */
    #define LEN_N22B7   180
    #define LEN_B5N19   60
#endif
#define LEN_N18B5   (LEN_N22B7 - 50)
//#define LEN_N18B5   100     /* N18B5 = 180 */
#define LEN_B7C6    LEN_B5N19 + 20

/* ===== 红绿灯门区段：全长（door_set_pass_node 用全长；map_message 中 DOOR 条目用 全长/2）===== */
#if USE_FIELD_ == FIELD_SCHOOL
    /* —— 学校场地实测值（TODO）—— */
    #define DOOR_LEN_N5N12  170
    #define DOOR_LEN_N5N8   170
    #define DOOR_LEN_N8N10  170
    #define DOOR_LEN_N3N10  170
#define DOOR_LEN_N20N3  170   /* D5 过门（回程 N20→N3）；先抄 N3N10，待标定 */
    #define DOOR_LEN_N3N8   170
    #define DOOR_LEN_N8N12  170
#else
    /* —— 比赛场地（现状）—— */
    #define DOOR_LEN_N5N12  220
    #define DOOR_LEN_N5N8   200
    #define DOOR_LEN_N8N10  200
    #define DOOR_LEN_N3N10  220
#define DOOR_LEN_N20N3  90   /* D5 过门（回程 N20→N3）；先抄 N3N10，待标定 */
    #define DOOR_LEN_N3N8   200
    #define DOOR_LEN_N8N12  200
#endif

/* ===== door_retreat 后退距离（与路段全长无关，按”起点→目标”方向命名）===== */
#if USE_FIELD_ == FIELD_SCHOOL
    /* —— 学校场地实测值（TODO）—— */
    #define DOOR_RETREAT_N5N8   60
    #define DOOR_RETREAT_N5N4   60
    #define DOOR_RETREAT_N10N8  83
#define DOOR_RETREAT_N20N8  83   /* D5 读灯失败退回 N20→N8；先抄 N10N8，待标定 */
    #define DOOR_RETREAT_N8N5   60
#else
    /* —— 比赛场地（现状）—— */
    #define DOOR_RETREAT_N5N8   72
    #define DOOR_RETREAT_N5N4   68
    #define DOOR_RETREAT_N10N8  100
#define DOOR_RETREAT_N20N8  100  /* D5 读灯失败退回 N20→N8；先抄 N10N8，待标定 */
    #define DOOR_RETREAT_N8N5   78
#endif

/* ===== 门区段角度基准量（与 DOOR_LEN_* 同名段，按”起点→目标”命名，范围 -180~+180）
 * 正向基准：N3→N8 / N5→N8；门两侧平行，N8→N12=N3N8、N8→N10=N5N8
 * 反向：加 180 或减 180，结果保持在 [-180, 180]  ===== */
#if USE_FIELD_ == FIELD_SCHOOL
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
 * 2026-10-11 晚 已接上（第一眼直视 + 全程不关相机）：WaitFor_OCR() 开一次 OCR 模式后全程保持
 *   （每0.48s重发指令保活），六轮摆位 = 中扫2.4s(第一眼直视) → 右20° → 左20° → [前进4cm靠近]
 *   → 右25° → 中 → 左25°；慢转 SWEEP_MS(2.5s) 期间相机持续在扫、扫到立即退出，
 *   到位后保底扫 SETTLE_MS(0.5s)。任一轮扫到立即非阻塞回中退出（近距轮扫到再倒回4cm复位车位）；
 *   全失败才回中+后退7cm 并 close_Maxicam。
 * 角度换算参照门区转头标定：HEAD 1500±750 单位 ≈ ±100° ⇒ ≈7.5 单位/°（20°=150、25°≈188 单位）。
 * FAR = 车在基准位（还没前进，±20°）；NEAR = 已前进 4cm 靠近号码板之后（±25°）。
 * 均在舵机行程（770~2250）内。 */
#define OCR_HEAD_MID         1500
#define OCR_HEAD_FAR_RIGHT   1350   /* 基准位右转约20° */
#define OCR_HEAD_FAR_LEFT    1650   /* 基准位左转约20° */
#define OCR_HEAD_NEAR_RIGHT  1310   /* 靠近后右转约25° */
#define OCR_HEAD_NEAR_LEFT   1690   /* 靠近后左转约25° */
#define OCR_HEAD_SWEEP_MS    2500   /* 缓慢转头：舵机运动时长(ms)，转动中相机持续在扫 */
#define OCR_HEAD_SETTLE_MS    500   /* 到位后保底扫时长(ms) */

#define QQB_LENGTH  48   //48


/* ===================== 底盘长度标定 =====================
 * LEN_SCALE = 每 1 个"代码长度单位"对应的厘米数。
 * 实测：车走 100 代码单位 ≈ 120cm  → LEN_SCALE = 120/100 = 1.2。
 */
#define LEN_SCALE  1.2f

#endif /* __CONFIG_H */
