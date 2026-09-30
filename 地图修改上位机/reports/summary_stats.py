# -*- coding: utf-8 -*-
"""最终汇总：step 分布 / 路口-补偿关系 / 门槛 / 坐标表落盘。"""
import sys
import math
import os
import json
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "map_editor"))
import map_model as M  # noqa: E402

m = M.MapModel.load_from_sources()
names = m.names()
idx = {n: i for i, n in enumerate(names)}

# ---------- step 分布 ----------
steps = sorted(m.step(e) for e in m.edges)
print("[S1] step 分布（%d 条边）：min %g  p10 %g  中位 %g  p90 %g  max %g"
      % (len(steps), steps[0], steps[len(steps) // 10], st.median(steps),
         steps[9 * len(steps) // 10], steps[-1]))
tiny = [(e.frm, e.to, m.step(e), e.func) for e in m.edges if (m.step(e) or 0) <= 18]
print("[S2] step<=18cm 的边：%d 条（0.7×step 里程门槛会提前放行）" % len(tiny))
for t in sorted(tiny, key=lambda t: t[2]):
    print("      %-5s→%-5s step=%-4g func=%s" % t)

# ---------- 路口 vs 补偿 ----------
deg = {}
for n in names:
    deg[n] = len(m.edges_of(n, True)) + len(m.edges_of(n, False))
tbl_nodes = {r["now"] for r in m.turn["stop"]} | {r["now"] for r in m.turn["gyro"]}
print("[J1] 两张表涉及的中转节点 %d 个：%s"
      % (len(tbl_nodes), ", ".join("%s(deg=%d)" % (n, deg[n]) for n in sorted(tbl_nodes))))
print("     其中 deg<=2（叶/端点）的：%s"
      % (", ".join(n for n in sorted(tbl_nodes) if deg[n] <= 2) or "无"))
junc = [n for n in names if deg[n] >= 8]
print("[J2] 主干枢纽（deg>=8）：%s" % ", ".join("%s(%d)" % (n, deg[n]) for n in junc))
print("     其中被补偿表覆盖？%s"
      % ", ".join("%s:%s" % (n, "有" if n in tbl_nodes else "无") for n in junc))

# ---------- 反解坐标（复用第二份脚本口径）----------
segs = {}
for e in m.edges:
    segs.setdefault(tuple(sorted((e.frm, e.to))), []).append(e)
seg_len = {}
for key, es in segs.items():
    cand = [m.step(e) for e in es if e.func == "NONE" and m.step(e)] or \
           [m.step(e) for e in es if m.step(e)]
    if cand:
        seg_len[key] = st.median(cand)

A, b = [], []


def add_eq(frm, to, dx, dy):
    row = [0.0] * (2 * len(names)); row[2 * idx[to]] += 1; row[2 * idx[frm]] -= 1
    A.append(row); b.append(dx)
    row = [0.0] * (2 * len(names)); row[2 * idx[to] + 1] += 1; row[2 * idx[frm] + 1] -= 1
    A.append(row); b.append(dy)


for e in m.edges:
    L = seg_len.get(tuple(sorted((e.frm, e.to))))
    a = m.ang(e)
    if L and a is not None:
        add_eq(e.frm, e.to, L * math.cos(math.radians(a)), L * math.sin(math.radians(a)))
W = 1e4
for i in (2 * idx["N1"], 2 * idx["N1"] + 1):
    row = [0.0] * (2 * len(names)); row[i] = W
    A.append(row); b.append(0.0)


def solve_ls(A, b, n):
    N = [[0.0] * n for _ in range(n)]; r = [0.0] * n
    for Ai in A:
        for p in range(n):
            ap = Ai[p]
            if not ap:
                continue
            r[p] += ap * b[A.index(Ai)] if False else 0     # placeholder
    # 正式实现
    N = [[0.0] * n for _ in range(n)]; r = [0.0] * n
    for i in range(len(A)):
        Ai = A[i]
        for p in range(n):
            ap = Ai[p]
            if not ap:
                continue
            r[p] += ap * b[i]
            for q in range(p, n):
                if Ai[q]:
                    N[p][q] += ap * Ai[q]
    for p in range(n):
        for q in range(p):
            N[p][q] = N[q][p]
    for c in range(n):
        piv = max(range(c, n), key=lambda rr: abs(N[rr][c]))
        if abs(N[piv][c]) < 1e-12:
            continue
        N[c], N[piv] = N[piv], N[c]; r[c], r[piv] = r[piv], r[c]
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


sol = solve_ls(A, b, 2 * len(names))
XY = {nm: (round(sol[2 * i], 1), round(sol[2 * i + 1], 1)) for i, nm in enumerate(names)}
out = os.path.join(HERE, "node_coords_solved.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"note": "由边表 angle+step 反解（锚点 N1=(0,0)，朝向未定）；单位 cm",
               "anchor": "N1", "coords": XY}, f, ensure_ascii=False, indent=1)
print("[C1] 反解坐标已写入 %s（%d 个节点）" % (os.path.basename(out), len(XY)))
