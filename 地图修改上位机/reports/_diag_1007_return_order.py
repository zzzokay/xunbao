# -*- coding: utf-8 -*-
"""复现用户报告的输入：宝物=3、线索=3、D2黑/D3蓝/D4黑/D5绿、punch=开、tour=开"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao\地图修改上位机\map_editor")
import map_model as M

print("门状态常量:", M.DOOR_STATE_NAME)
doors = [M.NO_PASS, M.ONE_WAY_PASS, M.NO_PASS, M.CAN_PASS]  # D2黑 D3蓝 D4黑 D5绿

print("punch_waypoints(3, 3) =", M.p3p4_punch_waypoints(3, 3))
print("upright_tour_waypoints(3, 3, punch=True) =", M.upright_tour_waypoints(3, 3, True))
print("round1_return_extra_waypoints(3, 3, True, True) =",
      M.round1_return_extra_waypoints(3, 3, True, True))

wp, why = M.treasure_return_waypoints("P7", doors, 3, 3, True, True)
print("treasure_return_waypoints ->", wp, "| why:", why)

wp3, blocked = M.door_return_home_waypoints("N3", 3, False, 3, True, True)
print("door_return_home_waypoints(N3, 3, clue=3, punch, tour) ->", wp3)
