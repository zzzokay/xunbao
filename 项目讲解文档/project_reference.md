# 项目参考文档 — xunbao（寻宝）

> **MCU**: STM32F750V8Tx | **工具链**: MDK-ARM **V5.32**（必须 V5，V6 会编译报错）| **RTOS**: FreeRTOS + CMSIS_V1 | **主频**: 216MHz
>
> **📌 读者对象**：**主要给 AI / 工具看**（每次空白上下文要先读它，就知道"去哪儿改、怎么操作、怎么 git 暂存、怎么写文档"）。**人（接任者）请读《[交接专用文档（新人先看我）](交接专用文档（新人先看我）.md)》**。
> **用途**：读完即可了解项目现状、知道去哪儿改、怎么操作、怎么安全提交。**改了什么的历史**见 [README.md](README.md) 的修改日志。本文档只保留**最终版本现状**（结构、数据流、到底层映射、配置、改图方法、已知坑、工作流），不追溯过程。

---

## 1. 项目一句话介绍

四轮直流编码电机小车，走"寻宝"赛项：
**上电 → 二维码平台(P1) → 门区(红绿灯/通行牌) → A/B 平台采线索 → 宝物平台 → 回家；第二轮按第一轮线索优化路线**。

硬件：16 路循迹板 + 陀螺仪(IMU) + 灰度传感器 + 视觉(Maxicam/K210)。走线靠"循迹为主 + 陀螺仪辅助"，障碍物上会额外用灰度/视觉。控制是"上层导航驱动 Chassis API → 底层 motor_task 闭环"的分层结构。

---

## 2. 完整目录结构（当前）

```
Mission/                    # 任务层 — 比赛业务逻辑（决定"去哪"）
  ├── mission_planner.c/h   # 路线决策（QR/门/宝物改路、get_newroute、Clear_door、load_route_at）
  ├── barrier.c/h           # 障碍执行 + 门（Stage/Bridge/Hill/南 & 跷跷板/波动板；door()/Door_ReadPass/door_set_pass_node/door_retreat）
  └── config.h              # 全局配置（所有开关/场地参数唯一入口）

Navigation/                 # 导航层 — 路径规划与执行（决定"怎么去"）
  ├── nav_planner.c/h       # 最短路算法（nav_init/nav_shortest_path/nav_plan_waypoints/nav_build_route/nav_find_edge）
  ├── map.c/h               # 导航执行（Navigation()/map_function()/getNextConnectNode/mapInit()/route[]/nav_planner_setup）
  └── map_message.c/h       # 地图数据（NavEdgeTbl[] 唯一人工编辑源；执行层 CSR 与规划层线路图都由 nav_init() 统一构建；NAV_EDGE_COUNT）

Application/                # 控制层 — 底盘控制与传感器（决定"怎么动"）
  ├── chassis_api.c/h       # 底盘API中间件（核心解耦层；Chassis_* 全部入口）
  ├── scaner.c/h            # 16路巡线（Scaner_Update/Go_Line/Get_scaner_error/line_data[5]/line_weight_default[16]）
  ├── turn.c/h              # 转弯（Turn_Angle_Base/Turn_Angle/Stage_turn_Angle/Turn360Step/Go_Angle/need2turn）
  ├── gray.c/h              # 灰度传感器
  ├── IIC.c/h               # 软件I2C
  ├── motion.c/h            # 运动控制
  ├── command.c/h           # 调试串口缓冲区
  ├── delay.c/h             # 延时
  └── sys.h                 # 系统类型定义(u8/u16 等)

Core/                       # STM32 HAL 核心
Math/                       # 算法库 — pid.c/h（增量内环+位置外环）、filter.c/h、sin_generate.c/h
Module/                     # 外设驱动 — imu.c/h、K210.c/h、QR.c/h、openmv.c/h、Rec_usart.c/h、Rudder_control、bsp_buzzer、bsp_led、bsp_linefollower、keys、interrupt_router、usart2_compat（ADC 走 CubeMX 的 Core/Src/adc.c；原 Module/adc.{c,h} 已删，见 §12.4 同名头文件说明）
Motor/                      # 电机驱动层 — motor.c/h、Encoder.c/h、speed_ctrl
Task/                       # FreeRTOS 任务 — main_task、motor_task、ArriveDetect_task、temporary_task、task_create
USMAT/                      # USMART 串口调试组件
MDK-ARM/                    # Keil 工程（test1.uvprojx）
test1.ioc                   # CubeMX 配置
```

> **口诀**：`Mission 决定"去哪"`（QR/门/宝物）→ `Navigation 决定"怎么去"`（最短路）→ `Application 决定"怎么动"`（PID/电机）。

---

## 3. 分层数据流（含"到底层"的完整映射）

```
┌───────────────────────── 上层：任务/导航 ─────────────────────────┐
│ Mission/mission_planner.c  决定 route[]  ←─ QR/门/宝物线索        │
│ Navigation/map.c:Navigation() 逐条执行 route[]（main_task 3ms）     │
└───────────────┬──────────────────────────────────────────────────┘
                │ 叫 Chassis_SetMode() / Chassis_SetTargetSpeed()
                ▼
┌──────────────────────── 中层：底盘解耦 (Application) ─────────────┐
│ Application/chassis_api.c：Chassis_MotorControl(mode,L,R,aim)     │
│   拿到"目标模式+左右速"，不碰 PID 细节 → 只写 motor_all.L/Rspeed    │
└───────────────┬──────────────────────────────────────────────────┘
                ▼
┌──────────────────────── 底层：电机任务 (Task) ────────────────────┐
│ Task/motor_task.c（每 5ms，最高优先级 6）                          │
│   读编码器 → 按 PIDMode 分发 →                                      │
│     is_Line → scaner.c:Go_Line()  （外环位置式巡线）                │
│     is_Turn → turn.c:Turn_Angle_Base()（陀螺仪转弯 PID）           │
│     is_Gyro → turn.c:Go_Angle()     （陀螺仪直行 PID）             │
│   → 外环输出 Fspeed → 设 motor_all.Lspeed/Rspeed                   │
│   → handle_target_speed() → 写 motor_L0/L1/R0/R1.target            │
│   → Math/pid.c:incremental_PID()（内环速度 PID）→ motor_set_pwm()  │
└───────────────┬──────────────────────────────────────────────────┘
                ▼
┌──────────────────────── 硬件层 (Motor) ───────────────────────────┐
│ Motor/motor.c:motor_set_pwm(i,PWM) → TIMx->CCRy = PWM             │
│   TIM4/8/9 → 电机驱动 → 4 个直流编码电机 → 轮子                     │
│   ← TIM1/2/3/5 编码器反馈 → 回 motor_task 闭环                     │
└──────────────────────────────────────────────────────────────────┘
```

**数据三处核心**：`route[]`（路线，map.c 起点）、`nodes`（lastNode/nowNode/nextNode，map.c）、`motor_all`（速度/里程，chassis_api.c）。

**障碍/门/宝物时**：`map_function()` 分发到 `barrier.c` 的 `Stage()/Bridge()/Hill()/door()` 等物理动作；做完后由 `mission_planner.()` 改写 `route[]`。**门回程(`update_route_by_door_*`)走手写穷举路线**（从当前内侧节点直接写回家/目标，不穿门掉头）；**出门点→平台等其它段**（`USE_PLANNER_ROUTE=1` 时）才走 `nav_build_route` 最短路。

---

## 4. 底层映射：电机 / 编码器 / PWM / IO（改硬件或排查时看）

### 4.1 电机与编码器
| 通道 | 角色 | PWM 定时器/引脚 | 编码器 | 方向逻辑 |
|------|------|----------------|--------|----------|
| motor_set_pwm(1) | L0 左前 | TIM9 PE5/PE6 | TIM1（正） | 正转: CCRx=0, CCRy=ccr；反转: CCRx=ccr, CCRy=0 |
| motor_set_pwm(2) | L1 左后 | TIM8 PC8/PC9 | TIM2（正） | 同上 |
| motor_set_pwm(3) | R0 右前 | TIM4 PD14/PD15 | TIM3（取反） | 同上 |
| motor_set_pwm(4) | R1 右后 | TIM4 PD12/PD13 | TIM5（取反） | 同上 |

- 编码器每圈 **5720** 脉冲，减速比 **0.362**，轮径 **104mm**；`ARR=65535`。
- ⚠️ 要反转电机方向：**交换 TIM 两通道极性 + 编码器取反**，**千万别把负值写进 PWM CCR**。

### 4.2 里程与长度标定
```
Distance += (avg_encoder × 10.4 × π / 5720) / 0.362 × LEN_SCALE
```
`LEN_SCALE=1.2f`（100 代码单位 ≈ 120cm，config.h）。地图 step 与各距离阈值已按 `cm=round(代码单位×LEN_SCALE)` 内联为整数厘米，仅运行时连续累加的里程公式乘 `LEN_SCALE`。

### 4.3 IO 引脚分配
| 外设 | 引脚 | 功能 |
|------|------|------|
| USART1 | PA9/PA10 | 调试串口 |
| USART3 | PB10/PB11 | IMU 陀螺仪（波特率必须匹配） |
| UART4/5/7 | PC10~PD2/PE7/PE8 | 其他串口通信 |
| UART8 | PE0/PE1 | K210/OpenMV |
| TIM1/2/3/5 | — | 编码器输入 |
| TIM4/8/9 | PD12~PD15/PC8/PC9/PE5/PE6 | 电机 PWM |
| TIM12 | PB14/PB15 | 舵机 PWM |
| ADC1 | PA2/PA3/PC4/PC5 | 电池电压/灰度 |

---

## 5. PID 与运动控制链（怎么动）

### 5.1 两层 PID
- **内环（速度环）**：`pid.c:incremental_PID()`，5ms 周期，`bias = target - 编码器速度`。增量式输出累加、带抗积分饱和；`target==0` 且测量很小时清历史防 PWM 残留抖动。参数 40/10/5（L0-L1/R0-R1），`outputMax=MOTOR_PWM_MAX`。
- **外环（航向环）**：`pid.c:positional_PID()`，输入是误差、输出是差速 `Fspeed`，微分带一阶低通（`differential_filterK≈0.5~0.7`）。
  - 巡线(line)：初始 7.0/0/0 ±80，运行时被 `line_pid_steps[]` 按实际速度覆盖。
  - 转弯(gyroT)：4.0/0/70 ±80；陀螺仪直行(gyroG)：2.0/0/5.0 ±80；灰度(lineG)：15/0/5 ±80。

### 5.2 速度等级与 PID 阶梯（`line_pid_steps[]`，chassis_api.c）
`SPEED0=25, SPEED1=36, SPEED2=45, SPEED25=55, SPEED3=60, SPEED4=70, SPEED5=75`。
`Chassis_UpdateLinePidBySpeed()` 每 5ms 按**当前实际速度**取档（当前速度 ≤ 档速才采样该档，尽量向上取高速档低 Kp；超过最高档用最高档）：
| 档速 | Kp | Kd | 档速 | Kp | Kd |
|------|----|----|------|----|----|
| 75(SPEED5) | 3.5 | 200 | 45(SPEED2) | 6.5 | 110 |
| 70(SPEED4) | 3.5 | 200 | 36(SPEED1) | 7.5 | 100 |
| 60(SPEED3) | 4.0 | 120 | 25(SPEED0) | 9.0 | 100 |
| 55(SPEED25) | 5.0 | 150 | 20/15/12 特低速 | 11 / 20 / 25 | 100/140/140 |

### 5.3 模式枚举与切换
```c
typedef enum { is_No=0, is_Free, is_Line, is_Turn, is_Gyro };
// 巡线子模式：TRACK_ALL=0, TRACK_LEFT_EDGE, TRACK_RIGHT_EDGE, TRACK_NEAR_CENTER（默认，绝大多数普通路段）
```
| 来源→目标 | 处理 |
|-----------|------|
| Gyro→Line | gyroG_pid→line_pid_obj, TG→TC |
| Line→Gyro | line_pid_obj→gyroG_pid, TC→TG |
| Turn→Line | 清 line_pid/TC/Cspeed |
| Turn→Gyro | 清 gyroG_pid/TG/Gspeed |
| →Turn | 清 gyroT_pid |

差速限幅统一在 `motor_all.Line_speedMax`，`line_pid_param.outputMax` 固定 ±80。`Go_Line` 中 `Fspeed *= |speed|/40`、`Go_Angle` 中 `GGspeed *= |speed|/50`（差速按速度缩放，使路径形状与车速无关）。

### 5.4 转弯逻辑（turn.c）
`need2turn(now,target)` 归一到 (-180,180]；`getAngleZ()=yaw+compensateZ`；`Turn_Angle_Base(Angle,ratio,force_thr)` 原地转基函数（误差<2°判到位、低速给±7死区补偿）；`Stage_turn_Angle` 平台转(force_thr=150°)；`Turn360Step` 360°梯形速度曲线（加速40°→全速→358°前减速）；`Go_Angle` 陀螺仪直行。

---

## 6. 传感器数据流（从哪里来）

**循迹**：16 路 GPIO/DMA → `bsp_linefollower` → `scaner.c:Scaner_Update()`（单入口；`line_data[5]` 滑动窗口，static 仅本文件访问）→ `Get_scaner_error()`（多数决+簇投票，丢线时返回上一次有效错误）→ `Go_Line()` 外环 PID → 差速。`value_calculation` 四种 `TRACK_` 模式均显式 case；`Scaner_ClearLineData()`/`Scaner_IsLineLost()` 为外部接口。
**寻中线**：亮灯总数≥4 保守判中心(error=0)；中心两灯(7,8)同亮判中心；否则扫描**连续亮灯段**（不允许跨空隙），段内只取最靠中心 2 灯算平均位置。
**IMU**：USART3 DMA + IDLE 中断 → `imu.c` 0x55 协议 10 字节校验 → `imu.yaw/roll/pitch`(±180°)；`IMU_CalibrateZero` 10 次采样归零，`getAngleZ()=yaw+imu.compensateZ`。
**视觉**：USART6 → `K210.c`（`WaitFor_QR`→`flag_line_clue`/`flag_clue_stage_A/B`；`Door_ReadPass`→`door_pass[5]`；OCR→`flag_clue_A/B`→`treasure`）。

---

## 7. Navigation() 执行流程（map.c）

```
Navigation()
├─ near_end==0（巡线行驶）
│   ├─ SEG_INIT：清里程、设巡线模式/速度、启用游龙+翘头保护
│   ├─ SEG_MID_SWITCH：里程≥50% 切换巡线模式
│   └─ SEG_PREP_ARRIVE：里程≥60% 降速
└─ near_end==1（节点处理）
    ├─ Nav_NearEnd：map_function() → 等待到达
    ├─ Nav_TurnAndAdvance：转弯（follow/停车原地转/陀螺仪）
    └─ Nav_PostProcess：查 cross_event → 推进节点
```

---

## 8. 关键配置：config.h（唯一入口，⚠️改前必看）

> 位置：`Mission/config.h`。所有**开关**和**场地参数**都集中在这里；其它文件只 `#include "config.h"`，**别重复 `#define`**（否则编译报重定义）。

**当前值（请以此为准，改前先确认）**：
| 宏 | 当前值 | 含义 |
|----|--------|------|
| `USE_FIELD` | `FIELD_SCHOOL` | 场地：`FIELD_COMP`=比赛 / `FIELD_SCHOOL`=学校。学校档 14 个 `TODO(学校)` 值已填数字，仍需按学校场地实测复核 |
| `USE_PLANNER_ROUTE` | `1` | `1`=除一轮门回程外的路线（初始、出门点→平台、二轮）由最短路算法生成；`0`=回退到手写 `route[]`/`door*route[]`。**一轮门回程(`update_route_by_door_*`)恒用手写穷举路线**，不受此开关影响（避免规划器穿门掉头）。⚠️ **切回 `0` 前必看**：`update_route_at_door_for_stageAB` 的手工兜底依赖已删除的 `rout_57/58/67/68`，该段现为 `#if !USE_PLANNER_ROUTE` 条件编译，需先恢复这些数组才能编过 |
| `MAP_DEBUG` | `0` | `1`=用 `FIRST_POINT→END_POINT` 最短路径自动生成调试路线 |
| `SKIP_ROUND1` | `0` | `1`=跳过第一轮直接进第二轮（调试用）；正式比赛必须 0 |
| `MAIN_DEBUG` / `STEP_DEBUG` | `0` / `0` | 调试分支/按一下跑一个节点；正式比赛必须 0 |
| `DEBUG` | `0` | `1`=门颜色走 `debug_door_pass[]` 预设（barrier.c） |
| 门区段 | — | `DOOR_LEN_*`(6)、`DOOR_RETREAT_*`(4)、`ANGLE_*`(2，反向用 `ANGLE_REV(a)`) |
| 长度标定 | `LEN_SCALE 1.2f` | 100 代码单位 ≈ 120cm；运行时里程公式用，其余距离阈值已内联为 cm |

---

## 9. 改地图/路线（核心方法，⭐最重要）

> 一句话：**改地图 = 改 `Navigation/map_message.c` 的 `NavEdgeTbl[]`（唯一人工编辑源）+ `Mission/config.h` 的几何/开关**，执行层三数组自动重建。改路线 = 改 `Mission/mission_planner.c` 的必经点 `wp`。

### 9.1 单源边表
```c
typedef struct { u8 from; u8 to; u32 flag; float angle; u16 step; float speed; u8 func; } NavEdge;
#define NAV_EDGE_COUNT 124
extern const NavEdge NavEdgeTbl[NAV_EDGE_COUNT];  // 唯一人工编辑源，用原 map_message 宏/名
int nav_init(const NavEdge *edges, uint16_t n_edges, uint8_t n_nodes);  // 一次建成执行层 CSR + 规划层线路图（nav_planner.c）
```
启动顺序：`mapInit()` → `nav_planner_setup()`(map.c) → `nav_init(NavEdgeTbl, NAV_EDGE_COUNT, 54)`，**一次调用同时建好**执行层 `Node[]/ConnectionNum[]/Address[]`（定义在 `nav_planner.c`，extern 声明在 `map.h`）与规划层线路图；`s_nav_ready` 保证只建一次。返回 -1 表示边/节点/连接数超静态容量。

### 9.2 节点编号（枚举顺序 = 索引，**不能调换**）
```
S1=0  P1=1  N1=2  B1=3  B2=4  B3=5  N2=6  P2=7  S2=8  P3=9
N3=10 N4=11 N5=12 N6=13 P4=14 N7=15 P6=16 B8=17 B9=18 N8=19
C1=20 C2=21 C3=22 N9=23 N10=24 N12=25 N13=26 P5=27 N14=28 S3=29
S4=30 N15=31 S5=32 C4=33 C5=34 B4=35 B5=36 B6=37 B7=38 N16=39
N18=40 N19=41 P7=42 N20=43 N22=44 C6=45 C7=46 C8=47 C9=48 P8=49
N11=50 G1=51 B10=52 B11=53
```
> B10/B11 = 波动板节点（正反向共用板尾），进板边 `BLBL`、出板边 `NONE`（恢复路口检测）。
> 每条边 = `{from, 目标, flag, 角度, step(cm), 速度(SPEED0~5), 功能}`；`flag` 控制巡线方式(`LEFT_LINE/RIGHT_LINE/NEAR_CENTER/Temp_L/Temp_R`)、转弯(`L_follow/R_follow/STOPTURN/NOTURN`)、到达检测(`MUL2SING/MUL2MUL/DLEFT/DRIGHT/CLEFT/CRIGHT/AWHITE`)。

### 9.3 改地图四步
1. `Navigation/map_message.c` 改 `NavEdgeTbl[]` 的 `from/to/flag/angle/step/speed/func`，并同步 `map_message.h` 的 `#define NAV_EDGE_COUNT`。
2. 增删节点 → 改 `Navigation/map.h` 的 `MapNode` 枚举（枚举顺序 = 索引，别插入中间）。
3. 门区段长度/角度 → 只改 `Mission/config.h` 的 `DOOR_LEN_*`/`ANGLE_*` 宏（别改散落手工值）。
4. 跑 PC 校验：`scripts/validate/_weight_calib.py`（改边/权重后）、`scripts/validate/_check_csr.py`（增删边后）、`scripts/validate/_check_door_logic.py`（改门逻辑后）；编译 0 error 再上真车。

### 9.4 必经点原则（改 `mission_planner.c` 的 `wp` 时必守）
`wp` **只写**「起点 + 门节点(`N5/N8/N12/N10/N3`) + `P` 平台 + 终点」；**别加平台入口锚点**（P5 前 `N13`、P6 前 `N9`、far 入口 `N4`）——P5/P6 是支路、P6 跷跷板单向由图强制，规划器必然经过它们，写进去冗余。**门节点必须**，否则会跨未确认/单向门。改 `wp` 后可用 `scripts/validate/_check_wp.py` 验证"删了某个必经点路线不变"。

---

## 10. 关键函数位置一览（知道去哪儿改）

| 功能 | 函数 | 位置 |
|------|------|------|
| 主循环路径执行 | `Navigation()` / `map_function()` / `getNextConnectNode()` | `Navigation/map.c` |
| 地图状态初始化 | `mapInit()` / `nav_planner_setup()` | `Navigation/map.c` |
| 单源边表构建 CSR + 线路图 | `nav_init()`（`nav_graph_init()` 已并入其中） | `Navigation/nav_planner.c` |
| 最短路 | `nav_init` / `nav_shortest_path` / `nav_plan_waypoints` / `nav_build_route` / `nav_find_edge` | `Navigation/nav_planner.c` |
| QR 分流、门/宝物改路 | `update_route_at_P1()` / `update_route_by_door_*()` / `update_route_at_door_for_stageAB()` / `update_route_at_P7/P8_for_treasure()` | `Mission/mission_planner.c` |
| 一轮门回程 | `update_route_by_door_1~4()`（**手写穷举路线**，不走规划器，防穿门掉头）。其中 `_1` 与 `_3` 进入条件相同（nowNode 均为 N3），实现已合并为 `route_return_from_N3()` | `Mission/mission_planner.c` |
| 第二轮完整路线 | `get_newroute()` / `Clear_door()` / `load_route_at()` | `Mission/mission_planner.c` |
| 门通行检测 + 障碍物理 | `door()` / `Door_ReadPass()` / `door_set_pass_node()` / `door_retreat()` | `Mission/barrier.c` |
| 底盘/电机/传感器 | `Chassis_*` API（`Chassis_Init/SetMode/SetTargetSpeed/SetTrackMode/MotorControl/Brake/DriveDistance_Blocking/Periodic_Update_5ms/OverrideLinePid`） | `Application/chassis_api.c` |
| 16 路巡线 | `Scaner_Update()` / `Go_Line()` / `Get_scaner_error()` | `Application/scaner.c` |
| 转弯 | `Turn_Angle_Base()` / `Go_Angle()` / `Stage_turn_Angle()` / `Turn360Step()` | `Application/turn.c` |
| 内/外环 PID | `incremental_PID()` / `positional_PID()` | `Math/pid.c` |
| 电机 PWM / 编码器 | `motor_set_pwm()` | `Motor/motor.c` |

---

## 11. 已知关键坑（改码前必读）

- 🚧 **door() D5黑+D2蓝 回程卡死**：`DOOR_D5_BACK` 该分支只写 `route[0]=N3`、没重建 `route[1..]`，车到 N8 转 N3 后 `getNextConnectNode(N3, route[1])` 撞残留脏值 → `Route_Error_Stop` 死停。**修复：`route[0]=N3;` 后补 `route[1]=0xFF;`**（让护栏跳过，车走 N8→N3 重触发 D4 门）。排查门区路线时注意 `door_retreat` 会**隐式改 `nodes.nowNode`**、`door_set_pass_node` 会改 `Node[].function/speed/step`。
- ⚠️ **`getNextConnectNode` 兜底防跑飞**：查不到连接时不再返回 0（会带车跑飞），改为打印并 `CarBrake_Stop()` 死停。改路线时确保每两个相邻节点在 `NavEdgeTbl[]` 里**有向连通**；`route[map.point]==0xFF` 是路线结束哨兵。
- ⚠️ **偏差/警告提示**：`pid.c` 有注释掉的 R1 死代码；`motor_task.c` 5ms 循环内若留有调试 printf 会拖慢周期；`main_task.c`/`motor_task.c` 循环里读 `DWT->CYCCNT`，但使能它的 `timing_dwt_init()` 已按"未引用"清理，若要恢复周期耗时测量需同时恢复该函数与调用。属遗留，别误删功能性代码。

---

## 12. 给 AI / 接任者的工作流提示（⚠️按此操作，避免丢代码）

1. **改任何代码/文档前，先暂存当前工作树**（血的教训）：
    本工程**未提交的改动只在工作树**，一旦被 `git checkout`/`reset`/本地覆盖就很难找回。约定：**每次动手前先 `git stash push`（改完 `git stash pop` 回来并核对），或直接 `git commit -m "..."`**。尤其 `mission_planner.c`/`barrier.c`/`nav_planner.c`/`map_message.c`/`config.h` 的规划器改动，务必先暂存。
2. **编译**：MDK 工程 `MDK-ARM/test1.uvprojx`，用 **Keil V5.32** 编译，预期 0 Error（可容忍未使用变量类 Warning）。改地图/权重后在 MDK 编译确认 0 error 再上真车。
3. **文件编码**：全工程 **UTF-8**（无 BOM）。写源码保持 UTF-8。
4. **include 规则**：所有源目录已在 Keil/EIDE 的 IncludePath 里，**一律用短写** `#include "xxx.h"`（全工程统一，不再用 `../Xxx/xxx.h`）。前提是**裸名必须唯一**：工程里 `sys.h`（`Application/`）与 `adc.h`（`Core/Inc/`）原各有两份同名文件，已分别删掉 `USMAT/sys.h`、`Module/adc.{c,h}` 消除歧义；**新增同名头文件前先确认不会撞名**，否则 `-I` 顺序会静默改变命中对象。`#include` 的查找顺序是「当前文件所在目录 → `-I` 列表顺序」。
5. **别做的操作**：`motor_task` 5ms 循环内别加阻塞/大量 `printf`（破坏周期）；别把负值写进 PWM CCR（反向换 TIM 通道极性并取反编码器）；CubeMX 重新生成后要注释 `main.c` 定时器中断回调 + `stm32f7xx_it.c` 的 `USART3_IRQHandler`。
6. **改完同步文档**：改完代码更新本文件（相关函数/配置/结构）和 [README.md](README.md) 的修改日志（写日期 + 改了啥）。
7. **验证方法**：`scripts/validate/_weight_calib.py`（复现参考路线/权重灵敏度）、`scripts/validate/_check_csr.py`（CSR 连通性）、`scripts/validate/_check_wp.py`（必经点删除不改路线）、`scripts/validate/_check_door_logic.py`（门逻辑表驱动）；这些脚本只做校验/分析，不进固件。

---
> 更细的底层资料直接看代码：`map.h`(节点枚举/结构)、`map_message.c`(边表)、`nav_planner.h`(权重 `NavObsPenalty[]`/`NAV_W_TURN`)、`chassis_api.c`(PID 阶梯 `line_pid_steps[]`)、`scaner.c`(权重表 `line_weight_default[16]`)、`pid.c`(内环/外环实现)。
