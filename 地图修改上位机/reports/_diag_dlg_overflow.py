# -*- coding: utf-8 -*-
"""AI 过程脚本：递归查两个对话框里"右边缘超出窗口"的控件（横向裁切）。"""
import os, sys, tkinter as tk
HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor")
sys.path.insert(0, ME)
import map_editor as E

app = E.App(os.path.join(E.M.ROOT, "寻宝地图", "节点图.jpg"))
app.update_idletasks()


def scan(tag, opener):
    opener()
    app.update_idletasks()
    d = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    W, H = d.winfo_width(), d.winfo_height()
    print("==== %s 窗口 %dx%d  req %dx%d ===="
          % (tag, W, H, d.winfo_reqwidth(), d.winfo_reqheight()))
    bad = []

    def walk(w):
        for c in w.winfo_children():
            try:
                cls = c.winfo_class()
                rx = c.winfo_rootx() - d.winfo_rootx()
                ry = c.winfo_rooty() - d.winfo_rooty()
                x1 = rx + c.winfo_width()
                y1 = ry + c.winfo_height()
            except Exception:                                # noqa: BLE001
                continue
            txt = ""
            try:
                txt = str(c.cget("text"))[:26]
            except Exception:                                # noqa: BLE001
                pass
            if x1 > W or y1 > H:
                bad.append((cls, rx, ry, x1, y1, txt))
            walk(c)
    walk(d)
    for cls, rx, ry, x1, y1, txt in bad[:14]:
        print("   ✗ %-10s x=%4d..%-4d y=%4d..%-4d %s%s"
              % (cls, rx, x1, ry, y1, txt,
                 ("  ← 右超 %d" % (x1 - W)) if x1 > W else "",
                 ("  ← 下超 %d" % (y1 - H)) if y1 > H else ""))
    print("   越界控件数 = %d" % len(bad))
    d.destroy()
    app.update()


scan("线索路线", app.plan_clue_route_dialog)
scan("二轮路线", app.plan_round2_route_dialog)
app.destroy()
