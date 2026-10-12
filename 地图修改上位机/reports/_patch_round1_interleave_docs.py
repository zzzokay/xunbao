# -*- coding: utf-8 -*-
"""项目讲解文档/README.md：同步"一轮交错 + S1/S2 判据跟着 P3/P4 走"。

§2.19 / §2.21 改写 + §9 追加一行（append-only）。
"""
import os, sys

ROOT = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao"
PATH = os.path.join(ROOT, "项目讲解文档", "README.md")

raw = open(PATH, "rb").read()
crlf = raw.count(b"\r\n"); lf = raw.count(b"\n") - crlf
print("EOL: CRLF=%d LF-only=%d" % (crlf, lf))
EOL = "\r\n" if crlf >= lf else "\n"
text = raw.decode("utf-8")


def b(s):
    return s.replace("\n", EOL)


edits = []

# ---- §2.19 标题 ----
edits.append(("2.19 标题",
    b("19. **直立景点巡回（S1/S2）：开关默认关；「走位通道」和「得分动作」是两件事。**（09-26 新增）"),
    b("19. **直立景点巡回（S1/S2）：开关默认关；判据是「这次回程会不会去 P3/P4」；「走位通道」和「得分动作」是两件事。**（09-26 新增，2026-10-16 改判据）")))

# ---- §2.19 需求 ----
edits.append(("2.19 需求",
    b("""    - **需求**：一轮的「回家腿」（取宝**之后**）顺路绕近的那个景点（宝物在 `P3` 绕 `S1`、在 `P4` 绕 `S2`）；
      二轮去 `P3`/`P4` 时**固定两个都绕**。开关 `UPRIGHT_TOUR_ENABLE`（`Mission/config.h`，**默认 0 = 现状不变**）。"""),
    b("""    - **需求**：一轮的「回家腿」（取宝**之后**）绕**这次会去的 `P3`/`P4`** 对应的景点；二轮去 `P3`/`P4` 时**固定两个都绕**。
      开关 `UPRIGHT_TOUR_ENABLE`（`Mission/config.h`，**默认 0 = 现状不变**）。
      ⚠️ **2026-10-16 改判据**：原来只看宝物值（`treasure == 3` 绕 `S1`、`== 4` 绕 `S2`），
      现在改成看 **「这次回程会不会去 `P3`/`P4`」** —— 会去 `P3` ⇒ 绕 `S1`，会去 `P4` ⇒ 绕 `S2`。
      其中「会去 `P3`」= 宝物平台就是 `P3`，**或** 补打卡 `P3P4_PUNCH_ENABLE` 开着且 QR 百位没走过 `P3`（§2.21）。
      ⇒ 补打卡开着时**两个景点都绕**（3/4 都去）；补打卡关掉则**自动退回旧行为**（宝物 `P3`→`S1`、`P4`→`S2`）。
      改判据的原因：补打卡一开，回程本来就必去 3/4，再要求「宝物正好在 3/4」就白开了这个开关。""")))

# ---- §2.19 落点 ----
edits.append(("2.19 落点",
    b("""    - **落点三处**（都在 `Mission/mission_planner.c`）：`plan_treasure_return()` 的 `target` 之后、
      `route_return_home()` 的 `P3`/`P4` 之后、`get_newroute()` 的 `P3`/`P4` 之后。
      ⚠️ **必须插在宝物平台【之后】** —— 规则：一轮取宝前走到其他平台或直立景点 = **直接结束比赛**。"""),
    b("""    - **落点**（都在 `Mission/mission_planner.c`）：一轮那两处（`plan_treasure_return()`、`route_return_home()`）
      **已合并进共享小函数 `append_round1_return_tail(wp, n)`** —— 它按 **`P3 -> S1 -> P4 -> S2` 交错**写点，
      两个回程函数各调一次（2026-10-16 起；之前是「先 `P3/P4` 再 `S1/S2`」两段独立的 if 块）；二轮那处在
      `get_newroute()` 的 `P3`/`P4` 之后（本来就是交错的写法）。
      ⚠️ **必须整体排在宝物平台【之后】** —— 规则：一轮取宝前走到其他平台或直立景点 = **直接结束比赛**。
      ⇒ 交错段里「宝物平台正好是 `P3`/`P4`」的那一次**不重复加**（平台已在更前面写过）：宝物 = P4 时实际是
      `P4 -> P3 -> S1 -> S2`（`P4` 是平台本身，先取宝；`P3`/`S1` 是一轮补的；`S2` 因为「会去 P4」而绕）。""")))

# ---- §2.19 坑② ----
edits.append(("2.19 坑②",
    b("""    - ⚠️ **坑②：`route_return_home()` 的 `u8 wp[3]` 会溢出**（nowNode + 平台 + S + `P2` = 4 个点）⇒ 已扩成 `wp[6]`，别再改回去。"""),
    b("""    - ⚠️ **坑②：`route_return_home()` 的 `u8 wp[3]` 会溢出** ⇒ 已扩成 `wp[8]`（交错后最坏
      nowNode + 平台 + `P3` + `S1` + `P4` + `S2` + `P2` = **7** 个点），别再改回去；
      `plan_treasure_return()` 的 `wp[10]` 同理（最坏 **9** 个点）。""")))

# ---- §2.19 护栏② ----
edits.append(("2.19 护栏②",
    b("""      ② 判据只用 `treasure == 3 / 4`，**不要自造 `treasure != 0`**（`treasure` 读线索时就有值，那时宝还在平台上）；"""),
    b("""      ② 判据（2026-10-16 起）=「会去 `P3`/`P4`」：`treasure == 3/4` **或**（补打卡开着 && `flag_line_clue != 3/4` && `treasure != 3/4`），
      **不要自造 `treasure != 0`**（`treasure` 读线索时就有值，那时宝还在平台上）；""")))

# ---- §2.19 上位机 ----
edits.append(("2.19 上位机",
    b("""    - **上位机（地图修改上位机）也镜像了这个开关**（2026-10-07 补）：`map_model.upright_tour_waypoints()` +
      `treasure_return_waypoints()` / `door_return_home_waypoints()` / `round2_waypoints()` 的 `tour` 参数；"""),
    b("""    - **上位机（地图修改上位机）也镜像了这个开关**（2026-10-07 补）：`map_model.upright_tour_waypoints()`
      （2026-10-16 起签名 `(treasure, line_clue=None, punch=False)`，语义 =「这次回程会绕哪些景点」）+
      一轮那两处统一走 `map_model.round1_return_extra_waypoints(treasure, line_clue, punch, tour)`
      （镜像 `append_round1_return_tail()`，交错 `P3 -> S1 -> P4 -> S2`）+
      `treasure_return_waypoints()` / `door_return_home_waypoints()` / `round2_waypoints()` 的 `tour` 参数；""")))

# ---- §2.21 落点 ----
edits.append(("2.21 落点",
    b("""    - **落点**：`mission_planner.c` **两处** —— `plan_treasure_return()`（P7/P8 读到宝物后的回程腿）与
      `route_return_home()`（过门回程）；位置都在**宝物平台之后、`S1/S2`（`UPRIGHT_TOUR_ENABLE`）之前**，顺序固定 `P3 -> P4`；
      `route_return_home()` 的 `wp[6] -> wp[8]`（最坏 nowNode + 宝物平台 + P3 + P4 + S + P2 = 6 个点）。
      ⚠️ **两处都得插**：回程过门时 `door()` 会重规划后半段，与本函数各管一段（同 §2.19）。"""),
    b("""    - **落点**：`mission_planner.c` 的共享小函数 `append_round1_return_tail(wp, n)`，被两个回程函数各调一次 ——
      `plan_treasure_return()`（P7/P8 读到宝物后的回程腿）与 `route_return_home()`（过门回程）；
      位置在**宝物平台之后、`P2` 之前**，与 `S1/S2` **交错**成 `P3 -> S1 -> P4 -> S2`
      （2026-10-16 起；原来顺序固定 `P3 -> P4`、排在 `S1/S2` 之前）。
      `route_return_home()` 的 `wp[6] -> wp[8]`（最坏 **7** 个点）；`plan_treasure_return()` 的 `wp[10]`（最坏 **9** 个点）。
      ⚠️ **两处都得调**：回程过门时 `door()` 会重规划后半段，与本函数各管一段（同 §2.19）。""")))

# ---- §2.21 平台必须最前 ----
edits.append(("2.21 平台最前",
    b("""    - ⚠️ **`P3 -> P4` 只是「补打卡内部」的顺序**：宝物平台**必须排在最前**（取宝之前去任何平台 = 走错即结束比赛）
      ⇒ 宝物 = P4 时实际走法是 `P4 -> P3`（先取宝、再补 P3），不是 `P3 -> P4`。"""),
    b("""    - ⚠️ **宝物平台必须排在最前**（取宝之前去任何平台 = 走错即结束比赛）⇒ 宝物 = P4 时实际走法是
      `P4 -> P3 -> S1 -> S2`：先取宝，`P3`/`S1` 是一轮补打卡 + 巡回，`S2` 因为「会去 P4」而绕
      （交错段里「宝物平台那一次」被跳过，所以不会出现两个 `P4`）。""")))

# ---- §2.21 上位机 ----
edits.append(("2.21 上位机",
    b("""    - **上位机镜像**：`map_model.p3p4_punch_waypoints(treasure, line_clue)` +
      `treasure_return_waypoints()/door_return_home_waypoints()` 的 `line_clue`/`punch` 参数；"""),
    b("""    - **上位机镜像**：`map_model.p3p4_punch_waypoints(treasure, line_clue)` +
      一轮两处统一走 `map_model.round1_return_extra_waypoints(treasure, line_clue, punch, tour)`（交错段）+
      `treasure_return_waypoints()/door_return_home_waypoints()` 的 `line_clue`/`punch` 参数；""")))

# ---- §2.21 仿真 ----
edits.append(("2.21 仿真",
    b("""    - **仿真**：`tools/sim_route_bookkeeping.py` 的源同步自检已扩到本开关（两处插点 / 二轮不该有 / `wp` 容量 ≥ 6），
      启动时打印开关取值 + 一张「门回程 wp 对比表」（关 → 开）。"""),
    b("""    - **仿真**：`tools/sim_route_bookkeeping.py` 的源同步自检（2026-10-16 重写）现在校验
      「交错段集中在 `append_round1_return_tail()` + 两个回程函数各调一次 + 插点顺序 `P3->S1->P4->S2`
      + `S` 插点必须与 `UPRIGHT_TOUR_ENABLE` 同行 + 一轮 `P3/P4` 必须与 `goP3/goP4`（或宝物平台行）同行 + `wp` 容量」；
      启动时打印开关取值 + 一张「门回程 wp 对比表」（补打卡关 → 开，巡回开关置开以显示交错）。""")))

# ---- §9 追加 ----
edits.append(("§9 追加",
    b("""`_guismoke` ⇒ **284 项（283 OK / 1 项既有 FAIL）**。"""),
    b("""`_guismoke` ⇒ **284 项（283 OK / 1 项既有 FAIL）**。
- **2026-10-16**：一轮回程改「交错 + S1/S2 判据跟着 P3/P4 走」【动固件 + 上位机 + 仿真 + 文档】—— 用户指出
「既然补打卡开关开着、回程必定把 3/4 跑完，就不该再要求『宝物在 P3/P4』才绕景点」。改法：
① `mission_planner.c` 抽出共享小函数 `append_round1_return_tail(wp, n)`，`plan_treasure_return()` 与
`route_return_home()` 各调一次；判据改成「会去 P3 = 宝物平台是 P3 或（补打卡开着 && 百位≠3 && 宝物≠3）」、
「会去 P4」同理，顺序 **`P3 -> S1 -> P4 -> S2`**（与二轮 `get_newroute()` 同序）；补打卡关掉时自动退回旧行为。
② `map_model.py`：`upright_tour_waypoints(treasure, line_clue=None, punch=False)` 语义改为「会绕哪些景点」，
新增 `round1_return_extra_waypoints()`（交错段），两个回程镜像函数改调它。
③ `tools/sim_route_bookkeeping.py`：镜像同步 + 源同步自检**重写**（旧的 ①③④⑤ 全部失效），
并把对比表改成「巡回开关置开」以显示交错。
④ `_guismoke` 断言更新（两开关同开时 = `P3 S1 P4 S2`）+ 新增「宝物=P1 也绕 S1/S2」「交错序列」+ **独立口径**
（直接读 `mission_planner.c` 文本确认共享小函数存在且两处都调用）。
验证：Keil 增量编译 **0 Error(s)**（日志确认重编 `mission_planner.c`，2 条警告来自 `barrier.h` 既有声明）；
`sim_route_bookkeeping` 源同步自检**通过**（「真实预设」那条 `Route_Error_Stop` 与旧版逐字一致 ⇒ 既有，
起因是仿真预设 `door_pass` 未读，非本次改动）；`_guismoke` **287 项（286 OK / 1 项既有 FAIL）**；
`_selftest` 1 项既有 FAIL（§13 路口标志位）；`validate/`：`_check_door_perm` **12/12**、
`_check_csr`/`_check_door_logic`/`_check_map_debug`/`_syntax_map_debug` 全过，
`_check_wp_east`（112 项）与 `_check_wp`（5 项）的失败**与改动前一致**（均不 import `map_model`、不读
`mission_planner.c`，属既有边表/权重 WIP）（§2.19 §2.21）""")))

ok = True
for name, old, new in edits:
    c = text.count(old)
    print("%-14s count=%d" % (name, c))
    if c != 1:
        ok = False
if not ok:
    print("!! 命中次数 != 1，未写盘")
    sys.exit(1)

for name, old, new in edits:
    text = text.replace(old, new, 1)

open(PATH, "wb").write(text.encode("utf-8"))
print("已写盘:", PATH)
