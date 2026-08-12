# 项目参考文档 — xunbao (寻宝)

> MCU: STM32F750V8Tx | 工具链: MDK-ARM V5.32 | FreeRTOS + CMSIS_V1 | 216MHz

---

## 一、项目结构

```
Application/          # 应用层 — 地图导航、障碍处理、底盘API
  ├── chassis_api.c/h # 底盘API中间件（核心解耦层）
  ├── map.c/h         # 地图导航 / Cross()路径规划
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
| main_task | `main_task()` | 5 | 2048字 | 5ms |
| motor_task | `motor_task()` | 6 | 512字 | 5ms |
| ArriveDetect_task | `arrive_detect_task()` | 3 | 512字 | - |

> 注：motor_task 优先级为 **6**（motor_task.h，configMAX_PRIORITIES=7，合法 0~6，已是最高的合法优先级）；main_task(5) **低于** motor_task(6)，当前配置下主任务无法抢占饿死电机任务（FreeRTOS 数值越大优先级越高）。Start_task 现含 IMU 上电自检（见已修复表 2026-08-10）。

**关键时序**: motor_task 每 5ms: 读编码器 → 模式切换 → 巡线/转弯/陀螺仪 → PID → 调PWM。

---

## 三、核心数据流

```
map.c:Cross() → Chassis_MotorControl(mode, Lspeed, Rspeed, aim)
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
struct I_pid_obj { float output; int bias; int last_bias; int last2_bias; float measure; float target; };
extern struct I_pid_obj motor_L0, motor_L1, motor_R0, motor_R1;
extern struct PID_param motor_pid_paramL0, motor_pid_paramL1, motor_pid_paramR0, motor_pid_paramR1;
extern struct P_pid_obj line_pid_obj, gyroT_pid, gyroG_pid;
extern struct PID_param line_pid_param, lineG_pid_param, gyroT_pid_param, gyroG_pid_param;
```

**Bias类型问题**: `bias` 是 `int`，`bias = target - measure` 会截断小数，低速时PID精度丢失。

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
extern NODE Node[126], route[100];
extern NODESR nodesr;  // lastNode/nowNode/nextNode
extern volatile uint8_t cross_event;
#define CROSS_EVENT_ARRIVED (1<<0)   // 已到达节点
#define CROSS_EVENT_DOOR    (1<<1)   // 门结果就绪
```

### 4.4 障碍标志 ([barrier.c](Application/barrier.c))

```c
uint8_t door_pass[5];    // 门通行状态(D2~D5,D1)：CAN_PASS/ONE_WAY_PASS/NO_PASS
uint8_t treasure;        // 宝物编号
uint8_t DownLiuShui;     // 流水下坡标志
float LiuShuiRate;       // 流水速度倍率(1.6)
uint8_t QR_code, get_cude, get_a, get_b;
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
| 巡线(line) | 10.5 | 0 | 500 | ±80 |
| 转弯(gyroT) | 4.0 | 0 | 70 | ±80 |
| 陀螺仪直行(gyroG) | 2 | 0.004 | 0.5 | ±80 |
| 灰度(lineG) | 15 | 0 | 5 | ±100 |

### 5.3 速度等级

`SPEED0=25, SPEED1=36, SPEED2=45, SPEED25=55, SPEED3=60, SPEED4=70, SPEED5=75`

速度→PID映射表 `line_pid_steps`（chassis_api.c 静态常量，2026-08-09 起改为**按当前实际速度阶梯选择**）：
- SPEED5/4: kp=3.5, kd=200 | SPEED3: kp=4.0, kd=120 | SPEED25: kp=5.0, kd=150
- SPEED2: kp=6.5, kd=110 | SPEED0/1/20: kp=6.0, kd=90 | 低速12/15: kp=15.0, kd=60

**阶梯选择机制**：`Chassis_SetTargetSpeed` 只设置 `motor_all.Cspeed`（目标速度），不再写 `line_pid_param`；
motor_task 每 5ms 调用 `Chassis_UpdateLinePidBySpeed()` 读取当前实际速度 `motor_all.encoder_avg`，规则：**只有当前速度 ≤ 某档速度才采样该档 PID**（即取所有 `档速 ≥ 当前速度` 中最低的一档，尽量向上取高速档低 Kp；超过最高档用最高档）。
高速→低速减速过程中 PID 随实际速度逐级下调：减速前期一直保持高速低 Kp，实际速度真正降到某档以下才换更高 Kp —— 既不减速期套用低速高 Kp（12/15→15.0）导致摇摆，也不晚切导致不跟线。
- 游龙 `Chassis_OverrideLinePid` 临时覆盖生效时（`line_pid_override_active`）优先级更高，不在此覆盖

---

## 六、模式枚举 ([motor_task.h](Task/motor_task.h))

```c
typedef enum { is_No=0, is_Free, is_Line, is_Turn, is_Gyro };
```

巡线子模式: `TRACK_ALL=0, TRACK_LEFT_EDGE, TRACK_RIGHT_EDGE, TRACK_LIUSHUI`

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
里程: `Distance += (avg_encoder * 10.4 * PI / 5720) / 0.362`

### 7.3 巡线传感器

16路 GPIO 读取（0=黑线，1=白底），权重表 `line_weight[16] = {-3..3}`。
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
- BLBS→Barrier_WavedPlate(87) | BLBL→Barrier_WavedPlate(160)
- BHM→Barrier_HighMountain() | DOOR→door()

---

## 九、Cross() 流程 ([map.c](Application/map.c))

```
Cross()
├── near_end==0 (巡线行驶)
│   ├── SEG_INIT:       清里程, 设巡线模式
│   ├── SEG_CRUISE:     设速度, 启用游龙
│   ├── SEG_MID_SWITCH: 里程≥50%, 切换巡线模式
│   └── SEG_PREP_ARRIVE:里程≥70%, 降速
│
└── near_end==1 (节点处理)
    ├── Cross_NearEnd: map_function() → 等待到达
    ├── Cross_TurnAndAdvance: 转弯（左follow/右follow/停车原地转/陀螺仪）
    └── Cross_PostProcess: 检查 cross_event → 推进节点
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

### ✓ 已修复主要项
| 修复内容 | 日期 |
|----------|------|
| PID bias int→float | 2026-05-01 |
| barrier.c 赋值写为比较(getZ==0) | 2026-05-01 |
| 除零保护 (sum_angle/add_time) | 2026-05-01 |
| motor_task 10函数 static 化 | 2026-06-27 |
| map.c include 从19精简到5 | 2026-06-27 |
| Cross() 拆40行+6子函数 | 2026-06-27 |
| normalize_angle 提取去重 | 2026-06-27 |
| nodesr.flag 阶段位拆出 | 2026-06-27 |
| Want2Go/Chassis_MoveDistance 去重 | 2026-06-27 |
| 堵转保护 (PWM>7000 硬上限 + 比值检测) | 2026-07-04 |
| 堵转保护调用点全部注释停用（运行时不再触发） | 2026-08-06 |
| Turn_Angle_Base 死区/钳位/TOCTOU | 2026-07-04 |
| Stage_P2/QQB/WavedPlate 状态机重写 | 2026-07-03~04 |
| IMU 偶发初始化失败修复（USART3_IRQHandler HAL_UART_IRQHandler 冲突 + 死代码 gyro_init 删除） | 2026-07-18 |
| scaner.c 循迹显式化：内部去重（count_led_line/pick_best_cluster/ReadLineSensorDetail）+ 合并 getline_error*/getline_error_ex 为 Scaner_Update() + line_data 转 static（新增 ClearLineData/IsLineLost） | 2026-08-06 |
| 红绿灯改版（2026新规则 黑/绿/蓝=不能过/能过/单相通过）：颜色常量改通行语义命名 `CAN_PASS/ONE_WAY_PASS/NO_PASS`（与具体颜色解耦，改色只改 barrier.h 映射 + Door_ReadPass 传感器识别）；`color_flag→door_pass`、`debug_color_flag→debug_door_pass`、`Door_ReadColor→Door_ReadPass` | 2026-08-07 |
| `PIG`→`MIKU` 舵机宏改名（Rudder_control.h/c + barrier.c zhunbei）；修复红绿灯改版遗留漏改 `debug_color_flag→debug_door_pass`（Door_ReadPass DEBUG 分支，编译报 #20 undefined） | 2026-08-07 |
| 修复 K210.c OCR 帧处理遗留旧名 `nodesr→nodes`、`clue_A_stage→flag_clue_stage_A`、`clue_B_stage→flag_clue_stage_B`（P5/P6/P7/P8 门控条件不变，编译报 #20 undefined）；其余 nodesr 引用在注释中 | 2026-08-07 |
| 修复链接 L6200E `UART5_IRQHandler multiply defined`：实际协议处理在 K210.c，CubeMX 生成的 stm32f7xx_it.c 同函数 `#if 0` 禁用。uart.c 不在 Keil 工程；USART3 由 imu.c 提供（it.c 已注释）；USART1 以 stm32f7xx_it.c 为准 | 2026-08-07 |
| 修复路线平台编号写错：按 map_message.c 连接表（P5↔N13、P6↔N7、P8↔N20、P7↔C9）核对，barrier.c `get_newroute()` 45 条 temp 路线 + `update_route_at_P7_for_treasure()` 2 条中 `N13,P6`/`N7,P5`/`C9,P8`/`N20,P7` 统一改 `N13,P5`/`N7,P6`/`C9,P7`/`N20,P8`；map.c 未引用门路线 door2/3_1/4/5/9/10/12route 同步修正（door1/6/7/8/11route 与 rout_57/58/67/68 原本正确）；barrier.c WaitFor_OCR 2350 行 `P5||P5`→`P5||P6` | 2026-08-07 |
| 重写第二轮路线 `get_newroute()`（barrier.c，9 门分支×2=18 条 temp 路线）：宝藏=6 只去 P1→P3→P4→P6 后直接回家；宝藏=2/3/4/5 只去 P1→P3→P4→P5 后直接回家。`switch(treasure)` 由原 5 case（2/3/4/5/6）合并为 2 case（`case 6` + `case 2/3/4/5`），删除各分支 P7/P8 绕行段，保留各分支门控有效路径段（D2/D3/D4/D5 不通时的绕行路径不变） | 2026-08-07 |
| IMU 零位校准 + 角度补偿三行（`IMU_CalibrateZero` + `vTaskDelay(100)` + `mpuZreset`）包装为公共函数 `IMU_Calibrate_Yaw(float referangle)`，放 turn.c/turn.h（`mpuZreset` 同族，turn.c 已含 imu.h 零新增依赖；避免 Module 层 imu.c 倒挂 Application 层）。参考角度由调用方传（main_task.c 传 `nodes.nowNode.angle`），与 map 全局解耦 | 2026-08-07 |
| 修复 barrier.c 编译错误 `#20 DOOR_D5_BACK/DOOR_D4_BACK undefined`：`enum DoorState` 定义在 `Door_ReadPass()`（1542 行）之后，C 枚举常量仅声明后可见；枚举前移到 `Door_ReadPass` 前置声明之前 | 2026-08-09 |
| 巡线PID按当前实际速度阶梯选择（防高速→低速减速期摇摆/不跟线）：`Chassis_SetTargetSpeed` 不再写 `line_pid_param`；新增 `line_pid_steps` 阶梯表，motor_task 每5ms 调 `Chassis_UpdateLinePidBySpeed()` 读 `motor_all.encoder_avg`，规则为只有当前速度≤档速才采样该档PID（尽量向上取）；减速时 PID 逐级下调；游龙 override 生效时不覆盖 | 2026-08-09 |
| IMU 上电自检 + 串口恢复 + ISR 兜底（应对偶发上电角度恒为0，根因=HAL 对 ORE 采取"中止DMA+交用户恢复"策略，与自定义 ISR"先重挂DMA再调 HAL_UART_IRQHandler"叠加成死锁）：imu.c 新增 `IMU_IsDataActive`/`IMU_WaitData`/`IMU_Reinit`（停DMA→清错误标志→重挂→开中断前再清一次ORE）；`USART3_IRQHandler` 开头清 ORE（HAL abort 分支由 errorflags≠0 门控，先清则错误中断不再杀死重挂的 DMA）；Start_task 在 user_init() 后自检，1s 全0则重启串口等2s重试，仍无数据仅警告不阻塞 | 2026-08-10 |
| 寻中线(TRACK_NEAR_CENTER/calc_near_center)：中心两灯(第7、8灯)任一亮即进入中心判定，且**只取最中心两灯**（与 calc_left/right_edge 一致最多取2灯，不再向左右扩出整个连续亮灯段），其余线一律忽略；误差按这两灯实际亮灯位置**成比例计算**（不强制0，避免5/6/7偏心线不修正）。中心灯全灭保持"离中心最近段"兜底。曾尝试强制 error=0+TRUTH_VALID（偏心线不修正）及扩出整段（被旁线拖偏）均撤回 | 2026-08-11 |
| 回退寻中线核心改动（仅 scaner.c + chassis_api.h 改回提交版）：calc_near_center 恢复"中心两灯同时亮才判中心 + 误差强制0 + 离中心最近段兜底"，line_weight_default 权重还原，TRACK_NEAR_CENTER 注释还原；调试配套（main_task 循迹测试 / map 调试路线 / chassis_api.c PID 调参 / barrier.c 坡道时序）保留未提交 | 2026-08-11 |
| 寻中线(calc_near_center)：保留"连续亮灯段"约束（不跨空隙取灯），段内只取最靠中心 2 灯算位置/误差——线最粗 2 格，亮区超过 2 格视为多线/路口，取其中中心处 2 灯追最中线（取消整段平均，粗线不拖偏；原 `MAX_LED>4` 段长否决失效）；中心两灯(7,8)同亮仍走 center 快路径 | 2026-08-12 |
| 寻中线(calc_near_center)：**亮灯总数 ≥ 4 时保守认为线在中心**（error=0 直行），应对旁线/路口干扰不被旁边线拖偏；原有中心两灯快路径、连续亮灯段内取最靠中心 2 灯逻辑不变 | 2026-08-12 |
| 任务周期耗时测量（调试用，测完可删）：motor_task.c/main_task.c 各加 `timing_dwt_init()`（DWT 周期计数器 @216MHz，TRCENA+CYCCNTENA）+ 循环内测量块。motor_task 每100ms 打印 `MOTOR cpu=xxus period=xxms`；main_task 每500ms 打印 `MAIN loop=xxus max=xxus`。用于排查任务饿死。注意 main_task 的 loop 值含阻塞等待（阻塞时 CPU 让出，期间 DWT 计数的是其它任务/ISR 的周期，非主任务自身 CPU 时间） | 2026-08-12 |
| FPU 浮点修复（消除软件 double，全走单精度硬件 FPU；Cortex-M7 仅单精度 FPU）：imu.c `USART3_IRQHandler` `180.0/32768.0`→`180.0f/32768.0f`（中断每帧 3 次软件 double 乘除）；turn/barrier/scaner 11 处 `fabs()`→`fabsf()`（参数全 float）；turn.c:263 活的 `printf("%.2f...")` 注释（拖进 printfa/_fp_digits 浮点格式化库）；pid.c speed_pid_kp/kd/ki `10.0/100.0`→`10.0f/100.0f`；Rec_usart `atof()`→`strtof()`（atof 拖 `__strtod_int`/`_scanf_real`）；sin_generate `sin()`→`sinf()`（未使用、链接器已 GC，保险性修改）。验证：修复前最终 image 含 `__aeabi_dmul/ddiv/dadd/dsub/f2d/d2f/i2d`，修复后应全部消失 | 2026-08-12 |
| 修复 barrier.c 参数未还原/清零遗留：Barrier_Hill 楼梯 `Chassis_OverrideGyroPid(7,0,60,50)` 的唯一 `Chassis_RestoreGyroPid()` 在不可达的 `default:` 分支（HILL_DESCEND 直接置 HILL_DONE 退出，还原从未执行）→ 移到 while 循环结束后，楼梯完成必还原陀螺仪 PID，不再污染后续陀螺仪模式行驶/转弯；Barrier_Bridge 长桥 `is_emergency` 计数上限 `<=10`（卡死 11，`==300` 死代码、`==10` 只触发一次）→ 改 `< 300`，连续偏出时第 10 次(≈50ms)与第 300 次(≈1.5s)各硬修一次 | 2026-08-12 |
| Barrier_HighMountain `HM_APPROACH` 提前切陀螺仪：坡底 `imu.pitch >= Begin_up`（basic_p+5，与 RampCtrl "刚上坡"一致）且里程≥15 即切 `HM_ASCEND_1`，不再等 `Stage_DetectedRamp` 的 10° 俯仰/循迹干扰条件。**根因**：`Stage_DetectedRamp` 俯仰阈值 `imu.pitch >= 10.0f`（绝对值）≈ RampCtrl `Begin_up`(basic_p+5) 的两倍，车在 0°→10° 爬坡期间仍处于巡线模式，而坡面无循迹线+干扰灯（幻影线 1-3 灯）既不被 `ledNum>=4` 捕获也到不了 10°，巡线追幻影线跑偏；`mile>=15` 门限排除起步加速翘头(≤7°)误触发。切过去后 RampCtrl 首个 RAMP_INIT 立即满足 `pitch>=Begin_up`，行为不变。仅作用于 HighMountain；其余平台沿用原 10° 阈值（如需统一改共享 `Stage_DetectedRamp` 的阈值，注意同步回归 Stage/Stage_Home/Bridge/Hill/WavedPlate） | 2026-08-12 |

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

- PWM 20kHz (10800-1, prescaler=0), 一般9800, 转弯限5000
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
| `Stage_turn_Angle(Angle)` | 平台转(ratio=1.15, force=150°) |
| `Turn360Step()` | 360°梯形速度曲线 |
| `Go_Angle(angle, speed, motor)` | 陀螺仪直行 |

Turn_Angle / Stage_turn_Angle 合并: 90%相同，提取 `Turn_Angle_Base` 基函数。
360°转圈: 从 PID+MustBeZero 脉冲改为梯形速度曲线(加速30°→全速30-300°→减速358°→停)。

---

## 十七、安全保护

### 17.1 丢线保护
`is_Line` 下 `line_data[5]` 全无效持续 80×5ms=0.4s 后 `CarBrake()` + `while(1)`。
一次性触发，`Chassis_EnableLineLostProtection()` 重新激活。

### 17.2 横滚角超限保护
`|imu.roll - basic_r| > 40°` 时 `CarBrake()` + `while(1)` 死停。
`Chassis_EnableRollProtection()/DisableRollProtection()`。

### 17.3 堵转保护
- PWM > 7000 硬上限 → 死停
- `output > target × 150` 连续 5 周期 → 死停（比值自适应各转速）
> ⚠️ **2026-08-06 起已停用**：`Chassis_EnableStallProtection()`（chassis_api.c:102 原本就注释）与全部 `Chassis_DisableStallProtection()` 调用点已注释（map.c Nav_TurnAndAdvance、barrier.c 南极 SP_IMPACT 两处）。`stall_protect_enabled` 恒为 0，上述两段检测不再执行。检测逻辑代码保留，恢复时取消调用点注释即可。

### 17.4 翘头保护
`is_Line` 下 `imu.pitch > basic_p + 8°` 时将 `Cincrement` 降至 0.05 抑制加速度，pitch 回落后恢复。需在 `Cross()` 中调用 `Chassis_EnableWheelieProtection()` 激活，使用模式与游龙一致。
阈值 8.0f (`WHEELIE_PITCH_THRESHOLD`) 定义在 `chassis_api.c`。

---

## 十八、无传感器调试模式

| 宏 | 定义位置 | 功能 |
|----|----------|------|
| `DEBUG` | [barrier.h](Application/barrier.h):45 | Door_ReadPass 用 `debug_door_pass[5]` 预设数组模拟 |
| `MAIN_DEBUG` | [main_task.c](Task/main_task.c):29 | 跳过 Cross()，执行 `test_flag`/`debug_test_item` |

测试项: 1=直线, 2=转180°, 3=过坡。`debug_test_item` 优先级高于 UART 设置的 `test_flag`。

---

## 十九、一键自检 ([chassis_api.c](Application/chassis_api.c))

`Chassis_SelfCheck()` 架车黑毯上每秒监测：
- 陀螺仪漂移: 角度变化 > 1°/s → `0x01`
- 灰度传感器: AD_Value_Gray ≥ 500 → `0x02`
- 循迹板: detail ≠ 0 → `0x04`

仅状态变化时打印，安静时无输出。调用于 `main_task.c` 的 `MAIN_DEBUG` 块。

---

## 二十、git 分支

- 当前: `feature_backup` | 主分支: `main`
- 项目路径: `C:\Users\14166\Desktop\MC_32\robotcup\xunbao`
