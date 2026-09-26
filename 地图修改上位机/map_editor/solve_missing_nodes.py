# -*- coding: utf-8 -*-
"""临时 v7：快速版联合求解（预抽约束，避免重复 O(E) 扫描）+ 回归检查。"""
import os
import sys
import math
import random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_model as M

m = M.MapModel.load_from_sources()
seed = M.load_seed_positions()
UNK = list(M.MISSING_SEED)
P = {n.name: (n.x, n.y) for n in m.nodes}


def dirs_of(e):
    ang = m.ang(e)
    if ang is None:
        return None
    r = math.radians(ang)
    ux, uy = math.sin(r), -math.cos(r)
    return (ux, uy, -ux, -uy)


# 预抽：(a, b, ux, uy, -ux, -uy)
CONS = []
for e in m.edges:
    d = dirs_of(e)
    if d:
        CONS.append((e.frm, e.to, d))


def dl(p, a, d):
    dx, dy = p[0] - a[0], p[1] - a[1]
    return min(abs(dx * d[1] - dy * d[0]), abs(dx * d[3] - dy * d[2]))


def make_cost(unknown, fixed, reg):
    rel = [(a, b, d) for (a, b, d) in CONS if a in unknown or b in unknown]

    def C(pp):
        c = 0.0
        for a, b, d in rel:
            pa = pp[a] if a in unknown else fixed[a]
            pb = pp[b] if b in unknown else fixed[b]
            e = dl(pb, pa, d)
            c += e * e
        for k in unknown:
            s = fixed[k]
            c += reg * ((pp[k][0] - s[0]) ** 2 + (pp[k][1] - s[1]) ** 2)
        return c
    return C, len(rel)


def anneal(unknown, fixed, start, reg, iters, sd):
    C, nrel = make_cost(unknown, fixed, reg)
    pos = {k: start[k] for k in unknown}
    bc = C(pos)
    random.seed(sd)
    step = 45.0
    for it in range(iters):
        if it % (max(1, iters // 10)) == 0 and it:
            step *= 0.65
        k = random.choice(unknown)
        cand = dict(pos)
        cand[k] = (pos[k][0] + random.uniform(-step, step),
                   pos[k][1] + random.uniform(-step, step))
        c = C(cand)
        if c < bc:
            pos, bc = cand, c
    for _ in range(150):
        imp = False
        for k in unknown:
            for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                cand = dict(pos)
                cand[k] = (pos[k][0] + dx, pos[k][1] + dy)
                c = C(cand)
                if c < bc - 1e-9:
                    pos, bc, imp = cand, c, True
        if not imp:
            break
    return pos, nrel


print("=== 回归：把每个已知节点当未知解一遍，看解回来离图上位置多远 ===")
# 只对"确实有 seed 坐标"的节点做（seed 里有 D1/D2 等图上没画的点，跳过）
known = [n for n in sorted(seed.keys()) if n in P and n not in UNK]
errs = []
for name in known:
    pos, nrel = anneal([name], P, {name: P[name]}, reg=1.0, iters=12000, sd=5)
    ex, ey = pos[name]
    errs.append((math.hypot(ex - P[name][0], ey - P[name][1]), name, nrel))
errs.sort()
print("  样本 %d：误差中位 %.1f px / 均值 %.1f px / 最大 %.1f px"
      % (len(errs), errs[len(errs) // 2][0], sum(e for e, _, _ in errs) / len(errs),
         errs[-1][0]))
print("  最差 6:", ", ".join("%s=%.0f" % (n, e) for e, n, _ in errs[-6:]))
print("  → 这就是「节点图本身的不准程度」的量级\n")

print("=== 联合求解 6 个未标注节点 ===")
START = {k: P[k] for k in UNK}
pos, nrel = anneal(UNK, P, START, reg=0.5, iters=250000, sd=99)

before, after = [], []
for a, b, d in [(a, b, d) for (a, b, d) in CONS if a in UNK or b in UNK]:
    before.append(dl(START.get(b, P[b]), START.get(a, P[a]), d))
    after.append(dl(pos.get(b, P[b]), pos.get(a, P[a]), d))
before.sort(); after.sort()
print("  相关边 %d 条" % nrel)
print("  求解前: 中位 %.1f 均值 %.1f 最大 %.1f px"
      % (before[len(before)//2], sum(before)/len(before), before[-1]))
print("  求解后: 中位 %.1f 均值 %.1f 最大 %.1f px"
      % (after[len(after)//2], sum(after)/len(after), after[-1]))
print()
print("%-5s %-18s %-18s %s" % ("节点", "原估计", "求解", "位移"))
for k in UNK:
    print("%-5s (%6.0f,%6.0f)   (%6.0f,%6.0f)   %5.0fpx"
          % (k, START[k][0], START[k][1], pos[k][0], pos[k][1],
             math.hypot(pos[k][0] - START[k][0], pos[k][1] - START[k][1])))
print("\n=== 粘贴用 ===")
for k in UNK:
    print("    '%s': (%.0f, %.0f)," % (k, round(pos[k][0]), round(pos[k][1])))
