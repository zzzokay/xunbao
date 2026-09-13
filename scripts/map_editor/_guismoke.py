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
import json
import time
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

    # ⚠️ App() 会自动载入用户保存的 layouts/default.json，而那份布局**可能已经和固件源码不同**
    # （用户会存试验性的改动；本项目就踩过一次：布局里多了 C10、少了 C9↔P7/B7↔C6）。
    # 冒烟测试的断言一律以**固件源码**为准，所以这里强制回到源码，保证结果不依赖用户数据。
    _old_pos = {n.name: (n.x, n.y) for n in app.model.nodes}
    _old_bg = dict(getattr(app.model, "background", {}) or {})
    app.model = E.M.MapModel.load_from_sources()
    app.model.background = _old_bg
    for _n in app.model.nodes:                     # 保住用户拖好的位置
        if _n.name in _old_pos:
            _n.x, _n.y = _old_pos[_n.name]
    app.sel_node = app.sel_edge = None
    app.route, app.route_split = [], None
    app.undo_stack.clear()
    app.redo_stack.clear()
    app._apply_model_background()
    app.refresh_all()
    app.update()
    _src = E.M.MapModel.load_from_sources()
    _src_e0 = _src.edges[0]
    check(len(app.model.nodes) == len(_src.nodes) and len(app.model.edges) == len(_src.edges)
          and app.model.edge(_src_e0.frm, _src_e0.to) is not None,
          "冒烟测试已固定在固件源码地图上（%d 节点 / %d 边；不受保存的布局影响）"
          % (len(app.model.nodes), len(app.model.edges)))

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
        # ⚠️ 按 **minsize 宽度**判，而不是当前窗口宽：窗口能被拉大，但缩到最小宽度时
        #    溢出的行会把右侧控件挤到屏幕外（这是这个断言的真正目的）。
        _minw = app.minsize()[0] or win_w
        check(widest <= _minw,
              "每行宽度 %d <= 最小窗口宽 %d（不溢出；实际窗口 %d）" % (widest, _minw, win_w))

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

    # --- 选中一条边（选哪条从模型推，别硬编码：地图改过，旧边可能就没了）---
    e = max(app.model.edges, key=lambda x: (app.model.step(x) or 0.0))
    step("select edge %s" % e.label())
    app._on_edge_press(type("Ev", (), {"x": 0, "y": 0})(), e)
    app.update()
    check(app._prop_widgets["step"].get() == e.step,
          "属性面板显示 %s 的 step=%s" % (e.label(), e.step))
    check(app._prop_widgets["func"].get() == e.func,
          "属性面板显示 func=%s" % e.func)

    # --- 双向边要能分开选：偏向哪条选哪条 + 同一处再点一次切换方向 ---
    step("picking one direction of a bidirectional pair")

    class _Ev2:
        def __init__(self, x, y):
            self.x, self.y, self.state = x, y, 0
            self.x_root, self.y_root = x, y

    _bid = next((x for x in app.model.edges if app.model.has_reverse(x)), None)
    check(_bid is not None, "地图里存在双向边可测")
    if _bid is not None:
        _rev = app.model.edge(_bid.to, _bid.frm)
        _a, _b = app.model.node(_bid.frm), app.model.node(_bid.to)
        _x1, _y1 = app.w2s(_a.x, _a.y)
        _x2, _y2 = app.w2s(_b.x, _b.y)
        _mx, _my = (_x1 + _x2) / 2.0, (_y1 + _y2) / 2.0
        _L = math.hypot(_x2 - _x1, _y2 - _y1)
        _ux, _uy = (_x2 - _x1) / _L, (_y2 - _y1) / _L
        _side = {}
        for _sg in (-1, 1):
            _c = app._edges_near(_mx - _uy * 6.0 * _sg, _my + _ux * 6.0 * _sg)
            _side[_sg] = _c[0] if _c else None
        check(all(_side[s] is not None for s in (-1, 1))
              and {_side[-1].tag, _side[1].tag} == {_bid.tag, _rev.tag},
              "双向边两条线两侧各能选到一条（%s / %s）"
              % (_side[-1].label() if _side[-1] else None,
                 _side[1].label() if _side[1] else None))
        app.sel_edge = None
        app._on_edge_press(_Ev2(_mx, _my), _bid)
        _first = app.sel_edge
        time.sleep(0.4)                       # 超过双击阈值才算"再点一次"
        app._on_edge_press(_Ev2(_mx, _my), _bid)
        _second = app.sel_edge
        check(_first is not None and _second is not None and _first.tag != _second.tag,
              "同一处再点一次切换方向（%s → %s）" % (_first.label(), _second.label()))
        check("切换" in app.status_var.get(), "状态栏提示「再点一次切换方向」")

    # --- 平台快速交换：长度不变，function 随平台切换 ---
    step("platform quick-swap (func follows the platform, step unchanged)")
    _snap_sw = app.model.snapshot()
    _n0 = (len(app.model.nodes), len(app.model.edges))
    _plats = [n.name for n in app.model.nodes if n.name[:1] == "P"]
    check(len(_plats) >= 2, "地图里至少 2 个 P 平台（%d 个）" % len(_plats))
    if len(_plats) >= 2:
        _pa, _pb = _plats[0], _plats[-1]
        _in_a = app.model.edges_of(_pa, False)[0]      # 进 A 的那条（带平台动作）
        _in_b = app.model.edges_of(_pb, False)[0]
        _xa, _ya = _in_a.frm, _in_b.frm
        _step_a, _step_b = _in_a.step, _in_b.step
        _role_a = app.model.node_io_roles(_pa)[0]
        _role_b = app.model.node_io_roles(_pb)[0]
        _dry = app.model.swap_platforms(_pa, _pb, dry_run=True)
        check(bool(_dry) and app.model.edge(_xa, _pa) is not None,
              "dry_run 返回 %d 处改动、且不动模型" % len(_dry))
        app.model.swap_platforms(_pa, _pb)
        _ea = app.model.edge(_xa, _pb)                 # 原 X→A ⇒ 现在 X→B
        _eb = app.model.edge(_ya, _pa)                 # 原 Y→B ⇒ 现在 Y→A
        check(_ea is not None and _eb is not None, "两个平台的名字都换过来了")
        check(_ea is not None and _eb is not None
              and _ea.step == _step_a and _eb.step == _step_b,
              "长度(step)沿用原值：%s / %s" % (_ea.step if _ea else None,
                                               _eb.step if _eb else None))
        check(_ea is not None and _eb is not None
              and _ea.func == _role_b and _eb.func == _role_a,
              "func 随平台切换：%s→%s，%s→%s"
              % (_role_a, _ea.func if _ea else None, _role_b, _eb.func if _eb else None))
        check((len(app.model.nodes), len(app.model.edges)) == _n0
              and app.model.edge(_pa, _pb) is None,
              "节点/边数不变（%d/%d），也没造出直连边" % _n0)
        app.model.restore(_snap_sw)
        app.refresh_all()
        check(app.model.edge(_xa, _pa) is not None
              and app.model.edge(_xa, _pa).func == _role_a,
              "restore 能完整撤回交换")

    app.platform_swap_dialog()
    app.update_idletasks()
    _tops = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
    check(len(_tops) == 1, "「平台快速交换」对话框能构建（Toplevel %d 个）" % len(_tops))
    for _w in _tops:
        _w.destroy()
    app.update()

    # --- UI 入口必须**真的可见**：曾把按钮加进 pack 空间已满的 frame，结果整块没被映射（用户找不到）---
    def _widgets_with_text(root, part):
        got = []

        def walk(w):
            for c in w.winfo_children():
                try:
                    t = str(c.cget("text"))
                except Exception:                                # noqa: BLE001
                    t = ""
                if part in t:
                    got.append(c)
                walk(c)
        walk(root)
        return got

    _entry = _widgets_with_text(app, "平台交换")
    check(_entry and all(b.winfo_ismapped() for b in _entry),
          "「平台交换」入口在界面上真的可见（找到 %d 个，mapped=%s）"
          % (len(_entry), [bool(b.winfo_ismapped()) for b in _entry]))

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

    # --- 线索 / 每盏门灯 / 宝物 → 固件分支路线（纯计算入口，不弹窗）---
    step("clue / per-door-light / treasure -> firmware branch")
    M = E.M
    ST_BACK = "第一轮·门区回程（route_return_home，门区禁用）"
    ST_R2 = "第二轮·完整路线（get_newroute）"

    def _sections_text(secs):
        """把 (标题, 行列表) 拼成纯文本——标题也要算进去（过门落在哪写在标题里）。"""
        return "\n".join("%s\n%s" % (title, "\n".join(lines)) for title, lines in secs)

    # door_2 + 宝物=P4：逐字等于 validate/_check_door_perm.py 的 golden
    secs, _cv, err = app._clue_route_sections(
        ST_BACK, None, (5, 7),
        [M.NO_PASS, M.ONE_WAY_PASS, M.NO_PASS, M.NO_PASS], 4, ("N8", True), "full")
    check(err is None and
          "N3 -> N4 -> N5 -> N6 -> P4 -> N6 -> N5 -> N4 -> B3 -> N2 -> P2" in _sections_text(secs),
          "门区回程 door_2/宝物P4 命中 golden（门区禁用 + 放行 N8→N3）")

    # D2/D3/D4 全黑：固件 CarBrake_Stop，不能算出一条路线
    secs, _cv, err = app._clue_route_sections(
        ST_R2, None, (5, 7),
        [M.NO_PASS, M.NO_PASS, M.NO_PASS, M.NO_PASS], 6, ("N3", False), "full")
    check(err is not None and "停车" in err[0], "D2/D3/D4 全黑 → 提示固件会 CarBrake_Stop")

    # 第二轮 宝物=P6：巡游方向必须翻成逆时针 P6→P8→P7→P5
    secs, _cv, err = app._clue_route_sections(
        ST_R2, None, (5, 7),
        [M.CAN_PASS, M.NO_PASS, M.NO_PASS, M.CAN_PASS], 6, ("N3", False), "full")
    txt2 = _sections_text(secs)
    check(err is None and "P6 -> P8 -> P7 -> P5" in txt2,
          "第二轮 宝物=P6 的必经点按逆时针排列")

    # 过门后 stageAB：D2 能过 → 落在 N12；灯全不能过 → 报停车
    secs, _cv, err = app._clue_route_sections(
        "第一轮·过门→平台A/B→宝物回程（stageAB + plan_treasure_return）", None, (5, 7),
        [M.CAN_PASS, M.NO_PASS, M.NO_PASS, M.NO_PASS], 4, ("N3", False), "full")
    _txt = _sections_text(secs)
    check(err is None and "过门落在 N12" in _txt,
          "D2 绿 → 过门落在 N12 并接上宝物回程（err=%s, 段落=%s）"
          % (err, [t[:24] for t, _ in secs]))

    # 对话框本身能否构建（只建窗、不进 mainloop，构建完立刻销毁）
    app.plan_clue_route_dialog()
    app.update_idletasks()
    tops = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
    check(len(tops) == 1, "「线索路线…」对话框能构建（Toplevel %d 个）" % len(tops))
    for w in tops:
        w.destroy()
    app.update()

    # --- 「线索路线…」记住上次的配置（内存 + 随布局持久化）---
    step("clue-route dialog remembers the last configuration")

    def _dlg_combo_values(app_):
        """把当前所有 Toplevel 里的下拉框取值按顺序读出来。"""
        out = []

        def walk(c):
            for ch in c.winfo_children():
                if ch.winfo_class() == "TCombobox":
                    out.append(ch.get())
                walk(ch)
        for w_ in app_.winfo_children():
            if isinstance(w_, tk.Toplevel):
                walk(w_)
        return out

    def _close_toplevels(app_):
        for w_ in [x for x in app_.winfo_children() if isinstance(x, tk.Toplevel)]:
            w_.destroy()
        app_.update()

    _cfg_want = {
        "stage": "第二轮·完整路线（get_newroute）",
        "p1clue": "线索=4：经过 P4",
        "stg": "A=6,B=8：P6 -> P8",
        "doors": ["绿(能过)", "蓝(单相)", "黑(不能过)", "蓝(单相)"],
        "treasure": "6 · P6",
        "back": "door_3：D4 回程绿（起点 N3）",
    }
    app.clue_route_cfg = dict(_cfg_want)
    app.plan_clue_route_dialog()
    app.update_idletasks()
    _vals = _dlg_combo_values(app)
    _close_toplevels(app)
    _expect = ([_cfg_want["stage"], _cfg_want["p1clue"], _cfg_want["stg"]]
               + _cfg_want["doors"] + [_cfg_want["treasure"], _cfg_want["back"]])
    check(_vals == _expect, "对话框按上次配置预填（读到 %d 个下拉）" % len(_vals))

    # 配置脏/过期时要安全回退（不能崩，也不能填出非法值）
    app.clue_route_cfg = {"stage": "不存在的阶段", "doors": ["乱写", 123],
                          "treasure": "??", "back": None, "stg": 999}
    app.plan_clue_route_dialog()
    app.update_idletasks()
    _vals2 = _dlg_combo_values(app)
    _close_toplevels(app)
    _legal_doors = [M.DOOR_STATE_NAME[s] for s in M.DOOR_STATE_ORDER]
    check(len(_vals2) == 9 and _vals2[0].startswith("第一轮·完整路线")
          and all(v in _legal_doors for v in _vals2[3:7]),
          "配置非法时回退默认值（阶段=%r，灯=%s）" % (_vals2[0][:12] if _vals2 else None,
                                                      _vals2[3:7]))

    # 随「保存布局」持久化（沙箱文件，绝不碰真实布局）
    _cfgdir = os.path.join(HERE, "_smoke_cfg_%d" % os.getpid())
    shutil.rmtree(_cfgdir, ignore_errors=True)
    os.makedirs(_cfgdir, exist_ok=True)
    try:
        _cfgpath = os.path.join(_cfgdir, "cfg.json")
        app.clue_route_cfg = dict(_cfg_want)
        check(app.save_layout(show_msg=False, path=_cfgpath) and os.path.isfile(_cfgpath),
              "带 clue_route 的布局能存到沙箱")
        with open(_cfgpath, encoding="utf-8") as fh:
            _blob = json.load(fh)
        check(_blob.get("constraints", {}).get("clue_route") == _cfg_want,
              "constraints.clue_route 已写进布局 JSON")
        app.clue_route_cfg = {}
        app.load_layout_file(_cfgpath, quiet=True)
        check(app.clue_route_cfg == _cfg_want, "载入布局后线索配置恢复")
    finally:
        shutil.rmtree(_cfgdir, ignore_errors=True)

    # --- door() 内部自己的路线（以前完全不显示）---
    ST_FLOW = "第一轮·门区全流程（door() 状态机 + 门里的手写路线）"
    # D2黑 → D3黑 → D4蓝：中间那步是 door() 内部 load_route_at(0, door1route)
    secs, _cv, err = app._clue_route_sections(
        ST_FLOW, None, (5, 7),
        [M.NO_PASS, M.NO_PASS, M.ONE_WAY_PASS, M.NO_PASS], 4, ("N3", False), "full")
    t3 = _sections_text(secs)
    check(err is None and "door1route" in t3 and "过门落在 N8" in t3,
          "door() 里 D3 黑的退回路线（door1route={N3,N8}）被显示出来")

    # D5 黑 + D2 蓝：door() 内部手写 route[0]=N3; route[1]=0xFF
    secs, _cv, err = app._clue_route_sections(
        ST_FLOW, None, (5, 7),
        [M.ONE_WAY_PASS, M.NO_PASS, M.NO_PASS, M.NO_PASS], 4, ("N3", False), "full")
    check("route[0]=N3" in _sections_text(secs),
          "door() 里 D5黑+D2蓝 的手写 route[0]=N3 被显示出来")

    # D5 黑但没有匹配分支：door() 不置 cross_event → 会反复重读该门（隐患要报出来）
    secs, _cv, err = app._clue_route_sections(
        ST_FLOW, None, (5, 7),
        [M.NO_PASS, M.NO_PASS, M.NO_PASS, M.NO_PASS], 4, ("N3", False), "full")
    check("反复重读" in _sections_text(secs),
          "door() 里 D5黑无匹配分支的隐患被提示")

    # 经过 DOOR 边必须告警（旧版 show_route_text 有，重写时曾漏掉）
    _p, _why = app.model.plan_route(["N5", "N8"], "full")
    _lines = app._fmt_planned(["N5", "N8"], _p, _why)
    check(any("是 DOOR 边" in ln for ln in _lines),
          "路线经过 DOOR 边时会告警（door() 会清空 route[]）")

    # 回程门区：D2蓝 + D5绿 ⇒ 固件 get_newroute 的 wp 只放 N10（N3 冗余），规划器必须走 N10→N3
    secs, flat, err = app._clue_route_sections(
        ST_R2, None, (5, 7),
        [M.ONE_WAY_PASS, M.NO_PASS, M.NO_PASS, M.CAN_PASS], 4, ("N3", False), "full")
    _tail = " -> ".join(flat or [])
    check("N10 -> N3" in _tail and "N10 -> N8" not in _tail,
          "D2蓝+D5绿（D3/D4黑）回程走 N10→N3，不绕 N10→N8")
    # 对照：D2蓝 + D3绿 + D4绿 + D5黑 ⇒ 固件 wp 里**明写 N8**（D5 黑、走 D4 回家），
    # 所以路线确实会经 N10→N8 再去 N3 —— 这是对的，不是 bug。
    _doors_x = [M.ONE_WAY_PASS, M.CAN_PASS, M.CAN_PASS, M.NO_PASS]
    _wpx, _ = M.round2_waypoints(_doors_x, 4)
    secs2, flat2, err2 = app._clue_route_sections(
        ST_R2, None, (5, 7), _doors_x, 4, ("N3", False), "full")
    check(_wpx is not None and "N8" in _wpx and "N10 -> N8" in " -> ".join(flat2 or []),
          "D5黑+D4绿 时固件 wp 明写 N8 ⇒ 经 N10→N8 再 N8→N3 是对的")

    # --- 第一轮完整路线：去程 + 回程拼接 + 画布分色 ---
    step("round-1 complete route (outbound/return splice + split colouring)")
    ST_ALL = "第一轮·完整路线（去程+门区+东区+回程 自动拼接，画布分色）"
    secs, flat, err = app._clue_route_sections(
        ST_ALL, 3, (5, 7),
        [M.NO_PASS, M.NO_PASS, M.ONE_WAY_PASS, M.CAN_PASS], 4, ("N3", False), "full")
    check(err is None and len(flat) > 20, "第一轮完整路线能拼出来（%d 跳）" % (len(flat) - 1))
    split = app.route_split
    check(split is not None and 0 < split < len(flat) - 1 and flat[split] == "P7",
          "回程起点 = 第二个平台 P7（下标 %s）" % split)
    check(flat[0] == "P2" and flat[-1] == "P2",
          "完整路线从 P2（家）出发、回到 P2")
    # 每一跳都要有边（否则画出来是假线）
    bad_hops = [(flat[i], flat[i + 1]) for i in range(len(flat) - 1)
                if app.model.edge(flat[i], flat[i + 1]) is None]
    check(not bad_hops, "完整路线每一跳都是真实边（无边 %d 处：%s）"
          % (len(bad_hops), bad_hops[:4]))
    # 回程穿过 N10→N3 的 BACK 门 ⇒ 必须出现 door() 的 BACK 分支重规划段
    check(any("BACK 分支重规划" in t for t, _ in secs),
          "回程穿 BACK 门时出现 door() 的 route_return_home() 重规划段")
    # 画布必须能按 去程/回程 分色画出来（真调一次 redraw，再查画布上确实有两种颜色）
    app.route = flat
    app.route_split = split
    app.redraw()
    app.update()
    cols = set()
    for it in app.canvas.find_all():
        if app.canvas.type(it) == "line":
            try:
                c = app.canvas.itemcget(it, "fill")
            except Exception:                                    # noqa: BLE001
                continue
            if c:
                cols.add(str(c))
    check(E.ROUTE_COLOR in cols and E.ROUTE_COLOR_BACK in cols,
          "画布上同时出现去程/回程两种颜色（%s / %s）"
          % (E.ROUTE_COLOR, E.ROUTE_COLOR_BACK))
    # 普通规划不应该残留 split（否则会错误分色）
    app.waypoints = ["N2", "P1", "N5"]
    app._refresh_wp()
    app.plan_route()
    check(app.route_split is None, "普通「规划路线」会清掉 route_split（不误分色）")

    # --- 右键连线（原来靠左键双击，经常点不中）---
    step("right-click connect (node context menu moved to Shift+right-click)")
    snap_rc = app.model.snapshot()
    app.connect_mode.set(False)
    app.connect_from = None
    check(app.model.edge("P3", "P5") is None, "前置：P3→P5 本来没有边")

    app._on_node_right(_Ev(), "P3")                      # ① 右键 = 选起点
    check(app.connect_from == "P3", "右键节点 = 设定连线起点")
    check(not app.connect_mode.get(),
          "右键连线不会顺手勾上「连线模式」（否则左键行为被改掉）")

    app._on_node_right(_Ev(), "P5")                      # ② 再右键 = 建边
    check(app.connect_from is None and app.model.edge("P3", "P5") is not None,
          "再右键目标节点即成边（P3→P5）")

    app._on_node_right(_Ev(), "C6")                      # ③ 右键自己两次 = 取消
    app._on_node_right(_Ev(), "C6")
    check(app.connect_from is None, "右键同一个节点两次 = 取消起点")

    app._on_node_right(_Ev(), "C6")                      # ④ 左键点目标也能完成
    app._on_node_press(_Ev(), "C8")
    check(app.connect_from is None and app.model.edge("C6", "C8") is not None,
          "右键起点后左键点目标也能建边（C6→C8）")

    calls = []                                           # ⑤ Shift+右键 = 老菜单
    orig_menu = app._on_node_menu
    app._on_node_menu = lambda ev, nm: calls.append(nm)  # 桩：避免真弹菜单挂住测试
    try:
        app._on_node_right(_Ev(state=0x0001), "N5")
    finally:
        app._on_node_menu = orig_menu
    check(calls == ["N5"] and app.connect_from is None,
          "Shift+右键 走节点快捷菜单，且不会误设连线起点")

    app._drag = app._link = None                         # ⑥ 空白左键 = 放弃起点
    app.adjust_bg.set(False)
    app._on_node_right(_Ev(), "P4")
    app._on_bg_press(_Ev())
    check(app.connect_from is None, "空白左键 = 取消待连线的起点")

    app.model.restore(snap_rc)
    app.refresh_all()

    # --- 新建边的角度必须是「边表约定」，不能是图上裸几何角 ---
    step("auto edge angle uses the edge-table convention")
    snap_ang = app.model.snapshot()
    _c9 = app.model.node("C9")
    _p7 = app.model.node("P7")
    app.model.add_node("ZZH", _c9.x + 500.0, _c9.y, "")            # C9 正水平
    app.model.add_node("ZZV", _c9.x, _c9.y - 400.0, "")            # C9 正竖直
    app.model.add_node("ZZV2", _c9.x, _c9.y - 400.0, "")           # C9 正竖直的近邻（备用）
    _ce = None                                                     # 取 C9 的第一条有 angle 的出边做锚定参照
    for _ee in app.model.edges_of("C9", True):
        if app.model.ang(_ee) is not None:
            _ce = _ee
            break
    _ct = app.model.node(_ce.to)
    app.model.add_node("ZZA", _c9.x + (_ct.x - _c9.x) * 1.6,
                       _c9.y + (_ct.y - _c9.y) * 1.6, "")          # 沿 C9→(第一条出边) 方向
    _v, _how = app._auto_edge_angle("C9", "ZZH")
    check(_v in (0, 180),
          "水平新边算出 180°/0°（而不是图上裸几何的 90°）：%g° — %s" % (_v, _how))
    _v2, _ = app._auto_edge_angle("ZZH", "C9")
    check(_v2 in (0, 180) and _v2 != _v, "水平反向边算出反向的 0°/180°：%g°" % _v2)
    _v4, _how4 = app._auto_edge_angle("C9", "ZZA")
    check(_v4 == app.model.ang(_ce) and "沿用共线边" in _how4,
          "与已有边共线时沿用它的角度（C9→%s = %g°）：%g°"
          % (_ce.to, app.model.ang(_ce), _v4))
    _v3b, _how3b = app._auto_edge_angle("C9", "ZZV")          # 竖直方向
    check(_v3b in (0, 90, 180, -90),
          "竖直新边算出干净角度（0/±90/180）：%g° — %s" % (_v3b, _how3b))
    _e = app.create_edge_quick("C9", "ZZH")
    check(_e is not None and _e.angle == "%g" % _v
          and app.model.edge("ZZH", "C9").angle == "%g" % _v2,
          "快捷建边写进边表的就是算出来的那个角度（%s / %s）" % (_e.angle,
                                                                 app.model.edge("ZZH", "C9").angle))
    app.create_edge_quick("C9", "ZZV")                       # 先建出来
    _ezv = app.model.edge("C9", "ZZV")
    _ezv.angle = "999"                                       # 故意写错，看按钮能否算回边表约定
    app.sel_edge = _ezv
    app.calc_angle_geo()
    check(app.model.edge("C9", "ZZV").angle == "%g" % _v3b,
          "「按图上位置算角度」按钮同样走边表约定：%s"
          % app.model.edge("C9", "ZZV").angle)
    app.model.restore(snap_ang)
    app.refresh_all()

    # --- 「写回固件」的拼接不能重复 size_check（曾每写回一次就多一份；纯函数，不碰真实文件）---
    step("firmware write-back splice keeps exactly one size_check")
    _fake_src = ('#include "x.h"\n\n'
                 'const NavEdge NavEdgeTbl[3] = {\n'
                 '    { A, B, NO, 0, 1, 2, NONE },\n'
                 '};\n\n'
                 '/* 编译期检查：占位 */\n'
                 'typedef char NavEdgeTbl_size_check[1];\n\n'
                 '/* Node[]/ConnectionNum[]/Address[] 已移至 nav_planner.c */\n')
    _blk = app.model.export_edge_table(with_header=False)
    _out = app._splice_edge_table(_fake_src, _blk)
    _n_td = _out.count("typedef char NavEdgeTbl_size_check")
    check(_n_td == 1, "写回拼接后 size_check 只有一份（实际 %d 份）" % _n_td)
    check(_out.count("const NavEdge NavEdgeTbl") == 1, "表体只出现一次")
    check(_out.startswith('#include "x.h"') and "已移至 nav_planner.c */" in _out,
          "写回拼接保留了文件头与文件尾")
    check("nav_graph_init() 已废弃" not in _out,
          "导出块自带的尾部（size_check + 尾注）不会被塞进文件 —— 这正是重复的根因")

    # --- 画布上的「图 xx.xcm」必须与缩放无关（曾因用屏幕 px ÷ K 而随缩放变） ---
    step("edge length label is zoom-independent")

    def _edge_label(app_, frm, to):
        """取某条边画在画布上的那个文字 item 的内容。"""
        e_ = app_.model.edge(frm, to)
        if e_ is None:
            return None
        for it_ in app_._canvas_items["edges"].get(e_.tag, []):
            if app_.canvas.type(it_) == "text":
                return app_.canvas.itemcget(it_, "text")
        return None

    _long_e = max(app.model.edges,
                  key=lambda x: (lambda a, b: math.hypot(b.x - a.x, b.y - a.y))(
                      app.model.node(x.frm), app.model.node(x.to)))
    _old_scale, _old_lbl = app.scale, app.label_mode.get()
    app.label_mode.set("无")
    app.show_edge_lengths.set(True)
    app.scale = 0.8
    app.redraw()
    app.update()
    _l1 = _edge_label(app, _long_e.frm, _long_e.to)
    app.scale = 2.4                                # 放大 3 倍
    app.redraw()
    app.update()
    _l2 = _edge_label(app, _long_e.frm, _long_e.to)
    _want_cm = app._world_len_cm(_long_e)
    check(_l1 is not None and _l1 == _l2 and "图 " in _l1,
          "放大 3 倍后「图 xx.xcm」一字不变（%s：缩放前 %r / 放大后 %r）"
          % (_long_e.label(), _l1, _l2))
    check(_want_cm is not None and ("图 %.1fcm" % _want_cm) in (_l1 or ""),
          "标签值 = 图坐标距离 ÷ K = %.1fcm（K=%.4g）" % (_want_cm or -1, app._unit_k()))
    app.show_edge_lengths.set(False)
    app.label_mode.set(_old_lbl)
    app.scale = _old_scale
    app.redraw()
    app.update()

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
