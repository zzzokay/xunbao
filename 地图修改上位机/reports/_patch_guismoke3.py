# -*- coding: utf-8 -*-
"""重写 guismoke 的 Shift 用例（新语义：选中起点 → 按住 Shift 点终点连线），
并把 _link 标注为遗留。"""
import io

# ---------- A) guismoke ----------
P = "_guismoke.py"
d = open(P, "rb").read()
assert d.count(b"\r\n") == 0 and d[:3] != b"\xef\xbb\xbf"

old = u'''    # ⭐ Shift = 连线（10-07 新语义）：Shift+点只有"定/续起点"这一个意思，不留下常驻模式。
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
'''

new = u'''    # ⭐ Shift = 连线（用户定的操作）：**先普通单击选中起点 → 按住 Shift 点别的点即连线 → 松开 Shift 回普通**。
    #    Shift 是"按住才生效"的修饰键、不改 connect_mode ⇒ 松开就不可能误连。
    step("Shift = connect from the selected node (held modifier, no sticky mode)")
    app.cancel_connect()

    def _drop_pair(a, b):
        for _x, _y in ((a, b), (b, a)):
            if app.model.edge(_x, _y):
                app.model.remove_edge(_x, _y)

    def _shift_click(name):
        app._on_node_press(_Ev(0, 0, state=0x0001), name)
        app._on_release(_Ev(0, 0, state=0x0001))

    # 动态挑"原本没有边"的节点组，别硬编码（地图会变）
    _names = [n.name for n in app.model.nodes]
    _free = [(x, y) for x in _names for y in _names
             if x != y and app.model.edge(x, y) is None and app.model.edge(y, x) is None]
    _st, _en = _free[0]
    _rd = next(y for x, y in _free if x == _en and y != _st)
    _ne0 = len(app.model.edges)

    # ① 没选中任何起点时 Shift+点：只提示，不建边、也不乱设起点
    app.sel_node = None
    app.connect_from = None
    _shift_click(_st)
    check(len(app.model.edges) == _ne0 and app.sel_node is None,
          "没选中起点时 Shift+点只提示，不建边也不乱设起点")

    # ② 普通单击选中起点 → 按住 Shift 点终点 ⇒ 连线，选中挪到终点
    app.select_node(_st)
    _shift_click(_en)
    check(app.model.edge(_st, _en) is not None,
          "普通单击选中 %s → 按住 Shift 点 %s ⇒ 连线" % (_st, _en))
    check(app.sel_node == _en, "连完选中挪到终点（可一路链式连下去）")
    check(not app.connect_mode.get(), "Shift+点不会留下常驻「连线模式」（松开即回普通）")

    # ③ 一直按着 Shift 继续点 ⇒ 链式
    _c1 = len(app.model.edges)
    _shift_click(_rd)
    check(app.model.edge(_en, _rd) is not None and len(app.model.edges) > _c1,
          "按住 Shift 继续点 %s ⇒ 链式再连一条（边数 %d → %d）"
          % (_rd, _c1, len(app.model.edges)))
    check(app.sel_node == _rd, "选中继续跟到 %s" % _rd)

    # ④ 松开 Shift ⇒ 普通点击只选中、不连线
    _c2 = len(app.model.edges)
    app._on_node_press(_Ev(0, 0), _st)
    app._on_release(_Ev(0, 0))
    check(len(app.model.edges) == _c2 and app.sel_node == _st,
          "松开 Shift 后普通点只选中、不连线（边数 %d 不变）" % _c2)

    # ⑤ Shift+点起点自己 ⇒ 不连自环
    _shift_click(_st)
    check(app.model.edge(_st, _st) is None, "Shift+点起点自己不会连出自环")

    _drop_pair(_st, _en)
    _drop_pair(_en, _rd)
    check(len(app.model.edges) == _ne0, "Shift 用例跑完边数复原（%d 条）" % _ne0)

    # 双击节点：不再连线、不动 connect_mode / connect_from
    app.cancel_connect()
    app._on_node_double(_Ev(0, 0), _st)
    check(app.connect_from is None and not app.connect_mode.get(),
          "双击节点不再进入连线模式（mode=%s from=%s）"
          % (app.connect_mode.get(), app.connect_from))
    app.cancel_connect()
'''
ob, nb = old.encode("utf-8"), new.encode("utf-8")
c = d.count(ob)
if c != 1:
    raise SystemExit("guismoke 块命中 %d 次（要求 1），放弃" % c)
open(P, "wb").write(d.replace(ob, nb))
print("OK _guismoke.py")

# ---------- B) map_editor: _link 标注为遗留 ----------
P2 = "map_editor.py"
d2 = open(P2, "rb").read()
oldb = u'        self._link = None             # 连线状态\n'
newb = u'        self._link = None             # 连线状态（10-07 起 Shift+拖出拉边已取消，此属性仅遗留/自愈清态用）\n'
c2 = d2.count(oldb.encode("utf-8"))
if c2 != 1:
    raise SystemExit("_link 注释命中 %d 次，放弃" % c2)
open(P2, "wb").write(d2.replace(oldb.encode("utf-8"), newb.encode("utf-8")))
print("OK map_editor.py (_link 注释)")
