# -*- coding: utf-8 -*-
"""改map_model.door_read_hops()：门区退回改用真实边 N5→N8 起步，不再拿 N12→N8 近似。

同时新增 door_read_dim_edges()：N5→N12 这条"只开半程去读 D2 灯"的边单独给界面画淡色。
用字节级替换（护栏：map_editor/*.py 是 CRLF；新块用同 eol；count 必须 ==1；全成功才写盘）。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))          # .../地图修改上位机/reports
TARGET = os.path.join(os.path.dirname(HERE), "map_editor", "map_model.py")

OLD = '''def door_read_hops(doors):
    """进门读灯时，**除了直接过门之外还要多走的节点**（退回重读），只挑边表里真实存在的边。

    第一轮 P1 之后的手写数组一律以 N12 结尾（= 在 N5→N12 上读 D2），所以这里返回的 hops
    直接接在 N12 后面即可拼成连续路径：
      D2 能过      → []                          （过门落在 N12）
      D2 黑、D3 能过 → ["N8"]                      （N12→N8 是真实边；物理上是退回后重走 N5→N8）
      D2 黑、D3 黑、D4 能过 → ["N8","N5","N4","N3","N8"]（N8→N5→N4→N3→N8 全是真实边）
    返回 (hops, enter_node, err)。
    """
    d2, d3, d4 = doors[0], doors[1], doors[2]
    if can_pass(d2):
        return [], "N12", None
    if can_pass(d3):
        return ["N8"], "N8", None
    if can_pass(d4):
        return ["N8", "N5", "N4", "N3", "N8"], "N8", None
    return [], None, "D2/D3/D4 全不能过 → 固件 barrier.c:door() 会 CarBrake_Stop()"
'''

NEW = '''def door_read_hops(doors):
    """进门读灯时，**退回重读那一段真正开过的节点**（全部是边表里的真实边）。

    ⚠️ 物理事实（barrier.c: DOOR_D2 → NO_PASS → door_retreat(N5,N8,DOOR_RETREAT_N5N8)）：
    车沿 P1 手写数组开到**N5→N12 这条 DOOR 边的中点**（step = DOOR_LEN_N5N12/2）就停下读 D2，
    **从来没真正到过 N12**；读出黑就 `Chassis_DriveDistance_Blocking(-SPEED2)` 倒车 63cm 退回 N5 一侧，
    转身面向 N5→N8，再沿 **N5→N8** 去读 D3。所以"退回去"的真实路径是 **N5→N8**，不是 N12→N8。
    （旧实现为了让 hops 能直接接在 P1 数组末尾的 N12 后面，用 N12→N8 近似 ——
      图上就会凭空多画一条车没走过的 N12→N8 斜线，而真正的 N5→N8 反而没画出来。）

    返回 (hops, enter_node, err)，**hops 不含 N5**（调用方已经站在 N5 上，直接接即可）：
      D2 能过→ []                                  （过门落在 N12）
      D2 黑、D3 能过        → ["N8"]（N5→N8 读 D3）
      D2 黑、D3 黑、D4 能过  → ["N8","N5","N4","N3","N8"]
                             （N5→N8 读 D3 → 退 N5 → door1route={N3,N8} 走 N5→N4→N3→N8 读 D4）
      D2/D3/D4 全不能过 → 固件 CarBrake_Stop()
    """
    d2, d3, d4 = doors[0], doors[1], doors[2]
    if can_pass(d2):
        return [], "N12", None
    if can_pass(d3):
        return ["N8"], "N8", None
    if can_pass(d4):
        return ["N8", "N5", "N4", "N3", "N8"], "N8", None
    return [], None, "D2/D3/D4 全不能过 → 固件 barrier.c:door() 会 CarBrake_Stop()"


def door_read_dim_edges(doors):
    """门区里"只开半程去读灯、没真正走过去"的边，供界面画成淡色（不进 self.route）。

    D2 的灯装在 N5→N12 这条边的中点（DOOR_LEN_N5N12/2）：D2 能过时车**确实**开过去了，
    那时 N5→N12 就是主线的一部分，不需要单独画；只有 **D2 不能过**时，车开到中点读完就得倒车退回，
    这一趟是"探灯"而不是"过门"，画成淡色才不会和真正的路线混淆。
    同理 D3 黑时，N5→N8 也只是"开到中点读 D3"（读完还要退 N5 走 door1route）⇒ 同样淡色。

    返回 [(from, to)]，画布上按这些边补淡色虚线。
    """
    d2, d3, d4 = doors[0], doors[1], doors[2]
    out = []
    if not can_pass(d2):
        out.append(("N5", "N12"))        # 开到 D2 门中点读灯，读不到 → 倒车退回
    if not can_pass(d2) and not can_pass(d3):
        out.append(("N5", "N8"))         # 开到 D3 门中点读灯，读不到 → 还要退 N5 走 door1route
    return out
'''


def main():
    with io.open(TARGET, "rb") as fh:
        data = fh.read()
    if b"\r\n" in data:
        eol = "\r\n"
    else:
        eol = "\n"
    old_b = OLD.replace("\n", eol).encode("utf-8")
    new_b = NEW.replace("\n", eol).encode("utf-8")
    n = data.count(old_b)
    if n != 1:
        print("FAIL: 目标块出现 %d 次（应为 1）" % n)
        return 1
    out = data.replace(old_b, new_b)
    with io.open(TARGET, "wb") as fh:
        fh.write(out)
    print("OK: map_model.door_read_hops 已改写，新增 door_read_dim_edges（eol=%r）"
          % eol)
    return 0


if __name__ == "__main__":
    sys.exit(main())