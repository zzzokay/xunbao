# -*- coding: utf-8 -*-
"""第二轮：去重成"无向段"后再解坐标，并与节点图做 Procrustes 对齐。

结论面向：
  1) 边表角度列是否自洽（方向场）
  2) 长度列 step 是不是真实长度（双向是否对称）
  3) 反解出的真实坐标 vs 节点图像素坐标 —— 节点图到底是不是按比例画的
"""
import sys
import math
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "map_editor"))
import map_model as M  # noqa: E402

m = M.MapModel.load_from_sources()
names = m.names()
idx = {n: i for i, n in enumerate(names)}

# ---- 1. 无向段 + 方向场自检 ----
segs = {}
for e in m.edges:
    key = tuple(sorted((e.frm, e.to)))
    segs.setdefault(key, []).append(e)

ang_ok = ang_bad = 0
for key, es in segs.items():
    if len(es) == 2:
        d = abs(M.need2turn(m.ang(es[0]), m.ang(es[1])))
        if abs(d - 180) <= 10:
            ang_ok += 1
        else:
            ang_bad += 1
print("[1] 方向场自洽性：双向段 %d，两条边角度互为反向(±180°) 的 %d，不符 %d"
      % (ang_ok + ang_bad, ang_ok, ang_bad))

# ---- 2. 长度对称性 ----
clean_pairs = [es for es in segs.values()
               if len(es) == 2 and all(e.func == "NONE" for e in es)]
asym = [(es, abs(m.step(es[0]) - m.step(es[1]))) for es in clean_pairs]
print("[2] 只看 func 都是 NONE 的双向段（%d 条）：step 不等的有 %d 条，中位差 %.1f cm，最大 %.0f cm"
      % (len(clean_pairs), sum(1 for p, d in asym if d > 0.5),
         st.median([d for p, d in asym]), max(d for p, d in asym)))

# ---- 3. 无向段长度（只取 func==NONE 的边；两边都有取中位）----
seg_len = {}
for key, es in segs.items():
    cand = [m.step(e) for e in es if e.func == "NONE" and m.step(e)]
    if not cand:
        cand = [m.step(e) for e in es if m.step(e)]
    if cand:
        seg_len[key] = st.median(cand)

# ---- 4. 解坐标（只用长度来源干净的段）----
A, b = [], []


def add_eq(frm, to, dx, dy):
    row = [0.0] * (2 * len(names))
    row[2 * idx[to]] += 1
    row[2 * idx[frm]] -= 1
    A.append(row)
    b.append(dx)
    row = [0.0] * (2 * len(names))
    row[2 * idx[to] + 1] += 1
    row[2 * idx[frm] + 1] -= 1
    A.append(row)
    b.append(dy)


used = 0
for e in m.edges:
    key = tuple(sorted((e.frm, e.to)))
    L = seg_len.get(key)
    a = m.ang(e)
    if not L or a is None:
        continue
    add_eq(e.frm, e.to, L * math.cos(math.radians(a)), L * math.sin(math.radians(a)))
    used += 1

# 锚点 + 朝向基准（N1=(0,0)，且 N1→P1 沿 +x）
W = 1e4
for val, i in ((0.0, 2 * idx["N1"]), (0.0, 2 * idx["N1"] + 1)):
    row = [0.0] * (2 * len(names))
    row[i] = W
    A.append(row)
    b.append(val)


def solve_ls(A, b, n):
    N = [[0.0] * n for _ in range(n)]
    r = [0.0] * n
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


sol = solve_ls(A, b, 2 * len(names))
XY = {nm: (sol[2 * i], sol[2 * i + 1]) for i, nm in enumerate(names)}

res = []
for key, L in seg_len.items():
    a, c = key
    ex = math.hypot(XY[c][0] - XY[a][0], XY[c][1] - XY[a][1]) - L
    res.append(abs(ex))
print("[3] 解出 %d 个节点；段长残差 中位 %.1f cm 均值 %.1f cm 最大 %.0f cm（%d 段）"
      % (len(names), st.median(res), st.mean(res), max(res), len(seg_len)))

# ---- 5. Procrustes 对齐节点图（复平面相似变换 G ≈ c·S + t，允许旋转+缩放、不允许镜像）----
import cmath

P = {n.name: (n.x, n.y) for n in m.nodes}
common = [n for n in names if n in P]
S = [complex(XY[n][0], XY[n][1]) for n in common]        # 反解坐标，cm
G = [complex(P[n][0], -P[n][1]) for n in common]         # 节点图，px（y 取反成数学系）
ms = sum(S) / len(S)
mg = sum(G) / len(G)
a = [x - ms for x in S]
bb = [x - mg for x in G]
c = sum(x.conjugate() * y for x, y in zip(a, bb)) / sum((x.conjugate() * x).real for x in a)
scale = abs(c)
rot = math.degrees(cmath.phase(c))

print("[4] 节点图 ↔ 反解坐标 相似变换：%.4f px/cm（1px = %.2f cm），旋转 %.1f°"
      % (scale, 1 / scale if scale else 0, rot))
err_cm = [abs(c * x - y) / scale for x, y in zip(a, bb)]
print("    对齐后每节点位置误差（cm）：中位 %.1f  均值 %.1f  最大 %.0f"
      % (st.median(err_cm), st.mean(err_cm), max(err_cm)))
_pr = sorted(zip(err_cm, common))
print("    最准 8 个：" + ", ".join("%s(%.0f)" % (n, e) for e, n in _pr[:8]))
print("    最差 8 个：" + ", ".join("%s(%.0f)" % (n, e) for e, n in _pr[::-1][:8]))

print("[4b] 反解坐标范围：x %.0f~%.0f cm，y %.0f~%.0f cm"
      % (min(v[0] for v in XY.values()), max(v[0] for v in XY.values()),
         min(v[1] for v in XY.values()), max(v[1] for v in XY.values())))
print("     规则图标注：宽 3500+3000+3500 = 1000 cm")

# ---- 6. px/step 的离散度（节点图非等比例的直接证据）----
ratios = []
for e in m.edges:
    s = m.step(e)
    if not s or e.frm not in P or e.to not in P:
        continue
    pl = math.hypot(P[e.to][0] - P[e.frm][0], P[e.to][1] - P[e.frm][1])
    ratios.append(pl / s)
ratios.sort()
print("[5] px/step 分布：min %.2f  p25 %.2f  中位 %.2f  p75 %.2f  max %.2f（跨度 %.0f 倍）"
      % (ratios[0], ratios[len(ratios) // 4], st.median(ratios),
         ratios[3 * len(ratios) // 4], ratios[-1], ratios[-1] / ratios[0]))
