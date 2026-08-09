# xunbao
2026-07-28 — 清理无用变量 isAllRoute（barrier.c 中 extern 但未定义），条件简化为 map.routetime!=0

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

详情与架构文档见 [project_reference.md](project_reference.md)。按日期汇总：

**2026-05-01** — PID bias int→float；底盘解耦、模式切换逻辑修正；全部源文件 GBK→UTF-8；游龙防抖修复；Turn_Angle/Stage_turn_Angle 合并为基函数；Turn360Step 重写为梯形速度曲线；IMU mutex 保护；参数显式化重构

**2026-05-02** — line_data 模式切换清零；丢线保持上次有效误差；除零保护；value_calculation 拆为 4 个 static 函数；coarse_filter 重命名与 static 化

**2026-05-26** — 灰度板 DMA 封装 + Gray_GetAngle() 坡道修正；RampCtrl_Blocking 新增灰度参数；Barrier_Hill 状态机重构

**2026-06-09** — 无传感器调试模式：Door_ReadColor DEBUG 分支 + MAIN_DEBUG 测试项

**2026-06-10** — 边缘循线限宽（最多取2灯）；后退巡线舵向反转；桥下坡红外修正

**2026-06-11** — 横滚角超限保护（roll > 40° 死停）

**2026-06-18** — update_route_by_QR 提取 load_route_at/is_green_or_yellow 简化；P7/P8 枚举名交换；桥面三层连续修正重构

**2026-06-21** — Sword_Mountain 状态机重构（SM_INIT→SM_WAIT_LINE→SM_CLIMB_UP→SM_DOWN→SM_DONE），Chassis API 化，Sword_CorrectByScanner 红线定中修正

**2026-06-24** — door() 提取 door_set_pass_node/door_retreat 辅助函数精简；QQB_1() 重写为状态机（QQB_INIT→WAIT_PITCH→GYRO→DONE）

**2026-06-27** — 变量重命名、pid_mode_switch 合并入 Chassis_SetMode、motor_task 10 函数 static 化、normalize_angle 提取、Want2Go 去重、map.c include 精简、Cross() 拆 6 子函数、nodesr.flag 阶段位拆出、CROSS_EVENT_RED/GREEN 合并为 DOOR

**2026-07-03** — Stage_P2/Barrier_WavedPlate 状态机重构；堵转保护（PWM>7000 硬上限 + output/target 比值检测）

**2026-07-04** — Turn_Angle_Base 死区补偿/钳位/TOCTOU 修复；Chassis_SelfCheck 一键自检；翘头保护（pitch > basic_p + 8° 自动降加速度，Cross_SegmentInit 中激活，与游龙同模式）

**2026-07-11** — update_route_by_door_1~4 和 update_route_at_P1 改用 load_route_at 简化；删除 copy_route()（全部替换为 load_route_at）；清理废弃的 undermou / ignore_node 函数

**2026-07-18** — IMU 初始化偶发失败修复：
  - USART3_IRQHandler 重构：HAL_UART_Receive_DMA 改为只在 IDLE 事件后重启；移除与手动 IDLE 处理冲突的 HAL_UART_IRQHandler 调用
  - 删除死代码 gyro_init / gyro UART 句柄（USART3 由 CubeMX 初始化，gyro_init 从未被调用）

**2026-07-18** — 新增 [project_handover.md](project_handover.md) 项目交接手册，涵盖快速上手、架构图解、地图系统详解、调参指南、已知陷阱等

**2026-08-06** — 重命名语义化：枚举 `UpStageP2`→`UpStageHome`、函数 `Stage_P2()`→`Stage_Home()`（P2 节点为返程上台阶回出发地；map.h / map_message.c / map.c / barrier.h / barrier.c 及 project_reference.md 同步更新）

**2026-08-06** — 删除 `mapInit1()`（与 `mapInit()` 逻辑完全重叠）；`get_newroute()` 改调 `mapInit()`，声明同步删除

**2026-08-06** — scaner.c 循迹逻辑显式化整理（两批）：
  - 第一批（纯内部，对外接口不变）：
    - 抽 `count_led_line()`：去重 Cross_getline / Line_Scan 的灯数/线数统计循环
    - `get_detail()` 复用 `ReadLineSensorDetail()`：去掉 16 行重复 GPIO 读
    - `Get_scaner_error()` 抽 `pick_best_cluster()`：去重两段奖励机制，逻辑等价
    - `Line_Scan()` 返回有效标志（原恒 0）；`value_calculation()` 补显式 TRACK_ALL case + static
    - 内联 `UpdateScanerFromRf/Gray` 透传层
  - 第二批（对外收敛 + line_data 私有化）：
    - 合并 `getline_error()`/`getline_error_ex()` 为 `Scaner_Update(void)`，RF/Gray 分发单入口；
      motor_task / turn ×2 / barrier 调用点同步更新
    - `line_data` 转 static，仅 scaner.c 内部访问；新增 `Scaner_ClearLineData()`（清零）与
      `Scaner_IsLineLost()`（丢线检测）；chassis_api 的清零/丢线检测、gray 的模式切换清零改调新接口

**2026-08-06** — 堵转保护调用点全部注释停用：`map.c` `Nav_TurnAndAdvance`、`barrier.c` 南极 `SP_IMPACT` 两处 `Chassis_DisableStallProtection()`。检测逻辑保留但 `stall_protect_enabled` 恒为 0，运行时不再触发（PWM 硬上限 + 比值累积两条防线均失效）。恢复：取消调用点注释即可。

**2026-08-07** — 红绿灯规则改版（2026新规则：黑/绿/蓝 = 不能过/能过/单相通过）。颜色常量改通行语义命名 `CAN_PASS/ONE_WAY_PASS/NO_PASS`，与具体颜色解耦（下次改色只需改 barrier.h 映射 + Door_ReadPass 传感器识别，逻辑代码不用动）；`color_flag→door_pass`、`debug_color_flag→debug_door_pass`、`Door_ReadColor→Door_ReadPass`、局部 `door_color→pass_state`。

**2026-08-07** — `PIG` 舵机宏改名 `MIKU`（Rudder_control.h 定义 + Rudder_control.c 判定 + barrier.c zhunbei 动作）；并修复红绿灯改版遗留漏改：`Door_ReadPass()` DEBUG 分支仍引用旧名 `debug_color_flag`（编译报 `#20 identifier undefined`），改为 `debug_door_pass`。

**2026-08-07** — 修复 K210.c OCR 帧处理遗留旧名：`nodesr`→`nodes`、`clue_A_stage`→`flag_clue_stage_A`、`clue_B_stage`→`flag_clue_stage_B`（编译报 `#20 undefined`，P5/P6/P7/P8 阶段门控条件语义不变）。其余 `nodesr` 引用均在注释中，无需处理。

**2026-08-07** — 修复链接错误 `L6200E: UART5_IRQHandler multiply defined`：协议处理在 K210.c，CubeMX 生成的 stm32f7xx_it.c 里同函数用 `#if 0` 禁用（函数体内有 `/* */` 注释，不能直接块注释）。注意 uart.c 不在 Keil 工程里（USART1 处理以 stm32f7xx_it.c 为准），USART3 已在 it.c 注释、由 imu.c 提供。

**2026-08-07** — 全量核对平台连接（按 map_message.c：P5↔N13、P6↔N7、P8↔N20、P7↔C9），修复四处平台编号写反：
  - barrier.c `get_newroute()` 全部 45 条 temp 路线：`N13,P6`→`N13,P5`、`N7,P5`→`N7,P6`、`C9,P8`→`C9,P7`、`N20,P7`→`N20,P8`
  - barrier.c `update_route_at_P7_for_treasure()` 2 条（1150/1169 行）：`N20,P7`→`N20,P8`（其中 `N13,P5`/`N7,P6` 原本正确）
  - map.c 未引用的门路线 door2/3_1/4/5/9/10/12route 同步修正：`C9,P8`→`C9,P7`、`N20,P7`→`N20,P8`（door1/6/7/8/11route 与 rout_57/58/67/68 原本正确）
  - barrier.c `WaitFor_OCR()` 2350 行重复条件 `P5 || P5`→`P5 || P6`（与 2411 行 P5/P6 线索A平台对一致）

**2026-08-07** — 重写第二轮路线 `get_newroute()`（barrier.c）：第二轮不再全平台扫描，改为目标平台直达后回家——
  - 宝藏=6：只去 P1→P3→P4→P6，然后直接回家
  - 宝藏≠6（2/3/4/5）：只去 P1→P3→P4→P5，然后直接回家
  - 全部 9 个门分支的 `switch(treasure)` 由原 5 case（2/3/4/5/6）统一合并为 2 case（`case 6` + `case 2/3/4/5`），删除各分支 P7/P8 绕行段，保留各分支门控有效路径段（D2/D3/D4/D5 不通时的绕行路径不变）

**2026-08-07** — IMU 零位校准 + 角度补偿三行（`IMU_CalibrateZero` + `vTaskDelay(100)` + `mpuZreset`）包装为公共函数 `IMU_Calibrate_Yaw(float referangle)`，放 turn.c/turn.h（`mpuZreset` 同族，turn.c 已含 imu.h 零新增依赖；非 imu.c 因避免 Module 层倒挂 Application 层）。参考角度由调用方传入（main_task.c 传 `nodes.nowNode.angle`），与 map 全局解耦。

**2026-08-09** — 修复 barrier.c 编译错误 `#20 DOOR_D5_BACK/DOOR_D4_BACK undefined`：`enum DoorState` 定义位于使用它的 `Door_ReadPass()`（1542 行）之后，C 语言枚举常量仅在声明后可见导致报错。将枚举前移到 `Door_ReadPass` 前置声明之前，编译验证 0 errors。
