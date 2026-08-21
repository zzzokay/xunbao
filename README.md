# xunbao

> STM32F750V8Tx | FreeRTOS + CMSIS_V1 | Keil MDK V5.32 | 216MHz
> 入门交接：[交接专用文档（新人先看我）.md](交接专用文档（新人先看我）.md)
> 技术参考：[project_reference.md](project_reference.md)

## 当前状态（2026-08-21，工作区未提交）

- 波动板拆节点：新增 **B10**（N14–C7，板尾 C7 侧）、**B11**（C8–C4，板尾 C4 侧）；进板边 `BLBL`、出板边 `NONE`，C7/C4 恢复视觉检测+路口播报（不再越过 C7/C4 提前转弯）
  - 受影响边：`N14→B10`（原 N14→C7）、`B10→C7`、`C8→B11`（原 C8→C4）、`B11→C4`；反向 `C7→N14`、`C4→C8` 仍直连 BLBL
  - 涉及文件：`map.h`（枚举+Node[128]）、`map_message.c/h`（连接表+索引数组扩容）、`map.c`（rout_58/67/68、注释调试路线）、`barrier.c`（tour_p6）
  - 待现场实测：`B10→C7` step=40、`B11→C4` step=20、`N14→B10` step=100、`C8→B11` step=30
- 门区段角度：`ANGLE_N3N8=145`、`ANGLE_N5N8=35`
- 门区段长度：`DOOR_LEN_N5N12/N3N10=200`，`DOOR_LEN_N5N8/N8N10/N3N8/N8N12=190`
- 回退距离：`DOOR_RETREAT_N5N8/N5N4=67`、`N10N8=80`、`N8N5=65`
- `map.h`：`MAP_DEBUG=1`、`SKIP_ROUND1=0`、`FIRST_POINT=N22`、`SECOND_POINT=B6`；`main_task.c` 预设 `door_pass={NO_PASS,CAN_PASS,CAN_PASS,NO_PASS,NO_PASS}`（D2/D3/D4/D5/D1）、`treasure=6`
- `Stage_Correct()` 重命名，平台纠偏超时放宽；`door()` 删一处多余 stop-turn
- `map_message.c` 微调：N5→N6 `150/SPEED2`、P4 下平台 `SPEED1`、N12→N13 `80`、N9→N10 `180`
- 未提交改动：`barrier.c`、`map.h`、`map_message.c/h`、`map.c`、`main_task.c`

## 关键里程碑

- 2026-05-01：PID bias int→float；底盘解耦 Chassis API；全工程 UTF-8
- 2026-06-27：motor_task 内部函数 static 化；Navigation 拆子函数；normalize_angle 提取
- 2026-07-03~04：障碍状态机重构；Turn_Angle_Base 死区/钳位修复；堵转保护（08-06 停用）
- 2026-07-18：IMU 偶发初始化失败修复（USART3_IRQHandler 冲突 + 删死代码）
- 2026-08-06：scaner 循迹显式化（Scaner_Update 单入口、line_data static）；堵转保护调用点停用
- 2026-08-07：红绿灯通行语义 `CAN_PASS/ONE_WAY_PASS/NO_PASS`；平台编号修正；第二轮按宝藏直达
- 2026-08-09：巡线 PID 按实际速度阶梯选择（line_pid_steps[]）
- 2026-08-10：IMU 上电自检 + `IMU_Reinit` + ORE 清理
- 2026-08-12：寻中线连续亮灯段+最中心2灯；FPU 单精度化；高山提前切陀螺仪
- 2026-08-13：二轮巡游所有平台后回家；SKIP_ROUND1；DWT 解锁；LEN_SCALE=1.2 长度标定；门区段长度宏
- 2026-08-14：平台/南极保留 `nodes.nowNode.function`，修复下平台后误转弯
- 2026-08-15：door() D4/D2→D3 判定修复；BY8001 音量控制
- 2026-08-16：门区段角度宏；二轮进东区/回程按宝藏位优化；跷跷板退车优先级
- 2026-08-17：门角度/长度调参、SKIP_ROUND1=1、map_message 微调（未提交）
- 2026-08-21：波动板拆节点 B10/B11，进板 BLBL 出板 NONE，C7/C4 恢复路口检测+播报（修复未到 C7 提前转弯）

## 重要坑

- CubeMX 重新生成后：注释 `main.c` 定时器中断回调 + `stm32f7xx_it.c` 的 `USART3_IRQHandler`（USART3 由 imu.c 提供）
- 别把负值写进 PWM CCR；反向换 TIM 通道极性并取反编码器
- motor_task 5ms 循环避免阻塞和 printf；调试别用低波特率蓝牙
- 源码统一 UTF-8；Keil 必须 V5.32
- 改代码后同步更新 `project_reference.md` 和交接文档