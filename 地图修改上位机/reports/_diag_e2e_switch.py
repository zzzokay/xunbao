# -*- coding: utf-8 -*-
"""AI 过程脚本：端到端 —— 按对话框默认（跟随 config.h）走一遍，看画布有没有 S1/S2。"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor")
sys.path.insert(0, ME)
import map_editor as E
import map_model as M

app = E.App(os.path.join(E.M.ROOT, "寻宝地图", "节点图.jpg"))
app.update_idletasks()
print("下拉档位 =", app._switch_vals("UPRIGHT_TOUR_ENABLE"))
punch = app._punch_on("跟随 config.h")
tour = app._tour_on("跟随 config.h")
print("跟随 config.h 解析：punch=%s  tour=%s" % (punch, tour))

ST_ALL = "第一轮·完整路线（去程+门区+东区+回程 自动拼接，画布分色）"
DOORS = [M.NO_PASS, M.NO_PASS, M.ONE_WAY_PASS, M.CAN_PASS]
for tsel, tval in (("未定", None), ("2 · P1", 2), ("3 · P3", 3), ("4 · P4", 4),
                   ("5 · P5", 5), ("6 · P6", 6)):
    secs, flat, err = app._clue_route_sections(ST_ALL, 3, (5, 7), DOORS, tval, "full",
                                              punch, tour)
    has = [n for n in ("S1", "S2") if n in (flat or [])]
    pun = [n for n in ("P3", "P4") if n in (flat or [])]
    print("  宝物=%-8s err=%-6s 跳数=%-3s  S1/S2=%-8s 画布里出现过的P3/P4=%s"
          % (tsel, "无" if err is None else err[0], len(flat or []), has or "无", pun or "无"))
app.destroy()
