# -*- coding: utf-8 -*-
"""AI 过程脚本：查「第一轮」回程开了 S1/S2 巡回后，画布路线里到底有没有 S1/S2。"""
import os
import sys
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor")
sys.path.insert(0, ME)
import map_editor as E                                       # noqa: E402
import map_model as M                                        # noqa: E402

app = E.App(os.path.join(E.M.ROOT, "寻宝地图", "节点图.jpg"))
app.update_idletasks()

ST_ALL = "第一轮·完整路线（去程+门区+东区+回程 自动拼接，画布分色）"
ST_BACK = "第一轮·门区回程（route_return_home，门区禁用）"
ST_AB = "第一轮·过门→平台A/B→宝物回程"
DOORS = [M.NO_PASS, M.NO_PASS, M.ONE_WAY_PASS, M.CAN_PASS]

print("=== 纯函数：treasure_return_waypoints(P7, doors, treasure, clue, punch, tour) ===")
for t in (3, 4, 2):
    off, _ = M.treasure_return_waypoints("P7", DOORS, t, 3, False, False)
    on, _ = M.treasure_return_waypoints("P7", DOORS, t, 3, False, True)
    print("  宝物=P%d  关=%s\n           开=%s" % (t, off, on))

for stage in (ST_ALL, ST_BACK, ST_AB):
    for t in (3, 4):
        secs, flat, err = app._clue_route_sections(stage, 3, (5, 7), DOORS, t, "full",
                                                   False, True)
        has = [n for n in ("S1", "S2") if n in (flat or [])]
        print("--- %s ｜宝物=P%d ｜tour=True ---" % (stage[:16], t))
        print("    err=%s  跳数=%s  S1/S2=%s" % (err, len(flat or []), has or "无"))
        # 找出 wp（从报告里抽）
        for title, lines in secs:
            for ln in lines:
                if ln.startswith("wp:") or ln.startswith("序列") or "route[]" in ln:
                    print("    [%s] %s" % (title[:18], ln[:110]))
        if not has:
            print("    ⚠ 这一路没有 S1/S2", "（err）" if err else "")
app.destroy()
