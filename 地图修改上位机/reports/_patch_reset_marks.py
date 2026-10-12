# -*- coding: utf-8 -*-
"""把 7 处 `self.route_split = None` 复位点统一改走 `self._reset_route_marks()`
（护栏 §6.10：任何设置 self.route 的地方都要复位路线标记，淡色边是新增的第二个标记）。
字节级替换，逐块 count==1 才写盘。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ME = os.path.join(os.path.dirname(HERE), "map_editor", "map_editor.py")

EDITS = [
    #普通规划
    ('''        self.route_split = None          # 普通规划不分去程/回程
        path, why = self.model.plan_route(self.waypoints, self.cost_mode.get())''',
     '''        self._reset_route_marks()        # 普通规划不分去程/回程，也无门区淡色边
        path, why = self.model.plan_route(self.waypoints, self.cost_mode.get())'''),
    # 常规路线
    ('''        self.route_split = None          # 常规路线不分去程/回程
        path, why = self.model.plan_route(waypoints, self.cost_mode.get())''',
     '''        self._reset_route_marks()        # 常规路线不分去程/回程，也无门区淡色边
        path, why = self.model.plan_route(waypoints, self.cost_mode.get())'''),
    # _clue_route_sections 每次重算
    ('''        self.route_split = None          # 每次重算；只有「第一轮·完整路线」会设它（画布分色用）''',
     '''        self._reset_route_marks()        # 每次重算；只有「第一轮·完整路线」会设 split/淡色边'''),
    # 对话框里报错的分支
    ('''                self.route = []
                self.route_split = None
                self.redraw()''',
     '''                self.route = []
                self._reset_route_marks()
                self.redraw()'''),
    # clear_route
    ('''        self.route = []
        self.route_split = None
        self.txt_route.delete("1.0", "end")''',
     '''        self.route = []
        self._reset_route_marks()
        self.txt_route.delete("1.0", "end")'''),
    # 载入布局
    ('''            self.route = []
            self.route_split = None
            self._current_layout = path''',
     '''            self.route = []
            self._reset_route_marks()
            self._current_layout = path'''),
    # 撤销/重做
    ('''            self.route = []
            self.route_split = None
            self.undo_stack.clear()''',
     '''            self.route = []
            self._reset_route_marks()
            self.undo_stack.clear()'''),
]


def main():
    with io.open(ME, "rb") as fh:
        data = fh.read()
    eol = "\r\n" if b"\r\n" in data else "\n"
    out = data
    for old, new in EDITS:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        got = out.count(ob)
        if got != 1:
            print("FAIL: 出现 %d 次（应为 1）\n%s" % (got, old[:120]))
            return 1
        out = out.replace(ob, nb)
    with io.open(ME, "wb") as fh:
        fh.write(out)
    print("OK: %d 处复位点已统一走 _reset_route_marks()" % len(EDITS))
    return 0


if __name__ == "__main__":
    sys.exit(main())