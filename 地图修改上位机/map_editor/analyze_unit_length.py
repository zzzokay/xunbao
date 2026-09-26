# -*- coding: utf-8 -*-
"""临时分析：节点图上"像素长度"与边表 step 的关系，用来定"单位长度"K。

问题：拖动节点时想约束"角度按表、长度 ≥ step 对应长度"。
      这要求图上像素距离 >= step * K（K = 每 cm 多少像素）。
      本脚本量出：① 现有图上像素距离 ② 每条边 step ③ 满足约束所需的 K 上界。
用完即删。
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_model as M

m = M.MapModel.load_from_sources()
rows = []
for e in m.edges:
    a, b = m.node(e.frm), m.node(e.to)
    if not a or not b:
        continue
    px = math.hypot(b.x - a.x, b.y - a.y)
    st = m.step(e)
    if st and st > 0:
        rows.append((e.frm, e.to, px, st, px / st, e.func))

rows.sort(key=lambda r: r[4])
print("图上像素距离 / step 的比值（升序）—— 这个比值就是【最多能取多大的 K】")
print("%-6s %-6s %8s %8s %10s  %s" % ("from", "to", "px", "step", "px/step", "func"))
for f, t, px, st, r, fn in rows:
    print("%-6s %-6s %8.1f %8.1f %10.3f  %s" % (f, t, px, st, r, fn))

rs = [r for *_x, r, _f in [(a, b, c, d, e2, f) for a, b, c, d, e2, f in rows]]
rs.sort()
n = len(rs)
print()
print("边总数(step>0) = %d" % n)
print("px/step 最小 = %.3f   中位 = %.3f   最大 = %.3f"
      % (rs[0], rs[n // 2], rs[-1]))

for K in (0.5, 0.884, 1.0, 1.5, 2.0, 3.0):
    bad = [(f, t, px, st) for f, t, px, st, r, fn in rows if px < st * K]
    print("  K=%-5.3f px/cm -> 违反【长度>=step*K】的边数 = %d" % (K, len(bad)))

print()
print("若取 K = 最小比值 %.3f：只有 1 条边是【刚好卡住】的临界边" % rs[0])
kmin = rs[0]
zero = [(f, t, px, st) for f, t, px, st, r, fn in rows if px < st * kmin - 1e-9]
print("  取 K=%.3f 时违反的边 = %d（应为 0）" % (kmin, len(zero)))
print()
print("=> 结论：只要 K <= %.3f，现有布局的每条边都满足【图上长度 >= step*K】。" % kmin)
print("   最小的那条是 %s->%s（px=%.1f, step=%.1f）。"
      % (rows[0][0], rows[0][1], rows[0][2], rows[0][3]))
