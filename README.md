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
