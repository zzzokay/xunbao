# 项目参考文档 — xunbao (寻宝)

> MCU: STM32F750V8Tx | 工具链: MDK-ARM V5.32 | FreeRTOS + CMSIS_V1 | 216MHz

---

## 一、项目结构

```
Application/          # 应用层 — 地图导航、障碍处理、底盘API
  ├── chassis_api.c/h # 底盘API中间件（核心解耦层）
  ├── map.c/h         # 地图导航 / Navigation()路径规划
  ├── map_message.c/h # 地图数据（Node[]连接表）
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
**标定**：实测车走 100 代码单位 ≈ 120cm → `#define LEN_SCALE 1.2f`（[chassis_api.h](Application/chassis_api.h)）。
**用法**：各处距离阈值已按 **cm = round(代码单位 × LEN_SCALE)** 直接折算为**整数厘米内联**在代码中（精确到 1cm），不再写 `×LEN_SCALE` 表达式。**LEN_SCALE 宏仅用于 motor_task 里程公式的比例补偿**（里程是运行时连续累加，无法内联）。
**覆盖范围**（共 250 处，已验证零遗漏零误伤）：
- 里程公式 `motor_task.c:182`：`Distance += ((encoder_avg*10.4*PI/5720)/0.362) * LEN_SCALE`（比例补偿）
- `map_message.c` Node[132] 表全部 step 字段（130 条边，如 `280→336`、`180→216`）
- `barrier.c`（90 处）：`Chassis_DriveDistance_Blocking` 距离、`Chassis_GetMileage`/`mileage_br` 比较、`Stage_DetectedRamp` 距离、`nodes.nowNode.step=`、`door_set_pass_node`/`door_retreat` 距离、`RampCtrl_Blocking` max_distance、QQB `dis`
- `map.c`（32 处）：`Barrier_WavedPlate`、两个 GetForwardDistance* 的 return 距离
- `main_task.c`（7 处）：`Chassis_DriveDistance_Blocking` 距离

> 注：`RampCtrl_Blocking` 只有最后一个参数 max_distance 是长度（thresh/speed/angle/max_correction 非长度，如 `15`/`20.0f`/`0.08` 保留）；`Stage_DetectedRamp` 的距离参数折算（其俯仰阈值 10° 非长度不折）；`return 0;` 等非长度返回值不折。
> **重新标定**：改 chassis_api.h 的 LEN_SCALE + 重算各处内联值（cm = round(代码单位 × 新倍率)）；原代码单位值在 git 历史中可查。
> **门区段距离**：`door_set_pass_node`/`door_retreat` 的门区段长度已集中为 [map_message.h](Application/map_message.h) 的 `DOOR_LEN_*`（6 条全长，map DOOR 条目用 `宏/2`）/ `DOOR_RETREAT_*`（4 个回退距离）宏（2026-08-13），改长度只改宏即可。当前工作区（2026-08-17）：`DOOR_LEN_N5N12/N3N10=200`，`DOOR_LEN_N5N8/N8N10/N3N8/N8N12=190`；`DOOR_RETREAT_N5N8/N5N4=67`、`DOOR_RETREAT_N10N8=80`、`DOOR_RETREAT_N8N5=65`。
> **门区段角度**：[map_message.h](Application/map_message.h) 的 `ANGLE_N3N8(145)/ANGLE_N5N8(35)`（正向基准），`ANGLE_N8N12=ANGLE_N3N8`、`ANGLE_N8N10=ANGLE_N5N8`（门两侧平行）；反向用 `ANGLE_REV(a)`（正角减180/负角加180，锁定 [-180,180]）派生 `ANGLE_N8N3(-35)/ANGLE_N8N5(-145)/ANGLE_N12N8(-35)/ANGLE_N10N8(-145)`（2026-08-16）。map_message.c Node 表 8 处门区段角度全部改用宏，原手工值（N8→N3 -45、N8→N5 -140、N8→N12 140、N8→N10 33、N12→N8 -43、N10→N8 -150）作废，改角度只改宏。

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
| `DEBUG` | [barrier.c](Application/barrier.c):33（当前默认 0） | Door_ReadPass 用 `debug_door_pass[5]` 预设数组模拟 |
| `MAIN_DEBUG` | [main_task.c](Task/main_task.c):27 | 跳过 Navigation()，执行 `test_flag`/`debug_test_item` |
| `SKIP_ROUND1` | [map.h](Application/map.h):8（当前工作区 1） | 跳过第一轮直接进第二轮（调试用）；main_task.c 初始化预设 `door_pass[5]`+`treasure`+`map.routetime=1`，首周期走真实二轮分支。**关键**：二轮分支 `get_newroute()` 后须再置 `routetime=2`（get_newroute 内部 mapInit 清 0），二轮全程 `routetime==2` 屏蔽 P7/P8 treasure 改路并保证跑完即停；`treasure!=0` 屏蔽 P1 残留 QR 改路 |

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
