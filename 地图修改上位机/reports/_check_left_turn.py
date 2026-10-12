# -*- coding: utf-8 -*-
"""只读检查：左栏「转弯补偿」表真的填进了内容（行数/表头/前几行文本）。用系统 Python（带 tkinter）。"""
import os, sys
HERE = os.path.dirname(os.path.split(os.path.abspath(__file__))[0])   # reports/ 的上级 = 地图修改上位机
sys.path.insert(0, os.path.join(HERE, "map_editor"))
os.chdir(os.path.join(HERE, "map_editor"))
import map_editor as E

app = E.App()
app.update()
t = app.tree_turn
kids = t.get_children()
print("树控件:", type(t).__name__)
print("列:", [t.heading(c)["text"] for c in ("#0", "ang", "br", "val", "src")])
print("行数:", len(kids), " 覆盖组合:", len(app.model.turn_coverage()["rows"]))
print("前 6 行：")
for k in kids[:6]:
    print("   ", repr(t.item(k, "text")), t.item(k, "values"), t.item(k, "tags"))
app.destroy()
