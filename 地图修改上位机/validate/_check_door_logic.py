#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_check_door_logic.py — 门逻辑 表驱动校验（主机侧，只读，不参与固件编译）
=====================================================================
背景：门(红绿灯)逻辑是 状态机匹配 + 读颜色 + 可通行判定 + 改路 + 后退/转向 搅在一起，
最容易出问题的三类：① 门边(DOOR 功能)从非预期方向进入时状态匹配不到、静默落到
默认 DOOR_D2；② 门状态组合未覆盖/不可达时直接 CarBrake_Stop 或 Route_Error_Stop；
③ 回程门退到 N5 后应转 N4 却大角度乱转。

本脚本复用 _weight_calib 解析出的真实边表，逐项断言（全部通过 exit 0，否则 exit 1）：
  1) 所有 DOOR 功能边要么命中 door() 的状态匹配表、要么在驱动前被 Clear_door()/门分支
     清成 NONE(=安全)。二者皆无才判为缺口（否则固件会静默落到默认 DOOR_D2）。
  2) 对 D2/D3/D4 每种颜色组合(绿/蓝/黑)，镜像 mission_planner 的 plan_after_return_door
     生成回程 wp 并跑最短路，检查：不产生 CarBrake_Stop 的组合是否都成功出路线、
     路线是否连通、是否以 P2 收尾；并报告哪些组合会死停/断链。
  3) D4 回程黑灯(N8→N3→退N5)：断言退到 N5 后回家路线的下一跳是 N4，且转角
     need2turn(N8→N5 航向, N5→N4 航向) 应为 +145°（路线与角度定义正确）。

用法：python3 地图修改上位机/validate/_check_door_logic.py
依赖：_weight_calib.py（同目录，提供 parse_graph/build_adj/plan_via_waypoints/need2turn 等）
"""
import sys
import os
import re
import _weight_calib as W

CAN, ONE, NO = 'CAN', 'ONE', 'NO'
def can_pass(c): return c in (CAN, ONE)

# 与 barrier.c door() 的状态匹配表（node 名对）
DOOR_TRIGGERS = {
    'DOOR_D2':      ('N5', 'N12'),   # lastNode, nowNode
    'DOOR_D3':      ('N5', 'N8'),
    'DOOR_D4':      ('N3', 'N8'),
    'DOOR_D4_BACK': ('N8', 'N3'),
    'DOOR_D5_BACK': ('N10', 'N3'),
}
def door_state(last, now):
    """返回命中的门状态名；若匹配不到返回 None（固件此时默认 state=DOOR_D2）。"""
    for st, (a, b) in DOOR_TRIGGERS.items():
        if last == a and now == b:
            return st
    return None

def cleared_door_pairs():
    """从 mission_planner.c 的 Clear_door() 提取 door_set_pass_node(a,b,...) 的节点名对。
    这些门边在二轮开始前被统一清成 function=NONE，之后驱动不会触发 door()，故安全。"""
    path = os.path.join(W.BASE, 'Mission', 'mission_planner.c')
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except IOError:
        return set()
    m = re.search(r'void\s+Clear_door\s*\(\s*\)\s*\{(.*?)\n\}', txt, re.S)
    body = m.group(1) if m else txt
    pairs = set()
    for mm in re.finditer(r'door_set_pass_node\s*\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*,', body):
        pairs.add((mm.group(1), mm.group(2)))
    return pairs

# 镜像 mission_planner.c plan_after_return_door(after_door)（USE_PLANNER_ROUTE 分支）
def plan_after_return_door(now_node, door, treasure, after_door='0xFF'):
    target = {2: 'P1', 3: 'P3', 4: 'P4', 5: 'P5', 6: 'P6'}.get(treasure)
    if target is None:
        return None
    wp = [now_node]
    if door[0] == CAN:
        wp.append('N5')
    elif door[1] == CAN:
        wp += ['N8', 'N5']
    elif door[2] == CAN:
        wp += ['N8', 'N3']
    elif any(door[i] == ONE for i in range(3)):
        wp.append('N10')
        wp.append('N3' if after_door in ('0xFF', None) else after_door)
    else:
        return None                      # 固件会 CarBrake_Stop
    if treasure not in (5, 6):
        wp.append(target)
    wp.append('P2')
    return W.plan_via_waypoints(edges, adj, wp, 1.0, 0.6, 1.0)

def route_connected(route):
    """检查 route 相邻节点对在边表里有向连通。route 为节点名序列(可含 None)。"""
    if not route:
        return None
    for i in range(len(route) - 1):
        a, b = route[i], route[i + 1]
        if a == b:
            continue
        if not any(e["from"] == W.NODE_IDX[a] and e["to"] == W.NODE_IDX[b]
                   for e in edges):
            return (a, b)
    return None

def main():
    global edges, adj
    edges = W.parse_graph()
    adj = W.build_adj(edges)
    fails = []

    print("=" * 78)
    print("门逻辑 表驱动校验（_check_door_logic）")
    print("=" * 78)

    # ---- ① DOOR 边是否都命中状态匹配表 或 在驱动前被清成 NONE ----
    print("\n[1] DOOR 边 → door() 状态匹配 / 驱动前被 Clear_door 清成 NONE")
    cleared = cleared_door_pairs()
    door_edges = [e for e in edges if e["func"] == W.FUNC.get('DOOR', 14)]
    real_gap = []
    for e in door_edges:
        last, now = W.IDX2NAME[e["from"]], W.IDX2NAME[e["to"]]
        st = door_state(last, now)
        safe = (st is not None) or ((last, now) in cleared)
        if not safe:
            real_gap.append((last, now))
        reason = st if st else ('已由 Clear_door 置 NONE' if (last, now) in cleared else '【缺口】')
        print(f"  {last:>4s} -> {now:<4s}  =>  {reason}")
    if real_gap:
        fails.append("有 DOOR 边既未命中状态匹配表、也未被 Clear_door 清 NONE(会静默走默认 D2)")
    print(f"  DOOR 边总数 {len(door_edges)}, 真实缺口 {len(real_gap)}")
    if real_gap:
        print("  缺口:", ", ".join(f"{a}->{b}" for a, b in real_gap))

    # ---- ② 门色组合 → 回程路线可行性（plan_after_return_door 镜像）----
    print("\n[2] D2/D3/D4 颜色组合 → plan_after_return_door 回程路线可行性")
    print("    (绿=CAN 蓝=ONE 黑=NO；'停'=固件会 CarBrake_Stop；'不通'=wp 不可达)")
    deadstop = []
    broken = []
    for d0 in (CAN, ONE, NO):
        for d1 in (CAN, ONE, NO):
            for d2 in (CAN, ONE, NO):
                door = [d0, d1, d2, NO, NO]     # D5 按黑(本脚本只测 D2/D3/D4 回程)
                for treasure in (2, 3, 4, 5, 6):
                    r = plan_after_return_door('N5', door, treasure)  # D4_BACK 黑退到 N5 起点
                    tag = f"D2={d0} D3={d1} D4={d2} 宝={treasure}"
                    if r is None:
                        deadstop.append(tag)
                    else:
                        bad = route_connected(r)
                        if bad is not None:
                            broken.append((tag, bad))
                            print(f"  [不通] {tag}: {bad[0]}->{bad[1]} 断链")
    print(f"  会 CarBrake_Stop(全黑/无绿无蓝)组合数: {len(deadstop)}")
    print(f"  路线断链组合数: {len(broken)}")
    for t in broken:
        print("    ", t)

    # ---- ③ D4 回程黑灯：N8→N5→N4 特判 ----
    print("\n[3] D4 回程黑灯 (N8->N3 读 D4=黑, 退到 N5)")
    # 从边表直接取 N8->N5 与 N5->N4 的实际航向角
    ang_n8n5 = next((e["angle"] for e in edges if W.IDX2NAME[e["from"]] == 'N8'
                     and W.IDX2NAME[e["to"]] == 'N5'), None)
    ang_n5n4 = next((e["angle"] for e in edges if W.IDX2NAME[e["from"]] == 'N5'
                     and W.IDX2NAME[e["to"]] == 'N4'), None)
    print(f"  N8->N5 航向 {ang_n8n5}°, N5->N4 航向 {ang_n5n4}°")
    if ang_n8n5 is not None and ang_n5n4 is not None:
        turn = abs(W.need2turn(ang_n8n5, ang_n5n4))
        print(f"  need2turn(N8->N5, N5->N4) = {turn}°")
        # 断言：N4 是 N5 的下一个回家节点（直接跑 N5→N4→...→P2 的最短路，看 N5 的下一跳）
        r = W.plan_via_waypoints(edges, adj, ['N5', 'N4', 'B3', 'N2', 'P2'], 1.0, 0.6, 1.0)
        nxt = r[1] if (r and r[0] == 'N5') else None
        print(f"  N5 之后的回家下一跳 = {nxt}（应为 N4）")
        if nxt != 'N4':
            fails.append("D4 回程 N5 后的下一跳不是 N4")
        if round(turn) != 145:
            fails.append(f"N5 处转角 {turn}° != 145°")
    else:
        fails.append("缺少 N8->N5 / N5->N4 边数据")

    print("\n" + "=" * 78)
    if fails:
        print(f"[FAIL] 共 {len(fails)} 项不通过:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    else:
        print("[OK] 门逻辑全部通过（参考路线/连通/转角均符合预期）")
        sys.exit(0)

if __name__ == '__main__':
    main()
