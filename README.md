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

**2026-08-09** — 巡线PID按当前实际速度阶梯选择（防高速→低速减速期摇摆/不跟线）：`Chassis_SetTargetSpeed` 不再写 `line_pid_param`；新增阶梯表 `line_pid_steps`（速度→Kp/Kd，与各速度档一致），motor_task 每5ms 调 `Chassis_UpdateLinePidBySpeed()` 读取当前实际速度 `motor_all.encoder_avg`，规则为**只有当前速度 ≤ 某档速度才采样该档PID（尽量向上取高速档低Kp）**。减速时 PID 随实际速度逐级下调：减速前期保持高速低Kp，速度真正降到档位以下才换更高Kp。游龙 `Chassis_OverrideLinePid` 临时覆盖生效时优先级更高（不覆盖）。编译验证 0 errors。

**2026-08-11** — 寻中线(TRACK_NEAR_CENTER/calc_near_center)：中心两灯(第7、8灯)任一亮即进入中心判定，且**只取最中心两灯**（与 calc_left/right_edge 一致最多取2灯，不再向左右扩出整个连续亮灯段），其余线一律忽略；误差按这两灯实际亮灯位置**成比例计算**（不强制为0：如 5/6/7 三灯亮会得到偏左的误差并修正，不会静止不动）。中心灯全灭时保持原"离中心最近段"兜底。演进过程：强制 error=0+TRUTH_VALID（偏心线不修正）→ 扩出整段（被旁线拖偏）→ 只取最中心两灯（均撤回前两种）。**随后回退核心改动（仅 scaner.c + chassis_api.h 改回提交版）**：`calc_near_center` 恢复"中心两灯同时亮才判中心、误差强制0、其余取离中心最近段兜底"，`line_weight_default` 权重还原，`TRACK_NEAR_CENTER` 注释还原。调试配套未动：main_task.c 循迹测试、map 调试路线、chassis_api.c PID 调参、barrier.c 坡道时序仍保留未提交。

**2026-08-10** — IMU 上电自检 + 串口恢复（应对偶发上电读不到陀螺仪数据、角度恒为0）：imu.c 新增 `IMU_IsDataActive()`（互斥锁读 `imu_shared_data`，3角任一非0即有数据）/ `IMU_WaitData(ms)`（每50ms采样，1s窗口内全程为0才判失败）/ `IMU_Reinit()`（关USART3中断→停DMA→清 ORE/NE/FE/PE/IDLE 错误标志→清零缓冲→重新 `HAL_UART_Receive_DMA`+开IDLE→开中断前再清一次ORE堵死残余竞态）；`Start_task` 在 `user_init()` 后自检：1s 读不到数据则打印失败、`IMU_Reinit()`、等2s再试一次，仍无数据打印警告后继续上电流程（不阻塞任务创建）；`USART3_IRQHandler` 开头加 `__HAL_UART_CLEAR_OREFLAG`——HAL_UART_IRQHandler 仅在错误标志≠0时才中止DMA，先清 ORE 使错误中断进来时不会杀死刚重挂的 DMA（根因：HAL 对 ORE 是"中止+交用户恢复"策略，与自定义 ISR"先重挂再调 HAL"叠加成死锁）。temporary_task.c 补 `#include "stdio.h"`。

**2026-08-12** — 寻中线(TRACK_NEAR_CENTER/calc_near_center)：**恢复"连续亮灯段"约束**（不再允许跨空隙取两灯），在选中的段内**只取离中心最近的 2 个灯**算位置/误差（取消整段平均，粗线不再拖偏；原 `MAX_LED>4` 段长否决随之失效，段内取 2 灯恒 ≤2）；中心两灯(7,8)同时亮仍走 center 快路径（error=0）。

**2026-08-12** — 寻中线(TRACK_NEAR_CENTER/calc_near_center)：**亮灯总数 ≥ 4 时保守认为线在中心**（error=0 直行），应对旁线/路口干扰、不被旁边线拖偏；原有中心两灯(7,8)快路径、连续亮灯段内取最靠中心 2 灯逻辑保持不变。

**2026-08-12** — 任务周期耗时测量（调试用，测完可删）：motor_task.c / main_task.c 各加 `timing_dwt_init()`（DWT 周期计数器 @216MHz 初始化，TRCENA+CYCCNTENA）与循环内测量块——motor_task 每 100ms 打印 `MOTOR cpu=xxus period=xxms`（本循环 CPU 耗时 + 实测周期，应≈5）；main_task 每 500ms 打印 `MAIN loop=xxus max=xxus`（单周期耗时含阻塞 + 历史最大值）。用于排查主任务是否饿死底层。当前优先级：motor_task=6 > main_task=5（configMAX_PRIORITIES=7），主任务已无法抢占饿死电机任务。

**2026-08-12** — FPU 浮点修复：消除用户代码里的软件 double 运算，全部走单精度硬件 FPU（Cortex-M7 仅单精度 FPU）：
- imu.c `USART3_IRQHandler`：`180.0`/`32768.0` → `180.0f`/`32768.0f`（IMU 中断每帧 3 次软件 double 乘除 + 4 次类型转换）
- turn.c / barrier.c / scaner.c 共 11 处 `fabs()`（double 版）→ `fabsf()`（参数全为 float，原会被提升为 double）
- turn.c:263 活着的 `printf("%.2f, %.2f\n", ...)` 注释掉（转弯循环里每 100ms 打印，把 float 提升 double 并拖进浮点格式化库 printfa/_fp_digits）
- pid.c `speed_pid_kp/kd/ki`：`param / 10.0` / `/ 100.0` → `/ 10.0f` / `/ 100.0f`（int/double → 软件 double 除法）
- Rec_usart.c `get_PIDdata()`：`atof()` → `strtof(value, NULL)`（atof 返回 double，拖进 `__strtod_int`/`_scanf_real` 556 字节；strtof 直接返回 float）
- sin_generate.c `sin()` → `sinf()`（该函数当前无调用、链接器已 GC，属保险性修改）
- 验证：修复前 map 文件最终 image 含 `__aeabi_dmul/ddiv/dadd/dsub/f2d/d2f/i2d`；修复后应全部消失（重编译后复查 map）。
**2026-08-12** — Barrier_HighMountain `HM_APPROACH` 提前切陀螺仪：坡底 `imu.pitch >= Begin_up`（basic_p+5，与 RampCtrl "刚上坡"定义一致）且里程≥15 即切 `HM_ASCEND_1`，不再等 `Stage_DetectedRamp` 的 10° 俯仰/循迹干扰条件。根因：`Stage_DetectedRamp` 俯仰阈值 `imu.pitch >= 10.0f` 约为 RampCtrl `Begin_up`(basic_p+5) 的两倍，车在 0°→10° 爬坡期间仍处于巡线模式，坡面无循迹线+干扰灯（幻影线）导致巡线跑偏；mile≥15 门限排除起步加速翘头误触发。切过去后 `RampCtrl_Blocking` 首个 RAMP_INIT 状态立即满足 `pitch >= Begin_up`，行为不变。仅作用于 HighMountain，其他平台沿用原 10° 阈值。

**2026-08-12** — 修复 barrier.c 两处"参数未还原/未清零"遗留：
- Barrier_Hill 楼梯 `Chassis_OverrideGyroPid(7,0,60,50)` 的唯一 `Chassis_RestoreGyroPid()` 在不可达的 `default:` 分支（HILL_DESCEND 直接置 HILL_DONE 退出循环，default 从不执行）→ 移到 while 循环结束后、与 `nodes.nowNode.function=0` 同处：楼梯完成后陀螺仪 PID 一定还原，不再污染后续陀螺仪模式行驶/转弯
- Barrier_Bridge 长桥 `is_emergency` 计数上限 `<=10` 把计数卡死在 ~11（`==300` 死代码、`==10` 每个连续检测只触发一次）→ 改 `< 300`：连续偏出时第 10 次(≈50ms)与第 300 次(≈1.5s)各做一次 5° 硬修正

**2026-08-13** — 第二轮路线改为「走所有平台后回家」：`get_newroute()`（barrier.c）不再按 treasure 只去目标平台，改为一次巡游所有平台——公共段 P1→P3→P4 后进东区 P5→P7→P8→P6，再按门状态回家 P2。原 18 条路线（9 门分支×2 宝藏）→ 9 条（每分支 1 条），删除 `switch(treasure)`；新增 `build_round2_route()` 拼接 公共段+东区巡游段+分支进出段。9 条已按 map_message.c 连接表逐边校验，覆盖 P1~P8，51~55 节点。

**2026-08-13** — 新增 `SKIP_ROUND1` 调试开关（map.h，默认 0）：跳过第一轮直接进第二轮。main_task.c 正常模式初始化处 `#if SKIP_ROUND1`：预设 `door_pass[5]`（默认 D2=CAN_PASS 双向，索引 0:D2/1:D3/2:D4/3:D5/4:D1，改门状态只需改这里）、`treasure`（预设宝物平台编号=5，二轮依赖一轮采集的宝物，treasure 非 0 才能跳过 P1 残留 QR 扫描 → `update_route_at_P1()` 改路）、并置 `map.routetime=1`，首个主循环周期走真实"二轮处理"分支；同时 `#elif` 跳过初始化处 zhunbei 避免双启动。**二轮分支修正**（关键）：`mapInit() → get_newroute() → map.routetime=2 → zhunbei()`，`routetime=2` 必须在 `get_newroute()` 之后置（get_newroute 内部 mapInit 把 routetime 清回 0）——二轮全程 `routetime==2` 使 barrier.c 的 P7/P8 treasure 改路（`update_route_at_P7/8_for_treasure`，`map.routetime==0` 门槛）不再触发，完整巡游不走样；且二轮跑完 `Nav_TurnAndAdvance` 使 routetime→3 即停，不再无限重启二轮。`SKIP_ROUND1=0` 时该块 `#if 0` 跳过，正常一轮→二轮路径与原代码逐字节一致，无影响。二轮门控路径安全：`get_newroute()` 内 `door_set_pass_node()` 把 8 条通行边（N5↔N12/N5↔N8/N3↔N8/N3↔N10）置 `function=NONE`，二轮过门不再重触发 `door()`，预设 door_pass 保持。

**2026-08-13** — 二轮东区巡游顺序按宝藏位优化（barrier.c `get_newroute()`）：新增 `tour_p6_first[]` 与 `use_tour = (treasure==6) ? tour_p6_first : tour`——宝藏=P6 时进东区后**先深入去 P6**，再 `P8→P7→P5` 绕回（终点仍 N10，9 个门分支 tail 不变）。`tour_p6_first` 逐边校验：`N12→N16→N18→B5→N19→C6→B7→N22→C9→N22→B6→N20→C4→C8→C7→N14→C3→N9→B9→N7→P6→N7→B8→N9→C3→N14→C7→C8→C4→N20→P8→N20→B6→N22→C9→P7→C9→N22→B7→C6→N19→N13→P5→N13→N12→N11→N10`，回程经 `N19→N13`（N18 连接表无 N13，不能走 N18→N13）。非 P6 宝藏仍用原 tour。

**2026-08-13** — 修复 DWT 周期耗时测量 `cpu=0us`：Cortex-M7（STM32F750）的 DWT 寄存器对**软件写**默认锁定，`timing_dwt_init()` 里 `DWT->CYCCNT=0` / `DWT->CTRL|=CYCCNTENA` 在缺解锁时被静默忽略，计数器恒为 0（调试器 DAP 始终可写，所以接仿真器时正常、脱机上电就恒 0）。motor_task.c / main_task.c 两处 `timing_dwt_init()` 在 TRCENA 之后统一补 `DWT->LAR = 0xC5ACCE55` 解锁。验证：烧录后 `MOTOR cpu=` 应输出非零 µs 值。

**2026-08-13** — 长度标定 `LEN_SCALE = 1.2f`：此前所有长度值（里程/地图 step/距离阈值）都是未标定的"代码单位"。用户实测 100 代码单位 ≈ 120cm，故 1 代码单位 = 1.2cm。**全部 250 处距离阈值已按 cm=round(代码单位×1.2) 直接折算为整数厘米内联**（精确到 1cm），不再保留 ×LEN_SCALE 表达式：
- [chassis_api.h](Application/chassis_api.h) 定义 `#define LEN_SCALE 1.2f`（附标定说明注释），宏现在**仅**用于里程公式比例补偿
- motor_task.c:182 里程公式 `Distance += (encoder_avg*10.4*PI/5720)/0.362 * LEN_SCALE`（运行时连续累加，只能在此乘 LEN_SCALE）
- 折算内联分布：map_message.c Node[126] 表 step 121 处（如 `280→336`、`180→216`）；barrier.c 90 处（`Chassis_DriveDistance_Blocking` 距离、`Chassis_GetMileage`/`mileage_br` 比较、`Stage_DetectedRamp` 距离、`nodes.nowNode.step=`、`door_set_pass_node`/`door_retreat` 距离、`RampCtrl_Blocking` max_distance、QQB `dis`）；map.c 32 处（`Barrier_WavedPlate(50/100→60/120)`、两个 `GetForwardDistance*` return）；main_task.c 7 处（`Chassis_DriveDistance_Blocking` 距离）
- 已脚本全工程校验零遗漏零误伤：非长度参数（`RampCtrl` 的 thresh/speed/angle 如 `15`/`20.0f`/`0.08`、`Stage_DetectedRamp` 俯仰阈值 10°、`return 0;`）不折
- 重新标定：改 chassis_api.h 的 LEN_SCALE + 重算内联值（cm = round(代码单位 × 新倍率)），代码单位原值见 git 历史

**2026-08-13** — 红绿灯门区段长度宏定义化（map_message.h 新增 `DOOR_LEN_*` / `DOOR_RETREAT_*`，一处修改全局同步；barrier.c 经 map.h→map_message.h 可见，map_message.c 无需额外 include）：
- 6 条门区段全长宏 `DOOR_LEN_N5N12/N5N8/N8N10/N3N10/N3N8/N8N12`（值：168/168/168/168/168/132）：barrier.c `door_set_pass_node` 全部 23 处改用全长宏；map_message.c 中 DOOR 条目改用 `宏/2`（半长=停车读灯位置），匹配的非 DOOR 条目用全长宏
- `door_retreat` 5 处回退距离改独立宏 `DOOR_RETREAT_N5N8(60)/N5N4(60)/N10N8(84)/N8N5(36)`（回退距离与路段全长无关）
- 取值以 map 半长×2 为准：N5N8/N3N8 全长统一为 168（barrier 原 144 共 11 处改 168）；map 中不匹配值强制为 `宏/2`：N8→N3 `72→84`、N8→N5 `180→84`；`get_newroute()` 预置 N5N12 `156→168`（如需保留 156 需拆独立宏）

**2026-08-13** — 修复 `Stage_correct()` 位运算优先级 bug（"平台段车不停下来"根因）：C 中 `==`/`!=` 优先级高于 `&`，故 `detail & 0xFFFF == 0xFFFF` 实为 `detail & (0xFFFF==0xFFFF)` = `detail & 1`，`detail & 0xFFFF != 0xFFFF` 实为 `detail & (0xFFFF!=0xFFFF)` = `detail & 0`（**恒假**）→ state 1 永不退出、`CarBrake()` 永不执行，车一直直线开。三处条件（state0/1 全16位判定 + case2 中心 0x0180/0x0100/0x0080 判定）全部补括号修复。另给 case2 加"停车 500ms 后无线形"重试兜底（新增 `state2_retry`，重扫 5 次仍无线则退出 state3），避免探头停偏后 `Stage_correct` 卡死循环
