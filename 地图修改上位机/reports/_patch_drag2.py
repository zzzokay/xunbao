# -*- coding: utf-8 -*-
"""修正补丁：Tk 会把同一次 ButtonPress-1 也送给画布 widget 绑定一次，
必须在 _on_bg_press 开头把它认出来原样退回，否则会清掉刚装好的 _drag。"""
P = "map_editor/map_editor.py"
d = open(P, "rb").read()
assert d.count(b"\r\n") == 0 and d[:3] != b"\xef\xbb\xbf", "行尾/BOM 不符合预期"

patches = []

# A. _on_node_press 开头记下这次按下的身份
patches.append((
    u'''    def _on_node_press(self, ev, name):
        self._clear_stale_ptr_state()
''',
    u'''    def _on_node_press(self, ev, name):
        self._ptr_press = self._ev_token(ev)      # 这次按下的身份，见 _on_bg_press
        self._clear_stale_ptr_state()
''',
))

# B. 新增 _ev_token（放在 _clear_stale_ptr_state 之前）
patches.append((
    u'''    def _clear_stale_ptr_state(self):
        """新的一次按下 ⇒ 上一轮交互的残留状态一定过期，清掉并返回是否清过。
''',
    u'''    @staticmethod
    def _ev_token(ev):
        """同一次按下的身份标识：item 绑定与 widget 绑定会拿到同一个 serial。

        用来认出"Tk 把同一次 <ButtonPress-1> 又送给画布 widget 绑定一次"的重复调用。
        测试里的假事件没有 serial ⇒ 返回 None ⇒ 永不触发重复判定。
        """
        s = getattr(ev, "serial", None)
        if s is None:
            return None
        return (getattr(ev, "time", None), s)

    def _clear_stale_ptr_state(self):
        """新的一次按下 ⇒ 上一轮交互的残留状态一定过期，清掉并返回是否清过。
''',
))

# C. _on_bg_press 开头：先认"同一次按下的重复调用"
patches.append((
    u'''    def _on_bg_press(self, ev):
        # 能收到一次新的按下 ⇒ 上一轮交互的残留状态必定过期（松开事件丢了）。
        # 清掉，别让它把 Ctrl 框选永久卡死（详见 _clear_stale_ptr_state）。
        self._clear_stale_ptr_state()
''',
    u'''    def _on_bg_press(self, ev):
        # ⚠️ 本机 Tk 实测：节点 item 绑定即使返回 "break"，画布的 widget 绑定**仍会被调一次**
        #    （原来那句 `if self._link or self._drag: return "break"` 正是靠它兜住刚装好的
        #    拖动状态 —— 别以为那两行是多余的）。同一次按下的 item/widget 绑定 serial 相同，
        #    靠 _ev_token 认出来、原样退回，否则会把 _on_node_press 刚装的 _drag 当残留清掉。
        tok = self._ev_token(ev)
        if tok is not None and tok == getattr(self, "_ptr_press", None):
            return "break"
        self._ptr_press = None
        # 走到这里 = **新的一次按下** ⇒ 上一轮交互的残留状态必是过期的（松开事件丢了）
        # ⇒ 清掉自愈，别让它把 Ctrl 框选永久卡死（详见 _clear_stale_ptr_state）。
        self._clear_stale_ptr_state()
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
print("已写盘")
