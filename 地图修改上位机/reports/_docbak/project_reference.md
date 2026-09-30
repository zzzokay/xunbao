# 项目参考文档 — xunbao（寻宝）

> **MCU**: STM32F750V8Tx | **工具链**: MDK-ARM **V5.32**（必须 V5，V6 会编译报错）| **RTOS**: FreeRTOS + CMSIS_V1 | **主频**: 216MHz
>
> **📌 读者对象**：**给 AI / 工具看**（空白上下文先读它，就知道"去哪儿改、怎么操作、怎么 git 暂存、怎么写文档"）。**人（接任者）读 [交接专用文档（新人先看我）](交接专用文档（新人先看我）.md)**。
> **用途**：本文档只保留**最终版本现状**（结构、数据流、底层映射、配置、改图方法、**§11 改码落点索引**、**§12 AI 工作流**），不追溯过程、不记改动（改动看 `git log`）；**坑与护栏**见 [README.md](README.md)（§9 附一行一条日志）。

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
上层：任务/导航
    Mission/mission_planner.c  决定 route[] ←─ QR/门/宝物线索
    Navigation/map.c:Navigation()  逐条执行 route[]（main_task 3ms）
        │  Chassis_SetMode() / Chassis_SetTargetSpeed()
        ▼
中层：底盘解耦 (Application)
    chassis_api.c: Chassis_MotorControl(mode,L,R,aim) —— 拿到"目标模式+左右速"，不碰 PID 细节
        ▼
底层：电机任务 (Task/motor_task.c，每 5ms，最高优先级 6)
    读编码器 → 按 PIDMode 分发：is_Line → scaner.c:Go_Line()（外环位置式巡线）
                             is_Turn → turn.c:Turn_Angle_Base()（陀螺仪转弯 PID）
                             is_Gyro → turn.c:Go_Angle()（陀螺仪直行 PID）
    → 外环输出 Fspeed → 设 motor_all.Lspeed/Rspeed → handle_target_speed() → 写 motor_L0/L1/R0/R1.target
    → Math/pid.c:incremental_PID()（内环速度 PID）→ motor_set_pwm()
        ▼
硬件层 (Motor)
    motor.c: motor_set_pwm(i,PWM) → TIMx->CCRy = PWM；TIM4/8/9 → 电机驱动 → 4 个直流编码电机 → 轮子
    ← TIM1/2/3/5 编码器反馈 → 回 motor_task 闭环
```

**数据三处核心**：`route[]`（路线，map.c 起点）、`nodes`（lastNode/nowNode/nextNode，map.c）、`motor_all`（速度/里程，chassis_api.c）。

**障碍/门/宝物时**：`map_function()` 分发到 `barrier.c` 的 `Stage()/Bridge()/Hill()/door()` 等物理动作；做完后由 `mission_planner.()` 改写 `route[]`。**门回程(`update_route_by_door_*`)改为"规划层门区禁用 + 极简必经点"**：`route_return_home()` 先用 `nav_set_edge_blocked()` 把门区 8 条边全部禁用（回程不再进门区、结构上不可能穿门掉头），再用 `wp={当前节点,[宝物平台],P2}` 让最短路算回家路；唯一例外是 door_2（额外放行 `N8→N3`，必须退回去重读 D4）。等价性由 `地图修改上位机/validate/_check_door_perm.py` 用改造前的 12 条手写路线当 golden 守住（12/12）。

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
| Turn→Line | 清 line_pid/TC（**不清 `Cspeed`**：它由调用方 `Chassis_SetTargetSpeed` 设，见 README §2.16） |
| Turn→Gyro | 清 gyroG_pid/TG（**不清 `Gspeed`**：同上） |
| →Turn | 清 gyroT_pid |

差速限幅统一在 `motor_all.Line_speedMax`，`line_pid_param.outputMax` 固定 ±80。`Go_Line` 中 `Fspeed *= |speed|/40`、`Go_Angle` 中 `GGspeed *= |speed|/50`（差速按速度缩放，使路径形状与车速无关）。

**PID 覆盖纪律（09-26 补）**：`Chassis_OverrideLinePid/GyroPid/TurnPid()` 配对的 Restore 一律写在**同一函数的正常出口**。
`Chassis_RestoreLinePid/GyroPid/TurnPid` 都是 `if (override_active)` 的阀门式还原；漏一次 ⇒ `override_active` 常驻 1，
之后任何 Override 都不再保存真值。⚠️ 本文件 `chassis_api.c:546` "陀螺仪模式和转弯模式共用 `gyroG_pid_param`" 的注释**已过时**：
转弯（`Turn_Angle_Base`，`is_Turn`）走**独立的** `gyroT_pid_param`（由 `Chassis_OverrideTurnPid` 改，`Chassis_Turn_By_StopGyro_Blocking` 用 6/0/90，
自带 Restore 自洽）；陀螺直行 `Go_Angle`（`is_Gyro`）走 `gyroG_pid_param`（默认 2/0/5，`GyroG_speedMax=100`）。

### 5.4 转弯逻辑（turn.c）
`need2turn(now,target)` 归一到 (-180,180]；`getAngleZ()=yaw+compensateZ`；`Turn_Angle_Base(Angle,ratio,force_thr)` 原地转基函数（误差<2°判到位、低速给±7死区补偿）；`Stage_turn_Angle` 平台转(force_thr=150°)；`Turn360Step` 360°梯形速度曲线（加速40°→全速→358°前减速）；`Go_Angle` 陀螺仪直行。

---

## 6. 传感器数据流（从哪里来）

**循迹**：16 路 GPIO/DMA → `bsp_linefollower` → `scaner.c:Scaner_Update()`（单入口；`line_data[5]` 滑动窗口，static 仅本文件访问）→ `Get_scaner_error()`（多数决+簇投票，丢线时返回上一次有效错误）→ `Go_Line()` 外环 PID → 差速。`value_calculation` 四种 `TRACK_` 模式均显式 case；`Scaner_ClearLineData()`/`Scaner_IsLineLost()` 为外部接口。
**寻中线**：亮灯总数≥4 保守判中心(error=0)；中心两灯(7,8)同亮判中心；否则扫描**连续亮灯段**（不允许跨空隙），段内只取最靠中心 2 灯算平均位置。
**寻左/寻右（边寻线）**：`calc_left_edge`/`calc_right_edge` 取最靠边的一段（最多 2 灯）；**节点保护**——用 `edge_run_len()` 量该段连续长度，`> EDGE_SEG_MAX_LED`（默认 3）判为节点横向线/粘连 → `return -1`（帧记 `ALL_ERR`，交 5 帧历史保持上次有效误差），避免节点处误差大跳变。参数 `EDGE_SEG_MAX_LED` 在 `scaner.c`（与 `MAX_LED` 同处）。⚠️ 局限：只覆盖"选中段被拉长（粘连宽线）"，"主线+独立 2 灯节点臂"拦不住，靠 `pos_detect`+5 帧投票兜底。
**IMU**：USART3 DMA + IDLE 中断 → `imu.c` 0x55 协议 10 字节校验 → `imu.yaw/roll/pitch`(±180°)；`IMU_CalibrateZero` 10 次采样归零，`getAngleZ()=yaw+imu.compensateZ`。
**视觉**：USART6 → `K210.c`（`WaitFor_QR`→`flag_line_clue`/`flag_clue_stage_A/B`；`Door_ReadPass`→`door_pass[5]`；OCR→`flag_clue_A/B`→`treasure`）。三条链路各自「一轮干等 `MAIXCAM_QR/OCR/COLOR_WAIT_TICKS`(800/800/1000)」，但**轮内每约 0.48s 重发一次模式指令**（`barrier.c` 顶部的 `MAIXCAM_RESEND_TICKS_3MS`/`_2MS`）⇒ 轮内 open 次数 1→5，见 `README.md` §2.20。

---

## 7. Navigation() 执行流程（map.c）

```
Navigation()
├─ near_end==0（巡线行驶）
│   ├─ SEG_INIT：清里程、设巡线模式/速度、启用游龙+翘头保护
│   ├─ SEG_MID_SWITCH：里程≥50% 切换巡线模式
│   └─ SEG_PREP_ARRIVE：里程≥60% 降速
└─ near_end==1（节点处理）
    ├─ Nav_NearEnd：map_function()（阻塞式动作）→ 等 ArriveDetect 判到达
    ├─ Nav_TurnAndAdvance：转弯（follow/停车原地转/陀螺仪）
    └─ Nav_PostProcess：查 cross_event → 推进节点
```

`nodes.nowNode.function` 是**会被改写的**：`Stage/Stage_Home/South_Pole` 结束时会**保留**它，但 `do_Upright()`(View) 会清成 0
⇒ **判断"刚才做过什么"不能读它**（现状仍会补走那 15cm，见 [README.md](README.md) §2.9）。
`Nav_TurnAndAdvance()` 的"直穿节点"分支只排除**平台类**功能：`UpStage` / `UpStageHome` / `BSoutPole`。

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
| `UPRIGHT_NEED_TREASURE` | `1` | 直立景点（`View`，`N14`/`N16`）门控：`1`=只有**宝藏已取到手**（标志 `treasure_taken`）与第二轮才做动作，取宝前（一轮去程 `N12→N16` + 一轮回程 `N18→N16`）都当普通节点直穿；`0`=边表 `func=View` 就做（旧行为）。⚠️ 判据是 `treasure_taken`，**不是 `treasure`**（`treasure` 只是线索算出的宝物平台编号）。见 [README.md](README.md) §2.14 |
| `UPRIGHT_TOUR_ENABLE` | `0` | 直立景点**巡回**（只管走位）开关，**默认关**：`1`=一轮取宝**之后**按宝物平台绕近的景点（`P3`→`S1`、`P4`→`S2`；取宝之前一次都不去）、二轮 `P3`/`P4` 之后固定两个都绕（+806cm）。落点 `mission_planner.c` 的 `plan_treasure_return` / `route_return_home` / `get_newroute`。⚠️ `S1`/`S2` 的 `func` 是 **`View1`**、`map_function()` 无 `case` ⇒ **只走位、不做动作不播报**（要得分需另写 `do_Upright1()`）。见 [README.md](README.md) §2.19 |
| 门区段 | — | `DOOR_LEN_*`(6)、`DOOR_RETREAT_*`(4)、`ANGLE_*`(2，反向用 `ANGLE_REV(a)`) |
| OCR 摆头角度 | `OCR_HEAD_*`(5) | ⚠️ **定义了但没接上**：`OCR_HEAD_MID`(1500) / `FAR_RIGHT|FAR_LEFT`(1350/1650，基准位 ±150) / `NEAR_RIGHT|NEAR_LEFT`(1320/1680，前进 4cm 靠近后 ±180) 共 5 个宏在 `config.h`，但**全工程没有一个 `.c` 引用**；`WaitFor_OCR()` 仍写死 `moveServo(0, 1440/1560/1500, 1000)`，`head_right_left`(1=右/2=左/0=中) 语义未变。**要用先接上** |
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

> ⚠️ 以 `Navigation/map.h` 的 `enum MapNode` 为唯一准绳（下表已按真实枚举核对）。**解析时必须先剥注释再编号**：
> `C1`/`C2` 是注释态（不占编号），否则从 `C3` 起全部错位（会把 P8 算成 49、实际 46）。根因见 [README.md](README.md) §5.1。

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
4. 跑 PC 校验：`地图修改上位机/validate/_weight_calib.py`（改边/权重后）、`地图修改上位机/validate/_check_csr.py`（增删边后）、`地图修改上位机/validate/_check_door_logic.py`（改门逻辑后）；编译 0 error 再上真车。

### 9.4 必经点原则（改 `mission_planner.c` 的 `wp` 时必守）
`wp` **只写**「起点 + 门节点(`N5/N8/N12/N10/N3`) + `P` 平台 + 终点」；**别加平台入口锚点**（P5 前 `N13`、P6 前 `N9`、far 入口 `N4`）——P5/P6 是支路、P6 跷跷板单向由图强制，规划器必然经过它们，写进去冗余。**门节点必须**，否则会跨未确认/单向门。改 `wp` 后可用 `地图修改上位机/validate/_check_wp.py` 验证"删了某个必经点路线不变"。
**唯一例外**：直立景点巡回打开时（`UPRIGHT_TOUR_ENABLE=1`）会额外把 `S1`/`S2` 写进 `wp` —— 它们是**死胡同支路**（`N3`/`N6` 岔口往返），
规划器**主动避开**（`NavObsPenalty[View]=NavObsPenalty[View1]=100`），不写进 `wp` 永远到不了；验证要用它专用的
`地图修改上位机/tools/sim_upright_tour.py`（`_check_wp.py` 的 golden 是硬编码的、不含 `S` 节点）。

### 9.5 图形化改图工具 `地图修改上位机/map_editor/`（⭐ 推荐先用它，别手抠边表）

> ⚠️ **目录迁移提示**：这些工具原先在仓库根的 `scripts/` 下，现已整体迁到 `地图修改上位机/`（`map_editor/`、`validate/`、`tools/`、`reports/`）。
> `README.md` §9 里 2026-09-26 之前的日志条目仍写旧路径（那是当时的真实情况，保留不改）；**执行命令一律按本文档的路径**。

手改 124 行边表容易改漏（`NAV_EDGE_COUNT`、分组注释、`flag` 位、正反向边）。用编辑器改，改完导出 C 代码，或让它直接写回（会先备份）。
📄 [map_editor/README.md](../地图修改上位机/map_editor/README.md)（给人：使用说明）｜🤖 [map_editor/AI_CONTEXT.md](../地图修改上位机/map_editor/AI_CONTEXT.md)（**给 AI：架构、坐标系、必须保住的不变量、踩坑、改动指引 —— 改这个工具前先读它**）

```bash
python 地图修改上位机/map_editor/map_editor.py    # 打开即当前固件地图；零依赖（tkinter 自带）
```

- **两条心智模型**：① **节点位置只是示意图** —— 长度只认 `step` 数值，**节点随便拖不影响任何数值**，图只表达"连接关系 + 角度关系"；
  ② **导出逐字段保真** —— 不做编辑时导出的边表与源文件完全相同（`_selftest.py` 断言差异 0 处）。
- **底图对齐**：自动把 `寻宝地图/节点图.jpg` 半透明铺底；`SEED_POSITIONS` 就是那张 **1729×1080 原图的像素坐标**（1:1）。
  ⚠️ `C2/B4/C6/C7/C8/G1` 六个节点原图**没画**，坐标是估的。
- **能力**：拖节点；Shift 拖出连线；点选改 `from/to/flag/angle/step/speed/func/comment`（`angle/step` 可直接写 `ANGLE_*`/`LEN_*`/`DOOR_LEN_*` 宏，按 `config.h` 当前 `USE_FIELD` 求值）；
  flag 25 位勾选板；补反向边；校验（孤立/单向/重名/宏能否求值）；必经点最短路（与固件同一套 Dijkstra + `NavObsPenalty`）；
  导出 `NavEdgeTbl[]`/`enum MapNode`/`NAV_EDGE_COUNT`/`route[]`；写回固件（**先自动备份**到 `map_editor/backups/`，有 error 级问题拒绝写回）。
- ⚠️ **工具只保证"导出文本正确"，不保证"业务自洽"**：增删节点后必须自己同步检查 `mission_planner.c` 的 `wp`、门逻辑、宝物表、`barrier.c` 的节点比较（节点编号 = 枚举顺序）。
- **转弯前补偿也能可视化改**（2026-09-29 新增）：左栏「**⟲ 转弯补偿…**」把 `map.c` 的两张表
  （`kTurnTbl[]` + 陀螺 if 链）与 `TURN_*` 公式参数搬进界面，可增删改 + 覆盖总览 + 画布高亮，
  改完显式「写回 map.c…」（先备份）。现状、参数可信度与写回口径见 **§14**。
- ⚠️ **不变量：写回 `config.h` 必须原样保住行尾注释**（2026-09-15 踩过，**直接编挂整份工程**）。已抽成纯函数 `App._rewrite_config_macro()`，
  `_selftest.py` 第 10 节守着它（6 条合成用例 + **真实 `config.h` 原值干跑、逐字节不变**）。现象与根因见 [README.md](README.md) §3.1。
  另注：`LEN_N22B7`/`DOOR_LEN_*` 这类宏在 `#if USE_FIELD==FIELD_SCHOOL / #else` **各定义一次**，写回只改**第一处** ⇒ 切到 `FIELD_COMP` 再改会落错分支（当前 `USE_FIELD=FIELD_SCHOOL`，暂时无害）。

### 9.6 `MAP_DEBUG` 地图调试路线（跑单点/多点用，与比赛 `wp` 无关）
只改 `Mission/config.h` 三个宏，`map.c:mapInit()` 的 `#if MAP_DEBUG` 分支用 `nav_plan_waypoints()` 自动生成 `route[]`：
```c
#define FIRST_POINT   N6    /* 调试起点（MapNode 枚举名） */
#define VIA_POINT     0     /* 调试途径点：填 0 = 不用途径点（退化成两点路线） */
#define END_POINT     P3    /* 调试终点 */
```
- 语义 = `wp = {FIRST_POINT, [VIA_POINT], END_POINT}` 的**必经点**规划；⚠️ **`S1=0`** ⇒ S1 不能当途径点（`0` 是"不用"哨兵）；
  途径点是**支路/平台**时（如 `P4`/`P5`）会"去一趟再折返"（`route[]` 里出现回到主路的节点），正常。
- `route[]` 语义不变：`nodes.nowNode` = 第一跳，`route[]` 从 path[2] 起，末尾 `0xFF`。
- **陀螺仪参考角（重要）**：`main_task.c` 在 `mapInit()` 后立刻 `mpuZreset(get_latest_yaw(), nodes.nowNode.angle)`，
  而 `nowNode` = 「`FIRST_POINT`→第一跳」这条边 ⇒ **参考角 = 该边的 `angle`**（地图里**没有"节点角度"**，只有边有 `angle`＝本段航向）。
  ⇒ **摆车必须把车放在 `FIRST_POINT`、车头顺着 `FIRST_POINT`→第一跳的方向**，否则整轮所有转弯一起偏这么多。
  - 参考角随"第一跳"变：`N6→N5=0°`、`N9→N10=180°`、`C7→B10=-90°`、`N8→N3=-35°`；**途径点也可能改掉第一跳**（`VIA=P5`→第一跳 C1=50°，`VIA=P4`→起手就上平台）。
  - 校准在 `main_task.c` 的**红外等待之前**：**校准后别再用手机械摆正车头**（`getAngleZ()` 是相对量会跟着转），要重校就复位一次。
  - 全工程统一语义：`barrier.c:397`（巡线稳定重校）与 `ArriveDetect_task.c:29` 同样用 `nowNode.angle`。
  - ⚠️ 唯一小坑：`FIRST_POINT=S1`(`0`) 时 `nodes.lastNode.nodenum==0` 会撞上 `Nav_IsStraightThrough()` 的"首边未初始化"哨兵，只影响第一段是否加陀螺阻尼，**不影响角度**。
- ⚠️ **场次(`USE_FIELD`)必须同步**：`validate/_weight_calib.py` 顶部的 `USE_FIELD` 是手写常量（默认 `FIELD_COMP`），与 `config.h` 不同步时镜像算出的"调试路线"≠车上实际（**09-11 踩过**：`FIRST=N6,VIA=N3,END=P4` 门惩罚 0 + 学校长度下是 `N3→N8→N5`、比赛长度下是 `N3→N4` 掉头）。
  已加 `sync_field_from_config()`（**`config.h` 里有 4 个 `#if USE_FIELD == FIELD_SCHOOL` 块，必须全部遍历**，只取第一块会漏门区长度）；`_check_map_debug.py` 自动按 `config.h` 覆盖长度宏并打场次告警；`_check_*` 的 golden 仍按 `FIELD_COMP`；镜像 `OBS_PENALTY` 已与 `nav_planner.c` 对齐（`DOOR`→60、`BLBS` 60→70）。
- ⚠️ **门惩罚 = 60**（`nav_planner.c: NavObsPenalty[14]`，09-11 从 0 提上来；"为什么是 60"见 [README.md](README.md) §5.2）。实测偏差（学校场地 `N3→P4`）：

  | `N3→P4` 两种走法 | 门惩罚 0（旧） | 门惩罚 60（现） |
  |---|---|---|
  | 原路折返 `N3→N4→N5→N6→P4` | 510 | 510 |
  | 穿门 `N3→N8→N5→N6→P4` | 493(学校) / 523(比赛) | 613 / 643 |
  | 规划器选 | **穿门**（学校） | **折返** |
  
  取 60 = 与 `UpStage` 同量级。回归证据：`NavObsPenalty[DOOR]` 在 **0→300** 全程，15 条参考路线 / 12 条门回程 golden / 门逻辑表 / wp 不变量**全部不变**。
  ⚠️ **残余风险**：门节点"从哪一侧进"由**成本最省**决定（`door()` 用 `lastNode/nowNode` 判 `D2/D3/D4/D5`）⇒ 提权重后若某个 wp 组合换了进门方向，读的灯也换 ⇒ **必须实车复核门区**。`DOOR1`(18) 目前**无任何边使用**。
  另：**必经点交界处的转弯在规划里不计费**（`nav_shortest_path` 对段首边只算 base）⇒ 别用"整条 route 总成本"评估改动。
- ⚠️ **调试路线一进 DOOR 边就不再是你的路线**：到点后 `map_function(DOOR)→door()` 开头 `map.point=0; route[0]=0xFF;` 会**清空 `route[]`**，之后跑比赛门逻辑；脚本检测到路线经过 DOOR 边会告警。想纯跑路线就别让必经点/终点把它带进门区。
- 校验：`validate/_check_map_debug.py`（穷举 54×54 断言 `VIA_POINT=0` 与两点行为逐字一致 + via 真经过途径点；第 4 节打印**参考角/摆车方向/逐段航向**，对"180° 原路折返"与"经过 DOOR 边"告警——平台节点上的折返标注为"平台内部转身，正常"）、`validate/_syntax_map_debug.py`（抽该代码块做 GCC 语法检查）。

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
| **地图图形化编辑（辅助工具，不进固件）** | `map_editor.py`（界面）/ `map_model.py`（解析+导出+校验+Dijkstra） | `地图修改上位机/map_editor/`（见 §9.5） |
| 底盘/电机/传感器 | `Chassis_*` API（`Chassis_Init/SetMode/SetTargetSpeed/SetTrackMode/MotorControl/Brake/DriveDistance_Blocking/Periodic_Update_5ms/OverrideLinePid`） | `Application/chassis_api.c` |
| 16 路巡线 | `Scaner_Update()` / `Go_Line()` / `Get_scaner_error()` | `Application/scaner.c` |
| 转弯 | `Turn_Angle_Base()` / `Go_Angle()` / `Stage_turn_Angle()` / `Turn360Step()` | `Application/turn.c` |
| **转弯前补偿距离** | `GetForwardDistanceBeforeTurn()`（停车转，默认19）/ `GetForwardDistanceBeforeGyroTurn()`（陀螺转，默认0） | `Navigation/map.c` |
| 内/外环 PID | `incremental_PID()` / `positional_PID()` | `Math/pid.c` |
| 电机 PWM / 编码器 | `motor_set_pwm()` | `Motor/motor.c` |

---

## 11. 改码落点索引（坑的「为什么」见 [README.md](README.md)）

> 现象/根因/护栏的**唯一归属**在 [README.md](README.md) §1~§8。本节只列「改这个功能必须同时动哪几处」，不重写根因（重复必然漂移）。

| 要改的东西 | 必须同时动 / 别踩 | 详见 |
|---|---|---|
| **新增障碍类型** | `enum barriers` **只能追加末尾**；同步扩 `NavObsPenalty[]`（1..19）。⚠️ `map_editor/_selftest.py` §8 按**数组位置**比对，抓不到错位 | README §2.1 |
| **边表写新 `func`** | `map_function()` 里补对应 `case`，否则落 `default:` 静默不触发（`View1` 现有 **5 条**边无 `case`：`N14→S3`/`N15→S4`/`N16→S5` + `N3→S1`/`N6→S2`） | README §2.2 |
| **增删边** | 同步 `NAV_EDGE_COUNT`（编译期尺寸断言兜着，漏改会报错） | README §2.3 |
| **改门区路线** | `door()` 开头**清空 `route[]`**；`door_retreat()` 改 `nodes.nowNode`；`door_set_pass_node()` 改 `Node[].function/speed/step`；⚠️ `DOOR_D5_BACK` 的"其余组合"**无兜底** | README §5.5~§5.8 |
| **改 `wp` / 读路线** | `getNextConnectNode()` 返回**连接表偏移**≠下标；`route[map.point]==0xFF` 是结束哨兵；改完保证相邻节点**有向连通** | README §5.4 |
| **用 `Chassis_Override*Pid()`** | Restore 必须在同一函数的**正常出口**（状态机 `while` 之外），别放 `default:` 这类走不到的分支 | README §2.7 |
| **直立景点 `do_Upright()`** | ① 在**边长 70%** 处就被调用（`B10→N14` 的 `step=100`）；② `step≥90` 时直立结束后**会再补走 15cm**（N16 不会）；③ 结尾清 `nodes.nowNode.function` ⇒ 判断"刚做过什么"别读它；④ 两次转向传 `TURN_TIMEOUT_DEFAULT`(2500ms) / 固定容差 2°（见下一行）；⑤ 受 `config.h` 的 `UPRIGHT_NEED_TREASURE` 门控，判据是 `barrier.c` 的标志 `treasure_taken`（`Stage_CollectTreasure()` 置位）而非 `treasure`；取宝前一次都不做；⑥ 打印 `[UPRIGHT] turn#N / turn#N done` | README §2.8 / §2.9 / §2.14 |
| **直立景点巡回（`S1`/`S2`）** | 开关 `UPRIGHT_TOUR_ENABLE`（`config.h`，**默认 0**）；插点三处且**必须都在宝物平台之后**（一轮取宝前去 = 结束比赛）：`mission_planner.c` 的 `plan_treasure_return()` / `route_return_home()`（⚠️ `wp[3]→wp[6]` 已扩容，别改回）/ `get_newroute()`；⚠️ **两处都要插**（该门边去程被 `door_set_pass_node()` 改成 `func=NONE` 时不进 `door()`）；⚠️ `S1`/`S2` 的 `func` 是 `View1` 且**无 `case`** ⇒ 只走位、不得分；⚠️ `S1 = 0` 会撞 `Nav_IsStraightThrough()` 的 0 号哨兵 | README §2.19 |
| **排查"车停住不说话"** | 按串口标签分层：`[PROTECT]`（保护，**都有播报**）/ `[HARD-STOP]` / `[HANG]` / `[DOOR]`；"完全没声音" ⇒ 只可能是 `CarBrake_Stop()`（9 处）或两个无超时等待（`Want2Go` / `door()` 等 8 灯） | README §2.10~§2.11 |
| **「转弯后切回巡线，车不动」** | `Task/motor_task.c` 的 `handle_mode_switch()`：**迁移只清「离开模式」的渐变/给速值**；⚠️ 进 `is_Line` 的路径必须紧跟一次 `Chassis_SetTargetSpeed`；⚠️ `chassis_api.c` 的 `is_Free/is_No` 分支**不能删**（`CarBrake()` 靠它停车） | README §2.16 |
| **MaixCam（二维码/数字/颜色）读不到 / 只发不解析** | 三者是**同一条链**（`K210.c` 的 `Maxicam_ProcessRxByte`）；接收是**单字节中断** ⇒ `huart6` 每个发送点之后**必须**补一次 `HAL_UART_Receive_IT`（`K210.c` 3 处 + `openmv.c` 2 处）；⚠️ 判"接收空闲"用 `huart6.RxState`，**别用 `HAL_UART_GetState()`**；⚠️ 改 `stm32f7xx_it.c:465` 那句必须**同一轮**把中断里的 `close_Maxicam()` 移出；⚠️ `Stage_Action()` 扫描失败无出口 | README §2.15 |
| **改摄像头「等待/重开」节奏** | 两个旋钮都在 `barrier.c` 顶部：`MAIXCAM_QR/OCR/COLOR_WAIT_TICKS` = 一轮总等待拍数（每拍 3ms）、`MAIXCAM_ROUND_BLOCKS` = 一轮切成几块（= 一轮重开几次）；`barrier.c` 顶部三个旋钮：`MAIXCAM_QR/OCR/COLOR_WAIT_TICKS` = 一轮总等待拍数；`MAIXCAM_RESEND_TICKS_3MS`(160×3ms) / `MAIXCAM_RESEND_TICKS_2MS`(240×2ms) = **轮内重发间隔 ≈0.48s**；⚠️ 重发**不许**加 `close_Maxicam()`；诊断看 `[MODE] … try/ack/n` | README §2.18 / §2.20 |
| **颜色（红绿灯）读不到 / `read=1` 分不清** | 与二维码、数字**同一条链**；⚠️ 兜底 `NO_PASS`(=1) 与真读到黑同为 1 ⇒ 看 `raw=`（**`raw=0` 才是没读到**）；⚠️ 映射 `barrier.h`(2绿/3蓝/1黑) 与 `Door_ReadPass` TODO 注释(1绿/2黄/3红) **互相矛盾**，须对齐相机端；⚠️ 读颜色**之前** `door()` 的 `while (Scaner.ledNum<8)` **无超时**；⚠️ `Open_COLOR_R()`/`Color_Right` 是**死代码**；`MAIXCAM_COLOR_WAIT_TICKS` 实际 2.0s（注释写 4s 是错的） | README §2.17 |
| **改原地转向"到位"精度 / 治"转不到位就无声死等"** | 到位容差**固定 2°**（`chassis_api.c` 的 `TURN_TOL_RELEASE`，须与 `turn.c: Turn_Angle_Base()` 的 2.0f 同步）；超时宏 `TURN_TIMEOUT_DEFAULT`(2500ms) 在 `chassis_api.h`，逐级传入 `Chassis_Turn_By_StopGyro_Blocking` → `Chassis_TurnToAngle_Blocking`；⚠️ 超时**只退出等待循环、不停电机** ⇒ **只能给"退出后马上切模式 / 停车"的调用点用**（⚠️ `barrier.c` 273/282/291/300/440/1558 共 6 处**块内无接管者**） | README §2.13 |
| **清"未引用"符号** | ⚠️ 别误删：`pid.c` 的 R1（注释态死代码）、`motor_task.c` 5ms 内的 printf、`DWT->CYCCNT` 的使能函数 `timing_dwt_init()`（要恢复周期测量需同时恢复它与调用） | — |
| **在 `if/else` 后插语句（如加打印）** | ⚠️ 先看该分支**有没有大括号**：无括号分支只绑定紧随的一条语句，插一行就会把后面的语句挤出分支。09-26 在 `mission_planner.c` 栽过（`CarBrake_Stop()` 变成无条件执行） | README §2.12 |
| **改转弯前补偿（`map.c` 两张表 / `TURN_*` 公式参数）** | ① **先别手抠**：用 `地图修改上位机/map_editor/` 左栏「⟲ 转弯补偿…」，它按源码实时算出"这一行会不会生效"；② 表1 `kTurnTbl[]`、表2 `GetForwardDistanceBeforeGyroTurn()` 各管一个**分支**（分支由 `Nav_TurnAndAdvance()` 判，不在表里）；③ 写回**只动三处**且护栏 typedef `kTurnTbl_node_check` 必须跟着表项重生成（节点数上限 `MAP_NODE_LIMIT`，`nav_init` 的节点数一起改）；④ 开关 `TURN_CALC_ENABLE` 在 `config.h`，**当前 0** | §14 / README §3.4 |
| **给 `map.c` 做语法检查** | RVDS `__asm{}` 过不了 GCC ⇒ 抽代码块套探针 TU 用 `arm-none-eabi-gcc -fsyntax-only` | README §4.4 |

---

## 12. AI 工作流（**开工前必读**；⚠️按此操作，避免丢代码）

> **开工先读什么**：[README.md](README.md) §1~§8（坑与护栏，**唯一归属**）+ 本文件的现状章节
> （§9 改地图 / §11 改码落点索引 / 本节）。改地图工具另读 `地图修改上位机/map_editor/AI_CONTEXT.md`。
> 《交接专用文档（新人先看我）》**是给人的，AI 不必读**。
> **收尾写什么**：坑 → README §1~§8 对应主题；日志 → README §9 追加一行（见下面第 6 条）。

1. **改任何代码/文档前，先暂存当前工作树**（血的教训）：
    本工程**未提交的改动只在工作树**，一旦被 `git checkout`/`reset`/本地覆盖就很难找回。约定：**每次动手前先 `git stash push`（改完 `git stash pop` 回来并核对），或直接 `git commit -m "..."`**。尤其 `mission_planner.c`/`barrier.c`/`nav_planner.c`/`map_message.c`/`config.h` 的规划器改动，务必先暂存。
2. **编译**：MDK 工程 `MDK-ARM/test1.uvprojx`，用 **Keil V5.32** 编译，预期 0 Error（可容忍未使用变量类 Warning）。改地图/权重后在 MDK 编译确认 0 error 再上真车。
3. **文件编码**：全工程 **UTF-8**（无 BOM）。写源码保持 UTF-8。
4. **include 规则**：所有源目录已在 Keil/EIDE 的 IncludePath 里，**一律用短写** `#include "xxx.h"`（全工程统一，不再用 `../Xxx/xxx.h`）。前提是**裸名必须唯一**：工程里 `sys.h`（`Application/`）与 `adc.h`（`Core/Inc/`）原各有两份同名文件，已分别删掉 `USMAT/sys.h`、`Module/adc.{c,h}` 消除歧义；**新增同名头文件前先确认不会撞名**，否则 `-I` 顺序会静默改变命中对象。`#include` 的查找顺序是「当前文件所在目录 → `-I` 列表顺序」。
5. **别做的操作**：`motor_task` 5ms 循环内别加阻塞/大量 `printf`（破坏周期）；别把负值写进 PWM CCR（反向换 TIM 通道极性并取反编码器）；CubeMX 重新生成后要注释 `main.c` 定时器中断回调 + `stm32f7xx_it.c` 的 `USART3_IRQHandler`。
6. **改完同步文档**：更新本文件（现状）**+ 把新踩的坑按主题追加到 [README.md](README.md) §1~§8**（那些小节只写"坑在哪、怎么避"）
   **+ 在 [README.md](README.md) §9 修改日志追加一行**（`日期：一句话`，不改写旧行；改动清单不写在本文件，细节留给 `git log`）。
7. **验证方法**：`地图修改上位机/validate/_weight_calib.py`（复现参考路线/权重灵敏度）、`地图修改上位机/validate/_check_csr.py`（CSR 连通性）、`地图修改上位机/validate/_check_wp.py`（必经点删除不改路线）、`地图修改上位机/validate/_check_door_logic.py`（门逻辑表驱动）、`地图修改上位机/validate/_check_door_perm.py`（门回程边禁用 golden）、`地图修改上位机/validate/_check_map_debug.py`（`MAP_DEBUG` 起终点/途径点路线）、`地图修改上位机/validate/_syntax_map_debug.py`（`map.c` 的 `MAP_DEBUG` 代码块 GCC 语法检查——`map.c` 整体因 RVDS `__asm` 编不过，故抽块检查）；这些脚本只做校验/分析，不进固件。
8. **改地图/路线用图形化工具，别手抠 124 行边表**（容易漏改 `NAV_EDGE_COUNT`/正反向边）：`python 地图修改上位机/map_editor/map_editor.py`，能力与坑见 §9.5。改完仍要跑上面 7 个脚本 + Keil 编译。

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
  - **完全没效果** → 没触发直穿判定（看 `step>=90`/角差条件）或 `KD=0`；**手推车头再松手**：一两个来回停住=符号对，等幅/增幅=符号反或增益过大；
    **整体关闭**：删 `Nav_SegmentInit()` 里的 `Chassis_EnableLineGyroComp(...)` 调用，或 `LINE_GYRO_COMP_KD = 0`。

### 13.2 边寻线节点保护

- **在哪**：`Application/scaner.c` 的 `calc_left_edge()`/`calc_right_edge()` + `edge_run_len()`。
- **参数**：`EDGE_SEG_MAX_LED`（默认 3；被选中连续亮灯段长度 **>** 该值即判节点、丢帧）。
- **排查**：正常直线被误丢 → **调大**；过节点还在摆 → **调小**；节点处触发丢线急刹 → **调大**；想完全恢复旧行为 → 调到 99。
- **局限**：只覆盖"选中段被拉长（线与线粘连成宽线）"；"主线 + 独立 2 灯节点臂"（如 CLEFT bits13/14）拦不住，靠 `pos_detect` + 5 帧投票兜底。

---

## 14. 转弯前补偿距离（硬补偿）——现状与"能算就算"机制

> **状态：已实现并编译通过（2026-09-12）；⚠️ 开关 `TURN_CALC_ENABLE` 当前 = 0（关闭，行为与改造前逐字一致）。**
> **本节自包含**。原始过程报告与当时的分析脚本属过程产物（已于 09-26 清理），结论全部并入本节。
> 改这套机制前**先读 14.3 的参数可信度表与 14.7 的量化依据**，否则容易以为公式"准"，其实只是"错得少一点"。

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
Tier1  表里（kTurnTbl[]）有这条三元组        → 用实测值
Tier2  规则命中 且 |公式 − 实测| ≤ 5cm       → 用公式
Tier3  其它                                 → 保持原默认 19

规则：入边 func ∈ {NONE, DOOR}  且  step ≥ 20cm  且  100° ≤ |转弯| < 178°
公式：Δ = 19.0 × (1 − cosφ) + d(判据)      d(CRIGHT)=+11  d(CLEFT)=−4  d(DLEFT)=−5  其他=−4
```

- ⚠️ **各 `d` 的可信度差别极大，动公式前先看这张表**（样本少的那几个只是"能凑出个数"）：

| 判据 | 样本 | 组内拟合 | 可信度 |
|---|---|---|---|
| `d(DLEFT)` | 5 | **5/5 全通过**（残差 −3.7~+1.3） | **最可信**，可直接用 |
| `d(CRIGHT)` | 5 | 4/5 通过；`P1→N1→B2`(45°) 差 22cm | 尚可，**小角度端不可信** |
| `d(CLEFT)` | 9 | 5/9 通过（`B8→N9→C3` 差 31cm） | **只能当中位数用** |
| `d(MCLEFT)`/`d(DRIGHT)`/`d(MUL2MUL)` | 各 1 | — | 单样本，等于拍脑袋 |

- **覆盖率**：Tier1 实测 7 + **Tier2 算出 39**（其中 33 条原本吃 19）+ Tier3 保留 163。
  ⚠️ "21 条生效"与"覆盖 14 个组合"是两个口径：21 = 表里去掉 8 条死值后**真正会被执行的表项数**（含入边是障碍/短段的），14 = 这些表项对应的 (入边,出边) 组合在 209 个里占的个数。
- **5cm 闸门挡回 2 条**（公式与实测差太多，一律用实测）：`C4→N20→P8`(35 vs 46.9)、`N4→N3→N8`(20 vs 29.1)。
- **闸门让机制自保护**：以后每往 `kTurnTbl[]` 补一条实测，公式与它矛盾就自动退回实测 ⇒ 可放心一条条加数据。
- **陀螺不停车转分支（`GetForwardDistanceBeforeGyroTurn`）未改动**：44 个组合绝大多数是小角度，现有表 + 默认 0 够用，而公式在 <90° 未经验证。
- ⚠️ 实现用 `cosf`（M7 只有单精度 FPU，不能用 `cos`）。
- ⚠️ **`func`/`step` 必须取"入边原始值"（`Node_Lookup(last)`）**，不能读 `nodes.nowNode.step/function`（`door_set_pass_node()` 会把 `step` 改成 72/50/36、`function` 改成 `NONE`）。
- ⚠️ **别用 `getNextConnectNode()` 的返回值当 `Node[]` 下标**：它返回连接表偏移，只有目标恰好是 `from` 的第一个连接时才凑巧相等。
- ⚠️ **`arrive_method` 会残留上一次的值**：`barrier.c` 里有若干处**不经过 `deal_arrive()`** 就直接 `cross_event |= CROSS_EVENT_ARRIVED`，此时它是上一段的值 ⇒ 公式退回"缺省 `d`"（**不会错到危险值，但也不准**）。
- ⚠️ **`TURN_CALC_ENABLE=1` 时公式是静默生效的**：改了 `angle`/`step` 或补了实测数据后补偿值可能跟着变；怀疑"某个弯突然不一样了"就先拨回 0 复现一次。

### 14.4 后续收益点（按性价比）

0. **先复核 5 条 `step ≤ 18cm` 的段长**（`B8→N9`=1、`B9→N7`=5、`P8→N20`/`B2→N4`=12、`P6→N7`=18）——
   最便宜的一刀，**不用写代码，量尺子即可**。它们的补偿值大概率只是在补段长（见 14.2 的 B 类信号），量准了这些"怪值"可能自己就正常。
1. **顺便采"检测时刻里程"（免费数据）**：`nodes.nowNode.step` 已是 cm 单位、检测发生在 `Nav_NearEnd()`，
   所以 `检测滞后 = nowNode.step − Chassis_GetMileage()` 就是现成的实测值，可用来验证上一条。
2. **补 3~5 条 90° 转弯的实测** → Tier2 从 39 条涨到约 90 条（R3 阈值放到 85°），闸门会自动筛掉不靠谱的。
3. **加节点坐标表**（与规划器需要的坐标是同一份数据）：有坐标后 `d = 节点到入边中心线的垂直距离` 可以直接算 ——
   这正是 14.7 证据 1 指出"出边信息在边表里根本没有"的补法，**收益最大的一项**。
4. **量两个机械常数**：旋转中心→板中心纵向距离 `L`（预期 ~19cm）、板有效半宽 `w`；量到后公式从"拟合"变"求解"。
5. **给 `N10` 补条目** —— 6 个主干枢纽（`N3 N4 N5 N8 N10 N12`）里**唯一一条都没有**的（`N8` 已补上 4 条；`N10` deg=10、5 进 5 出，见 14.9）。
6. **门区段的 `step` 会在运行中被 `door_set_pass_node()` 改写**（72/50/36），所以按"运行时 step"分档的判据（如 R2）只能取边表原始值，这一点在新增规则时要留意。

### 14.5 当时的分析脚本与报告（已清理）

8 个 `analyze_turn_comp_*.py`（只读源码统计/校验，不进固件）与两份报告（`转弯补偿拟合分析.md` 问题定位、`转弯补偿_能算就算方案.md` 落地方案）
已于 2026-09-26 随过程产物一并清理，结论全部并入本节。
⚠️ **本机不能在 PC 上跑 ARM 代码**（无主机 C 编译器、WSL 无发行版、`arm-none-eabi-gdb` 无 `target sim`）⇒ 当年只做**保真性（从 `map.c` 抽真实代码并断言可逆还原）+ GCC 语法编译**，数值靠 python 侧同式独立计算。

⚠️ **维护注意（以后新写解析脚本同样适用）**：脚本依赖"表在 `map.c` 里"。2026-09-12 把 if 链改成 `kTurnTbl[]` 时解析器一度失效（还在找 if 链），已改成**同时认两种格式** ⇒ **再改表结构要同步它**；
且抽表必须"**先剥注释再判断命中位置**"，简单正则会**把注释掉的条目当成生效**。

### 14.6 涉及的文件

| 文件 | 内容 |
|---|---|
| `Navigation/map.h` | 新增 `enum { ARRIVE_* }` 判据编号 + `extern volatile uint8_t arrive_method;` |
| `Navigation/map.c` | `GetForwardDistanceBeforeTurn()`：18 条 if 链 → `kTurnTbl[13]`（**清掉 3 条死值**）+ Tier2 公式 + 5cm 闸门；新增 `Node_Lookup()`、`arrive_method` 定义、`TURN_*` 宏 |
| `Task/ArriveDetect_task.c` | `deal_arrive()` 增加 `out_method` 出参，10 处 `return 1` 各自写命中判据；定义 `arrive_method` 全局；任务里把它传给 `deal_arrive` |
| `Task/ArriveDetect_task.h` | `deal_arrive` 声明同步 |
| `Mission/config.h` | 新增开关 `TURN_CALC_ENABLE`（1=启用能算就算，0=完全回到原行为；**当前 0**） |

### 14.7 量化依据：为什么是"判据 + 公式"，而不是"只加标志位"

严格留一验证（LOO：预测某条新边时只能用其余 20 条估参数），21 条实测数据：

| 模型 | 参数数 | 训练 MAE | LOO-MAE 量级 |
|---|---|---|---|
| 查 `(last,now,next)` 三元组（**改造前的做法**） | 21 | **0.00** | ~9（**退化成全局常量**，零泛化：多一条边就得多记一个数） |
| 只用判据（每个判据一个常量） | 7 | ~4.6 | ~12.3 |
| **判据 + 夹角 `L(1−cosφ)`（采用的做法）** | **8** | **~4.6** | **~7.0** |
| 入边 / 入边+判据（更细的分层） | 19~20 | ~0.6 | ~11.3（**典型过拟合**） |

> 结论：**标志位单独用不够**（12.3），必须配上夹角公式才有 7.0；再加参数也降不到 3 以下 —— 因为"没测过的边"里混着 14.2 那类**根本算不出来**的段长补偿。
> ⇒ 定位：**给"没测过的边"一个错得少一点的兜底，不替换已实测的边。**

**三条硬证据**（解释为什么它只能当兜底）：

1. **同一条入边 + 同一判据、仅出边不同，距离差 6~18cm**：`C4→N20→P8`(155°)=35 / `C4→N20→B6`(25°)=24（都是 CRIGHT）；
   `N3→N4→B2`(140°)=30 / `N3→N4→B3`(40°)=12（都是 CLEFT）。
   ⇒ 补上的距离被"出边"改变得**比被转弯角更多**，而出边坐标信息**边表里根本没有** —— 即 14.4 第 3 条"加节点坐标表"的依据。
2. **小角度端被系统性低估**：`B2→N1→P1`(40°)=25、`C4→N20→B6`(25°)=24，而任何 `L(1−cosφ)` 几何在 25~40° 只给 **1.8~4.4cm**；
   镜像的 `P1→N1→B2`(45°) 只有 **3cm** ⇒ **左右转差约 22cm**，主要在小角度上（`sinφ` 项没抓住，只改善 0.05cm）。
   怀疑是"**旋转中心与传感器板中心存在横向偏置**"或左右轮摩擦不对称 —— 这正是当年要一条条硬补偿的原因。
3. **`L` 的真实值定不住**：扫 `L` 的 LOO 最优点在 **~7cm**，而 145° 那批数据反解是 **30~36cm**。
   最终取 `L=19` 的理由只有两条：**与现有默认值一致** + **被 5cm 闸门挡掉的条数最少**（那 8 条标定数据反解为中位 16.7 / 均值 17.2 / 范围 11.0~24.4）。

**Tier3（161 条不可算）按原因分类** —— 也就是下一步补实测的优先级：

| 原因 | 条数 | 例 |
|---|---|---|
| 接近 180° 原路折返 | 55 | `P1→N1→P1`、`B1→N2→B1` |
| **转弯只有 90°**（几何项 `1−cosφ` 正好 =1.0，公式本可用） | **44** | `P3→N3→N10`、`N10→N9→N10` |
| 入边在障碍/平台上 | 37 | `N1→P1→N1`、`N7→P6→N7` |
| 入边 `step < 20cm` | 22 | `P6→N7→P6`(18)、`B2→N4→B2`(12) |
| 其他小角度 | 3 | `S2→N6→N5`(45°)、`N8→N5→N6`(35°) |

> **"90° 转弯"这 44 条最值得先补实测**（唯一缺的就是一条 90° 实测，补几条就能把 R3 阈值从 100° 放到 85°）。
> 另有 4 条长斜边/X 交叉怪值（`N13→N18→B5` 反解 35、`N10→N9→B9` 24、`N4→N3→N8` 11、`N1` 附近那条 3）**任何几何模型都解释不了**，只能实测。

---

### 14.8 上位机可视化编辑器（2026-09-29 新增，`地图修改上位机/map_editor/`）

上面这两张表和 `d` 参数以前只能手抠 `map.c`。现在编辑器左栏「**⟲ 转弯补偿…**」把它们变成可编辑界面
（**只读源码 → 改内存 → 显式写回**；写回前自动备份到 `backups/`）：

| 页签 | 内容 | 对应固件 |
|---|---|---|
| ① 停车原地转 | `kTurnTbl[]`，可增删改，逐行标出「当前会不会生效」 | `GetForwardDistanceBeforeTurn()`（Tier1） |
| ② 陀螺不停车转 | `GetForwardDistanceBeforeGyroTurn()` 的 if 链 | 同函数（末尾固定 `return 0`） |
| ③ 覆盖总览 | 地图里**所有** (入边, 出边) 转弯组合 + **当前生效值**，来源分档 = 表1 实测 / Tier2 公式 / Tier3 默认 19 / 表2 实测 / 默认 0 | 两表合起来的效果 |
| ④ 公式参数 | `TURN_L_PIVOT` / `TURN_GATE_CM` / `TURN_D_{CRIGHT,CLEFT,DLEFT,DEFAULT}` + 开关 `TURN_CALC_ENABLE` | map.c 的 `#define` / config.h |

点任一行 → 画布上把那个弯（上一步 → 当前 → 下一步）高亮出来。

- ⚠️ **14.1 里那份手写的"8 条死值/无效"清单已经和当前源码对不上了**（地图精简过、两张表本身也改过）。
  **以编辑器 / `_selftest.py` 从源码实时算出来的为准**，口径 = `Nav_TurnAndAdvance()` 的分支判定：
  `|Δ| < 10°` 直行；`STOPTURN && |Δ| > 20°` 或 `|Δ| ≥ 90°` ⇒ 停车转；否则陀螺转
  （其中 `STOPTURN` 那一条固件用的是**陀螺实测航向 `getAngleZ()`**，静态算不出来
  ⇒ 工具只能说"**按边表角度**这一行查得到/查不到"，实车以串口日志为准）。
- 写回**只替换三处**（表1 表体 / 表2 函数体 / `kTurnTbl_node_check` 表达式），
  **没编辑过就整段跳过**（不产生"缩进归一化"式无意义 diff）；**编辑过才会整段重排**（值不变）。
- 覆盖总览里 Tier2 档给的是 `值 min~max`（`d` 取决于运行时 `arrive_method`，会残留上一次的值），
  不是实车实测；任何补偿值最终仍要实车复核。
- 护栏：`_selftest.py` 第 12 节（往返一致 / 幂等 / 新增节点自动进 `kTurnTbl_node_check`），
  `_guismoke.py` 的 turn 段（真写回路径走**沙箱副本** + 真实 `map.c` SHA256 前后比对）。
  编辑器侧的坑与不变量写在 `地图修改上位机/map_editor/AI_CONTEXT.md` §6.14 / §7.10 / §10.7。

---

### 14.9 长度 / 标志位 / 路口线段的规律（2026-09-29 只读分析）

> 完整报告 `地图修改上位机/reports/转弯补偿_长度标志位路口规律分析.md` 与四个复现脚本（`turn_relation_dump.py` / `turn_phys_fit.py` / `solve_node_coords2.py` / `summary_stats.py`）都是**过程产物、可随时清空**；结论已全部并入本节。

**三条可依赖的事实**

1. **`angle` 是自洽方向场，`step` 不是物理长度。** 52 个双向段里 **49 段角度严格互为反向**（差 180°）；但**只有 18 段两侧 `step` 相等**，中位差 8cm、最大 **137cm**（`N12→N5`=222 vs `N5→N12`=85），即使两侧 `func` 都是 `NONE` 的 13 段里也有 9 段不等（中位 12、最大 36）。⇒ **按 `step` 反推距离/几何前必须先把双向段去重**（取两侧中位）。
2. **节点图不是按比例图，但与边表只差一个固定 180° 旋转。** `px/step` 从 0.68 到 162.6（**跨 240 倍**）；扣掉整体 180° 后角度残差中位 **6.5°**（62/108 落在 ±10° 内）。与「反解坐标」做相似变换对齐后，**每节点位置误差中位 42cm、最大 255cm**（`P8`）⇒ 节点图只能当拓扑骨架。（14.1 第 3 条说的「差一个固定的参考系旋转」现在可以写死为 **180°**。）
3. **补偿只发生在 `deg ≥ 4` 的中转节点上。** 两张表涉及的 11 个中转节点全部 `deg ≥ 4`；deg=2 的端点（`P*` / `S*` / `B8` / `B9` / `C5`）是「进去再原路出来」，那条 180° 折返由平台类 `func`（`UpStage`/`UpStageHome`/`BSoutPole`）内部完成，不走补偿。

**「能仿真计算吗」——能算的与不能算的**

- ✅ **能从边表反解节点真实坐标**：`dx = step·cos(angle), dy = step·sin(angle)` 超定最小二乘，段长残差 **中位 1.8cm / 均值 6.6cm / 最大 37cm**（去重后 55 段）。结果落在 `reports/node_coords_solved.json`（锚点 `N1=(0,0)`，朝向未定）—— 这就是 14.4 第 3 条「加节点坐标表」的起点，可直接搬进编辑器。
- ❌ **不能靠几何算补偿表**：留一验证下「判据 + `L(1−cosφ)`」的 LOO-MAE ≈ **7.2cm**（全 26 条实测），相对「只用判据」（7.7）只赚 0.5cm；而拐角上 7cm 就是「咬不咬得住线」。三个原因：`ε` 是主项（同入边同判据、仅出边不同就差 6~18cm）、**出边在节点处的错位在边表里没有数据源**、左右转不对称（`B2→N1→P1`=25 vs 镜像 `P1→N1→B2`=3，角度只差 3°、值差 22cm）。⇒ 14.7 的定位不变：**给「没测过的边」兜底，不替代实测**。
- 顺带否掉一个诱人的假说：`r(in_step, 补偿值)` 在 `|Δ|≥100` 子集上是 +0.57，看着像「段长越长越要补」，其实是**「长段 → 速度档高」的混淆效应**（`speed` 单独只有 +0.38，`speed²` +0.36）——没有刹车距离在主导。

**顺手查出的两处（比公式更值钱）**

- `N5→N12→N11`=5、`N4→N5→N12`=6：**全表仅有的两条 90° 实测**，却在表2、被分支判到表1 ⇒ **从不生效**，实车在这两个弯上吃的是默认 **19**。挪进 `kTurnTbl[]` 就能验「90° 要 5cm 还是 19cm」，是最便宜的一次实验。
- **`N10`（deg=10）是 6 个主干枢纽里唯一一条条目都没有的**（14.4 第 5 条原写的「给 `N8` 补」已经补上了）。
- 两张表当前真实状态：表1 **15/15 生效**、表2 **7/11 生效**（4 条死值：`B3→N2→P2` / `B2→N1→P1` 与表1 重复，`N5→N12→N11` / `N4→N5→N12` 真无用）。覆盖度：296 个转弯组合（直行 74 / 停车转 189 / 陀螺转 33），**需要补偿的 222 个里实测只覆盖 22 个（≈10%）**。
