# -*- coding: utf-8 -*-
"""AI 过程脚本：定位 _guismoke 第三条失败到底是 wp 少了 N8，还是规划route变了。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor")
sys.path.insert(0, ME)
import map_model as M                                     # noqa: E402

doors = [M.ONE_WAY_PASS, M.CAN_PASS, M.CAN_PASS, M.NO_PASS]   # D2蓝 D3绿 D4绿 D5黑
wp, why = M.round2_waypoints(doors, 4)
print("round2_waypoints =", wp)
print("  含 N8 ?", ("N8" in wp) if wp else "wp 为 None")
print("  why =", why)
