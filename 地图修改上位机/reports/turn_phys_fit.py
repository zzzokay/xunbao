# -*- coding: utf-8 -*-
"""补偿值的物理关系拟合 + 留一验证（LOO）：能不能靠仿真算出来？只读，不改固件。

模型：
  M0 常量         Δ̂ = 19
  M1 只判据       Δ̂ = d(judge)
  M2 判据+几何    Δ̂ = L*(1-cosφ) + d(judge)            ← 固件现用
  M3 M2 + 段长项  Δ̂ = L*(1-cosφ) + d(judge) + k*max(0,18-in_step)
  M4 三元组查表   Δ̂ = 实测（= 现状 Tier1，零泛化）
"""
import os
import sys
import math
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "map_editor"))
import map_model as M  # noqa: E402

m = M.MapModel.load_from_sources()

# deal_arrive() 的 if 链顺序 = 判据优先级（ArriveDetect_task.c）
PRIO = ["DLEFT", "DRIGHT", "CLEFT", "MCLEFT", "MCRIGHT", "CRIGHT", "MORELED", "AWHITE",
        "MUL2SING", "MUL2MUL"]
JUDGE_OF_FLAG = {"DLEFT": "ARRIVE_DLEFT", "DRIGHT": "ARRIVE_DRIGHT", "CLEFT": "ARRIVE_CLEFT",
                 "MCLEFT": "ARRIVE_MCLEFT", "MCRIGHT": "ARRIVE_MCRIGHT",
                 "CRIGHT": "ARRIVE_CRIGHT", "MORELED": "ARRIVE_MORELED",
                 "AWHITE": "ARRIVE_AWHITE", "MUL2SING": "ARRIVE_MUL2SING",
                 "MUL2MUL": "ARRIVE_MUL2MUL"}


def judge_of(flag):
    fs = M.flag_set(flag)
    for p in PRIO:
        if p in fs:
            return JUDGE_OF_FLAG[p]
    return "ARRIVE_NONE"


rows = []
for tbl in ("stop", "gyro"):
    for r in m.turn[tbl]:
        ie = m.edge(r["last"], r["now"])
        oe = m.edge(r["now"], r["next"])
        if ie is None or oe is None:
            continue
        d = M.need2turn(m.ang(ie), m.ang(oe))
        rows.append({
            "tbl": tbl, "key": "%s>%s>%s" % (r["last"], r["now"], r["next"]),
            "delta": d, "phi": abs(d), "y": r["dist"],
            "in_step": m.step(ie), "in_func": ie.func, "in_flag": ie.flag,
            "judge": judge_of(ie.flag), "branch": M.turn_branch(d, ie.flag, ie.func),
        })

print("样本 %d 行（表1 %d + 表2 %d）"
      % (len(rows), sum(1 for r in rows if r["tbl"] == "stop"),
         sum(1 for r in rows if r["tbl"] == "gyro")))
print()
print("%-16s %-6s %6s %7s %6s %-9s %-14s %s"
      % ("三元组", "表", "Δ", "step", "值", "判据", "flag", "分支"))
for r in sorted(rows, key=lambda r: (r["tbl"], -r["phi"])):
    print("%-16s %-6s %+6.0f %7s %6s %-9s %-14s %s"
          % (r["key"], r["tbl"], r["delta"], r["in_step"], r["y"],
             r["judge"].replace("ARRIVE_", ""), r["in_flag"][:14], r["branch"]))

# ---------------- 物理项分解 ----------------
print()
print("=" * 96)
print("物理分解：几何项 L(1-cosφ) / 判据偏置 d / 残差")
print("=" * 96)


def d_of(judge, dc):
    return {"ARRIVE_CRIGHT": dc[0], "ARRIVE_CLEFT": dc[1], "ARRIVE_DLEFT": dc[2]}.get(judge, dc[3])


def fit_L_d(data, L0=19.0, dc0=(11.0, -4.0, -5.0, -4.0)):
    """网格搜 L，再对每个判据取残差中位 → d。返回 (L, {judge: d}, 训练MAE)。"""
    best = None
    for L10 in range(50, 401, 5):          # L = 5.0 .. 40.0 步长 0.5
        L = L10 / 10.0
        res = {}
        for j in PRIO:
            rr = [r["y"] - L * (1 - math.cos(math.radians(r["phi"])))
                  for r in data if r["judge"] == "ARRIVE_" + j]
            if rr:
                res["ARRIVE_" + j] = st.median(rr)
        dflt = st.median([r["y"] - L * (1 - math.cos(math.radians(r["phi"]))) for r in data])
        err = 0.0
        for r in data:
            dj = res.get(r["judge"], dflt)
            err += abs(r["y"] - (L * (1 - math.cos(math.radians(r["phi"]))) + dj))
        err /= len(data)
        if best is None or err < best[2]:
            best = (L, res, err, dflt)
    return best


L, dmap, mae, dflt = fit_L_d(rows)
print("全量拟合（含障碍/短段，仅作对照）：L=%.1f 训练MAE=%.2f" % (L, mae))
print("  各判据 d：" + "  ".join("%s=%+.1f" % (k.replace("ARRIVE_", ""), v)
                                 for k, v in sorted(dmap.items())))
print("  缺省 d=%+.1f" % dflt)

# 只取"平地 + 大角度 + 长段"（固件 Tier2 的适用域）
clean = [r for r in rows if r["in_func"] in ("NONE", "DOOR") and (r["in_step"] or 0) >= 20
         and 100 <= r["phi"] < 178]
Lc, dc, maec, dfltc = fit_L_d(clean)
print()
print("仅 Tier2 适用域（平地/大角度/step>=20）：%d 行  L=%.1f 训练MAE=%.2f"
      % (len(clean), Lc, maec))
print("  各判据 d：" + "  ".join("%s=%+.1f" % (k.replace("ARRIVE_", ""), v)
                                 for k, v in sorted(dc.items())) + "  缺省=%+.1f" % dfltc)

# ---------------- LOO ----------------
print()
print("=" * 96)
print("留一验证 LOO（预测某行时只用其余行估参数）")
print("=" * 96)


def loo_mae(data, model):
    errs = []
    for i, r in enumerate(data):
        tr = data[:i] + data[i + 1:]
        if not tr:
            continue
        if model == "M0":
            p = st.median([x["y"] for x in tr])
        elif model == "M1":
            same = [x["y"] for x in tr if x["judge"] == r["judge"]]
            p = st.median(same) if same else st.median([x["y"] for x in tr])
        elif model == "M2":
            L2, d2, _, dfl2 = fit_L_d(tr)
            p = L2 * (1 - math.cos(math.radians(r["phi"]))) + d2.get(r["judge"], dfl2)
        elif model == "M3":
            best3 = None
            for L10 in range(50, 401, 5):
                L3 = L10 / 10.0
                for k in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.5]:
                    rr = {}
                    for j in PRIO:
                        vv = [x["y"] - L3 * (1 - math.cos(math.radians(x["phi"])))
                              - k * max(0.0, 18 - (x["in_step"] or 0))
                              for x in tr if x["judge"] == "ARRIVE_" + j]
                        if vv:
                            rr["ARRIVE_" + j] = st.median(vv)
                    dfl = st.median([x["y"] - L3 * (1 - math.cos(math.radians(x["phi"])))
                                     - k * max(0.0, 18 - (x["in_step"] or 0)) for x in tr])
                    e = sum(abs(x["y"] - (L3 * (1 - math.cos(math.radians(x["phi"])))
                                          + k * max(0.0, 18 - (x["in_step"] or 0))
                                          + rr.get(x["judge"], dfl))) for x in tr) / len(tr)
                    if best3 is None or e < best3[0]:
                        best3 = (e, L3, k, rr, dfl)
            _, L3, k, rr, dfl = best3
            p = (L3 * (1 - math.cos(math.radians(r["phi"])))
                 + k * max(0.0, 18 - (r["in_step"] or 0)) + rr.get(r["judge"], dfl))
        elif model == "M4":
            p = r["y"]
        errs.append(abs(r["y"] - p))
    return sum(errs) / len(errs)


for tag, data in (("全 26 行", rows), ("Tier2 适用域 %d 行" % len(clean), clean)):
    print()
    print("--- %s ---" % tag)
    for md, name in (("M0", "常量中位"), ("M1", "只判据"), ("M2", "判据+几何(L(1-cos))"),
                     ("M3", "M2+段长项"), ("M4", "三元组查表(=现状)")):
        print("  %-26s LOO-MAE = %6.2f cm" % (name, loo_mae(data, md)))

# ---------------- 相关性与物理量 ----------------
print()
print("=" * 96)
print("相关性 / 物理量估计")
print("=" * 96)


def corr(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


g = [1 - math.cos(math.radians(r["phi"])) for r in clean]
y = [r["y"] for r in clean]
print("Tier2 域内  r(1-cosφ, 补偿值) = %+.3f   （几何项解释力）" % corr(g, y))
print("全 26 行     r(1-cosφ, 补偿值) = %+.3f"
      % corr([1 - math.cos(math.radians(r["phi"])) for r in rows], [r["y"] for r in rows]))
print("全 26 行     r(in_step, 补偿值) = %+.3f"
      % corr([r["in_step"] or 0 for r in rows], [r["y"] for r in rows]))
big = [r for r in rows if r["phi"] >= 100]
print("|Δ|>=100 的 %d 行  r(in_step, 补偿值) = %+.3f"
      % (len(big), corr([r["in_step"] or 0 for r in big], [r["y"] for r in big])))
print()
print("按 入边 step 分档（|Δ|>=100 子集）：")
for lo, hi in ((0, 19), (20, 60), (61, 200)):
    sub = [r["y"] for r in big if lo <= (r["in_step"] or 0) <= hi]
    if sub:
        print("  step %3d~%-3d : n=%d  补偿值 中位 %.1f  范围 %.0f~%.0f"
              % (lo, hi, len(sub), st.median(sub), min(sub), max(sub)))

print()
print("按判据分档（全部 26 行）：")
for j in PRIO:
    sub = [r["y"] for r in rows if r["judge"] == "ARRIVE_" + j]
    if sub:
        print("  %-9s n=%-2d  中位 %5.1f  值 %s"
              % (j, len(sub), st.median(sub), sorted(sub)))
