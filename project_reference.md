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
  ├── turn.c/h        # 转弯控制（原地转、陀螺仪转、360°转）
  ├── gray.c/h        # 灰度传感器(I2C软件模拟)
  ├── IIC.c/h         # 软件I2C
  ├── motion.c/h      # 运动控制
  ├── command.c/h     # 调试串口缓冲区
  ├── delay.c/h       # 延时
  └── sys.h           # 系统类型定义(u8/u16等)

Core/                 # STM32 HAL核心
  ├── Inc/            # FreeRTOSConfig, adc, dma, gpio, main, tim, usart, it
  └── Src/            # main.c, freertos.c, gpio.c, adc.c, tim.c, usart.c 等

Math/                 # 算法库
  ├── pid.c/h         # PID控制器（增量式+位置式）
  ├── filter.c/h      # 去极值平均滤波
  └── sin_generate.c/h# 正弦波生成

Module/               # 外设驱动
  ├── imu.c/h         # IMU姿态解算（USART3+DMA+IDLE中断）
  ├── K210.c/h        # K210 AI摄像头
  ├── QR.c/h          # 二维码识别
  ├── openmv.c/h      # OpenMV相机
  ├── Rec_usart.c/h   # 串口接收
  ├── Rudder_control.c/h # 舵机控制
  ├── adc.c/h         # ADC读取（电池/灰度）
  ├── bsp_buzzer.c/h  # 蜂鸣器
  ├── bsp_led.c/h     # LED指示灯
  └── bsp_linefollower.c/h # 巡线传感器底层

Motor/                # 电机驱动层
  ├── motor.c/h       # PWM输出(motor_set_pwm)
  ├── Encoder.c/h     # 编码器读取(四路定时器编码器模式)
  └── speed_ctrl.c/h  # 已废弃，功能迁移至chassis_api

Task/                 # FreeRTOS任务
  ├── motor_task.c/h  # 电机控制任务（核心，5ms周期）
  ├── main_task.c/h   # 主任务
  ├── task_create.c/h # 任务创建
  ├── ArriveDetect_task.c/h # 节点到达检测
  └── temporary_task.c/h    # 临时任务

USMAT/                # USMART串口调试组件
MDK-ARM/              # Keil工程文件
test1.ioc             # CubeMX配置
```

---

## 二、任务与调度

| 任务 | 函数 | 优先级 | 栈大小 | 周期 |
|------|------|--------|--------|------|
| motor_task | `motor_task()` | 10 | 512字 | 5ms |
| main_task | `main_task()` | - | - | 5ms |
| ArriveDetect_task | - | - | - | - |

**关键时序**: motor_task 每 5ms 执行: 读编码器 → 模式切换 → 巡线/转弯/陀螺仪 → PID → 调PWM。

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
// 四个电机的内环PID对象（增量式PID）
struct I_pid_obj { float output; int bias; int last_bias; int last2_bias; float measure; float target; };
extern struct I_pid_obj motor_L0, motor_L1, motor_R0, motor_R1;
extern struct PID_param motor_pid_paramL0, motor_pid_paramL1, motor_pid_paramR0, motor_pid_paramR1;

// 巡线外环PID对象（位置式PID）
extern struct P_pid_obj line_pid_obj;    // 巡线PID
extern struct P_pid_obj gyroT_pid;       // 转弯PID
extern struct P_pid_obj gyroG_pid;       // 陀螺仪直行PID
extern struct PID_param line_pid_param, lineG_pid_param;
extern struct PID_param gyroT_pid_param, gyroG_pid_param;
```

**Bias类型问题**: `I_pid_obj.bias` 是 `int`，但 `measure`/`target` 是 `float`，`bias = target - measure` 会截断小数，**低速时PID精度严重丢失**。

### 4.2 底盘状态 ([chassis_api.h](Application/chassis_api.h))

```c
struct Motors {
    float Lspeed, Rspeed;         // 左右轮目标速度
    float Cspeed;                 // 巡线速度
    float Gspeed;                 // 陀螺仪速度
    float GyroT_speedMax;         // 转弯最大速度
    float GyroG_speedMax;         // 直行最大速度
    float encoder_avg;            // 编码器平均
    float Distance;               // 累计里程(cm)
    float Cincrement;             // 巡线加速度
    float CDOWNincrement;         // 巡线减速度
    float Gincrement;             // 陀螺仪加速度
    float GDOWNincrement;         // 陀螺仪减速度
};
extern volatile struct Motors motor_all;
extern float TC_speed, TG_speed;  // 巡线/陀螺仪渐变速度
extern volatile uint8_t PIDMode;  // 当前模式: is_No/is_Free/is_Line/is_Turn/is_Gyro
```

### 4.3 地图导航 ([map.h](Application/map.h))

```c
typedef struct _node {      // 地图节点
    u8 nodenum;             // 节点编号
    u32 flag;               // 标志位（转弯方式/巡线模式等）
    float angle;            // 目标角度
    u16 step;               // 步长(cm)
    float speed;            // 速度
    u8 function;            // 功能（障碍类型）
} NODE;

extern NODE Node[126];      // 完整地图节点数组
extern u8 route[100];       // 当前路径
extern NODESR nodesr;       // lastNode/nowNode/nextNode
```

### 4.4 障碍标志 ([barrier.c](Application/barrier.c))

```c
uint8_t color_flag[5];  // 颜色门标志(D2~D5,D1)
uint8_t isStage;        // 是否在平台上
uint8_t treasure;       // 宝物编号
uint8_t DownLiuShui;    // 流水下坡标志
float LiuShuiRate;      // 流水速度倍率(默认1.6)
uint8_t QR_code;        // 二维码结果
uint8_t get_cude, get_a, get_b; // 线索标志
```

---

## 五、PID 配置

### 5.1 内环速度PID ([pid.c:140-181](Math/pid.c#L140-L181))

| 参数 | L0 | L1 | R0 | R1 |
|------|----|----|----|----|
| Kp | 40 | 40 | 40 | 40 |
| Ki | 10 | 10 | 10 | 10 |
| Kd | 5 | 5 | 5 | 5 |
| outputMax | MOTOR_PWM_MAX | 同左 | 同左 | 同左 |
| actualMax | 100 | 100 | 100 | 100 |

### 5.2 外环PID ([pid.c:183-237](Math/pid.c#L183-L237))

| 用途 | Kp | Ki | Kd | outputMax |
|------|----|----|----|-----------|
| 巡线(line) | 10.5 | 0 | 500 | ±100 |
| 转弯(gyroT) | 4.0 | 0 | 70 | ±100 |
| 陀螺仪直行(gyroG) | 2 | 0.004 | 0.5 | ±100 |
| 灰度(lineG) | 15 | 0 | 5 | ±100 |

### 5.3 速度等级 ([chassis_api.h](Application/chassis_api.h))

```c
SPEED0=25, SPEED1=36, SPEED2=45, SPEED25=55, SPEED3=60, SPEED4=70, SPEED5=75
```

不同速度对应不同巡线PID参数（在 `Chassis_SetTargetSpeed` 中设置）：
- SPEED4: kp=4.0, kd=300
- SPEED3: kp=7, kd=300
- SPEED2: kp=7.0, ki=0.008, kd=400
- SPEED0/1: kp=7.0, kd=350

---

## 六、模式枚举 ([motor_task.h](Task/motor_task.h))

```c
typedef enum {
    is_No = 0,   // 关闭所有
    is_Free,     // 开环（直接设PWM）
    is_Line,     // 巡线模式
    is_Turn,     // 转弯模式（原地转/平台转/360°转）
    is_Gyro,     // 陀螺仪模式（沿指定角度直行）
};
```

巡线模式子模式 ([chassis_api.h](Application/chassis_api.h)):
```c
TRACK_ALL=0, TRACK_LEFT_EDGE, TRACK_RIGHT_EDGE, TRACK_LIUSHUI
```

---

## 七、电机与编码器映射

### 7.1 电机编号 ([motor.c:46-86](Motor/motor.c#L46-L86))

```
motor_set_pwm(1, pwm) → L0 (左前) → TIM9_CH1/CH2 → PE5/PE6
motor_set_pwm(2, pwm) → L1 (左后) → TIM8_CH3/CH4 → PC8/PC9
motor_set_pwm(3, pwm) → R0 (右前) → TIM4_CH3/CH4 → PD14/PD15
motor_set_pwm(4, pwm) → R1 (右后) → TIM4_CH1/CH2 → PD12/PD13
```

正转: 原值 → CCRx=0, CCRy=ccr
反转: 取反 → CCRx=ccr, CCRy=0

### 7.2 编码器 ([motor_task.c:304-330](Task/motor_task.c#L304-L330))

```
TIM1_CNT → Speed[0] → motor_L0.measure (左前，正)
TIM2_CNT → Speed[1] → motor_L1.measure (左后，正)
TIM3_CNT → Speed[2] → motor_R0.measure (右前，取反)
TIM5_CNT → Speed[3] → motor_R1.measure (右后，取反)
```

编码器每圈 5720 脉冲，减速比 0.362，轮径 104mm。
里程公式: `Distance += (avg_encoder * 10.4 * PI / 5720) / 0.362`

### 7.3 巡线传感器

16路，通过 GPIO 读引脚取反（0=黑线，1=白底），`ReadLineSensorDetail()` 返回 uint16_t 位图。

权重表: `line_weight[16] = {-3, -2.4, -1.8, -1.3, -0.9, -0.6, -0.4, -0.2, 0.2, 0.4, 0.6, 0.9, 1.3, 1.8, 2.4, 3}`

---

## 八、地图节点功能 ([map.h](Application/map.h))

```c
enum barriers {
    NONE=1, UpStage, Bridge, Hill, LBHill, SM, View, View1, BACK,
    BSoutPole, QQB, BLBS, BLBL, DOOR, BHM, IGNORE, UNDER, Special_node, DOOR1, UpStageP2
};
```

障碍函数映射 ([map.c:560-585](Application/map.c#L560-L585)):
```
UpStage   → Stage()        // 旋转平台
Bridge    → Barrier_Bridge() // 过桥
Hill      → Barrier_Hill()  // 山地
BSoutPole → South_Pole()   // 南极
QQB       → QQB_1()        // 跷跷板
BLBS      → Barrier_WavedPlate(87)  // 蓝波动板
BLBL      → Barrier_WavedPlate(160) // 红波动板
BHM       → Barrier_HighMountain()  // 高山
DOOR      → door()          // 开门
```

---

## 九、Cross() 流程 ([map.c:318-556](Application/map.c#L318-L556))

```
1. map.point==0 → 初始化路径
2. is_near_end==0:
   a. route_state==0: 清零里程, 设巡线模式
   b. 里程<50%: 设速度, 调用Chassis_EnableAntiSnake()
   c. 里程≥50%: 切换巡线模式(Temp_L/R/LiuShui)
   d. 里程≥70%: 判断转弯角度, 降速, is_near_end=1
3. is_near_end==1:
   a. map_function() 执行障碍功能
   b. 通知ArriveDetect_task, 等待到达确认
4. 节点切换:
   a. 无需转弯 → Handle_NoTurn_StraightPath()
   b. L_follow → Chassis_Turn_By_LeftLine_Blocking()
   c. R_follow → Chassis_Turn_By_RightLine_Blocking()
   d. STOPTURN或>90° → 停车 → 原地转
   e. 其他 → 陀螺仪不停车转弯
```

---

## 十、IMU 数据流 ([imu.c](Module/imu.c))

- USART3 DMA 接收，IDLE 中断触发
- 协议: 0x55 开头，10字节校验和
- 输出: `imu.yaw/roll/pitch` (±180°)
- `imu.yaw -= basic_y` 归零校正
- `imu_shared_data` 通过互斥锁保护（中断中用 FromISR 版本）
- `getAngleZ() = get_latest_yaw() + imu.compensateZ` 返回带补偿的偏航角

---

## 十一、已知 Bug 清单

### P0（已修复 ✓）
1. **PID bias int→float** [pid.h:8](Math/pid.h#L8): `I_pid_obj.bias` 改为 `float`
2. **barrier.c 赋值写为比较** [barrier.c:1229]: `getZ == 0` → `getZ = 0`
3. **barrier.c 除零保护** [barrier.c:753/813/1032]: `sum_angle/add_time` 添加 `if(add_time > 0)` 保护

### P1（重要）
4. **未使用的全局变量** [map.h:188-326]: ~120个 Clue*route 外部声明，占用 namespace
5. **R1 PID初始化死代码** [pid.c:167-180]: 注释掉的初始化块，后续又重复
6. **5ms循环中printf** [motor_task.c:95-96]: 串口输出影响实时性
7. **Cross()函数过大** [map.c:318]: 单函数包含完整路径状态机，状态变量分散

### P2（可优化）
8. **转弯前距离硬编码** [map.c:189-233]: if链应改用查表
9. **main_task.c 引用 speed_ctrl.h** 需确认文件是否已删除
10. **filter_motor_speed() 窗口过小** [filter.c:56-93]: 4点窗口，去极值后只剩2点平均
11. **Stage_P2 死循环** [barrier.c]: `if(Backtimes==1) while(1);`

---

## 十二、关键 API 函数表 ([chassis_api.c](Application/chassis_api.c))

| 函数 | 功能 | 调用者 |
|------|------|--------|
| `Chassis_Init()` | 初始化底盘状态 | motor_task |
| `Chassis_SetMode(mode)` | 设置 PID 模式 | map.c |
| `Chassis_SetTargetSpeed(speed)` | 设速度(自动映射PID参数) | map.c |
| `Chassis_SetTrackMode(mode)` | 设巡线模式(双边/左/右/流水) | map.c |
| `Chassis_MotorControl(mode,L,R,aim)` | 统一运动控制入口 | map.c/barrier.c |
| `Chassis_Brake()` | 急刹 | map.c |
| `Chassis_TurnToAngle_Blocking(angle,orig,ratio)` | 阻塞转指定角度(含等待) | chassis_api内部 |
| `Chassis_MoveDistance_Blocking(dist)` | 阻塞走指定距离 | chassis_api内部 |
| `Chassis_DriveDistance_Blocking(mode,dist,speed,aim,edge)` | 临时模式行驶固定距离 | map.c |
| `Chassis_OverrideLinePid(kp,ki,kd,max)` | 临时覆盖巡线PID | map.c |
| `Chassis_Periodic_Update_5ms()` | 游龙防护等周期更新 | motor_task (每5ms) |
| `Chassis_EnableAntiSnake()` | 激活游龙防护 | map.c |

---

## 十三、常量参数

- **PWM频率**: TIM4/8/9/12 均为 10800-1 周期，Prescaler=0 → 216MHz/10800 = 20kHz
- **PWM最大值**: 一般 9800，转弯模式限 5000
- **系统时钟**: HSE 8MHz → PLL x54 → 216MHz SYSCLK
- **APB1**: 54MHz (TIM 108MHz) | **APB2**: 108MHz (TIM 216MHz)
- **FreeRTOS tick**: 1000Hz (configTICK_RATE_HZ=1000)
- **巡线传感器**: 16路 GPIO 读取
- **编码器**: TIM1/2/3/5 编码器模式，ARR=65535

---

## 十四、IO 引脚分配

| 外设 | 引脚 | 功能 |
|------|------|------|
| USART1 | PA9/PA10 | 调试串口 |
| USART3 | PB10/PB11 | IMU(陀螺仪) |
| UART4 | PC10/PC11 | 串口通信 |
| UART5 | PC12/PD2 | 串口通信 |
| UART7 | PE7/PE8 | 串口通信 |
| UART8 | PE0/PE1 | K210/OpenMV |
| TIM1_CH1/CH2 | PE9/PE11 | 编码器(左前) |
| TIM2_CH1/CH2 | PA5/PB3 | 编码器(左后) |
| TIM3_CH1/CH2 | PA6/PA7 | 编码器(右前) |
| TIM5_CH1/CH2 | PA0/PA1 | 编码器(右后) |
| TIM4_CH1~4 | PD12~PD15 | 右后/右前 PWM |
| TIM8_CH3/CH4 | PC8/PC9 | 左后 PWM |
| TIM9_CH1/CH2 | PE5/PE6 | 左前 PWM |
| TIM12_CH1/CH2 | PB14/PB15 | 舵机 PWM |
| ADC1_IN2/3/14/15 | PA2/PA3/PC4/PC5 | 电池/灰度 |

---

## 十五、git 分支信息

- 当前分支: `study_code`
- 主分支: `main`
- 最近提交: `4f4816f` 接口验证完成
