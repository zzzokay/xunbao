# -*- coding: utf-8 -*-
"""AI 过程脚本 第 1 步：map_model.py 镜像 `UPRIGHT_TOUR_ENABLE`（S1/S2 巡回）。"""
import os

ME = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机", "map_editor")
MODEL = os.path.join(ME, "map_model.py")
EDITS = []


def rep(old, new):
    EDITS.append((old, new))


# 1) 新增纯函数 + treasure_return 签名/文档
rep('def treasure_return_waypoints(start, doors, treasure, line_clue=None, punch=False):\n'
    '    """镜像 plan_treasure_return()：在 P7/P8 读到宝物编号后的回程 wp。\n'
    '\n'
    '    punch=True 时按 P3P4_PUNCH_ENABLE 追加"补打卡"平台（见 p3p4_punch_waypoints()），\n'
    '    位置 = 宝物平台之后、S1/S2 之前；line_clue = QR 百位（0/3/4/None）。\n'
    '    """\n',
    'def upright_tour_waypoints(treasure):\n'
    '    """镜像 mission_planner.c 的 `UPRIGHT_TOUR_ENABLE` 一轮那两处：宝物 P3 绕 S1、P4 绕 S2。\n'
    '\n'
    '    其余宝物值一轮不绕（二轮"固定两个都绕"由 round2_waypoints() 自己插）。\n'
    '    ⚠️ S1/S2 的进边 `func` 是 `View1`、`map_function()` 里没有 `case View1`\n'
    '       ⇒ **只走位、不做动作、不得分**。\n'
    '    """\n'
    '    if treasure == 3:\n'
    '        return ["S1"]\n'
    '    if treasure == 4:\n'
    '        return ["S2"]\n'
    '    return []\n'
    '\n'
    '\n'
    'def treasure_return_waypoints(start, doors, treasure, line_clue=None, punch=False,\n'
    '                              tour=False):\n'
    '    """镜像 plan_treasure_return()：在 P7/P8 读到宝物编号后的回程 wp。\n'
    '\n'
    '    punch=True ⇒ 按 `P3P4_PUNCH_ENABLE` 追加"补打卡"平台（见 p3p4_punch_waypoints()）；\n'
    '    tour=True ⇒ 按 `UPRIGHT_TOUR_ENABLE` 追加 S1/S2（见 upright_tour_waypoints()）。\n'
    '    两者都在**宝物平台之后、P2 之前**，且 **punch 先于 tour**（与固件里的书写顺序一致）。\n'
    '    line_clue = QR 百位（0/3/4/None）。\n'
    '    """\n')

rep('    if punch:\n'
    '        wp += p3p4_punch_waypoints(treasure, line_clue)\n'
    '    wp.append("P2")\n'
    '    return wp, None\n',
    '    if punch:\n'
    '        wp += p3p4_punch_waypoints(treasure, line_clue)\n'
    '    if tour:\n'
    '        wp += upright_tour_waypoints(treasure)\n'
    '    wp.append("P2")\n'
    '    return wp, None\n')

# 2) door_return_home
rep('def door_return_home_waypoints(start, treasure, allow_N8_N3=False,\n'
    '                               line_clue=None, punch=False):\n',
    'def door_return_home_waypoints(start, treasure, allow_N8_N3=False,\n'
    '                               line_clue=None, punch=False, tour=False):\n')

rep('    if punch:\n'
    '        wp += p3p4_punch_waypoints(treasure, line_clue)\n'
    '    wp.append("P2")\n'
    '    blocked = set(DOOR_ZONE)\n',
    '    if punch:\n'
    '        wp += p3p4_punch_waypoints(treasure, line_clue)\n'
    '    if tour:\n'
    '        wp += upright_tour_waypoints(treasure)\n'
    '    wp.append("P2")\n'
    '    blocked = set(DOOR_ZONE)\n')

rep('    punch=True 时按 P3P4_PUNCH_ENABLE 追加"补打卡"平台（见 p3p4_punch_waypoints()），\n'
    '    位置 = 宝物平台之后、S1/S2 之前；line_clue = QR 百位（0/3/4/None）。\n'
    '    """\n'
    '    wp = [start]\n',
    '    punch=True ⇒ 按 `P3P4_PUNCH_ENABLE` 追加"补打卡"平台；tour=True ⇒ 按\n'
    '    `UPRIGHT_TOUR_ENABLE` 追加 S1/S2（两者都在宝物平台之后、P2 之前，punch 先于 tour）。\n'
    '    line_clue = QR 百位（0/3/4/None）。\n'
    '    """\n'
    '    wp = [start]\n')

# 3) round2
rep('def round2_waypoints(doors, treasure, cruise=None, cfg=None):\n',
    'def round2_waypoints(doors, treasure, cruise=None, cfg=None, tour=False):\n')

rep('    wp = ["N2", "P1", "P3", "P4", "N5"]\n',
    '    wp = ["N2", "P1", "P3"]\n'
    '    if tour:                       # ← 镜像 mission_planner.c 二轮那两处 UPRIGHT_TOUR_ENABLE\n'
    '        wp.append("S1")            #   二轮固定两个都绕（N3 支路）\n'
    '    wp.append("P4")\n'
    '    if tour:\n'
    '        wp.append("S2")            #   N6 支路\n'
    '    wp.append("N5")\n')

rep('    cruise = 自定义巡游顺序（P5~P8 各一次，顺序就是走法）；None = 固件当前顺序\n'
    '             （由 cfg 的 CW/CCW 组按宝物值选，cfg=None 用出厂默认）。\n',
    '    cruise = 自定义巡游顺序（P5~P8 各一次，顺序就是走法）；None = 固件当前顺序\n'
    '             （由 cfg 的 CW/CCW 组按宝物值选，cfg=None 用出厂默认）。\n'
    '    tour=True ⇒ 按 UPRIGHT_TOUR_ENABLE 在 P3 后插 S1、P4 后插 S2。\n')


def main():
    with open(MODEL, "rb") as f:
        data = f.read()
    eol = "\r\n" if data.count(b"\r\n") else "\n"
    for old, new in EDITS:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "命中 %d 次（期望 1）:\n%r" % (cnt, old[:80])
        data = data.replace(ob, nb)
    with open(MODEL, "wb") as f:
        f.write(data)
    print("[ok] map_model.py +%d 处, crlf=%d lf=%d"
          % (len(EDITS), data.count(b"\r\n"), data.count(b"\n") - data.count(b"\r\n")))


if __name__ == "__main__":
    main()
