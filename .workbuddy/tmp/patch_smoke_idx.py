# -*- coding: utf-8 -*-
# 修正 _guismoke 索引：对话框创建序 punch[8]/tour[9]/p56[10]/plan[11]/elapsed[12]。
import pathlib

G = pathlib.Path(r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao/地图修改上位机/map_editor/_guismoke.py")

def probe(path):
    b = path.read_bytes()
    crlf = b.count(b"\r\n"); lf = b.count(b"\n") - crlf
    assert (crlf == 0) or (lf == 0)
    return "\r\n" if crlf >= lf else "\n"

E = []

E.append(('''    check(len(_vals2) == 13 and _vals2[0].startswith("第一轮·完整路线")
          and all(v in _legal_doors for v in _vals2[3:7])
          and _vals2[8].startswith("跟随 config.h（当前：")
          and _vals2[9] == "不启用时间裁剪"
          and _vals2[10].startswith("跟随 config.h（当前：") and _vals2[11].startswith("跟随 config.h（当前：")
          and _vals2[12] == "不启用时间裁剪",
''',
'''    check(len(_vals2) == 13 and _vals2[0].startswith("第一轮·完整路线")
          and all(v in _legal_doors for v in _vals2[3:7])
          and _vals2[8].startswith("跟随 config.h（当前：") and _vals2[9].startswith("跟随 config.h（当前：")
          and _vals2[10].startswith("跟随 config.h（当前：")
          and _vals2[11] == "不启用时间裁剪" and _vals2[12] == "不启用时间裁剪",
''', 1))

E.append(('''    check(_vals2[10] == app._switch_vals("P3P4_PUNCH_ENABLE")[0]
          and _vals2[11] == app._switch_vals("UPRIGHT_TOUR_ENABLE")[0],
          "开关下拉的「跟随 config.h」直接写出当前值（%s ｜ %s）"
          % (_vals2[10], _vals2[11]))
''',
'''    check(_vals2[8] == app._switch_vals("P3P4_PUNCH_ENABLE")[0]
          and _vals2[9] == app._switch_vals("UPRIGHT_TOUR_ENABLE")[0],
          "开关下拉的「跟随 config.h」直接写出当前值（%s ｜ %s）"
          % (_vals2[8], _vals2[9]))
''', 1))

eol = probe(G)
data = G.read_bytes().decode("utf-8")
for i, (old, new, want) in enumerate(E):
    o = old.replace("\n", eol); n = new.replace("\n", eol)
    cnt = data.count(o)
    assert cnt == want, "edit#%d 命中 %d 次（应为 %d）" % (i, cnt, want)
    data = data.replace(o, n)
G.write_bytes(data.encode("utf-8"))
print("[WROTE] _guismoke.py：%d 组替换" % len(E))
