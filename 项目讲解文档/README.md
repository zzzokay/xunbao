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
  ⚠️ **下一步二选一**：① 按方案改 `map.c`（含判据标志位）；② 先加"检测时刻里程日志"（`nowNode.step − Chassis_GetMileage()` 免费可得）拿一轮真数据，优先补 90° 转弯那批（现 Tier3，补后阈值放到 85° 可再覆盖约 50 条）。

- **2026-09-12（转弯前补偿"能算就算"落地 + 两个"把注释当生效"的数据 bug）**：上一条的分析结果**已实现进代码**，并修正了上一条里的数字。
  **(1) 代码改动（4 个文件）**：
  ① `Navigation/map.h` 新增 `enum { ARRIVE_NONE, ARRIVE_DLEFT, ARRIVE_DRIGHT, ARRIVE_CLEFT, ARRIVE_MCLEFT, ARRIVE_MCRIGHT, ARRIVE_CRIGHT, ARRIVE_MORELED, ARRIVE_AWHITE, ARRIVE_MUL2SING, ARRIVE_MUL2MUL }` + `extern volatile uint8_t arrive_method;`（顺序 = `deal_arrive` 的 if 链优先级）。
  ② `Task/ArriveDetect_task.c`：`deal_arrive()` 增加 `uint8_t *out_method` 出参，10 处 `return 1` 各自写入命中判据；定义 `arrive_method` 全局；任务里传进去（先写判据、再置 `CROSS_EVENT_ARRIVED`，主任务阻塞等待故读到的一定是新值）。`.h` 声明同步。
  ③ `Navigation/map.c`：停车转表由 18 行 if 链改为 **`kTurnTbl[13]`**（清掉 3 条死值 + 1 条注释条目），在原 `return 19;` 前插入 **Tier2 公式** `Δ = 19·(1−cosφ) + d(判据)`（`d(CRIGHT)=+11 / d(CLEFT)=−4 / d(DLEFT)=−5 / 其他=−4`）与 **5cm 闸门**（表里有实测且 |公式−实测|>5cm 则用实测）；新增 `Node_Lookup()` 与 `TURN_*` 宏、`arrive_method` 定义。**陀螺不停车转表未动**。
  ④ `Mission/config.h` 新增开关 `TURN_CALC_ENABLE`（1=启用，0=完全回原行为）。
  **(2) 两个实现细节（踩过坑）**：`func`/`step` 必须取**入边原始值**（`Node_Lookup(last)`），**不能读 `nodes.nowNode.step/function`** —— `door_set_pass_node()` 会在跑的过程中把 step 改成 72/50/36、function 改成 NONE；**不能拿 `getNextConnectNode()` 的返回值当 `Node[]` 下标**（那是连接表偏移，只有恰好是第一个连接时才相等）。
  **(3) 修掉两个数据 bug（都是"把注释掉的代码当生效"）**：
  ① **`map.c` 里 `N13→N18→B5 = 60` 是被 `//` 注释掉的**，而分析脚本把它当生效条目，导致上一轮"拟合分析"的**全部数字偏差**：生效 22→**21** 条、停车转组合 241→**207**、Tier2 可算 53→**39**、闸门挡回 3→**2** 条、反解 `L` 范围 11.0~35.1→**11.0~24.4**、A 类相关性 +0.685→**+0.713**、"判据+夹角" LOO-MAE 8.04→**6.95**。脚本已加"剥注释后判断命中位置"的解析，两份报告已按修正值改写并加勘误说明，**方向性结论不变**。
  ② **`project_reference.md §9.2` 的节点编号表是旧版本、对不上 `map.h`**：`enum MapNode` 里 **`C1`/`C2` 是注释状态**（注释掉的枚举成员不占编号），真实成员只有 **50** 个、`B11=49`（旧表写 53，`C4=33`/`P8=49` 也全错）。已按真实枚举重抄该表并注明"必须先剥注释再编号"。⚠️ `map.c` 里 `nav_init(..., 54)` 与 `if (nownode >= 54)` 的 54 是**宽松上界**，不是节点个数。
  **(4) 校验**：新增 `scripts/analyze/analyze_turn_comp_probe.py` —— 从 `map.c` **逐字抽取** `kTurnTbl[]` 与 `GetForwardDistanceBeforeTurn()`，**断言抽取结果与原函数仅差 5 处已声明替换 + 1 处表扫描展开，且可逆还原逐字一致**，再用 `arm-none-eabi-gcc -std=c99 -Wall -Wextra -O0 -c` 编译 19 个用例调用 → **保真性 + 语法 PASS**。
  ⚠️ **本机无主机 C 编译器 / WSL 无发行版 / `arm-none-eabi-gdb` 无 `target sim`**，无法在 PC 上执行 ARM 代码做运行期断言；数值正确性靠 python 侧同式独立计算，**最终判据仍是实车**。
  **(5) 脚本同步**：`analyze_turn_comp_base.py` 的解析器改为**同时认 `kTurnTbl[]`（新）与 if 链（旧/陀螺转）** —— 本轮改表结构后它一度失效（还在找 if 链）。**以后改表结构记得同步它。**
  ⚠️ **实车待确认**：① `N10→N9→B9` 48→48.4、`N8→N3→N4` 30→30.6、`N20→C4→B11` 25→25.9、`N3→N4→B2` 30→29.6（这几条公式与实测差 ≤5cm、已切到公式，差异都很小）；② `C4→N20→P8`(35) 与 `N4→N3→N8`(20) 被闸门挡回、**保持实测值不变**；③ 33 个原本吃默认 19 的组合现在有了计算值（最大 48.7）。

- **2026-09-12（续：修 `L6200E: arrive_method multiply defined`）**：Keil 链接报 **`Symbol arrive_method multiply defined (by ArriveDetect_task.o and map.o)`**。
  **(1) 根因（我的错）**：我在 **两个** `.c` 里都写了 `volatile uint8_t arrive_method = ARRIVE_NONE;`（`Task/ArriveDetect_task.c` 与 `Navigation/map.c`）——头文件里是 `extern`、但 `.c` 里写成了**定义**，于是出现两个强符号。**`map.c` 里那行已删掉**，并在原处留注释说明"本文件只读、不要在此定义"。
  **(2) 顺带修掉我自己引入的第二个错误**：为了给 `kTurnTbl[]` 加编译期护栏，我写了 `NAV_NODE_COUNT` —— **这个宏在工程里根本不存在**（是我臆造的）。已改成显式 `#define MAP_NODE_LIMIT 50`（= `map.h` 里 `enum MapNode` 的真实成员数）+ 一段 `typedef char kTurnTbl_node_check[...]`，把表里 19 个节点号全断言在界内。**以后增删节点要同步这个常量与 `nav_init` 的节点数。**
  **(3) 新增 `scripts/analyze/analyze_turn_comp_selfcheck.py`**：不依赖 Keil 的静态自检，逐条查最容易出错的 7 类问题 —— ① `arrive_method` 必须**恰好 1 处定义**（就是这次的 L6200E）② 声明可见性（`map.h` 的 extern / `map.h`→`config.h` / `map.c`→`math.h` / 两个 `.c` 都 include `map.h`）③ 判据枚举 11 个齐全 + `deal_arrive` 三参原型/定义同步 ④ `deal_arrive` 的 **10 处 `return 1` 各自都写了命中判据**、且未命中复位 `ARRIVE_NONE` ⑤ `kTurnTbl` 13 行且节点号全部 < 50、`MAP_NODE_LIMIT` 与真实节点数一致 ⑥ 不引用不存在的符号 ⑦ `cosf`（不是 `cos`）、Tier2 用 `Node_lookup(last)` 而非 `getNextConnectNode` 当下标、Tier2 不读会被 `door_set_pass_node()` 改写的 `nodes.nowNode.step/function`。
      **实测：全部通过 ✓**（写这个脚本时我自己先误报过 3 次 —— 计数把复位语句算进去、用不存在的宏名、以及"剥注释前就做字符串匹配"把警示语本身当成违规；都已修正）。
  **(4) 换行符**：本工程的 `.c/.h` 工作树是 **CRLF**（`core.autocrlf=true`，无 `.gitattributes`），而我的编辑工具把 `Navigation/map.h` 整文件转成了 LF ⇒ `git diff` 会把**全文**报成改动。已把 `map.h` / `scripts/README.md` / `analyze_turn_comp_base.py` 统一回 **CRLF**。⚠️ **以后再编辑这些文件，注意别把 CRLF 弄丢**（否则 diff 没法读）。

  > 📌 **教训**：① 同一轮里既改头文件又改实现时，**先 grep 一遍新符号的"定义点数量"**再交给用户编译（`selfcheck.py` 第 1 节就是干这个的）；② 别凭记忆写宏名 —— `NAV_NODE_COUNT` 这种"看起来应该有"的宏**必须先确认存在**。

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

- **2026-09-13（编辑器：修「线索路线」显示 ≠ 实车路线 —— 成本表漏改 + 线索选项不够，**本轮未改固件**）**：
  用户反馈"显示路线时有点问题""线索填的选项不够多，应该是填每一个灯的情况，还有宝藏线索也没填"。核查后确认**两个都是真问题**：

  (1) **根因：`map_model.OBS` 与固件 `Navigation/nav_planner.c` 的 `NavObsPenalty[]` 不一致**。表上的注释写着"与 `nav_planner.c` 对齐"，实际只对了 4 项（`DOOR=60`/`UpStage=60`/`UpStageHome=60`/`BLBS=70`），其余 10 项**全被写成 0**，`BLBL` 还写成 70（固件是 50）。于是编辑器把**桥、山、楼梯、景点、后退桩、南极、跷跷板、高山、刀山**全当**免费**，规划器拿它们当捷径 ⇒ **显示的路线和车上跑的不是一条**。已逐项按固件重写，并在表上写明"漏改过"的教训。
  (2) **`plan_route()` 支持运行时边禁用**（`blocked=` 参数）：镜像 `nav_set_edge_blocked()`，被禁边既不作起点也不参与松弛。这是复现固件"门回程封门区"的前提，之前编辑器**完全没有**这个概念。
  (3) **「线索路线…」对话框重做**。原来只有 4 行：P1 线索 / 平台 A-B 线索 / **"红绿灯/门入口"（只有一个入口节点下拉）** / 回家复选框 —— **没有每盏灯、没有宝物**。现在：
      - **每盏门灯 D2/D3/D4/D5 各一格**（绿 `CAN_PASS` / 蓝 `ONE_WAY_PASS` / 黑 `NO_PASS`）；
      - **宝物线索**（P1~P6 / 未定）；
      - 四个**阶段**各逐条镜像固件一条代码路径：`update_route_at_P1()`（手写数组，非规划器）/ `update_route_at_door_for_stageAB()` + `plan_treasure_return()` / `route_return_home()`（门区 8 边全禁，door_2 额外放行 `N8→N3`）/ `get_newroute()`；
      - 过门落在 `N12` 还是 `N8` 由 D2 能否通过推出（镜像 `door()` 把 `door_set_pass_node()` 的返回值赋给 `nodes.nowNode`）；
      - 固件在这些输入下会 `CarBrake_Stop()` 的组合（D2/D3/D4 全黑、宝物未定等）**直接弹提示**，不再硬凑一条路线出来。
      - 计算与界面分离：镜像函数在 `map_model.py` 模块级（`p1_route` / `stageab_waypoints` / `stageab_enter_node` / `treasure_return_waypoints` / `door_return_home_waypoints` / `round2_waypoints`），UI 侧纯计算入口是 `map_editor._clue_route_sections()`（**无 Tk**）—— 这样冒烟测试才覆盖得到。
  (4) **`_selftest.py` 加两道护栏**：第 8 节解析固件源码，把 `NavObsPenalty[]` 与 `OBS` **自动逐项比对**（以后再单边改动会立刻失败）；第 9 节**直接 import `scripts/validate/_check_door_perm.py` 的 12 条 golden**（单一真值来源），用编辑器的规划器 + 边禁用复现 → **12/12**。
  (5) **`_selftest.py` 不再硬编码 54 节点 / 124 边**：地图精简（54→50 节点、124→109 边）后它已经挂了 5 项。改为从源码推导，并加"边端点必须在 enum 里""节点名不重复""`nav_init` 节点数 ≥ enum 节点数"等检查；编辑操作一节的距离也改成相对基准。
  (6) 验证：`_selftest` **exit 0**；`_guismoke` 从 84 → **92 项全过**（新增"门区回程 door_2/宝物P4 命中 golden""D2/D3/D4 全黑 → 提示停车""第二轮 宝物=P6 逆时针""D2 绿 → 过门落在 N12""「线索路线…」对话框能构建"）；真实 `layouts/*.json` SHA256 未变。

  **顺带查出 3 件事（前两件在 `_selftest` 里提示；**未改任何路线/门逻辑**）**：
  - ✅ **已修（2026-09-13 续）**：`Navigation/map_message.c` 的 `NavEdgeTbl_size_check` 曾**重复两遍**（地图精简时误加；HEAD 只有一遍）。C99 下是约束违规，GCC/armcc 只在 `-pedantic` 时告警、**仍能编过**。已删掉后面那一份 → `_selftest` 第 1 节该项由 WARN 变 **OK**；并用 `arm-none-eabi-gcc -fsyntax-only -std=c99 / -std=gnu11 -Wall -Wextra`（配一个只含 `SPEED*` 的桩 `chassis_api.h`，绕开 RVDS `portmacro.h` 的 `__asm{}`）实测 **0 error 0 warning**，`-pedantic` 也干净。这同时证明**编译期行数断言真的生效**（`sizeof(NavEdgeTbl)/sizeof(NavEdge) == NAV_EDGE_COUNT`，109 == 109）—— 以后改边表漏改计数会直接编译报错。
  - ⏳ **待办**：`Navigation/map.c` 仍写死 `nav_init(NavEdgeTbl, NAV_EDGE_COUNT, 54)`、`getNextConnectNode()` 的越界判断也还写着 `54`，而 `enum MapNode` 现在只有 **50** 个节点。多出的节点出度为 0，**当前无害**，但增删节点时别忘同步。
  - ⏳ **待办**：当前地图（**50 节点 / 109 边**）**改完还没编译过**：最后一次 Keil 构建产物是 `MDK-ARM/build/test1/test1.htm`（2026-09-12 23:05），而 `Navigation/map_message.c` 是 2026-09-13 19:22 改的。上真车前请先按 §5 跑 7 个 `validate` 脚本 + Keil V5.32 编译 0 error。（`scripts/validate/` 的 6 个脚本本轮实测**全部 exit 0**。）

- **2026-09-13（续：编辑器「线索路线」补上 `door()` 内部的路线 —— 门区才是看不懂的地方，**本轮未改固件**）**：
  用户反馈"路线显示**主要是在门那里**还有问题；有些在 `door` 里的路线也显示一下"。核查后确认这是**真遗漏**：`barrier.c:door()` 里有三处**不改 `NavEdgeTbl[]` 却直接改 `route[]` / `nodes.nowNode`** 的动作，编辑器一个都没显示：
  - ① **`door_retreat()` 隐式改 `nodes.nowNode`**：D2 黑退到 `N5→N8`（`DOOR_RETREAT_N5N8`）、D3 黑退到 `N5→N4`（`DOOR_RETREAT_N5N4`）、D5 黑退到 `N10→N8`（`DOOR_RETREAT_N10N8`）、D4 回程黑退到 `N8→N5`（`DOOR_RETREAT_N8N5`）；
  - ② **D3 黑**：`load_route_at(0, door1route)` ⇒ `route[] = {N3, N8}`（车由 `N5→N4→N3→N8` 去撞 D4 读灯）；
  - ③ **D5 黑 + D2 蓝**：`route[0]=N3; route[1]=0xFF`（退回 N8 重读 D4）。
  ⇒ "门区路线对不上"的结论，很多是把这三处漏算了。

  **改动**：
  (1) `map_model.py` 新增两个纯镜像函数：`door_read_flow(doors)`（进门读灯推进 D2→D3→D4，含退回去向与 `door1route`）与 `door_back_flow(doors)`（回家过门的 `DOOR_D5_BACK`/`DOOR_D4_BACK` 分支）。⚠️ 注意两个 BACK 分支的 `else` 是**"非绿"**（黑和蓝都走），不是只有黑。
  (2) 「线索路线…」新增阶段 **「第一轮·门区全流程（door() 状态机 + 门里的手写路线）」**：列出读灯推进 + 三处手写路线 + 四个 `DOOR_RETREAT_*` 实测距离，再自动接上 `stageAB` 与宝物回程；「过门」阶段也前置了读灯推进，「门区回程」阶段前置了对应的回家分支。退距从 `Mission/config.h` 宏实时求值（按当前 `USE_FIELD`）。
  (3) **补回重写时弄丢的告警**：新报告函数 `_fmt_planned()` 现在也会报 **"经过 DOOR 边 ⇒ `door()` 会先 `map.point=0`、`route[0]=0xFF` 再重写路线"** 与 **180° 原路折返**（旧版 `show_route_text()` 有，我上一轮重写时漏了）。
  (4) 顺带查出一个**潜在死循环**：`DOOR_D5_BACK` 在 D5 非绿时**只处理**「D2=蓝」或「D2=黑且 D3=蓝」两种组合；其它组合既不置 `cross_event` 也不改 `route[]` ⇒ `Navigation()` 会重跑同一段并**再次触发 `door()`，可能反复重读这扇门**。（本轮只把它作为提示显示出来，**未改固件**；是否需要加兜底请实车确认后再定。）
  验证：`_guismoke` 从 92 → **96 项全过**（新增"D3 黑的 `door1route` 被显示""D5黑+D2蓝 的 `route[0]=N3` 被显示""D5 无匹配分支隐患被提示""经过 DOOR 边会告警"）；`_selftest` exit 0。

- **2026-09-13（续 2：编辑器加「第一轮·完整路线」+ 画布 去程/回程 分色，**本轮未改固件**）**：
  用户："怎么没有显示第一轮的完整路线，你几段拼在一起，过去和回程颜色分开"。

  (1) **新增阶段「第一轮·完整路线（去程+门区+东区+回程 自动拼接，画布分色）」并设为默认**。拼接点全部取自固件的**真实交接点**（不是猜的）：
      ① `mapInit()` 把 `nowNode` 置成 `P2→N2`，之后 `route[] = nav_build_route({N2,P1,N5})`；P1 平台里 `update_route_at_P1()` 用手写数组**整条覆盖** `route[]`，而其**前 4 跳与 `mapInit` 完全相同** ⇒ 完整路线 = `P2 → N2 → 手写数组`；
      ② 三个手写数组一律以 `N12` 结尾（在 `N5→N12` 上读 D2）⇒ 门区从 `N12` 接着走；
      ③ `update_route_at_door_for_stageAB()` 的 `wp[0]` 就是过门落点 ⇒ 自然接上；
      ④ 到第二个平台(P7/P8)读宝物 ⇒ `plan_treasure_return()` 的 `wp[0]` 就是该平台，**回程从这里开始**；
      ⑤ 回程若穿过 **BACK 门**（`N10→N3` / `N8→N3`），`door()` 会再调 `route_return_home()` 覆盖一次 ⇒ 再拼一段。
  (2) **`map_model.door_read_hops(doors)`**：门区退回重读用**边表里真实存在的边**串起来（`N12→N8`；`N12→N8→N5→N4→N3→N8`），所以拼出来的路线**每一跳都有边**、能直接画。
  (3) **`map_model.door_back_chain(doors, door_edge)`**：镜像回程撞 BACK 门后的分支链，含"D5 非绿 + D2 蓝 ⇒ `route[0]=N3`、退回 N8、再由 `N8→N3` 重读 D4"这条两级链，以及"无匹配分支"的告警。
  (4) **画布分色**：`App.route_split`（回程起始下标）+ `_draw_route()` 双色（去程 `#1e88e5` 蓝 / 回程 `#00897b` 青绿，交接点单独套一圈，路线包围盒左上角给图例）。⚠️ `route_split` 在**所有设置 `self.route` 的地方**都复位（普通规划/常规路线/清路线/换布局），否则会误分色。
  (5) **实测样例**：P1 线索=3、门灯 `D2黑 / D3黑 / D4蓝 / D5绿`、宝物=P4、`A=5,B=7` ⇒ 完整路线 **56 跳**，回程起点 = `P7`（下标 32），**每一跳都是真实边**，回程在 `N10→N3` 处按 `door_1` 正确重规划。
  验证：`_guismoke` 从 96 → **103 项全过**（新增"完整路线能拼出来""回程起点=第二个平台""每一跳都是真实边""BACK 门重规划段出现""画布确实同时画出两种颜色""普通规划会清掉 `route_split`"）；`_selftest` exit 0。

- **2026-09-13（续 3：编辑器鼠标手势改右键连线 + 查清"上位机地图 ≠ 固件地图"，**本轮未改固件**）**：
  用户："那个启用连线的改为右键吧，左键老是误差"。改的过程中**顺带查出一个更重要的问题**。

  (1) **鼠标手势**：原来"**左键双击节点** = 以它为起点开始连线"，点不中就会变成选中/拖动/框选。现改为：
      - **右键点节点 = 开始连线**；再右键另一个节点即成边（左键点目标也行）；再右键自己 / 点空白 / `Esc` = 取消起点；
      - **节点右键菜单挪到 `Shift+右键`**（重命名/删除/补反向边/设为必经点等功能一个没少）；
      - 左键双击节点保留为**备用**方式；`Shift+左键拖出` 不动；右键连线**不会**顺手勾上「连线模式」（否则会改掉左键行为）；
      - 取点逻辑统一到 `_connect_pick()`，左右键、双击、`A` 键、工具栏按钮全走同一套。
  (2) **⚠️ 重大发现：`layouts/default.json` 会盖掉固件地图。** 布局文件里**连边表一起存**，而 `App.__init__` 启动会自动载入它 —— 于是存在两份地图且**布局优先**，界面上显示的路线/校验/导出的 C 代码都可能基于布局而非 `NavEdgeTbl[]`。
      实测当时那份 `default.json`（2026-09-13 20:30 存）：**51 节点 / 109 边**，比固件**多 `C10`、少 `C9↔P7` 与 `B7↔C6`** —— 与 `_selftest.py` 第 7 节那个"**演示改动**"逐字一致（切 `C9-P7`/`B7-C6`、加 `C10`、连 `C6↔C10`/`C10↔C9`），说明是演示改动被在界面里做出来并存了盘。
      这是"**上位机算的路线和车上跑的不一样**"的又一个大来源（前一个是 `OBS` 成本表漏改）。
      **护栏**：新增 `App._source_diff_items()`，把当前模型与 `M.MapModel.load_from_sources()` 逐项比对（多/缺的节点与边），不一致时**状态栏**（启动即提示）与**「校验」面板**都告警；点「重新载入源码」可回到固件版且不丢拖好的位置。
  (3) **`_guismoke.py` 改为确定性**：它以前会跟着用户存的布局跑（所以本轮一开始出现"画布边 item 数 106 == 模型边数 109"失败、以及 `C9→P7` 取不到边而崩）。现在创建 App 后**强制 `load_from_sources()`**（保留拖好的坐标）再断言，结果不再依赖用户数据。
  验证：`_guismoke` 从 103 → **112 项全过**（新增 7 条右键连线断言 + 1 条"已固定在固件源码地图上"）；`_selftest` exit 0；启动状态栏实测输出
  `⚠ 已自动载入布局，但它与固件源码不一致（＋1节点 / －0节点 / ＋4边 / －4边）`。
  ⚠️ **待你决定**：那份 `default.json` 是留作试验（改名另存）、还是点「重新载入源码」后覆盖回固件版 —— 本轮**没有动它**（是你的数据）。

- **2026-09-13（续 4：修「新建边角度算错 90°」—— 图上几何角 ≠ 边表 angle 约定，**本轮未改固件**）**：
  用户："新建的 C9→C10 本来应该是 0 或者 180（完全水平），但软件检测到是 88 度"。核查后确认是**真 bug**。

  (1) **根因**：`create_edge_quick()` 直接用图上裸几何 `atan2(dx, −dy)` 当 `angle` 写进边表。
      但节点图坐标是**示意图**，边表 `angle` 是**另一套约定**（**水平 = 0/180、竖直 = ±90**；
      见 `C9↔P7 = 180/0`、`C8↔C7 = 0/180`、`C9↔N22 = −90/90`）。两套正好差 90°。
      实测（固件地图 109 条边，`表 angle − 图上几何角`）：**52 条为 +90°、31 条为 −90°**
      （后者是同一根直线但**方向感相反**），其余是示意图本身不准的边 —— 所以"看图算方向"天生有歧义。
      用户的 `C9→C10` 几何是 **89.81°**（确实几乎水平），于是被写成 88/90° 而不是 180°。
  (2) **同一个 bug 还有第二处**：属性面板「**辅助 → 按图上位置算角度**」（`calc_angle_geo()`）也是裸几何角。
  (3) **修复**：新增 `App._auto_edge_angle(frm, to)`，两处共用，按优先级：
      ① **共线锚定** —— 起点 `frm` 已有出边与新边几乎共线（≤ `ANGLE_ANCHOR_TOL` 8°）⇒ **沿用它的 `angle`**（地图自己的方向约定，最可靠，能自动解决上面的 ±90 歧义）；
      ② 否则 **图上几何 + `DRAG_ANGLE_OFFSET`(90°)**（与「跟随角度表」同一套）；
      ③ 再把接近 `0/±90/180` 的值**吸附成整数**（`ANGLE_SNAP_TOL` 5°）。
      实测：`C9→C10` ⇒ **180°**、反向 **0°**；`C9→N22` 同方向的竖直边 ⇒ 沿用 **−90°**；水平/竖直/共线/按钮四条路径都验过。
  (4) 状态栏会说明角度是怎么来的（"沿用共线边 C9→P7 的 180°" / "图上 +89.8° +90° 偏移 → 吸附为 180°"），方便判断。
  验证：`_guismoke` 从 112 → **119 项全过**（新增 7 条角度断言）；`_selftest` exit 0。

- **2026-09-13（续 5：修「画布上的『图 xx.xcm』随缩放变化」+ `calc_step_geo` 硬编码 K，**本轮未改固件**）**：
  用户："点显示边长，那个『图多少cm』会随着我缩放改动"。核查后确认是**真 bug**。

  (1) **根因**：`_draw_edges()` 里 `seg = hypot(x2-x1, y2-y1)`，而端点来自 `_edge_endpoints()` → `w2s()`，
      是**屏幕像素**；再 `seg / K` 当 cm。因为 `屏px = 世界px × scale`，所以**放大几倍、cm 就大几倍**。
      修：新增 `App._world_len_cm(e)`（用**图坐标**算 `hypot(Δx, Δy) / K`），画布标签改用它。
      实测 `C9→P7`：缩放 0.8 → `图 327.1cm`；放大 3 倍（scale 2.4）→ 仍是 **`图 327.1cm`**（以前会变 3 倍）。
      对照：`_geometry_warning_data()`（几何报警表）与 `solve_drag_position()`（拖动浮层）本来就是世界坐标，**没这个 bug**。
  (2) **顺带查出**：属性面板「辅助 → **按图上位置算 step**」（`calc_step_geo()`）**硬编码 `÷0.884`**，
      忽略了工具栏里可改的「单位长 K」⇒ 同一个 K 下"标签显示的值"和"写进边表的 `step`"会不一致。
      改为 `÷ self._unit_k()`，按钮文字与状态栏也改成 `px÷K`。
  (3) ⚠️ 保留的**有意**缩放相关行为：标签的显示阈值（`seg >= 46` 屏幕 px）本来就是"屏幕上有没有地方放字"的
      防重叠规则，缩小到一定程度标签会隐藏 —— 这是刻意的，**不是**数值变化。
  验证：`_guismoke` 从 119 → **121 项全过**（新增"放大 3 倍后标签一字不变""标签值 = 图坐标距离 ÷ K"）；
  `_selftest` / `_check_door_perm` / `_weight_calib` 全 exit 0。

- **2026-09-13（续 6：「线索路线…」记住上次填的配置，**本轮未改固件**）**：
  用户："那个生成路线的线索也保留上一次的吧，要不然每次点开都要重新配"。

  (1) **内存记忆**：新增 `App.clue_route_cfg`，对话框打开时按它预填、点「显示路线」时写回 —— 同一会话内反复打开就是上次那套。
  (2) **持久化**：随「保存布局」写进布局 JSON 的 `constraints.clue_route`（和 `snap_mode`/`unit_px_per_cm`/`edge_view` 同一套机制），启动自动载入布局时一起恢复 ⇒ **重启后也还在**。
      存的键：`stage` / `p1clue` / `stg` / `doors[4]` / `treasure` / `back`，**一律按显示字符串存**。
  (3) **安全回退**：读回时逐个做**成员校验**（`_pick()`），配置里有非法/过期值（换了版本、手改了 JSON）就用默认值，**不会崩也不会填出非法选项**。
  (4) 对话框底部加了一行灰字说明"这些选择会记住 / 随保存布局一起存"。
  验证：`_guismoke` 从 121 → **126 项全过**（新增"按上次配置预填 9 个下拉""非法配置回退默认""带 clue_route 的布局能存沙箱""constraints.clue_route 写进 JSON""载入后配置恢复"）；
  `_selftest` / `_check_door_perm` / `_weight_calib` / `_check_csr` 全 exit 0。

  > ⚠️ **注意**：这条依赖「保存布局」才跨重启生效。你那份 `default.json` 目前还没有 `clue_route` 键，
  > 第一次用对话框后**按一次 Ctrl+S**（保存布局）就会写进去。

- **2026-09-13（续 7：查"D2蓝D5绿 回程绕 N10→N8→N3" —— 结论不是仿真 bug；顺带修「写回固件」重复 size_check）**：

  (1) **回程门区的疑问：仿真没问题。** 用**两个独立镜像**交叉验证（编辑器规划器 vs
      `scripts/validate/_weight_calib.py`，后者是仓库自己的 golden 工具，`OBS_PENALTY` 与固件逐项一致），
      在**固件地图**和**你存的那份布局地图**上各跑一遍：
      `D2=蓝 / D3=黑 / D4=黑 / D5=绿`、宝物 P2/P4/P6、6 个阶段全都扫过 ⇒ **回程一律是 `N10 → N3`**，
      两边**逐跳完全一致**，**没有任何一处出现 `N10 → N8`**。
      ⇒ 这个组合下固件 `get_newroute()` 的 wp 只放 `N10`（`d2==ONE_WAY && d5==CAN_PASS` 分支，N3 视为冗余），
      规划器从 N10 到 P2 的最省路就是 `N10→N3→N4→…→P2`（`N10→N3` 85cm+门惩罚60 明显便宜于 `N10→N8` 170cm）。
      **会走 `N10→N8→N3` 的是另一组灯**：`D2=蓝 + D3=绿 + D4=绿 + D5=黑`
      （固件 wp 那里**明写 N8**：`d2==ONE_WAY && d5==NO_PASS && d4==CAN_PASS ⇒ wp[n++]=N8`，
      即"D5 不能过、走 D4（N8→N3）回家"）；`D2=绿 D3=绿 D4=绿 D5=绿` 则会出现 `N10→N8→N5`。
      这两条现在都写成了 `_guismoke` 的断言（131 项里），以后不用再怀疑。
  (2) **顺带查出一个真 bug：「写回固件」每次都多写一份 `NavEdgeTbl_size_check`。**
      `export_edge_table(with_header=False)` 的输出**自带尾部**（`};` + 编译期检查 typedef + "已移至"注释），
      而原文件在 `};` 之后本来就有那一段 —— `_patch_edge_table()` 却把整块拼进去 ⇒ 重复。
      **证据链**：写回前备份（21:04:30）`size_check=1` → 写回后（21:04:31）`size_check=2`。
      修复：抽出纯函数 `App._splice_edge_table(src, block)`，**只取到表体收尾的 `};`**，尾部沿用原文件；
      并把固件里多出来的那份删掉。实测 `arm-none-eabi-gcc -std=c99 -pedantic -Wall -Wextra` **0 error 0 warning**
      （同时验证编译期行数断言 `111 == NAV_EDGE_COUNT` 成立）。
  (3) **⚠️ 固件源码在 21:04:31 已被「写回固件」改成含 `C10` 的新拓扑：51 节点 / 111 边**
      （`C9↔P7`、`B7↔C6` 已删，`C10↔C6`/`C10↔C9` 已加）。因此
      `scripts/validate/_weight_calib.py`（**11/15**）与 `_check_csr.py`（**exit 1**）**挂了** ——
      原因不是地图错，而是这两个脚本里的**参考路线表（`REF` / `route()`）还是按旧拓扑写的**，
      仍在引用 `C9↔P7`、`B7↔C6`。**上真车前必须先把它们的参考路线更新到新拓扑**，
      否则"7 个校验脚本全过"这条门槛不成立。其余 4 个（`_check_wp` / `_check_door_logic` /
      `_check_door_perm` / `_check_map_debug`）**全 exit 0**。
  (4) 测试脚本去掉硬编码（地图真会变）：`_selftest`/`_guismoke` 不再假定 `C9↔P7` 存在、不再用 `C10` 当临时名
      （它已进地图）、演示改动改成"挑一条现成双向边中间插点"。
  验证：`_guismoke` 126 → **131 项全过**、`_selftest` **exit 0**、四个文件 `py_compile` 干净。

- **2026-09-13（续 8：修「选边老是选到同一条，另一条点不开」—— 双向边两个方向分不开，**本轮未改固件**）**：
  用户："选线的时候有点难选，老是选到一条线上，另一条线点不开"。核查确认**两个原因**：

  (1) **画布上两个方向的线分不开**：双向边只做 `off=4px` 垂直偏移（两条线相隔 8px），
      而命中区宽 `EDGE_HIT_WIDTH=14px` ⇒ 两条带子**重叠 6px**；Tk 取"最上层 item"，
      而 `_draw_edges()` 按边表顺序画 ⇒ **永远命中表里靠后的那个方向**。
      修：偏移 4 → **6px**（两条线相隔 **12px**，看得清也点得开）。
  (2) **`_edge_near()` 根本区分不了方向**：它算的是**未偏移的中心线**，而双向边几何上是同一条线段
      ⇒ 两个方向距离完全相同，`<` 比较让它**永远返回表里靠前那条**（双击编辑也中招）。
      修：新增 `App._edges_near(sx, sy, tol)` —— **自己列出候选**（用带偏移的画线算距离，按距离+字典序稳定排序），
      `_edge_near()` 改为取它最近的一条。
  (3) **新增"同一处再点一次 = 切换方向"**：`_on_edge_press()` 若发现当前选中项也在候选里，
      就切到下一条；状态栏提示"同一处共 N 条，再点一次继续切换"。
      用 **0.35s / 3px** 判定双击，避免双击编辑时被当成切换；`_on_edge_double()` 尊重已选中的那条。
      **合并双向的边列表行**同样支持：再点同一行在正/反方向间切换。
  实测：偏向哪侧就选到哪条（`N3→S1` / `S1→N3`），同处连点三次循环 `N3→S1 → S1→N3 → N3→S1`。
  验证：`_guismoke` 131 → **135 项全过**（新增"双向边两侧各能选到一条""同处再点切换方向""状态栏提示"）；
  `_selftest` exit 0。

- **2026-09-13（续 9：新增「平台快速交换」—— function 随平台切换，长度/角度全沿用，**本轮未改固件**）**：
  用户："我想加一个平台快速交换的功能，function 函数随平台切换，其他沿用原来的，比如 P5 和 P7 切换，
  那 C9 连的就是 P5，长度还是原来的长度，但是 function 变成 stage"。

  (1) **模型层**：新增 `MapModel.swap_platforms(a, b, swap_xy=False, dry_run=False)` 与
      `MapModel.node_io_roles(name)`。语义严格按用户要求：
      - **只改 `from`/`to`**（名字互换）：`step`（长度）/`angle`/`flag`/`speed` **一个都不动**；
      - 每条相关边的 `func` 换成"**新名字那个平台**"的入口/出口动作 ⇒ **function 随平台切换**；
      - **入口/出口动作从当前地图读**（`node_io_roles()` 优先取 `func != NONE` 的那条进/出边），
        **不硬编码**"P5=UpStage"这种表 —— 地图改了也不会失效；
      - `swap_xy` 才连坐标一起换（默认不动 = "其他沿用原来的"）；
      - 两个平台之间**有直接边就拒绝**（那条边算谁的说不清），同名/不存在也拒绝（抛 `ValueError`）；
      - `dry_run=True` 只返回变更说明、不改模型（给对话框做预览）。
      实测 `P5⇄P7`（当前地图 P7 连的是 `B7`）：`B7→P7(10,BSoutPole)` ⇒ **`B7→P5(10,UpStage)`**
      —— 长度不变、function 变成 Stage，正是用户说的那个效果；`N13→P5(80,UpStage)` ⇒ `N13→P7(80,BSoutPole)`。
  (2) **界面**：左侧新增「**平台快速交换**」区 → 对话框选两个平台（P1~P8）+ 「连坐标一起换」勾选框 +
      **实时改动预览**（逐条列出"改名 …⇒…"和"func …→…（谁的动作）"）+ 交换/取消。
      改完状态栏提醒 **⚠ 请复核 `mission_planner.c` 的 wp / 门逻辑 / 宝物表**（它们按平台名走）。
      只改内存模型，可 `Ctrl+Z` 撤销；**要「写回固件」才动源码**。
  (3) 记忆上次换的两个平台（会话内），和「线索路线」对话框一致的体验。
  验证：`_guismoke` 135 → **143 项全过**（新增"dry_run 不改模型""step 沿用原值""func 随平台切换"
      "节点/边数不变且没造出直连边""restore 能完整撤回""对话框能构建"）；`_selftest` exit 0。

  > 📌 注：用户举例里的 `C9→P7` 是**旧拓扑**（C10 写回前）；当前地图里 P7 连的是 `B7`。
  > 功能语义不受影响，换的始终是"节点名字 + 随之而来的 func"。

- **2026-09-13（续 10：修「平台交换按钮看不见」—— 我上一轮把它加错容器了，**本轮未改固件**）**：
  用户："左侧添加在哪呢，我怎么没看到"。

  **我上一轮的错**：那段 UI 被加进了 `_build_prop_widgets()`（即**右栏「属性」面板**，`f = self.prop`），
  而不是左栏 —— 那个面板**每次改选中都会 `destroy` 全部子控件再重建**，所以按钮位置既不对、又会被反复重建。
  根因是我按"`ttk.Button(g, text="整条边取反…")`"这个锚点插入，而它属于属性面板。
  **修正 + 又踩了一个坑**：
  (1) 先挪到左栏 `_build_left` 的 `top`（总览，边表下面）→ **仍然看不见**：`pack` 的空间**按打包顺序**
      分配，那个父容器已被两个 `expand=True` 的 `Treeview` 占满，后加的整块 frame
      `winfo_ismapped()` 为 **False**（实测 h=1、w=1）。
  (2) 最终挂到左栏「**边显示: [合并双向 ▾]**」**那一行的右边**（顺序靠前、一定有位置），
      实测按钮 87×27、`mapped=True`。
  (3) 也试过放工具栏第 1 行，但该行宽度变成 **1254px > minsize 1200** ⇒ 最小窗口下右侧控件会跑到屏幕外，
      **撤掉了**（并在代码里留注释说明为什么不能加）。
  (4) **加了两道护栏**：① `_guismoke` 现在有一条断言检查入口按钮 **`winfo_ismapped()`**（这种"加到
      pack 满的容器里"的 bug 以前测不出来）；② 工具栏行宽断言从"按当前窗口宽"改成**按 `minsize` 宽（1200）**判
      —— 原来按实际窗口宽判（测试窗口 1711）根本抓不到 1254 的溢出。
  验证：`_guismoke` 143 → **144 项全过**（新增"入口在界面上真的可见"）；`_selftest` exit 0。

- **2026-09-13（续 11：`NavObsPenalty[Hill]` 300 → 230 —— "N8→C9 走楼梯、N12→N20 不走"，**本轮改了固件权重**）**：
  用户："从 N8 到 P5 实测应该走 N12 再走楼梯更近" → "**N8 到 C9 要走楼梯，但是 N12 到 N20 不要**"
  → "不要加必经点"。所以只能调**成本模型**（`func` 不能改：`map_function()` 里 `LBHill` 没有 case，改了车就不爬坡）。

  (1) **先确认不是我镜像的 bug**：用规划器**自身返回路径**的成本核算（不是手写路径），
      `Hill=238` 时走楼梯 1825 < 走南环 1827、`239` 时反过来 ⇒ 规划器每步都取最小，镜像没问题。
      （我中途手算过一次"交叉在 158"，是因为我手写的楼梯路径走了 `N8→N5→N12` 两跳、不是最优变体；
      规划器走 `N8→N12` 直连一跳。教训：**核成本必须用规划器自己的输出**。）
  (2) **关键发现：各起终点对的翻转阈值不一样**（用户正式图 `layouts/57交换.json`，全 2450 对）：

      | 起终点 | 翻成"走楼梯"的阈值 |
      |---|---|
      | **N8→C9** / N8→P5 | Hill ≤ **239** |
      | **N12→N20** | Hill ≤ **200** |
      | N12→P8 | Hill ≤ **247** |

      ⇒ 取 **230** 落在 (200, 239) 窗口内 ⇒ 用户要的两条**同时成立**；且固件 15 条参考路线仍 **15/15**
      （`rout_58` 要到 ≤200 才断；之前还实测过 [220,238] 全区间都 15/15）。
  (3) **改了三处（必须同步）**：`Navigation/nav_planner.c: NavObsPenalty[4]`、本工具 `map_model.OBS["Hill"]`、
      `scripts/validate/_weight_calib.py: OBS_PENALTY[4]`；并把两处旧注释
      「安全窗240~340 / 离翻南环临界240有60余量」改写成新的事实 —— 那句注释说的正是 **239** 这个翻转点，
      300 是作者当年为"让 N12→P8 走南环"故意留的 60 余量。
  (4) **代价（必须实车复核）**：全 2450 对里 **61 对（2.5%）** 改走楼梯侧，集中在楼梯走廊
      （N8/N12/N16/N18/B5/N19/C6/B7/N22/C9/P5）+ `P1→B3/P8`、`B1/B3→C9/N22/P5`、`N12→P8` 等。
      ⚠️ **现有 golden 覆盖不到这 61 对**（参考路线只有那 15 条）⇒ 属"数据对了但业务未验证"。
  (5) 验证：`arm-none-eabi-gcc -fsyntax-only -std=c99 -Wall -Wextra nav_planner.c` **0 error 0 warning**；
      `_selftest` 第 8 节「OBS 与固件逐项一致（19 项，不符 0 项）」+ exit 0；
      `_guismoke` **144/0**；`scripts/validate/` 六个脚本**全 exit 0**（`_weight_calib` **15/15**）。
