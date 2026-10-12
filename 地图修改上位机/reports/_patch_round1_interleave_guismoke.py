# -*- coding: utf-8 -*-
"""_guismoke.py：断言改成"一轮交错 + S1/S2 跟着 P3/P4 走"。

- 改：两个开关一起开时的期望序列（旧：P3 P4 S1；新：P3(平台已在前面) S1 P4 S2）。
- 加：round1_return_extra_waypoints 交错序列、宝物=P1 也绕 S1/S2、
      以及**独立口径**直接读 mission_planner.c 文本确认共享小函数存在且两处都调用。
"""
import os, sys

ROOT = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao"
PATH = os.path.join(ROOT, "地图修改上位机", "map_editor", "_guismoke.py")

raw = open(PATH, "rb").read()
crlf = raw.count(b"\r\n"); lf = raw.count(b"\n") - crlf
print("EOL: CRLF=%d LF-only=%d" % (crlf, lf))
EOL = "\r\n" if crlf >= lf else "\n"
text = raw.decode("utf-8")


def b(s):
    return s.replace("\n", EOL)


old = b('''    _both, _ = M.door_return_home_waypoints("N3", 3, False, 0, True, True)
    check(_both == ["N3", "P3", "P4", "S1", "P2"],
          "两个开关一起开：补打卡在前、巡回在后（%s）" % _both)
''')
new = b('''    _both, _ = M.door_return_home_waypoints("N3", 3, False, 0, True, True)
    check(_both == ["N3", "P3", "S1", "P4", "S2", "P2"],
          "两个开关一起开：宝物平台(已在前面)之后交错成 S1 -> P4 -> S2（%s）" % _both)
    # ★ 2026-10-16：S1/S2 不再要求"宝物在 P3/P4"，而是"这次回程会不会去 P3/P4"。
    _no_plat, _ = M.door_return_home_waypoints("N3", 2, False, 0, True, True)
    check(_no_plat == ["N3", "P1", "P3", "S1", "P4", "S2", "P2"],
          "宝物=P1：补打卡开着时照样绕 S1/S2（%s）" % _no_plat)
    check(M.round1_return_extra_waypoints(2, 0, True, True) == ["P3", "S1", "P4", "S2"]
          and M.round1_return_extra_waypoints(2, 0, False, True) == []
          and M.round1_return_extra_waypoints(3, 0, False, True) == ["S1"]
          and M.round1_return_extra_waypoints(4, 0, False, True) == ["S2"]
          and M.round1_return_extra_waypoints(2, 0, True, False) == ["P3", "P4"],
          "round1_return_extra_waypoints：交错 P3->S1->P4->S2；关掉补打卡则退回旧行为")
    check(M.upright_tour_waypoints(2, 0, True) == ["S1", "S2"]
          and M.upright_tour_waypoints(3, 0, True) == ["S1", "S2"]
          and M.upright_tour_waypoints(3, 3, True) == ["S1", "S2"],
          "upright_tour_waypoints 跟着「会去 P3/P4」走（补打卡开着 ⇒ 两个都绕）")
    # ⚠️ 独立口径：直接读 mission_planner.c 文本，确认交错段确实集中在共享小函数里、
    #    两个回程函数各调它一次（断言与实现不同源，防"同源错 ⇒ 自测假通过"）。
    _mp_p = os.path.join(M.ROOT, "Mission", "mission_planner.c")
    _mp_txt = open(_mp_p, encoding="utf-8", errors="replace").read()
    check("append_round1_return_tail(u8 *wp, uint8_t n)" in _mp_txt
          and _mp_txt.count("n = append_round1_return_tail(wp, n);") == 2,
          "mission_planner.c：交错段集中在 append_round1_return_tail()，两个回程函数各调一次")
''')

assert text.count(old) == 1, text.count(old)
open(PATH, "wb").write(text.replace(old, new, 1).encode("utf-8"))
print("已写盘:", PATH)
