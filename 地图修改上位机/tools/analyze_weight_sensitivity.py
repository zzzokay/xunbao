# -*- coding: utf-8 -*-
"""权重灵敏度分析：调"门惩罚 NavObsPenalty[DOOR]"或"转弯权重 NAV_W_TURN"会动哪些路线。

用途：想用权重让规划器"别穿门 / 别乱转弯"之前，先看这两个旋钮各自会改掉哪些既有路线。
做法：把候选值注入镜像(_weight_calib)，再跑 5 个校验脚本(其内部都用镜像的权重/长度)，
      同时算 `MAP_DEBUG` 调试路线(FIRST=N6,VIA=N3,END=P4)在两种场地下的选路结果。
只读代码，不进固件。

用法：python3 地图修改上位机/tools/analyze_weight_sensitivity.py
"""
import contextlib
import importlib
import io
import os
import runpy
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # 地图修改上位机/
sys.path.insert(0, os.path.join(BASE, "validate"))

import _weight_calib as W0  # noqa: E402

SCRIPTS = ["_weight_calib", "_check_csr", "_check_wp", "_check_door_logic", "_check_door_perm"]
DOOR_FUNC = 14          # map.h enum barriers: DOOR
UPSTAGE_FUNC = 2


def fresh(field):
    """重新加载镜像（拿到干净的 MACROS/权重），并按须要同步 config.h 的场地。"""
    W = importlib.reload(W0)
    if field == "school":
        W.sync_field_from_config()
    return W


def run_scripts():
    """跑 5 个校验脚本，返回 {脚本: 结果}。"""
    out = {}
    for name in SCRIPTS:
        path = os.path.join(BASE, "validate", name + ".py")
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                runpy.run_path(path, run_name="__main__")
            out[name] = "OK"
        except SystemExit as e:
            out[name] = "OK" if e.code in (0, None) else "FAIL"
        except Exception as e:                                   # noqa: BLE001
            out[name] = "ERR:" + type(e).__name__
    return out


def leg_cost(W, edges, adj, seq, w_turn):
    """★ 按 `nav_shortest_path`/线路图 Dijkstra 的**真实模型**算一条固定节点序列的成本：
    首边只算 base（**不含转弯费**——这正是必经点规划的行为：段与段交界处那个转弯不计费），
    其余每条边 = base + w_turn*|Δangle|。断链返回 None。
    注意：整条 route 的"总成本"不是规划器用来选路的量（跨段转弯不计费），别用它下结论。"""
    def find(a, b):
        best = None
        for j in adj.get(W.NODE_IDX[a], []):
            if edges[j]["to"] == W.NODE_IDX[b]:
                best = edges[j] if best is None else best
        return best

    total = 0.0
    prev = None
    for i in range(len(seq) - 1):
        e = find(seq[i], seq[i + 1])
        if e is None:
            return None
        total += e["step"] + W.obs_w(e["func"])
        if prev is not None:
            total += w_turn * W.need2turn(prev["angle"], e["angle"])
        prev = e
    return total


def probe(field, door_pen, w_turn):
    """一组参数下的：5 个脚本结果 + 调试路线(FIRST=N6,VIA=N3,END=P4) + 两条候选**分段**成本。"""
    W = fresh(field)
    W.OBS_PENALTY[DOOR_FUNC] = door_pen
    W.NAV_W_TURN = w_turn
    edges = W.parse_graph()
    adj = W.build_adj(edges)
    dbg = W.plan_via_waypoints(edges, adj, ["N6", "N3", "P4"], 1.0, w_turn, 1.0) or []
    # 关键那一段 = leg2 `N3→P4` 的两种走法（规划器就是在这两条里选）
    return {
        "scripts": run_scripts(),
        "dbg": dbg,
        "dbg_is": ("掉头N4" if len(dbg) > 4 and dbg[4] == "N4"
                   else "穿门N8" if len(dbg) > 4 and dbg[4] == "N8" else "?"),
        "cost_uturn": leg_cost(W, edges, adj, ["N3", "N4", "N5", "N6", "P4"], w_turn),
        "cost_via_n8": leg_cost(W, edges, adj, ["N3", "N8", "N5", "N6", "P4"], w_turn),
    }


def show(title, rows):
    print("\n===== %s =====" % title)
    print("  %-8s %-26s %-13s %-13s %-9s %s" % ("取值", "5个校验脚本", "leg2走N4(掉头)", "leg2走N8(穿门)", "差值", "规划器选"))
    for label, r in rows:
        bad = [k for k, v in r["scripts"].items() if v != "OK"]
        tag = "全过" if not bad else "破:" + ",".join(bad)
        cu, cn = r["cost_uturn"], r["cost_via_n8"]
        gap = ("%+0.1f" % (cn - cu)) if (cu is not None and cn is not None) else "N/A"
        print("  %-8s %-26s %-13s %-13s %-9s %s" % (
            label, tag,
            "%0.1f" % cu if cu is not None else "N/A",
            "%0.1f" % cn if cn is not None else "N/A",
            gap, r["dbg_is"] + "   " + " ".join(r["dbg"][3:])))


def main():
    for field in ("comp", "school"):
        fname = "比赛FIELD_COMP" if field == "comp" else "学校FIELD_SCHOOL(=你现在 config.h)"
        print("\n############ %s ############" % fname)
        show("A) 门惩罚 NavObsPenalty[DOOR]  (NAV_W_TURN 固定 0.6)",
             [(str(p), probe(field, p, 0.6)) for p in (0, 10, 20, 60, 100, 300)])
        show("B) 转弯权重 NAV_W_TURN  (门惩罚固定 0)",
             [("%.2f" % t, probe(field, 0, t)) for t in (0.0, 0.3, 0.6, 0.9, 1.2)])
    print("\n读法：'差值'= 穿门成本 - 掉头成本，<0 就会选穿门。"
          "\n      '破'= 某校验脚本 exit!=0（金标路线被改动）→ 该取值不能直接用。"
          "\n      镜像的 OBS_PENALTY[12](BLBS) 与 C 表有出入(60 vs 70)，本表只做相对比较；"
          "落地前以 C 表 + MDK 编译 + 5 个校验脚本为准。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
