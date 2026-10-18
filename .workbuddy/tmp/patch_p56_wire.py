# -*- coding: utf-8 -*-
"""上位机 GUI 接线（map_editor.py）+ 激活 P56_EXTRA_STOP_ENABLE（config.h 置 1）。
字节级替换；probe eol；断言命中次数；全部成功才写盘。"""
import pathlib

BASE = pathlib.Path(r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao")
ME = BASE / "地图修改上位机/map_editor/map_editor.py"
CFG = BASE / "Mission/config.h"

def probe(path):
    b = path.read_bytes()
    crlf = b.count(b"\r\n"); lf = b.count(b"\n") - crlf
    assert (crlf == 0) or (lf == 0)
    return "\r\n" if crlf >= lf else "\n"

edits_me = [
    # 1) _r2_s1_on 后面加 _p56_extra_on()（预编译开关：读不到宏按【关】，对齐 #if 语义）
    (r"""            self.status("⚠ 读 config.h 的 ROUND2_S1_ENABLE 失败（按开处理）：%s" % ex)
            return True
""",
     r"""            self.status("⚠ 读 config.h 的 ROUND2_S1_ENABLE 失败（按开处理）：%s" % ex)
            return True

    def _p56_extra_on(self):
        \"\"\"一轮宝物=P5/P6 补走 7/8 中未走平台（config.h 的 P56_EXTRA_STOP_ENABLE）。

        预编译开关（固件 #if 门控）：读不到宏按【关】处理 —— C 的 #if 对未定义宏当 0，
        语义对齐。时间判据（规划时刻剩余 ≥ TB_P56_EXTRA_MIN_REMAIN_S）在固件里查，
        上位机不知道比赛时钟：开关开 + 宝物=5/6 就把补走段画进预览。
        \"\"\"
        try:
            macros, _field = M.parse_config_macros()
            return bool(M.eval_c_expr("P56_EXTRA_STOP_ENABLE", macros))
        except Exception as ex:                                  # noqa: BLE001
            self.status("⚠ 读 config.h 的 P56_EXTRA_STOP_ENABLE 失败（按关处理）：%s" % ex)
            return False
"""),
    # 2) 两处 treasure_return_waypoints 调用透传 p56_extra（两处文本相同，各替换一次）
    (r"""        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,
                                                clue, punch, tour, elapsed_s)
""",
     r"""        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,
                                                clue, punch, tour, elapsed_s,
                                                p56_extra=self._p56_extra_on())
"""),
]

eol = probe(ME)
data = ME.read_bytes().decode("utf-8")
for i, (old, new) in enumerate(edits_me):
    o = old.replace("\n", eol); n = new.replace("\n", eol)
    cnt = data.count(o)
    want = 2 if i == 1 else 1
    assert cnt == want, "map_editor edit#%d 命中 %d 次（应为 %d）" % (i, cnt, want)
    data = data.replace(o, n)
print("[OK] map_editor.py 2 组替换断言通过 (eol=%r)" % eol)

# config.h：0 -> 1（激活）
eolc = probe(CFG)
cdata = CFG.read_bytes().decode("utf-8")
old = "#define P56_EXTRA_STOP_ENABLE        0"
assert cdata.count(old) == 1, cdata.count(old)
cdata = cdata.replace(old, "#define P56_EXTRA_STOP_ENABLE        1")
print("[OK] config.h P56_EXTRA_STOP_ENABLE 0 -> 1")

ME.write_bytes(data.encode("utf-8"))
CFG.write_bytes(cdata.encode("utf-8"))
print("[WROTE]", ME)
print("[WROTE]", CFG)
print("ALL DONE")
