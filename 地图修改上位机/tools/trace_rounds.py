# -*- coding: utf-8 -*-
"""第一轮 + 第二轮逐跳 trace，标出 View / 门 / 波动板 等关键 func 的落点。"""
import os, sys, importlib.util

ROOT = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao/地图修改上位机"
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "validate"))
spec = importlib.util.spec_from_file_location(
    "simrb", os.path.join(ROOT, "tools", "sim_route_bookkeeping.py"))
simrb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simrb)

S = simrb.Sim(clue=3, stage_a=5, stage_b=7,
              door_true=[simrb.ONE_WAY_PASS, simrb.CAN_PASS, simrb.CAN_PASS,
                         simrb.NO_PASS, simrb.NO_PASS],
              treasure=0)

INTEREST = {"View", "View1", "DOOR", "BLBL", "BLBS", "UpStage", "UpStageHome",
            "BSoutPole", "BHM", "Bridge", "Hill", "SM", "QQB"}


def dump(tag):
    print("=" * 78)
    print(tag)
    step = 0
    guard = 0
    while not S.finished and guard < 400:
        guard += 1
        step += 1
        frm, to = simrb.NAME[S.now["from"]], simrb.NAME[S.now["to"]]
        func = S.eff_func(S.now)
        fname = [k for k, v in simrb.W.FUNC.items() if v == func]
        fname = fname[0] if fname else str(func)
        mark = "  <<<" if fname in INTEREST else ""
        print("%-4d %-14s -> %-6s %s%s" % (step, frm, to, fname, mark))
        S.run_edge()


S.map_init()
dump("第一轮（DEBUG 门色 D2蓝 D3绿 D4绿 D5黑，clue=3/5/7，treasure 初值 0）")
print("routetime=%d door_pass=%s violations=%s" % (S.routetime, S.door_pass, S.violations))

wp2 = S.get_newroute()
print("\n二轮 wp: %s\n" % " ".join(wp2))
dump("第二轮")
print("routetime=%d violations=%s" % (S.routetime, S.violations))
