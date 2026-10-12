# -*- coding: utf-8 -*-
"""左栏「转弯补偿」表加「显示」下拉（像「边显示」），默认不显示全部。字节级替换，全唯一命中才写盘。"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

def load(p):
    return open(p, "rb").read().decode("utf-8")

def save(p, s):
    open(p, "wb").write(s.encode("utf-8"))

MM = "地图修改上位机/map_editor/map_model.py"
ME = "地图修改上位机/map_editor/map_editor.py"
GS = "地图修改上位机/map_editor/_guismoke.py"

# ---------- 1. map_model.py：TURN_LIST_MODES + turn_filter ----------
MM_OLD = '''    if td["calc_chg"]:
        sv, cv = td["calc_chg"]
        out.append("  ~ 开关 TURN_CALC_ENABLE：%d → %d（%s）"
                   % (sv, cv, "启用「能算就算」公式" if cv else "关闭，回到原行为"))
    return out


def turn_table_status(model, rows, table, turn=None):
'''

MM_NEW = '''    if td["calc_chg"]:
        sv, cv = td["calc_chg"]
        out.append("  ~ 开关 TURN_CALC_ENABLE：%d → %d（%s）"
                   % (sv, cv, "启用「能算就算」公式" if cv else "关闭，回到原行为"))
    return out


# 左栏「转弯补偿」表的显示档（像「边显示」那样只显示一类；默认第一档 = 不显示全部）
TURN_LIST_MODES = ("只看要补偿的", "只看实测", "只看吃默认", "只看停车转", "只看陀螺转", "全部")
_TURN_DEFAULT_SRCS = ("Tier3 默认 19", "默认 0", "角度求不出（宏没定义）")


def turn_filter(rows, mode):
    """按显示档过滤 `turn_coverage()` 的行（纯函数，界面与自检共用）。

    ⚠️ 「只看吃默认」的口径 = 对话框第③页那个勾选框：默认 19 / 默认 0 / 角度求不出。
    """
    rows = rows or []
    if mode == "只看要补偿的":
        return [r for r in rows if r["branch"] != "straight"]
    if mode == "只看实测":
        return [r for r in rows if r["source"] in ("表1 实测", "表2 实测")]
    if mode == "只看吃默认":
        return [r for r in rows if r["source"] in _TURN_DEFAULT_SRCS]
    if mode == "只看停车转":
        return [r for r in rows if r["branch"] == "stop"]
    if mode == "只看陀螺转":
        return [r for r in rows if r["branch"] == "gyro"]
    return list(rows)                      # 「全部」或未知档 ⇒ 不过滤


def turn_table_status(model, rows, table, turn=None):
'''

# ---------- 2. map_editor.py：_build_left 加「显示」下拉 ----------
ME1_OLD = '''        ttk.Label(top, text="转弯补偿（点一行 → 画布高亮；双击打开补偿编辑器）").pack(
            anchor="w", padx=4, pady=(4, 0))
        # 左栏上半原为「节点表」，按用户要求整块换成「转弯补偿」表。
        # 数据源 = model.turn_coverage()，与「⟲ 转弯补偿…」对话框第③页签同源。
'''
ME1_NEW = '''        # 左栏上半原为「节点表」，按用户要求整块换成「转弯补偿」表。
        # 数据源 = model.turn_coverage()，与「⟲ 转弯补偿…」对话框第③页签同源。
        # 「显示」下拉 = 只看其中一类（默认**不显示全部** ~300 行），参照「边显示」。
        trow = ttk.Frame(top)
        trow.pack(fill="x", padx=4, pady=(4, 0))
        ttk.Label(trow, text="转弯补偿").pack(side="left")
        ttk.Label(trow, text="显示:").pack(side="left", padx=(8, 0))
        self.turn_view = tk.StringVar(value=M.TURN_LIST_MODES[0])
        tvc = ttk.Combobox(trow, textvariable=self.turn_view, width=14,
                           state="readonly", values=list(M.TURN_LIST_MODES))
        tvc.pack(side="left", padx=(2, 0))
        tvc.bind("<<ComboboxSelected>>", lambda _e: self._fill_turn_list())
        self.lbl_turn_hint = ttk.Label(top, foreground="#666666", text="")
        self.lbl_turn_hint.pack(anchor="w", padx=4)
'''

# ---------- 3. map_editor.py：_fill_turn_list 按档过滤 + 提示行 ----------
ME2_OLD = '''    def _fill_turn_list(self, cov=None):
        """填左栏上半「转弯补偿」表：地图里每个 (入边, 出边) 转弯 + 当前生效补偿。

        数据 = `model.turn_coverage()`（与「⟲ 转弯补偿…」对话框第③页签同源）。
        点一行 → 画布高亮该弯；双击 → 打开补偿编辑器。
        """
        t = self.tree_turn
        t.delete(*t.get_children())
        cov = cov if cov is not None else self.model.turn_coverage()
        self._turn_cov = cov
        rows = cov["rows"]
        for i, r in enumerate(rows):
'''
ME2_NEW = '''    def _fill_turn_list(self, cov=None):
        """填左栏上半「转弯补偿」表：地图里的转弯 + 当前生效补偿（**按显示档过滤**）。

        数据 = `model.turn_coverage()`（与「⟲ 转弯补偿…」对话框第③页签同源），
        再用 `M.turn_filter(rows, self.turn_view)` 挑出当前档（默认不显示全部 ~300 行）。
        点一行 → 画布高亮该弯；双击 → 打开补偿编辑器。
        """
        t = self.tree_turn
        t.delete(*t.get_children())
        cov = cov if cov is not None else self.model.turn_coverage()
        self._turn_cov = cov
        rows = M.turn_filter(cov["rows"], self.turn_view.get())
        if getattr(self, "lbl_turn_hint", None) is not None:
            self.lbl_turn_hint.configure(
                text="%d 行（共 %d 个转弯组合）· 点一行 = 画布高亮 / 双击 = 打开补偿编辑器"
                     % (len(rows), cov["stats"]["total"]))
        for i, r in enumerate(rows):
'''

# ---------- 4. 持久化：constraints.turn_view ----------
ME3_OLD = '''            "edge_view": self.edge_view.get(),      # 边列表展示模式
            "label_mode": self.label_mode.get(),
'''
ME3_NEW = '''            "edge_view": self.edge_view.get(),      # 边列表展示模式
            "turn_view": self.turn_view.get(),      # 左栏「转弯补偿」表显示档
            "label_mode": self.label_mode.get(),
'''

ME4_OLD = '''            if con.get("edge_view") in ("合并双向", "逐条", "只看双向"):
                self.edge_view.set(con["edge_view"])
'''
ME4_NEW = '''            if con.get("edge_view") in ("合并双向", "逐条", "只看双向"):
                self.edge_view.set(con["edge_view"])
            if con.get("turn_view") in M.TURN_LIST_MODES:
                self.turn_view.set(con["turn_view"])
'''

# ---------- 5. _guismoke.py：树断言随「显示档」更新 ----------
GS1_OLD = '''    # --- 树 ---
    _cov_n = len(app.model.turn_coverage()["rows"])
    check(len(app.tree_turn.get_children()) == _cov_n,
          "左栏「转弯补偿」表 %d 行（= 地图转弯组合数 %d）"
          % (len(app.tree_turn.get_children()), _cov_n))
    _kids0 = app.tree_turn.get_children()
    app.tree_turn.selection_set(_kids0[0])
    app._on_tree_turn_select(None)
    check(app.turn_focus is not None,
          "点「转弯补偿」一行 → 设 turn_focus 供画布高亮")
    app.turn_focus = None
    app.redraw()
'''
GS1_NEW = '''    # --- 树 ---
    _cov = app.model.turn_coverage()
    _all_n = len(_cov["rows"])
    app.turn_view.set("全部")
    app._fill_turn_list()
    check(len(app.tree_turn.get_children()) == _all_n,
          "左栏「转弯补偿」表（显示=全部）%d 行 = 地图转弯组合数 %d"
          % (len(app.tree_turn.get_children()), _all_n))
    app.turn_view.set(E.M.TURN_LIST_MODES[0])
    app._fill_turn_list()
    _exp = len(E.M.turn_filter(_cov["rows"], E.M.TURN_LIST_MODES[0]))
    check(len(app.tree_turn.get_children()) == _exp and 0 < _exp < _all_n,
          "默认档「%s」过滤掉直行：%d 行 < 全部 %d"
          % (app.turn_view.get(), len(app.tree_turn.get_children()), _all_n))
    app.turn_view.set("只看实测")
    app._fill_turn_list()
    _exp2 = len(E.M.turn_filter(_cov["rows"], "只看实测"))
    check(len(app.tree_turn.get_children()) == _exp2,
          "「只看实测」= %d 行（表1/表2 命中）" % _exp2)
    app.turn_view.set(E.M.TURN_LIST_MODES[0])
    app._fill_turn_list()
    _kids0 = app.tree_turn.get_children()
    app.tree_turn.selection_set(_kids0[0])
    app._on_tree_turn_select(None)
    check(app.turn_focus is not None,
          "点「转弯补偿」一行 → 设 turn_focus 供画布高亮（过滤后仍对得上）")
    app.turn_focus = None
    app.redraw()
'''

GS2_OLD = '''    check(len(app.tree_turn.get_children()) == len(app.model.turn_coverage()["rows"]),
          "刷新后左栏「转弯补偿」表同步")
'''
GS2_NEW = '''    _covx = app.model.turn_coverage()
    check(len(app.tree_turn.get_children())
          == len(E.M.turn_filter(_covx["rows"], app.turn_view.get())),
          "刷新后左栏「转弯补偿」表与当前显示档一致")
'''

edits = [(MM, MM_OLD, MM_NEW), (ME, ME1_OLD, ME1_NEW), (ME, ME2_OLD, ME2_NEW),
         (ME, ME3_OLD, ME3_NEW), (ME, ME4_OLD, ME4_NEW),
         (GS, GS1_OLD, GS1_NEW), (GS, GS2_OLD, GS2_NEW)]

plan = []
for p, old, new in edits:
    n = load(p).count(old)
    plan.append((p, old, new, n))
    print("[check] %-16s count=%d %s | %s" % (p.split("/")[-1], n,
          "OK" if n == 1 else "!!", old.strip().splitlines()[0][:44]))
if any(x[3] != 1 for x in plan):
    print("\n有串未唯一命中，未写盘。"); sys.exit(1)

buf = {}
for p, old, new, n in plan:
    buf[p] = buf.get(p, load(p)).replace(old, new, 1)
for p, s in buf.items():
    save(p, s); print("[write]", p)
print("DONE")
