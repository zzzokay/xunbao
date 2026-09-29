#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_check_door_perm.py — 门回程"边禁用 + 极简必经点"表驱动校验（主机侧，只读，不进固件）
=====================================================================================
背景：第一轮门回程原本是 12 条手写穷举路线（mission_planner.c: update_route_by_door_1~4），
      根因是"规划器不知道哪扇门现在能过"，只能在代码里把回程路线一条条写死。

本脚本把**改造前的 12 条手写路线当标准答案（golden）**，断言下面这个模型能逐字复现它们：

    1) door() 门口读灯后，先把【整个门区 8 条边】全部禁用（回程不再进门区，防穿门掉头）；
    2) 只有 door_2 那一种情形例外：额外放行 N8->N3 ——车必须从 N8 经 D4 退回 N3 重读 D4；
    3) 然后一句 wp = {当前节点, [宝物平台], P2} 交给最短路。

断言项（全部通过 exit 0，否则 exit 1）：
  [1] 门区 8 条边在边表里都存在（缺边说明 NAV_EDGE_COUNT/边表改动漏了门边）
  [2] 12 个组合（start × treasure）的最短路输出 == golden 手写路线（逐字比对）
  [3] 改造前还能顺便核对：从 mission_planner.c 现存的 12 条数组字面量转录是否与 golden 一致
      （改造后数组已删，本项自动跳过并提示）

用法：python3 地图修改上位机/validate/_check_door_perm.py
依赖：_weight_calib.py（同目录，提供 parse_graph/build_adj/plan_via_waypoints/NODE_IDX 等）
"""
import sys
import collections
import _weight_calib as W

# 与 nav_planner.h 的权重一致（镜像 C 的 NAV_W_*）
W_LEN, W_TURN, W_OBS = 1.0, 0.6, 1.0

# 门区 8 条通行边（4 对 × 2 方向）——与 mission_planner.c 的 door_block_all() / Clear_door() 同一组
DOOR_ZONE = [("N5", "N12"), ("N12", "N5"),
             ("N5", "N8"),  ("N8", "N5"),
             ("N3", "N8"),  ("N8", "N3"),
             ("N3", "N10"), ("N10", "N3")]

# treasure -> 回程前要绕去取的宝物平台（5/6 在东区，回程直接回家）
TREASURE_PF = {2: "P1", 3: "P3", 4: "P4"}

# ---- golden：改造前 update_route_by_door_* 的手写数组（不含起点节点，栈内顺序即执行顺序）----
# door_1 与 door_3 被调用前 nodes.nowNode 都是 N3（分别来自 D5 绿、D4 回程绿），数组逐字相同。
GOLDEN = []
for t, want in ((5, "N4 B3 N2 P2"),
                (3, "P3 N3 N4 B3 N2 P2"),
                (4, "N4 N5 N6 P4 N6 N5 N4 B3 N2 P2"),
                (2, "N4 B2 N1 P1 N1 B1 N2 P2")):
    GOLDEN.append(("door_1(≡door_3)", "N3", t, False, want))
for t, want in ((5, "N3 N4 B3 N2 P2"),
                (3, "N3 P3 N3 N4 B3 N2 P2"),
                (4, "N3 N4 N5 N6 P4 N6 N5 N4 B3 N2 P2"),
                (2, "N3 N4 B2 N1 P1 N1 B1 N2 P2")):
    GOLDEN.append(("door_2", "N8", t, True, want))     # True = 放行 N8->N3（退回去重读 D4）
for t, want in ((5, "N4 B3 N2 P2"),
                (3, "N4 N3 P3 N3 N4 B3 N2 P2"),
                (4, "N6 P4 N6 N5 N4 B3 N2 P2"),
                (2, "N4 B2 N1 P1 N1 B1 N2 P2")):
    GOLDEN.append(("door_4", "N5", t, False, want))


def adj_with_perms(edges, allow_N8_N3):
    """镜像 door_block_all() + 可选放行 N8->N3：返回剔除被禁边后的邻接表。"""
    blocked = {(W.NODE_IDX[a], W.NODE_IDX[b]) for a, b in DOOR_ZONE}
    if allow_N8_N3:
        blocked.discard((W.NODE_IDX["N8"], W.NODE_IDX["N3"]))
    adj = collections.defaultdict(list)
    for i, e in enumerate(edges):
        if (e["from"], e["to"]) in blocked:
            continue
        adj[e["from"]].append(i)
    return adj


def golden_connectivity(edges):
    """golden 自检：每条 golden 的相邻节点对都必须在边表里有向连通。
    （能挡住"golden 里节点名打错"这类笔误；改造后 golden 是本脚本唯一的真值来源，
      所以这项自检要长期保留。）"""
    bad = []
    for name, start, t, allow, want in GOLDEN:
        seq = [start] + want.split()
        for a, b in zip(seq, seq[1:]):
            if not any(e["from"] == W.NODE_IDX[a] and e["to"] == W.NODE_IDX[b] for e in edges):
                bad.append(f"{name} t={t}: {a}->{b} 无边")
    return bad


def main():
    edges = W.parse_graph()
    fails = []
    print("=" * 78)
    print("门回程 边禁用 + 极简必经点 校验（_check_door_perm）")
    print("=" * 78)

    # [1] 门区 8 条边存在性
    have = {(W.IDX2NAME[e["from"]], W.IDX2NAME[e["to"]]) for e in edges}
    miss = [p for p in DOOR_ZONE if p not in have]
    print("\n[1] 门区 8 条边存在性")
    for a, b in DOOR_ZONE:
        print(f"  {a:>4s} -> {b:<4s}  {'OK' if (a, b) in have else '【缺边】'}")
    if miss:
        fails.append(f"门区边缺失: {miss}")
    print(f"  存在 {len(DOOR_ZONE) - len(miss)}/8")

    # [2] 12 组合逐字复现
    print("\n[2] 12 组合：wp={当前节点,[宝物平台],P2} + 门区全禁（door_2 放行 N8->N3）")
    ok = 0
    for name, start, t, allow, want in GOLDEN:
        adj = adj_with_perms(edges, allow)
        wps = [start] + ([TREASURE_PF[t]] if t in TREASURE_PF else []) + ["P2"]
        got = W.plan_via_waypoints(edges, adj, wps, W_LEN, W_TURN, W_OBS)
        got_s = " ".join(got[1:]) if got else "N/A"      # 去掉起点，与手写数组同格式
        good = (got_s == want)
        ok += good
        print(f"  [{'OK ' if good else 'DIF'}] {name:<16s} t={t} wp={','.join(wps):<14s} "
              f"{'' if good else f'期望={want} 实际={got_s}'}")
    print(f"  复现 {ok}/{len(GOLDEN)}")
    if ok != len(GOLDEN):
        fails.append(f"只复现 {ok}/{len(GOLDEN)} 个组合")

    # [3] golden 连通性自检
    print("\n[3] golden 自检：相邻节点对在边表中有向连通")
    bad = golden_connectivity(edges)
    if bad:
        for b in bad:
            print("  [DIF] " + b)
        fails.append(f"{len(bad)} 处 golden 相邻节点无边")
    else:
        segs = sum(len(w.split()) for *_, w in GOLDEN)
        print(f"  {len(GOLDEN)} 条 golden 共 {segs} 段，全部连通")

    print("\n" + "=" * 78)
    if fails:
        print(f"[FAIL] 共 {len(fails)} 项不通过:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("[OK] 门回程 12/12 复现通过（边禁用 + 极简 wp == 原手写穷举路线）")
    sys.exit(0)


if __name__ == "__main__":
    main()
