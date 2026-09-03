# xunbao

> STM32F750V8Tx | FreeRTOS + CMSIS_V1 | Keil MDK V5.32 | 216MHz
> 入门：[交接专用文档（新人先看我）.md](交接专用文档（新人先看我）.md) ｜ 技术参考：[project_reference.md](project_reference.md)（**§二十一 = 地图修改指南**）

> **👥 给同事（按需跳转）：** §1 切场地/改开关(L11–26) ｜ §2 算法路线/单源边表(L28–34) ｜ §3 长直线阻尼(L36–41) ｜ §4 按一下跑一个节点(L43–48) ｜ §5 里程碑(L50–65) ｜ §6 重要坑(L67–72)
> **所有开关和场地参数都在 `Application/config.h`**（唯一入口，改完重新编译）。开关值一律以 config.h 为准。

---

## 1. config.h：开关集中 + 场地切换

其它文件只 `#include "config.h"`，**别重复 `#define`**（否则编译报重定义）。

**场地切换**：`USE_FIELD`（`FIELD_COMP`=比赛，`FIELD_SCHOOL`=学校）。学校是**占位=比赛值**，去学校前先填 `config.h` 里带 `TODO(学校)` 的 **14 个值**：`LEN_N22B7`、`LEN_B5N19`、`DOOR_LEN_N5N12/N5N8/N8N10/N3N10/N3N8/N8N12`、`DOOR_RETREAT_N5N8/N5N4/N10N8/N8N5`、`ANGLE_N3N8/N5N8`。

**开关**：
- `MAP_DEBUG`：1=用 `FIRST_POINT→END_POINT` 最短路径**自动生成调试路线**（不再手写 route，也不再要 `SECOND_POINT`）。`MAP_DEBUG=0` 走正常流程。
- `USE_PLANNER_ROUTE`：1=首轮/二轮路线由算法生成。
- `MAIN_DEBUG`、`STEP_DEBUG`：正式比赛必须为 0。
- `DEBUG`（1=门颜色走预设）、`SKIP_ROUND1`（调试用）。
- 几何/标定：`DOOR_LEN_*`、`DOOR_RETREAT_*`、`ANGLE_*`（门区）、`LEN_*`（楼梯）、`LEN_SCALE`(1.2f，里程标定)。

**必验**：①编译 0 error（报重定义 → 宏只在 config.h 定义）；②默认(`FIELD_COMP`+`USE_PLANNER_ROUTE=0`)行为同旧版；③学校 14 值；④`MAP_DEBUG` 一键路线能跑到终点；⑤planner 路线对；⑥赛前 `MAIN_DEBUG/STEP_DEBUG`=0。

> ⚠️ 当前 config.h：`USE_FIELD=FIELD_SCHOOL` + `USE_PLANNER_ROUTE=1`——学校数值未填（占位=比赛值），上车前先确认。

## 2. 导航规划器（最短路径）+ 单源边表

`map_message.c` 的 `NavEdgeTbl[]` 是**唯一人工编辑源**；`mapInit()→nav_graph_init()` 自动建执行层 `Node[]/ConnectionNum/Address`。`USE_PLANNER_ROUTE=1` 时首轮/二轮路线由规划器生成 `route[]`；执行层 `Navigation()/getNextConnectNode()` 未动。
- 权重：`cost = 1.0×step + 0.6×|Δangle| + 1.0×obs_penalty`；`NavObsPenalty[]`/`NAV_W_TURN` 在 `nav_planner.c/h`。
- **改哪里**：改图 → `map_message.c` 边表 + `map_message.h` `NAV_EDGE_COUNT` + `map.h` 枚举；路线选错 → 调 `NavObsPenalty`/`NAV_W_TURN`。
- **必验**：编译；`USE_PLANNER_ROUTE` 下首轮/二轮路线是否对。
- **PC 校验**：`_weight_calib.py`（改边/权重后必跑）、`_check_csr.py`（增删边后必跑）。详见 `project_reference.md §4.5`。

## 3. 长直线陀螺仪阻尼补偿（抑制摆车）

在"直穿"直线段用陀螺仪 `yaw_rate` 阻尼，抑制加减速/过路口摆车；只在 `Go_Line` 差速叠加小项，不改循迹方式。
- 参数在 **`chassis_api.h`**（不在 config.h）：`LINE_GYRO_COMP_KD`(0.08)、`MAX`(8.0)、`YAW_FILTER`(0.5)；判定阈值 `STRAIGHT_ANGLE_THRESH=5.0f` 在 `map.c`。
- **必验**：跑直线手轻推车头，能**平滑回正**=符号对；越摆越大=反（`Chassis_GetLineGyroComp` 里 `-kd` 改 `+kd`）。确认覆盖 N3→N4/N4→N5/N5→N6，且爬坡/转弯(如 N6→P4)不误启。
- **禁用**：删 `Chassis_EnableLineGyroComp(...)` 调用，或 `LINE_GYRO_COMP_KD=0`。

## 4. 按一下跑一个节点（STEP_DEBUG 步进调试）

`STEP_DEBUG=1` 时按键计票，`Navigation()` 每跑一条边扣 1 票，扣到 0 停车等票；`0`=原行为（当前就是 0）。
- 开关在 config.h：`STEP_DEBUG`、`NAV_TOKEN_WINDOW_MS`(2000)；要跑起来还须 `MAIN_DEBUG=0`。
- **必验**：按一下跑一条边停；连按 N 次→2s 窗口并成 N 票连跑。
- **待做（未实现）**：①保护随票开关；②被打断→本段归零可继续。目前丢线/翻滚是 `while(1)` 死停，**`STEP_DEBUG=1` 测试时别抱车**。

## 5. 关键里程碑

- 2026-05：PID bias int→float；底盘解耦 Chassis API；全工程 UTF-8
- 2026-06-27：motor_task 内部函数 static 化；Navigation 拆子函数；normalize_angle
- 2026-07-03~04：障碍状态机重构；Turn_Angle_Base 修复；堵转保护（08-06 停用）
- 2026-07-18：IMU 偶发初始化失败修复
- 2026-08-06：scaner 循迹显式化（Scaner_Update 单入口、line_data static）
- 2026-08-07：红绿灯通行语义 CAN_PASS/ONE_WAY_PASS/NO_PASS；平台编号修正
- 2026-08-09：巡线 PID 按实际速度阶梯选择
- 2026-08-10：IMU 上电自检 + IMU_Reinit
- 2026-08-12：寻中线连续亮灯段+最中心2灯；FPU 单精度化
- 2026-08-13：二轮巡游后回家；SKIP_ROUND1；DWT 解锁；LEN_SCALE=1.2；门区段长度宏
- 2026-08-14：平台/南极结束保留 nodes.nowNode.function
- 2026-08-15：door() D4/D2→D3 判定修复；BY8001 音量
- 2026-08-16：门区段角度宏；二轮进东区按宝藏位优化
- 2026-08-21：波动板拆节点 B10/B11（进 BLBL 出 NONE，正反向共用，恢复路口检测）

## 6. 重要坑

- CubeMX 重新生成后：注释 `main.c` 定时器中断回调 + `stm32f7xx_it.c` 的 `USART3_IRQHandler`（USART3 由 imu.c 提供）
- 别把负值写进 PWM CCR；反向换 TIM 通道极性并取反编码器
- motor_task 5ms 循环避免阻塞和 printf；源码统一 UTF-8；Keil 必须 V5.32
- 改代码后同步更新 `project_reference.md` 和交接文档
