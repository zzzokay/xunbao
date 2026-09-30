# -*- coding: utf-8 -*-
"""从边表反解节点真实坐标（cm）——「能不能仿真计算」的关键实验。

思路：每条边给两个约束
    x_to - x_from ≈ step * cos(θ)
    y_to - y_from ≈ step * sin(θ)
θ = 边表 angle。全部有向边叠起来 → 超定线性方程组 → 最小二乘解 (x,y)。
再固定一个锚点 + 一个旋转基准消除规范自由度，看残差有多大。

残差小 ⇒ 边表是自洽的真实几何 ⇒ 可以拿坐标算补偿。
残差大 ⇒ 边表角度/长度本身不相容 ⇒ 纯几何仿真注定算不准。
"""
import sys
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "map_editor"))
import map_model as M  # noqa: E402


def solve_ls(A, b, n):
    """最小二乘 A x = b（法方程 + 高斯消元），A: list of list, b: list。返回 x。"""
    m = len(A)
    # 法方程 N = A^T A, r = A^T b
    N = [[0.0] * n for _ in range(n)]
    r = [0.0] * n
    for i in range(m):
        Ai = A[i]
        for p in range(n):
            ap = Ai[p]
            if ap == 0.0:
                continue
            r[p] += ap * b[i]
            Np = N[p]
            for q in range(p, n):
                if Ai[q]:
                    Np[q] += ap * Ai[q]
    for p in range(n):
        for q in range(p):
            N[p][q] = N[q][p]
    # 高斯消元（带部分主元）
    for c in range(n):
        piv = max(range(c, n), key=lambda rr: abs(N[rr][c]))
        if abs(N[piv][c]) < 1e-12:
            continue
        N[c], N[piv] = N[piv], N[c]
        r[c], r[piv] = r[piv], r[c]
        pv = N[c][c]
        for q in range(c, n):
            N[c][q] /= pv
        r[c] /= pv
        for rr in range(n):
            if rr != c and N[rr][c]:
                f = N[rr][c]
                for q in range(c, n):
                    N[rr][q] -= f * N[c][q]
                r[rr] -= f * r[c]
    return r


m = M.MapModel.load_from_sources()
names = m.names()
idx = {n: i for i, n in enumerate(names)}

# 只用"可靠"边：func 为 NONE/DOOR（平地直线段）、step>0、angle 可求
use = []
for e in m.edges:
    a = m.ang(e)
    s = m.step(e)
    if a is None or not s or s <= 0:
        continue
    use.append((e.frm, e.to, a, s, e.func))

# 未知：x_0..x_{n-1}, y_0..y_{n-1}，但固定 x[N1]=0, y[N1]=0（锚点），
# 以及 x[C6]=step(C6→N19)*cos(...) 之类不需要 —— 用"两个参考边"消自由度更稳：
# 简化：锚点 N1=(0,0)，并要求 x 轴沿 B1→N1 的反方向（即把 N1 的角度基准转正）。
# 这里先只做锚点，另外把一条基准边的方向硬塞进去。
anchor = "N1"
n2 = 2 * len(names)
A, b = [], []


def add(frm, to, adx, ady, bdx, bdy):
    row = [0.0] * n2
    row[2 * idx[to]] += adx
    row[2 * idx[frm]] -= adx
    A.append(row[:])
    b.append(bdx)
    row = [0.0] * n2
    row[2 * idx[to] + 1] += ady
    row[2 * idx[frm] + 1] -= ady
    A.append(row[:])
    b.append(bdy)


for (frm, to, a, s, fn) in use:
    dx = s * math.cos(math.radians(a))
    dy = s * math.sin(math.radians(a))
    add(frm, to, 1, 1, dx, dy)

# 锚点（硬约束，用大权重）
W = 1e4
row = [0.0] * n2
row[2 * idx[anchor]] = W
A.append(row)
b.append(0.0)
row = [0.0] * n2
row[2 * idx[anchor] + 1] = W
A.append(row)
b.append(0.0)

sol = solve_ls(A, b, n2)
XY = {nm: (sol[2 * i], sol[2 * i + 1]) for i, nm in enumerate(names)}

# 残差
res = []
for (frm, to, a, s, fn) in use:
    px, py = XY[frm]
    qx, qy = XY[to]
    lx, ly = qx - px, qy - py
    len_err = math.hypot(lx, ly) - s
    ang_err = math.degrees(math.atan2(ly, lx)) - a
    while ang_err > 180:
        ang_err -= 360
    while ang_err <= -180:
        ang_err += 360
    res.append((frm, to, s, fn, len_err, ang_err))

errs = [abs(r[4]) for r in res]
print("用 %d 条有向边解 %d 个节点坐标（锚点 %s=(0,0)）" % (len(use), len(names), anchor))
print()
print("长度残差 |解出长度 - 表step| ： 中位 %.1f cm  均值 %.1f cm  最大 %.1f cm"
      % (sorted(errs)[len(errs) // 2], sum(errs) / len(errs), max(errs)))
print("   <3cm 的边：%d/%d   <10cm：%d/%d   >30cm：%d/%d"
      % (sum(1 for x in errs if x < 3), len(errs),
         sum(1 for x in errs if x < 10), len(errs),
         sum(1 for x in errs if x > 30), len(errs)))
print()
print("残差最大的 15 条：")
print("%-6s %-6s %6s %-10s %10s %9s" % ("from", "to", "step", "func", "长度误差", "角度误差"))
for r in sorted(res, key=lambda r: -abs(r[4]))[:15]:
    print("%-6s %-6s %6.0f %-10s %+10.1f %+9.1f" % (r[0], r[1], r[2], r[3], r[4], r[5]))

# 输出解出的坐标（按 y 从小到大）
print()
print("解出的节点坐标（cm，锚点 N1=(0,0)，未定朝向）：")
for nm in sorted(names, key=lambda n: -XY[n][1]):
    print("  %-5s (%8.1f, %8.1f)" % (nm, XY[nm][0], XY[nm][1]))
