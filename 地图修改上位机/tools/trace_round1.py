# -*- coding: utf-8 -*-
"""reuse 已有的 sim_route_bookkeeping，打印第一轮逐跳 trace（找 N14 在哪一跳、func 是什么）"""
import os, sys, io
ROOT = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao/地图修改上位机"
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "validate"))
# 让它的 __main__ 不执行
import importlib.util
spec = importlib.util.spec_from_file_location("simrb", os.path.join(ROOT, "tools", "sim_route_bookkeeping.py"))
simrb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simrb)

S = simrb.Sim( clue=3, stage_a=5, stage_b=7,
               door_true=[simrb.ONE_WAY_PASS, simrb.CAN_PASS, simrb.CAN_PASS, simrb.NO_PASS, simrb.NO_PASS],
               treasure=0)
S.map_init()
print("%-4s %-16s %-7s %-16s %-14s %s" % ("step", "edge", "point", "route[point-1]", "nextNode", "func/@到达节点"))
guard = 0
while not S.finished and guard < 200:
    guard += 1
    frm, to = simrb.NAME[S.now["from"]], simrb.NAME[S.now["to"]]
    func = S.eff_func(S.now)
    fname = [k for k, v in simrb.W.FUNC.items() if v == func]
    fname = fname[0] if fname else str(func)
    print("%-4d %-16s %-7d %-16s %-14s %s" % (guard, "%s->%s" % (frm, to), S.point,
          str(simrb.NAME.get(S.route[S.point-1], S.route[S.point-1])), str(simrb.NAME.get(S.nxt["to"]) if S.nxt else None), fname))
    S.run_edge()
print("finished=%s routetime=%d door_pass=%s" % (S.finished, S.routetime, S.door_pass))
print("violations:", S.violations)
