# -*- coding: utf-8 -*-
"""路口检测几何仿真 —— 最终拟合 + 报告数据生成。

结论性脚本：只读源码，输出
  1. stop（停车原地转）分支：几何仿真 Δ = s + L，拟合最优物理参数 + 比例系数
  2. gyro（陀螺不停车转）分支：单独统计，说明其语义差异
  3. 逐条仿真 vs 实测对照表（JSON，供可视化/报告用）
"""
import os
import sys
import math
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "map_editor"))
import map_model as M
import sim_junction_detect as S


def main():
    m, turn = S.load_model_and_turn()
    coords = S.node_coords(m)

    # 收集真正生效的条目（分支判定 == 所在表），分 stop / gyro
    stop_meas, gyro_meas = [], []
    for tbl in ("stop", "gyro"):
        for r in turn[tbl]:
            ie = m.edge(r["last"], r["now"]); oe = m.edge(r["now"], r["next"])
            if ie is None or oe is None:
                continue
            d = M.need2turn(m.ang(ie), m.ang(oe))
            br = M.turn_branch(d, ie.flag, ie.func)
            if br != tbl:
                continue
            rec = {"last": r["last"], "now": r["now"], "next": r["next"],
                   "meas": float(r["dist"]), "ie": ie, "oe": oe, "phi": d,
                   "flag": ie.flag, "func": ie.func, "step": m.step(ie)}
            (stop_meas if tbl == "stop" else gyro_meas).append(rec)

    # ---- stop 分支网格拟合 ----
    # 评分：每条"未触发"记一个固定大残差（惩罚触发失败），其余按 |sim-meas|。
    # 这样不会选出"只在少数条上拟合好、其余全失败"的过拟合参数。
    MISS_PENALTY = 30.0
    best = None
    for led_gap in [1.0, 1.2, 1.4, 1.6, 1.8]:
        for cg in [1.5, 2.0, 2.5, 3.0]:
            for lw in [1.5, 2.0]:
                for L in [10, 12, 14, 16, 18, 20, 22]:
                    P = dict(S.PARAMS, led_gap=led_gap, center_gap=cg, L=L, line_half_width=lw)
                    errs = []
                    n_ok = 0
                    for r in stop_meas:
                        s, j = S.simulate_detect(m, coords, r["ie"], r["oe"], P)
                        if s is None:
                            errs.append(MISS_PENALTY)
                        else:
                            n_ok += 1
                            errs.append(abs((s + L) - r["meas"]))
                    mae = sum(errs) / len(errs)  # 含未触发惩罚的平均
                    if best is None or mae < best["mae"]:
                        best = {"mae": mae, "mae_ok": (sum(errs) - MISS_PENALTY * (len(errs) - n_ok)) / n_ok if n_ok else 99,
                                "led_gap": led_gap, "center_gap": cg,
                                "line_half_width": lw, "L": L, "n_ok": n_ok}

    P = dict(S.PARAMS, led_gap=best["led_gap"], center_gap=best["center_gap"],
             line_half_width=best["line_half_width"], L=best["L"])

    print("=" * 96)
    print("路口检测几何仿真 —— 最终拟合")
    print("最优物理参数：L=%.0f cm（旋转中心→板中心） 灯距=%.1f cm 中心间隙=%.1f cm 线半宽=%.1f cm"
          % (best["L"], best["led_gap"], best["center_gap"], best["line_half_width"]))
    print("=" * 96)

    # stop 逐条
    stop_rows = []
    print()
    print("【停车原地转 stop 分支】%d 条生效，MAE(成功条)=%.2f cm（%d/%d 仿真成功）"
          % (len(stop_meas), best["mae_ok"], best["n_ok"], len(stop_meas)))
    print("  %-16s %+6s %7s %7s %7s %7s %-8s" % ("三元组", "Δ", "s", "仿真Δ", "实测Δ", "残差", "判据"))
    for r in stop_meas:
        s, j = S.simulate_detect(m, coords, r["ie"], r["oe"], P)
        key = "%s>%s>%s" % (r["last"], r["now"], r["next"])
        if s is None:
            print("  %-16s %+6.0f 未触发" % (key, r["phi"]))
            stop_rows.append({**{k: r[k] for k in ("last", "now", "next", "meas", "phi", "func", "step")},
                              "s": None, "sim": None, "judge": None, "resid": None})
            continue
        sim = s + best["L"]
        resid = sim - r["meas"]
        print("  %-16s %+6.0f %7.1f %7.1f %7.1f %+7.1f %-8s"
              % (key, r["phi"], s, sim, r["meas"], resid, j or "-"))
        stop_rows.append({**{k: r[k] for k in ("last", "now", "next", "meas", "phi", "func", "step")},
                          "s": round(s, 2), "sim": round(sim, 2), "judge": j, "resid": round(resid, 2)})

    # stop 比例系数（过原点）
    xs = [r["sim"] for r in stop_rows if r["sim"] is not None]
    ys = [r["meas"] for r in stop_rows if r["sim"] is not None]
    k = sum(a * b for a, b in zip(xs, ys)) / sum(a * a for a in xs)
    print()
    print("  stop 分支 过原点比例系数 k = meas/sim = %.3f" % k)
    print("  （k≈1 ⇒ 仿真值本身就是 cm 正确值，几乎不需额外缩放）")

    # gyro 逐条（用同一几何，但语义不同，只对照）
    print()
    print("【陀螺不停车转 gyro 分支】%d 条生效（弧线转弯，语义不同，仅对照）" % len(gyro_meas))
    print("  %-16s %+6s %7s %7s %-8s" % ("三元组", "Δ", "几何Δ", "实测Δ", "判据"))
    gyro_rows = []
    for r in gyro_meas:
        s, j = S.simulate_detect(m, coords, r["ie"], r["oe"], P)
        key = "%s>%s>%s" % (r["last"], r["now"], r["next"])
        geom = (s + best["L"]) if s is not None else None
        print("  %-16s %+6.0f %7s %7.1f %-8s"
              % (key, r["phi"], ("%.1f" % geom) if geom is not None else "  -", r["meas"], j or "-"))
        gyro_rows.append({**{k: r[k] for k in ("last", "now", "next", "meas", "phi", "func", "step")},
                          "geom": (round(geom, 2) if geom is not None else None), "judge": j})

    out = {
        "params": {"L": best["L"], "led_gap": best["led_gap"],
                   "center_gap": best["center_gap"], "line_half_width": best["line_half_width"]},
        "stop_mae": round(best["mae_ok"], 2), "stop_k": round(k, 3),
        "stop": stop_rows, "gyro": gyro_rows,
    }
    out_path = os.path.join(HERE, "junction_fit_final.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print()
    print("结果已写入 %s" % out_path)


if __name__ == "__main__":
    main()
