# -*- coding: utf-8 -*-
"""同步 project_reference.md 与交接文档（都只写"现在是什么样"）。"""
import os, sys

BASE = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao/项目讲解文档"

PR = os.path.join(BASE, "project_reference.md")
HD = os.path.join(BASE, "交接专用文档（新人先看我）.md")


def load(p):
    raw = open(p, "rb").read()
    crlf = raw.count(b"\r\n"); lf = raw.count(b"\n") - crlf
    EOL = "\r\n" if crlf >= lf else "\n"
    return raw.decode("utf-8").split(EOL), EOL, crlf, lf


def save(p, lines, EOL):
    open(p, "wb").write(EOL.join(lines).encode("utf-8"))


# ===================== project_reference.md =====================
lines, EOL, crlf, lf = load(PR)
print("PR EOL CRLF=%d LF=%d  lines=%d" % (crlf, lf, len(lines)))

def find_one(pred, what):
    hit = [i for i, s in enumerate(lines) if pred(s)]
    assert len(hit) == 1, (what, len(hit))
    return hit[0]

# --- 1) 开关表 UPRIGHT_TOUR_ENABLE 行：改写 + 后面补 P3P4_PUNCH_ENABLE 行 ---
i = find_one(lambda s: s.startswith("| `UPRIGHT_TOUR_ENABLE` | `0` |"), "tour row")
lines[i] = (
    "| `UPRIGHT_TOUR_ENABLE` | `0` | 直立景点**巡回**（只管走位）开关，**默认关**：`1`=一轮取宝**之后**"
    "绕「**这次会去的** `P3`/`P4`」对应的景点（会去 `P3`→`S1`、会去 `P4`→`S2`；取宝之前一次都不去）、"
    "二轮 `P3`/`P4` 之后固定两个都绕（+806cm）。"
    "⚠️ **2026-10-07 起判据跟着 `P3`/`P4` 走**（不再要求「宝物就在 `P3`/`P4`」）："
    "补打卡 `P3P4_PUNCH_ENABLE` 开着 ⇒ 两个景点都绕；关掉 ⇒ 退回旧行为（宝物 `P3`→`S1`、`P4`→`S2`）。"
    "落点 = `mission_planner.c` 的共享小函数 `append_round1_return_tail()`（一轮，被 `plan_treasure_return` / "
    "`route_return_home` **各调一次**）+ `get_newroute()`（二轮）；一轮顺序与二轮一致，**交错成 "
    "`P3`→`S1`→`P4`→`S2`**。⚠️ `S1`/`S2` 的 `func` 是 **`View1`**、`map_function()` 无 `case` "
    "⇒ **只走位、不做动作不播报**（要得分需另写 `do_Upright1()`）。见 [README.md](README.md) §2.19 |")
lines.insert(i + 1,
    "| `P3P4_PUNCH_ENABLE` | `0` | 一轮**取宝之后**的回家腿把去程没去的 `P3`/`P4` **补打卡**"
    "（**缺哪个补哪个**：QR 百位=3 补 `P4` / =4 补 `P3` / =0 两个都补；宝物平台本身不重复加）；"
    "与 `S1`/`S2` **共用** `append_round1_return_tail()`，顺序**交错**（`P3`→`S1`→`P4`→`S2`）。"
    "⚠️ 宝物平台**必须排最前**（取宝前去任何平台 = 走错即结束）⇒ 宝物=P4 时实际 `P4`→`P3`→`S1`→`S2`。"
    "⚠️ 打开会改门回程 ⇒ **真实固件走法不再等于** `validate/_check_door_perm.py` 的 12 条 golden"
    "（那条脚本**不读开关、恒 12/12**，看不出本开关）。见 [README.md](README.md) §2.21 |")

# --- 2) 9.4 必经点原则的"唯一例外"段 ---
i = find_one(lambda s: s.startswith("**唯一例外**：直立景点巡回打开时"), "9.4 except")
lines[i] = (
    "**唯一例外**：直立景点巡回打开时（`UPRIGHT_TOUR_ENABLE=1`）会额外把 `S1`/`S2` 写进 `wp` —— "
    "它们是**死胡同支路**（`N3`/`N6` 岔口往返），")

# --- 3) 改码落点索引表 巡回 行 ---
i = find_one(lambda s: s.startswith("| **直立景点巡回（`S1`/`S2`）** |"), "落点索引 tour")
lines[i] = (
    "| **直立景点巡回（`S1`/`S2`）** + **一轮补打卡 `P3`/`P4`** | 开关 `UPRIGHT_TOUR_ENABLE` / "
    "`P3P4_PUNCH_ENABLE`（`config.h`）；**一轮两处已合并进共享小函数 "
    "`append_round1_return_tail(wp, n)`**（`plan_treasure_return()` / `route_return_home()` 各调一次），"
    "二轮在 `get_newroute()` 的 `P3`/`P4` 之后；顺序**交错成 `P3`→`S1`→`P4`→`S2`**，"
    "且**必须整体在宝物平台之后**（取宝前去 = 结束比赛）；`S1`/`S2` 的判据 =「会去 `P3`/`P4`」"
    "（`treasure == 3/4` **或** 补打卡开着且百位没走过）；⚠️ `wp` 已扩容（`route_return_home` 8 点、"
    "`plan_treasure_return` 10 点），别改回；⚠️ `S1`/`S2` 的 `func` 是 `View1` 且**无 `case`** "
    "⇒ 只走位、不得分；⚠️ `S1 = 0` 会撞 `Nav_IsStraightThrough()` 的 0 号哨兵 | "
    "README §2.19 §2.21 |")

save(PR, lines, EOL)
print("PR 已写盘")

# ===================== 交接文档 =====================
lines, EOL, crlf, lf = load(HD)
print("HD EOL CRLF=%d LF=%d  lines=%d" % (crlf, lf, len(lines)))

def find_one2(pred, what):
    hit = [i for i, s in enumerate(lines) if pred(s)]
    assert len(hit) == 1, (what, len(hit))
    return hit[0]

# --- 1) L434-437 四行块 ---
i = find_one2(lambda s: s.startswith("⚠️ **「要不要绕 S1/S2」是另一个独立开关**"), "HD 434")
assert lines[i + 1].startswith("置 `1` 时一轮取宝**之后**按宝物平台绕近的那个"), lines[i + 1]
assert lines[i + 2].startswith("二轮 `P3`/`P4` 之后固定两个都绕"), lines[i + 2]
assert lines[i + 3].startswith("⇒ 车开过去**不做动作、不播报**"), lines[i + 3]
lines[i:i + 4] = [
    "⚠️ **「要不要绕 S1/S2」是另一个独立开关** `UPRIGHT_TOUR_ENABLE`（`Mission/config.h`，**当前 `1` = 绕**）；",
    "**「回程要不要补打卡 P3/P4」又是另一个** `P3P4_PUNCH_ENABLE`（同文件，**当前 `1` = 补**）。两者**共用同一段**：",
    "`mission_planner.c` 的 `append_round1_return_tail()`（一轮 `plan_treasure_return()` / `route_return_home()` 各调一次），",
    "顺序**交错成 `P3`→`S1`→`P4`→`S2`**，整体排在**宝物平台之后**（取宝之前走到 = 规则上直接结束比赛）。",
    "",
    "`S1`/`S2` 的判据（**2026-10-07 改**）是「**这次回程会不会去 `P3`/`P4`**」：会去 `P3`→绕 `S1`、会去 `P4`→绕 `S2`；",
    "所以补打卡开着时**两个景点都绕**（3/4 都去），关掉补打卡则退回旧行为（宝物 `P3`→`S1`、`P4`→`S2`）。",
    "二轮 `P3`/`P4` 之后固定两个都绕（里程 +806cm）。它只改**走位**：`S1`/`S2` 的 `func` 是 `View1`、`map_function()` 里没有 `case View1`",
    "⇒ 车开过去**不做动作、不播报**，得分动作尚缺（要另写 `do_Upright1()`）。详见 [README.md](README.md) §2.19 / §2.21。",
]

# --- 2) L422 的括注 ---
j = find_one2(lambda s: "`S1`/`S2` 由 `UPRIGHT_TOUR_ENABLE` 决定是否经过（默认不经过）" in s, "HD 422")
lines[j] = lines[j].replace(
    "`S1`/`S2` 由 `UPRIGHT_TOUR_ENABLE` 决定是否经过（默认不经过）",
    "`S1`/`S2` 由 `UPRIGHT_TOUR_ENABLE` 决定是否经过（判据 =「这次回程会不会去 `P3`/`P4`」，见 §2.19）")

# --- 3) L427 ---
k = find_one2(lambda s: s.startswith("`S1`/`S2` 只在 `UPRIGHT_TOUR_ENABLE=1` 时才进 `wp`"), "HD 427")
lines[k] = ("`S1`/`S2` 只在 `UPRIGHT_TOUR_ENABLE=1` 时才进 `wp`（**当前 config.h 里是 1**），"
            "**用 S1/S2 前先确认动作由谁做**（见 [README.md](README.md) §2.19）。")

save(HD, lines, EOL)
print("HD 已写盘")
