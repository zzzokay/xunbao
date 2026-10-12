# -*- coding: utf-8 -*-
"""诊断3：真实事件链 + 起点/终点都落在空白处，测 Ctrl 框选 + 群拖。不改文件。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor")
if ME not in sys.path:
    sys.path.insert(0, ME)

import map_editor as E


def main():
    app = E.App()
    app.update_idletasks()
    app._fit_view()
    app.update()

    def scr(nm):
        return app.w2s(*app._node_xy(nm))

    node_items = set()
    for lst in app._canvas_items["nodes"].values():
        node_items.update(lst)

    def empty_at(x, y):
        hits = set(app.canvas.find_overlapping(x - 2, y - 2, x + 2, y + 2))
        return not (hits & node_items)

    a = "S1"
    b = "P1"
    pts = [scr(a), scr(b)]
    bx0 = int(min(p[0] for p in pts)); by0 = int(min(p[1] for p in pts))
    bx1 = int(max(p[0] for p in pts)); by1 = int(max(p[1] for p in pts))

    # 从 bbox 角向外找空白起点（最多退 80px）
    sx = sy = None
    for d in range(12, 90, 4):
        cx, cy = bx0 - d, by0 - d
        if 2 < cx < app.canvas.winfo_width() - 2 and 2 < cy < app.canvas.winfo_height() - 2 \
                and empty_at(cx, cy):
            sx, sy = cx, cy
            break
    print("marquee start (empty)=%s,%s  end=%s,%s" % (sx, sy, bx1 + 12, by1 + 12))
    if sx is None:
        print("!! 找不到空白起点"); app.destroy(); return

    app.canvas.event_generate("<Motion>", x=sx, y=sy); app.update()
    app.canvas.event_generate("<ButtonPress-1>", x=sx, y=sy, state=0x0004); app.update()
    print("marquee after press: %r (None=没进框选分支)" % getattr(app, "_marquee", None))
    app.canvas.event_generate("<B1-Motion>", x=bx1 + 12, y=by1 + 12, state=0x0004); app.update()
    app.canvas.event_generate("<ButtonRelease-1>", x=bx1 + 12, y=by1 + 12, state=0x0004); app.update()
    print("selected_nodes=%s" % sorted(app.selected_nodes))
    print("status: %s" % app.status_var.get())

    if len(app.selected_nodes) > 1:
        ax, ay = int(scr(a)[0]), int(scr(a)[1])
        bb = {nm: app._node_xy(nm) for nm in sorted(app.selected_nodes)}
        app.canvas.event_generate("<Motion>", x=ax, y=ay); app.update()
        app.canvas.event_generate("<ButtonPress-1>", x=ax, y=ay); app.update()
        print("group press -> _drag=%r" % (app._drag,))
        app.canvas.event_generate("<B1-Motion>", x=ax + 45, y=ay + 35); app.update()
        app.canvas.event_generate("<ButtonRelease-1>", x=ax + 45, y=ay + 35); app.update()
        for nm in sorted(app.selected_nodes):
            print("  REAL group %s: %s -> %s moved=%s"
                  % (nm, bb[nm], app._node_xy(nm), bb[nm] != app._node_xy(nm)))
    else:
        print("!! 真实事件下框选没选中 >1 节点")

    app.destroy()


if __name__ == "__main__":
    main()
