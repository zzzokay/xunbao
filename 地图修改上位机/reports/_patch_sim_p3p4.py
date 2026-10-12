# -*- coding: utf-8 -*-
"""AI 过程脚本：让仿真镜像也覆盖新的 P3P4_PUNCH_ENABLE（插点 + 源同步自检）。"""
import os

TOOLS = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机", "tools")
S = os.path.join(TOOLS, "sim_route_bookkeeping.py")
EDITS = []


def rep(old, new):
    EDITS.append((old, new))


# 1) 新增开关宏 + 读值
rep('TOUR_MACRO = "UPRIGHT_TOUR_ENABLE"\n',
    'TOUR_MACRO = "UPRIGHT_TOUR_ENABLE"\n'
    'PUNCH_MACRO = "P3P4_PUNCH_ENABLE"      # 一轮回程补打卡 P3/P4（缺哪个补哪个）\n')

rep('_TOUR_RAW = read_config_flag(TOUR_MACRO)\n'
    'TOUR = 0 if _TOUR_RAW is None else _TOUR_RAW      # 开关真值（0 = 与现状一致）\n',
    '_TOUR_RAW = read_config_flag(TOUR_MACRO)\n'
    'TOUR = 0 if _TOUR_RAW is None else _TOUR_RAW      # 开关真值（0 = 与现状一致）\n'
    '_PUNCH_RAW = read_config_flag(PUNCH_MACRO)\n'
    'PUNCH = 0 if _PUNCH_RAW is None else _PUNCH_RAW\n')

# 2) 自检：补打卡两处 + 二轮不该有
rep('    # ④ wp 容量：nowNode + 宝物平台 + S + P2 = 4\n'
    '    body = _fn_body(MP_CODE, "route_return_home") or ""\n'
    '    m = re.search(r"u8\\s+wp\\s*\\[\\s*(\\d+)\\s*\\]", body)\n'
    '    if not m:\n'
    '        SYNC_PROBLEMS.append("route_return_home() 里找不到 u8 wp[N]")\n'
    '    elif int(m.group(1)) < 4:\n'
    '        SYNC_PROBLEMS.append(\n'
    '            "route_return_home() 的 wp[%s] 装不下 nowNode+平台+S+P2（需 >=4）" % m.group(1))\n',
    '    # ④ 一轮回程补打卡 P3/P4（P3P4_PUNCH_ENABLE）：一轮两处，条件 = 百位/宝物平台去过就跳过\n'
    '    if _PUNCH_RAW is None:\n'
    '        SYNC_PROBLEMS.append("config.h 里找不到 #define %s" % PUNCH_MACRO)\n'
    '    for fn in ("plan_treasure_return", "route_return_home"):\n'
    '        body = _fn_body(MP_CODE, fn)\n'
    '        if body is None:\n'
    '            continue\n'
    '        blks = _guarded(body, PUNCH_MACRO)\n'
    '        if len(blks) != 1:\n'
    '            SYNC_PROBLEMS.append("%s() 里 if (%s) 块有 %d 个，镜像假设 1 个"\n'
    '                                 % (fn, PUNCH_MACRO, len(blks)))\n'
    '            continue\n'
    '        for cond, stmt in (("flag_line_clue != 3", "wp[n++] = P3;"),\n'
    '                           ("flag_line_clue != 4", "wp[n++] = P4;")):\n'
    '            if cond not in blks[0] or stmt not in blks[0]:\n'
    '                SYNC_PROBLEMS.append("%s() 的补打卡块里缺 %s + %s" % (fn, cond, stmt))\n'
    '    _r2 = _fn_body(MP_CODE, "get_newroute") or ""\n'
    '    if _guarded(_r2, PUNCH_MACRO):\n'
    '        SYNC_PROBLEMS.append(\n'
    '            "get_newroute() 里也出现 %s —— 二轮本来就固定走 P3/P4，不该再插" % PUNCH_MACRO)\n'
    '\n'
    '    # ⑤ wp 容量：nowNode + 宝物平台 + P3/P4 + S + P2 = 6\n'
    '    body = _fn_body(MP_CODE, "route_return_home") or ""\n'
    '    m = re.search(r"u8\\s+wp\\s*\\[\\s*(\\d+)\\s*\\]", body)\n'
    '    if not m:\n'
    '        SYNC_PROBLEMS.append("route_return_home() 里找不到 u8 wp[N]")\n'
    '    elif int(m.group(1)) < 6:\n'
    '        SYNC_PROBLEMS.append(\n'
    '            "route_return_home() 的 wp[%s] 装不下 nowNode+平台+P3+P4+S+P2（需 >=6）"\n'
    '            % m.group(1))\n')

# 3) Sim：新增 punch 参数
rep('    def __init__(self, clue=3, stage_a=5, stage_b=7, door_true=None, treasure=0,\n'
    '                 tour=None, treasure_at_clue=None):\n',
    '    def __init__(self, clue=3, stage_a=5, stage_b=7, door_true=None, treasure=0,\n'
    '                 tour=None, treasure_at_clue=None, punch=None):\n')

rep('        self.tour = TOUR if tour is None else int(bool(tour))\n',
    '        self.tour = TOUR if tour is None else int(bool(tour))\n'
    '        self.punch = PUNCH if punch is None else int(bool(punch))\n')

# 4) 两处镜像插点
rep('        if self.treasure not in (5, 6):\n'
    '            wp.append({2: "P1", 3: "P3", 4: "P4"}[self.treasure])\n'
    '        if self.tour:      # ← 镜像 mission_planner.c 的 UPRIGHT_TOUR_ENABLE 块\n',
    '        if self.treasure not in (5, 6):\n'
    '            wp.append({2: "P1", 3: "P3", 4: "P4"}[self.treasure])\n'
    '        if self.punch:     # ← 镜像 mission_planner.c 的 P3P4_PUNCH_ENABLE 块\n'
    '            if self.clue != 3 and self.treasure != 3:   wp.append("P3")\n'
    '            if self.clue != 4 and self.treasure != 4:   wp.append("P4")\n'
    '        if self.tour:      # ← 镜像 mission_planner.c 的 UPRIGHT_TOUR_ENABLE 块\n')

rep('        elif self.treasure == 4:\n'
    '            wp.append("P4")\n'
    '        if self.tour:      # ← 镜像 mission_planner.c 的 UPRIGHT_TOUR_ENABLE 块\n',
    '        elif self.treasure == 4:\n'
    '            wp.append("P4")\n'
    '        if self.punch:     # ← 镜像 mission_planner.c 的 P3P4_PUNCH_ENABLE 块\n'
    '            if self.clue != 3 and self.treasure != 3:   wp.append("P3")\n'
    '            if self.clue != 4 and self.treasure != 4:   wp.append("P4")\n'
    '        if self.tour:      # ← 镜像 mission_planner.c 的 UPRIGHT_TOUR_ENABLE 块\n')

# 5) 摘要行
rep('    print("UPRIGHT_TOUR_ENABLE = %s   （读自 Mission/config.h；不用改本脚本）" % TOUR)\n',
    '    print("UPRIGHT_TOUR_ENABLE = %s ｜ P3P4_PUNCH_ENABLE = %s"\n'
    '          "   （读自 Mission/config.h；不用改本脚本）" % (TOUR, PUNCH))\n')

rep('        print("源同步自检：通过（三处 wp 插点 / 开关取值 / wp 容量 均与 mission_planner.c 一致）")\n',
    '        print("源同步自检：通过（S1/S2 三处 + P3/P4 两处插点 / 两个开关取值 / wp 容量"\n'
    '              " 均与 mission_planner.c 一致）")\n')


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
    print("[ok] sim_route_bookkeeping.py +%d 处改动, crlf=%d lf=%d"
          % (len(EDITS), data.count(b"\r\n"), data.count(b"\n") - data.count(b"\r\n")))


if __name__ == "__main__":
    main()
