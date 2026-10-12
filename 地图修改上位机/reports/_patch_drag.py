# -*- coding: utf-8 -*-
"""给 map_editor.py 打补丁：连线模式下拖动优先 + 残留指针状态自愈。
字节级替换（LF 保持不变），任一处 old 不唯一/不命中就整体不写盘。"""
import sys

P = "map_editor/map_editor.py"
d = open(P, "rb").read()
orig = d
if d[:3] == b"\xef\xbb\xbf":
    raise SystemExit("意外：出现 BOM")
crlf = d.count(b"\r\n")
if crlf:
    raise SystemExit("意外：本以为纯 LF，实测 CRLF=%d" % crlf)

patches = []

# ---------- 1. 常量 ----------
patches.append((
    u'BATCH_COLOR = "#8e44ad"          # 框选批量选中（节点/边通用）：紫，不撞单选橙、路线蓝/青、告警红\n',
    u'BATCH_COLOR = "#8e44ad"          # 框选批量选中（节点/边通用）：紫，不撞单选橙、路线蓝/青、告警红\n'
    u'DRAG_START_PX = 4                # 按下后位移超过该屏幕像素才算"拖动"，否则算点击（连线模式下=选起点）\n',
))

# ---------- 2. _on_node_press：连线模式不再抢走点击 + 自愈 ----------
old2 = u'''    def _on_node_press(self, ev, name):
        # 待连线状态（右键起点 / 连线模式起点）：左键点目标节点也能把边建出来
        if self.connect_from is not None or self.connect_mode.get():
            self._connect_pick(name)
            return "break"
        shift = bool(ev.state & 0x0001)
        if shift:
            self._link = {"from": name, "sx": ev.x, "sy": ev.y, "item": None}
            self.status("从 %s 拉出连线…松手在目标节点上完成" % name)
            return "break"
        if name in self.selected_nodes and len(self.selected_nodes) > 1:
            sx, sy = self.s2w(ev.x, ev.y)
            self._drag = {"group": tuple(self.selected_nodes),
                          "start": (sx, sy), "origin": {
                              nm: self._node_xy(nm) for nm in self.selected_nodes},
                          "moved": False}
            self._snap_before = self.model.snapshot()
            return "break"
        self.select_node(name)
        n = self.model.node(name)
        self._drag = {"name": name, "dx": n.x - self.s2w(ev.x, ev.y)[0],
                      "dy": n.y - self.s2w(ev.x, ev.y)[1], "moved": False}
        self._snap_before = self.model.snapshot()
        return "break"
'''
new2 = u'''    def _clear_stale_ptr_state(self):
        """新的一次按下 ⇒ 上一轮交互的残留状态一定过期，清掉并返回是否清过。

        为什么需要：松开鼠标时若指针不在画布上（拖到左右面板/窗外松手，或拖动中弹了
        对话框），画布收不到 <ButtonRelease-1>，`_drag`/`_link`/`_marquee`/`_bg_drag`
        就会残留；而 `_on_bg_press` 原来"见残留就 return break"、空白点击又清不掉
        ⇒ **Ctrl 框选会在本次运行里永久失效**，且不报任何错（踩过）。
        这几个状态都只在"按住左键期间"有效，能再收到一次 ButtonPress-1 就说明已过期。
        """
        stale = bool(self._drag or self._link
                     or getattr(self, "_marquee", None)
                     or getattr(self, "_bg_drag", None))
        if stale:
            self._drag = None
            self._link = None
            self._marquee = None
            self._bg_drag = None
            self.redraw()        # 抹掉可能还画着的橡皮筋框 / 连线虚线
        return stale

    def _on_node_press(self, ev, name):
        self._clear_stale_ptr_state()
        # 「连线模式」/ 待连线起点：**不立刻把这次点击拿走**，先按拖动处理；
        # 只有"按住后没移动就松手"才算"选连线起点"（见 _on_release）。
        # 踩过：连线模式一旦被打开（双击节点 / 按 A 键 / 勾工具栏复选框都会打开），
        # 点节点就全被 _connect_pick 吃掉 ⇒ 单拖、群拖一起失效，看着像"拖动坏了"。
        pending_connect = (self.connect_from is not None or self.connect_mode.get())
        shift = bool(ev.state & 0x0001)
        if shift:
            self._link = {"from": name, "sx": ev.x, "sy": ev.y, "item": None}
            self.status("从 %s 拉出连线…松手在目标节点上完成" % name)
            return "break"
        if name in self.selected_nodes and len(self.selected_nodes) > 1:
            sx, sy = self.s2w(ev.x, ev.y)
            self._drag = {"group": tuple(self.selected_nodes), "name": name,
                          "press": (ev.x, ev.y), "connect": pending_connect,
                          "start": (sx, sy), "origin": {
                              nm: self._node_xy(nm) for nm in self.selected_nodes},
                          "moved": False}
            self._snap_before = self.model.snapshot()
            return "break"
        self.select_node(name)
        n = self.model.node(name)
        self._drag = {"name": name, "press": (ev.x, ev.y), "connect": pending_connect,
                      "dx": n.x - self.s2w(ev.x, ev.y)[0],
                      "dy": n.y - self.s2w(ev.x, ev.y)[1], "moved": False}
        self._snap_before = self.model.snapshot()
        return "break"
'''
patches.append((old2, new2))

# ---------- 3. _on_motion：抖动容忍（没够阈值不算拖动） ----------
patches.append((
    u'''        if self._drag:
            d = self._drag
            if d.get("group"):
''',
    u'''        if self._drag:
            d = self._drag
            if not d["moved"]:
                px, py = d.get("press", (ev.x, ev.y))
                if abs(ev.x - px) <= DRAG_START_PX and abs(ev.y - py) <= DRAG_START_PX:
                    return "break"      # 抖动容忍：还没够"拖动"，松手仍按点击处理
            if d.get("group"):
''',
))

# ---------- 4. _on_release：没移动 + 连线待命 ⇒ 这才算选连线起点 ----------
patches.append((
    u'''        if self._drag:
            moved = self._drag["moved"]
            self._drag = None
            if moved:
                self._push_undo(self._snap_before)
            self.refresh_trees()
            return "break"
''',
    u'''        if self._drag:
            d = self._drag
            moved = d["moved"]
            self._drag = None
            if not moved and d.get("connect"):
                # 拖动优先的另一半：按住没动就松手 ⇒ 这一下才是"选连线起点"
                self._connect_pick(d["name"])
                return "break"
            if moved:
                self._push_undo(self._snap_before)
            self.refresh_trees()
            return "break"
''',
))

# ---------- 5. _on_bg_press：不再因残留状态直接 return ----------
patches.append((
    u'''    def _on_bg_press(self, ev):
        if self._link or self._drag:
            return "break"
''',
    u'''    def _on_bg_press(self, ev):
        # 能收到一次新的按下 ⇒ 上一轮交互的残留状态必定过期（松开事件丢了）。
        # 清掉，别让它把 Ctrl 框选永久卡死（详见 _clear_stale_ptr_state）。
        self._clear_stale_ptr_state()
''',
))

for i, (o, n) in enumerate(patches, 1):
    ob, nb = o.encode("utf-8"), n.encode("utf-8")
    c = d.count(ob)
    if c != 1:
        raise SystemExit("patch %d 命中 %d 次（要求恰好 1 次），整体放弃，未写盘" % (i, c))
    d = d.replace(ob, nb)
    print("patch %d OK" % i)

if d == orig:
    raise SystemExit("没有任何变化")
if d.count(b"\r\n") != 0:
    raise SystemExit("写盘前行尾检查失败")
open(P, "wb").write(d)
print("已写盘，%d -> %d bytes" % (len(orig), len(d)))
