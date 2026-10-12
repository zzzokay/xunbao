# -*- coding: utf-8 -*-
"""上位机侧文档同步：tools/README.md、map_editor/README.md、map_editor/AI_CONTEXT.md（均 LF）。"""
import os, sys

ROOT = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao"
BASE = os.path.join(ROOT, "地图修改上位机")

# ---------------- tools/README.md ----------------
P1 = os.path.join(BASE, "tools", "README.md")
E1 = [
 ("sim_route_bookkeeping 自检描述",
  "**开机先读 `Mission/config.h` 的 `UPRIGHT_TOUR_ENABLE` / `P3P4_PUNCH_ENABLE` 并对 `mission_planner.c` 自检**"
  "（`S` 三处 + `P3`/`P4` 两处插点 / 两个开关取值 / `wp` 容量），对不上就报「镜像已过期」并 exit 1；"
  "另校验红线「`S1`/`S2` 不得排在宝物平台之前」，并打印「补打卡」开关下的门回程 wp 对比表",
  "**开机先读 `Mission/config.h` 的 `UPRIGHT_TOUR_ENABLE` / `P3P4_PUNCH_ENABLE` 并对 `mission_planner.c` 自检**"
  "（2026-10-16 重写：一轮交错段必须集中在 `append_round1_return_tail()` + 两个回程函数各调一次 + 插点顺序 "
  "`P3->S1->P4->S2` + `S` 插点必须与 `UPRIGHT_TOUR_ENABLE` 同行 + 一轮 `P3`/`P4` 必须与 `goP3`/`goP4`（或宝物平台行）"
  "同行 + `wp` 容量；二轮 `S` 两处插点），对不上就报「镜像已过期」并 exit 1；"
  "另校验红线「`S1`/`S2` 不得排在宝物平台之前」，并打印「补打卡」开关下的门回程 wp 对比表（巡回置开以显示交错）"),
 ("sim_upright_tour 描述",
  "直立景点巡回（`S1`/`S2`）路线验证：镜像 `mission_planner.c` 三处插点，算 `UPRIGHT_TOUR_ENABLE=0/1` "
  "两种状态的 `route[]` —— 关态无 `S`（回归基线）、开态 `S` 在 `P3`/`P4` 之后且在宝物平台之后、"
  "去掉 `S` 支路后与关态逐跳一致（5700 项）。**二轮巡游顺序读 `config.h` 的 `ROUND2_CRUISE_*`**（不抄死值）",
  "直立景点巡回（`S1`/`S2`）路线验证：镜像 `mission_planner.c` 三处插点，算 `UPRIGHT_TOUR_ENABLE` × "
  "`P3P4_PUNCH_ENABLE` 各状态的 `route[]` —— 关态无 `S`（回归基线）；**punch=0 时旧行为不变**；"
  "**punch=1 时 `S` 跟着「会去 P3/P4」走**（会去 P3→S1、会去 P4→S2；宝物不在 P3/P4 也绕），"
  "且交错成 `P3 -> S1 -> P4 -> S2`、`S` 在宝物平台之后、去掉 `S` 支路后与关态逐跳一致。"
  "**自带源同步自检**（交错段是否仍在 `append_round1_return_tail()` / 两处调用 / 插点顺序）；"
  "**二轮巡游顺序读 `config.h` 的 `ROUND2_CRUISE_*`**（不抄死值）。"
  "⚠️ `[1] 二轮` 一段当前 `0/315`（镜像连 `N12 -> P5` 都走不通）属**既有**权重/边表 WIP，与 `S` 插点无关"),
]
# ---------------- map_editor/README.md ----------------
P2 = os.path.join(BASE, "map_editor", "README.md")
E2 = [
 ("左栏下 巡回说明",
  "  「直立景点巡回」在「二轮路线…」对话框里也有（二轮固定 P3 后绕 S1、P4 后绕 S2）。",
  "  「直立景点巡回」在「二轮路线…」对话框里也有（二轮固定 P3 后绕 S1、P4 后绕 S2）。\n"
  "  ⚠️ 一轮那两处的巡回到 `S1`/`S2` 的**判据 2026-10-16 改了**：不再要求「宝物就在 P3/P4」，\n"
  "  而是跟着「这次回程会不会去 P3/P4」走（补打卡开着 ⇒ 两个景点都绕），顺序与二轮一致，\n"
  "  交错成 `P3 -> S1 -> P4 -> S2`。详见 `项目讲解文档/README.md` §2.19 / §2.21。"),
]
# ---------------- map_editor/AI_CONTEXT.md ----------------
P3 = os.path.join(BASE, "map_editor", "AI_CONTEXT.md")
E3 = [
 ("AI_CONTEXT punch 行",
  "固件 `config.h` 的 `P3P4_PUNCH_ENABLE` + `mission_planner.c` **两处**插点（`plan_treasure_return` / `route_return_home`）；"
  "镜像 `M.p3p4_punch_waypoints(treasure, line_clue)` + `treasure_return_waypoints(..., line_clue, punch)` / "
  "`door_return_home_waypoints(..., line_clue, punch)`；",
  "固件 `config.h` 的 `P3P4_PUNCH_ENABLE` + `mission_planner.c` 的共享小函数 `append_round1_return_tail(wp, n)`"
  "（被 `plan_treasure_return` / `route_return_home` **各调一次**）；"
  "镜像 `M.p3p4_punch_waypoints(treasure, line_clue)` + `M.round1_return_extra_waypoints(treasure, line_clue, punch, tour)` + "
  "`treasure_return_waypoints(..., line_clue, punch, tour)` / `door_return_home_waypoints(..., line_clue, punch, tour)`；"),
 ("AI_CONTEXT punch golden 注",
  "打开会改门回程路线 ⇒ `validate/_check_door_perm.py` 的 12 golden 只在开关**关**时成立。",
  "打开会改门回程路线 ⇒ 真实固件走法不再等于 `validate/_check_door_perm.py` 的 12 golden"
  "（那条脚本不读开关、恒 12/12，看不出本开关）。"),
 ("AI_CONTEXT tour 行 1",
  "固件 `config.h` 的 `UPRIGHT_TOUR_ENABLE` + `mission_planner.c` **三处**（`plan_treasure_return` / `route_return_home` / `get_newroute`）；"
  "镜像 `M.upright_tour_waypoints(treasure)` + `treasure_return_waypoints` / `door_return_home_waypoints` / `round2_waypoints` 的 `tour` 参数；",
  "固件 `config.h` 的 `UPRIGHT_TOUR_ENABLE` + `mission_planner.c` 三处（一轮两处走共享小函数 `append_round1_return_tail()` + 二轮 `get_newroute()`）；"
  "镜像 `M.upright_tour_waypoints(treasure, line_clue=None, punch=False)`（语义 =「会绕哪些景点」）+ "
  "`M.round1_return_extra_waypoints(...)`（一轮交错段）+ `treasure_return_waypoints` / `door_return_home_waypoints` / `round2_waypoints` 的 `tour` 参数；"),
 ("AI_CONTEXT tour 行 2",
  "**一轮只用宝物判据**（P3→S1、P4→S2），**二轮固定两个都绕**；落点都在宝物平台 / 补打卡**之后**、`P2` 之前（两开关同开时顺序 = 平台 → 补打卡 → 巡回）。",
  "**一轮判据（2026-10-16 改）跟着「这次回程会不会去 P3/P4」走**（会去 P3→S1、会去 P4→S2；补打卡开着 ⇒ 两个都绕，"
  "关掉 ⇒ 退回旧行为「宝物 P3→S1、P4→S2」），**二轮固定两个都绕**；落点都在宝物平台**之后**、`P2` 之前，"
  "交错成 **P3 → S1 → P4 → S2**（宝物平台那一次不重复加 ⇒ 宝物 = P4 时实际 `P4→P3→S1→S2`）。"),
 ("AI_CONTEXT tour 行 3",
  "改完跑 `_guismoke` 的「round-1/2: upright tour S1/S2」段 + `tools/sim_upright_tour.py`。",
  "改完跑 `_guismoke` 的「round-1/2: upright tour S1/S2」段 + `tools/sim_upright_tour.py`"
  "（自带源同步自检）+ `tools/sim_route_bookkeeping.py`。"),
]

grand_ok = True
for path, edits in ((P1, E1), (P2, E2), (P3, E3)):
    raw = open(path, "rb").read()
    crlf = raw.count(b"\r\n"); lf = raw.count(b"\n") - crlf
    EOL = "\r\n" if crlf >= lf else "\n"
    t = raw.decode("utf-8")
    print("== %s  (CRLF=%d LF-only=%d)" % (os.path.basename(path), crlf, lf))
    plan = []
    ok = True
    for name, old, new in edits:
        o = old.replace("\n", EOL)
        n = new.replace("\n", EOL)
        c = t.count(o)
        print("   %-28s count=%d" % (name, c))
        if c != 1:
            ok = False
        plan.append((o, n))
    if not ok:
        grand_ok = False
        print("   !! 命中异常，跳过本文件")
        continue
    for o, n in plan:
        t = t.replace(o, n, 1)
    open(path, "wb").write(t.encode("utf-8"))
    print("   已写盘")

sys.exit(0 if grand_ok else 1)
