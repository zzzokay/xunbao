# -*- coding: utf-8 -*-
"""端到端验证：D2黑+D3绿 时门区画线必须是 N5→N8（不再有 N12→N8），
且 N5→N12 以淡色画成"探灯半程"。同时跑 D2绿 / D2黑D3黑D4绿 两个对照。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ED = os.path.join(os.path.dirname(HERE), "map_editor")
if ED not in sys.path:
    sys.path.insert(0, ED)

import map_editor as E          # noqa: E402
import map_model as M# noqa: E402

FAIL = []


def check(cond, msg):
    print(("  [OK]   " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAIL.append(msg)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    app = E.App()
    app.update_idletasks()
    # ⚠️ 布局优先于源码（§7.6），且 default.json 里有源码没有的 N23 ⇒ 必须强制读源码，
    #    否则门区断言会被布局那份边表干扰。load_from_sources 之后再 redraw。
    app.model.load_from_sources()
    app.route = []
    app._reset_route_marks()
    app.redraw()
    app.update()

    def door_seg(flat):
        """截门区那一段：从**第一个 N5**（P1 数组末尾那个，D2 黑时已被砍掉）
        到**去程范围内**最后一个 N8/N12（过门落点）为止。

        ⚠️ 三个坑：
        · 不能按"N4 的位置"定位 —— clue=3/4 的 P1 手写数组本身就含 N4→N3→P3→N3→N4。
        · 必须限定在去程内找落点 —— 回程从 N16 经 N12→N8 回家，也会出现 N8/N12。
        · D2 绿时过门落在 N12、去程里根本没有 N8 ⇒ 落点要取 N8/N12 里靠后的那个，
          且不能对空序列取 max（上面那次ValueError 就是这么来的）。
        """
        out = flat[:app.route_split + 1] if app.route_split else flat
        i = out.index("N5")
        ends = [k for k, n in enumerate(out) if n in ("N8", "N12")]
        return out[i:max(ends) + 1]

    # ---------- D2黑 + D3绿 ----------
    doors = [M.NO_PASS, M.CAN_PASS, M.NO_PASS, M.NO_PASS]
    secs, flat, err = app._clue_route_sections(
        "第一轮·完整路线（去程+门区+东区+回程 自动拼接，画布分色）", 3, (5, 7),
        doors, 4, "full")
    print("\n=== D2黑 + D3绿 ===")
    print("门区段:", " -> ".join(door_seg(flat)))
    print("淡色边:", app.route_dim_edges)
    check(err is None, "路线能算出来")
    seg = door_seg(flat)
    check("N12" not in seg, "门区段内不再出现 N12（D2 黑 ⇒ 没真到过 N12），实际 %s"
          % "->".join(seg))
    check(seg[0] == "N5", "门区段从 N5 起步（实际 %s）" % seg[0])
    i5 = seg.index("N5")
    check(seg[i5 + 1] == "N8",
          "N5 之后直接是 N8（真正的 N5→N8 画出来了），实际 %s" % "->".join(seg[i5:i5 + 3]))
    check(("N12", "N8") not in [(seg[k], seg[k + 1]) for k in range(len(seg) - 1)],
          "门区段内不再出现凭空的 N12→N8")
    check(app.route_dim_edges == [("N5", "N12")],
          "淡色边 = [('N5','N12')]（只开到中点读 D2），实际 %s" % (app.route_dim_edges,))
    # 每一跳仍是真实边（主线）
    bad = [(flat[k], flat[k + 1]) for k in range(len(flat) - 1)
           if app.model.edge(flat[k], flat[k + 1]) is None]
    check(not bad, "主线每一跳都是边表里的真实边（无边 %d 处：%s）" % (len(bad), bad[:4]))

    # 画布上确实同时有主线色与淡色
    app.route = flat
    app.redraw()
    app.update()
    cols = set()
    for it in app.canvas.find_all():
        if app.canvas.type(it) == "line":
            c = app.canvas.itemcget(it, "fill")
            if c:
                cols.add(str(c))
    check(E.ROUTE_DIM_COLOR in cols, "画布上出现淡色线%s" % E.ROUTE_DIM_COLOR)
    check(E.ROUTE_COLOR in cols, "画布上出现主线色 %s" % E.ROUTE_COLOR)

    # ---------- 对照：D2绿（不该有淡色边，主线就是 N5→N12）----------
    print("\n=== 对照 D2绿 ===")
    _s2, flat2, err2 = app._clue_route_sections(
        "第一轮·完整路线（去程+门区+东区+回程 自动拼接，画布分色）", 3, (5, 7),
        [M.CAN_PASS, M.NO_PASS, M.NO_PASS, M.NO_PASS], 4, "full")
    print("门区段:", " -> ".join(door_seg(flat2)), "| 淡色:", app.route_dim_edges)
    check(err2 is None and app.route_dim_edges == [],
          "D2绿：无淡色边（车真过门了，N5→N12 属于主线）")
    check("N12" in flat2, "D2绿：主线含 N12（过门落在 N12）")

    # ---------- 对照：D2黑+D3黑+D4绿（door1route 那条）----------
    print("\n=== 对照 D2黑+D3黑+D4绿 ===")
    _s3, flat3, err3 = app._clue_route_sections(
        "第一轮·完整路线（去程+门区+东区+回程 自动拼接，画布分色）", 3, (5, 7),
        [M.NO_PASS, M.NO_PASS, M.CAN_PASS, M.NO_PASS], 4, "full")
    print("门区段:", " -> ".join(door_seg(flat3)), "| 淡色:", app.route_dim_edges)
    check(err3 is None, "能算出来")
    i5 = flat3[:app.route_split + 1].index("N5")
    check(flat3[i5:i5 + 3] == ["N5", "N8", "N5"],
          "N5→N8 读 D3 后退回 N5，实际 %s" % "->".join(flat3[i5:i5 + 3]))
    check(flat3[i5:i5 + 6] == ["N5", "N8", "N5", "N4", "N3", "N8"],
          "门区段 = N5→N8→N5→N4→N3→N8（door1route={N3,N8}），实际 %s"
          % "->".join(flat3[i5:i5 + 6]))
    check(("N12", "N8") not in [(flat3[k], flat3[k + 1]) for k in range(len(flat3) - 1)
                               if flat3[k] == "N12" and k <= i5 + 6],
          "门区段内不再出现凭空的 N12→N8")
    check(app.route_dim_edges == [("N5", "N12"), ("N5", "N8")],
          "淡色边 = N5→N12 与 N5→N8（两次探灯都没过门），实际 %s" % (app.route_dim_edges,))

    # ---------- 淡色边必须随重算复位 ----------
    print("\n=== 复位护栏 ===")
    # ⚠️ 必须调真正会复位的入口：_refresh_wp() 只刷必经点控件、不碰路线标记。
    # 走 show_default_route()（= 固件 mapInit 的常规路线），它内部调了 _reset_route_marks()。
    app.plan_normal_route()
    check(app.route_dim_edges == [] and app.route_split is None,
          "常规路线后淡色边与 split 都已复位（dim=%s split=%s）"
          % (app.route_dim_edges, app.route_split))
    app.clear_route()
    check(app.route_dim_edges == [] and app.route_split is None,
          "清空路线后仍为空（clear_route 也走复位）")

    app.destroy()
    print("\n结果：%d 项 FAIL" % len(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())