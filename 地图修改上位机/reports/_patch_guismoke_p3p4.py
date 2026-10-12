# -*- coding: utf-8 -*-
"""AI 过程脚本：_guismoke.py 适配「回程补打卡 P3/P4」（第 5 个下拉）+ 新增断言。

- 修：对话框预填/回退默认值两条断言（下拉数 8 -> 9）。
- 加：p3p4_punch_waypoints 纯函数、门回程 wp、_punch_on 跟随 config.h、规划路线真的经过 P3/P4。
"""
import os

ME = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机", "map_editor")
G = os.path.join(ME, "_guismoke.py")
EDITS = []


def rep(old, new):
    EDITS.append((old, new))


# 1) 预填配置里加 punch
rep('    _cfg_want = {\n'
    '        "stage": "第二轮·完整路线（get_newroute）",\n'
    '        "p1clue": "线索=4：经过 P4",\n'
    '        "stg": "A=6,B=8：P6 -> P8",\n'
    '        "doors": ["绿(能过)", "蓝(单相)", "黑(不能过)", "蓝(单相)"],\n'
    '        "treasure": "6 · P6",\n'
    '    }\n',
    '    _cfg_want = {\n'
    '        "stage": "第二轮·完整路线（get_newroute）",\n'
    '        "p1clue": "线索=4：经过 P4",\n'
    '        "stg": "A=6,B=8：P6 -> P8",\n'
    '        "doors": ["绿(能过)", "蓝(单相)", "黑(不能过)", "蓝(单相)"],\n'
    '        "treasure": "6 · P6",\n'
    '        "punch": "强制开",\n'
    '    }\n')

rep('    _expect = ([_cfg_want["stage"], _cfg_want["p1clue"], _cfg_want["stg"]]\n'
    '               + _cfg_want["doors"] + [_cfg_want["treasure"]])\n',
    '    _expect = ([_cfg_want["stage"], _cfg_want["p1clue"], _cfg_want["stg"]]\n'
    '               + _cfg_want["doors"] + [_cfg_want["treasure"], _cfg_want["punch"]])\n')

# 2) 回退默认值：下拉数 8 -> 9，并检查补打卡档位回退到默认
rep('    check(len(_vals2) == 8 and _vals2[0].startswith("第一轮·完整路线")\n'
    '          and all(v in _legal_doors for v in _vals2[3:7]),\n',
    '    check(len(_vals2) == 9 and _vals2[0].startswith("第一轮·完整路线")\n'
    '          and all(v in _legal_doors for v in _vals2[3:7])\n'
    '          and _vals2[8] == "跟随 config.h",\n')

# 3) 新增：P3P4 补打卡断言
rep('                                                      _vals2[3:7]))\n'
    '\n'
    '    # 随「保存布局」持久化（沙箱文件，绝不碰真实布局）\n',
    '                                                      _vals2[3:7]))\n'
    '\n'
    '    # --- 一轮回程补打卡 P3/P4（P3P4_PUNCH_ENABLE）---\n'
    '    step("round-1 return: extra P3/P4 punch")\n'
    '    check(M.p3p4_punch_waypoints(3, 0) == ["P4"]\n'
    '          and M.p3p4_punch_waypoints(4, 0) == ["P3"]\n'
    '          and M.p3p4_punch_waypoints(2, 0) == ["P3", "P4"]\n'
    '          and M.p3p4_punch_waypoints(3, 3) == ["P4"]\n'
    '          and M.p3p4_punch_waypoints(4, 4) == ["P3"]\n'
    '          and M.p3p4_punch_waypoints(5, 3) == ["P4"],\n'
    '          "p3p4_punch_waypoints 缺哪个补哪个（去过的 / 宝物平台本身都不重复加）")\n'
    '    _punch_off, _ = M.door_return_home_waypoints("N3", 2, False)\n'
    '    _punch_on, _ = M.door_return_home_waypoints("N3", 2, False, 0, True)\n'
    '    check(_punch_off == ["N3", "P1", "P2"]\n'
    '          and _punch_on == ["N3", "P1", "P3", "P4", "P2"],\n'
    '          "门回程：补打卡插在宝物平台之后、P2 之前（%s -> %s）"\n'
    '          % (_punch_off, _punch_on))\n'
    '    check(app._punch_on("跟随 config.h") is False\n'
    '          and app._punch_on("强制开") is True and app._punch_on("强制关") is False,\n'
    '          "「回程补打卡」下拉跟随 config.h（当前 P3P4_PUNCH_ENABLE=0 ⇒ 关）")\n'
    '    _wp_p, _ = M.door_return_home_waypoints("N3", 4, False, 0, True)\n'
    '    _rt_p, _why_p = app.model.plan_route(_wp_p, "full")\n'
    '    check(bool(_rt_p) and "P4" in _rt_p and "P3" in _rt_p,\n'
    '          "开了补打卡后的门回程路线真的绕到 P4、P3 再回家（%s）"\n'
    '          % (" -> ".join(_rt_p or [])[:60]))\n'
    '\n'
    '    # 随「保存布局」持久化（沙箱文件，绝不碰真实布局）\n')


def main():
    with open(G, "rb") as f:
        data = f.read()
    eol = "\r\n" if data.count(b"\r\n") else "\n"
    for old, new in EDITS:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "命中 %d 次（期望 1）:\n%r" % (cnt, old[:80])
        data = data.replace(ob, nb)
    with open(G, "wb") as f:
        f.write(data)
    print("[ok] _guismoke.py +%d 处改动, crlf=%d lf=%d"
          % (len(EDITS), data.count(b"\r\n"), data.count(b"\n") - data.count(b"\r\n")))


if __name__ == "__main__":
    main()
