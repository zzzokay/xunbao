# xunbao — 修改日志

> **📌 读者对象**：**主要给 AI / 工具看**（配合 project_reference.md 一起喂给空白上下文的 AI，这里是"改了什么"的日志）。
> **当前项目现状、目录结构、config 开关、改地图方法、AI 工作流** 见 **[project_reference.md](project_reference.md)**。
> 本文件只按日期记录「改了什么」，供追溯。

---

## 修改日志

- **2026-05**：PID bias int→float；底盘解耦 Chassis API；全工程 UTF-8
- **2026-06-27**：motor_task 内部函数 static 化；Navigation 拆子函数；normalize_angle
- **2026-07-03~04**：障碍状态机重构；Turn_Angle_Base 修复；堵转保护（08-06 停用）
- **2026-07-18**：IMU 偶发初始化失败修复
- **2026-08-06**：scaner 循迹显式化（Scaner_Update 单入口、line_data static）
- **2026-08-07**：红绿灯通行语义 CAN_PASS/ONE_WAY_PASS/NO_PASS；平台编号修正
- **2026-08-09**：巡线 PID 按实际速度阶梯选择
- **2026-08-10**：IMU 上电自检 + IMU_Reinit
- **2026-08-12**：寻中线连续亮灯段+最中心2灯；FPU 单精度化
- **2026-08-13**：二轮巡游后回家；SKIP_ROUND1；DWT 解锁；LEN_SCALE=1.2；门区段长度宏
- **2026-08-14**：平台/南极结束保留 nodes.nowNode.function
- **2026-08-15**：door() D4/D2→D3 判定修复；BY8001 音量
- **2026-08-16**：门区段角度宏；二轮进东区按宝藏位优化
- **2026-08-21**：波动板拆节点 B10/B11（进 BLBL 出 NONE，正反向共用，恢复路口检测）
- **2026-09-06**：三层架构重构——`Mission/Navigation/Application` 分层；`barrier.c` 的路线决策（QR/门/宝物改路、`get_newroute`、`Clear_door`）拆到 `Mission/mission_planner.c`；导航规划 + 单源边表收敛到 `Navigation/nav_planner.c` + `Navigation/map_message.c`。此前的 `REFACTORING_SUMMARY / ARCHITECTURE_OPTIMIZATION / REFACTORING_COMPLETE` 三份记录已删除，内容并入 project_reference.md 与本文档。

- **2026-09-06 晚**：结构优化四改——(1) `door_retreat()`/`door_set_pass_node()` 改为返回 `NODE`，副作用显式化；(2) `map_message.c` 增加 `_Static_assert` 检查 `NAV_EDGE_COUNT` 与 `NavEdgeTbl[]` 长度一致；(3) 删除 135 个纯死代码声明（`Clue*route`/`Clue*P4route`/`TempRoute`）+ 7 个未引用 `door*route` 定义；(4) 三份校验脚本路径修正（`Application/` → `Navigation/`）+ 增加 exit code + 创建 `.git/hooks/pre-commit` 自动触发。
> 逐日修复历史已从本文件精简；需要更早/更细的改动可查 `git log`。
