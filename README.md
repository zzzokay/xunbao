# xunbao
4.14（张东骏）
加入command.c作为调试串口缓存区
发现：每次mx生成完都要注释掉main的定时器中断回调，和stm32f7xx.....里的USART3_IRQHandler(void)
删掉了stm32....里的void UART5_IRQHandler(void)的标志位判定，改用hal自带的api，HAL_UARTEx_ReceiveToIdle_IT


4.18（张东骏）
修改：goline(),runwithangle,将motorall最为参数传入，而不是全局变量，
修改：在scanner.c里增加注释
修改(舍弃)：对轮子测量值进行窗口滤波处理 效果：output变稳定了，应该能提高稳定性

教训：烧了电线，原因是太鲁莽，把负的数传入ccr，想更改电机方向只需修改tim两个通道顺序，同时编码器方向取反

重点问题（已解决）：四个轮子测试单独测试时都能正常运行，但是一起运行时左边正常，右边发疯（应该是正反馈）


使用提示:要调试当个轮子时只需修改rec_uart.h里的宏定义和motortask里的set_pwm;

4.19 （张东骏）
修改：将R0对应的定时器与R1互换，使0为前，1为后；
现象：发现诡异的现象了，右前与右后只转一个轮子两个轮子都有数值（解决；原来是滤波写错了）
完成：终于正常了，四个轮子正常转动（修改：pid限幅调为4000（还是别一下调太高））
修改：把主任务注释掉了，现在来调motorall.cspeed
对了，调试不建议使用蓝牙，蓝牙波特率太慢会破坏5ms周期

4.24 (张东骏)
项目结构大改：上层导航任务与电机任务解耦，使底盘内聚性更高。外部只需调用api无需知道底层原理；新增chassis_api_.c.h
将散落在map.c,barrier。c的电机控制函数全部移动至chassis_api_.c，并做了统一名称处理
寻迹——陀螺仪转换逻辑更改，外部不再需要设置标志位，电机任务内部检查；
切换模式时同时传递目标速度，外部只需要设置小车速度，不需要考虑设置的是寻迹速度还是陀螺仪模式的速度(设置速度唯一api:Chassis_SetTargetSpeed)
游龙算法移至motortask,map.c仅通过标志位触发
在cross显示表示巡线模式（之前用节点标志位直接隐式传）现用标志位，left_right_line,作为判断巡线模式的唯一标准
统一底盘初始化，顺便把user初始化放在starttask;电机变量全部显示初始化

将speed_control逻辑全部移至chassis_api.c.h；彻底移除speed_control.c.h

目前map到chassis_api的再到电机逻辑逻辑基本写完，有部分显示过程，时序理清以及重复减少的优化，整体思路基本不变，
scanner让ai修改过还没仔细检查，后续来看,实际效果好像还行？//TODO
- `handle_qiang_jiao()` 函数（特定场地上坡PID修改）被删除，目前好像还没补回去//TODO
    
---

## Claude 修改记录
//加入project_reference,关于项目的信息，修改，都在里面，可以直接喂给ai


1. **pid.h** — `I_pid_obj.bias` 从 `int` 改为 `float`，修复低速 PID 截断
2. **barrier.c:1229** — `getZ == 0` → `getZ = 0`（赋值写成比较）
3. **barrier.c:753/813/1032** — `sum_angle/add_time` 除零保护


**2026-05-01 上午 — 底盘解耦与模式切换；编码，游龙修改**

4. **chassis_api.c pid_mode_switch** — 进入 is_Turn 只清 gyroT_pid，不再清 line_pid_obj/gyroG_pid
5. **motor_task.c handle_mode_switch** — 新增 Turn→Line/Gyro 的清零转换逻辑
6. **全部源文件** — GBK → UTF-8 编码转换
7. **motor_task.c handle_mode_switch** — 补充模式切换注释（6种切换路径的处理方式和设计要点）
8. **chassis_api.c pid_mode_switch** — 移除 is_Turn 的 gyroT_pid 清零，仅保留 PWM 限幅
9.  **motor_task.c handle_mode_switch** — 新增 Line/Gyro→Turn 清零 gyroT_pid，所有 PID 清零统一在此函数
10. **chassis_api.c** — 删除 chassis.PID_mode，统一使用全局 PIDMode（修复 P1 不同步问题）
11. **chassis_api.c** — 差速限幅统一到 motor_all.Line_speedMax，删除 LINE_SPEED_MAX 宏，OverrideLinePid 改为保存/恢复 motor_all.Line_speedMax
12. **scaner.c** — Go_Line 使用 motor_all.Line_speedMax 替代 LINE_SPEED_MAX 宏
13. **chassis_api.c** — anti_snake 衰减逻辑修复：改为 -= 10 递减，解除条件改为 err_count <= 0
14. **chassis_api.c** — anti_snake PID 覆盖改为通过 OverrideLinePid 机制，解决与 Override 冲突问题
15. **chassis_api.c** — anti_snake 重置移入 pid_mode_switch，修复 is_Turn 绕过 Chassis_SetMode 不清游龙状态的问题

**2026-05-01 下午 — 转弯逻辑重构**

16. **turn.c Turn_Angle + Stage_turn_Angle** — 合并为 `Turn_Angle_Base(Angle, right_ratio)` 基函数，消除 ~40 行重复代码
17. **turn.c Turn360Step** — 从 PID+MustBeZero 脉冲方案重写为梯形速度曲线（加速→全速→减速→停），速度更平滑
18. **turn.c Turn360Step** — `imu.yaw` 改为 `get_latest_yaw()`，通过 mutex 保护 IMU 并发读取
19. **turn.c** — 清理 `MustBeZero`、`Turn360RecallAngle` 死代码

**2026-05-01 晚 — 节点检测任务参数显式化 + 导航逻辑分析**

20. **scaner.c/h** — `Cross_getline(void)` 改为 `Cross_getline(volatile SCANER *scaner)`，显式传参替代隐式全局
21. **ArriveDetect_task.c/h** — `deal_arrive()` 改为 `deal_arrive(volatile SCANER *scaner, uint32_t node_flag)`，消除对 `nodesr.nowNode.flag` 和 `Cross_Scaner` 的隐式依赖
22. **barrier.c / chassis_api.c** — 所有 `Cross_getline()` 调用更新为 `Cross_getline(&Cross_Scaner)`

**2026-05-02 — 巡线逻辑检测与优化**

23. **gray.c ScanerMode_Switch** — 模式切换时清零 `line_data[5]`，避免旧模式历史数据污染新模式
24. **scaner.c Get_scaner_error** — 添加 `last_valid_error` 静态变量，丢线时保持上次有效误差而非返回 0（直行）
25. **scaner.c value_calculation** — LEFT_EDGE / RIGHT_EDGE 合并冗余 `if` 条件，减少重复位运算
26. **scaner.c value_calculation** — `pos /= LED_Num_Temp` 前添加除零保护，LIUSHUI 模式 `len=0` 时返回 -1

**2026-05-02 — 巡线函数结构重构**

27. **scaner.h** — 新增 `enum LineTruth`（TRUTH_VALID/TRUTH_ALL_ERR/TRUTH_POS_ERR），替代魔法数字 0/1/2
28. **scaner.c value_calculation** — 拆分为 4 个 static 函数 `calc_left_edge/calc_right_edge/calc_liushui/calc_track_all`，原函数退化为 switch 分发器
29. **scaner.c error_detect_one** — 重命名为 `coarse_filter`，改为 static
30. **scaner.c Line_Scan** — 扁平化，用 early return 消除嵌套，减少重复的 error 平均计算
31. **scaner.c** — `R_` 宏重命名为 `POS_CLUSTER_RADIUS`；`pos_detect`/`Update_line_data` 改为 static；从 header 移除内部函数声明

---

## 小车导航逻辑

### 概述
小车采用**预定义路线 + 运行时决策**的导航方式。所有可能的路径预先写死在 `route[]` 数组中，运行时根据传感器检测结果选择具体走哪条路线。

### 数据结构
- `route[100]`：路径数组，存储节点编号序列，`0xFF` 表示路径结束
- `nodesr`（NODESR 结构体）：当前导航状态
  - `lastNode`：上一个节点（路径起点）
  - `nowNode`：当前目标节点（路径终点）
  - `nextNode`：下一个目标节点
  - `flag`：运行状态标志位（到达、退回、红灯等）
- `map.point`：route 数组的当前读取索引
- 每个 NODE 包含：`nodenum`（编号）、`flag`（行为标志）、`angle`（航向角）、`step`（段长度）、`speed`（速度）、`function`（特殊功能）

### 核心状态机 — Cross()
每段路径的执行分为两个阶段：

1. **前半段巡线**（`is_near_end == 0`）
   - 0%~50%：正常巡线
   - 50%：切换巡线模式（如左循迹→右循迹）
   - 70%：降速准备转弯，进入节点处理

2. **节点处理**（`is_near_end == 1`）
   - 执行 `map_function()`（障碍物/平台/门等功能）
   - 等待 `arrive_detect_task` 确认到达
   - 执行转弯（原地转/陀螺仪转/巡线加强转）
   - 推进节点：`lastNode = nowNode → nowNode = nextNode → nextNode = route[point++]`

### 路径决策点

#### 1. 门检测（D2~D5）
`door()` 函数在到达门节点时执行。机器人停在门前，用颜色传感器逐个读取 4 道门的灯：
- 红灯 = 门关，绿灯/黄灯 = 门开

根据 4 道门的开关组合，从 12 条预定义路线（`door1route`~`door12route`）中选择一条，覆盖所有 2^4 种情况。

#### 2. 旋转平台颜色检测
到达平台节点（N12/N5）后，`Stage()` 读取灯颜色：
- **红灯**：退回，`flag |= 0x20`，更新 `lastNode` 和 `nextNode`，换方向
- **绿灯/黄灯**：确认 QR 码，`flag |= 0x80`，更新 `nowNode` 和 `nextNode`，规划去宝物平台的路线

#### 3. QR 码路线规划
`update_route_by_QR()` 根据线索位置（`clue_A_stage`、`clue_B_stage`）选择路线：
- 线索在 5 号和 7 号平台 → `rout_57`
- 线索在 5 号和 8 号平台 → `rout_58`
- 线索在 6 号和 7 号平台 → `rout_67`
- 线索在 6 号和 8 号平台 → `rout_68`

### 整体流程
```
起点 N2
  ↓
默认路线: B1→N1→P1（第一个平台）
  ↓
门检测: 读 D2~D5 颜色 → 选 doorXroute
  ↓
沿路线走到旋转平台（N12/N5）
  ↓
读 QR 码 → 知道宝物在哪个平台
  ↓
读灯颜色:
  红灯 → 退回，走另一条路（flag|=0x20）
  绿灯/黄灯 → 确认路线，调用 update_route_by_QR()（flag|=0x80）
  ↓
沿 rout_XX 路线到达宝物平台，取宝物
  ↓
按路线返回终点
```

### 到达检测 — arrive_detect_task
独立任务，通过 FreeRTOS 通知与 main_task 同步。根据 `nodesr.nowNode.flag` 中的标志位判断到达条件：
- DLEFT/DRIGHT：左/右半边 6 灯中 5 个亮
- CLEFT/CRIGHT：左/右分岔路检测
- MUL2SING/MUL2MUL：多线→单线/多线→多线转换
- MORELED：5 个灯以上亮
- AWHITE：全白（全黑）
- RESTMPUZ：到达后执行陀螺仪 Z 轴校正
