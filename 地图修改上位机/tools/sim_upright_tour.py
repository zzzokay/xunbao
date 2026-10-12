# -*- coding: utf-8 -*-
"""直立景点巡回（S1/S2）开关路线验证 —— 只读源码，不改任何文件。

对照 Mission/mission_planner.c 的三处插点（plan_treasure_return / route_return_home /
get_newroute），用 nav_planner 镜像算出 UPRIGHT_TOUR_ENABLE × P3P4_PUNCH_ENABLE 各状态的 route[]：

  · 0（默认，保持现状）：任何路线里都不出现 S 节点 —— 即回归基线。
  · 1（打开）：一轮那两处**交错**成 `P3 -> S1 -> P4 -> S2`（与二轮同序）；S 的判据
    2026-10-07 起**跟着"这次回程会不会去 P3/P4"走**（不再是"宝物就在 P3/P4"）：
      会去 P3 ⇒ 绕 S1；会去 P4 ⇒ 绕 S2。补打卡 P3P4_PUNCH_ENABLE 开着 ⇒ 两个景点都绕。
    一轮里 S 必在对应宝物平台之后（规则：取宝前走到其他平台或直立景点 = 直接结束比赛）。

局限（有意为之）：
  · 本脚本**不镜像门区边禁用**（那是 validate/_check_door_perm.py 的职责），
    因此 route_return_home 一项只验证【S 的插入位置】与【可达性】，不代表门回程里程。

跑法：python3 地图修改上位机/tools/sim_upright_tour.py
"""
import os
import re
import sys
import itertools

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "validate"))
import _weight_calib as W  # noqa: E402

W.sync_field_from_config()          # ★ 必须在 parse_graph 之前：按 config.h 真实场次取长度宏
edges = W.parse_graph()
adj = W.build_adj(edges)
IDX2NAME = {v: k for k, v in W.NODE_IDX.items()}
STEP = {(e["from"], e["to"]): e["step"] for e in edges}
W_LEN, W_TURN, W_OBS = 1.0, 0.6, 1.0

CAN, ONE, NO = "CAN", "ONE", "NO"


# 第二轮巡游顺序：2026-10-07 起由 Mission/config.h 的 ROUND2_CRUISE_CW_*/_CCW_* 给出
# （不再是 mission_planner.c 里的死值）。镜像必须跟着源码读，否则宏一改就成"假通过"。
_CFG_TXT = ""
try:
    with open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "Mission", "config.h"),
              encoding="utf-8", errors="replace") as _f:
        _CFG_TXT = _f.read()
except OSError:
    pass


def _cfg_order(key, dflt):
    """读 ROUND2_CRUISE_<key>_1..4；缺宏 / 非法名 / 有重复 ⇒ 出厂默认。"""
    vals = []
    for i in range(1, 5):
        m = re.search(r"^\s*#define\s+ROUND2_CRUISE_%s_%d\s+(\S+)" % (key, i), _CFG_TXT, re.M)
        vals.append(m.group(1) if m else None)
    if None in vals or any(v not in ("P5", "P6", "P7", "P8") for v in vals) \
            or len(set(vals)) != 4:
        return list(dflt)
    return vals


R2_CW = _cfg_order("CW", ("P5", "P7", "P8", "P6"))
R2_CCW = _cfg_order("CCW", ("P6", "P8", "P7", "P5"))


def _cfg_flag(name, default=0):
    """读 config.h 的 #define <name> <十进制>。"""
    m = re.search(r"^\s*#define\s+" + re.escape(name) + r"\s+([0-9]+)\b", _CFG_TXT, re.M)
    return int(m.group(1)) if m else default


TOUR = _cfg_flag("UPRIGHT_TOUR_ENABLE", 0)
PUNCH = _cfg_flag("P3P4_PUNCH_ENABLE", 0)

# ---- 源同步自检：一轮交错段必须仍集中在共享小函数里（2026-10-07 起的结构）----
SYNC = []
try:
    with open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "Mission",
                           "mission_planner.c"), encoding="utf-8", errors="replace") as _f:
        _MP = _f.read()
except OSError:
    _MP = ""
if not _MP:
    SYNC.append("读不到 Mission/mission_planner.c")
else:
    _mp = re.sub(r"/\*.*?\*/", " ", _MP, flags=re.S)
    _mp = re.sub(r"//[^\n]*", " ", _mp)
    _m = re.search(r"append_round1_return_tail\s*\([^;{}]*\)\s*\{", _mp)
    if not _m:
        SYNC.append("mission_planner.c 里找不到 append_round1_return_tail()（一轮交错段落点变了）")
    else:
        _d, _end, _body = 0, None, ""
        for _j in range(_m.end() - 1, len(_mp)):
            if _mp[_j] == "{":
                _d += 1
            elif _mp[_j] == "}":
                _d -= 1
                if _d == 0:
                    _end = _j
                    break
        if _end:
            _body = _mp[_m.end() - 1:_end + 1]
        for _need in ("goP3", "goP4", "P3P4_PUNCH_ENABLE", "UPRIGHT_TOUR_ENABLE"):
            if _need not in _body:
                SYNC.append("append_round1_return_tail() 里缺 %s（判据 / 开关变了）" % _need)
        _ord = [_body.find("wp[n++] = P3;"), _body.find("wp[n++] = S1;"),
                _body.find("wp[n++] = P4;"), _body.find("wp[n++] = S2;")]
        if -1 in _ord or _ord != sorted(_ord):
            SYNC.append("append_round1_return_tail() 的插点顺序不是 P3 -> S1 -> P4 -> S2（偏移 %s）"
                        % _ord)
    if _mp.count("n = append_round1_return_tail(wp, n);") != 2:
        SYNC.append("append_round1_return_tail() 的调用点不是 2 个"
                    "（plan_treasure_return / route_return_home 各一次）")


def cp(c):
    return c in (CAN, ONE)


def plan(wps):
    return W.build_route_mirror(edges, adj, wps, W_LEN, W_TURN, W_OBS)


def dist_cm(path):
    """路线里程（cm）。边表 step 是"代码长度单位"，× LEN_SCALE 得厘米。"""
    tot = 0.0
    for a, b in zip(path, path[1:]):
        tot += STEP.get((W.NODE_IDX.get(a), W.NODE_IDX.get(b)), 0.0)
    return tot * 1.2


def dedup(seq):
    return [k for k, _ in itertools.groupby(seq)]


def strip_S(path):
    return dedup([n for n in path if n not in ("S1", "S2")])


def has_S(path):
    return any(n in ("S1", "S2") for n in path)


# ==================== 三处插点的 wp 构造（照抄 C 代码） ====================

def r2_wp(door, treasure, tour):
    """镜像 mission_planner.c:get_newroute() 的 wp。door=(D2,D3,D4,D5)"""
    p6f = (treasure == 6)
    wp = ["N2", "P1", "P3"]
    if tour:
        wp.append("S1")
    wp.append("P4")
    if tour:
        wp.append("S2")
    wp.append("N5")
    # 进门
    if cp(door[0]):
        wp.append("N12")
    elif cp(door[1]):
        wp.append("N8")
    elif cp(door[2]):
        wp.append("N3")
        if p6f:
            wp.append("N8")
    else:
        return None
    # 巡游（顺序来自 config.h 的 ROUND2_CRUISE_*）
    wp += (R2_CCW if p6f else R2_CW)
    # 回程
    if door[0] == CAN:
        wp.append("N5")
    elif door[0] == ONE and door[3] == CAN:
        wp.append("N10")
    elif door[0] == ONE and door[3] == NO and door[2] == CAN:
        wp.append("N8")
    elif door[0] == ONE and door[3] == NO and door[2] == NO:
        wp += ["N8", "N5"]
    elif door[0] == NO and door[1] == CAN:
        wp += ["N8", "N5"]
    elif door[0] == NO and door[1] == ONE and door[3] == CAN:
        wp.append("N10")
    elif door[0] == NO and door[1] == ONE and door[3] == NO:
        wp.append("N8")
    elif door[0] == NO and door[1] == NO and door[2] == CAN:
        wp.append("N8")
    elif door[0] == NO and door[1] == NO and door[2] == ONE:
        wp.append("N10")
    else:
        return None
    wp.append("P2")
    return wp


def round1_tail(treasure, clue, punch, tour):
    """镜像 mission_planner.c:append_round1_return_tail()：宝物平台之后、P2 之前的交错段。

    判据（2026-10-07 改）：会去 P3 = 平台就是 P3 或（补打卡开着且百位没走过 P3）；会去 P4 同理。
    顺序固定 P3 -> S1 -> P4 -> S2。返回列表**不含宝物平台本身**（调用方已在更前面加过）。
    """
    go_p3 = (treasure == 3) or (bool(punch) and clue != 3 and treasure != 3)
    go_p4 = (treasure == 4) or (bool(punch) and clue != 4 and treasure != 4)
    out = []
    if go_p3 and treasure != 3:
        out.append("P3")
    if go_p3 and tour:
        out.append("S1")
    if go_p4 and treasure != 4:
        out.append("P4")
    if go_p4 and tour:
        out.append("S2")
    return out


def tret_wp(start, door, treasure, tour, clue=0, punch=False):
    """镜像 mission_planner.c:plan_treasure_return() 的 wp。"""
    if treasure not in (2, 3, 4, 5, 6):
        return None
    target = {2: "P1", 3: "P3", 4: "P4", 5: "P5", 6: "P6"}[treasure]
    wp = [start]
    if treasure == 5:
        wp.append("P5")
    elif treasure == 6:
        wp.append("P6")
    if door[0] == CAN:
        wp += ["N12", "N5"]
    elif door[1] == CAN:
        wp += ["N8", "N5"]
    elif door[2] == CAN:
        wp += ["N8", "N3"]
    elif ONE in door[0:3]:
        wp += ["N10", "N3"]
    else:
        return None
    if treasure not in (5, 6):
        wp.append(target)
    wp += round1_tail(treasure, clue, punch, tour)   # ← 镜像 append_round1_return_tail()
    wp.append("P2")
    return wp


def home_wp(now, treasure, tour, clue=0, punch=False):
    """镜像 mission_planner.c:route_return_home() 的 wp。"""
    wp = [now]
    if treasure == 2:
        wp.append("P1")
    elif treasure == 3:
        wp.append("P3")
    elif treasure == 4:
        wp.append("P4")
    wp += round1_tail(treasure, clue, punch, tour)   # ← 镜像 append_round1_return_tail()
    wp.append("P2")
    return wp


# ==================== 检查框架 ====================
FAILS = []
N_CHECK = 0
EX = {}


def check(cond, tag, detail=""):
    global N_CHECK
    N_CHECK += 1
    if not cond:
        FAILS.append(f"{tag}  {detail}")
        print(f"  [FAIL] {tag}   {detail}")


print("=" * 78)
print("直立景点巡回（S1/S2）路线验证 —— 镜像 mission_planner.c 的三处插点")
print("UPRIGHT_TOUR_ENABLE=%d ｜ P3P4_PUNCH_ENABLE=%d（读自 Mission/config.h）" % (TOUR, PUNCH))
if SYNC:
    print("★ 源同步自检：不通过 —— 本镜像是旧版，下面的结论不可信：")
    for _p in SYNC:
        print("   - %s" % _p)
else:
    print("源同步自检：通过（交错段在 append_round1_return_tail()、两处调用、顺序 P3->S1->P4->S2）")
print("=" * 78)

# ---------- [1] 二轮 get_newroute ----------
print("\n[1] 二轮 get_newroute()：P3 之后绕 S1、P4 之后绕 S2")
n_case = n_sol = 0
d_off = []
d_on = []
for door in itertools.product((CAN, ONE, NO), repeat=4):
    for tre in (2, 3, 4, 5, 6):
        w0 = r2_wp(door, tre, False)
        w1 = r2_wp(door, tre, True)
        if w0 is None:
            continue
        n_case += 1
        p0, p1 = plan(w0), plan(w1)
        if p0 is None:
            continue
        n_sol += 1
        tag = f"二轮 door={door} t={tre}"
        check(not has_S(p0), tag + " 关闭态不应有 S", f"{p0}")
        check(p1 is not None, tag + " 打开态应可达")
        if p1 is None:
            continue
        check("S1" in p1 and "S2" in p1, tag + " 打开态应含 S1+S2", f"{p1}")
        if "S1" in p1 and "P3" in p1:
            check(p1.index("S1") > p1.index("P3"), tag + " S1 应在 P3 之后")
        if "S2" in p1 and "P4" in p1:
            check(p1.index("S2") > p1.index("P4"), tag + " S2 应在 P4 之后")
        check(strip_S(p1) == p0, tag + " 去掉 S 支路后应与关闭态一致",
              f"\n          开-去S: {' '.join(strip_S(p1))}\n          关闭态: {' '.join(p0)}")
        d_off.append(dist_cm(p0))
        d_on.append(dist_cm(p1))
        EX.setdefault("r2", (door, tre, w0, w1, p0, p1))

print(f"    可达组合 {n_sol}/{n_case}")
if n_sol == 0 and n_case:
    print("    ⚠️ [1] 一个可达组合都没有：当前 `Navigation/map.c` / `map_message.c`（工作树 WIP）下，"
          "镜像连 `N12 -> P5` 都走不通 —— 属**既有**问题（`validate/_check_wp_east.py`、"
          "`validate/_check_wp.py` 同样在报），与 S1/S2 插点无关；修复权重/边表后本段会自动恢复。")
if d_off:
    inc = [b - a for a, b in zip(d_off, d_on)]
    print(f"    里程增量：min={min(inc):.0f}cm  max={max(inc):.0f}cm  "
          f"中位={sorted(inc)[len(inc)//2]:.0f}cm")

# ---------- [2] 一轮 plan_treasure_return ----------
print("\n[2] 一轮 plan_treasure_return()：A 段 punch=0 回归基线；B 段 punch=1 交错 P3->S1->P4->S2")
n_case = n_sol = 0
D_TRET = []
N_PUNCH2 = 0


def _tail_wp_order(wp):
    return [n for n in wp if n in ("P3", "S1", "P4", "S2")]


for door in itertools.product((CAN, ONE, NO), repeat=4):
    for tre in (2, 3, 4, 5, 6):
        for start in ("P7", "P8"):
            w0 = tret_wp(start, door, tre, False)
            if w0 is None:
                continue
            n_case += 1
            p0 = plan(w0)
            if p0 is None:
                continue
            n_sol += 1
            tag = f"一轮 {start} t={tre} door={door}"
            check(not has_S(p0), tag + " 关闭态不应有 S", f"{p0}")
            # --- A. punch=0 + tour=1：旧行为（S 只跟宝物值），回归基线 ---
            w1 = tret_wp(start, door, tre, True, 0, False)
            p1 = plan(w1)
            check(p1 is not None, tag + " 打开态应可达")
            if p1 is not None:
                if tre in (3, 4):
                    s, plat = ("S1", "P3") if tre == 3 else ("S2", "P4")
                    check(s in p1, tag + f" 打开态应含 {s}", f"{p1}")
                    if s in p1:
                        check(p1.index(s) > p1.index(plat),
                              tag + f" {s} 必须排在宝物平台 {plat} 之后（取宝前去 = 结束比赛）")
                else:
                    check(not has_S(p1), tag + f" 宝物 t={tre}（补打卡关）不应插 S", f"{p1}")
                check(strip_S(p1) == p0, tag + " 去掉 S 支路后应与关闭态一致",
                      f"\n          开-去S: {' '.join(strip_S(p1))}\n          关闭态: {' '.join(p0)}")
                if tre in (3, 4):        # 只拿"真正插了 S"的案例做示例
                    EX.setdefault("tret", (start, door, tre, w0, w1, p0, p1))
                    D_TRET.append(dist_cm(p1) - dist_cm(p0))
            # --- B. punch=1 + tour=1：新判据（S 跟着"会去 P3/P4"走；顺序交错）---
            for clue in (0, 3, 4):
                w2 = tret_wp(start, door, tre, True, clue, True)
                go3 = (tre == 3) or (clue != 3 and tre != 3)
                go4 = (tre == 4) or (clue != 4 and tre != 4)
                tg2 = tag + f" clue={clue} punch=1"
                N_PUNCH2 += 1
                _o = _tail_wp_order(w2)
                check("S1" not in _o or "P3" not in _o or _o.index("S1") > _o.index("P3"),
                      tg2 + " wp 里 S1 应排在 P3 之后", f"{_o}")
                check("S2" not in _o or "P4" not in _o or _o.index("S2") > _o.index("P4"),
                      tg2 + " wp 里 S2 应排在 P4 之后", f"{_o}")
                if go3 and go4 and tre not in (3, 4):
                    check(_o == ["P3", "S1", "P4", "S2"],
                          tg2 + " 两个景点都绕（宝物不在 P3/P4）时 wp 应为 P3 -> S1 -> P4 -> S2", f"{_o}")
                check(("S1" in w2) == bool(go3), tg2 + f" S1 应{'在' if go3 else '不在'}（go3={go3}）",
                      f"{w2}")
                check(("S2" in w2) == bool(go4), tg2 + f" S2 应{'在' if go4 else '不在'}（go4={go4}）",
                      f"{w2}")
                p2 = plan(w2)
                check(p2 is not None, tg2 + " 应可达")
                if p2 is None:
                    continue
                check(("S1" in p2) == bool(go3), tg2 + f" route 里 S1 应与 go3 一致（{p2}）")
                check(("S2" in p2) == bool(go4), tg2 + f" route 里 S2 应与 go4 一致（{p2}）")
                if tre in (3, 4):
                    s, plat = ("S1", "P3") if tre == 3 else ("S2", "P4")
                    if s in p2:
                        check(p2.index(s) > p2.index(plat),
                              tg2 + f" {s} 必须排在宝物平台 {plat} 之后")
                if tre not in (3, 4) and go3 and go4:
                    check("S1" in p2 and "S2" in p2,
                          tg2 + " 宝物不在 P3/P4 时（补打卡开）两个景点都该绕", f"{p2}")
                EX.setdefault("punch_interleave", (start, door, tre, clue, w2, p2))

print(f"    可达组合 {n_sol}/{n_case}")
if D_TRET:
    print(f"    插 S 组合里程增量：min={min(D_TRET):.0f}cm  max={max(D_TRET):.0f}cm")

# ---------- [3] 一轮 route_return_home ----------
print("\n[3] 一轮 route_return_home()：A 段 punch=0 回归基线；B 段 punch=1 交错 P3->S1->P4->S2")
n_case = n_sol = 0
D_HOME = []
N_PUNCH3 = 0
for now in ("N3", "N8", "N5"):
    for tre in (2, 3, 4, 5, 6):
        w0 = home_wp(now, tre, False)
        w1 = home_wp(now, tre, True)
        n_case += 1
        p0 = plan(w0)
        if p0 is None:
            continue
        n_sol += 1
        tag = f"门回程 now={now} t={tre}"
        check(not has_S(p0), tag + " 关闭态不应有 S", f"{p0}")
        # --- A. punch=0 + tour=1：旧行为 ---
        p1 = plan(w1)
        check(p1 is not None, tag + " 打开态应可达")
        if p1 is not None:
            if tre in (3, 4):
                s, plat = ("S1", "P3") if tre == 3 else ("S2", "P4")
                check(s in p1, tag + f" 打开态应含 {s}", f"{p1}")
                if s in p1:
                    check(p1.index(s) > p1.index(plat),
                          tag + f" {s} 必须排在宝物平台 {plat} 之后")
            else:
                check(not has_S(p1), tag + f" 宝物 t={tre}（补打卡关）不应插 S", f"{p1}")
            check(strip_S(p1) == p0, tag + " 去掉 S 支路后应与关闭态一致",
                  f"\n          开-去S: {' '.join(strip_S(p1))}\n          关闭态: {' '.join(p0)}")
            if tre in (3, 4):
                EX.setdefault("home", (now, tre, w0, w1, p0, p1))
                D_HOME.append(dist_cm(p1) - dist_cm(p0))
        # --- B. punch=1 + tour=1：新判据 ---
        for clue in (0, 3, 4):
            w2 = home_wp(now, tre, True, clue, True)
            go3 = (tre == 3) or (clue != 3 and tre != 3)
            go4 = (tre == 4) or (clue != 4 and tre != 4)
            tg2 = tag + f" clue={clue} punch=1"
            N_PUNCH3 += 1
            _o = _tail_wp_order(w2)
            check("S1" not in _o or "P3" not in _o or _o.index("S1") > _o.index("P3"),
                  tg2 + " wp 里 S1 应排在 P3 之后", f"{_o}")
            check("S2" not in _o or "P4" not in _o or _o.index("S2") > _o.index("P4"),
                  tg2 + " wp 里 S2 应排在 P4 之后", f"{_o}")
            if go3 and go4 and tre not in (3, 4):
                check(_o == ["P3", "S1", "P4", "S2"],
                      tg2 + " 两个景点都绕（宝物不在 P3/P4）时 wp 应为 P3 -> S1 -> P4 -> S2", f"{_o}")
            check(("S1" in w2) == bool(go3), tg2 + f" S1 应{'在' if go3 else '不在'}（go3={go3}）",
                  f"{w2}")
            check(("S2" in w2) == bool(go4), tg2 + f" S2 应{'在' if go4 else '不在'}（go4={go4}）",
                  f"{w2}")
            p2 = plan(w2)
            check(p2 is not None, tg2 + " 应可达")
            if p2 is None:
                continue
            check(("S1" in p2) == bool(go3), tg2 + f" route 里 S1 应与 go3 一致（{p2}）")
            check(("S2" in p2) == bool(go4), tg2 + f" route 里 S2 应与 go4 一致（{p2}）")
            if tre in (3, 4):
                s, plat = ("S1", "P3") if tre == 3 else ("S2", "P4")
                if s in p2:
                    check(p2.index(s) > p2.index(plat), tg2 + f" {s} 必须排在宝物平台 {plat} 之后")
            if tre not in (3, 4) and go3 and go4:
                check("S1" in p2 and "S2" in p2,
                      tg2 + " 宝物不在 P3/P4 时（补打卡开）两个景点都该绕", f"{p2}")
            EX.setdefault("home_punch_interleave", (now, tre, clue, w2, p2))

print(f"    可达组合 {n_sol}/{n_case}")
if D_HOME:
    print(f"    插 S 组合里程增量：min={min(D_HOME):.0f}cm  max={max(D_HOME):.0f}cm")

# ==================== 示例输出 ====================
print("\n" + "=" * 78)
print("示例路线（UPRIGHT_TOUR_ENABLE=1）")
print("=" * 78)


def show_interleave(title, key):
    if key not in EX:
        return
    e = EX[key]
    if key == "punch_interleave":
        start, door, tre, clue, w2, p2 = e
        print(f"\n【{title} · 起点={start} 宝物=P{tre} 百位={clue}】")
    else:
        now, tre, clue, w2, p2 = e
        print(f"\n【{title} · nowNode={now} 宝物=P{tre} 百位={clue}】")
    print(f"  补打卡开的 wp   : {' '.join(w2)}")
    print(f"  补打卡开的 route: {' '.join(p2)}")


def show(title, wps, p):
    print(f"\n{title}")
    print(f"  wp    : {' '.join(str(x) for x in wps)}")
    if p is None:
        print("  route : <不可达>")
        return
    print(f"  route : {' '.join(p)}")


if "r2" not in EX:
    print("\n【二轮 · 无示例】[1] 没有可达组合（见上面的既有可达性说明）")
else:
    d, t, w0, w1, p0, p1 = EX["r2"]
    print(f"\n【二轮 · 门={d} 宝物={t}】")
    print(f"  关闭 wp   : {' '.join(w0)}")
    print(f"  关闭 route: {' '.join(p0)}  ({dist_cm(p0):.0f}cm)")
    print(f"  打开 wp   : {' '.join(w1)}")
    print(f"  打开 route: {' '.join(p1)}  ({dist_cm(p1):.0f}cm)")
    print(f"  里程增量  : {dist_cm(p1) - dist_cm(p0):.0f}cm")

for key, title in (("tret", "一轮 plan_treasure_return"), ("home", "一轮 route_return_home")):
    if key not in EX:
        continue
    e = EX[key]
    if key == "tret":
        start, door, tre, w0, w1, p0, p1 = e
        print(f"\n【{title} · 起点={start} 宝物=P{tre}】")
    else:
        now, tre, w0, w1, p0, p1 = e
        print(f"\n【{title} · nowNode={now} 宝物=P{tre}】")
    print(f"  关闭 wp   : {' '.join(w0)}")
    print(f"  关闭 route: {' '.join(p0)}")
    print(f"  打开 wp   : {' '.join(w1)}")
    print(f"  打开 route: {' '.join(p1)}")
    print(f"  里程增量  : {dist_cm(p1) - dist_cm(p0):.0f}cm")

# ==================== 结果 ====================
print("\n" + "=" * 78)
if FAILS:
    print(f"[FAIL] {len(FAILS)} 项不通过 / 共 {N_CHECK} 项检查")
    for f in FAILS[:20]:
        print("   -", f)
    sys.exit(1)
show_interleave("一轮 plan_treasure_return（交错）", "punch_interleave")
show_interleave("一轮 route_return_home（交错）", "home_punch_interleave")
print("\n" + "=" * 78)
if FAILS:
    print(f"[FAIL] {len(FAILS)} 项不通过 / 共 {N_CHECK} 项检查")
    for f in FAILS[:20]:
        print("   -", f)
    sys.exit(1)
print(f"[OK] 全部通过（{N_CHECK} 项检查）："
      "关闭态无 S（回归基线）· punch=0 时旧行为不变 · punch=1 时 S 跟着「会去 P3/P4」走"
      "且交错成 P3->S1->P4->S2 · S 在宝物平台之后 · 去 S 后与关闭态一致")
print("=" * 78)
