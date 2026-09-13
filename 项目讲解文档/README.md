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

- **2026-09-11 晚**：**零风险合并 / 去重 / 清死代码（不改任何路线与门逻辑行为）**。
  (1) **`update_route_by_door_1` 与 `update_route_by_door_3` 合并**：两者被调用前 `nodes.nowNode` 都已退到 N3（分别来自 D5 绿、D4 回程绿），手写路线逐字相同 → 抽出 `static void route_return_from_N3()`；对外两个入口名保留，`barrier.c` 调用点不变。
  (2) 门回程重复字面量去重：`{N4,B2,N1,P1,N1,B1,N2,P2}` 原在 `door_1`/`door_4` 各写一份 → 抽为 `static const u8 ret_via_P1[]`。
  (3) 删 `map.c:GetForwardDistanceBeforeTurn()` 的不可达死分支：`(last=N3,now=N4,next=B2)` 在原 183/192 行各出现一次（`->30` 在前、`->24` 在后），后者恒被遮蔽。⚠️ 保留生效值 **30**，但 24/30 哪个是期望值未定，动这条等于改 N4→B2 的转弯前补偿，**改前须实车确认**。
  (4) `update_route_at_door_for_stageAB()` 4 处 `sizeof(wp)` → `sizeof(wp)/sizeof(wp[0])`（原写法只在元素恰为 `u8` 时凑巧正确，换类型即错）。
  (5) 删死代码：`nav_planner` 的 `nav_stitch()`（全工程零调用，拼接逻辑已内联在 `nav_plan_waypoints()`）、`map.h` 的悬空声明 `Change_Route`/`Turn_Flag`/`mul2sing`/`sing2mul`/`select_speed()`（均无定义、无引用；`mul2sing/sing2mul` 还与 `ArriveDetect_task.c` 的 static 定义同名冲突）、`Mission/barrier.c.backup`（59KB 陈旧副本，不在 Keil 工程内）。
  (6) 文档同步：`project_reference.md` 去掉已删的 `nav_stitch`、门回程条目补注 `_1/_3` 同源；`scripts/README.md` 更正"`pre-commit` 自动触发"——**该钩子实际已被停用**（现存为 `.git/hooks/pre-commit.disabled`），恢复需手动改名。
  验证：`_weight_calib`(15/15) / `_check_csr` / `_check_wp` / `_check_door_logic` 全过；`Mission/mission_planner.c`、`Navigation/nav_planner.c` 经 `arm-none-eabi-gcc -Wall -Wextra -fsyntax-only` **0 error 0 warning**（`map.c`/`map_message.c` 因 Keil RVDS 端口的 `__asm{}` 块无法用 GCC 做语法检查，改为人工逐行核对）。
  > **另**：本轮还实测确认了"门回程 12 条手写穷举路线 = 规划器在'门边禁用'下的最短路"（12/12 逐字复现），改造方案与证据见 `.claude/plans/door-permission-planner.md`。

- **2026-09-11 晚（续）**：**删两处废值**（用户确认）。
  (1) `Mission/barrier.h` 的 `void select_speed_stage(void);` —— 只有声明、全工程无定义无调用，属残留（同 `map.h` 已删的 `select_speed`）。
  (2) `Navigation/map_message.c` 的 `{ N13, C2, NONE, NONE, NONE, NONE, NONE }` —— 退化桩：`flag=NONE(1)`、`angle=1.0`、`step=1`、`speed=1.0`，即"N13→C2 只要 1cm、无转弯"的假边，是给规划器埋的雷（一旦被 Dijkstra 选中会算出荒谬路线）。已删除，`NAV_EDGE_COUNT` 125→**124**。C2 仍可经 `C1→C2` 进入、`C2→C1`/`C2→N13` 离开，无路线依赖该反向边。
  验证：4 个校验脚本全过（`_weight_calib` 15/15）；`Navigation/map_message.c` 经 `arm-none-eabi-gcc -Wall -Wextra -fsyntax-only` 0 error 0 warning，表内行数实测 124（与 `NAV_EDGE_COUNT` 的编译期 size check 一致）。

- **2026-09-11 晚（阶段 B1）**：**给规划器加"运行时边禁用" + 门回程 golden 校验脚本（不接线，固件行为零变化）**。
  (1) `Navigation/nav_planner.c/h` 新增 `nav_clear_blocked()` / `nav_set_edge_blocked(from,to,blocked)`：`static uint8_t s_blocked[NAV_MAX_EDGES]` 按边号标记，`nav_shortest_path()` 的"起点边初始化"与"松弛"两处 `continue` 跳过被禁边；只影响规划层，不动执行层 `Node[]` 与 `Navigation()`。`nav_init()` 里复位（默认全开）。原先零调用的 `nav_find_edge()` 正好用于按 `from->to` 定位边号。
  (2) 新增 `scripts/validate/_check_door_perm.py`：把改造前 `update_route_by_door_1~4` 的 **12 条手写穷举路线当 golden**，断言"门区 8 条边全禁 +（door_2 额外放行 `N8→N3`）+ `wp={当前节点,[宝物平台],P2}`"能逐字复现，另含 golden 连通性自检。**golden 已与改造前 git 快照 `d44f954:Mission/mission_planner.c` 机械比对（16 条数组逐字一致，含 door_1≡door_3）**。实测 12/12 通过。
  (3) `scripts/README.md` 收录新脚本（现共 5 个 validate 脚本）；`project_reference.md` 补 `nav_set_edge_blocked` 到函数表。
  验证：`_check_door_perm` 12/12 + golden 88 段全连通；原 4 个脚本全过；`nav_planner.c` 经 `arm-none-eabi-gcc -Wall -Wextra -fsyntax-only` 0 error 0 warning。

- **2026-09-11 晚（阶段 B2）**：**门回程改用"规划层门区禁用 + 极简必经点"，删掉 12 条手写穷举路线**。
  (1) `Mission/mission_planner.c`：新增 `door_zone[8][2]`（门区 4 对 × 2 方向，与 `Clear_door()` 同一组边）、`door_block_all()`、`route_return_home(allow_N8_N3)`。回程先用 `nav_set_edge_blocked()` 把门区 8 条边**全部禁用**（回程不再进门区 → 结构上不可能穿门掉头），再用 `wp={当前节点,[宝物平台],P2}` 交给最短路；唯一例外 `door_2` 额外放行 `N8→N3`（D5 黑 + D3 蓝已用尽，必须退回 N3 重读 D4）。`update_route_by_door_1~4` 变成 4 个一行包装（分别传 0/1/0/0）。
  (2) **删除**：3 个全局数组 `door7route`/`door_return_via_N4`、`ret_via_P1`，以及 12 条内联路线字面量（原 88 行 → 现约 35 行）。**保留** `door1route = {N3,N8}`：它是 `DOOR_D3 NO_PASS` 分支"从 N4 去撞 D4 读灯"的**去程**（不是回程、只有 2 个节点），未纳入本次改造。
  (3) `plan_route_at()` 从 `#if USE_PLANNER_ROUTE` 里挪出来改为恒编译（门回程恒用规划器，不受该开关影响）。
  (4) `mapInit()`（每轮开始）与 `Clear_door()`（二轮全放行）各加 `nav_clear_blocked()`：门区禁用状态不能跨轮残留。
  行为变化（有意，需实车确认）：① 路线本身按 `_check_door_perm` 证明与旧手写路线**逐字一致**；② 若规划失败（如边表漏配）现在会 `CarBrake_Stop()` 死停而不是照旧数组硬走；③ `treasure` 非法(0/1)时旧代码不写任何路线（行为未定义）、新代码直接回家。
  验证：5 个校验脚本全过（`_check_door_perm` 12/12）；`mission_planner.c`/`map_message.c`/`nav_planner.c` 经 `arm-none-eabi-gcc -Wall -Wextra -fsyntax-only` 0 error 0 warning；另用探针 TU（`#include "map.h"`+`nav_planner.h` 调 `nav_clear_blocked()`）确认新符号在 `map.c` 的包含链下可见。`map.c` 本体因桩缺 `TaskHandle_t` 未能过 GCC 语法检查，改动仅一行调用 + 删一行语句，已人工核对。

- **2026-09-11 晚（MAP_DEBUG 途径点）**：**`MAP_DEBUG` 调试路线支持一个"途径点"**（原来只能起点→终点两个点）。
  (1) `Mission/config.h` 新增 `VIA_POINT`：填 **`0` = 不用途径点**（退化成原来的两点行为），填 `MapNode` 枚举名 = 路线必须经过该点。⚠️ **`S1=0`**（`enum MapNode` 第 0 项），所以 **S1 不能当途径点**。
  (2) `Navigation/map.c` 的 `#if MAP_DEBUG` 分支：由 `nav_shortest_path(FIRST_POINT,END_POINT)` 改为 `nav_plan_waypoints()`，必经点数组 `wp = {FIRST_POINT, [VIA_POINT], END_POINT}`（`VIA_POINT=0` 时不压入）。`nodes.nowNode`(=第一跳 path[1]) 与 `route[]`(=path[2..] + `0xFF`，不与 nowNode 重复) 语义**完全不变**；`n<3`（起点==终点/不可达）时照旧直接 return 不规划。
  (3) 新增 `scripts/validate/_check_map_debug.py`：镜像改造前/后两版 MAP_DEBUG 逻辑并断言——① `VIA_POINT=0` 时两者**逐字一致**（穷举 54×54=2916 组 FIRST/END 全过）；② `VIA_POINT≠0` 时路线**依次经过**该点、且成本不短于无 via、相邻跳在边表里有向连通；③ 途径点写成起点/终点时等价于"不用途径点"；④ 打当前 `config.h` 实配路线。另新增 `scripts/validate/_syntax_map_debug.py`：从 `map.c` 抽出 `MAP_DEBUG` 代码块（真实源码文本，非手抄）套进探针 TU 做 `arm-none-eabi-gcc -fsyntax-only`——`map.c` 整体因 FreeRTOS RVDS `portmacro.h` 的 `__asm{}` 无法用 GCC 检查，故按 §12 的探针办法只查这一块。
  验证：6 个 validate 脚本全过（`_weight_calib`/`_check_csr`/`_check_wp`/`_check_door_logic`/`_check_door_perm`/`_check_map_debug` 全部 exit 0）；语法探针 **0 error 0 warning**（并做了负向测试确认它真能报错）。当前实配 `FIRST_POINT=N6, VIA_POINT=0, END_POINT=P3` → `nowNode=N5, route={N4,N3,P3,0xFF}`——**与改造前逐字一致，`VIA_POINT=0` 时固件行为零变化**；例：同一对起终点填 `VIA_POINT=P1` → `route={N4,B2,N1,P1,N1,B2,N4,N3,P3,0xFF}`（确实往返经过 P1）。
  (4) **陀螺仪角度初始化核对**（`mpuZreset(get_latest_yaw(), nodes.nowNode.angle)`，`main_task.c` 紧跟 `mapInit()`）：机制**正确**——`nowNode` = 「`FIRST_POINT`→第一跳」那条边，`mpuZreset` 后 `getAngleZ()` 立即等于该边 `angle`，之后所有转弯目标 `nextNode.angle` 同框。但结论带 3 个前提：① 地图**没有"节点角度"**，参考角是**边**的航向；② 摆车必须放在 `FIRST_POINT` 且**车头顺着 `FIRST_POINT`→第一跳**（`FIRST=N6→N5=0°`；`N9→N10=180°`；`C7→B10=-90°`），**换起点或换途径点都可能改掉第一跳→参考角跟着变**（`N6` 起点 + `VIA=P5`→第一跳 `C1=50°`）；③ 校准在**红外等待之前**，校完再用手摆车头就白校了。故 `_check_map_debug.py` 第 4 节现在会直接打印"参考角 + 摆车方向"。`lastNode.nodenum` 被设成 `FIRST_POINT` 是**对的**（首跳转弯的 `(last,now,next)` 三元组查表才准），唯一小坑是 `FIRST_POINT=S1(0)` 会撞上 `Nav_IsStraightThrough()` 的"首边未初始化"哨兵（只影响巡线陀螺阻尼，不影响角度）。

- **2026-09-11 晚（MAP_DEBUG 路线预测纠错：场次不同步 + 主动穿门）**：排查"`FIRST=N6,VIA=N3,END=P4` 走到 N3 没掉头反而往 N8 走"时确认——**不是车的问题：路线本来就要去 N8；而预测工具算错了。**
  (1) **根因（工具不同步）**：`scripts/validate/_weight_calib.py` 顶部写死 `USE_FIELD = FIELD_COMP`，而 `Mission/config.h` 是 `FIELD_SCHOOL`。门段长度两场地不同（`DOOR_LEN_*` 200 vs 170 → `map_message.c` 的 `DOOR_LEN_*/2` 即 100 vs 85），而**门边权重惩罚为 0**（`nav_planner.c: NavObsPenalty[DOOR]=0`，设计上"门用必经点约束、不靠权重"）⇒ `N3→P4` 有两种走法、换场地就翻盘：原路折返 `N3→N4→N5→N6→P4` = **510**（与场地无关）；穿门 `N3→N8→N5→N6→P4` = **523(比赛) / 493(学校)**。⇒ **学校场地下选穿门**（493<510）：`N3` 处 `nextNode=N3→N8`（angle 145, func=DOOR）→ **145° 停车转**（`GetForwardDistanceBeforeTurn(N4,N3,N8)=20`，正是调过的那条表项）→ 进 D4 门；比赛场地下才会选掉头（510<523）。**上一轮我说"会掉头"就是被这个不同步坑了。**
  (2) **修复**：`_weight_calib.py` 新增 `sync_field_from_config()`（读 `config.h` 的 `USE_FIELD`，覆盖该场地的 `LEN_*/DOOR_LEN_*`，含 `#endif` 后的派生宏 `LEN_N18B5`/`LEN_B7C6`）；`_check_map_debug.py` 开头调用它、按真实场次解析图，不同步时打告警。（`_check_wp`/`_check_csr`/`_check_door_*` 的 golden 仍按 `FIELD_COMP`，未改动，照旧全过。）
  (3) **新增两类告警**：`_check_map_debug.py` 第 4 节现打印**逐段航向/step/func + 每个节点的转弯需求量**，并告警 ① **180° 原路折返**（该三元组在 `GetForwardDistanceBeforeTurn` 通常无表项→退化默认值；180° 目标又正好落在 `need2turn` 的 ±180 边界、转向由亚度噪声决定；平台节点 `UpStage/UpStageHome/BSoutPole` 的折返标注为"平台内部转身，正常"）；② **路线经过 DOOR 边**（到点后 `map_function(DOOR)→door()`，而 `door()` 开头 `map.point=0; route[0]=0xFF;` 会**清空调试路线**，之后跑比赛门逻辑、`DEBUG=0` 时真读红绿灯）。
  验证：7 个校验脚本全过；实测 `FIRST=N6,VIA=N3,END=P4` 现预测 `route[]={N4,N3,N8,N5,N6,P4,0xFF}`（与车上观察一致，并给出门边告警），`VIA=N3,END=P3` 预测 `{N4,N3,P3,0xFF}`（N3 处直行，无门无折返）。**本轮未改固件**（只改校验脚本 + 文档）。

- **2026-09-11 晚（权重调整：门惩罚 0→60）**：用户提"要不给门的权限拉高 / 转弯权限降低"→ 先量化再动手（新增 `scripts/analyze/analyze_weight_sensitivity.py`）。
  (1) **修完两个镜像 bug 后测出的真值**（学校场地，`N3→P4` 这一段的两种走法）：原路折返 `N3→N4→N5→N6→P4`=**510**；穿门 `N3→N8→N5→N6→P4`=**493(门惩罚0) / 523(比赛场地)**。
      - **提高门惩罚**：每条门边 +P（这条走法有 2 条）→ **P=10 就翻**（差值 −17→+3），P=60 余量 +103。✅ 方向正确 → 已采用。
      - **降低转弯权重**：**方向反了**——掉头那条路 0 转弯费（全 180°）、穿门那条有 105° 转弯费，所以降 `NAV_W_TURN` 是**削弱穿门的劣势**（0.6→0.3 差值 −17→−48.5，比赛场地 0.6 本来选掉头、降到 0.3 反而穿门）。要它翻这个 case 得把 `NAV_W_TURN` **提到 ≥0.76**（学校），那是全局大改（南环/Hill 安全窗那套边界都建立在 0.6 上）→ **不动**。
  (2) **改动**：`nav_planner.c` 的 `NavObsPenalty[14]`(DOOR) **0 → 60**（等效 cm，与 UpStage 同量级：门要停车→等线→刹车→读灯 500ms+转弯，纯长度模型没算，取 0 等于把穿门当免费捷径）；`DOOR1`(18) 无任何边使用，保持 0。镜像 `_weight_calib.py` 同步 `DOOR`→60、并把 `BLBS` 60→**70** 与 C 表对齐（原为镜像/C 不一致的隐患）。
  (3) **回归证据**：门惩罚在 **0→300** 全程，`_weight_calib`(15 条参考路线)/`_check_csr`/`_check_wp`/`_check_door_logic`/`_check_door_perm`(12 条门回程 golden) **全部不变**；改完后 7 个脚本全过。效果：`wp={N6,N3,P4}` 从"穿门 N3→N8"改为"原路折返 N3→N4"（`{N4,N3,N4,N5,N6,P4}`），`wp={N6,N3,P3}` 仍是直行 `{N4,N3,P3}`。
  (4) ⚠️ **残余风险（需实车）**：门节点"从哪一侧进"由成本决定（`door()` 按 `lastNode/nowNode` 判 D2/D3/D4/D5），提权重后若某 wp 组合换了进门方向 → 读的灯也换 → **门区必须实车复核**；另外这条要求"原路折返 N3"的动作本身在 `GetForwardDistanceBeforeTurn` 里**没有调过**（走 19cm 默认值），所以调试路线仍建议用 `VIA=N3,END=P3` 那种"直行过 N3"的组合。
  (5) **"到底改了哪些路线"——穷举确认**（新增 `scripts/analyze/analyze_door_weight_route_diff.py`：按源码分支穷举固件**全部**规划调用点 + `MAP_DEBUG` 全空间；用"A 值下不含门边的路线在"只加不减"惩罚下**数学上不可能变**"剪枝，带分段缓存整轮约 10s）：

  | 范围 | 比赛 FIELD_COMP | 学校 FIELD_SCHOOL |
  |---|---|---|
  | ① 固件规划调用点（第一轮初始 / 门回程 `route_return_home` / `plan_treasure_return` / `stageAB` / 第二轮 `get_newroute`；140 个有效用例，其中 A 值下走门 89 个） | **改变 0 个** | **改变 4 个** |
  | ② `MAP_DEBUG` 全空间（FIRST×VIA×END，146,175 个有效组合；A 值下走门 67,005/67,810 个） | 改变 4,421 个 | 改变 5,881 个 |

  ①那 4 个全部是 **`plan_treasure_return`（宝物=P4 从 P7/P8 回程）的 `D4CAN`/`ONEWAY` 两个门分支 × 2 个起点（P7/P8）**，变化为
  `… N3 → N8 → N5 → N6 → P4 …`（旧）→ `… N3 → N4 → N5 → N6 → P4 …`（新），**门边数 3→1**：旧路线离开 N3 后为省 17cm **又钻回门区**（`N3→N8`=D4、`N8→N5`=D3，到 N8 还会触发 `door()` 清空 `route[]`），新路线只保留 wp 强制的 `N8→N3`。**等于顺手修掉一个隐患**。
  ②的变化**全部是"穿过更少门"**，无一例增加：门边数分布（学校）`1→0:3452 / 2→0:524 / 2→1:1317 / 3→0:4 / 3→1:584`；（比赛）`1→0:2982 / 2→0:133 / 2→1:1196 / 3→1:110`。
  > 即：**比赛场地的固件路线一处未动**；学校场地仅 4 处且都是"少钻门"；其余差异只出现在"本来会穿门"的组合里（正是本次要治的）。

- **2026-09-11 晚（边寻线节点保护：抑制节点干扰）**：修"寻左/寻右在节点处误差大跳变"。
  (1) **根因**：`Application/scaner.c` 的 `calc_left_edge`/`calc_right_edge` 是"无条件取最靠边的一段（最多 2 灯）"，**没有任何多灯/多线判断**（对比 `calc_near_center` 有 `ledNum>=4→error=0`、`calc_track_all` 有 `ledNum>MAX_LED(4)→return -1`）。节点横线/线与线粘连时，最边上那段被拉长/移位 → `error` 在节点处大跳变 → 车"打一下方向"再被拉回。`coarse_filter` 只挡 `ledNum>=6`，**4~5 灯的节点标记会漏进来**。
  (2) **修复**：新增 `edge_run_len()` 统计**被选中那段连续亮灯的长度**，`> EDGE_SEG_MAX_LED` 判为节点横向线/粘连 → `return -1`（该帧记 `ALL_ERR`）→ 交给 5 帧历史保持上次有效误差，节点处不再跳变。**左/右两个边寻线函数都加**。
  (3) **参数**：`Application/scaner.c` 的 `EDGE_SEG_MAX_LED`（默认 **3** = 丢弃 4 灯及以上的段）。正常要跟的细线一般 1~3 灯；节点横线/粘连 ≥4 灯。
  (4) **验证（需实车）**：① 过节点不再打方向（跑 `N3→N4`/`N4→N5` 等带节点段）；② 正常直线循迹没变差（变差=被误丢 → 调大阈值）；③ 节点处**不触发**丢线保护急刹（节点丢帧是短暂的，不该触发 `Scaner_IsLineLost()` 的 80×5ms）。
  (5) ⚠️ **局限（重要）**：只覆盖"**被选中段被拉长（线与线粘连成宽线）**"这一类；若节点是"主线 + **独立 2 灯节点臂**"（如 CLEFT 的 bits13/14），该段长仍为 2，**这条判据拦不住**，那种情况仍靠 `pos_detect`（位置跳变）+ 5 帧投票兜底。若实测确认这类干扰仍明显，再补 `lineNum` 判据（如 `ledNum>=4 && lineNum==1`）。
  (6) 关掉本保护：把 `EDGE_SEG_MAX_LED` 调成很大的值（如 99）即恢复旧行为。

- **2026-09-12（过门后必经点精简：能靠 P5~P8 就不写 N）**：用户提"过门后能否尽量少 N、主要靠 P5~P8"→ 先量化再动手。
  (1) **结论（22/22 场次逐字节相同）**：删掉这些**冗余 N 锚点**后，规划器路线与写全锚点时**完全一致**：
      ① 二轮巡游段末尾的 `N10`（顺时针）/`N12`（逆时针）——从 P6/P5 去回程门节点本来就走它们；
      ② 二轮进门时"第二个门节点"：`N8,N12`→`N8`、`N3,N8,N12`→`N3`（`p6_first` 时 D4 进门的 `N3,N8` 两个都要留）；
      ③ 二轮回程中第二跳为 `N3` 的：`N8,N3`→`N8`、`N10,N3`→`N10`；
      ④ 第一轮 `stageAB` 的环上中间 N：`P5,N12,P7`→`P5,P7`、`N10,P6,…`→`P6,…`。
  (2) ⚠️ **不能删**（删了会改路/改门）：进门与回程的**第一个门节点**（`N12`/`N8`/`N3`/`N5`/`N10`，它锁定"走哪扇门"）；**`N8,N5` 里的 `N5`**（删掉后规划器改走 `N8→N3` **穿 D4** 出西侧，实测路线真的变）；`stageAB` 尾部的 `C9`/`N20`（→ 见下条：不能单独删，补了"平台交接"后才删）。
  (3) **改动**：只动 `Mission/mission_planner.c` 的二轮 wp 与 `update_route_at_door_for_stageAB()`；二轮 wp 由 15~16 点降到 12~13 点（当前 debug 场次 15→12）。**不改第一轮门回程、不改边表、不改权重**。
  (4) **新增 `scripts/validate/_check_wp_east.py`**：把"精简 wp"与"写全 N 锚点的旧 wp"锁死——遍历**全部可达门状态组合 × 宝物**（100 组）+ `stageAB` 4×3 组合。⚠️ 冗余性是在**当前权重**下成立的，动权重后必须重跑。
  验证：`_check_wp_east` 100+12 组合 0 差异；7 个旧校验脚本全过（`_weight_calib` 15/15、`_check_door_perm` 12/12）；armcc 全量 49 个 TU **0 error、31 warning（与改前一致，无新增）**。

- **2026-09-12（续：stageAB 尾锚点 C9/N20 与"平台交接"）**：上条里"`C9/N20` 保留待实测"这一步做完了 —— 结论是**它不能单独删**，必须配套"平台交接"。
  (1) **先解耦 `origin_angle`（零行为变化）**：`barrier.c:985`（`Barrier_HighMountain`，P8）/`1136`（`South_Pole`，P7）原写 `origin_angle = nodes.nextNode.angle`（= 出平台边，依赖"路线里还有下一跳"），改为 `origin_angle = need2turn(0.0f, nodes.nowNode.angle + 180.0f)`（= "进平台边的反向"）。因 P7/P8 都是**死胡同支路**（进出同一条边、方向相反：`C9→P7`=180↔`P7→C9`=0，`N20→P8`=0↔`P8→N20`=180），新写法与原值**逐值相同**（P7:0、P8:180），纯解耦。
      注：`need2turn(a,b)` 返回 `b-a` 归一化值，所以写 `need2turn(x, x+180)` 会恒等于 180（P7 就错了）；正确写法是 `need2turn(0.0f, x+180.0f)`。
  (2) ⚠️ **只删 `C9/N20` 会死停车**（仿真 4/4 复现，A5B7/A5B8/A6B7/A6B8 全中）：平台出口锚点不只是"终点"，它被**节点推进**消费 —— `map.c` 的 `nodes.nowNode = nodes.nextNode` 靠它把 nowNode 从"进平台那条边"挪到"出平台第一跳"，正好接上平台上重规划出来的回程 `route[]`（`plan_treasure_return()` 用 `plan_route_at(map.point - 1, …)` 覆盖）。删掉后 `nextNode` 停在进平台边 → 下一步 `getNextConnectNode(P8, 回程第二跳)` 找不到边 → `Route_Error_Stop()` 死停车；同一处 `nodes.nextNode` 还被 `Stage_Correct()`（`barrier.c:179-180`）当行驶航向用。
      证据：仿真脚本严格照抄 `map.c` 的推进逻辑（`door()` 里 `map.point=0` 提供索引锚点），三种方案对比 `tail`(✅4/4) / `notail`(❌4/4 报 `P7->N22 无边`、`P8->C4 无边`) / `notail+fix`(✅4/4)。
  (3) **改动**：`update_route_at_door_for_stageAB()` 的 4 个 wp 去掉尾部锚点（`{now,P5,P7,C9}`→`{now,P5,P7}` 等，这一段现在**只写 `P5/P6` + `P7/P8`**）；`plan_treasure_return()` 末尾补**交接修正**：`if (plan_route_at(...)==0) return 0; u8 first = route[map.point-1]; if (first != 0xFF) nodes.nextNode = Node[getNextConnectNode(start, first)];`（把 nextNode 显式对齐到"出平台第一跳"）。
  (4) `_check_wp_east.py` 的 stageAB 断言相应升级为：① 删中间 N → 路线逐字节不变；② 删尾锚点 → **只允许少最后一个节点**，路径本身必须完全一致（这就是交接成立的前提）。
  验证：`_check_wp_east` 100+12 通过；7 个校验脚本全过；armcc 全量 49 个 TU **0 error、31 warning（无新增）**。⚠️ 仍需实车确认 P7/P8 下坡朝向与平台后第一跳。

- **2026-09-12（转弯前硬补偿：现状分析 + "能算就算"改造方案 —— 本轮未改固件）**：
  背景：用户提"路线很多依赖硬补偿，想综合节点检测方式与当前边/下一条边的夹角直接算距离"。**先量化再定方案**，本轮**只加分析脚本 + 文档，`Navigation/map.c` 一个字没动**。
  (1) **现状**（`map.c` 的 `GetForwardDistanceBeforeTurn` / `GetForwardDistanceBeforeGyroTurn` 两张表共 29 条）：真正生效 **22 条**，**7 条是死值/无效** —— `B3→N2→P2`=24、`N8→N3→P3`=18、`B8→N9→N10`=30、`B2→N1→P1`=18、`N5→N12→N11`=5、`N4→N5→N12`=6 因"分支判定 `(STOPTURN&&|turn|>30)||(|turn|>=90)`"与表项位置不一致而**永远不生效**；`N2→N8→N10`=15 连边都不存在。边表里"需要停车转"的 (入边,出边) 组合共 **241** 个，实测值只覆盖 **14** 个（6%），其余一律吃默认 **19**。
  (2) **根因（数据 + 图像双重验证）**：硬补偿那一列**同时表达两件事** —— ① 真·转弯几何 `Δ = L(1−cosφ) + d(判据)`（`L` = 旋转中心→传感器板中心纵向距离；9 条"平地+大角度"数据反解 `L` 中位 **17.0** / 均值 **19.2**，`1−cosφ` 与实测相关 **r=+0.70**）；② **段长补偿**（`map.c` 到达门槛是 `里程 ≥ 0.7×step`，`step≤18cm` 时车被**里程提前放行**，补偿实际在补段长：`0.7×step + 补偿` 全部落在 17~38cm 的正常检测起点量级）。两件事混在一列 ⇒ 任何公式都拟合不了。
  (3) **崩掉的点零反例**：用地图像素坐标（5 条长直边标定 0.884 px/cm）定位后确认，全部落在 ①跷跷板/山/桥/平台（板子离地、检测时刻不可预测）②门区 / X 交叉（多判据竞争）③入边 `step≤18cm` 三类；**能对上的 8 条全部是普通平地的单线节点**。另确认 **表里 `angle` 是可信的**（与地图真实走向只差一个固定参考系旋转），但**节点图是示意图、不能用像素反推距离**（`B9→N7` 表 5cm / 图上约 99cm；用图算角反而更差 MAE 10.11 vs 9.61）。
  (4) **方案（已定，含安全闸门）**：`Tier1 表里有→实测值 / Tier2 规则命中且 |公式−实测| ≤ 5cm→公式 / Tier3 其它→保留默认 19`；规则 = 入边 `func∈{NONE,DOOR}` 且 `step≥20cm` 且 `100°≤|转弯|<178°`；公式 `Δ = 19.0(1−cosφ) + d`，`d(CRIGHT)=+11 / d(CLEFT)=−4 / d(DLEFT)=−5 / 其他=−4`。覆盖：Tier1 **8** + **Tier2 53**（其中 47 条原本吃 19）+ Tier3 **186**；**5cm 闸门挡回 3 条**（`N13→N18→B5` 60vs28.9、`C4→N20→P8` 35vs46.9、`N4→N3→N8` 20vs29.1）。闸门让机制**自保护**：以后每补一条实测数据，公式与它矛盾就自动退回实测值。**陀螺不停车转分支本次不动**（44 个组合多为小角度，公式在 <90° 未经验证）。唯一必需的代码新增 = 把 `ArriveDetect_task.c` 的 `deal_arrive()` 的**判据标志位**传出来（现在只返回 0/1）。
  (5) **产物**：新增 `项目讲解文档/转弯补偿拟合分析.md`（问题定位）+ `转弯补偿_能算就算方案.md`（含 Tier2 完整 53 条清单与代码骨架）；新增 `scripts/analyze/analyze_turn_comp_{base,step_check,rule,final_plan,gate,map_geom}.py`（6 个只读分析脚本）；`project_reference.md` 新增 §14、§10 函数表补 `GetForwardDistanceBefore*`；`scripts/README.md` 收录 6 个脚本。
  ⚠️ **下一步二选一**：① 按方案改 `map.c`（含判据标志位）；② 先加"检测时刻里程日志"（`nowNode.step − Chassis_GetMileage()` 免费可得）拿一轮真数据，优先补 90° 转弯那批（现 53 条 Tier3，补后阈值放到 85° 可再覆盖约 53 条）。

- **2026-09-12（新增：地图图形化编辑器 `scripts/map_editor/`，**本轮未改固件**）**：
  背景：用户要调整地图（切 `C9↔P7`、`B7↔C6`、加 `C10`、把 P7 挪到 C6 位置），但手改 `NavEdgeTbl[]` 太容易错（124 行 + `NAV_EDGE_COUNT` + 正反向边 + 宏）。⇒ 做个可拖拽的图形编辑器，**只加辅助工具，`Navigation/`、`Mission/` 一个字没动**。
  (1) **能力**：打开即从源码读图（`enum MapNode` + `NavEdgeTbl[]` + `config.h` 宏）；拖节点、Shift 拖出连线、点选改 `from/to/flag/angle/step/speed/func/comment`（`angle/step` 可直接写 `ANGLE_*`/`LEN_*`/`DOOR_LEN_*` 宏并按当前 `USE_FIELD` 求值）、flag 25 位勾选板、补反向边、方向取反；校验（孤立/单向/重名/宏求值）；必经点最短路（**与固件同一套 Dijkstra + `NavObsPenalty`**，输出 `route[]`、逐段明细，并对 **180° 折返**与**经过 DOOR 边**告警）；导出 `NavEdgeTbl[]`/`enum MapNode`/`NAV_EDGE_COUNT`/`route[]`；「写回固件」先自动备份到 `backups/` 且有 error 时拒写。
  (2) **两条心智模型（用户明确要求）**：① **节点位置只是示意图** —— 图上远近不代表实际长度，长度只认 `step` 数值，**节点随便拖不影响任何数值**；图只表达「连接关系 + 角度关系」并贴合标准节点图。② **导出逐字段保真** —— 不做编辑时导出的边表与源文件**完全相同**（`_selftest.py` 断言差异 0 处），所以"打开→导出"零风险。
  (3) **底图对齐**：自动把 `寻宝地图/节点图.jpg` 半透明铺在节点下面。关键发现：**`SEED_POSITIONS` 是该 1729×1080 原图的像素坐标**（实测 `P8(96,510)` 与 `N12(645,340)` 的像素差 549/170 与模型坐标差完全一致）⇒ 底图 1:1 铺开即对齐；`C2/B4/C6/C7/C8/G1` 六个节点原图**没画**，坐标按相邻节点与边角度估（`map_model.MISSING_SEED`），拖动微调即可。
  (4) **修掉 3 个真 bug**（都写了自检护栏）：① `config.h` 宏解析把 `#define LEN_N18B5 (LEN_N22B7 - 20)` 的括号当成函数宏参数表 → 宏丢失（改用「紧贴括号=函数宏 | 其余=对象宏」两分支）；② `ANGLE_N8N3` 这类名字被文本替换成 `ANGLE_REV(...)` 时子串污染（改成手写递归下降求值器，不依赖 `eval` 文本替换）；③ 界面 `select_node → _tree_select → <<TreeviewSelect>> → select_node` 无限重绘（加 `_syncing_tree` 抑制）+ **画布被 `ttk.Panedwindow`/grid 按左栏 Notebook 请求宽度挤成 394px**（改 `pack` + `pack_propagate(False)`，现 1049px）。
  (5) **产物**：`scripts/map_editor/{map_editor.py, map_model.py, README.md, _selftest.py, _guismoke.py}`；`scripts/README.md` 新增 `map_editor/` 段；`project_reference.md` 新增 §9.5（原 §9.5 MAP_DEBUG 顺延为 §9.6）+ §10 函数表一行 + §12.8。
  验证：`_selftest.py` 全过（往返差异 0 处、124 条边宏求值 100%、导出行数==`NAV_EDGE_COUNT`、增删改/改名/撤销、规划、一次"切边+加节点+挪 P7"演练）；`_guismoke.py` 全过（画布 1049×859、54 节点/124 边 item 数一致、选中/拖动/三档标注/校验/规划/6 类导出）；**既有 7 个校验脚本全过且 exit 0**（`_weight_calib` 15/15、`_check_door_perm` 12/12）—— 证明没碰坏既有工具链。
  ⚠️ **未做**：具体那次地图改动（切 `C9↔P7`/`B7↔C6`、加 `C10`、挪 `P7`）**要等用户确认最终拓扑**再改；编辑器只保证"导出文本正确"，增删节点后仍需人工同步 `mission_planner.c` 的 `wp`、门逻辑、宝物表。

- **2026-09-12（续：编辑器加「保存布局」+「自定义/对齐底图」，**仍未改固件**）**：
  用户反馈"节点和背景图对不上、要自己拖吗、拖完能保留吗、背景图能不能自己定" ⇒ 补三件事。
  (1) **保存布局**：工具栏「保存布局」→ `scripts/map_editor/layouts/default.json`，**下次打开自动载入**（节点位置 + 底图标定一起存）；关窗口有改动会问"是/否/取消"；`Ctrl+S` 同效；「重新载入源码」**不再丢布局**（按节点名把坐标搬过去）。⇒ **拖一次存一次，以后打开就是调好的样子。**
  (2) **底图可自定义 + 可微调**：右栏新增「底图对齐」面板 —— 下拉列出 `寻宝地图/` 所有图片、「浏览…」可选任意目录任意图片（jpg 需 pillow）；五条滑条（偏移 X/Y、缩放 X/Y、透明度）；「重置」回 1:1 居中；**「用节点反推最佳位置」= 拿图上量过坐标的节点做最小二乘拟合**。命令行也支持 `--bg <图片>`。实测：**48 个点反推，平均残差仅 5.7 px**（原图 1729×1080）⇒ 说明节点坐标本身是准的。
  (3) **说清"哪几个节点本来就不可能对上"**：`C2/B4/C6/C7/C8/G1` 在 `节点图.jpg` 上**根本没画**（已列进 `map_model.MISSING_SEED`），坐标按相邻节点+边表角度估；用户拖到自认的位置即可，**不影响任何数值**。
  (4) **启动器**：`run_editor.bat`（双击开，无命令行窗口）、`run_editor_console.bat`（带窗口看报错）。⚠️ 踩坑记录：**`.bat` 文件名不能带中文** —— 在 `cmd` 的 GBK 代码页下会被拆坏（报 `'m' is not recognized`），故改用纯 ASCII 名。另：Store 版 Python 的 `pythonw` 进程名是 **`pythonw3.13`**，用 `Get-Process pythonw` 查会误判成"没启动"。
  (5) **JSON 版本升到 2**：新增 `background` 字段（底图路径+标定），`version 1` 的旧工程仍可读。
  验证：`_selftest` 全过；`_guismoke` 全过（新增"拖动→保存→重新载入坐标恢复""底图反推/滑条/重置"两组断言）；**既有 8 个校验脚本全部 exit 0**（`_weight_calib` 15/15、`_check_door_perm` 12/12、`_check_wp_east` 100+12）；固件源码指纹与本轮开始时**逐字节一致**（4 个文件 SHA256 未变）。

- **2026-09-12（续：编辑器加「约束拖动」，**仍未改固件**）**：
  用户要求"拖动只能沿角度拖、角度严格按表里的值、长度也不能随便、要 ≥ step 对应长度"。
  (1) **实现**：工具栏「**锁角度**」「**限最小长度**」「**单位长 K**（px/cm，可改，默认 0.884）」三个控件（默认开启）。拖动时把节点吸附到"相邻边的 `angle` 直线"上、且该边图上长度 ≥ `step×K`；画布上实时把每条相邻边标**绿(合规)/红(违规)**并显示 `px/cm/step/需≥`，状态栏同步读数。
  (2) **⚠️ 关键实测结论（必须先知道）**：节点图**不是等比例的** —— `图上px ÷ step` 比值从 **0.17 到 94.9（差 500 倍）**，所以**不存在**能让全部边都满足"长度≥step×K"的 K。实测违反数：K=0.5 → 5/122；**K=0.884 → 25/122**；K=1.0 → 30/122；K=2.0 → 63/122。（典型：`C2→C1` step=185cm 但图上仅 32px；`B9→N7` step=5cm 但图上 87px。）⇒ 新增工具栏「**违反约束的边**」列出这些"本来就拖不出合法位置"的边，让用户自己取舍 K。
  (3) **多边节点角度约束常"互斥"**：一个节点连 ≥3 条不同方向的边时，"所有边都严格保持角度"**无解**（如 `C9` 同时被 `N22`(-90°) 与 `G1`(180°) 要求）。求解器优先找满足全部约束的最近点；找不到就退化为"逐条边投影取最优"并**如实报「约束互斥」+ 逐条标红**，不假装满足。关掉两个勾即可自由拖。
  (4) **修掉 3 个求解器 bug**（都写了断言护栏）：① 角度判据原用"与方向向量平行"（叉积）→ 同一条线段两个方向记的角度不同（`S1→N3=160°` / `N3→S1=-25°`）会把正常情况误判成矛盾 ⇒ 改为**点到直线距离**；② 射线候选点漏了**垂足** ⇒ 单边节点被弹到几十像素外；③ 去重分支无条件塞回方向 ⇒ **关掉"锁角度"也关不掉**。
  (5) **新增只读分析脚本** `scripts/map_editor/analyze_unit_length.py`（量 px/step 分布，定 K 上界）。
  验证：`_selftest` 全过；`_guismoke` **49 项 [OK] / 0 FAIL**（含"S1 单边可行且角度长度合规""P8 度2 角度全合规""C9 度3 正确识别互斥""关约束后可自由拖""违规清单可用"）；**既有 8 个校验脚本全部 exit 0**；固件源码 SHA256 未变。

- **2026-09-12（续：编辑器加「视图旋转」+ 底图位置可精确输入，**仍未改固件**）**：
  用户反馈"坐标系搞错了，0 度是竖着的"+"背景偏太多移不到中间"。
  (1) **视图旋转**：新增工具栏「旋转」下拉（0/90/180/270），**节点与底图一起转**（底图用 PIL `transpose` 同步旋转），保证两者始终贴合；纯显示设置，**不改任何数值**，随「保存布局」记住，也可 `--rot 90°` 指定。
      **实测各档与表里 `angle` 的自洽度**（`|屏幕方向−表里angle|` 中位 / 符合≤10° 的边数）：**0°→90.0°/0-77；90°→5.6°/55-77；180°→90.0°/0-77；270°→174.4°/0-77**。⇒ 就"图与表角对得上"而言 **90° 唯一自洽**；但朝向是口味问题，四档都留着让用户自己选。各档下"表里 0°"依次指向 0°→上、90°→左、180°→下、270°→右。
      ⚠️ **踩坑记录（重要）**：中途我曾把 `ROT_DEFAULT` 改成 270° 又改回——因为**约定本身无法从数据推断**（同一个"0°"在不同参考系里含义不同），最终决定**默认 0°（不旋转，即节点图原样）+ 提供四档切换**，不再替用户猜。
  (2) **底图位置可精确输入**：偏移/缩放的滑条旁**各加一个数字框**（滑条范围放宽到 ±3000，数字框无限制），解决"移不到中间"；按钮改名为「贴到节点」「居中」。
  验证：`_selftest` 全过；`_guismoke` **49 项 [OK] / 0 FAIL**；**既有 8 个校验脚本全部 exit 0**；固件 SHA256 未变。

- **2026-09-13（编辑器：坐标校准 + 引导线偏移 + 布局文件，**仍未改固件**）**：
  (1) **坐标差 1.7 倍的真正病根**：`SEED_POSITIONS` 存的是**预览图(1012 宽)坐标**，而底图是**原图(1729×1080)**，所以底图整体偏移。用图上地标量出倍率（P1 方框 1.7106、P2 方框 1.7115 → 取 **1.7112**，y 另加 +9），把 58 个坐标全部换算到原图像素系。校准后与图上实测：`P1` 差 (−12,+1)、`P2` 差 (0,+14)、`N3→N5` Δ=(+462,0) 与图完全一致。
  (2) **`world_to_view` 在 0° 档也不是恒等变换**（把 y 取反了），把节点翻到负坐标区。四个旋转档改成干净的旋转矩阵，`0° = 恒等`。**默认旋转 = 0°（沿用 `节点图.jpg` 原本角度，用户确认原图角度是对的）**。
  (3) **拖动引导线角度偏移** `DRAG_ANGLE_OFFSET = 90°`（模块常量）：实测"表里 angle"与"图上边实际方向"整体差 90°（有符号偏差中位 −89.2°，61 条边落在 −90° 桶），故约束方向按 `angle + 90°` 算。副作用：同段两方向算出的引导线不再共线 → 某些节点（如 `S1↔N3`）会报"引导线角度互相矛盾"；此时**放开不吸附**（节点照鼠标走、违规边标红），不会假死。
  (4) **布局文件**：`保存布局`(`Ctrl+S`) → `scripts/map_editor/layouts/default.json`，**启动自动载入**（优先级高于出厂 `SEED_POSITIONS`）；「载入布局」可切多套；`--layout` 可指定。文件内含节点坐标+边表+底图标定+约束设置。
  (5) **新增只读分析** `scripts/map_editor/analyze_layout.py`：输出挪动清单、位置精度、单位长度 K 建议与违规边、按 `angle+偏移` 的角度一致性。
  **用户布局实测结论**：位置对齐良好；`K=0.63` 时仅 1 条边（`C2→C1`）不满足长度约束（出厂默认 0.884 是 3 条；理论最大可行 K=0.520）；按 `angle+90°` 判定 93/124 条边在 15° 内一致，不一致的 31 条里 `B2/B3/C1/N4/N5N8` 一带需要 `angle+0°`；6 条线段（`N3↔S1`/`C1↔N6`/`C1↔C2`/`N14↔S3`/`N15↔S4`/`N16↔S5`）两个方向需要的偏移相反 → 该段在任何单一约定下都无法同时对齐（已如实告知用户）。
  (6) **测试护栏**：`_guismoke` 新增"引导线方向 = 表里 angle + 偏移"、"约束矛盾时放开不吸附"等断言；并验证**冒烟测试跑完布局文件 SHA256 不变**（测试内部备份/还原）。
  验证：`_selftest` 全过；`_guismoke` **50 项 [OK] / 0 FAIL**；**既有 8 个校验脚本全部 exit 0**；固件 SHA256 未变；用户布局文件 SHA256 未变。

- **2026-09-13（编辑器：点图形选边 / 快捷增删 / 另存为+多版本 / 工具栏两行 / **新增 AI 文档**）**：
  (1) **点图形选边**：边加了 `EDGE_HIT_WIDTH=14px` 的**隐形粗线命中区**（`fill=""`，放进 `_canvas_items[tag]` 才有绑定），不用精确点中 1.3px 细线；选中后状态栏提示可用操作。
  (2) **快捷增删**：新增「连线模式」（点两个节点**直接建边、不弹对话框**；点边则以它的 to 端起继续连）、`A` 键以选中节点续连、`Esc` 取消、`Delete` 删选中的边；右键节点/边新增「删全部入边/出边」「删除这一对（双向都删）」「从 X 继续连」「补反向边」。快捷建边**角度按图上位置自动算**，`step` 默认 0（提示用户改实测值）。
  (3) **另存为 + 多版本**（用户要求"不要只保留一个版本"）：工具栏「保存布局 / **另存为** / 载入布局（列表挑选）」；每次保存前把旧版快照到**被测文件同目录**的 `snapshots/`（保留 30 份）；标题栏显示当前布局名 + `*` 未保存标记。
  (4) **工具栏改两行**：加了旋转/锁角度/限长度/单位长后一行放不下，**右侧控件跑到屏幕外**。拆成「文件/编辑」+「视图/约束/导出」两行（宽 1264 / 1132），`minsize` 改 **1300×720**，标签略精简。
  (5) 🤖 **新增 `scripts/map_editor/AI_CONTEXT.md`**（**给 AI 读的项目参考**，11 节）：边界、文件职责、数据流、**坐标系与角度**（含 1.7112 倍换算、0° 恒等、`DRAG_ANGLE_OFFSET=90` 的实测依据）、拖动约束求解、**6 条必须保住的不变量**、**5 条安全规则（含"测试绝不许碰真实布局"）**、测试期望值、常见改动指引、已知限制（不要当 bug 修）、数据来源可追溯。已在 `scripts/README.md`、`map_editor/README.md`、`project_reference.md §9.5` 三处挂上入口。
  (6) **事故与修复（重要）**：本轮我**误删了用户调好的 `layouts/default.json`**（把它当测试产物），git/回收站/卷影副本/OneDrive 全无备份，**无法恢复**。已加三层防护并写进 AI_CONTEXT §7：① 保存自动多版本快照；② `_guismoke.py` 改用 `layouts/` 之外的工作区沙箱 + 对真实布局做 **SHA256 前后比对**；③ 沙箱目录**不能用 `tempfile.mkdtemp`**（本环境文件沙箱下写入 PermissionError，必须用 `os.makedirs`）。
  (7) **文档数字核对**：写了 `_verify_doc.py` 对照代码逐条验证 AI_CONTEXT 里声称的常量/行为（29 项全一致）后即删。
  验证：`_selftest` 全过；`_guismoke` **68 项 [OK] / 0 FAIL**（新增"工具栏两行且不溢出""边有命中线""连线模式点两下建双向边""Delete 删边""真实布局 SHA256 不变"等断言）；既有 4/8 个校验脚本抽样 exit 0；固件 SHA256 未变。

- **2026-09-13（编辑器：修双击冲突 + 边列表三种展示模式）**：
  (1) **修"双击边同时触发新建节点"**：`_on_bg_double()` 原来**无条件建节点**，从不判断落点。现在按落点分派：**节点**=忽略 / **边附近**=打开该边编辑框 / **Shift+空白**=新建节点 / **空白**=只提示不弹窗；每个分支都 `return "break"` 防冒泡。新增 `_edge_near()`（点到线段距离，容差 6px + 命中区半径 7px）做边命中判定。双击节点改为"以它为起点续连"。
  (2) **边列表三种展示模式**（左栏「边显示」下拉）：**合并双向**（默认）/ 逐条 / 只看双向。合并模式**同一条线段的两个方向合成一行**，两方向的「角度/step」并列显示：`↔ A↔B  →角度 →step ←角度 ←step`。为此边树列结构改为 `(a1,s1,a2,s2)`，表头随模式切换；树 iid 有两种前缀 `e:A->B`（单行）/ `b:A<->B`（合并行），选中/回写选中都要兼容。
  (3) **属性面板补"反向边参数"**：选中双向线段时标题显示 `线段 A↔B 【反向边参数】B→A：xx°/step xx/func`；选中单向边提示 `⚠ 没有反向边`。
  (4) 展示模式与标注档位随「保存布局」一起记入 `constraints`。
  **用户数据实测**：124 条边中 **114 条有反向边**、共 **67 条线段**（57 条双向）；即 10 条单向边（`N7→B8`/`B8→N9`/`B9→N7`/`C2→N13`/`N9→B9`/`N10→N12`/`N12→P5`/`N13→N18`/`B4→C5`/`B4→N18`）。
  验证：`_guismoke` 从 68 → **78 项全过**（新增"合并双向行数==线段数""合并行同时显示两方向参数""只看双向行数==有反向边数""双击分派不冲突"等断言）；`_selftest` 全过；真实布局 SHA256 未变。

- **2026-09-13（编辑器：拖动改为「自动吸附水平/竖直」+ 工具栏三行）**：
  (1) **新增吸附模式**（工具栏第 3 行「吸附」下拉，默认**吸附水平/竖直**）：方向离屏幕上的 **0°/90°/180°/−90°** 最近的轴 —— **≤ 阈值(默认8°) 精确吸正**、**≤ 软范围(25°) 投到该轴**、再远不干预。另两档：**跟随角度表**（旧行为，`angle+90°`）、**自由**（不约束方向）。「限长度」（`≥ step×单位长K`）独立生效。
      之所以默认改成"吸附水平/竖直"：实测**表里 `angle` 与图上边方向整体差 90°**（有符号偏差中位 −89.2°：61 条 −90°、32 条 +90°），且不一致的 31 条里 `B2/B3/C1/N4` 一带需要 `+0°` —— 说明"按角度表硬锁"本来就跟图不符；用户也明确要求偏好水平/竖直。
  (2) **两个实现陷阱（都写了注释与断言）**：① 软拉扯**不能**用"权重 × 垂距²"——`tan(near)²≈0.217` 太小，轴候选分数比原始位置大 **4.6 倍**（6029 vs 1311）根本拉不动 ⇒ 改成**按范围确定性吸附**；② 硬吸正**不能**"逐方向试 + 比分数"——偏 5° 时"垂足"与"轴上点"分数差 **<1e-9** 会被容差挡掉 ⇒ 改成**先挑最近的轴再无条件吸**。
  (3) **工具栏改三行**（吸附控件加进来后两行放不下）：①文件/编辑 ②视图 ③吸附/长度/导出；实测三行宽 1163 / 656 / 729，`minsize` 回调到 **1200×720**。
  验证：`_guismoke` 从 78 → **84 项全过**（新增"默认吸附模式""偏5°精确吸正""偏15°软拉扯到最近轴""偏40°不干预""自由模式不约束方向"等断言）；`_selftest` 全过；真实布局 SHA256 未变。
