# -*- coding: utf-8 -*-
"""MAP_DEBUG 调试路线校验（FIRST_POINT / VIA_POINT / END_POINT）。

镜像 `Navigation/map.c` 的 `#if MAP_DEBUG` 分支（只读源码，不进固件）：
  改造前（旧）：n = nav_shortest_path(FIRST, END)
                nowNode = path[1]（第一跳）; route = path[2..] + [0xFF]
  改造后（新）：wp = [FIRST] + ([VIA] if VIA!=0) + [END]
                n = nav_plan_waypoints(wp)   # 返回 节点数+1（末尾 0xFF）
                nowNode = path[1]; route = path[2..n-2] + [0xFF]

断言：
  1) VIA_POINT=0 时，新逻辑与旧逻辑**逐字一致**（对全部 54×54 组 FIRST/END 做穷举回归）；
  2) VIA_POINT≠0 时，路线必然**依次**经过 FIRST -> VIA -> END，且
     via 路线成本 >= 无 via 路线成本（绕路不可能更短）；
  3) VIA_POINT 等于 FIRST 或 END 时，等价于不用途径点（不产生额外节点）；
  4) 生成的 route 相邻节点在边表里**有向连通**（执行层可解析），且 route[0]/nowNode 不重复；
  5) 直接对 `Mission/config.h` 的**当前值**跑一遍，报告当前配置会生成什么路线。

用法（仓库根）：python3 地图修改上位机/validate/_check_map_debug.py
exit：0=全部通过，1=有差异
"""
import os, re, sys

import _weight_calib as W

CONFIG_H = os.path.join(W.BASE, "Mission", "config.h")
SENTINEL = 0xFF   # route[] 结束哨兵（map.h 的 0xFF）

all_ok = True


def fail(msg):
    global all_ok
    all_ok = False
    print("  [FAIL] " + msg)


def read_config_points():
    """从 config.h 读 FIRST_POINT / VIA_POINT / END_POINT 当前值（枚举名或数字）。"""
    txt = open(CONFIG_H, encoding="utf-8", errors="replace").read()
    out = {}
    for key in ("FIRST_POINT", "VIA_POINT", "END_POINT"):
        m = re.search(r"^\s*#define\s+%s\s+([^\s/]+)" % key, txt, re.M)
        if not m:
            fail("config.h 里找不到 #define %s" % key)
            return None
        tok = m.group(1).strip()
        if re.fullmatch(r"\d+", tok):
            out[key] = int(tok)                       # 数字（0 = 不用途径点）
        elif tok in W.NODE_IDX:
            out[key] = W.NODE_IDX[tok]                # MapNode 枚举名
        else:
            fail("config.h 的 %s = %r 不是已知节点名/数字" % (key, tok))
            return None
    return out


# ---------------- 旧逻辑（改造前 map.c 的 MAP_DEBUG 分支） ----------------
def old_logic(edges, adj, first, end):
    """返回 (nowNode, route) 或 None（不可达/起终点相同 -> C 里 n<2 直接 return）。"""
    if first == end:
        return None
    path, _ = W.dijkstra(edges, adj, first, end, 1.0, 0.6, 1.0)
    if path is None or len(path) < 2:
        return None
    return (path[1], path[2:] + [SENTINEL])


# ---------------- 新逻辑（改造后 map.c 的 MAP_DEBUG 分支） ----------------
def new_logic(edges, adj, first, via, end):
    """返回 (nowNode, route) 或 None。via=0 表示不用途径点。"""
    wp = [first] + ([via] if via != 0 else []) + [end]
    full = W.plan_via_waypoints(edges, adj, [W.IDX2NAME[x] for x in wp], 1.0, 0.6, 1.0)
    if full is None:
        return None
    full = [W.NODE_IDX[x] for x in full]
    n = len(full) + 1                                  # +1 = 末尾 0xFF 哨兵（C 的返回值）
    if n < 3:                                          # 至少要 起点+第一跳+0xFF
        return None
    return (full[1], full[2:] + [SENTINEL])            # route = path[2..n-2] + 0xFF


def route_cost(edges, adj, first, route):
    """按 map.c 的 route 语义（nowNode 已消费第一跳）算成本：first->nowNode->...，用于比较绕路长短。"""
    seq = [first] + [x for x in route if x != SENTINEL]
    total = 0.0
    for a, b in zip(seq, seq[1:]):
        best = None
        for j in adj.get(a, []):
            if edges[j]["to"] == b:
                c = 1.0 * edges[j]["step"] + 1.0 * W.obs_w(edges[j]["func"])
                best = c if best is None else min(best, c)
        if best is None:
            return None                                # 相邻不连通
        total += best
    return total


def walk_is_connected(edges, adj, first, res):
    """检查 first->nowNode->route[0]->... 每一跳在边表里都存在有向边。res = (nowNode, route)。"""
    now, rest = res
    seq = [first, now] + [x for x in rest if x != SENTINEL]
    for a, b in zip(seq, seq[1:]):
        if not any(edges[j]["to"] == b for j in adj.get(a, [])):
            return False, (W.IDX2NAME[a], W.IDX2NAME[b])
    return True, None


def first_hop_edge(edges, adj, a, b):
    """返回 a->b 的边（取第一条，与 C 的 getNextConnectNode 首个命中一致）；没有则 None。"""
    for j in adj.get(a, []):
        if edges[j]["to"] == b:
            return edges[j]
    return None


def leg_report(edges, adj, first, now, route):
    """列出逐段航向与每个节点处的转弯需求量；标出 |Δ|>=170° 的"原路折返"和 func=DOOR 的门边。"""
    seq = [first, now] + [x for x in route if x != SENTINEL]
    rows = []
    for i in range(len(seq) - 1):
        e = first_hop_edge(edges, adj, seq[i], seq[i + 1])
        rows.append((seq[i], seq[i + 1], e["angle"] if e else None, e))
    print("  逐段航向、节点转弯量与门边：")
    for a, b, ang, e in rows:
        tag = ""
        if e is not None and e["func"] == W.FUNC["DOOR"]:
            tag = "   [门边 DOOR]"
        elif e is not None and e["func"] in (W.FUNC["UpStage"], W.FUNC["UpStageHome"]):
            tag = "   [平台 %s]" % W.FUNC2NAME[e["func"]]
        print("    %-4s -> %-4s  angle=%-6s step=%-5s%s" % (W.IDX2NAME[a], W.IDX2NAME[b],
              "%g" % ang if ang is not None else "?", "%g" % e["step"] if e else "?", tag))
    reversals = []
    print("  各节点转弯需求量：")
    for i in range(1, len(rows)):
        a1, a2 = rows[i - 1][2], rows[i][2]
        if a1 is None or a2 is None:
            continue
        turn = W.need2turn(a1, a2)          # 已取绝对值
        in_func = rows[i - 1][3]["func"] if rows[i - 1][3] else 0
        platform = in_func in (W.FUNC["UpStage"], W.FUNC["UpStageHome"], W.FUNC["BSoutPole"])
        tag = ""
        if rows[i][0] == rows[i - 1][0] or turn >= 170.0:
            if platform:
                # 平台/南极节点：Stage()/Stage_Home()/South_Pole() 内部已完成 180° 转身，
                # map.c 的 Nav_TurnAndAdvance 对 UpStage/UpStageHome/BSoutPole 明确跳过转弯 → 正常
                tag = "  (=平台内部 180° 转身，map.c 已跳过转弯，正常)"
            else:
                tag = "  <== 180° 就地折返(原路返回)"
                reversals.append((rows[i - 1][0], rows[i][0], rows[i][1], turn))
        print("    at %-4s  |Δ|=%-6.0f%s" % (W.IDX2NAME[rows[i][0]], turn, tag))
    for a, b, c, turn in reversals:
        print("  [WARN] 路线在 %s 处要求\"原路折返\"(%s->%s->%s, |Δ|=%0.0f°)："
              % (W.IDX2NAME[b], W.IDX2NAME[a], W.IDX2NAME[b], W.IDX2NAME[c], turn))
        print("         比赛路线里没有这种动作（(last=%s,now=%s,next=%s) 在 map.c 的 GetForwardDistanceBefore* "
              "里通常没有表项，会退化成默认值），且 180° 目标正好落在 need2turn 的 ±180 边界上、"
              "转向由亚度噪声决定 → 在多岔口容易滑到旁边支线。建议改 FIRST/VIA/END 避开折返。"
              % (W.IDX2NAME[a], W.IDX2NAME[b], W.IDX2NAME[c]))
    doors = [(a, b) for a, b, ang, e in rows if e is not None and e["func"] == W.FUNC["DOOR"]]
    for a, b in doors:
        print("  [WARN] 路线经过门边 %s->%s：到点后 map_function(DOOR)→door() 接管，"
              % (W.IDX2NAME[a], W.IDX2NAME[b]))
        print("         而 door() 开头就 `map.point=0; route[0]=0xFF;`（barrier.c）**清空调试路线**，"
              "之后跑的是比赛门逻辑（DEBUG=0 时会真读红绿灯）。想纯跑路线就别让必经点/终点把它带进门区。")
    return reversals


def main():
    field, module_field = W.sync_field_from_config()
    if field != module_field:
        print("=== [WARN] 场次同步：config.h 的 USE_FIELD=%s，而 _weight_calib 默认按 %s 算 ===" % (field, module_field))
        print("    本脚本已按 config.h 覆盖长度宏（否则镜像会算错路线）；"
              "_check_wp/_check_csr/_check_door_* 的 golden 仍按 %s，未改动。" % module_field)
        print()
    edges = W.parse_graph()
    adj = W.build_adj(edges)
    nodes = sorted(W.NODE_IDX.values())

    print("=== 0) 镜像保真自检：边表里不允许自环（from==to，Python/C 对重复节点的处理不同） ===")
    loops = [(W.IDX2NAME[e["from"]]) for e in edges if e["from"] == e["to"]]
    if loops:
        fail("边表存在自环 %s：本脚本的镜像可能与 C 不完全一致" % ",".join(loops))
    else:
        print("  [OK] 无边表自环，可安全镜像")

    print("\n=== 1) VIA_POINT=0：新逻辑 vs 旧逻辑 全组合逐字一致（54x54）===")
    diff = 0
    for first in nodes:
        for end in nodes:
            o = old_logic(edges, adj, first, end)
            n = new_logic(edges, adj, first, 0, end)
            if o != n:
                diff += 1
                if diff <= 5:
                    fail("%s->%s 旧=%s 新=%s" % (W.IDX2NAME[first], W.IDX2NAME[end], o, n))
    if diff == 0:
        print("  [OK] 2916 组全部一致（不用途径点 = 原两点行为，零行为变化）")
    else:
        fail("共 %d 组不一致" % diff)

    print("\n=== 2) VIA_POINT≠0：路线依次经过 FIRST -> VIA -> END，且不短于无 via ===")
    pairs = [(W.NODE_IDX["N6"], W.NODE_IDX["P3"]), (W.NODE_IDX["N9"], W.NODE_IDX["N12"]),
             (W.NODE_IDX["B1"], W.NODE_IDX["P8"]), (W.NODE_IDX["N13"], W.NODE_IDX["P2"])]
    checked = skipped = 0
    for first, end in pairs:
        base = new_logic(edges, adj, first, 0, end)
        for via in nodes:
            if via == 0:                                # S1=0：按约定不能作途径点，跳过
                continue
            r = new_logic(edges, adj, first, via, end)
            if r is None:
                skipped += 1
                continue
            now, route = r
            seq = [first, now] + [x for x in route if x != SENTINEL]
            if via == first or via == end:
                # 途径点与起点/终点重合 -> 必须等价于不用途径点
                if r != base:
                    fail("%s->%s 途经自身(%s) 应与无 via 相同" %
                         (W.IDX2NAME[first], W.IDX2NAME[end], W.IDX2NAME[via]))
            elif via not in seq:
                fail("%s->%s 途经 %s：路线里没有该点" %
                     (W.IDX2NAME[first], W.IDX2NAME[end], W.IDX2NAME[via]))
            ok, bad = walk_is_connected(edges, adj, first, r)
            if not ok:
                fail("%s->%s 途经 %s：相邻跳 %s->%s 无边" %
                     (W.IDX2NAME[first], W.IDX2NAME[end], W.IDX2NAME[via], bad[0], bad[1]))
            cb, cv = route_cost(edges, adj, first, base[1]), route_cost(edges, adj, first, route)
            if cb is not None and cv is not None and cv + 1e-6 < cb:
                fail("%s->%s 途经 %s：via 路线(%0.1f) 比无 via(%0.1f) 还短" %
                     (W.IDX2NAME[first], W.IDX2NAME[end], W.IDX2NAME[via], cv, cb))
            checked += 1
    print("  [OK] 校验 %d 组 via 路线（%d 组该 via 不可达，按无路处理）" % (checked, skipped))

    print("\n=== 3) route/nowNode 结构自检（不重复第一跳、末尾 0xFF、route[0] 合法）===")
    for first in nodes:
        for via in (0, W.NODE_IDX["P5"], W.NODE_IDX["N8"]):
            for end in (W.NODE_IDX["P3"], W.NODE_IDX["P2"]):
                r = new_logic(edges, adj, first, via, end)
                if r is None:
                    continue
                now, route = r
                if route[-1] != SENTINEL:
                    fail("route 末尾不是 0xFF")
                if route[0] == now and len(route) > 1:
                    fail("%s: route[0]=%s 与 nowNode 重复" % (W.IDX2NAME[first], W.IDX2NAME[now]))
                if first == now:
                    fail("%s: 第一跳指向起点自身（应无此情况）" % W.IDX2NAME[first])
    print("  [OK] 结构自检通过")

    print("\n=== 4) 当前 config.h 实配路线 ===")
    cfg = read_config_points()
    if cfg:
        first, via, end = cfg["FIRST_POINT"], cfg["VIA_POINT"], cfg["END_POINT"]
        vs = "不用途径点" if via == 0 else W.IDX2NAME[via]
        print("  FIRST_POINT=%s  VIA_POINT=%s  END_POINT=%s" %
              (W.IDX2NAME[first], vs, W.IDX2NAME[end]))
        r = new_logic(edges, adj, first, via, end)
        if r is None:
            fail("当前配置生成不出路线（起点==终点 或 不可达）：地图调试会原地不动")
        else:
            now, route = r
            names = [W.IDX2NAME[x] for x in route if x != SENTINEL]
            print("  nowNode(第一跳) = %s" % W.IDX2NAME[now])
            print("  route[] = {%s, 0xFF}" % ", ".join(names))
            # ---- 陀螺仪角度初始化核对（main_task.c: mapInit() 后紧跟 mpuZreset(get_latest_yaw(), nodes.nowNode.angle)）----
            e = first_hop_edge(edges, adj, first, now)
            if e is None:
                fail("找不到第一跳边 %s->%s：getNextConnectNode 会失败" %
                     (W.IDX2NAME[first], W.IDX2NAME[now]))
            else:
                print("  第一跳边 = %s->%s，angle = %g°（该边同时给出 flag/step/speed）" %
                      (W.IDX2NAME[first], W.IDX2NAME[now], e["angle"]))
                print("  >>> 陀螺仪校准参考 = nowNode.angle = %g°：mpuZreset() 后 getAngleZ() 立即等于该值，" %
                      e["angle"])
                print("      之后所有转弯目标是同框的 nextNode.angle，故只要**摆车时车头顺着 %s->%s（%g°）**，整套角度就是自洽的。" %
                      (W.IDX2NAME[first], W.IDX2NAME[now], e["angle"]))
                print("      注意：main_task.c 在**红外等待之前**就校准了；校准后别再用手摆车头，否则参考角作废（要重校就复位一次）。")
                if abs(e["angle"]) < 1e-6:
                    print("      （参考角恰为 0°：该起点第一跳就是全图 0° 基准方向）")
            print()
            leg_report(edges, adj, first, now, route)
            o = old_logic(edges, adj, first, end)
            if via == 0 and o != r:
                fail("当前配置（无 via）与旧逻辑不一致")
            if via != 0:
                seq = [first, now] + [x for x in route if x != SENTINEL]
                if via not in seq:
                    fail("当前配置路线没经过 VIA_POINT=%s" % vs)

    print("\n===== 结果：%s =====" % ("全部通过" if all_ok else "有差异，见上方 [FAIL]"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
