# -*- coding: utf-8 -*-
"""AI 过程脚本 第 3 步：_guismoke.py —— 线索对话框多出第 6 个下拉 + 新增 S1/S2 巡回断言。

⚠️ 两条断言改成**从 config.h 读当前值**再比（原来写死"当前 =0"，
   而 P3P4_PUNCH_ENABLE 已经被改成 1 了 —— 写死就会假失败）。
"""
import os

G = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机",
                 "map_editor", "_guismoke.py")
EDITS = []


def rep(old, new):
    EDITS.append((old, new))


rep('        "treasure": "6 · P6",\n'
    '        "punch": "强制开",\n'
    '    }\n',
    '        "treasure": "6 · P6",\n'
    '        "punch": "强制开",\n'
    '        "tour": "强制开",\n'
    '    }\n')

rep('    _expect = ([_cfg_want["stage"], _cfg_want["p1clue"], _cfg_want["stg"]]\n'
    '               + _cfg_want["doors"] + [_cfg_want["treasure"], _cfg_want["punch"]])\n',
    '    _expect = ([_cfg_want["stage"], _cfg_want["p1clue"], _cfg_want["stg"]]\n'
    '               + _cfg_want["doors"]\n'
    '               + [_cfg_want["treasure"], _cfg_want["punch"], _cfg_want["tour"]])\n')

rep('    check(len(_vals2) == 9 and _vals2[0].startswith("第一轮·完整路线")\n'
    '          and all(v in _legal_doors for v in _vals2[3:7])\n'
    '          and _vals2[8] == "跟随 config.h",\n',
    '    check(len(_vals2) == 10 and _vals2[0].startswith("第一轮·完整路线")\n'
    '          and all(v in _legal_doors for v in _vals2[3:7])\n'
    '          and _vals2[8] == "跟随 config.h" and _vals2[9] == "跟随 config.h",\n')

# 补打卡那条断言：改成读 config.h 的当前值（别再写死 =0）
rep('    check(app._punch_on("跟随 config.h") is False\n'
    '          and app._punch_on("强制开") is True and app._punch_on("强制关") is False,\n'
    '          "「回程补打卡」下拉跟随 config.h（当前 P3P4_PUNCH_ENABLE=0 ⇒ 关）")\n',
    '    _cfg_punch = bool(M.eval_c_expr("P3P4_PUNCH_ENABLE", M.parse_config_macros()))\n'
    '    check(app._punch_on("跟随 config.h") is _cfg_punch\n'
    '          and app._punch_on("强制开") is True and app._punch_on("强制关") is False,\n'
    '          "「回程补打卡」下拉跟随 config.h（当前 P3P4_PUNCH_ENABLE=%d）" % _cfg_punch)\n')

# 新增 S1/S2 巡回断言
rep('    _wp_p, _ = M.door_return_home_waypoints("N3", 4, False, 0, True)\n'
    '    _rt_p, _why_p = app.model.plan_route(_wp_p, "full")\n'
    '    check(bool(_rt_p) and "P4" in _rt_p and "P3" in _rt_p,\n'
    '          "开了补打卡后的门回程路线真的绕到 P4、P3 再回家（%s）"\n'
    '          % (" -> ".join(_rt_p or [])[:60]))\n',
    '    _wp_p, _ = M.door_return_home_waypoints("N3", 4, False, 0, True)\n'
    '    _rt_p, _why_p = app.model.plan_route(_wp_p, "full")\n'
    '    check(bool(_rt_p) and "P4" in _rt_p and "P3" in _rt_p,\n'
    '          "开了补打卡后的门回程路线真的绕到 P4、P3 再回家（%s）"\n'
    '          % (" -> ".join(_rt_p or [])[:60]))\n'
    '\n'
    '    # --- 直立景点巡回 S1/S2（UPRIGHT_TOUR_ENABLE）---\n'
    '    step("round-1/2: upright tour S1/S2")\n'
    '    check(M.upright_tour_waypoints(3) == ["S1"]\n'
    '          and M.upright_tour_waypoints(4) == ["S2"]\n'
    '          and M.upright_tour_waypoints(2) == [],\n'
    '          "upright_tour_waypoints：一轮宝物 P3→S1、P4→S2，其余宝物不绕")\n'
    '    _t_off, _ = M.door_return_home_waypoints("N3", 3, False)\n'
    '    _t_on, _ = M.door_return_home_waypoints("N3", 3, False, 0, False, True)\n'
    '    check(_t_off == ["N3", "P3", "P2"] and _t_on == ["N3", "P3", "S1", "P2"],\n'
    '          "门回程：巡回插在宝物平台之后、P2 之前（%s -> %s）" % (_t_off, _t_on))\n'
    '    _both, _ = M.door_return_home_waypoints("N3", 3, False, 0, True, True)\n'
    '    check(_both == ["N3", "P3", "P4", "S1", "P2"],\n'
    '          "两个开关一起开：补打卡在前、巡回在后（%s）" % _both)\n'
    '    _cfg_tour = bool(M.eval_c_expr("UPRIGHT_TOUR_ENABLE", M.parse_config_macros()))\n'
    '    check(app._tour_on("跟随 config.h") is _cfg_tour\n'
    '          and app._tour_on("强制开") is True and app._tour_on("强制关") is False,\n'
    '          "「直立景点巡回」下拉跟随 config.h（当前 UPRIGHT_TOUR_ENABLE=%d）" % _cfg_tour)\n'
    '    _r2_off, _ = M.round2_waypoints([M.CAN_PASS] * 4, 4)\n'
    '    _r2_on, _ = M.round2_waypoints([M.CAN_PASS] * 4, 4, None, None, True)\n'
    '    check("S1" not in _r2_off and "S2" not in _r2_off\n'
    '          and _r2_on.index("S1") == _r2_on.index("P3") + 1\n'
    '          and _r2_on.index("S2") == _r2_on.index("P4") + 1,\n'
    '          "二轮：巡回开后在 P3 后插 S1、P4 后插 S2（%s）" % " ".join(_r2_on[:7]))\n'
    '    _rt_t, _ = app.model.plan_route(_t_on, "full")\n'
    '    check(bool(_rt_t) and "S1" in _rt_t,\n'
    '          "开了巡回后的门回程路线真的经过 S1（%s）" % (" -> ".join(_rt_t or [])[:60]))\n')


def main():
    with open(G, "rb") as f:
        data = f.read()
    eol = "\r\n" if data.count(b"\r\n") else "\n"
    for old, new in EDITS:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "命中 %d 次（期望 1）:\n%r" % (cnt, old[:90])
        data = data.replace(ob, nb)
    with open(G, "wb") as f:
        f.write(data)
    print("[ok] _guismoke.py +%d 处, crlf=%d lf=%d"
          % (len(EDITS), data.count(b"\r\n"), data.count(b"\n") - data.count(b"\r\n")))


if __name__ == "__main__":
    main()
