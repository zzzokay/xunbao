# -*- coding: utf-8 -*-
"""「线索路线…」对话框加「宝物=P5/P6 补走 7/8」开关并线程化传入宝物回程。
字节级替换；probe eol；断言命中次数；全部成功才写盘。
定界符用三个单引号（内容可含双引号三连）；插入文本只用井号注释。"""
import pathlib

ME = pathlib.Path(r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao/地图修改上位机/map_editor/map_editor.py")

def probe(path):
    b = path.read_bytes()
    crlf = b.count(b"\r\n"); lf = b.count(b"\n") - crlf
    assert (crlf == 0) or (lf == 0)
    return "\r\n" if crlf >= lf else "\n"

E = []   # (old, new, expect_count)

# ---- 1) _tour_on 后加 _p56_on 助手 ----
E.append(('''    def _tour_on(self, choice):
        """「直立景点巡回 S1/S2」下拉 → bool（`UPRIGHT_TOUR_ENABLE`）。"""
        return self._switch_on("UPRIGHT_TOUR_ENABLE", choice)
''',
'''    def _tour_on(self, choice):
        """「直立景点巡回 S1/S2」下拉 → bool（`UPRIGHT_TOUR_ENABLE`）。"""
        return self._switch_on("UPRIGHT_TOUR_ENABLE", choice)

    def _p56_on(self, choice):
        # 「宝物=P5/P6 补走 7/8」下拉 → bool（P56_EXTRA_STOP_ENABLE，固件 #if 预编译开关）。
        # 固件里真触发还要过时间判据（规划时刻剩余 >= TB_P56_EXTRA_MIN_REMAIN_S）；
        # 上位机没有比赛时钟：强制开 = 预览按会去补走画（固件侧仍以时间为准）。
        return self._switch_on("P56_EXTRA_STOP_ENABLE", choice)
''', 1))

# ---- 2) _append_after_door 签名 + 文档行 ----
E.append(('''    def _append_after_door(self, sections, enter, ab, doors, treasure, mode,
                           clue=None, punch=False, tour=False, elapsed_s=None):
''',
'''    def _append_after_door(self, sections, enter, ab, doors, treasure, mode,
                           clue=None, punch=False, tour=False, elapsed_s=None,
                           p56=None):
''', 1))

# ---- 3) 两处 treasure_return_waypoints 调用：p56 缺省回退读 config ----
E.append(('''        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,
                                                clue, punch, tour, elapsed_s,
                                                p56_extra=self._p56_extra_on())
''',
'''        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,
                                                clue, punch, tour, elapsed_s,
                                                p56_extra=(self._p56_extra_on()
                                                           if p56 is None else p56))
''', 2))

# ---- 4) _round1_complete 签名 ----
E.append(('''    def _round1_complete(self, clue, ab, doors, treasure, mode="full", punch=False,
                         tour=False, elapsed_s=None):
''',
'''    def _round1_complete(self, clue, ab, doors, treasure, mode="full", punch=False,
                         tour=False, elapsed_s=None, p56=None):
''', 1))

# ---- 5) _input_section 签名 ----
E.append(('''    def _input_section(self, stage, clue, ab, doors, treasure, punch=None, tour=None,
                       elapsed_s=None):
''',
'''    def _input_section(self, stage, clue, ab, doors, treasure, punch=None, tour=None,
                       elapsed_s=None, p56=None):
''', 1))

# ---- 6) _input_section 回显：tour 块后加 p56 行 ----
E.append(('''                            if tour else "（不进 S1/S2）"))
        if elapsed_s is not None:
''',
'''                            if tour else "（不进 S1/S2）"))
        if p56 is not None:
            lines.append("宝物=P5/P6 补走 7/8（P56_EXTRA_STOP_ENABLE）= %s%s"
                         % ("开" if p56 else "关",
                            "；固件里还要过时间判据（规划时刻剩余 >= 阈值才真去）"
                            if p56 else "（不补走）"))
        if elapsed_s is not None:
''', 1))

# ---- 7) _clue_route_sections 签名 ----
E.append(('''    def _clue_route_sections(self, stage, clue, ab, doors, treasure, mode="full",
                             punch=False, tour=False, elapsed_s=None):
''',
'''    def _clue_route_sections(self, stage, clue, ab, doors, treasure, mode="full",
                             punch=False, tour=False, elapsed_s=None, p56=None):
''', 1))

# ---- 8) _clue_route_sections：_input_section 调用 ----
E.append(('''        sections = [self._input_section(stage, clue, ab, doors, treasure, punch, tour,
                                        elapsed_s=elapsed_s)]
''',
'''        sections = [self._input_section(stage, clue, ab, doors, treasure, punch, tour,
                                        elapsed_s=elapsed_s, p56=p56)]
''', 1))

# ---- 9) _clue_route_sections：_round1_complete 调用 ----
E.append(('''            sub, flat, split, err = self._round1_complete(clue, ab, doors, treasure, mode,
                                                          punch, tour, elapsed_s)
''',
'''            sub, flat, split, err = self._round1_complete(clue, ab, doors, treasure, mode,
                                                          punch, tour, elapsed_s, p56=p56)
''', 1))

# ---- 10) 两处 _append_after_door 调用 ----
E.append(('''            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode,
                                             clue, punch, tour, elapsed_s) or []
''',
'''            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode,
                                             clue, punch, tour, elapsed_s, p56=p56) or []
''', 2))

# ---- 11) 对话框：P56_VALS ----
E.append(('''        PUNCH_VALS = self._switch_vals("P3P4_PUNCH_ENABLE")
        TOUR_VALS = self._switch_vals("UPRIGHT_TOUR_ENABLE")
''',
'''        PUNCH_VALS = self._switch_vals("P3P4_PUNCH_ENABLE")
        TOUR_VALS = self._switch_vals("UPRIGHT_TOUR_ENABLE")
        P56_VALS = self._switch_vals("P56_EXTRA_STOP_ENABLE")
''', 1))

# ---- 12) 对话框：p56 下拉插到巡回之后，已用时顺延一行 ----
E.append(('''        tour_sel = combo(7, "直立景点巡回 S1/S2", TOUR_VALS,
                         _pick("tour", TOUR_VALS, TOUR_VALS[0]))
        TIME_VALS = time_budget_choices()   # 10 秒阶梯 + config.h 的 TB_* 边界
        elapsed_sel = combo(8, "比赛已用时", TIME_VALS,
                            _pick("elapsed", TIME_VALS, TIME_VALS[0]))
''',
'''        tour_sel = combo(7, "直立景点巡回 S1/S2", TOUR_VALS,
                         _pick("tour", TOUR_VALS, TOUR_VALS[0]))
        p56_sel = combo(8, "宝物=P5/P6 补走 7/8", P56_VALS,
                        _pick("p56", P56_VALS, P56_VALS[0]))
        TIME_VALS = time_budget_choices()   # 10 秒阶梯 + config.h 的 TB_* 边界
        elapsed_sel = combo(9, "比赛已用时", TIME_VALS,
                            _pick("elapsed", TIME_VALS, TIME_VALS[0]))
''', 1))

# ---- 13) 说明文字：补走解释 + grid 行号 9->10 ----
E.append(('''                            "巡回 = UPRIGHT_TOUR_ENABLE（一轮跟着「会不会去 P3/P4」绕 S1/S2，与补打卡交错成 P3→S1→P4→S2，二轮两个都绕）；"
                            "已用时 = 固件比赛计时（出发起算）；选了就会按时间预算裁剪尾段"
                            "（宝物在 P1 另有更紧的 2:15 / 2:25 两档，见「时间预算…」）；"
                            "这些选择会记住，随「保存布局」一起存，重启也在）",
                  foreground="#666666", wraplength=620, justify="left").grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(6, 0))
''',
'''                            "巡回 = UPRIGHT_TOUR_ENABLE（一轮跟着「会不会去 P3/P4」绕 S1/S2，与补打卡交错成 P3→S1→P4→S2，二轮两个都绕）；"
                            "补走 7/8 = P56_EXTRA_STOP_ENABLE（宝物在 P5/P6 时先绕去 7/8 中没去过的那个平台再过门；固件里还要按剩余时间判，强制开 = 预览按会去画）；"
                            "已用时 = 固件比赛计时（出发起算）；选了就会按时间预算裁剪尾段"
                            "（宝物在 P1 另有更紧的 2:15 / 2:25 两档，见「时间预算…」）；"
                            "这些选择会记住，随「保存布局」一起存，重启也在）",
                  foreground="#666666", wraplength=620, justify="left").grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(6, 0))
''', 1))

# ---- 14) run()：解析 p56 ----
E.append(('''            punch = self._punch_on(punch_sel.get())
            tour = self._tour_on(tour_sel.get())
            elapsed = self._elapsed_from_choice(elapsed_sel.get())
''',
'''            punch = self._punch_on(punch_sel.get())
            tour = self._tour_on(tour_sel.get())
            p56 = self._p56_on(p56_sel.get())
            elapsed = self._elapsed_from_choice(elapsed_sel.get())
''', 1))

# ---- 15) run()：记进 cfg ----
E.append(('''                "punch": punch_sel.get(),
                "tour": tour_sel.get(),
                "elapsed": elapsed_sel.get(),
''',
'''                "punch": punch_sel.get(),
                "tour": tour_sel.get(),
                "p56": p56_sel.get(),
                "elapsed": elapsed_sel.get(),
''', 1))

# ---- 16) run()：传给 _clue_route_sections ----
E.append(('''            sections, canvas, err = self._clue_route_sections(
                stage.get(), clue, ab, doors, tval, self.cost_mode.get(), punch, tour,
                elapsed_s=elapsed)
''',
'''            sections, canvas, err = self._clue_route_sections(
                stage.get(), clue, ab, doors, tval, self.cost_mode.get(), punch, tour,
                elapsed_s=elapsed, p56=p56)
''', 1))

# ---- 17) 按钮行 row 10 -> 11 ----
E.append(('''        buttons = ttk.Frame(frm)
        buttons.grid(row=10, column=0, columnspan=2, sticky="w", pady=(14, 0))
''',
'''        buttons = ttk.Frame(frm)
        buttons.grid(row=11, column=0, columnspan=2, sticky="w", pady=(14, 0))
''', 1))

eol = probe(ME)
data = ME.read_bytes().decode("utf-8")
for i, (old, new, want) in enumerate(E):
    o = old.replace("\n", eol); n = new.replace("\n", eol)
    cnt = data.count(o)
    assert cnt == want, "edit#%d 命中 %d 次（应为 %d）:\n%s" % (i, cnt, want, old[:120])
    data = data.replace(o, n)
print("[OK] %d 组替换断言全部通过 (eol=%r)" % (len(E), eol))
ME.write_bytes(data.encode("utf-8"))
print("[WROTE]", ME)
