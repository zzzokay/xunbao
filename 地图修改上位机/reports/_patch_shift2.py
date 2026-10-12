# -*- coding: utf-8 -*-
"""Shift 语义改为：按住 Shift = 连线（起点取当前选中节点，点别的点即连线）。"""
P = "map_editor/map_editor.py"
d = open(P, "rb").read()
assert d.count(b"\r\n") == 0 and d[:3] != b"\xef\xbb\xbf", "行尾/BOM 不符合预期"

patches = []

# 1. shift 分支：直接按"连线"处理（起点 = 当前选中节点）
patches.append((
    u'''        shift = bool(ev.state & 0x0001)
        if shift:
            # Shift = 连线（10-07 起的新语义，见 _on_node_double 的说明）。这里同样"拖动优先"：
            #   按住 Shift **拖动**    = 拉一条新边（松手落在目标节点上）
            #   按住 Shift **原地松手** = 定/续连线起点（在 _on_release 里分流，看 armed）
            self._link = {"from": name, "sx": ev.x, "sy": ev.y, "item": None,
                          "press": (ev.x, ev.y), "armed": False}
            return "break"
''',
    u'''        shift = bool(ev.state & 0x0001)
        if shift:
            # 按住 Shift = 「连线」（10-07 用户定的操作）：
            #   ① 先**普通单击**选中起点；② 按住 Shift 点另一个节点 ⇒ 连线；③ 松开 Shift 即回到普通。
            # Shift 不是常驻开关，**不会改 connect_mode**，所以松开就不可能误连。
            self._connect_from_sel(name)
            return "break"
''',
))

# 2. 去掉 _on_motion 里的 _link 分支（Shift+拖出拉边已取消：抖动 5px 就会误判成拉边，不可靠）
patches.append((
    u'''        if self._link:
            d = self._link
            if not d.get("armed"):
                px, py = d.get("press", (ev.x, ev.y))
                if abs(ev.x - px) <= DRAG_START_PX and abs(ev.y - py) <= DRAG_START_PX:
                    return "break"      # 抖动容忍：还没够"拖动" ⇒ 松手按"定起点"处理
                d["armed"] = True
                self.status("从 %s 拉出连线…松手在目标节点上完成" % d["from"])
            x1, y1 = self.w2s(*self._node_xy(d["from"]))
            if d["item"]:
                self.canvas.delete(d["item"])
            d["item"] = self.canvas.create_line(x1, y1, ev.x, ev.y,
                                                fill=EDGE_COLOR_SEL, width=2, dash=(4, 3))
            return "break"
''',
    u'''        # （Shift+拖出拉边已取消：Shift 现在是"按住=连线"的修饰键，见 _on_node_press）
''',
))

# 3. 去掉 _on_release 里的 _link 分支
patches.append((
    u'''        if self._link:
            d = self._link
            if d.get("item"):
                self.canvas.delete(d["item"])
            self._link = None
            if not d.get("armed"):
                # 按住 Shift 没动就松手 ⇒ 这一下是"定/续连线起点"（拖动优先的另一半）
                self._connect_pick(d["from"])
                return "break"
            tgt = self.node_at(ev.x, ev.y)
            if tgt and tgt != d["from"]:
                self.create_edge_quick(d["from"], tgt)
            else:
                self.status("连线取消（没落在别的节点上）")
            self.redraw()
            return "break"
''',
    u'''        # （Shift+拖出拉边的收尾已取消，见 _on_motion 里的说明）
''',
))

# 4. 新增 _connect_from_sel（放在 _connect_pick 之前）
patches.append((
    u'''    def _connect_pick(self, name):
        """连线取点（左键/右键共用）：第一下选起点，第二下成边，再点自己取消。"""
''',
    u'''    def _connect_from_sel(self, name):
        """**按住 Shift 点节点** = 连线：起点取"当前选中的节点"，终点是刚点的 name。

        为什么起点取选中节点（而不是这次点的节点）：用户要的操作是
        "**普通单击**选中一个点 → 按住 Shift 点别的点就把它连上 → 松开 Shift 回到普通"。
        连完把选中挪到终点 ⇒ 一直按着 Shift 可以**一路连着点下去**（链式）。
        起点找不到（没选中、也没有右键留下的待连起点）时只提示，不猜。
        """
        start = self.sel_node or self.connect_from
        if start is None:
            self.status("连线：先**单击**选中起点节点，再按住 Shift 点终点"
                        "（或直接用右键点节点连线）")
            return
        if start == name:
            self.status("连线：起点和终点是同一个节点（%s），没连" % name)
            return
        self.connect_from = None          # 用掉了右键留下的待连起点就清掉，别留残留状态
        self.create_edge_quick(start, name)
        self.select_node(name)            # 终点变新起点 ⇒ 按住 Shift 可继续连

    def _connect_pick(self, name):
        """连线取点（右键 / 「连线模式」共用）：第一下选起点，第二下成边，再点自己取消。"""
''',
))

# 5. 双击节点的提示语更新（Shift 用法变了）
patches.append((
    u'''        self.status("双击不再连线；连线请用 Shift+点起点，或右键点节点（Shift+右键 = 节点菜单）")
''',
    u'''        self.status("双击不再连线；连线请先单击选中起点、再按住 Shift 点终点，或右键点节点")
''',
))

# 6. _on_node_right 文档里那句话也更新
patches.append((
    u'''        且 10-07 起**双击节点的连线入口已彻底封掉**（太容易误触发），右键是仅存的"有意图感"入口。
''',
    u'''        且 10-07 起**双击节点的连线入口已彻底封掉**（太容易误触发）；
        连线入口只剩两个：**按住 Shift 点节点**（起点=当前选中）与**右键点节点**。
''',
))

for i, (o, n) in enumerate(patches, 1):
    ob, nb = o.encode("utf-8"), n.encode("utf-8")
    c = d.count(ob)
    if c != 1:
        raise SystemExit("patch %d 命中 %d 次（要求 1），整体放弃" % (i, c))
    d = d.replace(ob, nb)
    print("patch %d OK" % i)

assert d.count(b"\r\n") == 0
open(P, "wb").write(d)
print("已写盘", len(d), "bytes")
