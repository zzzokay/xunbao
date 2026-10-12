# -*- coding: utf-8 -*-
"""AI 过程脚本：验证 P3P4 补打卡的实际行为（纯函数 + 规划出的路线），用于写冒烟断言。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor")
sys.path.insert(0, ME)
import map_model as M                                     # noqa: E402

print("=== p3p4_punch_waypoints(treasure, line_clue) ===")
for t, c in ((3, 0), (4, 0), (2, 0), (3, 3), (4, 4), (5, 3), (2, 4), (6, 0), (2, None)):
    print("  treasure=%s clue=%s -> %s" % (t, c, M.p3p4_punch_waypoints(t, c)))

print("=== door_return_home_waypoints ===")
for t in (2, 3, 4, 5):
    off, _ = M.door_return_home_waypoints("N3", t, False)
    on, _ = M.door_return_home_waypoints("N3", t, False, 0, True)
    print("  treasure=%d off=%s  on=%s" % (t, off, on))

print("=== treasure_return_waypoints（P7 读宝，D2 绿）===")
doors = [M.CAN_PASS, M.NO_PASS, M.NO_PASS, M.NO_PASS]
for t in (2, 3, 4, 5):
    off, _ = M.treasure_return_waypoints("P7", doors, t)
    on, _ = M.treasure_return_waypoints("P7", doors, t, 0, True)
    print("  treasure=%d off=%s\n            on =%s" % (t, off, on))

print("=== 规划出的路线（treasure=4, P3 未去）===")
for punch in (False, True):
    wp, _ = M.door_return_home_waypoints("N3", 4, False, 0, punch)
    p, why = M.MapModel.load_from_sources().plan_route(wp, "full")
    print("  punch=%s wp=%s\n           route=%s" % (punch, wp, p))
