# -*- coding: utf-8 -*-
"""_guismoke.py 预期更新：线索路线对话框新增「宝物=P5/P6 补走 7/8」下拉（12 个）。
字节级替换；全部断言通过才写盘。用三单引号定界。"""
import pathlib

G = pathlib.Path(r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao/地图修改上位机/map_editor/_guismoke.py")

def probe(path):
    b = path.read_bytes()
    crlf = b.count(b"\r\n"); lf = b.count(b"\n") - crlf
    assert (crlf == 0) or (lf == 0)
    return "\r\n" if crlf >= lf else "\n"

E = []

# 1) _cfg_want 增加 p56 键
E.append(('''        "punch": "强制开",
        "tour": "强制开",
        "elapsed": "不启用时间裁剪",
    }
''',
'''        "punch": "强制开",
        "tour": "强制开",
        "p56": "强制关",
        "elapsed": "不启用时间裁剪",
    }
''', 1))

# 2) _expect 增加 p56（顺序 = 对话框创建序：...punch, tour, p56, elapsed）
E.append(('''    _expect = ([_cfg_want["stage"], _cfg_want["p1clue"], _cfg_want["stg"]]
               + _cfg_want["doors"]
               + [_cfg_want["treasure"], _cfg_want["punch"], _cfg_want["tour"],
                  _cfg_want["elapsed"]])
''',
'''    _expect = ([_cfg_want["stage"], _cfg_want["p1clue"], _cfg_want["stg"]]
               + _cfg_want["doors"]
               + [_cfg_want["treasure"], _cfg_want["punch"], _cfg_want["tour"],
                  _cfg_want["p56"], _cfg_want["elapsed"]])
''', 1))

# 3) 非法配置回退检查：11 -> 12 个下拉，索引平移
E.append(('''    check(len(_vals2) == 11 and _vals2[0].startswith("第一轮·完整路线")
          and all(v in _legal_doors for v in _vals2[3:7])
          and _vals2[8].startswith("跟随 config.h（当前：") and _vals2[9].startswith("跟随 config.h（当前：")
          and _vals2[10] == "不启用时间裁剪",
''',
'''    check(len(_vals2) == 12 and _vals2[0].startswith("第一轮·完整路线")
          and all(v in _legal_doors for v in _vals2[3:7])
          and _vals2[8].startswith("跟随 config.h（当前：") and _vals2[9].startswith("跟随 config.h（当前：")
          and _vals2[10].startswith("跟随 config.h（当前：")
          and _vals2[11] == "不启用时间裁剪",
''', 1))

# 4) punch/tour 标签索引 8/9 -> 9/10
E.append(('''    check(_vals2[8] == app._switch_vals("P3P4_PUNCH_ENABLE")[0]
          and _vals2[9] == app._switch_vals("UPRIGHT_TOUR_ENABLE")[0],
          "两个开关下拉的「跟随 config.h」直接写出当前值（%s ｜ %s）"
          % (_vals2[8], _vals2[9]))
''',
'''    check(_vals2[9] == app._switch_vals("P3P4_PUNCH_ENABLE")[0]
          and _vals2[10] == app._switch_vals("UPRIGHT_TOUR_ENABLE")[0],
          "开关下拉的「跟随 config.h」直接写出当前值（%s ｜ %s）"
          % (_vals2[9], _vals2[10]))
''', 1))

# 5) 新增 p56 冒烟断言（跟随档解析 + wp 插点）
E.append(('''    _cfg_punch = bool(M.eval_c_expr("P3P4_PUNCH_ENABLE", M.parse_config_macros()[0]))
    check(app._punch_on("跟随 config.h") is _cfg_punch
          and app._punch_on("强制开") is True and app._punch_on("强制关") is False,
          "「回程补打卡」下拉跟随 config.h（当前 P3P4_PUNCH_ENABLE=%d）" % _cfg_punch)
''',
'''    _cfg_punch = bool(M.eval_c_expr("P3P4_PUNCH_ENABLE", M.parse_config_macros()[0]))
    check(app._punch_on("跟随 config.h") is _cfg_punch
          and app._punch_on("强制开") is True and app._punch_on("强制关") is False,
          "「回程补打卡」下拉跟随 config.h（当前 P3P4_PUNCH_ENABLE=%d）" % _cfg_punch)
    _p56_cfg = bool(M.eval_c_expr("P56_EXTRA_STOP_ENABLE", M.parse_config_macros()[0]))
    check(app._p56_on("跟随 config.h") is _p56_cfg
          and app._p56_on("强制开") is True and app._p56_on("强制关") is False,
          "「补走 7/8」下拉跟随 config.h（当前 P56_EXTRA_STOP_ENABLE=%d）" % _p56_cfg)
    _w0, _ = M.treasure_return_waypoints("P8", [2, 1, 1, 1], 5, 0, True, True, None)
    _w1, _ = M.treasure_return_waypoints("P8", [2, 1, 1, 1], 5, 0, True, True, None,
                                         p56_extra=True)
    check(_w0 == ["P8", "P5", "N12", "N5", "P3", "S1", "P4", "S2", "P2"]
          and _w1[:3] == ["P8", "P5", "P7"] and len(_w1) == len(_w0) + 1,
          "补走 7/8：宝物=P5 时在宝物平台后、门节点前插没走过的那个（%s -> %s）"
          % (_w0, _w1))
''', 1))

eol = probe(G)
data = G.read_bytes().decode("utf-8")
for i, (old, new, want) in enumerate(E):
    o = old.replace("\n", eol); n = new.replace("\n", eol)
    cnt = data.count(o)
    assert cnt == want, "edit#%d 命中 %d 次（应为 %d）" % (i, cnt, want)
    data = data.replace(o, n)
print("[OK] %d 组替换断言通过 (eol=%r)" % (len(E), eol))
G.write_bytes(data.encode("utf-8"))
print("[WROTE]", G)
