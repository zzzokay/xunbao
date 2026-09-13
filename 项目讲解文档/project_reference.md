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
  ├── nav_planner.c/h       # 最短路算法（nav_init/nav_shortest_path/nav_plan_waypoints/nav_build_route/nav_find_edge/nav_set_edge_blocked）
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

**障碍/门/宝物时**：`map_function()` 分发到 `barrier.c` 的 `Stage()/Bridge()/Hill()/door()` 等物理动作；做完后由 `mission_planner.()` 改写 `route[]`。**门回程(`update_route_by_door_*`)改为"规划层门区禁用 + 极简必经点"**：`route_return_home()` 先用 `nav_set_edge_blocked()` 把门区 8 条边全部禁用（回程不再进门区、结构上不可能穿门掉头），再用 `wp={当前节点,[宝物平台],P2}` 让最短路算回家路；唯一例外是 door_2（额外放行 `N8→N3`，必须退回去重读 D4）。等价性由 `scripts/validate/_check_door_perm.py` 用改造前的 12 条手写路线当 golden 守住（12/12）。

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
**寻左/寻右（边寻线）**：`calc_left_edge`/`calc_right_edge` 取最靠边的一段（最多 2 灯）；**节点保护**——用 `edge_run_len()` 量该段连续长度，`> EDGE_SEG_MAX_LED`（默认 3）判为节点横向线/粘连 → `return -1`（帧记 `ALL_ERR`，交 5 帧历史保持上次有效误差），避免节点处误差大跳变。参数 `EDGE_SEG_MAX_LED` 在 `scaner.c`（与 `MAX_LED` 同处）。⚠️ 局限：只覆盖"选中段被拉长（粘连宽线）"，"主线+独立 2 灯节点臂"拦不住，靠 `pos_detect`+5 帧投票兜底。
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
| `USE_PLANNER_ROUTE` | `1` | `1`=路线（初始、出门点→平台、二轮）由最短路算法生成；`0`=回退到手写 `route[]`。**一轮门回程(`update_route_by_door_*`)不受此开关影响——它恒用规划器 + 门区边禁用**（见 §10）。⚠️ **切回 `0` 前必看**：`update_route_at_door_for_stageAB` 的手工兜底依赖已删除的 `rout_57/58/67/68`，该段现为 `#if !USE_PLANNER_ROUTE` 条件编译，需先恢复这些数组才能编过（即当前 `0` 档实际编不过） |
| `MAP_DEBUG` | `0` | `1`=用 `FIRST_POINT→[VIA_POINT]→END_POINT` 必经点最短路径自动生成调试路线（`VIA_POINT=0` 表示**不用途径点**，即原来的两点行为） |
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

> ⚠️ **以 `Navigation/map.h` 的 `enum MapNode` 为唯一准绳**（下表已于 2026-09-12 按真实枚举重抄并核对）。
> 旧版本文档里那份编号（`C1=20 C2=21 C3=22 … C4=33 … P8=49 … B11=53`）**是过期的**：
> `map.h` 里 **C1/C2 已被注释掉**（注释掉的枚举成员不占编号），必须**先剥注释再依次编号**，
> 否则从 `C3` 起全部错位（会把 P8 算成 49、实际是 46）。`scripts/analyze/analyze_turn_comp_probe.py`
> 就按这个规则解析，并会断言抽查值。

```
S1=0  P1=1  N1=2  B1=3  B2=4  B3=5  N2=6  P2=7  S2=8  P3=9
N3=10 N4=11 N5=12 N6=13 P4=14 N7=15 P6=16 B8=17 B9=18 N8=19
C3=20 N9=21 N10=22 N12=23 N13=24 P5=25 N14=26 S3=27 S4=28 N15=29
S5=30 C4=31 C5=32 B5=33 B6=34 B7=35 N16=36 N18=37 N19=38 P7=39
N20=40 N22=41 C6=42 C7=43 C8=44 C9=45 P8=46 N11=47 B10=48 B11=49
```
> 共 **50** 个真实成员（`map.h` 里 `C1`/`C2` 为注释状态，不占编号；`C10` 不存在）。
> ⚠️ `map.c` 里 `nav_init(NavEdgeTbl, NAV_EDGE_COUNT, 54)` 与 `if (nownode >= 54)` 的 **54 是个宽松上界**
> （只有 `nav_init` 会按 `n_nodes` 建表，`54 > 50` 无害），但别拿它当节点个数。
> `B10`/`B11` = 波动板节点（正反向共用板尾），进板边 `BLBL`、出板边 `NONE`（恢复路口检测）。
> 每条边 = `{from, 目标, flag, 角度, step(cm), 速度(SPEED0~5), 功能}`；`flag` 控制巡线方式(`LEFT_LINE/RIGHT_LINE/NEAR_CENTER/Temp_L/Temp_R`)、转弯(`L_follow/R_follow/STOPTURN/NOTURN`)、到达检测(`MUL2SING/MUL2MUL/DLEFT/DRIGHT/CLEFT/CRIGHT/AWHITE`)。

### 9.3 改地图四步
1. `Navigation/map_message.c` 改 `NavEdgeTbl[]` 的 `from/to/flag/angle/step/speed/func`，并同步 `map_message.h` 的 `#define NAV_EDGE_COUNT`。
2. 增删节点 → 改 `Navigation/map.h` 的 `MapNode` 枚举（枚举顺序 = 索引，别插入中间）。
3. 门区段长度/角度 → 只改 `Mission/config.h` 的 `DOOR_LEN_*`/`ANGLE_*` 宏（别改散落手工值）。
4. 跑 PC 校验：`scripts/validate/_weight_calib.py`（改边/权重后）、`scripts/validate/_check_csr.py`（增删边后）、`scripts/validate/_check_door_logic.py`（改门逻辑后）；编译 0 error 再上真车。

### 9.4 必经点原则（改 `mission_planner.c` 的 `wp` 时必守）
`wp` **只写**「起点 + 门节点(`N5/N8/N12/N10/N3`) + `P` 平台 + 终点」；**别加平台入口锚点**（P5 前 `N13`、P6 前 `N9`、far 入口 `N4`）——P5/P6 是支路、P6 跷跷板单向由图强制，规划器必然经过它们，写进去冗余。**门节点必须**，否则会跨未确认/单向门。改 `wp` 后可用 `scripts/validate/_check_wp.py` 验证"删了某个必经点路线不变"。

### 9.5 图形化改图工具 `scripts/map_editor/`（⭐ 推荐先用它，别手抠边表）

> 手改 124 行边表容易改漏（`NAV_EDGE_COUNT`、分组注释、`flag` 位、正反向边）。用编辑器改，
> 改完导出 C 代码，或让它直接写回（会先备份）。
> 📄 **[scripts/map_editor/README.md](../scripts/map_editor/README.md)**（给人：使用说明）
> ｜ 🤖 **[scripts/map_editor/AI_CONTEXT.md](../scripts/map_editor/AI_CONTEXT.md)**
> （**给 AI：架构、坐标系、必须保住的不变量、安全规则与踩坑、常见改动指引 —— 改这个工具前先读它**）

```bash
python scripts/map_editor/map_editor.py    # 打开即当前固件地图；零依赖（tkinter 自带）
```

- **两条心智模型**：① **节点位置只是示意图**——图上远近不代表实际长度，长度只认 `step` 数值，
  所以**节点随便拖，不影响任何数值**；图的作用是表达"连接关系 + 角度关系"并贴合标准节点图。
  ② **导出逐字段保真**——不做任何编辑时，导出的边表与源文件完全相同（`_selftest.py` 断言差异 0 处）。
- **底图对齐**：自动把 `寻宝地图/节点图.jpg` 半透明铺在下面。对齐依据是 `SEED_POSITIONS`
  就是该 **1729×1080 原图的像素坐标**（1:1，无需换算）。⚠️ `C2/B4/C6/C7/C8/G1` 六个节点
  原图**没画**，坐标是估的，拖一下即可。
- **能力**：拖节点；Shift 拖出连线；点选改 `from/to/flag/angle/step/speed/func/comment`（`angle/step`
  可直接写 `ANGLE_*`/`LEN_*`/`DOOR_LEN_*` 宏，按 `config.h` 当前 `USE_FIELD` 求值）；
  flag 25 位勾选板；补反向边；校验（孤立/单向/重名/宏能否求值）；必经点最短路（与固件同一套
  Dijkstra + `NavObsPenalty`）；导出 `NavEdgeTbl[]`/`enum MapNode`/`NAV_EDGE_COUNT`/`route[]`；
  写回固件（**先自动备份**到 `scripts/map_editor/backups/`，有 error 级问题拒绝写回）。
- ⚠️ **工具只保证"导出文本正确"，不保证"业务自洽"**：增删节点后必须自己同步检查
  `mission_planner.c` 的 `wp`、门逻辑、宝物表、`barrier.c` 的节点比较（节点编号 = 枚举顺序）。

### 9.6 `MAP_DEBUG` 地图调试路线（跑单点/多点用，与比赛 `wp` 无关）
只改 `Mission/config.h` 三个宏，`map.c:mapInit()` 的 `#if MAP_DEBUG` 分支用 `nav_plan_waypoints()` 自动生成 `route[]`：
```c
#define FIRST_POINT   N6    /* 调试起点（MapNode 枚举名） */
#define VIA_POINT     0     /* 调试途径点：填 0 = 不用途径点（退化成两点路线） */
#define END_POINT     P3    /* 调试终点 */
```
- 语义 = `wp = {FIRST_POINT, [VIA_POINT], END_POINT}` 的**必经点**规划：`VIA_POINT≠0` 时路线保证依次经过它。
- ⚠️ **`S1=0`**（`enum MapNode` 第 0 项），所以 **S1 不能当途径点**（`0` 已被占为"不用"哨兵）。
- ⚠️ 途径点是**支路/平台**时（如 `P4`、`P5`）会"去一趟再折返"，`route[]` 里会出现回到主路的节点，属正常。
- `route[]` 语义不变：`nodes.nowNode` = 第一跳，`route[]` 从 path[2] 起（不与 nowNode 重复），末尾 `0xFF`。
- **陀螺仪参考角（重要）**：`main_task.c` 在 `mapInit()` 之后立刻 `mpuZreset(get_latest_yaw(), nodes.nowNode.angle)`；而 `nowNode` = 「`FIRST_POINT`→第一跳」这条边，`mpuZreset` 令 `compensateZ = need2turn(yaw, referangle)`、`getAngleZ()=yaw+compensateZ`，所以**参考角 = 该边的 `angle`**（注意：地图里**没有"节点角度"**，只有边有 `angle`＝本段航向）。⇒ **摆车时必须把车放在 `FIRST_POINT`，且车头顺着 `FIRST_POINT`→第一跳的方向**，否则整轮所有转弯一起偏这么多。
  - 参考角随"第一跳"变：`FIRST=N6→N5=0°`、`N9→N10=180°`、`C7→B10=-90°`、`N8→N3=-35°`；**途径点也可能改掉第一跳**（`FIRST=N6,END=P3` 无 via=0°，`VIA=P5`→第一跳 C1=50°，`VIA=P4`→第一跳 P4=180° 起手就上平台）。
  - 校准时机在 `main_task.c` 的**红外等待之前**（line 62 早于 77~81 行的挡板等待）：**校准后别再用手机械摆正车头**（`getAngleZ()` 是相对量，会跟着一起转），要重校就复位一次。
  - 现存约定一致：`barrier.c:397`（巡线稳定重校）与 `ArriveDetect_task.c:29` 同样用 `nowNode.angle`，可见"`nowNode.angle` = 当前边航向"是全工程统一语义。
  - ⚠️ 唯一小坑：`FIRST_POINT=S1`(=`0`) 时 `nodes.lastNode.nodenum==0` 会撞上 `Nav_IsStraightThrough()` 里"首个边未初始化"的哨兵，只影响第一段是否加巡线陀螺阻尼，**不影响角度**。
- ⚠️ **场次(`USE_FIELD`)必须同步**：`scripts/validate/_weight_calib.py` 顶部的 `USE_FIELD` 是手写常量（默认 `FIELD_COMP`），与 `Mission/config.h` 的 `USE_FIELD` 不同步时，镜像算出的"调试路线"会和车上实际跑的不一样（**2026-09-11 实测踩过**：`FIRST=N6,VIA=N3,END=P4` 在门惩罚 0 + 学校长度下是 `N3→N8→N5`、比赛长度下是 `N3→N4` 掉头）。已加 `_weight_calib.sync_field_from_config()`（**注意 config.h 里有 4 个 `#if USE_FIELD == FIELD_SCHOOL` 块，必须全部遍历**，只取第一块会漏掉门区长度），`_check_map_debug.py` 每次自动按 `config.h` 覆盖长度宏 + 打场次告警；`_check_wp/_check_csr/_check_door_*` 的 golden 仍按 `FIELD_COMP`（保持原行为）。镜像的 `OBS_PENALTY` 也已与 `nav_planner.c` 对齐（`DOOR`→60、`BLBS` 60→70）。
- ⚠️ **门惩罚已从 0 提到 60**（`nav_planner.c: NavObsPenalty[14]`，2026-09-11 改）。原值 0 的设计是"门用必经点约束、不靠权重"，但门有**固定时间开销**（停车→等线 `Scaner.ledNum>=8`→刹车→读灯 500ms+转弯），纯"长度+转弯"模型完全没算 → 取 0 会让规划器把"穿门"当**免费捷径**。实测这个偏差（学校场地 `N3→P4`）：

  | `N3→P4` 两种走法 | 门惩罚 0（旧） | 门惩罚 60（现） |
  |---|---|---|
  | 原路折返 `N3→N4→N5→N6→P4` | 510 | 510 |
  | 穿门 `N3→N8→N5→N6→P4` | 493(学校) / 523(比赛) | 613 / 643 |
  | 规划器选 | **穿门**（学校） | **折返** |
  
  取 60 = 与 `UpStage` 同量级。回归证据：`NavObsPenalty[DOOR]` 在 **0→300** 全程，15 条参考路线 / 12 条门回程 golden / 门逻辑表 / wp 不变量**全部不变**，只有"本来就不该穿门"的组合会改。⚠️ **残余风险**：门节点的"从哪一侧进"是靠**成本最省**决定的（`door()` 用 `lastNode/nowNode` 判 `D2/D3/D4/D5`），提权重后若某个 wp 组合换了进门方向 → 读的灯也换 → **必须实车复核门区**。`DOOR1`(18) 目前**无任何边使用**，保持 0。
  另外：**必经点交界处那个转弯在规划里不计费**（`nav_shortest_path` 对段首边只算 base）——所以"在 N3 拐 145° 还是 180°"的差别根本没进成本，这也是上面两种走法只差十几的原因；评估改动时别用"整条 route 总成本"下结论。
- ⚠️ **调试路线一进 DOOR 边就不再是你的路线**：到点后 `map_function(DOOR)→door()`，而 `door()` 开头 `map.point=0; route[0]=0xFF;`（`barrier.c`）会**清空 `route[]`**，之后跑比赛门逻辑（`DEBUG=0` 时真读红绿灯，`door()` 按 `lastNode/nowNode` 定 `DOOR_D2/D3/D4/…`）。脚本检测到路线经过 DOOR 边会告警。想纯跑路线就别让必经点/终点把它带进门区。
- 校验：`scripts/validate/_check_map_debug.py`（穷举 54×54 断言"`VIA_POINT=0` 与改造前两点行为逐字一致"+ via 路线真经过途径点；第 4 节打印当前配置的**陀螺仪参考角**、摆车方向、**逐段航向/转弯量**，并对"**180° 原路折返**"和"**经过 DOOR 边**"告警——平台节点(UpStage/UpStageHome/BSoutPole)上的折返会标注为"平台内部转身，正常"）、`scripts/validate/_syntax_map_debug.py`（把该代码块抽出来做 GCC 语法检查）。

---

## 10. 关键函数位置一览（知道去哪儿改）

| 功能 | 函数 | 位置 |
|------|------|------|
| 主循环路径执行 | `Navigation()` / `map_function()` / `getNextConnectNode()` | `Navigation/map.c` |
| 地图状态初始化 | `mapInit()` / `nav_planner_setup()` | `Navigation/map.c` |
| 单源边表构建 CSR + 线路图 | `nav_init()`（`nav_graph_init()` 已并入其中） | `Navigation/nav_planner.c` |
| 最短路 | `nav_init` / `nav_shortest_path` / `nav_plan_waypoints` / `nav_build_route` / `nav_find_edge` | `Navigation/nav_planner.c` |
| 运行时边禁用（门区回程用） | `nav_set_edge_blocked` / `nav_clear_blocked` | `Navigation/nav_planner.c` |
| QR 分流、门/宝物改路 | `update_route_at_P1()` / `update_route_by_door_*()` / `update_route_at_door_for_stageAB()` / `update_route_at_P7/P8_for_treasure()` | `Mission/mission_planner.c` |
| 一轮门回程 | `update_route_by_door_1~4()` → 统一走 `route_return_home()`（**规划层禁用门区 + `wp={当前节点,[宝物平台],P2}`**，不再手写路线）。door_2 额外放行 `N8→N3`（退回重读 D4）；`door_zone[8][2]` 是禁用的门区边表 | `Mission/mission_planner.c` |
| 第二轮完整路线 | `get_newroute()` / `Clear_door()` / `load_route_at()` | `Mission/mission_planner.c` |
| 门通行检测 + 障碍物理 | `door()` / `Door_ReadPass()` / `door_set_pass_node()` / `door_retreat()` | `Mission/barrier.c` |
| **地图图形化编辑（辅助工具，不进固件）** | `map_editor.py`（界面）/ `map_model.py`（解析+导出+校验+Dijkstra） | `scripts/map_editor/`（见 §9.5） |
| 底盘/电机/传感器 | `Chassis_*` API（`Chassis_Init/SetMode/SetTargetSpeed/SetTrackMode/MotorControl/Brake/DriveDistance_Blocking/Periodic_Update_5ms/OverrideLinePid`） | `Application/chassis_api.c` |
| 16 路巡线 | `Scaner_Update()` / `Go_Line()` / `Get_scaner_error()` | `Application/scaner.c` |
| 转弯 | `Turn_Angle_Base()` / `Go_Angle()` / `Stage_turn_Angle()` / `Turn360Step()` | `Application/turn.c` |
| **转弯前补偿距离** | `GetForwardDistanceBeforeTurn()`（停车转，默认19）/ `GetForwardDistanceBeforeGyroTurn()`（陀螺转，默认0） | `Navigation/map.c` |
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
7. **验证方法**：`scripts/validate/_weight_calib.py`（复现参考路线/权重灵敏度）、`scripts/validate/_check_csr.py`（CSR 连通性）、`scripts/validate/_check_wp.py`（必经点删除不改路线）、`scripts/validate/_check_door_logic.py`（门逻辑表驱动）、`scripts/validate/_check_door_perm.py`（门回程边禁用 golden）、`scripts/validate/_check_map_debug.py`（`MAP_DEBUG` 起终点/途径点路线）、`scripts/validate/_syntax_map_debug.py`（`map.c` 的 `MAP_DEBUG` 代码块 GCC 语法检查——`map.c` 整体因 RVDS `__asm` 编不过，故抽块检查）；这些脚本只做校验/分析，不进固件。
8. **改地图/路线建议用图形化工具**：`python scripts/map_editor/map_editor.py`（见 §9.5）。手抠 124 行边表容易漏改 `NAV_EDGE_COUNT`/正反向边；工具能导出逐字段保真的 C 代码，也能直接写回（先自动备份）。改完仍要跑上面 7 个脚本 + Keil 编译。

---
> 更细的底层资料直接看代码：`map.h`(节点枚举/结构)、`map_message.c`(边表)、`nav_planner.h`(权重 `NavObsPenalty[]`/`NAV_W_TURN`)、`chassis_api.c`(PID 阶梯 `line_pid_steps[]`)、`scaner.c`(权重表 `line_weight_default[16]`)、`pid.c`(内环/外环实现)。

---

## 13. 巡线稳定性两处改动：配置 / 验证 / 排查

> 用于"跑直线/过节点还摆"时快速定位。两处都是**附加**逻辑，可独立关闭，互不依赖。

### 13.1 长直线陀螺仪阻尼（方案A）

- **在哪**：`Application/chassis_api.c/h` 的 `Chassis_EnableLineGyroComp()/DisableLineGyroComp()/GetLineGyroComp()`；`Navigation/map.c` 的 `Nav_IsStraightThrough()` 判"直穿段"并开关；`Application/scaner.c` 的 `Go_Line()` 末尾 `Fspeed += Chassis_GetLineGyroComp();`。
- **原理**：只做**角速度阻尼**（`Gcomp = -kd × yaw_rate`，yaw_rate 为一阶低通后的角速度），**不加绝对目标角** → 不需要 `RESTMPUZ`（一阶差分自动抵消零位偏差），也不怕进直线时车头偏几度；横向纠偏仍由激光负责，两者分工。
- **参数（`Application/chassis_api.h`，当前值）**：`LINE_GYRO_COMP_KD = 0.08f`（增益，°/s→差速）、`LINE_GYRO_COMP_MAX = 7.0f`（陀螺仪项**独立小限幅**，保证只是小修正）、`LINE_GYRO_YAW_FILTER = 0.8f`（yaw_rate 一阶低通，越小越平滑/滞后越大）。
- **启用判定（`Navigation/map.c`）**：`Nav_IsStraightThrough()` = `nodes.lastNode.nodenum != 0`（首边未初始化哨兵）且（`|need2turn(nowNode.angle, nextNode.angle)| < STRAIGHT_ANGLE_THRESH(5°)` **或** `nodes.nowNode.step >= 90`）。`Nav_TurnAndAdvance()` 也用它决定"直行推 15cm（`Chassis_DriveDistance_Blocking(is_Line,15,...,edge_ignore=6)`）"。
- **排查**：
  - **越摆越大（助振）** → 翻转符号：`Chassis_GetLineGyroComp()` 里 `-chassis.line_gyro_kd` 改 `+`。
  - **高频嗡嗡** → 调小 `LINE_GYRO_YAW_FILTER`；**低频摆尾** → 调小 `LINE_GYRO_COMP_KD`；**输出顶限幅/发飘** → 调小 `LINE_GYRO_COMP_MAX`。
  - **高速小幅度震动（只在高速出现）** → ① 先 A/B：`KD=0` 确认是不是本项；② 按频率定方向：**细密高频（微分噪声主导）**→调小 `LINE_GYRO_YAW_FILTER`（0.8→0.5，增加平滑）；**固定几 Hz（滞后/相位裕度主导）**→调大 `LINE_GYRO_YAW_FILTER`（0.8→0.95，减少滞后）；③ **两种情况"降 `KD`"都有效**（相位裕度不足时降增益直接见效），**别靠加大 `KD` 求"快"**——那是加大环路增益，只会更抖。
  - ⚠️ **滞后量参考**：一阶低通 `LINE_GYRO_YAW_FILTER=a` 的截止 `f_c = -ln(1-a)/(2π·5ms)` → `a=0.8`≈**51Hz**、`a=0.5`≈22Hz、`a=0.4`≈16Hz；相位滞后 `atan(f/f_c)`，51Hz 档在 5/10/20Hz 仅约 6°/11°/21°。判断"是不是滤波滞后造成"要先看抖的频率。
  - ⚠️ **本项不随速度缩放**（循迹项是 `×|speed|/40`）：高速时循迹项变大、本项固定，易顶到 `LINE_GYRO_COMP_MAX` **饱和**，饱和后是固定幅度 bang-bang，易形成小幅极限环 → "高速抖"优先**降 `MAX`**，别加大 `KD`。
  - ⚠️ **滞后主要在上游（关键）**：本项微分的 `getAngleZ()` 是 IMU 的**融合角度帧**（`imu.c` 只解析角度帧；软件滤波 `filter_Open` 已为 0），模块内部融合本身低带宽/有滞后 → 本层 `LINE_GYRO_YAW_FILTER` 再怎么调收益有限。**根治：改用模块原生角速度帧**（WIT/JY62 系为 `0x52`，`gz` 即偏航角速度）→ `gcomp = -kd × gyroZ`，**无微分、无融合滞后、无微分噪声**，同时解决"慢"与"噪声"（需先抓原始帧确认模块确实发 `0x52`）。
  - **完全没效果** → 没触发直穿判定（看 `step>=90`/角差条件）或 `KD=0`。
  - 手推车头再松手：一两个来回停住=符号对；等幅/增幅=符号反或增益过大。
  - 整体关闭：删 `Nav_SegmentInit()` 里的 `Chassis_EnableLineGyroComp(...)` 调用，或 `LINE_GYRO_COMP_KD = 0`。

### 13.2 边寻线节点保护

- **在哪**：`Application/scaner.c` 的 `calc_left_edge()`/`calc_right_edge()` + `edge_run_len()`。
- **参数**：`EDGE_SEG_MAX_LED`（默认 3；被选中连续亮灯段长度 **>** 该值即判节点、丢帧）。
- **排查**：正常直线被误丢 → **调大**；过节点还在摆 → **调小**；节点处触发丢线急刹 → **调大**；想完全恢复旧行为 → 调到 99。
- **局限**：只覆盖"选中段被拉长（线与线粘连成宽线）"；"主线 + 独立 2 灯节点臂"（如 CLEFT bits13/14）拦不住，靠 `pos_detect` + 5 帧投票兜底。

---

## 14. 转弯前补偿距离（硬补偿）——现状分析与"能算就算"改造

> **状态：✅ 已实现并编译通过（2026-09-12）。** 完整报告见
> [转弯补偿拟合分析.md](转弯补偿拟合分析.md)（问题定位）与 [转弯补偿_能算就算方案.md](转弯补偿_能算就算方案.md)（落地方案）。

### 14.1 现状（务必先知道这三点）

1. **两张表 29 条，只有 21 条真正生效**，8 条是死值/无效：
   - 路由错分支（永远不生效）：`B3→N2→P2`=24、`N8→N3→P3`=18、`B8→N9→N10`=30、`B2→N1→P1`=18、`N5→N12→N11`=5、`N4→N5→N12`=6
   - 边表里根本没这条组合：`N2→N8→N10`=15
   - **被 `//` 注释掉**：`N13→N18→B5`=60
   - 原因：分支判定是 `(STOPTURN && |turn|>30) || |turn|>=90`，与表项所在的位置没有一致性约束。**调车时很容易调到一张没在跑的表。**
2. **覆盖率极低**：边表里"需要停车转"的 (入边,出边) 组合共 **209** 个，实测值只覆盖 **14** 个（约 7%），其余一律吃默认 **19**。
3. **表里 `angle` 是可信的**：与节点图上的真实走向只差一个固定的参考系旋转（图像分析结论）。
   ⚠️ 但**节点图是示意图不是按比例图**（`B9→N7` 表 5cm / 图上约 99cm），**不能用像素反推距离**。

### 14.2 为什么"硬补偿"不通用（根因）

硬补偿那一列**同时表达了两件不同的事**：

| 信号 | 内容 | 能否计算 |
|---|---|---|
| **A 真·转弯几何** | `Δ = L·(1−cosφ) + d(判据)`，`L` = 旋转中心→传感器板中心纵向距离 | **能**。8 条"平地+大角度"数据反解 `L` 中位 **16.7**、均值 **17.2**、范围 11.0~24.4，`1−cosφ` 与实测相关 **r=+0.71** |
| **B 段长补偿** | `map.c` 到达门槛是 `里程 ≥ 0.7×step`；`step≤18cm` 时车被**里程提前放行**，补偿实际在补段长 | **不能**，只能改数据。证据：`0.7×step + 补偿` 落在 17~38cm（正常检测起点量级） |

**崩掉的点有零反例的共同点**（用地图像素坐标定位后确认）：
①跷跷板/山/桥/平台（板子离地，检测时刻不可预测）②门区/X 交叉（多判据竞争）③入边 `step≤18cm`。
能对上的 8 条**全部是普通平地的单线节点**。

### 14.3 改造：能算就算、不能算保留原值（已实现，含 5cm 闸门）

```
Tier1  表里（kTurnTbl[]）有这条三元组              → 用实测值
Tier2  规则命中 且 |公式 − 实测| ≤ 5cm              → 用公式
Tier3  其它                                        → 保持原默认 19

规则：入边 func ∈ {NONE, DOOR}  且  step ≥ 20cm  且  100° ≤ |转弯| < 178°
公式：Δ = 19.0 × (1 − cosφ) + d(判据)
      d(CRIGHT)=+11   d(CLEFT)=−4   d(DLEFT)=−5   其他=−4
```

- **覆盖率**：Tier1 实测 7 + **Tier2 算出 39**（其中 33 条原本吃 19）+ Tier3 保留 163。
  （按"所有 209 个组合"口径，实测值名义上覆盖 14 个；叠加 5cm 闸门后走实测值的 7 个、走公式的 39 个。）
  ⚠️ "21 条生效"与"覆盖 14 个组合"是两个口径：21 = 表里去掉 8 条死值后**真正会被执行的表项数**（含入边是障碍/短段的），14 = 这些表项对应的 (入边,出边) 组合在 209 个里占的个数。
- **5cm 闸门挡回 2 条**（公式与实测差太多，一律用实测）：`C4→N20→P8`(35 vs 46.9)、`N4→N3→N8`(20 vs 29.1)。
- **闸门让机制自保护**：以后每往 `kTurnTbl[]` 补一条实测数据，公式与它矛盾就自动退回实测值 ⇒ 可以放心一条条加数据。
- **陀螺不停车转分支（`GetForwardDistanceBeforeGyroTurn`）未改动**：它 44 个组合绝大多数是小角度，现有表+默认 0 够用，而公式在 <90° 未经验证。
- ⚠️ 实现用 `cosf`（M7 只有单精度 FPU，不能用 `cos`）。
- ⚠️ **`func`/`step` 必须取"入边原始值"（`Node_Lookup(last)`），不能读 `nodes.nowNode.step/function`**：
  `door_set_pass_node()` 会在跑的过程中把 `step` 改成 72/50/36、`function` 改成 `NONE`。
- ⚠️ **不能用 `getNextConnectNode()` 的返回值当 `Node[]` 下标**：它返回的是连接表偏移，不是节点下标，
  只有目标节点恰好是 `from` 的第一个连接时才凑巧相等（本轮踩过）。

### 14.4 后续收益点（按性价比）

1. **复核 5 条 `step ≤ 18cm` 的段长**（`B8→N9`=1、`B9→N7`=5、`P8→N20`/`B2→N4`=12、`P6→N7`=18）—— 不用写代码，量尺子即可，那几条"怪值"可能自己就正常。
2. **补 3~5 条 90° 转弯的实测** → Tier2 从 39 条涨到约 90 条（R3 阈值放到 85°），闸门会自动筛掉不靠谱的。
3. **量"旋转中心→板中心"实距**，替换拟合出的 `L=19` → 公式从"拟合"变"求解"。
4. **给 `N8` 补条目** —— 全图最复杂的 X 交叉（两条对角线 + 四条门臂），两张表里一条都没有。
5. **门区段的 `step` 会在运行中被 `door_set_pass_node()` 改写**（72/50/36），所以按"运行时 step"分档的判据（如 R2）只能取边表原始值，这一点在新增规则时要留意。

### 14.5 分析脚本

`scripts/analyze/analyze_turn_comp_*.py`（7 个，只读源码做统计/校验，不进固件）：
`base`（生效/死值清单 + 每条命中判据，**已修"把注释掉的表项当生效"的解析 bug**）、
`step_check`（段长假设检验）、`rule`（判据验证）、`final_plan`（三层覆盖率）、
`gate`（★最终方案 + Tier2 完整清单）、`map_geom`（节点图几何 vs 表里 angle）、
`probe`（保真性 + 语法校验：从 `map.c` 抽取真实代码并断言可逆还原）。
详情见 [scripts/README.md](../scripts/README.md)。

### 14.6 本轮改动的文件

| 文件 | 改动 |
|---|---|
| `Navigation/map.h` | 新增 `enum { ARRIVE_* }` 判据编号 + `extern volatile uint8_t arrive_method;` |
| `Navigation/map.c` | `GetForwardDistanceBeforeTurn()`：18 条 if 链 → `kTurnTbl[13]`（**清掉 3 条死值**）+ Tier2 公式 + 5cm 闸门；新增 `Node_Lookup()`、`arrive_method` 定义、`TURN_*` 宏 |
| `Task/ArriveDetect_task.c` | `deal_arrive()` 增加 `out_method` 出参，10 处 `return 1` 各自写命中判据；定义 `arrive_method` 全局；任务里把它传给 `deal_arrive` |
| `Task/ArriveDetect_task.h` | `deal_arrive` 声明同步 |
| `Mission/config.h` | 新增开关 `TURN_CALC_ENABLE`（1=启用能算就算，0=完全回到原行为） |
