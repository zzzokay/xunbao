# -*- coding: utf-8 -*-
"""AI 过程脚本：拍「线索路线…」对话框（含 DPI 1.5 换算）—— 看两个开关下拉显示的当前值。"""
import os, sys, time, tkinter as tk
HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor")
sys.path.insert(0, ME)
import map_editor as E
from PIL import ImageGrab

app = E.App(os.path.join(E.M.ROOT, "寻宝地图", "节点图.jpg"))
app.update_idletasks()
app.plan_clue_route_dialog()
app.update()
d = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
d.attributes("-topmost", True); d.lift()
for _ in range(6):
    app.update(); time.sleep(0.08)
full = ImageGrab.grab()
s = full.size[0] / app.winfo_screenwidth()
x, y, w, h = d.winfo_rootx(), d.winfo_rooty(), d.winfo_width(), d.winfo_height()
box = (int(x * s), int(y * s), int((x + w) * s), int((y + h) * s))
p = os.path.join(HERE, "线索路线对话框_开关显示当前值.png")
full.crop(box).save(p)
print("saved", p, full.crop(box).size)
d.destroy(); app.destroy()
