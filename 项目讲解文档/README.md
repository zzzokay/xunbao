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

- **2026-09-08**：**修复一轮门回程 180° 掉头**。根因：2026-09-06 重构把一轮门回程改成了**规划器**生成，`plan_after_return_door()` 在 D3 绿(D2 不绿)时给 `wp` 追加 `[N8,N5]`，而 `wp[0]=nodes.nowNode` 已是退回到的 `N5`，拼成 `N5→N8→N5`，`need2turn(-145°,35°)=180°` 就地反转；D4 绿同理会 `N3→N8→N5` 穿门掉头。**修复**：恢复重构前的"手写穷举"方案——`update_route_by_door_1/2/3/4` 一律用手写路线数组（去掉 `plan_after_return_door` 规划器分支并移除该函数），从当前(内侧)节点直接写回家/目标路线，不再穿门掉头。**二轮 `get_newroute` 未动**（门已被 `Clear_door` 清为 NONE，无门干扰；规划器只做"出门点→平台"，已实测不穿门）。已验证：手写路线与重构提交 `b45aa45` 逐字一致、无 `N8` 掉头；`_weight_calib/_check_csr/_check_wp/_check_door_logic` 全部通过。

> 逐日修复历史已从本文件精简；需要更早/更细的改动可查 `git log`。

- **2026-09-11**：**建图统一 + 目录约定 + 死代码清理**。
  (1) `nav_init()` 统一构建执行层（`Node[]/ConnectionNum[]/Address[]`，定义移到 `nav_planner.c`、extern 声明在 `map.h`）+ 规划层线路图，删除 `map_message.c` 的 `nav_graph_init()`；`nav_planner.h` 不再包含 `map.h`（打断 `map.h→map_message.h→nav_planner.h` 循环包含），`Node[]` 改用不完整数组类型声明消除尺寸冲突。
  (2) 门回程路线数组从 `map.c` 移到 `mission_planner.c` 并与业务同处；`door6/8/11route` 合并为 `door_return_via_N4`；`door1route` 由 `barrier.c` extern 引用；删除已无数据源的 `rout_57/58/67/68`（其 `USE_PLANNER_ROUTE=0` 兜底分支改为条件编译）。**注意：切回 `USE_PLANNER_ROUTE=0` 前需先恢复这些数组**。
  (3) **include 全工程统一为短写** `#include "xxx.h"`（原 25 处 `../Dir/xxx.h` 仅 `Navigation/map.c` 3 处会编不过：Keil 的 `-I` 只到目录本身）；为消除裸名歧义删除 `USMAT/sys.h`、`Module/adc.{c,h}`（后者不在构建列表、无任何引用）。
  (4) **死代码清理**（全部有 armcc 未引用警告佐证）：`nav_edge_base_cost`、`timing_dwt_init`×2、`handle_led_mouse`、`openmv.c` 的 `retry`×2、`barrier.c` 的 `state2_retry/now_angle/sub_stage`×3/`approach_timeout`、`chassis_api.c` 不可达 `return`、`map.h` 残留的 `TempRoute[50]` 与 `ErrorTimes[2]` 两条只有声明无定义零引用的 extern；`USE_PLANNER_ROUTE=0` 的两处兜底分支改为条件编译。armcc 全量编译 49 个 TU：**0 error，警告 45→31**（余下均为改动前既有）。
