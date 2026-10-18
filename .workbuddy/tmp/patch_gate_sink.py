# -*- coding: utf-8 -*-
# 时间判据从对话框 run() 下沉到 _clue_route_sections（纯计算层，所有调用路径都过闸）。
import pathlib

ME = pathlib.Path(r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao/地图修改上位机/map_editor/map_editor.py")

def probe(path):
    b = path.read_bytes()
    crlf = b.count(b"\r\n"); lf = b.count(b"\n") - crlf
    assert (crlf == 0) or (lf == 0)
    return "\r\n" if crlf >= lf else "\n"

E = []

# 1) run() 里的闸删掉（只留解析）
E.append(('''            p56 = self._p56_on(p56_sel.get())
            plan_elapsed = self._elapsed_from_choice(plan_sel.get())
            elapsed = self._elapsed_from_choice(elapsed_sel.get())
            # 补走 7/8 的时间判据（固件 plan_treasure_return() 在 P7/P8 那一刻查）：
            # 已用时 + TB_P56_EXTRA_MIN_REMAIN_S > 180 ⇒ 固件不会绕，预览也按不绕画。
            if p56 and plan_elapsed is not None:
                try:
                    _need = int(M.time_budget_macros()["TB_P56_EXTRA_MIN_REMAIN_S"])
                except Exception:                                # noqa: BLE001
                    _need = 85
                if plan_elapsed + _need > 180:
                    p56 = False
''',
'''            p56 = self._p56_on(p56_sel.get())
            plan_elapsed = self._elapsed_from_choice(plan_sel.get())
            elapsed = self._elapsed_from_choice(elapsed_sel.get())
''', 1))

# 2) 闸放进 _clue_route_sections，且回显之前（回显的 开/关 = 生效值）
E.append(('''        sections = [self._input_section(stage, clue, ab, doors, treasure, punch, tour,
                                        elapsed_s=elapsed_s, p56=p56,
                                        plan_elapsed_s=plan_elapsed_s)]
''',
'''        # 补走 7/8 的时间判据（固件 plan_treasure_return() 在 P7/P8 那一刻查）：
        # 已用时 + TB_P56_EXTRA_MIN_REMAIN_S > 180 ⇒ 固件不会绕，预览也按不绕画。
        # 放在纯计算层（而非对话框 run()）：直接调本函数的路径（冒烟/脚本）同样过闸。
        if p56 and plan_elapsed_s is not None:
            try:
                _need = int(M.time_budget_macros()["TB_P56_EXTRA_MIN_REMAIN_S"])
            except Exception:                                # noqa: BLE001
                _need = 85
            if plan_elapsed_s + _need > 180:
                p56 = False
        sections = [self._input_section(stage, clue, ab, doors, treasure, punch, tour,
                                        elapsed_s=elapsed_s, p56=p56,
                                        plan_elapsed_s=plan_elapsed_s)]
''', 1))

# 3) 回显措辞：预览自己会判（选了时刻）/ 固件侧判（没选时刻）
E.append(('''                            "；固件里还要过时间判据（规划时刻剩余 >= 阈值才真去）"
''',
'''                            "；时间判据看下面「规划回程已用时」（没选则按会去画，固件侧仍会判）"
''', 1))

eol = probe(ME)
data = ME.read_bytes().decode("utf-8")
for i, (old, new, want) in enumerate(E):
    o = old.replace("\n", eol); n = new.replace("\n", eol)
    cnt = data.count(o)
    assert cnt == want, "edit#%d 命中 %d 次（应为 %d）" % (i, cnt, want)
    data = data.replace(o, n)
ME.write_bytes(data.encode("utf-8"))
print("[WROTE] map_editor.py：%d 组替换" % len(E))
