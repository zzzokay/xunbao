# -*- coding: utf-8 -*-
"""诊断：单拖 / 群拖 在真实事件序列下到底走没走。不改任何文件。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor")
if ME not in sys.path:
    sys.path.insert(0, ME)

import map_editor as E


class _Ev:
    def __init__(self, x=0, y=0, state=0):
        self.x, self.y, self.state = x, y, state
        self.x_root, self.y_root = x, y


def main():
    app = E.App()
    app.update_idletasks()
    app._fit_view()
    app.update()
    app.model = E.M.MapModel.load_from_sources()
    app.sel_node = app.sel_edge = None
    app.selected_nodes = set()
    app.selected_edges = set()
    app.undo_stack.clear()
    app.redo_stack.clear()
    app.refresh_all()
    app.update()

    print("connect_mode=%s connect_from=%s adjust_bg=%s show_bg=%s"
          % (app.connect_mode.get(), app.connect_from,
             app.adjust_bg.get(), app.show_bg.get()))

    # 找两个都有图的节点，且屏幕坐标在画布内
    names = [n.name for n in app.model.nodes][:6]
    a, b = names[0], names[1]
    print("case nodes:", a, b)

    def scr(nm):
        return app.w2s(*app._node_xy(nm))

    # ---------- 单拖 ----------
    ax, ay = scr(a)
    before = app._node_xy(a)
    app._on_node_press(_Ev(int(ax), int(ay)), a)
    print("single-press -> _drag=%r" % (app._drag,))
    app._on_motion(_Ev(int(ax) + 40, int(ay) + 30))
    after = app._node_xy(a)
    app._on_release(_Ev(int(ax) + 40, int(ay) + 30))
    print("single drag: before=%s after=%s moved=%s"
          % (before, after, before != after))

    # ---------- 群拖 ----------
    app.model = E.M.MapModel.load_from_sources()
    app.refresh_all()
    app.update()
    pts = [scr(a), scr(b)]
    bx0 = min(p[0] for p in pts) - 10
    by0 = min(p[1] for p in pts) - 10
    bx1 = max(p[0] for p in pts) + 10
    by1 = max(p[1] for p in pts) + 10
    app._on_bg_press(_Ev(int(bx0), int(by0), state=0x0004))
    print("marquee started: %r" % (app._marquee,))
    app._on_motion(_Ev(int(bx1), int(by1)))
    app._on_release(_Ev(int(bx1), int(by1)))
    print("selected_nodes=%s selected_edges=%s"
          % (sorted(app.selected_nodes), sorted(app.selected_edges)))

    if len(app.selected_nodes) > 1:
        ax, ay = scr(a)
        b_before = {nm: app._node_xy(nm) for nm in (a, b)}
        app._on_node_press(_Ev(int(ax), int(ay)), a)
        print("group-press -> _drag=%r" % (app._drag,))
        app._on_motion(_Ev(int(ax) + 50, int(ay) + 40))
        b_after = {nm: app._node_xy(nm) for nm in (a, b)}
        app._on_release(_Ev(int(ax) + 50, int(ay) + 40))
        for nm in (a, b):
            print("  group %s: %s -> %s moved=%s"
                  % (nm, b_before[nm], b_after[nm], b_before[nm] != b_after[nm]))
    else:
        print("!! 框选没选到 >1 个节点，群拖无从测起")

    app.destroy()


if __name__ == "__main__":
    main()
