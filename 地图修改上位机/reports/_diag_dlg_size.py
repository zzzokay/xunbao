# -*- coding: utf-8 -*-
"""AI 过程脚本：量「线索路线…」「二轮路线…」两个对话框的真实需求尺寸 vs 设定尺寸。"""
import os
import sys
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor")
sys.path.insert(0, ME)
import map_editor as E                                       # noqa: E402

app = E.App(os.path.join(E.M.ROOT, "寻宝地图", "节点图.jpg"))
app.update_idletasks()


def dump(tag, opener):
    opener()
    app.update_idletasks()
    tops = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
    if not tops:
        print(tag, "没建起来")
        return
    d = tops[-1]
    frm = [c for c in d.winfo_children()][0]
    print("==== %s ====" % tag)
    print("  窗口 geometry=%s  实际=%dx%d  req=%dx%d"
          % (d.geometry(), d.winfo_width(), d.winfo_height(),
             d.winfo_reqwidth(), d.winfo_reqheight()))
    print("  内容 frm req=%dx%d" % (frm.winfo_reqwidth(), frm.winfo_reqheight()))
    # 逐个子控件看有没有被窗口底边裁掉
    rows = []
    for w in frm.winfo_children():
        try:
            info = w.grid_info()
        except Exception:                                    # noqa: BLE001
            continue
        if not info:
            continue
        rows.append((int(info.get("row", 0)), w.winfo_class(),
                     w.winfo_reqwidth(), w.winfo_reqheight(),
                     w.winfo_y(), w.winfo_y() + w.winfo_height()))
    for r, cls, rw, rh, y0, y1 in sorted(rows):
        flag = ""
        if y1 > d.winfo_height():
            flag = "  <== 超出窗口底边 %d > %d" % (y1, d.winfo_height())
        print("    row=%-2d %-9s req=%4dx%3d  y=%4d..%-4d%s" % (r, cls, rw, rh, y0, y1, flag))
    d.destroy()
    app.update()


dump("线索路线", app.plan_clue_route_dialog)
dump("二轮路线", app.plan_round2_route_dialog)
app.destroy()
