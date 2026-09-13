# -*- coding: utf-8 -*-
"""
_guismoke.py — 地图编辑器界面冒烟测试（会短暂弹一下窗口然后自动关）

跑法（仓库根）：
    python scripts/map_editor/_guismoke.py

检查：窗口能建起来、画布真的画出了节点/边、树能填满、选中/拖动/规划/导出
不抛异常。**不打开任何模态对话框**，所以可以无人值守跑。
"""
import math
import os
import sys
import shutil
import hashlib
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

FAIL = []


def check(cond, msg):
    print(("  [OK]   " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAIL.append(msg)


def step(msg):
    print("  ... %s" % msg, flush=True)


class _Ev:
    """假的鼠标事件（给 _on_node_press 等用）。"""

    def __init__(self, x=0, y=0, state=0):
        self.x, self.y, self.state = x, y, state
        self.x_root, self.y_root = x, y


def main():
    try:
        import tkinter as tk
        probe = tk.Tk()
        probe.withdraw()
        probe.destroy()
    except Exception as ex:
        print("没有可用的图形环境，跳过 GUI 冒烟测试：%s" % ex)
        return 0

    import map_editor as E

    # 不额外新建 Tk 根窗口：直接建 App，然后 update_idletasks() 让 tk 完成布局
    app = E.App()
    app.update_idletasks()
    app._fit_view()
    app.update()

    print("窗口标题:", app.title())
    print("画布尺寸: %dx%d  缩放: %.3f"
          % (app.canvas.winfo_width(), app.canvas.winfo_height(), app.scale))
    check(app.canvas.winfo_width() > 600,
          "画布宽度合理（%d > 600，之前被左右栏挤成 394）" % app.canvas.winfo_width())
    check(app.scale > 0.3, "缩放不为下限（%.3f）" % app.scale)
    check(app.bg.img is not None, "底图已载入（节点图.jpg）")

    # --- 工具栏必须放得下（曾经一行太长，右侧控件跑到屏幕外）---
    step("toolbar fits in window")
    app.update_idletasks()
    win_w = app.winfo_width()
    rows = [w for w in app.winfo_children()
            if isinstance(w, __import__("tkinter").ttk.Frame)]
    # 找工具栏容器：里面有两个 Frame（两行）
    tb_rows = []
    for w in app.winfo_children():
        try:
            subs = [c for c in w.winfo_children()
                    if c.winfo_class() == "TFrame"]
            if len(subs) >= 2 and all(s.winfo_reqheight() < 60 for s in subs):
                tb_rows = subs
                break
        except Exception:
            pass
    check(len(tb_rows) >= 3,
          "工具栏至少三行（找到 %d 行；曾因一行太长把控件挤到屏幕外）" % len(tb_rows))
    if tb_rows:
        widest = max(r.winfo_reqwidth() for r in tb_rows)
        check(widest <= max(win_w, 100),
              "每行宽度 %d <= 窗口宽 %d（不溢出）" % (widest, win_w))

    # --- 拖动节点 → 保存布局 → 重新载入，位置要保留 ---
    # 直接用假的"真实布局"验证隔离（内容非法会被 load 拒绝，不影响隔离测试）
    step("drag P7 then save/load layout")
    # ⚠️ 绝不动用户的 layouts/*.json！保存/载入都走临时沙箱文件。
    #    （曾经因为脚本直接写/删真实布局文件，把用户调好的布局弄丢了 —— 血的教训。）
    real_layout = app._layout_path()
    real_hash_before = None
    if os.path.isfile(real_layout):
        with open(real_layout, "rb") as fh:
            real_hash_before = hashlib.sha256(fh.read()).hexdigest()
    # 沙箱目录必须用普通 mkdir 创建：tempfile.mkdtemp() 建出来的目录
    # 在本环境的文件沙箱下写入会 PermissionError（工作区内也一样，实测踩过）。
    tmpdir = os.path.join(HERE, "_smoke_%d" % os.getpid())
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.makedirs(tmpdir, exist_ok=True)
    layout = os.path.join(tmpdir, "sandbox.json")
    try:
        n7 = app.model.node("P7")
        n7.x, n7.y = 777.0, 555.0
        app.model.dirty = True
        # path= 是专为测试留的入口：只写沙箱，不碰真实布局
        check(app.save_layout(show_msg=False, path=layout) and os.path.isfile(layout),
              "保存布局写出沙箱文件（不碰真实布局）")
        with open(layout, encoding="utf-8") as fh:
            blob = fh.read()
        check('"P7"' in blob and "777" in blob, "布局文件里含拖过的坐标")
        check('"background"' in blob, "布局文件里含底图标定")
        check('"constraints"' in blob, "布局文件里含约束设置")
        app.save_layout(show_msg=False, path=layout)     # 再存一次
        check(len(app.list_layouts()) >= 1,
              "list_layouts() 能列出布局（%d 个，含历史快照）" % len(app.list_layouts()))
        app.model.node("P7").x = 1.0
        app.load_layout_file(layout, quiet=True)
        check(abs(app.model.node("P7").x - 777.0) < 0.01,
              "载入布局后坐标恢复（=> 拖动能保留）")
        app.model.node("P7").x = 2.0
        app.load_layout_file(layout, quiet=True)
        check(abs(app.model.node("P7").x - 777.0) < 0.01, "可反复载入同一布局")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    # 真实布局必须原封不动
    if real_hash_before is not None:
        with open(real_layout, "rb") as fh:
            real_hash_after = hashlib.sha256(fh.read()).hexdigest()
        check(real_hash_before == real_hash_after,
              "真实布局文件未被冒烟测试改动（SHA256 一致）")
    check(not os.path.exists(layout), "沙箱布局已清理")

    # --- 底图：候选 / 反推标定 / 滑条 / 重置 ---
    step("background controls")
    check(hasattr(app.bg, "fit_to_nodes"), "背景管理器就位")
    check(len(E.list_bg_candidates()) >= 1,
          "发现 %d 张候选底图（可切换/自定义）" % len(E.list_bg_candidates()))
    n_pts, resid = app.bg.fit_to_nodes()
    check(n_pts >= 2, "用节点反推标定：%d 个点，残差 %.1f px" % (n_pts, resid))
    app.bg.opacity = 0.3
    app.redraw()
    app.update()
    app.bg_reset()
    app.update()
    app.refresh_bg_panel()
    check(app._bg_widgets.get("off_x") is not None, "底图控制面板已构建且不报错")
    check(callable(app._on_close), "_on_close 已注册为窗口关闭钩子")

    # --- 拖动约束（角度锁定 + 最小长度 + 引导线角度偏移）---
    step("drag constraints")
    check(isinstance(app.lock_angle.get(), bool)
          and isinstance(app.enforce_min_len.get(), bool),
          "约束开关状态可用（布局可覆盖保存值）")
    check(app._unit_k() > 0.01,
          "单位长度 K 有效 = %.4f px/cm（会被保存的布局覆盖，故只校验有效）"
          % app._unit_k())
    check(abs(E.DRAG_ANGLE_OFFSET - 90.0) < 1e-9,
          "引导线角度偏移 = 90°（用户要求：引导线要相对表里 angle 再转 90°）")

    # 引导线方向必须 = 表里 angle + 偏移（用一条长边验证；需切到「跟随角度表」模式，
    # 因为默认模式是"吸附水平/竖直"，那时方向偏好是 0/90/180/-90 而不是角度表）
    app.snap_mode.set("跟随角度表")
    _e = app.model.edge("N5", "N4")
    _ang = app.model.ang(_e)
    _dirs = app._edge_pref_dirs(_e, "N4")
    _expect = _ang + E.DRAG_ANGLE_OFFSET
    _got = math.degrees(math.atan2(_dirs[0][0], -_dirs[0][1]))
    _diff = abs((_got - _expect + 180) % 360 - 180)
    check(_diff < 0.01,
          "「跟随角度表」下引导线 = 表里 angle + 90°（表里%.0f° → 引导%.0f°）"
          % (_ang, _expect))
    app.snap_mode.set("吸附水平/竖直")

    _pt, info = app.solve_drag_position("S1", (200.0, 900.0))
    check(isinstance(info["feasible"], bool), "S1：求解返回明确可行性")
    check(all(it["len_ok"] for it in info["edges"]), "S1：长度 >= step*K")
    # 关键：约束矛盾时必须"放开不锁死"，否则某些节点怎么拖都不动
    if not info["feasible"]:
        check(abs(_pt[0] - 200.0) < 1e-6 and abs(_pt[1] - 900.0) < 1e-6,
              "约束矛盾时放开不吸附（节点仍跟着鼠标走）")
    else:
        check(True, "约束可满足，正常吸附")
    _pt2, info2 = app.solve_drag_position("P8", (400.0, 1200.0))
    check(isinstance(info2["feasible"], bool), "P8 度2：求解返回明确可行性")
    _pt3, info3 = app.solve_drag_position("C9", (1500.0, 1500.0))
    check(isinstance(info3["feasible"], bool), "C9 度3：求解返回明确可行性")
    # 自由模式 + 不限长度 → 位置完全不动（旧版用 lock_angle=False，现已由 snap_mode 取代）
    app.snap_mode.set("自由")
    app.enforce_min_len.set(False)
    _pt4, _info4 = app.solve_drag_position("C9", (1500.0, 1500.0))
    check(abs(_pt4[0] - 1500.0) < 1e-6 and abs(_pt4[1] - 1500.0) < 1e-6,
          "「自由」模式 + 关长度约束 → 可自由拖到任意位置")
    app.snap_mode.set("吸附水平/竖直")
    app.enforce_min_len.set(True)
    bad, k = app.constraint_violations()
    check(isinstance(bad, list) and k > 0,
          "违规清单可用：K=%.3f 时 %d 条边图上长度不足 step*K" % (k, len(bad)))
    app.redraw()
    app.update()
    check(True, "约束设置改动后重绘正常")

    # --- 点图形选边 + 快捷增删 ---
    step("edge picking + quick add/delete")
    check(E.EDGE_HIT_WIDTH >= 10,
          "边命中区加宽到 %gpx（不用精确点中细线）" % E.EDGE_HIT_WIDTH)
    # 每条边都应有一个"透明命中线"(width=EDGE_HIT_WIDTH) + 一条可见线
    _e0 = app.model.edges[0]
    _items = app._canvas_items["edges"].get(_e0.tag) or []
    _widths = [float(app.canvas.itemcget(i, "width") or 0) for i in _items]
    check(any(abs(w - E.EDGE_HIT_WIDTH) < 0.01 for w in _widths),
          "边 %s 有隐形命中线（widths=%s）" % (_e0.label(), _widths))
    # 离边 6px 处应能叠到命中线（用中点+法向偏移验证）
    _a = app.model.node(_e0.frm)
    _b = app.model.node(_e0.to)
    _dx, _dy = _b.x - _a.x, _b.y - _a.y
    _L = math.hypot(_dx, _dy) or 1.0
    _wx = (_a.x + _b.x) / 2 + (-_dy / _L) * 6
    _wy = (_a.y + _b.y) / 2 + (_dx / _L) * 6
    _sx, _sy = app.w2s(_wx, _wy)
    _found = app.canvas.find_overlapping(_sx, _sy, _sx, _sy)
    check(len(_found) > 0, "离边 6px 处仍能命中图形（叠到 %d 个 item）" % len(_found))

    # 连线模式：点两下直接建边（不弹对话框）
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

    # 快捷键 A / Esc
    app.connect_mode.set(False)
    app.select_node("N3")
    app.start_connect_from_sel()
    check(app.connect_from == "N3" and app.connect_mode.get(), "按 A 以选中节点为起点")
    app.cancel_connect()
    check(app.connect_from is None and not app.connect_mode.get(), "Esc 取消连线模式")

    # Delete 删边（不弹框）
    _e1 = app.model.edge("N13", "N12")
    if _e1:
        _n1 = len(app.model.edges)
        app.sel_edge = _e1
        app.sel_node = None
        app.delete_sel_edge()
        check(len(app.model.edges) == _n1 - 1, "Delete 删掉选中的边")
        app.undo()

    # --- 双击分派：节点/边/空白不得互相冲突 ---
    step("double-click dispatch")
    _calls = []
    _saved_new = app.create_node_dialog
    app.create_node_dialog = lambda x, y: _calls.append("new_node")
    try:
      # 双击边（中点）→ 选中边并显示在右侧属性栏，不建节点/弹窗
        _e = app.model.edge("N5", "N4")
        _a, _b = app.model.node(_e.frm), app.model.node(_e.to)
        _p1, _p2 = app.w2s(_a.x, _a.y), app.w2s(_b.x, _b.y)
        _mx, _my = (_p1[0] + _p2[0]) / 2, (_p1[1] + _p2[1]) / 2
        _calls.clear()
        app._on_bg_double(_Ev(_mx, _my))
        check(not _calls
              and app.sel_edge is not None
              and app._prop_widgets["from"].get() == app.sel_edge.frm
              and app._prop_widgets["to"].get() == app.sel_edge.to,
              "双击边 → 右侧属性栏显示边，不建节点/弹窗（%s）" % _calls)
        # 双击节点 → 什么都不弹
        _n = app.model.node("N3")
        _calls.clear()
        app._on_bg_double(_Ev(*app.w2s(_n.x, _n.y)))
        check(_calls == [], "双击节点 → 不弹建节点/编辑边（%s）" % _calls)
        # 空白普通双击 → 不建节点（防误触）
        _blank = None
        for cand in ((app.canvas.winfo_width() - 8, app.canvas.winfo_height() - 8),
                     (8, app.canvas.winfo_height() - 8),
                     (app.canvas.winfo_width() - 8, 8)):
            if app.node_at(*cand) is None and app._edge_near(*cand) is None:
                _blank = cand
                break
        if _blank:
            _calls.clear()
            app._on_bg_double(_Ev(*_blank))
            check(_calls == [], "空白普通双击 → 不建节点（防误触）")
            _calls.clear()
            app._on_bg_double(_Ev(_blank[0], _blank[1], state=0x0001))   # Shift
            check(_calls == ["new_node"], "Shift+双击空白 → 新建节点（%s）" % _calls)
        else:
            check(False, "找不到空白点做双击测试")
    finally:
        app.create_node_dialog = _saved_new

    # --- 边列表展示模式（合并双向 / 逐条 / 只看双向）---
    step("edge list display modes")
    _n_edges = len(app.model.edges)
    _n_bidir = sum(1 for e in app.model.edges if app.model.has_reverse(e))
    _n_seg = len({frozenset((e.frm, e.to)) for e in app.model.edges})

    def _rows(mode):
        app.edge_view.set(mode)
        app.refresh_trees()
        return list(app.tree_edges.get_children())

    _it = _rows("合并双向")
    check(len(_it) == _n_seg,
          "「合并双向」行数 %d == 线段数 %d（同一条线段两个方向合一）"
          % (len(_it), _n_seg))
    _both = [i for i in _it if i.startswith("b:")]
    check(len(_both) == _n_bidir // 2,
          "其中双向合并行 %d 条（= %d/2）" % (len(_both), _n_bidir))
    _vals = app.tree_edges.item(_both[0])["values"] if _both else None
    check(_vals and len(_vals) == 4 and _vals[2] not in (None, "", "—"),
          "合并行同时显示两方向的角度/step：%s" % (_vals,))
    _it2 = _rows("逐条")
    check(len(_it2) == _n_edges, "「逐条」行数 %d == 边数 %d" % (len(_it2), _n_edges))
    _it3 = _rows("只看双向")
    check(len(_it3) == _n_bidir,
          "「只看双向」行数 %d == 有反向边的边数 %d" % (len(_it3), _n_bidir))
    check(all("↔" in app.tree_edges.item(i)["text"] for i in _it3),
          "「只看双向」的行都标了 ↔")
    _rows("合并双向")          # 恢复默认

    # --- 拖动吸附（水平/竖直自动吸附）---
    step("snap to horizontal/vertical")
    check(app.snap_mode.get() == "吸附水平/竖直",
          "默认吸附模式 = 吸附水平/竖直（%s）" % app.snap_mode.get())
    check(E.SNAP_MODES == ("吸附水平/竖直", "跟随角度表", "自由"),
          "三种模式可选：%s" % (E.SNAP_MODES,))
    _leaf = app.model.node("P1")
    _e0 = [e for e in app.model.edges
           if e.frm == _leaf.name or e.to == _leaf.name][0]
    _on = app.model.node(_e0.to if _e0.frm == _leaf.name else _e0.frm)

    def _dir_deg(pt, o):
        return math.degrees(math.atan2(pt[0] - o.x, -(pt[1] - o.y)))

    def _axis_dev(a):
        return min(abs((a - x + 180) % 360 - 180) for x in E.AXIS_ANGLES)

    app.snap_mode.set("吸附水平/竖直")
    app.snap_tol.set(8.0)
    app.snap_near.set(25.0)
    _D = 300.0
    # 偏 5°（< 阈值）→ 精确吸正
    _w = (_on.x + math.sin(math.radians(5)) * _D,
          _on.y - math.cos(math.radians(5)) * _D)
    _p, _inf = app.solve_drag_position("P1", _w)
    check(_axis_dev(_dir_deg(_p, _on)) < 0.5 and _inf.get("snapped"),
          "偏 5° → 精确吸正（离轴 %.1f°）" % _axis_dev(_dir_deg(_p, _on)))
    # 偏 15°（阈值外、软范围内）→ 拉到最近轴但不标 snapped
    _w = (_on.x + math.sin(math.radians(15)) * _D,
          _on.y - math.cos(math.radians(15)) * _D)
    _p2, _inf2 = app.solve_drag_position("P1", _w)
    check(_axis_dev(_dir_deg(_p2, _on)) < 0.5 and not _inf2.get("snapped"),
          "偏 15° → 软拉扯到最近轴（离轴 %.1f°）"
          % _axis_dev(_dir_deg(_p2, _on)))
    # 偏 40°（超范围）→ 不干预
    _w = (_on.x + math.sin(math.radians(40)) * _D,
          _on.y - math.cos(math.radians(40)) * _D)
    _p3, _inf3 = app.solve_drag_position("P1", _w)
    check(math.hypot(_p3[0] - _w[0], _p3[1] - _w[1]) < 1.0,
          "偏 40° → 不吸附（位移 %.1f px）" % math.hypot(_p3[0] - _w[0], _p3[1] - _w[1]))
    # 自由模式 → 位置完全不动
    app.snap_mode.set("自由")
    _p4, _ = app.solve_drag_position("P1", _w)
    check(math.hypot(_p4[0] - _w[0], _p4[1] - _w[1]) < 1e-6,
          "「自由」模式不做方向约束")
    app.snap_mode.set("吸附水平/竖直")

    # --- 画布真的画了东西吗 ---
    nodes_drawn = len(app._canvas_items["nodes"])
    edges_drawn = len(app._canvas_items["edges"])
    check(nodes_drawn == len(app.model.nodes),
          "画布节点 item 数(%d) == 模型节点数(%d)" % (nodes_drawn, len(app.model.nodes)))
    check(edges_drawn == len(app.model.edges),
          "画布边 item 数(%d) == 模型边数(%d)" % (edges_drawn, len(app.model.edges)))
    check(len(app.canvas.find_all()) > 2 * len(app.model.edges),
          "画布上确实有图形（item 总数 %d）" % len(app.canvas.find_all()))

    # --- 树 ---
    check(len(app.tree_nodes.get_children()) == len(app.model.nodes),
          "节点树 %d 行" % len(app.tree_nodes.get_children()))
    # 边树行数取决于展示模式（默认「合并双向」→ 每线段一行）
    _mode = app.edge_view.get()
    _expect = (len({frozenset((e.frm, e.to)) for e in app.model.edges})
               if _mode == "合并双向" else len(app.model.edges))
    check(len(app.tree_edges.get_children()) == _expect,
          "边树 %d 行（模式「%s」应为 %d）：%s"
          % (len(app.tree_edges.get_children()), _mode, _expect,
             app.edge_view.get()))

    # --- 选中一个节点 ---
    step("select_node P7")
    app.select_node("P7")
    app.update()
    check(app.sel_node == "P7", "选中 P7")
    check(app._prop_widgets["name"].get() == "P7", "属性面板显示 P7")

    # --- 选中一条边 ---
    step("select edge C9->P7")
    e = app.model.edge("C9", "P7")
    app._on_edge_press(type("Ev", (), {"x": 0, "y": 0})(), e)
    app.update()
    check(app._prop_widgets["step"].get() == "260", "属性面板显示 C9->P7 的 step=260")
    check(app._prop_widgets["func"].get() == "BSoutPole", "属性面板显示 func=BSoutPole")

    # --- 拖动节点（直接改模型，模拟 _on_motion 的效果）---
    step("move node P7")
    n = app.model.node("P7")
    old = (n.x, n.y)
    app.model.move_node("P7", n.x + 25, n.y - 15)
    app.redraw()
    app.update()
    check((app.model.node("P7").x, app.model.node("P7").y) == (old[0] + 25, old[1] - 15),
          "节点坐标可改并重绘")

    # --- 标注三档都不炸 ---
    for mode in ("无", "标准", "详细"):
        app.label_mode.set(mode)
        app.redraw()
        app.update()
        check(True, "标注模式「%s」重绘正常" % mode)
    app.label_mode.set("标准")
    app.redraw()

    # --- 图上长度显示与几何报警 ---
    step("edge length labels and geometry warnings")
    app.label_mode.set("无")
    app.show_edge_lengths.set(True)
    app.show_geometry_warnings.set(True)
    app.redraw()
    _texts = [app.canvas.itemcget(_item, "text")
              for _item in app.canvas.find_all()
              if app.canvas.type(_item) == "text"]
    check(any("图 " in text and "cm" in text for text in _texts),
          "开启边长显示后，箭头旁有当前单位长度标签")
    _warning_data = app._geometry_warning_data()
    check(isinstance(_warning_data, list), "几何报警能生成边偏差清单")
    check(len(app._geometry_warning_map()) == len(_warning_data),
          "几何报警清单能映射到对应边")
    app.show_edge_lengths.set(False)
    app.show_geometry_warnings.set(False)
    app.redraw()

    # --- 校验面板 ---
    items = app.do_validate()
    check(isinstance(items, list) and len(items) > 0, "校验返回 %d 条" % len(items))
    text = app.txt_val.get("1.0", "end")
    check("单向边" in text, "校验文本里能看到单向边告警")

    # --- 规划 + 导出（不动文件）---
    app.waypoints = ["N2", "P1", "N5"]
    app._refresh_wp()
    app.plan_route()
    app.update()
    check(app.route and app.route[0] == "N2" and app.route[-1] == "N5",
          "规划路线 %s" % (" -> ".join(app.route) if app.route else "(空)"))
    check("route[100]" in app.txt_route.get("1.0", "end"), "结果框里有 route[] 数组")

    # --- 纯文本导出（不弹窗）---
    for fn, name in ((app.model.export_edge_table, "NavEdgeTbl"),
                     (app.model.export_edges_only, "表体"),
                     (app.model.export_enum, "enum"),
                     (app.model.export_nav_edge_count, "NAV_EDGE_COUNT"),
                     (app.model.export_eval_report, "求值自检")):
        blob = fn()
        check(isinstance(blob, str) and len(blob) > 10, "导出 %s（%d 字符）" % (name, len(blob)))

    # --- 新建/删除/撤销 走一遍（不开对话框，直接调模型 + 刷新）---
    snap = app.model.snapshot()
    app.model.add_node("ZZTEST", 700, 600, "")
    app.model.add_edge("ZZTEST", "C9", flag="NO", angle="0", step="10",
                       speed="SPEED2", func="NONE")
    app.model.add_edge("C9", "ZZTEST", flag="NO", angle="180", step="10",
                       speed="SPEED2", func="NONE")
    app.refresh_all()
    app.update()
    check(app.model.node("ZZTEST") is not None, "加节点后界面刷新正常")
    check(len(app.tree_nodes.get_children()) == len(app.model.nodes),
          "刷新后节点树同步")
    app.model.restore(snap)
    app.refresh_all()
    app.update()
    check(app.model.node("ZZTEST") is None, "restore 后节点消失")

    # --- 缩放/平移不炸 ---
    ev = type("Ev", (), {"x": 400, "y": 300, "delta": 120})()
    app._on_wheel(ev)
    app.update()
    app._on_wheel(type("Ev", (), {"x": 400, "y": 300, "delta": -120})())
    app.update()
    check(True, "滚轮缩放正常")

    app.destroy()

    print()
    if FAIL:
        print("失败 %d 项：" % len(FAIL))
        for f in FAIL:
            print("  -", f)
        return 1
    print("GUI 冒烟测试全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
