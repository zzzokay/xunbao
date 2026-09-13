# scripts/ — 工程辅助 Python 脚本

> **用途**：把所有 `.py` 辅助脚本从仓库根收拢至此，按用途分三类。**只读/校验，不进固件**；执行层固件（`Navigation/`、`Mission/`、`Application/`）不依赖它们，仅仓库根 `MDK-ARM/update_keil_project.py` 留在原处。
> **本地跑**：在**仓库根**执行，或按提示加路径；脚本内部已改为相对 `scripts/` 上一两级自动定位仓库根，换机器/换路径不用改。

---

## `map_editor/` — 地图图形化编辑器（改地图先看这个）⭐

> **一句话**：把 `Navigation/map_message.c` 的 `NavEdgeTbl[]` 画成可拖拽的图，改完直接导出 C 代码，
> 不用手抠 124 行边表。**只做辅助，不进固件**。
> 详见 **[map_editor/README.md](map_editor/README.md)**（给人：使用说明）
> 与 **[map_editor/AI_CONTEXT.md](map_editor/AI_CONTEXT.md)**（🤖 给 AI：架构/坐标系/不变量/安全规则/踩坑）。

```bash
python scripts/map_editor/map_editor.py    # 打开即当前固件地图；零依赖(tkinter 自带)
python scripts/map_editor/_selftest.py     # 自检：解析/往返一致/宏求值/导出/编辑/规划
python scripts/map_editor/_guismoke.py     # 界面冒烟测试（68 项；全程沙箱，不碰真实布局）
python scripts/map_editor/analyze_layout.py  # 只读分析你的布局（精度/单位长 K/角度一致性）
```

| 文件 | 作用 |
|------|------|
| `map_editor.py` | tkinter 界面：画布拖拽、节点/边增删改、点图形选边、连线模式、底图对齐、校验、路线规划、导出/写回 |
| `map_model.py` | 核心：解析 `enum MapNode` / `NavEdgeTbl[]` / `config.h` 宏；数据模型；校验；Dijkstra；C 代码导出 |
| `AI_CONTEXT.md` | 🤖 **给 AI 读的项目参考**（改了代码要让下一个 AI 知道的东西都在这） |
| `README.md` | 给人看的使用说明 |
| `_selftest.py` | 无界面自检（**含"不编辑则导出与源文件逐字段一致"的护栏**） |
| `_guismoke.py` | 界面冒烟测试（**绝不碰 `layouts/*.json`**，见 AI_CONTEXT §7） |
| `analyze_layout.py` / `analyze_unit_length.py` | 只读分析脚本 |
| `layouts/default.json` | 保存的布局，启动自动载入；`layouts/snapshots/` 是自动多版本快照 |
| `backups/` | 「写回固件」时自动生成的源码备份 |

**两条最重要的心智模型**：
1. **节点位置只是示意图** —— 图上远近**不代表**实际长度，长度只认 `step` 数值，
   所以**节点可以随便拖，不影响任何数值**；图的作用是表达"连接关系 + 角度关系"并贴合标准节点图。
2. **导出是逐字段保真的** —— 没编辑时导出的边表与源文件完全相同（`_selftest.py` 第 2 节，差异 0 处）。

---

## `validate/` — 上真车前必跑的校验

> ⚠️ **`pre-commit` 钩子当前是关闭状态**：文件在 `.git/hooks/pre-commit.disabled`（2026-09-11 核查时发现已被改名停用），所以**不会自动触发**，需手动跑下面 8 个脚本。要恢复自动触发：`mv .git/hooks/pre-commit.disabled .git/hooks/pre-commit`。

| 脚本 | 作用 | 什么时候跑 | exit |
|------|------|-----------|------|
| `_weight_calib.py` | 从 `map_message.c` 的 `NavEdgeTbl[]` 解析图；校验所有参考路线相邻节点皆有合法边；edge 状态(line-graph) Dijkstra 复现 仅长度/长度+转角/长度+转角+障碍 三种成本模型的路线。**基准回归工具**。 | 改边或权重后 | 0=全过 1=有差异 |
| `_check_csr.py` | 镜像 `nav_planner.c` 的 `nav_init()` 自动构建 CSR（`ConnectionNum/Address/Node[]`），验证 `getNextConnectNode` 能解析全部参考边 + 8 条门边。 | 增删边后 | 0=连通 1=缺边 |
| `_check_wp.py` | 镜像 `nav_plan_waypoints`，对若干必经点组合验证"删掉某个必经点不改路线"（`build_wp` 新旧两版路线一致）。 | 改 `wp` 必经点后 | 0=一致 1=不一致 |
| `_check_door_logic.py` | **门逻辑表驱动校验**（新增，重点排查门区问题）：① 所有 `DOOR` 功能边要么命中 `door()` 状态匹配表、要么在驱动前被 `Clear_door()` 清成 `NONE`（二者皆无才报缺口，避免把"回程边必先清 NONE"误判成 bug）；② 对 D2/D3/D4 每种颜色组合镜像 `plan_after_return_door` 生成回程路线，检查是否 `CarBrake_Stop`/断链；③ D4 回程黑灯退到 N5 后下一跳必须 `N4` 且转角 `need2turn(-145°,0°)=145°`。 | 改门逻辑后 | 0=通过 1=发现问题 |
| `_check_door_perm.py` | **门回程"边禁用 + 极简必经点"校验**：把改造前 `update_route_by_door_1~4` 的 12 条手写穷举路线当 golden，断言"门区 8 条边全禁 +（door_2 放行 `N8→N3`）+ `wp={当前节点,[宝物平台],P2}`"能逐字复现它们；另含 golden 连通性自检。 | 改门回程/门区边/权重后 | 0=12/12 复现 1=有差异 |
| `_check_map_debug.py` | **`MAP_DEBUG` 调试路线校验（起终点/途径点）**：**先按 `Mission/config.h` 的 `USE_FIELD` 覆盖长度宏**（修正"镜像固定 `FIELD_COMP` 而实际是 `FIELD_SCHOOL`"导致算错路线的问题，并打场次告警），再镜像 `map.c` 改造前(两点)/改造后(带途径点)两版逻辑，断言 `VIA_POINT=0` 时二者**逐字一致**（穷举 54×54=2916 组）、`VIA_POINT≠0` 时路线依次经过该点且相邻跳连通；最后打印**陀螺仪参考角/摆车方向 + 逐段航向/step/func + 每节点转弯量**，并对"**180° 原路折返**"和"**路线经过 DOOR 边**"告警。 | 改 `MAP_DEBUG` / 调试起终点 / `nav_plan_waypoints` / `USE_FIELD` 后 | 0=全过 1=有差异 |
| `_syntax_map_debug.py` | **`map.c` 的 MAP_DEBUG 代码块语法检查**：把该块**真实源码文本**抽出来，套进只 `#include "map.h"`+`nav_planner.h` 的探针 TU 跑 `arm-none-eabi-gcc -fsyntax-only -Wall -Wextra`。`map.c` 整体编不过 GCC（FreeRTOS RVDS `portmacro.h` 的 `__asm{}`），故按 project_reference.md §12 的探针办法只查这一块；临时探针文件用完即删。 | 改 `map.c` 的 MAP_DEBUG 块后 | 0=0 error（本机无 GCC 则跳过）1=有错 |
| `_check_wp_east.py` | **过门后（东区）必经点"精简 vs 全锚点"等价性回归**：① 二轮精简 wp（只留门节点 + `P5~P8`）与写全 N 锚点的旧 wp，在**全部可达门状态组合 × 宝物(6/非6)**（100 组）下逐字节对比；② 第一轮 `stageAB`：删环上中间 N 后路线必须**逐字节不变**，删尾部出口锚点 `C9/N20` 后**只允许少最后一个节点**——后者是"平台交接"成立的前提（该锚点原本给 `nodes.nextNode` 兜底，现改由 `plan_treasure_return()` 显式对齐到"出平台第一跳"；**只删不补交接 → 平台推进错位 → `Route_Error_Stop` 死停车**，状态机仿真 4/4 复现）。⚠️ 结论依赖当前权重模型，**动权重后必须重跑**。 | 改二轮 wp / 门状态分支 / `stageAB` / `plan_treasure_return()` / 权重后 | 0=等价 1=有差异 |

> `_check_csr.py` / `_check_wp.py` / `_check_wp_east.py` / `_check_door_logic.py` / `_check_door_perm.py` / `_check_map_debug.py` 都 `import _weight_calib`，**七个必须同目录**（现都在 `scripts/validate/`）。`_weight_calib` 的 `BASE` 已上溯两级指向仓库根，才会去读 `Navigation/map_message.c`；`_check_map_debug.py` 另外会读 `Mission/config.h` 的 `USE_FIELD`/`FIRST_POINT`/`VIA_POINT`/`END_POINT`，并调 `_weight_calib.sync_field_from_config()` 按真实场次覆盖长度宏（**其它脚本仍按 `_weight_calib` 顶部手写的 `FIELD_COMP` 跑，golden 不受影响**）。`_syntax_map_debug.py` 不依赖 `_weight_calib`。
>
> ⚠️ **`_weight_calib.py` 顶部的 `USE_FIELD` 是手写常量，默认 `FIELD_COMP`；`Mission/config.h` 切到 `FIELD_SCHOOL` 时它会与真实场地不同步**，凡是拿镜像**预测真实路线**的地方都要先 `sync_field_from_config()`（已踩过坑：`N3→P4` 在学校场地下选穿门 `N3→N8`、在比赛场地下选掉头 `N3→N4`，结论相反）。

## `analyze/` — 诊断/排查用（只读，非回归校验）

| 脚本 | 作用 | 备注 |
|------|------|------|
| `analyze_door_return_route.py` | **解析真实源码**复现 `nav_planner.c` 线路图 Dijkstra，回答过门 `N8→N5` 下一节点（=N4）与 N5 处转角为何≈180°；读取的是当前 `map.h`/`map_message.c`/`config.h`(学校场地)/`barrier.c`。**最可信、常维护**。 | 新增 |
| `analyze_weight_sensitivity.py` | **权重灵敏度**：把候选值注入镜像后跑 5 个校验脚本，回答"调 `NavObsPenalty[DOOR]` 或 `NAV_W_TURN` 会动哪些路线"。会同时给出两种场地、以及 `MAP_DEBUG` 调试 case 的选路结果（含"掉头/穿门"的成本差与金标是否被破坏）。**改权重前必跑**。 | 新增 |
| `analyze_door_weight_route_diff.py` | **门权重改动前后的路线穷举比对**（"改了会影响哪些路线"的**完整**答案）：① 按源码分支穷举固件里**所有** `nav_build_route/nav_plan_waypoints` 调用点（第一轮初始/门回程 `route_return_home`/`plan_treasure_return`/`update_route_at_door_for_stageAB`/第二轮 `get_newroute`）+ 三种**可达**边禁用状态；② `MAP_DEBUG` 的 FIRST×VIA×END 全枚举（≈14.6 万组合）。用"门惩罚只加不减 ⇒ 不含门边的路线数学上不可能变"做剪枝，只对含门边的组合实算。带分段缓存，整轮约 10s。 | 改 `NavObsPenalty[]` 任何一项后 |
| `analyze_turn_comp_base.py` | **转弯前硬补偿分析基础库 + 主报表**：解析 `map_message.c` 的 `NavEdgeTbl[]`、`map.h` 的 flag 位、`Mission/config.h` 的 `ANGLE_*`/`DOOR_LEN_*` 宏，再解析 `map.c` 的 `GetForwardDistanceBeforeTurn()`/`GetForwardDistanceBeforeGyroTurn()` 两张表；输出「生效 22 条 / 死值 7 条」清单、每条的真实转弯量、该入边启用的到达判据（按 `ArriveDetect_task.c` 的 if 链优先级）。**其余 5 个脚本都 `exec` 它做前置解析**。 | 改转弯补偿表/边表角度后 |
| `analyze_turn_comp_step_check.py` | **"step 太短导致里程提前放行"假设检验**：按入边 `step` 分档，验证 `step≤18cm` 时 `0.7×step + 补偿` 落在 17~38cm（正常检测起点量级）⇒ 那批补偿实际在补段长。含 A/B 类分组与组内相关性。 | 复核段长时 |
| `analyze_turn_comp_rule.py` | **"能算就算"判据验证**：按 R1(平地 `func∈{NONE,DOOR}`) / R2(`step≥20`) / R3(`100°≤|转弯|<178°`) 给 22 条打标，列出各自反解的 `L`，并统计边表全部 (入,出) 组合的命中率。 | 改判据阈值后 |
| `analyze_turn_comp_final_plan.py` | **三层覆盖率统计**：Tier1 实测保留 / Tier2 公式算出 / Tier3 保留默认 19，输出各层条数与明细。 | 定方案时 |
| `analyze_turn_comp_gate.py` | **★最终方案（含 5cm 闸门）验证**：Tier1 实测 / Tier2 `|公式−实测|≤5cm` 用公式 / Tier3 保留默认；输出 L 敏感性扫描、被闸门挡回的条目、**Tier2 完整清单（53 条）**与取值范围。**改方案参数后跑这个**。 | 改方案/`L`/阈值后 |
| `analyze_turn_comp_map_geom.py` | **从节点图反查几何**：内置 `节点图.jpg` 的节点像素坐标 + 5 条长直边标定比例（0.884 px/cm），算每条边的地图真实走向与表里 `angle` 的偏差，并输出"地图真实转弯量 vs 表转弯量"。结论：表里角度**是对的**（只差参考系旋转），但节点图是**示意图**、臂长与 `step` 大面积不符，**不能用来定量反推补偿**。⚠️ 本文件的节点名→编号映射是**旧版**，以 ⑦ probe 的解析为准。 | 需要对照地图几何时 |
| `analyze_turn_comp_probe.py` | **★改造保真性 + 语法校验**：从 `Navigation/map.c` **逐字抽取** `TURN_*` 宏、`kTurnTbl[]`、`GetForwardDistanceBeforeTurn()` 函数体，断言"仅差 5 处已声明替换 + 1 处表扫描展开，且**可逆还原后逐字一致**"（保证校验对象是真代码而非手抄副本），再用 `arm-none-eabi-gcc -std=c99 -Wall -Wextra -O0 -c` 编译 19 个用例调用；同时按 **C 的真实枚举规则**解析 `map.h`（先剥注释再编号，带 `N4/N8/P8/B11` 抽查断言）并打印 python 侧独立算出的期望值。**改 `map.c` 的补偿逻辑后跑这个。** | 改转弯补偿表/公式后 |
| `analyze_turn_comp_selfcheck.py` | **★不依赖 Keil 的静态自检**（7 节约 30 条断言）：① `arrive_method` 必须**恰好 1 处定义**（`L6200E multiply defined` 就是这么来的）② 声明可见性（extern / include 链）③ 判据枚举齐全 + `deal_arrive` 三参原型与定义同步 ④ `deal_arrive` 的 10 处 `return 1` 各自都写了命中判据、未命中复位 `ARRIVE_NONE` ⑤ `kTurnTbl` 行数与节点号上界、`MAP_NODE_LIMIT` 与真实节点数一致 ⑥ 不引用不存在的宏 ⑦ `cosf` / `Node_Lookup` / 不读会被 `door_set_pass_node()` 改写的 `nodes.nowNode.step`。**交给用户编译前先跑这个。** | 改这 5 个文件后 |
| `analyze_door_bug.py` | 早期打印式分析 D4 回程 `door_retreat` 后退+转向的冲突（文本输出，非解析源码）。 | 历史 |
| `analyze_n8_n5_turn.py` | 早期打印式逐步分解 `N8→N5→N4` 执行流程、查找 N5->N4 边角度。 | 历史 |
| `check_door_route_logic.py` | 早期打印式分析 `DOOR_D4_BACK` 与 `plan_after_return_door` 的分支可行性。 | 历史 |
| `check_route.py` | 早期打印当前 DEBUG 路线（`route[100]`）与 `GetForwardDistanceBeforeTurn` 中 `N8→N5→N4` 的前进距离。 | 使用了**过时/硬编码** NODE_MAP，仅参考 |
| `trace_d4_black.py` | 打印式完整推演 D4 黑灯(`DOOR_D4_BACK`)的路线生成逻辑。 | 历史，含硬编码节点映射 |

> ⚠️ `analyze/` 下除 `analyze_door_return_route.py` 外的几个为历史排查脚本，里面**节点编号映射可能过时/硬编码**（与当前 `map.h` 不一致时结论仅供参考）；改动前请以 `validate/` 的校验脚本 + 当前源码为准。

---

## 运行示例（在仓库根）

```bash
# 改地图：图形化编辑器（打开即当前固件地图）
python scripts/map_editor/map_editor.py
python scripts/map_editor/_selftest.py          # 编辑器自检（往返一致护栏）

# 上真车前必跑
python3 scripts/validate/_weight_calib.py
python3 scripts/validate/_check_csr.py
python3 scripts/validate/_check_wp.py
python3 scripts/validate/_check_door_logic.py
python3 scripts/validate/_check_door_perm.py
python3 scripts/validate/_check_map_debug.py
python3 scripts/validate/_syntax_map_debug.py

# 排查门区
python3 scripts/analyze/analyze_door_return_route.py

# 转弯前硬补偿：现状清单 / 方案验证
python3 scripts/analyze/analyze_turn_comp_base.py       # 生效22条 + 死值7条 + 每条命中判据
python3 scripts/analyze/analyze_turn_comp_gate.py       # ★最终方案：Tier2 53 条清单 + 5cm 闸门
python3 scripts/analyze/analyze_turn_comp_map_geom.py   # 节点图几何 vs 表里 angle
python3 scripts/analyze/analyze_turn_comp_probe.py      # ★保真性(可逆还原) + 语法编译校验
python3 scripts/analyze/analyze_turn_comp_selfcheck.py  # ★静态自检(定义点/可见性/枚举/节点上界)

# 改权重前：看会动哪些路线（灵敏度表 + 穷举 diff）
python3 scripts/analyze/analyze_weight_sensitivity.py
python3 scripts/analyze/analyze_door_weight_route_diff.py      # 门惩罚 0→60 会动哪些路线（默认）
```
