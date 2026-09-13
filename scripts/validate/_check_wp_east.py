#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_check_wp_east.py — 过门后（东区）必经点"精简 vs 全锚点"等价性回归（主机侧，只读，不进固件）
=====================================================================================
背景：二轮巡游段与第一轮 stageAB 段原先在 wp 里写了不少环上 N 节点
      （巡游尾巴 N10/N12、进门第二个门节点、回程第二跳 N3/N5、stageAB 中间 N12/N10、
        以及 stageAB 尾部出口锚点 C9/N20）。
      这些 N 多数是"冗余锚点"：删掉后最短路自己也会走它们。
      2026-09-12 做过轮精简，本脚本把"精简后的 wp"与"写全锚点的旧 wp"锁死。

断言项（全部通过 exit 0，否则 exit 1）：
  [1] 二轮：所有"可达门状态组合 × 宝物(6/非6)"下，精简 wp 路线 == 旧 wp 路线（逐字节）
  [2] 第一轮 stageAB：4 种 A/B 组合 × 3 种起始节点(N12/N8/N3)
      ① 删中间 N（N12/N10）后路线必须**逐字节不变**；
      ② 删尾部出口锚点 C9/N20 后只允许"少最后一个节点"，路径本身必须完全一致
         —— 这是"平台交接"成立的前提：平台出口锚点原本负责给 nodes.nextNode 兜底，
            现在改由 plan_treasure_return() 显式把 nextNode 对齐到"出平台第一跳"。
            ⚠️ 只删 C9/N20 而不做该交接修正 → 平台推进时 nowNode/nextNode 错位 →
               getNextConnectNode 找不到边 → Route_Error_Stop 死停车（状态机仿真 4/4 复现）。

用法：python3 scripts/validate/_check_wp_east.py
依赖：_weight_calib.py（同目录，提供 parse_graph/build_adj/plan_via_waypoints/NODE_IDX）
注意：⚠️ 这些"冗余"结论是在**当前权重模型**下成立的（NAV_W_TURN / 障碍表 / 门惩罚）。
      动权重后必须重跑本脚本 + _weight_calib.py，否则可能悄悄改路。
"""
import sys
import itertools
import _weight_calib as W

W_LEN, W_TURN, W_OBS = 1.0, 0.6, 1.0     # 与 nav_planner.h 的 NAV_W_* 一致

CAN, ONE, NO = "CAN", "ONE", "NO"        # 对应 CAN_PASS / ONE_WAY_PASS / NO_PASS

ROUND2_PRE = ["N2", "P1", "P3", "P4", "N5"]   # 二轮固定前段（含起点 N2）
TAIL = ["P2"]


def route(wps):
    return W.plan_via_waypoints(W.EDGES, W.ADJ, wps, W_LEN, W_TURN, W_OBS)


# ---------------- 二轮：旧 wp（写全 N 锚点，精简前的版本） ----------------
def wp_round2_old(dp, p6_first):
    d2, d3, d4, d5 = dp
    if d2 == CAN:
        en = ["N12"]
    elif d3 == CAN:
        en = ["N8"] + ([] if p6_first else ["N12"])
    elif d4 == CAN:
        en = ["N3", "N8"] + ([] if p6_first else ["N12"])
    else:
        return None
    tour = (["P6", "P8", "P7", "P5", "N12"] if p6_first
            else ["P5", "P7", "P8", "P6", "N10"])
    if d2 == CAN:
        rn = ["N5"]
    elif d2 == ONE and d5 == CAN:
        rn = ["N10", "N3"]
    elif d2 == ONE and d5 == NO and d4 == CAN:
        rn = ["N8", "N3"]
    elif d2 == ONE and d5 == NO and d4 == NO:
        rn = ["N8", "N5"]
    elif d2 == NO and d3 == CAN:
        rn = ["N8", "N5"]
    elif d2 == NO and d3 == ONE and d5 == CAN:
        rn = ["N10", "N3"]
    elif d2 == NO and d3 == ONE and d5 == NO:
        rn = ["N8", "N3"]
    elif d2 == NO and d3 == NO and d4 == CAN:
        rn = ["N8", "N3"]
    elif d2 == NO and d3 == NO and d4 == ONE:
        rn = ["N10", "N3"]
    else:
        return None
    return ROUND2_PRE + en + tour + rn + TAIL


# ---------------- 二轮：新 wp（当前 mission_planner.c） ----------------
def wp_round2_new(dp, p6_first):
    d2, d3, d4, d5 = dp
    if d2 == CAN:
        en = ["N12"]
    elif d3 == CAN:
        en = ["N8"]
    elif d4 == CAN:
        en = ["N3"] + (["N8"] if p6_first else [])
    else:
        return None
    tour = ["P6", "P8", "P7", "P5"] if p6_first else ["P5", "P7", "P8", "P6"]
    if d2 == CAN:
        rn = ["N5"]
    elif d2 == ONE and d5 == CAN:
        rn = ["N10"]
    elif d2 == ONE and d5 == NO and d4 == CAN:
        rn = ["N8"]
    elif d2 == ONE and d5 == NO and d4 == NO:
        rn = ["N8", "N5"]          # ⚠️ N5 不可删（删了会改穿 N3/D4）
    elif d2 == NO and d3 == CAN:
        rn = ["N8", "N5"]          # ⚠️ 同上
    elif d2 == NO and d3 == ONE and d5 == CAN:
        rn = ["N10"]
    elif d2 == NO and d3 == ONE and d5 == NO:
        rn = ["N8"]
    elif d2 == NO and d3 == NO and d4 == CAN:
        rn = ["N8"]
    elif d2 == NO and d3 == NO and d4 == ONE:
        rn = ["N10"]
    else:
        return None
    return ROUND2_PRE + en + tour + rn + TAIL


# ---------------- 第一轮 stageAB ----------------
AB_OLD = {                       # (A, B) -> 旧的 wp（除起点外）
    (5, 7): ["P5", "N12", "P7", "C9"],
    (5, 8): ["P5", "N12", "P8", "N20"],
    (6, 7): ["N10", "P6", "P7", "C9"],
    (6, 8): ["N10", "P6", "P8", "N20"],
}
AB_NEW = {                       # 现状：环上中间 N 和尾部出口锚点 C9/N20 都不写
    (5, 7): ["P5", "P7"],
    (5, 8): ["P5", "P8"],
    (6, 7): ["P6", "P7"],
    (6, 8): ["P6", "P8"],
}
AB_NO_TAIL_ANCHOR = AB_NEW       # 别名：语义 = 去掉了尾部锚点
AB_KEEP_ANCHOR = {               # 中间态：只去掉环上中间 N，保留尾部锚点（过渡态，留作对照）
    (5, 7): ["P5", "P7", "C9"],
    (5, 8): ["P5", "P8", "N20"],
    (6, 7): ["P6", "P7", "C9"],
    (6, 8): ["P6", "P8", "N20"],
}
AB_STARTS = ["N12", "N8", "N3"]  # door_set_pass_node 后 possible 的 nowNode
AB_ANCHOR = {(5, 7): "C9", (5, 8): "N20", (6, 7): "C9", (6, 8): "N20"}


def check_round2():
    print("=" * 78)
    print("[1] 二轮：精简 wp vs 旧 wp（全部可达门状态组合 × 宝物）")
    print("=" * 78)
    fails, n = [], 0
    states = [CAN, ONE, NO]
    for dp in itertools.product(states, repeat=4):
        for p6_first in (False, True):
            old = wp_round2_old(dp, p6_first)
            new = wp_round2_new(dp, p6_first)
            if old is None or new is None:
                continue                      # 该组合在 C 里直接 CarBrake_Stop，不可达
            n += 1
            if len(new) > 24:
                fails.append(f"wp 超界: {dp} 宝物{'=6' if p6_first else '≠6'} -> {len(new)} > 24")
                continue
            ra, rb = route(old), route(new)
            if ra is None or rb is None:
                fails.append(f"无路: {dp} 宝物{'=6' if p6_first else '≠6'} old_ok={ra is not None} new_ok={rb is not None}")
                continue
            if ra != rb:
                i = 0
                while i < min(len(ra), len(rb)) and ra[i] == rb[i]:
                    i += 1
                fails.append(f"路线变了: {dp} 宝物{'=6' if p6_first else '≠6'} "
                             f"第{i}节点 old={ra[max(0,i-1):i+3]} new={rb[max(0,i-1):i+3]}")
            elif not rb or rb[-1] != "P2":
                fails.append(f"结尾不是 P2: {dp} 宝物{'=6' if p6_first else '≠6'}")
    print(f"  可达组合 {n} 个，差异 {len(fails)} 个")
    for f in fails:
        print("   ❌ " + f)
    return fails, n


def check_stageAB():
    print()
    print("=" * 78)
    print("[2] 第一轮 stageAB：删中间 N / 删尾部锚点 C9·N20 后的路线关系")
    print("=" * 78)
    fails, n = [], 0
    for ab in sorted(AB_OLD):
        for st in AB_STARTS:
            n += 1
            full = route([st] + AB_OLD[ab])                 # 原版（中间 N + 尾部锚点）
            mid = route([st] + AB_KEEP_ANCHOR[ab])          # 只删中间 N
            fin = route([st] + AB_NEW[ab])                  # 现状（都删）
            tag = f"now={st} A{ab[0]}B{ab[1]}"
            if full is None or mid is None or fin is None:
                fails.append(f"无路: {tag}")
                continue
            # ① 删中间 N：路线必须逐字节不变
            if full != mid:
                fails.append(f"删中间 N 改变了路线: {tag}")
                continue
            # ② 删尾部锚点：只允许"少最后一个节点"，其余必须完全一致
            #    （这样交接才成立：plan_treasure_return() 显式把 nextNode 对齐到出平台第一跳）
            if full[:-1] != fin:
                i = 0
                while i < min(len(full), len(fin)) and full[i] == fin[i]:
                    i += 1
                fails.append(f"删尾锚点后路径本身变了(第{i}节点起): {tag} "
                             f"full={full[max(0,i-1):i+3]} fin={fin[max(0,i-1):i+3]}")
            elif full[-1] != AB_ANCHOR[ab]:
                fails.append(f"原版结尾不是出口锚点: {tag} -> {full[-1]}")
            elif fin[-1] not in ("P7", "P8"):
                fails.append(f"精简版结尾不是宝物平台: {tag} -> {fin[-1]}")
    print(f"  组合 {n} 个（4 种 A/B × 3 种起点），差异 {len(fails)} 个")
    for f in fails:
        print("   ❌ " + f)
    return fails, n


def main():
    # _weight_calib 只在使用时解析图，这里显式加载一次
    if not hasattr(W, "EDGES"):
        W.EDGES = W.parse_graph()
        W.ADJ = W.build_adj(W.EDGES)

    f1, n1 = check_round2()
    f2, n2 = check_stageAB()
    fails = f1 + f2

    print()
    print("=" * 78)
    if fails:
        print(f"[FAIL] 共 {len(fails)} 项不一致（二轮 {n1} 组合 / stageAB {n2} 组合）")
        print("       精简 wp 与全锚点 wp 不再等价——权重或边表改动后请复核本脚本注释里的取舍")
        return 1
    print(f"[OK] 全部通过：二轮 {n1} 组合逐字节等价；stageAB {n2} 组合「删中间 N 不变 + 删尾锚点只少末节点」")
    print("     ⚠️ stageAB 末节点（C9/N20）依赖 plan_treasure_return() 里的 nextNode 交接修正，改那条路径时必看本脚本顶部注释")
    return 0


if __name__ == "__main__":
    sys.exit(main())
