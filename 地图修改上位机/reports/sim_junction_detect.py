# -*- coding: utf-8 -*-
"""路口检测几何仿真 —— 从"检测到路口瞬间车头位置"推算补偿距离，并与 map.c 硬编码值比对拟合。

目标（用户 2026-10-02 需求）：
  把"从检测到路口到走到路口中心"这一步，从人工实测改为仿真直接计算。
  方法是第一性原理几何仿真：
    1. 用边表 angle + step 反解节点真实坐标（cm），重建每个路口的"引导线折线"几何；
    2. 参数化小车模型：旋转中心 O（四轮几何中心）、循迹板（16 灯，车头，板中心在 O 前方 L）；
    3. 模拟车沿入边循迹前进，逐位置计算 16 灯是否压在引导线（3cm 宽红白胶带）上；
    4. 复刻 deal_arrive() 的判据触发逻辑，找到"检测到路口"瞬间的板中心位置；
    5. 补偿值 = 该瞬间让旋转中心到达路口中心还需前进的距离。

只读源码，不改固件。过程产物，可随时清空。
"""
import os
import sys
import math
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "map_editor"))
import map_model as M  # noqa: E402

# ---------------------------------------------------------------- 物理/几何参数（可调）
PARAMS = {
    "L": 19.0,              # 旋转中心 → 板中心 纵向距离（cm，文档 ≈19）
    "led_gap": 1.4,         # 相邻灯间距（cm，用户：约 1.x cm）
    "center_gap": 2.8,      # 中间（bit7/bit8 之间）的额外间隙（cm，用户：左右八路间隔较大）
    "line_half_width": 1.5, # 引导线半宽（cm，规则：30mm 宽 ⇒ 半宽 1.5）
    "detect_tol": 0.2,      # 灯"压线"判定容差（cm，灯中心到线中心距离 < 线半宽 + 容差 即算亮）
}

# 判据 → 该判据在 deal_arrive 里的 if 链顺序（优先级，map.h enum ARRIVE_*）
PRIO = ["DLEFT", "DRIGHT", "CLEFT", "MCLEFT", "MCRIGHT", "CRIGHT", "MORELED", "AWHITE",
        "MUL2SING", "MUL2MUL"]

# 判据 → 灯位映射（bit 号，bit15=最左 1 号灯，bit0=最右 16 号灯）
# DLEFT: 左 6 灯 = bit15..10；DRIGHT: 右 6 灯 = bit0..5
# CLEFT: bit14|bit13；CRIGHT: bit2|bit3；MCLEFT: bit15；MCRIGHT: bit0
# AWHITE: 正中 10 灯 = bit4..13
JUDGE_BITS = {
    "DLEFT":  list(range(15, 9, -1)),   # bit15..10
    "DRIGHT": list(range(0, 6)),        # bit0..5
    "CLEFT":  [14, 13],
    "MCLEFT": [15],
    "MCRIGHT": [0],
    "CRIGHT": [2, 3],
    "AWHITE": list(range(4, 14)),       # bit4..13
}


def build_led_offsets(P):
    """16 灯的横向偏移 y_i（相对板中心，向左为正，cm）。

    bit15 = 最左（y 最大），bit0 = 最右（y 最小）。
    灯间距 led_gap，中间 bit7/bit8 之间额外加 center_gap。
    """
    gap = P["led_gap"]
    cg = P["center_gap"]
    # 半板 = 7 个普通间隔 + 1 个中心大间隔 + 2 个半间距
    # 从左到右：bit15(左端) ... bit8 | bit7 ... bit0(右端)
    # 左半（bit15..bit8）8 灯，右半（bit7..bit0）8 灯
    half = 7 * gap  # 半板内部 7 个间隔
    # 中心 gap = bit8(左半最右) 到 bit7(右半最左) 的距离
    # 板总宽 = 2*half + cg
    # 左端 bit15 在 y = +half + cg/2，右端 bit0 在 y = -half - cg/2
    y = {}
    # 左半 bit15..bit8（index 15 down to 8），从左到右 y 递减
    for i, bit in enumerate(range(15, 7, -1)):   # bit15..bit8
        y[bit] = (half + cg / 2) - i * gap
    # 右半 bit7..bit0
    for i, bit in enumerate(range(7, -1, -1)):   # bit7..bit0
        y[bit] = -(cg / 2) - i * gap
    return y


def load_model_and_turn():
    m = M.MapModel.load_from_sources()
    turn = m.turn
    return m, turn


def node_coords(m):
    """反解节点真实坐标（cm），锚点 N1=(0,0)。返回 {name: (x, y)}。

    用边表 angle + step 做超定最小二乘（去重后的双向段取中位长度）。
    """
    names = m.names()
    idx = {n: i for i, n in enumerate(names)}
    # 无向段长度（取双向中位，func==NONE 优先）
    segs = {}
    for e in m.edges:
        key = tuple(sorted((e.frm, e.to)))
        segs.setdefault(key, []).append(e)
    seg_len = {}
    for key, es in segs.items():
        cand = [m.step(e) for e in es if e.func == "NONE" and m.step(e)]
        if not cand:
            cand = [m.step(e) for e in es if m.step(e)]
        if cand:
            seg_len[key] = sorted(cand)[len(cand) // 2]

    A, b = [], []
    def add(frm, to, dx, dy):
        row = [0.0] * (2 * len(names)); row[2 * idx[to]] += 1; row[2 * idx[frm]] -= 1
        A.append(row); b.append(dx)
        row = [0.0] * (2 * len(names)); row[2 * idx[to] + 1] += 1; row[2 * idx[frm] + 1] -= 1
        A.append(row); b.append(dy)

    for e in m.edges:
        key = tuple(sorted((e.frm, e.to)))
        L = seg_len.get(key)
        a = m.ang(e)
        if not L or a is None:
            continue
        add(e.frm, e.to, L * math.cos(math.radians(a)), L * math.sin(math.radians(a)))

    # 锚点 N1=(0,0)
    W = 1e4
    for val, i in ((0.0, 2 * idx["N1"]), (0.0, 2 * idx["N1"] + 1)):
        row = [0.0] * (2 * len(names)); row[i] = W
        A.append(row); b.append(val)

    # 解最小二乘（高斯消元）
    n = 2 * len(names)
    N = [[0.0] * n for _ in range(n)]; r = [0.0] * n
    for i in range(len(A)):
        Ai = A[i]
        for p in range(n):
            if not Ai[p]:
                continue
            r[p] += Ai[p] * b[i]
            for q in range(p, n):
                if Ai[q]:
                    N[p][q] += Ai[p] * Ai[q]
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
    return {nm: (r[2 * i], r[2 * i + 1]) for i, nm in enumerate(names)}


def point_seg_dist(px, py, ax, ay, bx, by):
    """点 P 到线段 AB 的最短距离。"""
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    c1 = vx * wx + vy * wy
    if c1 <= 0:
        return math.hypot(px - ax, py - ay)
    c2 = vx * vx + vy * vy
    if c2 <= c1:
        return math.hypot(px - bx, py - by)
    t = c1 / c2
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def simulate_detect(m, coords, ie, oe, P, max_s=40.0, ds=0.05):
    """模拟车沿入边 ie 前进，检测判据触发瞬间的板中心纵向位置 s（s>0 = 板中心还没到路口中心）。

    解析化：灯 i（横向偏移 y_i，左正）到出边线的带符号距离 = s·sinφ + y_i·cosφ，
    到主线（入边线）的距离 = |y_i|。灯亮 ⟺ min(|y_i|, |s·sinφ+y_i·cosφ|) < lw。

    返回 (s_detect, judge) 或 (None, None)。
    """
    ang_in = m.ang(ie)
    ang_out = m.ang(oe)
    if ang_in is None or ang_out is None:
        return None, None
    phi = M.need2turn(ang_in, ang_out)
    if phi is None:
        return None, None

    led_y = build_led_offsets(P)
    lw = P["line_half_width"] + P["detect_tol"]
    sp, cp = math.sin(math.radians(phi)), math.cos(math.radians(phi))

    flag = ie.flag
    fs = M.flag_set(flag)
    active_judges = [j for j in PRIO if j in fs]

    # 车前进：s 从大到小。s = 板中心到路口中心的纵向距离（沿入边反向）。
    s = max_s
    while s >= -max_s * 0.5:
        # 每灯亮否（解析）
        lit_num = 0
        lit_bits = set()
        for bit in range(16):
            y = led_y[bit]
            d_in = abs(y)                      # 到主线（入边线）距离
            d_out = abs(s * sp + y * cp)       # 到出边线距离
            if d_in <= lw or d_out <= lw:
                lit_num += 1
                lit_bits.add(bit)

        hit = None
        for j in active_judges:
            if j in ("DLEFT", "DRIGHT"):
                if lit_num >= 5:
                    bits = JUDGE_BITS[j]
                    if sum(1 for b in bits if b in lit_bits) >= 5:
                        hit = j
                        break
            elif j in ("CLEFT", "CRIGHT", "MCLEFT", "MCRIGHT"):
                if 4 <= lit_num <= 7:
                    bits = JUDGE_BITS[j]
                    if any(b in lit_bits for b in bits):
                        hit = j
                        break
            elif j == "MORELED":
                if lit_num >= 5:
                    hit = j
                    break
            elif j == "AWHITE":
                if lit_num >= 10 and all(b in lit_bits for b in JUDGE_BITS["AWHITE"]):
                    hit = j
                    break
        if hit:
            return s, hit
        s -= ds
    return None, None


def run_sim(m, coords, turn, P):
    """用参数 P 跑全部补偿三元组，返回 results（含 sim/meas）。"""
    rows = []
    for tbl in ("stop", "gyro"):
        for r in turn[tbl]:
            rows.append({"tbl": tbl, "last": r["last"], "now": r["now"],
                         "next": r["next"], "meas": float(r["dist"])})
    results = []
    for r in rows:
        ie = m.edge(r["last"], r["now"])
        oe = m.edge(r["now"], r["next"])
        if ie is None or oe is None:
            results.append({**r, "status": "无此边", "s": None, "judge": None, "sim": None})
            continue
        ang_in = m.ang(ie)
        ang_out = m.ang(oe)
        phi = M.need2turn(ang_in, ang_out) if (ang_in is not None and ang_out is not None) else None
        s, judge = simulate_detect(m, coords, ie, oe, P)
        sim = (s + P["L"]) if s is not None else None
        results.append({**r, "status": "ok" if s is not None else "未触发",
                        "phi": phi, "s": s, "judge": judge, "sim": sim,
                        "flag": ie.flag, "func": ie.func, "in_step": m.step(ie),
                        "ang_in": ang_in, "ang_out": ang_out})
    return results


def fit_params(m, coords, turn):
    """网格搜索最优物理参数（灯距、中心间隙、L、线半宽），最小化 MAE。

    只对"仿真成功"的条目算残差；同时记录每条的可信度（是否成功）。
    """
    best = None
    for led_gap in [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]:
        for center_gap in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
            for L in [14.0, 16.0, 17.0, 18.0, 19.0, 20.0, 22.0, 24.0]:
                for lw in [1.0, 1.5, 2.0]:
                    P = dict(PARAMS, led_gap=led_gap, center_gap=center_gap, L=L,
                             line_half_width=lw)
                    results = run_sim(m, coords, turn, P)
                    ok = [r for r in results if r["sim"] is not None]
                    if not ok:
                        continue
                    errs = [abs(r["sim"] - r["meas"]) for r in ok]
                    mae = sum(errs) / len(errs)
                    n_ok = len(ok)
                    # 评分：MAE 为主，成功率次之
                    score = mae - 0.02 * n_ok
                    if best is None or score < best["score"]:
                        best = {"score": score, "mae": mae, "n_ok": n_ok, "P": P,
                                "results": results}
    return best


def main():
    m, turn = load_model_and_turn()
    coords = node_coords(m)

    # ---- 先跑默认参数看结果 ----
    print("=" * 100)
    print("路口检测几何仿真：检测瞬间车头位置 → 补偿距离")
    print("默认参数：L=%.1f 灯距=%.2f 中心间隙=%.2f 线半宽=%.2f"
          % (PARAMS["L"], PARAMS["led_gap"], PARAMS["center_gap"], PARAMS["line_half_width"]))
    print("=" * 100)

    results = run_sim(m, coords, turn, PARAMS)
    print()
    print("%-18s %-5s %+7s %8s %8s %8s %-8s %-9s %s"
          % ("三元组", "表", "Δ(度)", "s(cm)", "仿真Δ", "实测Δ", "判据", "入边func", "flag"))
    for r in results:
        key = "%s>%s>%s" % (r["last"], r["now"], r["next"])
        phi = r.get("phi")
        phi_s = "%+.0f" % phi if phi is not None else "  -"
        s_s = "%.1f" % r["s"] if r["s"] is not None else "  -"
        sim_s = "%.1f" % r["sim"] if r["sim"] is not None else "  -"
        judge = r["judge"] or "-"
        print("%-18s %-5s %7s %8s %8s %8s %-8s %-9s %s"
              % (key, r["tbl"], phi_s, s_s, sim_s, "%.1f" % r["meas"], judge,
                 r["func"], (r["flag"] or "")[:16]))

    ok = [r for r in results if r["sim"] is not None]
    if ok:
        errs = [abs(r["sim"] - r["meas"]) for r in ok]
        xs = [r["sim"] for r in ok]
        ys = [r["meas"] for r in ok]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
        sx = math.sqrt(sum((a - mx) ** 2 for a in xs))
        sy = math.sqrt(sum((b - my) ** 2 for b in ys))
        k = sum(a * b for a, b in zip(xs, ys)) / sum(a * a for a in xs)
        print()
        print("=" * 100)
        print("残差统计（%d 条仿真成功）" % len(ok))
        print("  MAE = %.2f cm   中位 = %.2f cm   最大 = %.2f cm"
              % (sum(errs) / len(errs), sorted(errs)[len(errs) // 2], max(errs)))
        print("  相关系数 r(sim, meas) = %+.3f" % (cov / (sx * sy) if sx * sy else 0))
        print("  过原点比例系数 k = meas/sim ≈ %.3f（实测 ≈ %.3f × 仿真）" % (k, k))

    # ---- 网格搜索拟合 ----
    print()
    print("=" * 100)
    print("网格搜索最优参数（最小化 MAE）…")
    best = fit_params(m, coords, turn)
    Pbest = best["P"]
    print("最优参数：L=%.1f 灯距=%.2f 中心间隙=%.2f 线半宽=%.2f"
          % (Pbest["L"], Pbest["led_gap"], Pbest["center_gap"], Pbest["line_half_width"]))
    print("  MAE = %.2f cm（%d/%d 条仿真成功）" % (best["mae"], best["n_ok"], len(best["results"])))

    # 最优参数下的比例系数（拟合补偿 = k * 仿真）
    bok = [r for r in best["results"] if r["sim"] is not None]
    bxs = [r["sim"] for r in bok]
    bys = [r["meas"] for r in bok]
    k_best = sum(a * b for a, b in zip(bxs, bys)) / sum(a * a for a in bxs)
    # 也拟合带截距的线性回归
    n = len(bxs)
    mx, my = sum(bxs) / n, sum(bys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(bxs, bys))
    vx = sum((a - mx) ** 2 for a in bxs)
    slope = cov / vx if vx else 0
    intercept = my - slope * mx
    print("  过原点比例系数 k = %.3f" % k_best)
    print("  线性回归：meas = %.3f × sim %+.2f（截距 %.2f）" % (slope, intercept, intercept))

    # 最优参数下的逐条结果
    print()
    print("最优参数下逐条（仿真 vs 实测）：")
    print("%-18s %-5s %+7s %8s %8s %7s %-8s"
          % ("三元组", "表", "Δ", "仿真Δ", "实测Δ", "残差", "判据"))
    for r in best["results"]:
        if r["sim"] is None:
            continue
        key = "%s>%s>%s" % (r["last"], r["now"], r["next"])
        phi = r.get("phi") or 0
        print("%-18s %-5s %+7.0f %8.1f %8.1f %+7.1f %-8s"
              % (key, r["tbl"], phi, r["sim"], r["meas"], r["sim"] - r["meas"],
                 r["judge"] or "-"))

    # 保存
    out_path = os.path.join(HERE, "junction_sim_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"default_params": PARAMS, "best_params": Pbest,
                   "best_mae": best["mae"], "k_overorigin": k_best,
                   "slope": slope, "intercept": intercept,
                   "results": best["results"]}, f, ensure_ascii=False, indent=1)
    print()
    print("结果已写入 %s" % out_path)


if __name__ == "__main__":
    main()
