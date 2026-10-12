# -*- coding: utf-8 -*-
"""给 _guismoke.py 补 Shift 语义与「双击不再连线」的断言。"""
P = "_guismoke.py"
d = open(P, "rb").read()
assert d.count(b"\r\n") == 0 and d[:3] != b"\xef\xbb\xbf", "行尾/BOM 不符合预期"

old = u'''    app.selected_nodes = set()
    app.selected_edges = set()

    # 快捷键 A / Esc
'''
new = u'''    app.selected_nodes = set()
    app.selected_edges = set()

    # ⭐ Shift = 连线（10-07 新语义）：Shift+点只有"定/续起点"这一个意思，不留下常驻模式。
    #    "双击节点 = 进入连线模式"这条易误触入口已删除（用户报"连线太容易触发"）。
    step("Shift = connect (pick start by click, no sticky mode)")
    app.cancel_connect()
    _ne0 = len(app.model.edges)

    def _drop_pair(a, b):
        for _x, _y in ((a, b), (b, a)):
            if app.model.edge(_x, _y):
                app.model.remove_edge(_x, _y)

    def _shift_click(name):
        app._on_node_press(_Ev(0, 0, state=0x0001), name)
        app._on_release(_Ev(0, 0, state=0x0001))

    _shift_click("N13")
    check(app.connect_from == "N13" and not app.connect_mode.get(),
          "Shift+点第一个点 = 定起点，且不会留下常驻「连线模式」（mode=%s from=%s）"
          % (app.connect_mode.get(), app.connect_from))
    app._on_node_press(_Ev(0, 0), "N16")          # 松开 Shift，普通点第二个点
    app._on_release(_Ev(0, 0))
    check(app.connect_from is None and app.model.edge("N13", "N16") is not None,
          "松开 Shift 后普通点第二个点 ⇒ 边建好（N13→N16）")
    _drop_pair("N13", "N16")

    app.cancel_connect()
    _shift_click("N13")
    _shift_click("N16")
    check(app.connect_from is None and app.model.edge("N13", "N16") is not None,
          "按住 Shift 点两下同样能建边")
    _drop_pair("N13", "N16")
    check(len(app.model.edges) == _ne0, "Shift 用例跑完边数复原（%d 条）" % _ne0)

    app.cancel_connect()
    app._on_node_double(_Ev(0, 0), "N13")
    check(app.connect_from is None and not app.connect_mode.get(),
          "双击节点不再进入连线模式（mode=%s from=%s）"
          % (app.connect_mode.get(), app.connect_from))
    # Shift+微动仍按"点击"处理（抖动容忍）；Shift+真拖动才是"拉出新边"
    app.cancel_connect()
    app._on_node_press(_Ev(100, 100, state=0x0001), "N13")
    app._on_motion(_Ev(102, 101))
    check(app._link is not None and not app._link.get("armed"),
          "Shift+按住只挪 2/1 px ⇒ 还没进入「拉出新边」")
    app._on_release(_Ev(102, 101))
    check(app.connect_from == "N13", "Shift+按住没动就松手 ⇒ 当「定起点」处理（%s）"
          % app.connect_from)
    app.cancel_connect()

    # 快捷键 A / Esc
'''
ob, nb = old.encode("utf-8"), new.encode("utf-8")
c = d.count(ob)
if c != 1:
    raise SystemExit("命中 %d 次（要求 1），放弃" % c)
d = d.replace(ob, nb)
assert d.count(b"\r\n") == 0
open(P, "wb").write(d)
print("已写盘", len(d), "bytes")
