# -*- coding: utf-8 -*-
"""2026-10-07 二轮顺序显示 bug 修复补丁：
1) map_editor.py  _clue_route_sections 二轮分支：cfg 传 None → 现场 parse_round2_cruise()
2) _guismoke.py   二轮断言：写死的默认顺序 → 从 config.h 现值推导
全部成功才写盘；每处 assert 恰好命中一次。
"""
import sys, io

ED = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao/地图修改上位机/map_editor"

def load(path):
    b = open(path, "rb").read()
    crlf = b.count(b"\r\n"); lf = b.count(b"\n") - crlf
    assert not (crlf and lf), "mixed eol in %s" % path
    eol = b"\r\n" if crlf else b"\n"
    return b, eol.decode("ascii"), b.decode("utf-8")

def save(path, eol, txt):
    open(path, "wb").write(txt.encode("utf-8"))

jobs_ok = []

# ---------- 1) map_editor.py ----------
p1 = ED + "/map_editor.py"
b1, eol1, t1 = load(p1)
lines = t1.split(eol1)

# 找二轮分支：`None, None, tour)` 所在行，其上一行含 round2_waypoints(doors
idxs = [i for i, l in enumerate(lines) if l.strip() == "None, None, tour)"]
assert len(idxs) == 1, "anchor 'None, None, tour)' hits %d lines" % len(idxs)
i3 = idxs[0]
i2 = i3 - 1
assert "M.round2_waypoints(doors, treasure if treasure is not None else 0," in lines[i2], lines[i2]
i1 = i2 - 1
assert lines[i1].strip() == "else:", lines[i1]
i8 = i3 + 5
assert lines[i8].strip() == "canvas = list(path) if path else []", lines[i8]
i7 = i8 - 1
assert "sections.append((\"第二轮·完整路线 / get_newroute()\", self._fmt_planned(wp, path, e)))" == lines[i7].strip(), lines[i7]

new_block = [
    "        else:",
    "            # 二轮巡游顺序以 config.h 的 ROUND2_CRUISE_* 为准（「二轮路线…」写回后即生效）：",
    "            # 之前 cfg 传 None 会落回出厂默认，显示的顺序不跟配置走（2026-10-07 修）。",
    "            fw_r2 = M.parse_round2_cruise()",
    "            _t2 = treasure if treasure is not None else 0",
    "            wp, why = M.round2_waypoints(doors, _t2,",
    "                                        None, fw_r2, tour)",
    "            if wp is None:",
    "                return sections, canvas, (\"固件会停车\", str(why))",
    "            path, e = plan(wp)",
    "            sections.append((\"第二轮·完整路线 / get_newroute()（巡游 %s）\"",
    "                             % \"→\".join(M.round2_firmware_cruise(_t2, fw_r2)),",
    "                             self._fmt_planned(wp, path, e)))",
    "            canvas = list(path) if path else []",
]
lines[i1:i8+1] = new_block
t1 = eol1.join(lines)
jobs_ok.append("map_editor.py 二轮分支已改")

# ---------- 2) _guismoke.py ----------
p2 = ED + "/_guismoke.py"
b2, eol2, t2 = load(p2)
old_chk = eol2.join([
    "    # 第二轮 宝物=P6：巡游方向必须翻成逆时针 P6→P8→P7→P5",
    "    secs, _cv, err = app._clue_route_sections(",
    "        ST_R2, None, (5, 7),",
    "        [M.CAN_PASS, M.NO_PASS, M.NO_PASS, M.CAN_PASS], 6, \"full\")",
    "    txt2 = _sections_text(secs)",
    "    check(err is None and \"P6 -> P8 -> P7 -> P5\" in txt2,",
    "          \"第二轮 宝物=P6 的必经点按逆时针排列\")",
])
assert t2.count(old_chk) == 1, "guismoke anchor hits %d" % t2.count(old_chk)
new_chk = eol2.join([
    "    # 第二轮 宝物=P6：巡游方向必须翻成逆时针（CCW = config.h 现值，线索路线镜像固件）",
    "    _ccw_now = M.round2_firmware_cruise(6, M.parse_round2_cruise())",
    "    secs, _cv, err = app._clue_route_sections(",
    "        ST_R2, None, (5, 7),",
    "        [M.CAN_PASS, M.NO_PASS, M.NO_PASS, M.CAN_PASS], 6, \"full\")",
    "    txt2 = _sections_text(secs)",
    "    check(err is None and \" -> \".join(_ccw_now) in txt2,",
    "          \"第二轮 宝物=P6 的必经点按逆时针排列（%s）\" % \" -> \".join(_ccw_now))",
])
t2 = t2.replace(old_chk, new_chk)
jobs_ok.append("_guismoke.py 二轮断言已改为从 config.h 推导")

# ---------- 全部成功才写盘 ----------
save(p1, eol1, t1)
save(p2, eol2, t2)
for j in jobs_ok:
    print("OK:", j)
