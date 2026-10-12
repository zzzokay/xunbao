# -*- coding: utf-8 -*-
"""AI 过程脚本：给仿真主程序加"补打卡开关打开"的预演（只改仿真入参）。"""
import os

S = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机",
                 "tools", "sim_route_bookkeeping.py")
EDITS = []


def rep(old, new):
    EDITS.append((old, new))


rep('def run_case(title, clue, stage_a, stage_b, door_true, treasure,\n'
    '             tour=None, treasure_at_clue=None):\n'
    '    eff = TOUR if tour is None else int(bool(tour))\n'
    '    print("=" * 78)\n'
    '    print("%s   （线索=%s 平台=%s/%s 物理灯色 D2..D5=%s 宝物=%s 巡回开关=%s）"\n'
    '          % (title, clue, stage_a, stage_b, door_true, treasure, eff))\n'
    '    sim = Sim(clue=clue, stage_a=stage_a, stage_b=stage_b, door_true=door_true,\n'
    '              treasure=treasure, tour=tour, treasure_at_clue=treasure_at_clue)\n',
    'def run_case(title, clue, stage_a, stage_b, door_true, treasure,\n'
    '             tour=None, treasure_at_clue=None, punch=None):\n'
    '    eff = TOUR if tour is None else int(bool(tour))\n'
    '    eff_p = PUNCH if punch is None else int(bool(punch))\n'
    '    print("=" * 78)\n'
    '    print("%s   （线索=%s 平台=%s/%s 物理灯色 D2..D5=%s 宝物=%s 巡回开关=%s 补打卡开关=%s）"\n'
    '          % (title, clue, stage_a, stage_b, door_true, treasure, eff, eff_p))\n'
    '    sim = Sim(clue=clue, stage_a=stage_a, stage_b=stage_b, door_true=door_true,\n'
    '              treasure=treasure, tour=tour, treasure_at_clue=treasure_at_clue,\n'
    '              punch=punch)\n')

rep('    for _tre, _tag in ((3, "S1"), (4, "S2")):\n'
    '        run_case("巡回预演（宝物=P%d → 一轮回家腿绕 %s）" % (_tre, _tag), 3, 5, 7,\n'
    '                 [ONE_WAY_PASS, CAN_PASS, CAN_PASS, NO_PASS, NO_PASS], 0,\n'
    '                 tour=True, treasure_at_clue=_tre)\n',
    '    for _tre, _tag in ((3, "S1"), (4, "S2")):\n'
    '        run_case("巡回预演（宝物=P%d → 一轮回家腿绕 %s）" % (_tre, _tag), 3, 5, 7,\n'
    '                 [ONE_WAY_PASS, CAN_PASS, CAN_PASS, NO_PASS, NO_PASS], 0,\n'
    '                 tour=True, treasure_at_clue=_tre)\n'
    '\n'
    '    # 补打卡开关打开后的预演（只改仿真入参，不碰任何文件）：\n'
    '    # 宝物选 P1（=2）⇒ 回程腿与 P3/P4 无关，补打卡才看得清楚；\n'
    '    # 线索=3（去程去过 P3）⇒ 只补 P4；线索=0（两个都没去）⇒ 两个都补。\n'
    '    for _clue, _tag in ((3, "只补 P4"), (0, "两个都补")):\n'
    '        run_case("补打卡预演（线索=%d → 一轮回家腿%s）" % (_clue, _tag), _clue, 5, 7,\n'
    '                 [ONE_WAY_PASS, CAN_PASS, CAN_PASS, NO_PASS, NO_PASS], 0,\n'
    '                 punch=True, treasure_at_clue=2)\n')


def main():
    with open(S, "rb") as f:
        data = f.read()
    eol = "\r\n" if data.count(b"\r\n") else "\n"
    for old, new in EDITS:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "命中 %d 次（期望 1）:\n%r" % (cnt, old[:80])
        data = data.replace(ob, nb)
    with open(S, "wb") as f:
        f.write(data)
    print("[ok] sim +%d 处改动, crlf=%d lf=%d"
          % (len(EDITS), data.count(b"\r\n"), data.count(b"\n") - data.count(b"\r\n")))


if __name__ == "__main__":
    main()
