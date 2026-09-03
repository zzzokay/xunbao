# 项目参考文档 — xunbao (寻宝)

> MCU: STM32F750V8Tx | 工具链: MDK-ARM V5.32 | FreeRTOS + CMSIS_V1 | 216MHz

---

## 一、项目结构

```
Application/          # 应用层 — 地图导航、障碍处理、底盘API
  ├── chassis_api.c/h # 底盘API中间件（核心解耦层）
  ├── map.c/h         # 地图导航 / Navigation()路径规划
  ├── map_message.c/h # 地图数据（已迁至 map_message.c 单数据源；map_message.c 仅剩空 Node/ConnectionNum/Address 全局，几何/开关宏在 config.h）
  ├── barrier.c/h     # 障碍处理（平台/桥/山/南极/跷跷板/波动板）
  ├── scaner.c/h      # 16路巡线传感器
  ├── turn.c/h        # 转弯控制（原地转、陀螺仪转、360°转、梯形速度曲线）
  ├── gray.c/h        # 灰度传感器
  ├── IIC.c/h         # 软件I2C
  ├── motion.c/h      # 运动控制
  ├── command.c/h     # 调试串口缓冲区
  ├── delay.c/h       # 延时
  └── sys.h           # 系统类型定义(u8/u16等)

Core/                 # STM32 HAL核心
Math/                 # 算法库 — pid.c/h, filter.c/h, sin_generate.c/h
Module/               # 外设驱动 — imu, K210, QR, openmv, Rec_usart, 舵机, ADC, 蜂鸣器, LED, 巡线底层
Motor/                # 电机驱动层 — motor.c/h, Encoder.c/h
Task/                 # FreeRTOS任务 — motor_task, main_task, task_create, ArriveDetect_task, temporary_task
USMAT/                # USMART串口调试组件
MDK-ARM/              # Keil工程文件
test1.ioc             # CubeMX配置
```

---

## 二、任务与调度

| 任务 | 函数 | 优先级 | 栈大小 | 周期 |
|------|------|--------|--------|------|
| Start_task | `Start_task()` | 6 | 256字 | 一次性(创建三任务后自删) |
| main_task | `main_task()` | 5 | 2048字 | 3ms |
| motor_task | `motor_task()` | 6 | 512字 | 5ms |
| ArriveDetect_task | `arrive_detect_task()` | 5 | 512字 | - |

> 注：motor_task 优先级为 **6**（motor_task.h，configMAX_PRIORITIES=7，合法 0~6，已是最高的合法优先级）；main_task(5) **低于** motor_task(6)，当前配置下主任务无法抢占饿死电机任务（FreeRTOS 数值越大优先级越高）。Start_task 现含 IMU 上电自检（见已修复表 2026-08-10）。

**关键时序**: motor_task 每 5ms: 读编码器 → 模式切换 → 巡线/转弯/陀螺仪 → PID → 调PWM。

---

## 三、核心数据流

```
map.c:Navigation() → Chassis_MotorControl(mode, Lspeed, Rspeed, aim)
                → motor_task:handle_xxx_mode()
                    → scaner.c:Go_Line() / turn.c:Go_Angle() / Stage_turn_Angle()
                        → 设置 motor_all.Lspeed / Rspeed
                    → handle_target_speed() → 写 motor_L0.target 等
                    → incremental_PID() → motor_set_pwm()
```

---

## 四、关键全局变量

### 4.1 电机控制 ([pid.h](Math/pid.h))

```c
struct I_pid_obj { float output; float bias; float last_bias; float last2_bias; float measure; float target; };
extern struct I_pid_obj motor_L0, motor_L1, motor_R0, motor_R1;
extern struct PID_param motor_pid_paramL0, motor_pid_paramL1, motor_pid_paramR0, motor_pid_paramR1;
extern struct P_pid_obj line_pid_obj, gyroT_pid, gyroG_pid;
extern struct PID_param line_pid_param, lineG_pid_param, gyroT_pid_param, gyroG_pid_param;
```

**Bias类型（已修复）**: `bias` 原为 `int`，`bias = target - measure` 会截断小数，低速时PID精度丢失；2026-05-01 已改为 `float`。

### 4.2 底盘状态 ([chassis_api.h](Application/chassis_api.h))

```c
struct Motors {
    float Lspeed, Rspeed, Cspeed, Gspeed;
    float GyroT_speedMax, GyroG_speedMax, Line_speedMax;
    float encoder_avg, Distance;
    float Cincrement, CDOWNincrement, Gincrement, GDOWNincrement;
};
extern volatile struct Motors motor_all;
extern float TC_speed, TG_speed;
extern volatile uint8_t PIDMode;  // is_No/is_Free/is_Line/is_Turn/is_Gyro
```

### 4.3 地图导航 ([map.h](Application/map.h))

```c
typedef struct _node {
    u8 nodenum; u32 flag; float angle; u16 step; float speed; u8 function;
} NODE;
extern NODE Node[132], route[100];
extern Nodes nodes;    // lastNode/nowNode/nextNode
extern volatile uint8_t cross_event;
#define CROSS_EVENT_ARRIVED (1<<0)   // 已到达节点
#define CROSS_EVENT_DOOR    (1<<1)   // 门结果就绪
```

> **⚠️ 数据源变更（2026-08-21 起）**：`Node[132]`、`ConnectionNum[54]`、`Address[55]` 不再是 `map_message.c` 里的手工字面量，而是**空全局**，由 `nav_graph_init()`（`map_message.c`）在启动时从**单张自描述边表 `NavEdgeTbl[]`** 自动构建（见 4.5）。`getNextConnectNode`/执行层逻辑不变，只换数据来源；从而彻底去掉"增删边要手工同步三数组"的坑。

### 4.4 障碍标志 ([barrier.c](Application/barrier.c))

```c
uint8_t door_pass[5];    // 门通行状态(D2~D5,D1)：CAN_PASS/ONE_WAY_PASS/NO_PASS
uint8_t treasure;        // 宝物编号
volatile uint8_t flag_line_clue;     // QR 百位：0=跳过P3/P4，3=P3，4=P4
volatile uint8_t flag_clue_stage_A;  // QR 十位：5=P5，6=P6
volatile uint8_t flag_clue_stage_B;  // QR 个位：7=P7，8=P8
uint8_t flag_clue_A, flag_clue_B;    // 平台上的线索数字
volatile uint8_t get_cude;           // QR 读取完成标志
```

### 4.5 导航规划器与单数据源图（最短路径）([nav_planner](Application/nav_planner.h) / [map_message](Application/map_message.h))

**目标**：用「必经点 + 最短路 + 拼接」替代手写路线数组，并把图收敛为**单张自描述边表**（单一数据源）。换地图只需改边表，路线自动重算。

**单数据源图**（`map_message.c/.h`）：
```c
typedef struct { u8 from; u8 to; u32 flag; float angle; u16 step; float speed; u8 func; } NavEdge;
#define NAV_EDGE_COUNT 125
extern const NavEdge NavEdgeTbl[NAV_EDGE_COUNT];   // 唯一人工编辑源(用原 map_message 宏/名)
void nav_graph_init(void);   // 启动时由本表自动构建 Node[]/ConnectionNum/Address
```
- 表中 `flag/speed/func/from/to` 均用**原 `map_message.c` 的宏/名**（如 `LEFT_LINE|CRIGHT`、`SPEED1`、`UpStage`），编译期即等于原 `Node[]` 字面量 → 与执行层语义完全一致。
- 启动顺序：`mapInit()` → `nav_planner_setup()` → `nav_graph_init()`（建执行层 CSR）→ `nav_init()`（建规划器邻接）。`s_nav_ready` 保证只构建一次。

**规划器 API**（`nav_planner.c/h`）：
- `nav_init(edges, n, nodes)`：建邻接（CSR，节点→出边列表）。
- `nav_shortest_path(from, to, out, max_len)`：**线路图(line-graph)上的点式 Dijkstra**——把每条路当做一个"点"，两条首尾相接的路连边，转弯权重在 `nav_init` 里**提前并入连接权**，主循环即标准点式 Dijkstra；返回节点序列。
- `nav_plan_waypoints(route, max, wps, n)`：依次求相邻必经点最短路并**拼接**（去重连接点）。
- `nav_build_route(route, max, wps, n)`：生成 `route[]`（去掉起点、`0xFF` 收尾），wps[0] 为起点。
- `nav_stitch(...)`、`nav_find_edge(from,to)`：拼接多条段、查边。

**代价模型**（`nav_planner.c/h`）：`cost(边) = 1.0×step + 0.6×|Δangle| + 1.0×obs_penalty(func)`
- `obs_penalty`（`NavObsPenalty[]`）：Hill30 / Bridge40 / 短波板60 / 平台60 / 长波板70 / 跷跷板80 / 南极高山90 / 景点支路100 / 刀山SM120 / 后退桩1000 / 门0(用必经点处理)。
- 已用 PC 基准 `_weight_calib.py` 标定：**复现现有 14 条路线；rout_58 按最短路径（北线）**。

**开关**：[config.h](Application/config.h) 的 `#define USE_PLANNER_ROUTE 1`。`0`=沿用现有路线数组（行为不变）；`1`=首轮初始、二维码分流、门后 A/B 平台、P7/P8 宝物回程、回程门分支和第二轮全程都由规划器生成。门色仍作为必经门侧节点约束，避免规划器跨越未确认或单向门。改地图/调权重后应先在 MDK 编译确认，再上真车。

**PC 校验工具**（仓库根，不进固件）：
- `_weight_calib.py`：读 `map_message.c` 建图 → 校验 15 条参考路线连通性 → 必经点细分/完整 route 拼接核对 → 权重灵敏度。换图后重跑确认路线未偏离。
- `_check_csr.py`：镜像 `nav_graph_init`+`getNextConnectNode`，校验自动 CSR 能解析全部参考边与 8 条门边。

---

## 五、PID 配置

### 5.1 内环速度PID

| 参数 | L0-L1 | R0-R1 |
|------|-------|-------|
| Kp/Ki/Kd | 40/10/5 | 40/10/5 |
| outputMax | MOTOR_PWM_MAX | MOTOR_PWM_MAX |

### 5.2 外环PID

| 用途 | Kp | Ki | Kd | outputMax |
|------|----|----|----|-----------|
| 巡线(line) 初始 | 7.0 | 0 | 0 | ±80（运行中由 `line_pid_steps[]` 按实际速度实时覆盖，见 5.3） |
| 转弯(gyroT) | 4.0 | 0 | 70 | ±80 |
| 陀螺仪直行(gyroG) | 2.0 | 0 | 5.0 | ±80 |
| 灰度(lineG) | 15 | 0 | 5 | ±80 |

### 5.3 速度等级

`SPEED0=25, SPEED1=36, SPEED2=45, SPEED25=55, SPEED3=60, SPEED4=70, SPEED5=75`

速度→PID映射表 `line_pid_steps`（chassis_api.c 静态常量，2026-08-09 起改为**按当前实际速度阶梯选择**）：
- SPEED5/4(75/70): kp=3.5, kd=200 | SPEED3(60): kp=4.0, kd=120 | SPEED25(55): kp=5.0, kd=150
- SPEED2(45): kp=6.5, kd=110 | SPEED1(36): kp=7.5, kd=100 | SPEED0(25): kp=9.0, kd=100
- 特低速 20: kp=11.0, kd=100 | 15: kp=20.0, kd=140 | 12: kp=25.0, kd=140

**阶梯选择机制**：`Chassis_SetTargetSpeed` 只设置 `motor_all.Cspeed`（目标速度），不再写 `line_pid_param`；
motor_task 每 5ms 调用 `Chassis_UpdateLinePidBySpeed()` 读取当前实际速度 `motor_all.encoder_avg`，规则：**只有当前速度 ≤ 某档速度才采样该档 PID**（即取所有 `档速 ≥ 当前速度` 中最低的一档，尽量向上取高速档低 Kp；超过最高档用最高档）。
高速→低速减速过程中 PID 随实际速度逐级下调：减速前期一直保持高速低 Kp，实际速度真正降到某档以下才换更高 Kp —— 既不减速期套用低速高 Kp（12/15→15.0）导致摇摆，也不晚切导致不跟线。
- 游龙 `Chassis_OverrideLinePid` 临时覆盖生效时（`line_pid_override_active`）优先级更高，不在此覆盖

---

## 六、模式枚举 ([motor_task.h](Task/motor_task.h))

```c
typedef enum { is_No=0, is_Free, is_Line, is_Turn, is_Gyro };
```

巡线子模式: `TRACK_ALL=0, TRACK_LEFT_EDGE, TRACK_RIGHT_EDGE, TRACK_NEAR_CENTER`（默认）

---

## 七、电机与编码器映射

### 7.1 电机编号
```
motor_set_pwm(1) → L0 (左前) TIM9 PE5/PE6
motor_set_pwm(2) → L1 (左后) TIM8 PC8/PC9
motor_set_pwm(3) → R0 (右前) TIM4 PD14/PD15
motor_set_pwm(4) → R1 (右后) TIM4 PD12/PD13
```
正转: CCRx=0, CCRy=ccr | 反转: CCRx=ccr, CCRy=0

### 7.2 编码器
```
TIM1 → L0 (正) | TIM2 → L1 (正) | TIM3 → R0 (取反) | TIM5 → R1 (取反)
```
编码器每圈 5720 脉冲，减速比 0.362，轮径 104mm。
里程: `Distance += (avg_encoder * 10.4 * PI / 5720) / 0.362 * LEN_SCALE`

### 7.4 长度标定 LEN_SCALE（2026-08-13 起）

**背景**：此前所有长度值（里程、地图 step、距离阈值）都是未标定的"代码单位"。
**标定**：实测车走 100 代码单位 ≈ 120cm → `#define LEN_SCALE 1.2f`（[config.h](Application/config.h)，2026-08-27 起集中到 config.h）。
**用法**：各处距离阈值已按 **cm = round(代码单位 × LEN_SCALE)** 直接折算为**整数厘米内联**在代码中（精确到 1cm），不再写 `×LEN_SCALE` 表达式。**LEN_SCALE 宏仅用于 motor_task 里程公式的比例补偿**（里程是运行时连续累加，无法内联）。
**覆盖范围**（共 250 处，已验证零遗漏零误伤）：
- 里程公式 `motor_task.c:182`：`Distance += ((encoder_avg*10.4*PI/5720)/0.362) * LEN_SCALE`（比例补偿）
- `map_message.c` Node[132] 表全部 step 字段（130 条边，如 `280→336`、`180→216`）
- `barrier.c`（90 处）：`Chassis_DriveDistance_Blocking` 距离、`Chassis_GetMileage`/`mileage_br` 比较、`Stage_DetectedRamp` 距离、`nodes.nowNode.step=`、`door_set_pass_node`/`door_retreat` 距离、`RampCtrl_Blocking` max_distance、QQB `dis`
- `map.c`（32 处）：`Barrier_WavedPlate`、两个 GetForwardDistance* 的 return 距离
- `main_task.c`（7 处）：`Chassis_DriveDistance_Blocking` 距离

> 注：`RampCtrl_Blocking` 只有最后一个参数 max_distance 是长度（thresh/speed/angle/max_correction 非长度，如 `15`/`20.0f`/`0.08` 保留）；`Stage_DetectedRamp` 的距离参数折算（其俯仰阈值 10° 非长度不折）；`return 0;` 等非长度返回值不折。
> **重新标定**：改 config.h 的 LEN_SCALE + 重算各处内联值（cm = round(代码单位 × 新倍率)）；原代码单位值在 git 历史中可查。
> **门区段距离**：`door_set_pass_node`/`door_retreat` 的门区段长度已集中为 [config.h](Application/config.h) 的 `DOOR_LEN_*`（6 条全长，map DOOR 条目用 `宏/2`）/ `DOOR_RETREAT_*`（4 个回退距离）宏（2026-08-13，2026-08-27 起集中到 config.h），改长度只改宏即可。当前工作区（2026-08-17）：`DOOR_LEN_N5N12/N3N10=200`，`DOOR_LEN_N5N8/N8N10/N3N8/N8N12=190`；`DOOR_RETREAT_N5N8/N5N4=67`、`DOOR_RETREAT_N10N8=80`、`DOOR_RETREAT_N8N5=65`。
> **门区段角度**：[config.h](Application/config.h) 的 `ANGLE_N3N8(145)/ANGLE_N5N8(35)`（正向基准），`ANGLE_N8N12=ANGLE_N3N8`、`ANGLE_N8N10=ANGLE_N5N8`（门两侧平行）；反向用 `ANGLE_REV(a)`（正角减180/负角加180，锁定 [-180,180]）派生 `ANGLE_N8N3(-35)/ANGLE_N8N5(-145)/ANGLE_N12N8(-35)/ANGLE_N10N8(-145)`（2026-08-16）。map_message.c Node 表 8 处门区段角度全部改用宏，原手工值（N8→N3 -45、N8→N5 -140、N8→N12 140、N8→N10 33、N12→N8 -43、N10→N8 -150）作废，改角度只改宏。

### 7.3 巡线传感器

16路 GPIO 读取（0=黑线，1=白底），权重表 `line_weight_default[16]`（约 -3..3，含小数，对称）。
`line_data[5]` 滑动窗口（**static，仅 scaner.c 内部访问**），truth 枚举: VALID/ALL_ERR/POS_ERR。
RF/Gray 分发收敛在 **`Scaner_Update()`** 单入口（合并自原 getline_error/getline_error_ex）；外部操作 line_data 只能通过 `Scaner_ClearLineData()`（清零）与 `Scaner_IsLineLost()`（丢线检测）。
内部函数均为 static: `coarse_filter`/`pos_detect`/`Update_line_data`/`value_calculation`/`count_led_line`/`pick_best_cluster`。
`Line_Scan` 返回有效标志（1=已记录样本，0=粗滤/位置计算失败）；`value_calculation` 四种 TRACK_ 模式均为显式 case。

---

## 八、地图节点功能 ([map.h](Application/map.h))

```c
enum barriers {
    NONE=1, UpStage, Bridge, Hill, LBHill, SM, View, View1, BACK,
    BSoutPole, QQB, BLBS, BLBL, DOOR, BHM, IGNORE, UNDER, Special_node, DOOR1, UpStageHome
};
```
- UpStage→Stage() | UpStageHome→Stage_Home() | Bridge→Barrier_Bridge() | Hill→Barrier_Hill()
- BSoutPole→South_Pole() | QQB→QQB_1()
- BLBS→Barrier_WavedPlate(70) | BLBL→Barrier_WavedPlate(100)
- BHM→Barrier_HighMountain() | DOOR→door()

> ⚠️ 波动板节点约定（2026-08-21 拆 B10/B11，正反向共用）：把 BLBL/BLBS 直接加在节点间会令 `Barrier_WavedPlate` 内部自置 `CROSS_EVENT_ARRIVED`，跳过 `ArriveDetect`/`deal_arrive` → 无路口检测、无"路口"播报，且出板落点漂移导致未到真实路口就提前转弯。正解：拆一个板节点（B10=N14–C7 段板尾、B11=C8–C4 段板尾），进板边 `BLBL`(flag NO)、出板边 `NONE`(flag=路口视觉标志如 DLEFT/CRIGHT) → 真实路口恢复视觉检测+播报；板节点为直通点（入/出 angle 相同不转弯）。正反向共用同一板节点：正向 `N14→B10→C7`、`C8→B11→C4`，反向 `C7→B10→N14`、`C4→B11→C8`（B10/B11 各 2 条出边，角度按方向区分，见 map_message.c；step 均待现场实测）。

---

## 九、Navigation() 流程 ([map.c](Application/map.c))

```
Navigation()
├── near_end==0 (巡线行驶)
│   ├── SEG_INIT:       清里程, 设巡线模式/速度, 启用游龙+翘头保护
│   ├── SEG_MID_SWITCH: 里程≥50%, 切换巡线模式
│   └── SEG_PREP_ARRIVE:里程≥60%, 降速
│
└── near_end==1 (节点处理)
    ├── Nav_NearEnd: map_function() → 等待到达
    ├── Nav_TurnAndAdvance: 转弯（左follow/右follow/停车原地转/陀螺仪）
    └── Nav_PostProcess: 检查 cross_event → 推进节点
```

---

## 十、IMU 数据流 ([imu.c](Module/imu.c))

- USART3 DMA + IDLE 中断，0x55 协议，10字节校验和
- `imu.yaw/roll/pitch` (±180°)，`imu.yaw -= basic_y` 归零
- `getAngleZ() = get_latest_yaw() + imu.compensateZ`
- `IMU_CalibrateZero(&basic_y, &basic_p, &basic_r)` — 10次采样平均

---

## 十一、已知 Bug & 已修复

### P1（未修复）
- `map.h:188-326` ~120个 Clue*route 外部声明未使用
- `pid.c:167-180` 注释掉的 R1 初始化死代码
- `motor_task.c:95-96` 5ms 循环内 printf 影响实时性

### P2（未修复）
- `map.c:189-233` 转弯前距离 if 链应改用查表
- `filter.c:56-93` 4点去极值滤波窗口过小

### ✓ 关键状态（2026-08-17）
- **getNextConnectNode 兜底（防跑飞）**：查不到连接（节点写错/连接表漏配）时不再返回 0（Node[0]=S1 会带车跑飞），改为打印 `ROUTE ERROR: no connection X -> Y` 并 `CarBrake_Stop()` 死停车；`nownode>=54` 越界同样兜底。所有调用点已同步：mapInit/Nav_TurnAndAdvance/Nav_PostProcess 在 `route[map.point]==0xFF`（路线结束哨兵）时跳过查询；door_set_pass_node/door_retreat 对 `ROUTE_NOT_FOUND` 提前 return
- door() 回程 D5/D4 黑灯分支修复：DOOR_D5_BACK 原 `map.point-=1; route[map.point]=N3` 在公共初始化 `map.point=0` 后下溢成 255 越界写，改为 `route[0]=N3`；door7route/door11route 开头多余节点（N8/N5）删除，避免 `getNextConnectNode` 返回 0 → Node[0]=S1 跑飞
- DOOR_D4_BACK 黑灯分支顺序修复：`door_retreat(N8,N5)` 拷贝 nowNode 前须先 `door_set_pass_node` 放行 D3 门（N8→N5 原定义 SPEED0+DOOR，先拷贝会拿到旧值→慢走+到 N5 二次触发 door() 乱转）；另显式 `nodes.nowNode.function=NONE`
- PID bias 已 int→float；内环增量式带抗积分饱和，外环位置式带微分低通
- 巡线 PID 按实际速度阶梯选择（line_pid_steps[]，见 §5.3）
- 红绿灯按通行语义 CAN_PASS/ONE_WAY_PASS/NO_PASS，门区段长度/角度全部宏定义化
- door() 状态按 lastNode/nowNode 精确匹配，D2→D3 链已修复；二轮巡游所有平台后回家
- IMU 上电自检 + ORE 清理；DWT 解锁；FPU 单精度化
- 平台/南极结束后保留 nodes.nowNode.function，避免下平台后误停车转弯
- 工作区未提交：门角度 145/35、门长 200/190、SKIP_ROUND1=1、treasure=6、N5→N6 等 map_message 微调
- 逐日修复历史已从本文件移除，需要追溯时看 git log

---

## 十二、关键 API ([chassis_api.c](Application/chassis_api.c))

| 函数 | 功能 | 调用者 |
|------|------|--------|
| `Chassis_Init()` | 初始化底盘 | motor_task |
| `Chassis_SetMode(mode)` | 设PID模式 | map.c |
| `Chassis_SetTargetSpeed(speed)` | 设速度(自动映射PID) | map.c |
| `Chassis_SetTrackMode(mode)` | 设巡线模式 | map.c |
| `Chassis_MotorControl(mode,L,R,aim)` | 统一运动控制入口 | map.c/barrier.c |
| `Chassis_Brake()` | 急刹 | map.c |
| `Chassis_DriveDistance_Blocking(...)` | 临时模式行驶固定距离 | map.c |
| `Chassis_OverrideLinePid(kp,ki,kd,max)` | 临时覆盖巡线PID | map.c |
| `Chassis_Periodic_Update_5ms()` | 游龙+丢线+滚转+翘头保护 | motor_task |
| `Chassis_UpdateLinePidBySpeed()` | 巡线PID阶梯选择(速度≤档速才取该档) | motor_task |
| `Chassis_EnableAntiSnake()` | 激活游龙防护 | map.c |
| `Chassis_EnableLineLostProtection()` | 开启丢线保护 | map.c |
| `Chassis_EnableRollProtection()` | 使能横滚角保护(>40°死停) | map.c/barrier.c |
| `Chassis_EnableWheelieProtection()` | 使能翘头保护(pitch>8°降加速度) | map.c |
| `Chassis_SelfCheck()` | 一键自检 | main_task.c |
| `Chassis_EnableLineGyroComp(kd)` | 使能长直线陀螺仪阻尼（锁定当前角度为上一拍，防首帧跳变） | map.c（直穿段） |
| `Chassis_DisableLineGyroComp()` | 关闭长直线陀螺仪阻尼 | map.c（离开直线段） |
| `Chassis_GetLineGyroComp()` | 返回陀螺仪阻尼量（-kd×yaw_rate，独立小限幅），`Go_Line` 叠加 | scaner.c |

---

## 十三、常量参数

- PWM 20kHz (10800-1, prescaler=0), 一般 `MOTOR_PWM_MAX=8500`（`Chassis_Init()` 设置），转弯限5000
- 系统 216MHz (HSE 8MHz × PLL 54), APB1=54MHz, APB2=108MHz
- FreeRTOS tick=1000Hz, 编码器 ARR=65535

---

## 十四、IO 引脚分配

| 外设 | 引脚 | 功能 |
|------|------|------|
| USART1 | PA9/PA10 | 调试串口 |
| USART3 | PB10/PB11 | IMU |
| UART4/5/7 | PC10~PD2/PE7/PE8 | 串口通信 |
| UART8 | PE0/PE1 | K210/OpenMV |
| TIM1/2/3/5 | 编码器 | 四路编码器 |
| TIM4/8/9 | PD12~PD15/PC8/PC9/PE5/PE6 | 电机 PWM |
| TIM12 | PB14/PB15 | 舵机 PWM |
| ADC1 | PA2/PA3/PC4/PC5 | 电池/灰度 |

---

## 十五、模式切换 ([chassis_api.c](Application/chassis_api.c) + [motor_task.c](Task/motor_task.c))

```
map.c / barrier.c → Chassis_SetMode() → PIDMode = mode → motor_task 5ms循环
```

**状态转移表**:
| 来源→目标 | 处理 |
|-----------|------|
| Gyro→Line | gyroG_pid→line_pid_obj, TG→TC |
| Line→Gyro | line_pid_obj→gyroG_pid, TC→TG |
| Turn→Line | 清 line_pid/TC/Cspeed |
| Turn→Gyro | 清 gyroG_pid/TG/Gspeed |
| →Turn | 清 gyroT_pid |

差速限幅统一在 `motor_all.Line_speedMax`，`line_pid_param.outputMax` 固定±80。

---

## 十六、转弯逻辑 ([turn.c](Application/turn.c))

| 函数 | 作用 |
|------|------|
| `need2turn(now,target)` | 计算最短旋转角(-180,180] |
| `getAngleZ()` | yaw + compensateZ |
| `Turn_Angle_Base(Angle, ratio, force_thr)` | 原地转基函数(static) |
| `Turn_Angle(Angle)` | 原地转(ratio=1.0, force=0) |
| `Stage_turn_Angle(Angle)` | 平台转(ratio=1.0, force=150°；注释保留 1.15 历史) |
| `Turn360Step()` | 360°梯形速度曲线 |
| `Go_Angle(angle, speed, motor)` | 陀螺仪直行 |

Turn_Angle / Stage_turn_Angle 合并: 90%相同，提取 `Turn_Angle_Base` 基函数。
360°转圈: 从 PID+MustBeZero 脉冲改为梯形速度曲线(加速40°→全速40-300°→减速358°→停)。

---

## 十七、安全保护

### 17.1 丢线保护
`is_Line` 下 `line_data[5]` 全无效持续 80×5ms=0.4s 后 `CarBrake()` + `while(1)`。
一次性触发，`Chassis_EnableLineLostProtection()` 重新激活。

### 17.2 横滚角超限保护
`|imu.roll - basic_r| > 40°` 时 `CarBrake()` + `while(1)` 死停。
`Chassis_EnableRollProtection()/DisableRollProtection()`。

### 17.3 堵转保护
- PWM > 8000 硬上限（`STALL_PWM_ABSOLUTE_MAX`）→ 死停
- `output > target × 180`（`STALL_SPEED_RATIO`）连续 5 周期 → 死停（比值自适应各转速）
> ⚠️ **2026-08-06 起已停用**：`Chassis_EnableStallProtection()`（chassis_api.c:102 原本就注释）与全部 `Chassis_DisableStallProtection()` 调用点已注释（map.c Nav_TurnAndAdvance、barrier.c 南极 SP_IMPACT 两处）。`stall_protect_enabled` 恒为 0，上述两段检测不再执行。检测逻辑代码保留，恢复时取消调用点注释即可。

### 17.4 翘头保护
`is_Line` 下 `imu.pitch > basic_p + 8°` 时将 `Cincrement` 降至 0.05 抑制加速度，pitch 回落后恢复。需在 `Navigation()` 中调用 `Chassis_EnableWheelieProtection()` 激活，使用模式与游龙一致。
阈值 8.0f (`WHEELIE_PITCH_THRESHOLD`) 定义在 `chassis_api.c`。

---

## 十八、无传感器调试模式

| 宏 | 定义位置 | 功能 |
|----|----------|------|
| `DEBUG` | [config.h](Application/config.h)（当前默认 0） | Door_ReadPass 用 `debug_door_pass[5]` 预设数组模拟 |
| `MAIN_DEBUG` | [config.h](Application/config.h)（当前默认 1） | 跳过 Navigation()，执行 `test_flag`/`debug_test_item` |
| `SKIP_ROUND1` | [config.h](Application/config.h)（当前默认 0） | 跳过第一轮直接进第二轮（调试用）；main_task.c 初始化预设 `door_pass[5]`+`treasure`+`map.routetime=1`，首周期走真实二轮分支。**关键**：二轮分支 `get_newroute()` 后须再置 `routetime=2`（get_newroute 内部 mapInit 清 0），二轮全程 `routetime==2` 屏蔽 P7/P8 treasure 改路并保证跑完即停；`treasure!=0` 屏蔽 P1 残留 QR 改路 |

测试项: 1=循迹, 2=转180°, 3=障碍物, 4=坡道, 5=红外, 6=灰度, 7=十字路口, 8=一键自检, 9=机器人动作, 10=门颜色, 11=OCR, 12=二维码。`debug_test_item` 优先级高于 UART 设置的 `test_flag`。

---

## 十九、一键自检 ([chassis_api.c](Application/chassis_api.c))

`Chassis_SelfCheck()` 架车黑毯上每秒监测：
- 陀螺仪漂移: 角度变化 > 1°/s → `0x01`
- 灰度传感器: AD_Value_Gray ≥ 500 → `0x02`
- 循迹板: detail ≠ 0 → `0x04`

仅状态变化时打印，安静时无输出。调用于 `main_task.c` 的 `MAIN_DEBUG` 块。

---

## 二十、git 分支

- 当前工作区: `codex/restore-barrier-main-task`（2026-08-17 快照） | 历史主分支: `feature_backup` / `main`
- 项目路径: `C:\Users\14166\Desktop\MC_32\robotcup\xunbao`

---

## 二十一、地图修改指南（浓缩版）

> 由原《MDK-ARM\地图快速修改指南.md》浓缩并入（2026-08-27），独立文件已删除。以后改地图只看这一节即可；机制细节见前面各节。其核心结论：**改地图 = 改 `map_message.c` 的 `NavEdgeTbl[]`（唯一人工编辑源）+ `config.h` 的几何/开关**，执行层三数组自动重建。

### 21.1 一句话结论与四大改动点

图已收敛为**单张自描述边表 `map_message.c:NavEdgeTbl[]`**；执行层 `Node[]/ConnectionNum/Address` 由 `nav_graph_init()` 自动构建；场地几何与开关集中 **`config.h`**。换图通常只需动 4 处：

1. `Application/map_message.c` — `NavEdgeTbl[]` 的 `from/to/flag/angle/step/speed/func`，并同步 `map_message.h` 的 `#define NAV_EDGE_COUNT`
2. `Application/config.h` — 门区 `DOOR_LEN_*`/`ANGLE_*`/`DOOR_RETREAT_*`、楼梯长、场地/调试开关、`LEN_SCALE`
3. `Application/map.c` — 初始 `route[]`（或用 planner 生成）、转弯前补偿距离
4. `Application/barrier.c` — 第一轮 QR/门/宝物改路、第二轮 `get_newroute()` 拼接

### 21.2 各文件职责（地图变动时动哪些）

| 文件 | 作用 | 地图变动时改什么 |
|------|------|------------------|
| `config.h` | 所有开关/场地参数（唯一配置入口） | 调场地/开关只改这里 |
| `map.h` | `MapNode` 枚举、`NODE` 结构 | 增删节点时改枚举 |
| `map_message.c/h` | `NavEdgeTbl[]`（唯一人工编辑源）+ `nav_graph_init()` 自动构建 CSR | 路段 `from/to/flag/angle/step/speed/func`、`NAV_EDGE_COUNT` |
| `nav_planner.c/h` | 最短路/必经点/拼接（见 §4.5） | 想改算法才动；调 `NavObsPenalty[]`/`NAV_W_*` |
| `map.c` | `route[]`、`Navigation()`、转弯前距离 | 初始路线、转弯补偿 |
| `barrier.c` | `door()`、各改路函数、`get_newroute()` | 第一轮动态改路、第二轮路线拼接 |
| `main_task.c` | 主循环、二轮启动 | 二轮入口、`door_pass[]` 预设（开关在 config.h） |

### 21.3 常见修改场景（改哪里）

| 场景 | 改哪里 |
|------|--------|
| 某段变长/变短 | `map_message.c` 对应边 `step`（单位 cm） |
| 某段转弯角度变了 | `map_message.c` 对应边 `angle`；门区段改 `config.h` 的 `ANGLE_*` |
| 某段速度不合适 | `map_message.c` 对应边 `speed`（`SPEED0~SPEED5`） |
| 某段巡线方式不对 | `map_message.c` 对应边 `flag`（`LEFT_LINE/RIGHT_LINE/NEAR_CENTER/Temp_L/R`） |
| 增删节点 | `map.h` 枚举 + `map_message.c` 增删行 + `map_message.h` `NAV_EDGE_COUNT`（`Node[]/ConnectionNum/Address` 自动生成） |
| 门位置/数量变了 | `config.h` 宏、`door()` 状态机、`door_pass[]` 下标、各门分支路线 |
| 第一轮路线变了 | `map.c` 初始 `route[]`、`barrier.c` QR/门/宝物改路 |
| 第二轮路线变了 | `barrier.c` `get_newroute()` 里 `pre/entry/tour/tail` |
| 只是换场地、节点没变 | 通常只改 `map_message.c` 的 `step/angle`、`config.h` 门区宏和路线数组 |

### 21.4 修改流程

1. 读新图/新说明，与当前 `NavEdgeTbl[]`、`route[]` 做差异对比。
2. 改 `map_message.c` `NavEdgeTbl[]`（只改有变化的边，其余保留；`from/to/flag/angle/step/speed/function` 都用原宏/名）。
3. 同步 `map_message.h` `#define NAV_EDGE_COUNT`；增删节点时改 `map.h` `MapNode` 枚举。
4. 改 `config.h` 门区宏。
5. 改 `map.c` 初始路线（或用 planner 生成）和门分支路线。
6. 改 `barrier.c` 动态改路函数、`get_newroute()`（`USE_PLANNER_ROUTE=1` 时全程由 planner 生成；门色仅保留为必经点约束）。
7. 核对连通性：跑 `_weight_calib.py` / `_check_csr.py`。
8. 核对方向：`NavEdgeTbl[]` 是有向边，反向需单独存在或由角度宏派生。
9. 编译，预期 0 Error 0 Warning；输出"改动清单"、标出需现场实测的 step/angle/speed。

### 21.5 改完必须核对

- 每条路线 `0xFF` 结尾，长度 ≤ 100；相邻节点在 `NavEdgeTbl[]` 中必须存在有向连接。
- 新增节点：`map.h` 枚举 + `NavEdgeTbl[]` 增行 + `NAV_EDGE_COUNT` 同步（三数组自动生成）。
- 门区段长度/角度只改宏（`config.h`），不要改散落的手工值。
- 门区段共 8 条双向边：N5-N12、N5-N8、N3-N8、N3-N10。
- 反向路段角度与正向差约 180°，`ANGLE_REV()` 自动算。
- 平台/南极结束保留 `nodes.nowNode.function`，不要误清。
- 改完 `route[]` 后 `mapInit()` 的起始节点逻辑不能冲突。

### 21.6 当前常量速查

**节点编号**（枚举顺序即索引，不能调换）：
```
S1=0  P1=1  N1=2  B1=3  B2=4  B3=5  N2=6  P2=7  S2=8  P3=9
N3=10 N4=11 N5=12 N6=13 P4=14 N7=15 P6=16 B8=17 B9=18 N8=19
C1=20 C2=21 C3=22 N9=23 N10=24 N12=25 N13=26 P5=27 N14=28 S3=29
S4=30 N15=31 S5=32 C4=33 C5=34 B4=35 B5=36 B6=37 B7=38 N16=39
N18=40 N19=41 P7=42 N20=43 N22=44 C6=45 C7=46 C8=47 C9=48 P8=49
N11=50 G1=51 B10=52 B11=53
```
**B10/B11**（波动板节点，正反向共用，见 §八）：B10=N14–C7 段板尾(C7 侧)，B11=C8–C4 段板尾(C4 侧)。正向 `N14→B10→C7`、`C8→B11→C4`；反向 `C7→B10→N14`、`C4→B11→C8`。进板边 `BLBL`(flag NO)、出板边 `NONE`(flag=路口视觉标志)；板节点为直通点。

**第一轮初始**：`route[] = {B1, N1, P1, N1, B2, N4, N5, 0xFF}`（P1 读 QR：百位 3→先去 P3、4→先去 P4、0→直接到 N5 门区）
**第一轮线索平台**：A=5,B=7→`rout_57`；5,8→`rout_58`；6,7→`rout_67`；6,8→`rout_68`
**门分支**（实际被调用）：`door1route={N3,N8,0xFF}`、`door6route={N4,B3,N2,P2,0xFF}`、`door7route={N8,N3,N4,B3,N2,P2,0xFF}`、`door8route={N4,B3,N2,P2,0xFF}`、`door11route={N5,N4,B3,N2,P2,0xFF}`（其余 door2route/door3_1/door4/5/9/10/12 暂未调用，可保留备用）
**第二轮拼接**（`get_newroute()`）：`pre={B1,N1,P1,N1,B2,N4,N3,P3,N3,N4,N5,N6,P4,N6,N5}`；`tour={N13,P5,N13,N12,N16,N18,B5,N19,C6,B7,N22,C9,P7,C9,N22,B6,N20,P8,N20,C4,B11,C8,C7,B10,N14,C3,N9,B9,N7,P6,N7,B8,N9,N10}`；宝藏=P6 时用 `tour_p6`。
（`USE_PLANNER_ROUTE=1` 时首轮和第二轮全程均由 planner 从必经点生成；上述数组只作为关闭开关时的兼容回退，见 §4.5。）

### 21.7 给我信息模板

```
新地图：<文件路径/图片位置>
与旧图差异：
- 平台编号/位置：P1..P8 是否变化
- 新增/删除节点：哪些编号
- 门/指示牌：数量、位置、颜色、方向
- 路段长度：哪一段从多少改到多少（cm）
- 转弯角度：哪一段改多少度
- 障碍物：类型和位置
- 两轮策略：第一轮/第二轮路线是否要改
- 现场实测后要微调的值：step / angle / speed / DOOR_LEN / ANGLE
```

### 21.8 调试开关

全部集中在 `config.h`（见 §十八）。正式比赛前 `MAIN_DEBUG`、`STEP_DEBUG` 必须改回 `0`；当前 `USE_PLANNER_ROUTE=1`，改图或调权重后先 MDK 编译确认 0 error 再上真车。
