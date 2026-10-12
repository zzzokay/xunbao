# -*- coding: utf-8 -*-
"""把左栏上半「节点表」整块换成「转弯补偿」表（map_editor.py），并同步 _guismoke.py 断言。
字节级替换，全部唯一命中才写盘。"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

def load(p):
    return open(p, "rb").read().decode("utf-8")

def save(p, s):
    open(p, "wb").write(s.encode("utf-8"))

ME = "地图修改上位机/map_editor/map_editor.py"
GS = "地图修改上位机/map_editor/_guismoke.py"

# ============ 1. _build_left：节点表 -> 转弯补偿表 ============
A_OLD = '''        ttk.Label(top, text="节点（双击定位 / 右键菜单）").pack(
            anchor="w", padx=4, pady=(4, 0))
        self.tree_nodes = ttk.Treeview(top, columns=("idx", "kind", "deg"),
                                       show="tree headings", height=10)
        self.tree_nodes.heading("#0", text="节点")
        self.tree_nodes.heading("idx", text="#")
        self.tree_nodes.heading("kind", text="类型")
        self.tree_nodes.heading("deg", text="出/入")
        self.tree_nodes.column("#0", width=104)
        self.tree_nodes.column("idx", width=30, anchor="e")
        self.tree_nodes.column("kind", width=48)
        self.tree_nodes.column("deg", width=44, anchor="center")
        self.tree_nodes.pack(fill="both", expand=True, padx=4)
        self.tree_nodes.bind("<<TreeviewSelect>>", self._on_tree_node_select)
'''
A_NEW = '''        ttk.Label(top, text="转弯补偿（点一行 → 画布高亮；双击打开补偿编辑器）").pack(
            anchor="w", padx=4, pady=(4, 0))
        # 左栏上半原为「节点表」，按用户要求整块换成「转弯补偿」表。
        # 数据源 = model.turn_coverage()，与「⟲ 转弯补偿…」对话框第③页签同源。
        self.tree_turn = ttk.Treeview(top, columns=("ang", "br", "val", "src"),
                                      show="tree headings", height=10)
        self.tree_turn.heading("#0", text="转弯（上一步→当前→下一步）")
        self.tree_turn.heading("ang", text="角")
        self.tree_turn.heading("br", text="分支")
        self.tree_turn.heading("val", text="值cm")
        self.tree_turn.heading("src", text="来源")
        self.tree_turn.column("#0", width=132)
        self.tree_turn.column("ang", width=46, anchor="e", stretch=False)
        self.tree_turn.column("br", width=34, anchor="center", stretch=False)
        self.tree_turn.column("val", width=46, anchor="e", stretch=False)
        self.tree_turn.column("src", width=58, anchor="w", stretch=False)
        self.tree_turn.pack(fill="both", expand=True, padx=4)
        self.tree_turn.bind("<<TreeviewSelect>>", self._on_tree_turn_select)
        self.tree_turn.bind("<Double-1>", lambda _e: self.turn_comp_dialog())
        # 行着色：实测=绿 / 公式=蓝 / 直行=灰 / 默认或求不出=橙
        self.tree_turn.tag_configure("meas", foreground="#2e7d32")
        self.tree_turn.tag_configure("calc", foreground="#1565c0")
        self.tree_turn.tag_configure("straight", foreground="#9e9e9e")
        self.tree_turn.tag_configure("dflt", foreground="#e65100")
'''

# ============ 2. _tree_select：节点树没了（node -> 直接返回） ============
B_OLD = '''        tree = self.tree_nodes if kind == "node" else self.tree_edges
        if kind == "node":
            iid = "n:" + str(key)
        else:
            # 边：合并模式下两个方向共用一条 iid 为 "b:A<->B" 的行
            frm, to = str(key).split("->")
            both = (self.edge_view.get() == "合并双向"
                    and self.model.edge(frm, to) and self.model.edge(to, frm))
            iid = ("b:%s<->%s" % (frm, to)) if both else ("e:%s->%s" % (frm, to))
'''
B_NEW = '''        if kind == "node":
            return          # 左栏节点表已改成「转弯补偿」表 ⇒ 没有节点树可同步
        tree = self.tree_edges
        # 边：合并模式下两个方向共用一条 iid 为 "b:A<->B" 的行
        frm, to = str(key).split("->")
        both = (self.edge_view.get() == "合并双向"
                and self.model.edge(frm, to) and self.model.edge(to, frm))
        iid = ("b:%s<->%s" % (frm, to)) if both else ("e:%s->%s" % (frm, to))
'''

# ============ 3. _on_tree_node_select -> _on_tree_turn_select ============
C_OLD = '''    def _on_tree_node_select(self, _ev):
        if self._suspend_ui or getattr(self, "_syncing_tree", False):
            return
        sel = self.tree_nodes.selection()
        if not sel:
            return
        name = sel[0][2:]
        if name == self.sel_node:
            return
        # 只更新状态 + 重绘，不再回写树选中（避免递归）
        self.sel_node = name
        self.sel_edge = None
        self.refresh_props()
        self.redraw()
'''
C_NEW = '''    _TURN_SRC_SHORT = {"表1 实测": "表1", "Tier2 公式": "公式", "Tier3 默认 19": "默认19",
                       "表2 实测": "表2", "默认 0": "默认0", "直行（不走补偿）": "直行",
                       "角度求不出（宏没定义）": "角度?"}
    _TURN_BR_SHORT = {"straight": "直", "stop": "停", "gyro": "陀", "unknown": "?"}

    def _on_tree_turn_select(self, _ev):
        """点左栏「转弯补偿」一行 → 把那个弯（上一步→当前→下一步）在画布上高亮。"""
        if self._suspend_ui or getattr(self, "_syncing_tree", False):
            return
        sel = self.tree_turn.selection()
        rows = getattr(self, "_turn_rows", None)
        if not sel or not rows:
            return
        try:
            r = rows[int(sel[0][2:])]
        except (ValueError, IndexError):
            return
        self.turn_focus = (r["last"], r["now"], r["next"])
        self.redraw()
        self.status("转弯补偿：%s→%s→%s　转弯 %s　生效 %s cm（%s）"
                    % (r["last"], r["now"], r["next"],
                       "-" if r["delta"] is None else "%+.1f°" % r["delta"],
                       "-" if r["value"] is None else "%g" % r["value"], r["source"]))
'''

# ============ 4. refresh_trees：填节点行 -> 填转弯补偿表 ============
D_OLD = '''            self.tree_nodes.delete(*self.tree_nodes.get_children())
            for i, n in enumerate(self.model.nodes):
                deg = "%d/%d" % (len(self.model.edges_of(n.name, True)),
                                 len(self.model.edges_of(n.name, False)))
                self.tree_nodes.insert("", "end", iid="n:" + n.name,
                                       text=n.name, values=(i, KIND_ZH.get(n.kind, "?"), deg))
'''
D_NEW = '''            self._fill_turn_list()
'''

# ============ 5. 新增 _fill_turn_list（插在 _fill_edges_merged 前） ============
E_OLD = '''    def _fill_edges_merged(self):
'''
E_NEW = '''    def _fill_turn_list(self, cov=None):
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
            src = r["source"]
            if src in ("表1 实测", "表2 实测"):
                tag = "meas"
            elif src == "Tier2 公式":
                tag = "calc"
            elif src.startswith("直行"):
                tag = "straight"
            else:
                tag = "dflt"
            t.insert("", "end", iid="t:%d" % i, tags=(tag,),
                     text="%s→%s→%s" % (r["last"], r["now"], r["next"]),
                     values=("-" if r["delta"] is None else "%+.0f°" % r["delta"],
                             self._TURN_BR_SHORT.get(r["branch"], "?"),
                             "—" if r["value"] is None else "%g" % r["value"],
                             self._TURN_SRC_SHORT.get(src, src)))
        self._turn_rows = rows

    def _fill_edges_merged(self):
'''

# ============ 6. 对话框 refresh_head 里同步刷新左栏补偿表 ============
F_OLD = '''        def refresh_head():
            cov = self.model.turn_coverage()
            self._turn_cov = cov
            s = cov["stats"]
'''
F_NEW = '''        def refresh_head():
            cov = self.model.turn_coverage()
            self._turn_cov = cov
            self._fill_turn_list(cov)       # 左栏「转弯补偿」表跟着刷新（同数据源）
            s = cov["stats"]
'''

# ============ 7. _guismoke.py 断言同步 ============
G_OLD = '''    check(len(app.tree_nodes.get_children()) == len(app.model.nodes),
          "节点树 %d 行" % len(app.tree_nodes.get_children()))
'''
G_NEW = '''    _cov_n = len(app.model.turn_coverage()["rows"])
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

H_OLD = '''    check(len(app.tree_nodes.get_children()) == len(app.model.nodes),
          "刷新后节点树同步")
'''
H_NEW = '''    check(len(app.tree_turn.get_children()) == len(app.model.turn_coverage()["rows"]),
          "刷新后左栏「转弯补偿」表同步")
'''

edits = [(ME, A_OLD, A_NEW), (ME, B_OLD, B_NEW), (ME, C_OLD, C_NEW), (ME, D_OLD, D_NEW),
         (ME, E_OLD, E_NEW), (ME, F_OLD, F_NEW), (GS, G_OLD, G_NEW), (GS, H_OLD, H_NEW)]

plan = []
for p, old, new in edits:
    n = load(p).count(old)
    plan.append((p, old, new, n))
    print("[check] %-40s count=%d %s | %s" % (p.split("/")[-1], n,
          "OK" if n == 1 else "!!", old.strip().splitlines()[0][:48]))

if any(x[3] != 1 for x in plan):
    print("\n有串未唯一命中，未写盘。")
    sys.exit(1)

buf = {}
for p, old, new, n in plan:
    buf[p] = buf.get(p, load(p)).replace(old, new, 1)
for p, s in buf.items():
    save(p, s)
    print("[write] %s" % p)
print("\nDONE")
