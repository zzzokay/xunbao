# -*- coding: utf-8 -*-
"""门惩罚(或任意障碍权重)改动前后"会动哪些路线"的穷举比对（只读，不进固件）。

回答的问题：把 `NavObsPenalty[DOOR]` 从 A 改成 B，**哪些路线会变**？覆盖固件里**所有**会调用
`nav_build_route/nav_plan_waypoints` 的地方（按源码分支穷举参数）+ `MAP_DEBUG` 调试空间全枚举
+ 三种**可达**的边禁用状态（无禁用 / 门区 8 条全禁（door_block_all）/ 再放行 N8→N3（door_2））。

关键加速（也是结论依据）：
  门惩罚只**增加**"走门边"那条路的成本；若 A 下的最优路线**不含任何 DOOR 边**，它的成本在 B 下不变，
  而其它路线的成本只增不减 → **最优解不可能变**。所以只有"A 下含 DOOR 边"的组合才需要真算 B。

用法（仓库根）：
  python3 地图修改上位机/tools/analyze_door_weight_route_diff.py            # 默认 A=0 B=60，两种场地都跑
  python3 地图修改上位机/tools/analyze_door_weight_route_diff.py 0 100      # 自定义 A/B
exit：0=跑完（有差异也会打印明细，不算失败）
"""
import collections
import importlib
import io
import contextlib
import os
import runpy
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # 地图修改上位机/
sys.path.insert(0, os.path.join(BASE, "validate"))

import _weight_calib as W0  # noqa: E402

DOOR_FUNC = 14
DOOR_ZONE = [("N5", "N12"), ("N12", "N5"), ("N5", "N8"), ("N8", "N5"),
             ("N3", "N8"), ("N8", "N3"), ("N3", "N10"), ("N10", "N3")]
DOOR_NODES = ["N5", "N8", "N12", "N3", "N10"]
CLUE_COMBOS = [(5, 7), (5, 8), (6, 7), (6, 8)]
TREASURE_PF = {2: "P1", 3: "P3", 4: "P4", 5: "P5", 6: "P6"}
# 每轮开始时全是这 5 个路径点（get_newroute 固定前缀）
R2_PREFIX = ["N2", "P1", "P3", "P4", "N5"]


# ----------------------------------------------------------------------------- 固件调用点穷举
def firmware_cases():
    """返回 [(标签, wp, 禁用状态)]，标签里带源码位置。禁用状态: 'none'/'zone'/'zone+N8N3'"""
    cases = []
    # map.c: 第一轮初始路线（USE_PLANNER_ROUTE=1）
    cases.append(("map.c:mapInit 初始", ["N2", "P1", "N5"], "none"))

    # mission_planner.c:route_return_home（门回程，door_1..4）——门区全禁，(door_2 再放行 N8→N3)
    for start in ("N3", "N8", "N5"):
        for t in (2, 3, 4, 5, 6):
            for st in ("zone", "zone+N8N3"):
                wp = [start] + ([TREASURE_PF[t]] if t in (2, 3, 4) else []) + ["P2"]
                cases.append(("mission_planner.c:route_return_home(%s,t%d)" % (start, t), wp, st))

    # mission_planner.c:plan_treasure_return（P7/P8 拿到宝物后回程）——4 个门分支
    for start in ("P7", "P8"):
        for t in (2, 3, 4, 5, 6):
            for br, door_wp in (("D2CAN", ["N12", "N5"]), ("D3CAN", ["N12", "N8", "N5"]),
                                ("D4CAN", ["N12", "N8", "N3"]), ("ONEWAY", ["N10", "N3"])):
                wp = [start] + ([TREASURE_PF[t]] if t in (5, 6) else [])
                wp += door_wp + ([] if t in (5, 6) else [TREASURE_PF[t]]) + ["P2"]
                cases.append(("mission_planner.c:plan_treasure_return(%s,t%d,%s)" % (start, t, br), wp, "none"))

    # mission_planner.c:update_route_at_door_for_stageAB —— 4 个线索组合 × 当前门外侧节点
    for now in DOOR_NODES:
        for a, b in CLUE_COMBOS:
            tail = {5: ("P5", "N12", "P7", "C9"), 6: ("N10", "P6", "P7", "C9")}[a]
            end = {7: ("C9",), 8: ("N20",)}[b]
            wp = [now] + list(tail[:2]) + ([ "P7", "C9"] if b == 7 else ["P8", "N20"])
            cases.append(("mission_planner.c:stageAB(A%d,B%d,now=%s)" % (a, b, now), wp, "zone"))

    # mission_planner.c:get_newroute（第二轮完整路线）——入口 3 分支 × 巡游 2 方向 × 回程 8 分支
    entry = {"D2CAN": ["N12"], "D3CAN": ["N8", "N12"], "D4CAN": ["N3", "N8", "N12"]}
    for p6 in (False, True):
        for ebr, ewp in entry.items():
            wp_e = list(ewp if not p6 else [w for w in ewp if w != "N12"])
            tour = (["P6", "P8", "P7", "P5", "N12"] if p6 else ["P5", "P7", "P8", "P6", "N10"])
            for rbr, rwp in (("D2CAN", ["N5"]), ("OW+D5CAN", ["N10", "N3"]),
                             ("OW+D5NO+D4CAN", ["N8", "N3"]), ("OW+D5NO+D4NO", ["N8", "N5"]),
                             ("D2NO+D3CAN", ["N8", "N5"]), ("D2NO+D3OW+D5CAN", ["N10", "N3"]),
                             ("D2NO+D3OW+D5NO", ["N8", "N3"]), ("D2NO+D3NO+D4CAN", ["N8", "N3"]),
                             ("D2NO+D3NO+D4OW", ["N10", "N3"])):
                wp = R2_PREFIX + wp_e + tour + rwp + ["P2"]
                cases.append(("mission_planner.c:get_newroute(p6=%d,%s,%s)" % (p6, ebr, rbr), wp, "none"))
    return cases


def debug_cases(W, nodes):
    """MAP_DEBUG 调试空间：FIRST×VIA×END（VIA=0=不用途径点，S1=0 按约定不能当途径点）。
    返回 (wp_names, 标签)。"""
    out = []
    for first in nodes:
        for end in nodes:
            out.append(([W.IDX2NAME[first], W.IDX2NAME[end]], "%s->%s" % (W.IDX2NAME[first], W.IDX2NAME[end])))
            for via in nodes:
                if via == 0 or via == first or via == end:
                    continue
                out.append(([W.IDX2NAME[first], W.IDX2NAME[via], W.IDX2NAME[end]],
                            "%s->%s->%s" % (W.IDX2NAME[first], W.IDX2NAME[via], W.IDX2NAME[end])))
    return out


# ----------------------------------------------------------------------------- 工具
def fresh(field):
    W = importlib.reload(W0)
    if field == "school":
        W.sync_field_from_config()
    return W


def make_adj(W, edges, state):
    blocked = set()
    if state != "none":
        blocked = {(W.NODE_IDX[a], W.NODE_IDX[b]) for a, b in DOOR_ZONE}
        if state == "zone+N8N3":
            blocked.discard((W.NODE_IDX["N8"], W.NODE_IDX["N3"]))
    adj = collections.defaultdict(list)
    for i, e in enumerate(edges):
        if (e["from"], e["to"]) in blocked:
            continue
        adj[e["from"]].append(i)
    return adj


def has_door(W, edges, adj, seq):
    """路线里是否走过 DOOR 边（决定"B 值下是否可能变"）"""
    if not seq:
        return False
    for a, b in zip(seq, seq[1:]):
        for j in adj.get(W.NODE_IDX[a], []):
            if edges[j]["to"] == W.NODE_IDX[b] and edges[j]["func"] == DOOR_FUNC:
                return True
    return False


def plan(W, edges, adj, wp, pen):
    W.OBS_PENALTY[DOOR_FUNC] = pen
    return W.plan_via_waypoints(edges, adj, wp, 1.0, 0.6, 1.0)


# ---- 分段缓存：调试空间里同一段 X→Y 会被重复求上千次，缓存后整轮从 ~9min 降到 ~20s ----
_LEG_CACHE = {}


def plan_cached(W, edges, adj, wp, pen, key):
    """与 nav_plan_waypoints 逐字同语义，但按段缓存 dijkstra 结果。"""
    out = []
    for i in range(len(wp) - 1):
        k = (key, wp[i], wp[i + 1], pen)
        if k not in _LEG_CACHE:
            W.OBS_PENALTY[DOOR_FUNC] = pen
            seg, _c = W.dijkstra(edges, adj, W.NODE_IDX[wp[i]], W.NODE_IDX[wp[i + 1]], 1.0, 0.6, 1.0)
            _LEG_CACHE[k] = [W.IDX2NAME[x] for x in seg] if seg else None
        seg = _LEG_CACHE[k]
        if seg is None:
            return None
        j = 1 if (out and seg[0] == out[-1]) else 0
        out.extend(seg[j:])
    return out


def count_door(W, edges, adj, seq):
    """路线里 DOOR 边的条数"""
    n = 0
    for a, b in zip(seq, seq[1:]):
        for j in adj.get(W.NODE_IDX[a], []):
            if edges[j]["to"] == W.NODE_IDX[b] and edges[j]["func"] == DOOR_FUNC:
                n += 1
    return n


def run(field, pen_a, pen_b):
    _LEG_CACHE.clear()
    W = fresh(field)
    edges = W.parse_graph()
    nodes = sorted(W.NODE_IDX.values())
    print("\n############ %s ：门惩罚 %s → %s ############"
          % ("学校FIELD_SCHOOL" if field == "school" else "比赛FIELD_COMP", pen_a, pen_b))

    # ---- ① 固件调用点 ----
    adj_cache = {st: make_adj(W, edges, st) for st in ("none", "zone", "zone+N8N3")}
    tot = door_used = changed = 0
    changes = []
    for label, wp, st in firmware_cases():
        adj = adj_cache[st]
        r0 = plan_cached(W, edges, adj, wp, pen_a, st)
        if not r0:
            continue
        tot += 1
        if not has_door(W, edges, adj, r0):
            continue                      # 数学上保证不变
        door_used += 1
        r1 = plan_cached(W, edges, adj, wp, pen_b, st)
        if r0 != r1:
            changed += 1
            changes.append((label, st, wp, r0, r1,
                            count_door(W, edges, adj, r0), count_door(W, edges, adj, r1)))
    print("\n① 固件调用点穷举：%d 个有效用例（其中 A 值下走门的 %d 个 → 这些才可能变）；"
          "**实际改变 %d 个**" % (tot, door_used, changed))
    for label, st, wp, r0, r1, d0, d1 in changes[:20]:
        print("   [变了] %s  [禁用:%s]  门边数 %d → %d" % (label, st, d0, d1))
        print("          wp = %s" % ",".join(wp))
        print("          A: %s" % " ".join(r0))
        print("          B: %s" % " ".join(r1))
    if changed > 20:
        print("   ...（共 %d 个，仅列前 20）" % changed)

    # ---- ② MAP_DEBUG 调试空间 ----
    dbg = debug_cases(W, nodes)
    adj = adj_cache["none"]
    d_tot = d_door = d_changed = 0
    d_examples = []
    stat = collections.Counter()          # (A 的门边数, B 的门边数) 分布
    for wp, label in dbg:
        r0 = plan_cached(W, edges, adj, wp, pen_a, "none")
        if not r0:
            continue
        d_tot += 1
        if not has_door(W, edges, adj, r0):
            continue
        d_door += 1
        r1 = plan_cached(W, edges, adj, wp, pen_b, "none")
        if r0 != r1:
            d_changed += 1
            stat[(count_door(W, edges, adj, r0), count_door(W, edges, adj, r1))] += 1
            if len(d_examples) < 6:
                d_examples.append((label, r0, r1))
    print("\n② MAP_DEBUG 空间（FIRST×VIA×END 全枚举）：%d 个有效组合（其中 A 值下走门的 %d 个）；"
          "**实际改变 %d 个**" % (d_tot, d_door, d_changed))
    for label, r0, r1 in d_examples:
        print("   组合 %-14s A: %s" % (label, " ".join(r0)))
        print("   %-18s B: %s" % ("", " ".join(r1)))
    if d_changed:
        print("   变化前后(门边数)分布 A→B: %s"
              % ", ".join("%d扇→%d扇:%d个" % (k[0], k[1], v) for k, v in sorted(stat.items())))
    return changed, d_changed


def main():
    pen_a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    pen_b = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    for field in ("school", "comp"):
        run(field, pen_a, pen_b)
    print("\n说明：① 里 'zone'/'zone+N8N3' 是 `door_block_all()` 的两种可达禁用状态；"
          "② 调试空间不涉及禁用。\n      'A 值下走门' 之外的组合按单调性论证**数学上保证不变**，故未逐一实算 B。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
