# -*- coding: utf-8 -*-
"""Shift 语义改造：Shift = 连线（Shift+点=定/续起点，Shift+拖=拉边），双击节点不再连线。"""
P = "map_editor/map_editor.py"
d = open(P, "rb").read()
assert d.count(b"\r\n") == 0 and d[:3] != b"\xef\xbb\xbf", "行尾/BOM 不符合预期"

patches = []

# 1. _on_node_press 注释：双击不再是入口
patches.append((
    u'''        # 踩过：连线模式一旦被打开（双击节点 / 按 A 键 / 勾工具栏复选框都会打开），
        # 点节点就全被 _connect_pick 吃掉 ⇒ 单拖、群拖一起失效，看着像"拖动坏了"。
''',
    u'''        # 踩过：连线模式一旦被打开（按 A 键 / 勾工具栏复选框会开；10-07 前双击节点也会开），
        # 点节点就全被 _connect_pick 吃掉 ⇒ 单拖、群拖一起失效，看着像"拖动坏了"。
''',
))

# 2. shift 分支：改成"拖动优先"（Shift+拖=拉边，Shift+原地松手=定起点）
patches.append((
    u'''        shift = bool(ev.state & 0x0001)
        if shift:
            self._link = {"from": name, "sx": ev.x, "sy": ev.y, "item": None}
            self.status("从 %s 拉出连线…松手在目标节点上完成" % name)
            return "break"
''',
    u'''        shift = bool(ev.state & 0x0001)
        if shift:
            # Shift = 连线（10-07 起的新语义，见 _on_node_double 的说明）。这里同样"拖动优先"：
            #   按住 Shift **拖动**    = 拉一条新边（松手落在目标节点上）
            #   按住 Shift **原地松手** = 定/续连线起点（在 _on_release 里分流，看 armed）
            self._link = {"from": name, "sx": ev.x, "sy": ev.y, "item": None,
                          "press": (ev.x, ev.y), "armed": False}
            return "break"
''',
))

# 3. _on_motion 的 _link 分支：加抖动容忍，够阈值才进入"拉边"
patches.append((
    u'''        if self._link:
            d = self._link
            x1, y1 = self.w2s(*self._node_xy(d["from"]))
''',
    u'''        if self._link:
            d = self._link
            if not d.get("armed"):
                px, py = d.get("press", (ev.x, ev.y))
                if abs(ev.x - px) <= DRAG_START_PX and abs(ev.y - py) <= DRAG_START_PX:
                    return "break"      # 抖动容忍：还没够"拖动" ⇒ 松手按"定起点"处理
                d["armed"] = True
                self.status("从 %s 拉出连线…松手在目标节点上完成" % d["from"])
            x1, y1 = self.w2s(*self._node_xy(d["from"]))
''',
))

# 4. _on_release 的 _link 分支：没够阈值就当"定/续连线起点"
patches.append((
    u'''        if self._link:
            d = self._link
            if d.get("item"):
                self.canvas.delete(d["item"])
            self._link = None
            tgt = self.node_at(ev.x, ev.y)
''',
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
''',
))

# 5. 双击节点：不再连线
patches.append((
    u'''    def _on_node_double(self, ev, name):
        """双击节点 = 打开"编辑边"不方便，改为：以它为起点快速连线。"""
        self.start_connect_from(name)
        return "break"
''',
    u'''    def _on_node_double(self, ev, name):
        """双击节点：**不再连线**（只提示，不动任何状态）。

        10-07 之前这里是"以它为起点快速连线"，而且会顺手把「连线模式」置真 ⇒
        之后**普通点几下不同节点就把边连出来了**，用户报"连线太容易触发"的头号原因。
        现在连线只保留有明确意图的入口：**Shift+点起点** 或 **右键点节点**。
        """
        self.status("双击不再连线；连线请用 Shift+点起点，或右键点节点（Shift+右键 = 节点菜单）")
        return "break"
''',
))

# 6. _on_node_right 文档：双击入口已封
patches.append((
    u'''        原因：原来"左键双击节点开始连线"经常点不中（一歪就变成选中/拖动/框选），
        右键单击更稳。菜单里的功能（重命名/删除/补反向边/设为必经点…）一个没少，只是挪到 Shift+右键。
''',
    u'''        原因：原来"左键双击节点开始连线"经常点不中（一歪就变成选中/拖动/框选），右键单击更稳；
        且 10-07 起**双击节点的连线入口已彻底封掉**（太容易误触发），右键是仅存的"有意图感"入口。
        菜单里的功能（重命名/删除/补反向边/设为必经点…）一个没少，只是挪到 Shift+右键。
''',
))

# 7. start_connect_from 文档：双击已不再走这里
patches.append((
    u'''        """进入"点两下连线"，并把起点设为 name。（右键节点 / 双击节点 / 按 A 都走这里）"""''',
    u'''        """进入"点两下连线"，并把起点设为 name。（按 A / 节点菜单「连出新边」走这里；双击节点已不再走）"""''',
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
