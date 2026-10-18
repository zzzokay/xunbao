# -*- coding: utf-8 -*-
# 「线索路线…」已用时拆成两个：规划回程（P7/P8 拿宝前，补走判据）+ 出门（N3/N5，尾段裁剪）。
# 字节级替换；全部断言通过才写盘。用三单引号定界；插入内容只用井号注释。
import pathlib

BASE = pathlib.Path(r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao/地图修改上位机/map_editor")
ME = BASE / "map_editor.py"
G = BASE / "_guismoke.py"

def probe(path):
    b = path.read_bytes()
    crlf = b.count(b"\r\n"); lf = b.count(b"\n") - crlf
    assert (crlf == 0) or (lf == 0)
    return "\r\n" if crlf >= lf else "\n"

E_ME = []

# 1) 对话框：p56 下拉之后加「规划回程已用时」，原已用时改名「出门已用时」
E_ME.append(('''        p56_sel = combo(8, "宝物=P5/P6 补走 7/8", P56_VALS,
                        _pick("p56", P56_VALS, P56_VALS[0]))
        TIME_VALS = time_budget_choices()   # 10 秒阶梯 + config.h 的 TB_* 边界
        elapsed_sel = combo(9, "比赛已用时", TIME_VALS,
                            _pick("elapsed", TIME_VALS, TIME_VALS[0]))
''',
'''        p56_sel = combo(8, "宝物=P5/P6 补走 7/8", P56_VALS,
                        _pick("p56", P56_VALS, P56_VALS[0]))
        TIME_VALS = time_budget_choices()   # 10 秒阶梯 + config.h 的 TB_* 边界
        plan_sel = combo(9, "规划回程已用时（P7/P8 拿宝前）", TIME_VALS,
                         _pick("plan_elapsed", TIME_VALS, TIME_VALS[0]))
        elapsed_sel = combo(10, "出门已用时（N3/N5）", TIME_VALS,
                            _pick("elapsed", TIME_VALS, TIME_VALS[0]))
''', 1))

# 2) 说明文字：两个时刻各管什么
E_ME.append(('''                            "已用时 = 固件比赛计时（出发起算）；选了就会按时间预算裁剪尾段"
''',
'''                            "两个已用时都是固件比赛计时（出发起算）：规划回程（P7/P8 拿宝前）= 补走 7/8 的时间判据（已用时+85 ≤ 180 才绕，预览同样把关）；"
                            "出门（N3/N5）= 选了就会按时间预算裁剪尾段"
''', 1))

# 3) run()：解析两个时刻；补走在预览里也执行固件时间判据
E_ME.append(('''            p56 = self._p56_on(p56_sel.get())
            elapsed = self._elapsed_from_choice(elapsed_sel.get())
''',
'''            p56 = self._p56_on(p56_sel.get())
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
''', 1))

# 4) run()：cfg 记 plan_elapsed
E_ME.append(('''                "p56": p56_sel.get(),
                "elapsed": elapsed_sel.get(),
''',
'''                "p56": p56_sel.get(),
                "plan_elapsed": plan_sel.get(),
                "elapsed": elapsed_sel.get(),
''', 1))

# 5) run()：把 plan 时也传下去（回显用）
E_ME.append(('''            sections, canvas, err = self._clue_route_sections(
                stage.get(), clue, ab, doors, tval, self.cost_mode.get(), punch, tour,
                elapsed_s=elapsed, p56=p56)
''',
'''            sections, canvas, err = self._clue_route_sections(
                stage.get(), clue, ab, doors, tval, self.cost_mode.get(), punch, tour,
                elapsed_s=elapsed, p56=p56, plan_elapsed_s=plan_elapsed)
''', 1))

# 6) _input_section 签名
E_ME.append(('''    def _input_section(self, stage, clue, ab, doors, treasure, punch=None, tour=None,
                       elapsed_s=None, p56=None):
''',
'''    def _input_section(self, stage, clue, ab, doors, treasure, punch=None, tour=None,
                       elapsed_s=None, p56=None, plan_elapsed_s=None):
''', 1))

# 7) _input_section：p56 回显行后加规划时刻行
E_ME.append(('''                            if p56 else "（不补走）"))
        if elapsed_s is not None:
''',
'''                            if p56 else "（不补走）"))
        if plan_elapsed_s is not None:
            lines.append("规划回程已用时（P7/P8 拿宝前）= %d s（%s）⇒ 补走 7/8 的时间判据用这个时刻"
                         % (plan_elapsed_s, M.mmss(plan_elapsed_s)))
        if elapsed_s is not None:
''', 1))

# 8) _clue_route_sections 签名
E_ME.append(('''    def _clue_route_sections(self, stage, clue, ab, doors, treasure, mode="full",
                             punch=False, tour=False, elapsed_s=None, p56=None):
''',
'''    def _clue_route_sections(self, stage, clue, ab, doors, treasure, mode="full",
                             punch=False, tour=False, elapsed_s=None, p56=None,
                             plan_elapsed_s=None):
''', 1))

# 9) _clue_route_sections：_input_section 调用带 plan 时刻
E_ME.append(('''        sections = [self._input_section(stage, clue, ab, doors, treasure, punch, tour,
                                        elapsed_s=elapsed_s, p56=p56)]
''',
'''        sections = [self._input_section(stage, clue, ab, doors, treasure, punch, tour,
                                        elapsed_s=elapsed_s, p56=p56,
                                        plan_elapsed_s=plan_elapsed_s)]
''', 1))

E_G = []

# g1) _cfg_want 加 plan_elapsed
E_G.append(('''        "p56": "强制关",
        "elapsed": "不启用时间裁剪",
''',
'''        "p56": "强制关",
        "plan_elapsed": "不启用时间裁剪",
        "elapsed": "不启用时间裁剪",
''', 1))

# g2) _expect 插 plan_elapsed（13 个下拉）
E_G.append(('''    _expect = ([_cfg_want["stage"], _cfg_want["p1clue"], _cfg_want["stg"]]
               + _cfg_want["doors"]
               + [_cfg_want["treasure"], _cfg_want["punch"], _cfg_want["tour"],
                  _cfg_want["p56"], _cfg_want["elapsed"]])
''',
'''    _expect = ([_cfg_want["stage"], _cfg_want["p1clue"], _cfg_want["stg"]]
               + _cfg_want["doors"]
               + [_cfg_want["treasure"], _cfg_want["punch"], _cfg_want["tour"],
                  _cfg_want["p56"], _cfg_want["plan_elapsed"], _cfg_want["elapsed"]])
''', 1))

# g3) 非法配置回退：12 -> 13，plan_elapsed 在 [9]，punch/tour 平移到 [10]/[11]
E_G.append(('''    check(len(_vals2) == 12 and _vals2[0].startswith("第一轮·完整路线")
          and all(v in _legal_doors for v in _vals2[3:7])
          and _vals2[8].startswith("跟随 config.h（当前：") and _vals2[9].startswith("跟随 config.h（当前：")
          and _vals2[10].startswith("跟随 config.h（当前：")
          and _vals2[11] == "不启用时间裁剪",
''',
'''    check(len(_vals2) == 13 and _vals2[0].startswith("第一轮·完整路线")
          and all(v in _legal_doors for v in _vals2[3:7])
          and _vals2[8].startswith("跟随 config.h（当前：")
          and _vals2[9] == "不启用时间裁剪"
          and _vals2[10].startswith("跟随 config.h（当前：") and _vals2[11].startswith("跟随 config.h（当前：")
          and _vals2[12] == "不启用时间裁剪",
''', 1))

# g4) punch/tour 标签索引 9/10 -> 10/11
E_G.append(('''    check(_vals2[9] == app._switch_vals("P3P4_PUNCH_ENABLE")[0]
          and _vals2[10] == app._switch_vals("UPRIGHT_TOUR_ENABLE")[0],
          "开关下拉的「跟随 config.h」直接写出当前值（%s ｜ %s）"
          % (_vals2[9], _vals2[10]))
''',
'''    check(_vals2[10] == app._switch_vals("P3P4_PUNCH_ENABLE")[0]
          and _vals2[11] == app._switch_vals("UPRIGHT_TOUR_ENABLE")[0],
          "开关下拉的「跟随 config.h」直接写出当前值（%s ｜ %s）"
          % (_vals2[10], _vals2[11]))
''', 1))

for path, edits, tag in ((ME, E_ME, "map_editor"), (G, E_G, "guismoke")):
    eol = probe(path)
    data = path.read_bytes().decode("utf-8")
    for i, (old, new, want) in enumerate(edits):
        o = old.replace("\n", eol); n = new.replace("\n", eol)
        cnt = data.count(o)
        assert cnt == want, "%s edit#%d 命中 %d 次（应为 %d）:\n%s" % (tag, i, cnt, want, old[:100])
        data = data.replace(o, n)
    path.write_bytes(data.encode("utf-8"))
    print("[WROTE] %s：%d 组替换 (eol=%r)" % (path.name, len(edits), eol))
print("ALL DONE")
