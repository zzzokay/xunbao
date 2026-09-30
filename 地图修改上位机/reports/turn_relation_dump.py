# -*- coding: utf-8 -*-
"""转弯补偿「长度 / 标志位 / 路口线段」关系分析（只读，不改固件）。

输出四块：
  A 全边表：from,to,flag,angle,step,func + 像素几何角/像素长
  B 表1/表2 全表项 + 上下文（Δ、入边 step、入边 func、flag、补偿值、分支）
  C 关系矩阵：补偿值 vs |Δ| / 1-cos / in_step / 判据
  D 角度参考系对齐：表 angle vs 图上几何角，找最佳整体旋转
"""
import os
import sys
import math
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "map_editor"))
import map_model as M  # noqa: E402

m = M.MapModel.load_from_sources()
P = {n.name: (n.x, n.y) for n in m.nodes}


def geo_angle(frm, to):
    """图上 from→to 的几何角（向右=0，向上=+90，逆时针），度。"""
    if frm not in P or to not in P:
        return None
    dx = P[to][0] - P[frm][0]
    dy = P[to][1] - P[frm][1]          # 图像 y 向下
    return math.degrees(math.atan2(-dy, dx))


def px_len(frm, to):
    if frm not in P or to not in P:
        return None
    return math.hypot(P[to][0] - P[frm][0], P[to][1] - P[frm][1])


def norm180(a):
    if a is None:
        return None
    while a > 180:
        a -= 360
    while a <= -180:
        a += 360
    return a


print("=" * 100)
print("A 全边表（%d 条）" % len(m.edges))
print("=" * 100)
print("%-5s %-5s %-5s %-16s %8s %8s %8s %8s %s"
      % ("from", "to", "ang", "flag", "step", "px", "geo", "px/step", "func"))
for e in sorted(m.edges, key=lambda e: (e.frm, e.to)):
    a = m.ang(e)
    s = m.step(e)
    g = geo_angle(e.frm, e.to)
    pl = px_len(e.frm, e.to)
    ratio = (pl / s) if (pl and s) else None
    print("%-5s %-5s %-5s %-16s %8s %8s %8s %8s %s"
          % (e.frm, e.to, ("%g" % a) if a is not None else "?",
             e.flag, ("%g" % s) if s is not None else "?",
             ("%.0f" % pl) if pl else "-",
             ("%.1f" % g) if g is not None else "-",
             ("%.2f" % ratio) if ratio else "-", e.func))

print()
print("=" * 100)
print("B 补偿表全表项 + 上下文")
print("=" * 100)


def ctx(rows, table):
    out = []
    for r in rows:
        ie = m.edge(r["last"], r["now"])
        oe = m.edge(r["now"], r["next"])
        d = {"row": r, "ie": ie, "oe": oe}
        if ie is not None and oe is not None:
            d["delta"] = M.need2turn(m.ang(ie), m.ang(oe))
            d["in_step"] = m.step(ie)
            d["in_func"] = ie.func
            d["in_flag"] = ie.flag
            d["out_step"] = m.step(oe)
            d["out_func"] = oe.func
            d["out_flag"] = oe.flag
            d["branch"] = M.turn_branch(d["delta"], ie.flag, ie.func)
        out.append(d)
    return out


for name, rows, table in (("表1 kTurnTbl（停车原地转）", m.turn["stop"], "stop"),
                          ("表2 GyroTurn（陀螺不停车转）", m.turn["gyro"], "gyro")):
    print()
    print("--- %s ：%d 条 ---" % (name, len(rows)))
    print("%-4s %-5s %-5s %-13s %-8s %6s %6s %-6s %-6s %6s %6s %s"
          % ("n", "last", "now", "next", "  ", "Δ", "step", "func",
             "flag", "outst", "值", "当前分支"))
    for i, d in enumerate(ctx(rows, table), 1):
        r = d["row"]
        if d.get("delta") is None:
            print("%-4d %-5s %-5s %-13s %-8s  边表缺失" % (i, r["last"], r["now"], r["next"], ""))
            continue
        print("%-4d %-5s %-5s %-13s %-8s %+6.0f %6s %-6s %-16s %6s %6s %s"
              % (i, r["last"], r["now"], r["next"], "", d["delta"], d["in_step"],
                 d["in_func"], d["in_flag"], d["out_step"], r["dist"], d["branch"]))

print()
print("=" * 100)
print("C 关系矩阵：表1 补偿值 vs 特征")
print("=" * 100)
stop_ok = [d for d in ctx(m.turn["stop"], "stop")
           if d.get("delta") is not None and d.get("in_step") is not None]
print("%-22s %6s %6s %8s %8s %10s %8s" %
      ("三元组", "Δ", "|Δ|", "step", "1-cos", "L19(1-cos)", "值"))
for d in sorted(stop_ok, key=lambda x: -abs(x["delta"])):
    phi = abs(d["delta"])
    c = 1 - math.cos(math.radians(phi))
    print("%-22s %+6.0f %6.0f %8s %8.3f %10.1f %8s"
          % ("%s>%s>%s" % (d["row"]["last"], d["row"]["now"], d["row"]["next"]),
             d["delta"], phi, d["in_step"], c, 19.0 * c, d["row"]["dist"]))

print()
print("=" * 100)
print("D 角度参考系：表 angle vs 图上几何角")
print("=" * 100)
diffs = []
for e in m.edges:
    a = m.ang(e)
    g = geo_angle(e.frm, e.to)
    if a is None or g is None:
        continue
    diffs.append((norm180(a - g), e.frm, e.to, a, g))
ds = [d[0] for d in diffs]
print("n=%d  中位偏差=%.1f°  均值=%.1f°  |偏差|<10° 的有 %d 条"
      % (len(ds), st.median(ds), st.mean(ds), sum(1 for x in ds if abs(x) < 10)))
# 最佳整体旋转
best = None
for k in range(0, 360, 1):
    err = sum(abs(norm180(x - k)) for x in ds)
    if best is None or err < best[1]:
        best = (k, err)
print("最佳整体旋转 = %d°（残差和 %.0f，平均 %.1f°）" % (best[0], best[1], best[1] / len(ds)))
rest = [norm180(x - best[0]) for x in ds]
print("去掉该旋转后：中位|残差|=%.1f°  均值=%.1f°  |残差|<10°=%d  <20°=%d"
      % (st.median([abs(x) for x in rest]), st.mean([abs(x) for x in rest]),
         sum(1 for x in rest if abs(x) < 10), sum(1 for x in rest if abs(x) < 20)))
print()
print("偏差最大的 10 条：")
for d in sorted(diffs, key=lambda x: -abs(x[0]))[:10]:
    print("  %-5s→%-5s 表=%+6.0f° 图=%+7.1f° 差=%+7.1f°" % (d[1], d[2], d[3], d[4], d[0]))
