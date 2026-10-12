# -*- coding: utf-8 -*-
"""AI 过程脚本（第 2 步）：map_editor.py 侧 —— 「线索路线…」对话框加"回程补打卡 P3/P4" + 透传。"""
import os

ME = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机", "map_editor")
EDITOR = os.path.join(ME, "map_editor.py")
EDITS = []


def rep(old, new):
    EDITS.append((old, new))


# 1) _punch_on()
rep('    def _macro_value(self, name):\n'
    '        """求 Mission/config.h 里的宏（按当前 USE_FIELD 展开）。求不出来返回 None。"""\n'
    '        try:\n'
    '            return M.eval_c_expr(name, self.model.macros)\n'
    '        except Exception:                                        # noqa: BLE001\n'
    '            return None\n'
    '\n',
    '    def _macro_value(self, name):\n'
    '        """求 Mission/config.h 里的宏（按当前 USE_FIELD 展开）。求不出来返回 None。"""\n'
    '        try:\n'
    '            return M.eval_c_expr(name, self.model.macros)\n'
    '        except Exception:                                        # noqa: BLE001\n'
    '            return None\n'
    '\n'
    '    def _punch_on(self, choice):\n'
    '        """「回程补打卡 P3/P4」下拉 → bool。\n'
    '\n'
    '        「跟随 config.h」= **直读** `Mission/config.h` 的 `P3P4_PUNCH_ENABLE`（不用 model.macros ——\n'
    '        那是布局里的宏快照，载入旧布局时会把这个开关恒钉在旧值上）；另两档是临时试算用。\n'
    '        """\n'
    '        if choice == "强制开":\n'
    '            return True\n'
    '        if choice == "强制关":\n'
    '            return False\n'
    '        try:\n'
    '            return bool(M.eval_c_expr("P3P4_PUNCH_ENABLE", M.parse_config_macros()))\n'
    '        except Exception:                                        # noqa: BLE001\n'
    '            return False\n'
    '\n')

# 2) _append_after_door 签名
rep('    def _append_after_door(self, sections, enter, ab, doors, treasure, mode):\n'
    '        """过门之后：stageAB（平台 A/B）+ 宝物回程。返回可上画布的 path（或 None）。"""\n',
    '    def _append_after_door(self, sections, enter, ab, doors, treasure, mode,\n'
    '                           clue=None, punch=False):\n'
    '        """过门之后：stageAB（平台 A/B）+ 宝物回程。返回可上画布的 path（或 None）。\n'
    '\n'
    '        clue = P1 线索（QR 百位）、punch = P3P4_PUNCH_ENABLE，透传给宝物回程。\n'
    '        """\n')

# 3) _append_after_door 内的 treasure_return 调用
rep('        doors_eff, _read, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure)\n',
    '        doors_eff, _read, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,\n'
    '                                                clue, punch)\n')

# 4) 两处 _append_after_door 调用点
rep('            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode) or []\n'
    '\n'
    '        elif stage.startswith("第一轮·过门"):\n',
    '            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode,\n'
    '                                             clue, punch) or []\n'
    '\n'
    '        elif stage.startswith("第一轮·过门"):\n')

rep('            sections.append(("门区读灯推进（door()，路线写在门里）", trace))\n'
    '            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode) or []\n',
    '            sections.append(("门区读灯推进（door()，路线写在门里）", trace))\n'
    '            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode,\n'
    '                                             clue, punch) or []\n')

# 5) _input_section
rep('    def _input_section(self, stage, clue, ab, doors, treasure):\n'
    '        """报告头：把这次的输入原样回显（免得以后分不清这份报告是哪套灯算的）。"""\n',
    '    def _input_section(self, stage, clue, ab, doors, treasure, punch=None):\n'
    '        """报告头：把这次的输入原样回显（免得以后分不清这份报告是哪套灯算的）。"""\n')

rep('        return ("本次输入（这份报告按这套算）",\n'
    '                ["阶段：%s" % stage,\n'
    '                 "P1 线索 = %s ｜ 平台 A/B = P%d/P%d ｜ 宝物 = %s"\n'
    '                 % (clue_txt, ab[0], ab[1],\n'
    '                    "未定" if treasure is None else "P%d" % treasure),\n'
    '                 "门灯：%s（绿=能过 / 蓝=单相 / 黑=不能过）" % lights])\n',
    '        lines = ["阶段：%s" % stage,\n'
    '                 "P1 线索 = %s ｜ 平台 A/B = P%d/P%d ｜ 宝物 = %s"\n'
    '                 % (clue_txt, ab[0], ab[1],\n'
    '                    "未定" if treasure is None else "P%d" % treasure),\n'
    '                 "门灯：%s（绿=能过 / 蓝=单相 / 黑=不能过）" % lights]\n'
    '        if punch is not None:\n'
    '            lines.append("回程补打卡 P3/P4（P3P4_PUNCH_ENABLE）= %s%s"\n'
    '                         % ("开" if punch else "关",\n'
    '                            "；缺哪个补哪个（百位 3 补 P4 / 4 补 P3 / 0 两个都补）"\n'
    '                            if punch else "（回程只去宝物平台）"))\n'
    '        return ("本次输入（这份报告按这套算）", lines)\n')

# 6) _clue_route_sections
rep('    def _clue_route_sections(self, stage, clue, ab, doors, treasure, mode="full"):\n',
    '    def _clue_route_sections(self, stage, clue, ab, doors, treasure, mode="full",\n'
    '                             punch=False):\n')

rep('              treasure=宝物编号或 None。\n'
    '        返回 (sections, canvas_path, err)：sections=[(标题, 行列表)]；err=(标题, 说明) 或 None。\n'
    '        第一段固定是「本次输入」回显，方便对上报告是哪套灯算的。\n'
    '        """\n'
    '        sections = [self._input_section(stage, clue, ab, doors, treasure)]\n',
    '              treasure=宝物编号或 None；punch=P3P4_PUNCH_ENABLE（一轮回程补打卡 P3/P4）。\n'
    '        返回 (sections, canvas_path, err)：sections=[(标题, 行列表)]；err=(标题, 说明) 或 None。\n'
    '        第一段固定是「本次输入」回显，方便对上报告是哪套灯算的。\n'
    '        """\n'
    '        sections = [self._input_section(stage, clue, ab, doors, treasure, punch)]\n')

rep('            sub, flat, split, err = self._round1_complete(clue, ab, doors, treasure, mode)\n',
    '            sub, flat, split, err = self._round1_complete(clue, ab, doors, treasure, mode,\n'
    '                                                          punch)\n')

# 7) _round1_complete
rep('    def _round1_complete(self, clue, ab, doors, treasure, mode="full"):\n',
    '    def _round1_complete(self, clue, ab, doors, treasure, mode="full", punch=False):\n')

rep('        doors_eff, read_entry, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure)\n',
    '        doors_eff, read_entry, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,\n'
    '                                                clue, punch)\n')

rep('            wp3, blocked = M.door_return_home_waypoints(start, treasure, allow)\n',
    '            wp3, blocked = M.door_return_home_waypoints(start, treasure, allow,\n'
    '                                                        clue, punch)\n')

# 8) 门区回程分支
rep('            wp, blocked = M.door_return_home_waypoints(start, treasure, allow)\n',
    '            wp, blocked = M.door_return_home_waypoints(start, treasure, allow,\n'
    '                                                       clue, punch)\n')

# 9) 对话框 PUNCH_VALS（用 light_vals 那行做唯一锚点）
rep('        TREASURE_VALS = ["未定", "2 · P1", "3 · P3", "4 · P4", "5 · P5", "6 · P6"]\n'
    '        light_vals = [M.DOOR_STATE_NAME[s] for s in M.DOOR_STATE_ORDER]\n',
    '        TREASURE_VALS = ["未定", "2 · P1", "3 · P3", "4 · P4", "5 · P5", "6 · P6"]\n'
    '        PUNCH_VALS = ["跟随 config.h", "强制开", "强制关"]\n'
    '        light_vals = [M.DOOR_STATE_NAME[s] for s in M.DOOR_STATE_ORDER]\n')

# 10) 对话框控件 + 提示行下移
rep('        treasure = combo(5, "宝物线索", TREASURE_VALS,\n'
    '                         _pick("treasure", TREASURE_VALS, TREASURE_VALS[0]))\n'
    '        ttk.Label(frm, text="（回程走哪个门区入口不用选：由上面 4 格门灯自动推；"\n'
    '                            "这些选择会记住，随「保存布局」一起存，重启也在）",\n'
    '                  foreground="#666666").grid(row=6, column=0, columnspan=2,\n'
    '                                             sticky="w", pady=(6, 0))\n',
    '        treasure = combo(5, "宝物线索", TREASURE_VALS,\n'
    '                         _pick("treasure", TREASURE_VALS, TREASURE_VALS[0]))\n'
    '        punch_sel = combo(6, "回程补打卡 P3/P4", PUNCH_VALS,\n'
    '                          _pick("punch", PUNCH_VALS, PUNCH_VALS[0]))\n'
    '        ttk.Label(frm, text="（回程走哪个门区入口不用选：由上面 4 格门灯自动推；"\n'
    '                            "补打卡 = P3P4_PUNCH_ENABLE，缺哪个补哪个；"\n'
    '                            "这些选择会记住，随「保存布局」一起存，重启也在）",\n'
    '                  foreground="#666666").grid(row=7, column=0, columnspan=2,\n'
    '                                             sticky="w", pady=(6, 0))\n')

# 11) run()
rep('            # 记住这次的选择（下次打开就是这套；也会随「保存布局」写进 constraints）\n'
    '            self.clue_route_cfg = {\n'
    '                "stage": stage.get(),\n'
    '                "p1clue": p1clue.get(),\n'
    '                "stg": stg.get(),\n'
    '                "doors": [light_vars[i].get() for i in range(4)],\n'
    '                "treasure": tsel,\n'
    '            }\n'
    '            sections, canvas, err = self._clue_route_sections(\n'
    '                stage.get(), clue, ab, doors, tval, self.cost_mode.get())\n',
    '            punch = self._punch_on(punch_sel.get())\n'
    '            # 记住这次的选择（下次打开就是这套；也会随「保存布局」写进 constraints）\n'
    '            self.clue_route_cfg = {\n'
    '                "stage": stage.get(),\n'
    '                "p1clue": p1clue.get(),\n'
    '                "stg": stg.get(),\n'
    '                "doors": [light_vars[i].get() for i in range(4)],\n'
    '                "treasure": tsel,\n'
    '                "punch": punch_sel.get(),\n'
    '            }\n'
    '            sections, canvas, err = self._clue_route_sections(\n'
    '                stage.get(), clue, ab, doors, tval, self.cost_mode.get(), punch)\n')


def main():
    with open(EDITOR, "rb") as f:
        data = f.read()
    eol = "\r\n" if data.count(b"\r\n") else "\n"
    for old, new in EDITS:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "命中 %d 次（期望 1）:\n%r" % (cnt, old[:80])
        data = data.replace(ob, nb)
    with open(EDITOR, "wb") as f:
        f.write(data)
    crlf, lf = data.count(b"\r\n"), data.count(b"\n") - data.count(b"\r\n")
    print("[ok] map_editor.py +%d 处改动, eol=%s crlf=%d lf=%d"
          % (len(EDITS), eol.strip() or "LF", crlf, lf))


if __name__ == "__main__":
    main()
