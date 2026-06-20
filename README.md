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

**2026-05-26 — 灰度板封装 + 坡道灰度修正 + Barrier_Hill 状态机重构**

32. **gray.c/h** — 新增 `Gray_Open()` / `Gray_Close()` 封装 DMA 启停，替代裸 HAL 调用
33. **gray.c/h** — 删除全部 I2C 相关代码（I2C_Judge/Start/Stop/SendACK/WaitAck/SendByte/ReceiveByte/ReadOnce）及 I2C 宏定义，header guard 改为 `_GRAY_H_`
34. **gray.c/h** — 新增 `Gray_GetAngle()` 坡道灰度角度修正函数，找最大 ADC 值并判断是否明显高于其他传感器，输出对应角度偏移；`DIFF_THRESH` 作为宏定义
35. **barrier.c/h** — `RampCtrl_Blocking` 新增 `uint8_t use_gray` 参数，为 1 时开启灰度 DMA、循环内叠加 `Gray_GetAngle()` 修正角度、退出时关闭灰度
36. **barrier.c** — `Barrier_Hill` 重构为状态机（HILL_APPROACH / HILL_ASCEND / HILL_DESCEND / HILL_DONE），上坡下坡均开启灰度修正，新增 `GyroStableReset` 航向校准
37. **barrier.c** — 5 处 `RampCtrl_Blocking` 调用方补上 `use_gray=0` 参数，保持原行为

**2026-06-10 — 边缘循线优化 + 后退循迹 + 桥下坡修正**

41. **scaner.c calc_left_edge/calc_right_edge** — 边缘循线模式找到第一段连续亮灯后，break 条件加 `|| *lednum >= 2`，最多取 2 个灯。解决交叉线融合点处线宽增加导致位置偏移的问题
42. **scaner.c Go_Line** — 后退时舵向反转（`if (speed < 0) Fspeed = -Fspeed`），传感器在车头为尾随端，方向需取反
43. **barrier.c BRIDGE_ON_BRIDGE** — 桥下坡从单段 `RampCtrl_Blocking` 改为两段 + 中间 15cm 红外修正（`Chassis_CorrectByInfrared`），模仿上桥的红外修正模式

**2026-06-11 — 横滚角超限保护与 IMU 校准扩展**

44. **imu.c/h** — `IMU_CalibrateZero` 新增 `float* roll_out` 参数，同步累计 roll 并输出 10 次采样平均值；新增 `extern float basic_r` 全局零偏值
45. **chassis_api.c** — `Chassis_Periodic_Update_5ms()` 开头增加横滚角超限保护：`imu.roll - basic_r > 40°` 时立即 `CarBrake()` + `while(1)` 死停（受 `roll_protect_enabled` 开关控制）
46. **chassis_api.c/h** — 新增 `Chassis_EnableRollProtection()` / `Chassis_DisableRollProtection()`，与丢线保护 API 风格一致
47. **barrier.c / main_task.c** — `IMU_CalibrateZero` 调用更新为 `(&basic_y, &basic_p, &basic_r)`

**2026-06-18 — update_route_by_QR 重构**

48. **barrier.c** — 新增 `load_route_at(offset, src)` 辅助函数 + `is_green_or_yellow()`，将 `update_route_by_QR()` 中 8 段重复的 route 拷贝循环简化为 `if/else if` 分支 + 两行调用。原函数从 ~100 行缩至 ~30 行

**2026-06-18 — P7/P8 枚举名称交换**

49. **map.h** — 交换 `enum MapNode` 中 P7(原42) 与 P8(原49) 的名称，使名称与物理位置一致（C9→P7, C7/N14→P8）。仅交换枚举名，编译时自动修正所有 route 数组和条件判断中的引用
50. **map_message.c** — 同步更新节点表注释标签（`/*P7*/`↔`/*P8*/`）
51. **barrier.h / barrier.c** — 更新 `flag_clue_stage_B` 注释标注交换历史

**2026-06-18 — Barrier_Bridge 桥面连续修正重构**

52. **barrier.c** — 合并 BRIDGE_CORRECT + BRIDGE_ACCELERATE 为 BRIDGE_ON_BRIDGE_TOP 三级连续循环：巡线板最外侧紧急硬跳修正 ±5°(第1层) → 红外增量修正(第2层) → 居中连续计数达标后加速到 SPEED2(第3层)。改用 `Chassis_SetTargetSpeed()` 调速（不覆盖 `angle.AngleG`），去掉硬编码角度融合。75mm 最大里程保险兜底。

**2026-06-09 — 无传感器调试模式**

38. **barrier.c/h** — `Door_ReadColor()` 新增 `#if DEBUG` 分支，通过 `debug_door_color_right/left` 全局变量模拟门颜色传感器，无需硬件即可调试 door() 状态机
39. **main_task.c** — 新增独立 `MAIN_DEBUG` 宏（与 barrier 的 `DEBUG` 分开控制），`MAIN_DEBUG=1` 时走 `test_flag/debug_test_item` 测试项，不执行依赖传感器的 `Cross()` 导航
40. **barrier.c/h** — `Door_ReadColor()` 重构：返回颜色值而非通过全局变量传递；DEBUG 路径改为预设数组 `debug_door_colors[5]`；`door()` 通过局部变量 `door_color` 直接使用返回值

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

#### 1. 门检测（D2~D5）— door() 状态机
`door()` 函数在到达门节点时执行。机器人停在门前，用颜色传感器逐个读取 4 道门的灯：
- 红灯 = 门关，绿灯/黄灯 = 门开

**状态机设计**：`door()` 使用 `static enum DoorState` 变量，每次调用只读一个灯的颜色，然后返回。下一次进入 `door()` 时继续从上次的状态执行。

```c
enum DoorState {
    DOOR_D2 = 0,   // 看D2（第一次）
    DOOR_D3,        // 看D3（D2红）
    DOOR_D4,        // 看D4（D2红 D3红）
    DOOR_D5,        // 看D5（D2黄 或 D2红D3黄）
    DOOR_D4_AGAIN   // 看D4回退（D2黄 D5红）
};
```

**状态转移逻辑**：
```
D2绿 → 路线确定（DOOR_D2），调用 update_route_by_QR()
D2黄 → 还要看D5（DOOR_D5），调用 update_route_by_QR()
D2红 → 看D3（DOOR_D3）
  D3绿/黄 → 路线确定（DOOR_D2），调用 update_route_by_QR()
  D3红 → 看D4（DOOR_D4）
    D4绿/黄 → 路线确定（DOOR_D2），调用 update_route_by_QR()
D5绿 → 路线确定（DOOR_D2），调用 update_route_by_door_1()
D5红 + D2黄 → 回去看D4（DOOR_D4_AGAIN）
  D4绿 → 路线确定，调用 update_route_by_door_3()
  D4红 → 路线确定，调用 update_route_by_door_4()
D5红 + D2红D3黄 → 路线确定，调用 update_route_by_door_2()
```

根据 4 道门的开关组合，从 12 条预定义路线（`door1route`~`door12route`）中选择一条。

#### 2. 旋转平台颜色检测 — Stage()
到达平台节点（N12/N5）后，`Stage()` 读取灯颜色：
- **红灯**：退回，`flag |= 0x20`，更新 `lastNode` 和 `nextNode`，换方向
- **绿灯/黄灯**：确认 QR 码，`flag |= 0x80`，更新 `nowNode` 和 `nextNode`，规划去宝物平台的路线

#### 3. QR 码路线规划
`update_route_by_QR()` 根据线索位置（`flag_clue_stage_A`、`flag_clue_stage_B`）选择路线：
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
Stage() 读 QR 码 → flag_line_clue, flag_clue_stage_A, flag_clue_stage_B
  ↓
update_route_for_stage34() 根据 flag_line_clue 规划路线：
  0 → 跳过P3/P4，直接走门
  3 → 先去P3，再去门
  4 → 先去P4，再去门
  ↓
门检测: door() 状态机读 D2~D5 颜色 → 选 doorXroute
  ↓
update_route_by_QR() 根据 flag_clue_stage_A/B 规划去线索平台的路线
  ↓
沿路线走到线索平台（P5/P6 读 clue_A，P7/P8 读 clue_B）
  ↓
treasure = flag_clue_A + flag_clue_B → 宝物平台编号
  ↓
update_rout_by_treasure_7/8() 更新回家路线
  ↓
沿路线到达宝物平台，取宝物
  ↓
按路线返回终点
```

### 路由修改点（共 4 次）

| 修改点 | 函数 | 触发条件 | 修改内容 |
|--------|------|----------|----------|
| 1 | `update_route_for_stage34()` | Stage() 读到 QR 码后 | 根据 flag_line_clue 规划是否先去 P3/P4 |
| 2 | `door()` + `update_route_by_QR()` | 门检测完成后 | 根据门颜色选择路线，根据 QR 码选择去哪个线索平台 |
| 3 | `update_rout_by_treasure_7()` | Sword_Mountain() 中，`flag_clue_stage_B == 7` | 在 P7/P8 读完线索后更新回家路线 |
| 4 | `update_rout_by_treasure_8()` | Barrier_HighMountain() 中，`flag_clue_stage_B == 8` | 在 P7/P8 读完线索后更新回家路线 |

### 标志位说明

#### QR 码三位数格式
- **百位** → `flag_line_clue`：0=跳过P3/P4直接走门，3=先去P3，4=先去P4
- **十位** → `flag_clue_stage_A`：5=P5（原P6），6=P6（原P5）
- **个位** → `flag_clue_stage_B`：7=P7，8=P8

#### 线索与宝物
- `flag_clue_A`：P5/P6 平台读到的线索数字（OCR）
- `flag_clue_B`：P7/P8 平台读到的线索数字（OCR）
- `treasure = flag_clue_A + flag_clue_B`：宝物平台编号

#### 门检测颜色标志
- `color_flag[0]`：D2 颜色
- `color_flag[1]`：D3 颜色
- `color_flag[2]`：D4 颜色
- `color_flag[3]`：D5 颜色
- `color_flag[4]`：D1 颜色（未使用）

### P5/P6 名称交换
**问题**：物理布局中，P5 和 P6 的位置与代码中的枚举名称不一致，导致小车走到错误的平台。

**解决方案**：交换 `map.h` 中的枚举名称：
- 原 `P5`（位置16）→ 改为 `P6`
- 原 `P6`（位置27）→ 改为 `P5`

同时更新：
- `map_message.c` 中的节点表（位置17和28的数据交换）
- `map.c` 中所有路线数组（doorXroute、rout_XX）
- `barrier.c/h` 中的注释

### S 节点（直立式景点）碰撞分析
S 节点（S1-S5）是直立式景点，连接关系：
- S1 ← N3
- S2 ← N6
- S3 ← N14
- S4 ← N15
- S5 ← N16

**当前路线分析**：在获取宝藏前的路线中，小车不会经过 S 节点。路线设计已确保在完成线索平台访问前，不会误入直立式景点区域。

### 到达检测 — arrive_detect_task
独立任务，通过 FreeRTOS 通知与 main_task 同步。根据 `nodesr.nowNode.flag` 中的标志位判断到达条件：
- DLEFT/DRIGHT：左/右半边 6 灯中 5 个亮
- CLEFT/CRIGHT：左/右分岔路检测
- MUL2SING/MUL2MUL：多线→单线/多线→多线转换
- MORELED：5 个灯以上亮
- AWHITE：全白（全黑）
- RESTMPUZ：到达后执行陀螺仪 Z 轴校正
