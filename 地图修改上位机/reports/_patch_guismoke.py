# -*- coding: utf-8 -*-
"""更新 _guismoke.py：连线落在松手上 + 补拖动优先/抖动容忍/残留自愈用例。
字节级替换（LF 不变），任一处不命中就整体不写盘。"""
P = "_guismoke.py"
d = open(P, "rb").read()
crlf = d.count(b"\r\n")
assert crlf == 0 and d[:3] != b"\xef\xbb\xbf", "行尾/BOM 不符合预期"

patches = []

old1 = u'''    # 连线模式：点两下直接建边（不弹对话框）
    step("connect mode click-click")
    app.var_quick_both.set(True)
    _n0 = len(app.model.edges)
    app.connect_mode.set(True)
    app.connect_from = None
    app._on_node_press(_Ev(0, 0), "N13")
    check(app.connect_from == "N13", "第一下选中起点 N13")
    app._on_node_press(_Ev(0, 0), "N16")
    check(app.connect_from is None, "第二下清掉起点（完成连线）")
    check(len(app.model.edges) == _n0 + 2,
          "双向边自动建好（边数 %d → %d）" % (_n0, len(app.model.edges)))
    check(app.model.edge("N13", "N16") and app.model.edge("N16", "N13"),
          "N13↔N16 两个方向都在")
    # 删掉刚建的这一对
    app.model.remove_edge("N13", "N16")
    app.model.remove_edge("N16", "N13")
    check(len(app.model.edges) == _n0, "删除这一对后回到 %d 条" % _n0)
'''

new1 = u'''    # 连线模式：点两下直接建边（不弹对话框）
    # ⚠️ 连线现在落在**松手**上（拖动优先：按住动了=拖节点，按住没动=选起点），
    #    所以"一次点击"必须写成 press + 原地 release，只调 press 是不够的。
    step("connect mode click-click")
    app.var_quick_both.set(True)
    _n0 = len(app.model.edges)
    app.connect_mode.set(True)
    app.connect_from = None

    def _click(name):
        """模拟一次完整左键点击（按下 → 原地松开）。"""
        app._on_node_press(_Ev(0, 0), name)
        app._on_release(_Ev(0, 0))

    _click("N13")
    check(app.connect_from == "N13", "第一下选中起点 N13")
    _click("N16")
    check(app.connect_from is None, "第二下清掉起点（完成连线）")
    check(len(app.model.edges) == _n0 + 2,
          "双向边自动建好（边数 %d → %d）" % (_n0, len(app.model.edges)))
    check(app.model.edge("N13", "N16") and app.model.edge("N16", "N13"),
          "N13↔N16 两个方向都在")
    # 删掉刚建的这一对
    app.model.remove_edge("N13", "N16")
    app.model.remove_edge("N16", "N13")
    check(len(app.model.edges) == _n0, "删除这一对后回到 %d 条" % _n0)

    # ⭐ 拖动优先：连线模式开着也必须能拖动节点。
    #    踩过的坑：连线模式一被打开（双击节点 / 按 A 键 / 勾工具栏复选框都会打开），
    #    点节点就全被 _connect_pick 吃掉 ⇒ 单拖和群拖一起失效；用户看到的是
    #    "Ctrl 框选照样能选出一堆紫色点，但一拖就全哑"。
    step("connect mode must NOT eat dragging (drag wins)")
    app.adjust_bg.set(False)
    app.connect_from = None
    _p0 = app._node_xy("S1")
    app._on_node_press(_Ev(100, 100), "S1")
    check(app._drag is not None and app._drag.get("connect"),
          "连线模式下按住节点：先装好拖动状态，而不是直接跑去选连线起点")
    app._on_motion(_Ev(134, 122))              # 位移 34/22 px，超过 DRAG_START_PX
    check(app._drag["moved"] and app._node_xy("S1") != _p0,
          "连线模式下拖动 S1 真的移动了：%s → %s" % (_p0, app._node_xy("S1")))
    app._on_release(_Ev(134, 122))
    check(app.connect_from is None, "拖动之后不会被当成'选连线起点'")
    check(not app._drag, "松手后拖动状态已清干净")
    app.undo()                                 # 撤掉这次拖动，别影响后面的断言

    # ⭐ 抖动容忍：按住但几乎没动 ⇒ 连线模式下仍按"选起点"处理（不然点击全变成微拖）
    app.connect_from = None
    app._on_node_press(_Ev(100, 100), "S1")
    app._on_motion(_Ev(102, 101))              # 只挪 2/1 px < DRAG_START_PX ⇒ 不算拖动
    check(not app._drag["moved"], "微微抖动（≤%d px）不触发拖动" % E.DRAG_START_PX)
    app._on_release(_Ev(102, 101))
    check(app.connect_from == "S1",
          "按住没动就松手 ⇒ 按'选连线起点'处理（%s）" % app.connect_from)
    app.cancel_connect()

    # ⭐ 残留指针状态自愈：松开鼠标时指针不在画布上（拖到左右面板外松手）会漏掉
    #    <ButtonRelease-1> ⇒ _drag/_link/_marquee 残留；旧代码"见残留就 return break"，
    #    空白点击又清不掉 ⇒ Ctrl 框选在本次运行里**永久失效**且不报错。
    step("stale pointer state self-heals (marquee never dies)")
    app.adjust_bg.set(False)
    app.connect_from = None
    app._drag = {"name": "S1", "dx": 0, "dy": 0, "moved": False}   # 假装松手事件丢了
    app._on_bg_press(_Ev(500, 500, state=0x0004))
    check(app._drag is None, "空白按下会清掉残留 _drag，而不是直接 return break")
    check(getattr(app, "_marquee", None), "清掉残留后 Ctrl 框选能正常开始（不是永久废掉）")
    app._marquee = None
    app.selected_nodes = set()
    app.selected_edges = set()
'''
patches.append((old1, new1))

old2 = u'''    app._on_node_right(_Ev(), "C6")                      # ④ 左键点目标也能完成
    app._on_node_press(_Ev(), "C8")
    check(app.connect_from is None and app.model.edge("C6", "C8") is not None,
          "右键起点后左键点目标也能建边（C6→C8）")
'''
new2 = u'''    app._on_node_right(_Ev(), "C6")                      # ④ 左键点目标也能完成
    app._on_node_press(_Ev(), "C8")
    app._on_release(_Ev())                               # 连线落在松手上（拖动优先）
    check(app.connect_from is None and app.model.edge("C6", "C8") is not None,
          "右键起点后左键点目标也能建边（C6→C8）")
'''
patches.append((old2, new2))

for i, (o, n) in enumerate(patches, 1):
    ob, nb = o.encode("utf-8"), n.encode("utf-8")
    c = d.count(ob)
    if c != 1:
        raise SystemExit("patch %d 命中 %d 次（要求 1），整体放弃" % (i, c))
    d = d.replace(ob, nb)
    print("patch %d OK" % i)

assert d.count(b"\r\n") == 0
open(P, "wb").write(d)
print("已写盘")
