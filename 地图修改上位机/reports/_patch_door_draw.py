# -*- coding: utf-8 -*-
"""改 map_editor 的门区画线：
 1) _round1_complete()：D2 不能过时，leg1 末尾那个 N12 砍掉（P1 手写数组以 N12 结尾只对
    "车真的过门到 N12"成立；D2 黑时车只开到 N5→N12 边中点就读灯、然后倒车退回 N5）。
    砍掉后 hops 直接接在 N5 上，N5→N8 就是真实边 ⇒ 不再凭空画 N12→N8。
 2) 新增 App.route_dim_edges + _draw_route() 里用淡色补画"探灯半程"边。
 3) 所有复位 route_split 的地方一并复位 route_dim_edges（护栏：新的"设置 route"处必须同复位）。
字节级替换，全部成功才写盘。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor", "map_editor.py")


def apply(path, edits):
    """edits = [(old, new, expect_count)]；任一不匹配则整体放弃，不写盘。"""
    with io.open(path, "rb") as fh:
        data = fh.read()
    eol = "\r\n" if b"\r\n" in data else "\n"
    out = data
    for old, new, cnt in edits:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        got = out.count(ob)
        if got != cnt:
            print("FAIL [%s]: 目标块出现 %d 次（应为 %d）\n--- 片段 ---\n%s"
                  % (os.path.basename(path), got, cnt, old[:160]))
            return False
        out = out.replace(ob, nb)
    with io.open(path, "wb") as fh:
        fh.write(out)
    print("OK: %s 应用了 %d 处替换（eol=%r）"
          % (os.path.basename(path), len(edits), eol))
    return True


# ---------------------------------------------------------------- 1) 属性
E1 = (
'''        self.route_split = None       # 回程起始下标（仅"第一轮完整路线"用；其余为 None）''',
'''        self.route_split = None       # 回程起始下标（仅"第一轮完整路线"用；其余为 None）
        # 门区"探灯半程"淡色边 [(from,to)]：车只开到DOOR 边中点读灯、没真过门就退回的那些边。
        # 不进 self.route（那是动画/分色用的主线），单由 _draw_route() 补画。
        self.route_dim_edges = []''',
1)

# ---------------------------------------------------------------- 2) 复位处
E2 = (
'''    def _round1_complete(self, clue, ab, doors, treasure, mode="full"):''',
'''    def _reset_route_marks(self):
        """复位"分色 / 淡色边"两个标记。

        ⚠️ 护栏：**任何**新设置 self.route 的地方都必须调它，否则会残留上一条路线的分色或淡色边
        （以前 route_split 就是这么被漏掉的）。新增路线标记时也挂到这里。
        """
        self.route_split = None
        self.route_dim_edges = []

    def _round1_complete(self, clue, ab, doors, treasure, mode="full"):''',
1)

# ---------------------------------------------------------------- 3) _round1_complete 门区段
E3 = (
'''        # ---- ② 门区读灯（退回重读的额外节点）----
        hops, enter, err = M.door_read_hops(doors)
        if err:
            return sections, [], None, ("固件会停车", err)
        trace, _e, _er = self._door_trace_lines(doors, with_back=False)
        sections.append(("② 去程·门区读灯 / barrier.c:door()", list(trace) + [
            "门区额外节点: %s" % (" -> ".join(hops) if hops else "（无，D2 直接过门）"),
            "过门落点: %s" % enter]))
        outbound = self._join(leg1, hops)''',
'''        # ---- ② 门区读灯（退回重读的额外节点）----
        hops, enter, err = M.door_read_hops(doors)
        if err:
            self.route_dim_edges = []
            return sections, [], None, ("固件会停车", err)
        # P1 手写数组一律以 N12 结尾（固件就是让它去N5→N12 上读 D2）。
        # 但 **D2 不能过时车只开到这条边的中点就读灯、然后倒车退回 N5**，从没到过 N12——
        # 这时把末尾的 N12 砍掉，hops 才能接在 N5 上、让 N5→N8 画成真实边。
        dim = M.door_read_dim_edges(doors)
        if dim and leg1[-1] == "N12":
            leg1 = leg1[:-1]
            leg1_note = ("⚠ D2 不能过 ⇒ 砍掉手写数组末尾的 N12：车只开到 N5→N12 边中点读 D2，"
                         "读不到就 door_retreat(N5,N8)倒车退回 N5，从来没到过 N12。")
        else:
            leg1_note = ""
        trace, _e, _er = self._door_trace_lines(doors, with_back=False)
        sections.append(("② 去程·门区读灯 / barrier.c:door()",
                         ([leg1_note] if leg1_note else []) + list(trace) + [
            "门区额外节点: %s" % ("N5 -> " + " -> ".join(hops) if hops
                                  else "（无，D2 直接过门）"),
            "过门落点: %s" % enter,
            "探灯半程（画布上淡色，不算主线）: %s"
            % ("、".join("%s→%s（只开到中点读灯就退回）" % pe for pe in dim) if dim else "（无）")]))
        outbound = self._join(leg1, hops)
        self.route_dim_edges = [tuple(pe) for pe in dim]''',
1)

# ---------------------------------------------------------------- 4) _draw_route 画淡色边
E4 = (
'''        drawn, allpts = [], []
        for names, col, tag in segs:''',
'''        drawn, allpts = [], []
        # 门区"探灯半程"淡色边：车只开到 DOOR 边中点读灯就退回，没真过门⇒ 不是主线。
        # 画在主线下面，且比主线细/淡，避免被误读成路线的一跳。
        if self.route_dim_edges and mode != "只看回程":
            for a, b in self.route_dim_edges:
                na, nb = self.model.node(a), self.model.node(b)
                if not (na and nb):
                    continue
                x1, y1 = self.w2s(na.x, na.y)
                x2, y2 = self.w2s(nb.x, nb.y)
                self.canvas.create_line(x1, y1, x2, y2, fill=ROUTE_DIM_COLOR,
                                        width=3, dash=(4, 6))
        for names, col, tag in segs:''',
1)

# ---------------------------------------------------------------- 5) 淡色常量
E5 = (
'''ROUTE_COLOR_BACK = "#00897b"      # 路线·回程（青绿）—— 与去程区分，且不撞边的红/橙/选中色''',
'''ROUTE_COLOR_BACK = "#00897b"      # 路线·回程（青绿）—— 与去程区分，且不撞边的红/橙/选中色
ROUTE_DIM_COLOR = "#90a4ae"       # 路线·探灯半程（灰蓝淡色）—— 只到DOOR 边中点读灯、没真过门''',
1)

ok = apply(ME, [E1, E2, E3, E4, E5])
sys.exit(0 if ok else 1)