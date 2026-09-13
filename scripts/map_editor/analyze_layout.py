# -*- coding: utf-8 -*-
"""
analyze_layout.py — 分析「保存布局」里的节点摆放，输出可用的量化结论。

跑法（仓库根）：
    python scripts/map_editor/analyze_layout.py

产出：
  1) 你的布局 vs 出厂坐标：挪动了哪些节点、挪了多少
  2) 位置精度：图上量得出的地标，和你的坐标差多少
  3) 单位长度 K：图上px/step 的分布，给出建议 K 与"违规边"清单
  4) 角度：按「表里 angle + DRAG_ANGLE_OFFSET」与图上实际方向比，列出不一致的边
     （注意：+90° 偏移是用户明确要求的，所以判定要带上它，否则会误报"整体差90°"）
只读，不改任何东西。
"""
import os
import re
import sys
import math
import json
import statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_model as M
import map_editor as E

LAYOUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layouts", "default.json")
if not os.path.exists(LAYOUT):
    print("找不到布局文件：%s\n先在编辑器里点「保存布局」。" % LAYOUT)
    sys.exit(1)

with open(LAYOUT, encoding="utf-8") as f:
    d = json.load(f)
nodes = {n["name"]: (n["x"], n["y"]) for n in d.get("nodes", [])}
bg = d.get("background", {}) or {}
con = d.get("constraints", {}) or {}
m = M.MapModel.load_from_sources()
seed = M.load_seed_positions()
OFF = E.DRAG_ANGLE_OFFSET

# 图上量得出来的地标（原图像素，实测）
LANDMARK = {"P1": (564.5, 55.5), "P2": (1189.5, 54.5), "P3": (183.0, 239.5)}

print("=" * 76)
print("布局文件 :", LAYOUT)
print("节点 %d / 边 %d" % (len(nodes), len(d.get("edges", []))))
print("底图     : %s  rot=%s  off=(%.0f,%.0f)  scale=(%.4f,%.4f)  透明=%.2f"
      % (os.path.basename(bg.get("path", "?")), bg.get("rot"),
         bg.get("off_x", 0), bg.get("off_y", 0), bg.get("scale_x", 1),
         bg.get("scale_y", 1), bg.get("opacity", 0)))
print("约束     : 锁角度=%s 限最小长度=%s  单位长K=%.4f  旋转=%s  引导线偏移=%+.0f°"
      % (con.get("lock_angle"), con.get("enforce_min_len"),
         con.get("unit_px_per_cm", 0), con.get("rot"), OFF))
print("=" * 76)

# ---- 1) 挪动过的节点 ----
moved = []
for name, (x, y) in nodes.items():
    if name in seed:
        dist = math.hypot(x - seed[name][0], y - seed[name][1])
        if dist > 5:
            moved.append((dist, name, seed[name], (x, y)))
moved.sort(reverse=True)
print("\n【1】相对出厂坐标挪动过的节点（>5px）：%d 个" % len(moved))
for dist, name, s, n in moved[:15]:
    tag = "（图上没画，坐标本来就是估的）" if name in M.MISSING_SEED else ""
    print("   %-5s (%6.0f,%6.0f) → (%6.0f,%6.0f)   移了 %5.0fpx %s"
          % (name, s[0], s[1], n[0], n[1], dist, tag))
if len(moved) > 15:
    print("   ...（共 %d 个）" % len(moved))

# ---- 2) 位置精度 ----
print("\n【2】位置精度（对照图上实测地标，原图像素）")
for name, lm in LANDMARK.items():
    if name in nodes:
        x, y = nodes[name]
        print("   %-4s 你的(%6.0f,%6.0f)  图上(%6.0f,%6.0f)  差(%+.0f,%+.0f)"
              % (name, x, y, lm[0], lm[1], x - lm[0], y - lm[1]))
n3, n5, n8 = nodes.get("N3"), nodes.get("N5"), nodes.get("N8")
if n3 and n5 and n8:
    print("   N3→N5  Δ=(%+.0f,%+.0f)   图上 Δ=(+462,+0)" % (n5[0] - n3[0], n5[1] - n3[1]))
    print("   N3→N8  Δ=(%+.0f,%+.0f)   图上 Δ≈(+232,+222)" % (n8[0] - n3[0], n8[1] - n3[1]))

# ---- 3) 单位长度 K ----
pairs = []
for e in m.edges:
    a, b = nodes.get(e.frm), nodes.get(e.to)
    st = m.step(e)
    if not a or not b or not st or st <= 0:
        continue
    dist = math.hypot(b[0] - a[0], b[1] - a[1])
    if dist >= 5:
        pairs.append((dist, st, e.frm, e.to, dist / st, e.func))
ratios = sorted(p[4] for p in pairs)
K = con.get("unit_px_per_cm", 0.884)
print("\n【3】单位长度 K = 图上px ÷ step(cm)")
print("   样本 %d 条；比值 最小 %.3f  中位 %.3f" % (len(pairs), ratios[0],
                                                statistics.median(ratios)))
print("   当前 K = %.3f；理论最大可行 K = %.3f（由最紧的边决定）" % (K, ratios[0]))
print("   不同 K 下「图上长度 < step*K」的边数：")
for k in (0.3, 0.5, 0.63, 0.7, 0.884, 1.0, 1.5):
    bad = sum(1 for p in pairs if p[4] < k)
    print("      K=%-6.3f → %3d / %d %s" % (k, bad, len(pairs),
                                            "  ← 当前" if abs(k - K) < 1e-6 else ""))
viol = sorted([p for p in pairs if p[4] < K], key=lambda p: p[4])
print("   当前 K 下不满足长度约束的边（编辑器会标红）：%d 条" % len(viol))
for dist, st, frm, to, r, fn in viol:
    print("      %-6s→%-6s 图上%6.0fpx  需≥%6.0fpx (step=%6.0f)  %s"
          % (frm, to, dist, st * K, st, fn))

# ---- 4) 角度（带 +90° 引导线偏移）----
good = []
bad = []
for e in m.edges:
    a, b = nodes.get(e.frm), nodes.get(e.to)
    ang = m.ang(e)
    if not a or not b or ang is None:
        continue
    dx, dy = b[0] - a[0], b[1] - a[1]
    if math.hypot(dx, dy) < 40:
        continue
    real = math.degrees(math.atan2(dx, -dy))
    diff = (real - (ang + OFF)) % 360.0
    if diff > 180:
        diff -= 360
    dev = min(abs(diff), abs(abs(diff) - 180))
    (good if dev <= 15 else bad).append((dev, e.frm, e.to, ang, real))
print("\n【4】角度一致性（图上方向 vs 表里 angle %+.0f°）" % OFF)
print("   一致(≤15°) %d 条；不一致 %d 条" % (len(good), len(bad)))
bad.sort(reverse=True)
if bad:
    print("   最不一致的 10 条：")
    for dev, frm, to, ang, real in bad[:10]:
        print("      %-6s→%-6s 表ang=%7.1f  图上=%8.1f  差 %.1f°"
              % (frm, to, ang, real, dev))

# ---- 5) 估计点 ----
print("\n【5】图上没画、坐标靠估计的节点（这些只能靠手摆）")
for k in M.MISSING_SEED:
    if k in nodes:
        x, y = nodes[k]
        print("   %-4s (%6.0f,%6.0f)" % (k, x, y))
print("\n（只读分析，不改任何文件）")
