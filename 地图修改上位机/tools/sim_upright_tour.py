# -*- coding: utf-8 -*-
"""直立景点巡回（S1/S2）开关路线验证 —— 只读源码，不改任何文件。

对照 Mission/mission_planner.c 的三处插点（plan_treasure_return / route_return_home /
get_newroute），用 nav_planner 镜像算出 UPRIGHT_TOUR_ENABLE=0/1 两种状态的 route[]：

  · 0（默认，保持现状）：任何路线里都不出现 S 节点 —— 即回归基线。
  · 1（打开）：S1 只在 P3 之后、S2 只在 P4 之后；一轮里 S 必在宝物平台之后
    （规则：取宝前走到其他平台或直立景点 = 直接结束比赛）。

局限（有意为之）：
  · 本脚本**不镜像门区边禁用**（那是 validate/_check_door_perm.py 的职责），
    因此 route_return_home 一项只验证【S 的插入位置】与【可达性】，不代表门回程里程。

跑法：python3 地图修改上位机/tools/sim_upright_tour.py
"""
import os
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
    # 巡游
    wp += (["P6", "P8", "P7", "P5"] if p6f else ["P5", "P7", "P8", "P6"])
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


def tret_wp(start, door, treasure, tour):
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
    if tour:                                  # ← 新增插点
        if treasure == 3:
            wp.append("S1")
        elif treasure == 4:
            wp.append("S2")
    wp.append("P2")
    return wp


def home_wp(now, treasure, tour):
    """镜像 mission_planner.c:route_return_home() 的 wp。"""
    wp = [now]
    if treasure == 2:
        wp.append("P1")
    elif treasure == 3:
        wp.append("P3")
    elif treasure == 4:
        wp.append("P4")
    if tour:                                  # ← 新增插点
        if treasure == 3:
            wp.append("S1")
        elif treasure == 4:
            wp.append("S2")
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
if d_off:
    inc = [b - a for a, b in zip(d_off, d_on)]
    print(f"    里程增量：min={min(inc):.0f}cm  max={max(inc):.0f}cm  "
          f"中位={sorted(inc)[len(inc)//2]:.0f}cm")

# ---------- [2] 一轮 plan_treasure_return ----------
print("\n[2] 一轮 plan_treasure_return()：仅宝物=P3/P4 时插，且必须在宝物平台【之后】")
n_case = n_sol = 0
D_TRET = []
for door in itertools.product((CAN, ONE, NO), repeat=4):
    for tre in (2, 3, 4, 5, 6):
        for start in ("P7", "P8"):
            w0 = tret_wp(start, door, tre, False)
            w1 = tret_wp(start, door, tre, True)
            if w0 is None:
                continue
            n_case += 1
            p0, p1 = plan(w0), plan(w1)
            if p0 is None:
                continue
            n_sol += 1
            tag = f"一轮 {start} t={tre} door={door}"
            check(not has_S(p0), tag + " 关闭态不应有 S", f"{p0}")
            check(p1 is not None, tag + " 打开态应可达")
            if p1 is None:
                continue
            if tre in (3, 4):
                s = "S1" if tre == 3 else "S2"
                plat = "P3" if tre == 3 else "P4"
                check(s in p1, tag + f" 打开态应含 {s}", f"{p1}")
                if s in p1:
                    check(p1.index(s) > p1.index(plat),
                          tag + f" {s} 必须排在宝物平台 {plat} 之后（取宝前去 = 结束比赛）")
                    check(not (p1.index(s) < p1.index(plat)), tag + " 红线：取宝前不得出现 S")
            else:
                check(not has_S(p1), tag + f" 宝物 t={tre} 时不应插 S", f"{p1}")
            check(strip_S(p1) == p0, tag + " 去掉 S 支路后应与关闭态一致",
                  f"\n          开-去S: {' '.join(strip_S(p1))}\n          关闭态: {' '.join(p0)}")
            if tre in (3, 4):        # 只拿"真正插了 S"的案例做示例
                EX.setdefault("tret", (start, door, tre, w0, w1, p0, p1))
                D_TRET.append(dist_cm(p1) - dist_cm(p0))

print(f"    可达组合 {n_sol}/{n_case}")
if D_TRET:
    print(f"    插 S 组合里程增量：min={min(D_TRET):.0f}cm  max={max(D_TRET):.0f}cm")

# ---------- [3] 一轮 route_return_home ----------
print("\n[3] 一轮 route_return_home()：门口重规划，S 同样在宝物平台之后")
n_case = n_sol = 0
D_HOME = []
for now in ("N3", "N8", "N5"):
    for tre in (2, 3, 4, 5, 6):
        w0 = home_wp(now, tre, False)
        w1 = home_wp(now, tre, True)
        n_case += 1
        p0, p1 = plan(w0), plan(w1)
        if p0 is None:
            continue
        n_sol += 1
        tag = f"门回程 now={now} t={tre}"
        check(not has_S(p0), tag + " 关闭态不应有 S", f"{p0}")
        check(p1 is not None, tag + " 打开态应可达")
        if p1 is None:
            continue
        if tre in (3, 4):
            s = "S1" if tre == 3 else "S2"
            plat = "P3" if tre == 3 else "P4"
            check(s in p1, tag + f" 打开态应含 {s}", f"{p1}")
            if s in p1:
                check(p1.index(s) > p1.index(plat),
                      tag + f" {s} 必须排在宝物平台 {plat} 之后")
        else:
            check(not has_S(p1), tag + f" 宝物 t={tre} 时不应插 S", f"{p1}")
        check(strip_S(p1) == p0, tag + " 去掉 S 支路后应与关闭态一致",
              f"\n          开-去S: {' '.join(strip_S(p1))}\n          关闭态: {' '.join(p0)}")
        if tre in (3, 4):
            EX.setdefault("home", (now, tre, w0, w1, p0, p1))
            D_HOME.append(dist_cm(p1) - dist_cm(p0))

print(f"    可达组合 {n_sol}/{n_case}")
if D_HOME:
    print(f"    插 S 组合里程增量：min={min(D_HOME):.0f}cm  max={max(D_HOME):.0f}cm")

# ==================== 示例输出 ====================
print("\n" + "=" * 78)
print("示例路线（UPRIGHT_TOUR_ENABLE=1）")
print("=" * 78)


def show(title, wps, p):
    print(f"\n{title}")
    print(f"  wp    : {' '.join(str(x) for x in wps)}")
    if p is None:
        print("  route : <不可达>")
        return
    print(f"  route : {' '.join(p)}")


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
print(f"[OK] 全部通过（{N_CHECK} 项检查）："
      "关闭态无 S（回归基线）· 打开态 S 位置正确且在宝物平台之后 · 去 S 后与关闭态一致")
print("=" * 78)
