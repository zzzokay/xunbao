# -*- coding: utf-8 -*-
"""AI 过程脚本：上位机镜像固件新增的 `P3P4_PUNCH_ENABLE`（一轮回程补打卡 P3/P4）。

- map_model.py（LF）：新增纯函数 p3p4_punch_waypoints()；treasure_return_waypoints 与
  door_return_home_waypoints 各加 line_clue / punch 参数（默认关 ⇒ 老调用点行为不变）。
- map_editor.py（LF）：「线索路线…」对话框加「回程补打卡 P3/P4」下拉（跟随 config.h / 强制开 / 强制关），
  并把 punch 透传到 _clue_route_sections / _round1_complete / _append_after_door。
每个替换 assert 命中恰好 1 次，全部成功才写盘。
"""
import os

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao\ME"  # 占位，见下
ME = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机", "map_editor")
MODEL = os.path.join(ME, "map_model.py")
EDITOR = os.path.join(ME, "map_editor.py")

EDITS = {MODEL: [], EDITOR: []}


def rep(path, old, new):
    EDITS[path].append((old, new))


# ================================================================ map_model.py
rep(MODEL,
    'def treasure_return_waypoints(start, doors, treasure):\n'
    '    """镜像 plan_treasure_return()：在 P7/P8 读到宝物编号后的回程 wp。"""\n',
    'def p3p4_punch_waypoints(treasure, line_clue):\n'
    '    """镜像 mission_planner.c 的 `P3P4_PUNCH_ENABLE` 段：一轮回程要"补打卡"的平台。\n'
    '\n'
    '    **缺哪个补哪个**：QR 百位 = 3 ⇒ 去程已去过 P3、= 4 ⇒ 已去过 P4、\n'
    '    0 / None ⇒ 两个都没去；宝物平台正好是它时也不重复加（回程本来就要去那儿打卡）。\n'
    '    顺序固定 P3 -> P4。返回平台名列表（可能为空）。\n'
    '    """\n'
    '    out = []\n'
    '    if line_clue != 3 and treasure != 3:\n'
    '        out.append("P3")\n'
    '    if line_clue != 4 and treasure != 4:\n'
    '        out.append("P4")\n'
    '    return out\n'
    '\n'
    '\n'
    'def treasure_return_waypoints(start, doors, treasure, line_clue=None, punch=False):\n'
    '    """镜像 plan_treasure_return()：在 P7/P8 读到宝物编号后的回程 wp。\n'
    '\n'
    '    punch=True 时按 P3P4_PUNCH_ENABLE 追加"补打卡"平台（见 p3p4_punch_waypoints()），\n'
    '    位置 = 宝物平台之后、S1/S2 之前；line_clue = QR 百位（0/3/4/None）。\n'
    '    """\n')

rep(MODEL,
    '    if treasure not in (5, 6):\n'
    '        wp.append(TREASURE_PF[treasure])\n'
    '    wp.append("P2")\n'
    '    return wp, None\n',
    '    if treasure not in (5, 6):\n'
    '        wp.append(TREASURE_PF[treasure])\n'
    '    if punch:\n'
    '        wp += p3p4_punch_waypoints(treasure, line_clue)\n'
    '    wp.append("P2")\n'
    '    return wp, None\n')

rep(MODEL,
    'def door_return_home_waypoints(start, treasure, allow_N8_N3=False):\n'
    '    """镜像 mission_planner.c:route_return_home()：门区 8 条边全禁 + wp={当前节点,[宝物平台],P2}。\n'
    '\n'
    '    返回 (wp, blocked)，blocked 是规划时需封闭的 (from,to) 集合。\n'
    '    allow_N8_N3=True 对应 door_2（D5 黑且 D3 蓝已用尽）额外放行 N8→N3，退回去重读 D4。\n'
    '    """\n'
    '    wp = [start]\n'
    '    if treasure in (2, 3, 4):\n'
    '        wp.append(TREASURE_PF[treasure])\n'
    '    wp.append("P2")\n',
    'def door_return_home_waypoints(start, treasure, allow_N8_N3=False,\n'
    '                               line_clue=None, punch=False):\n'
    '    """镜像 mission_planner.c:route_return_home()：门区 8 条边全禁 + wp={当前节点,[宝物平台],P2}。\n'
    '\n'
    '    返回 (wp, blocked)，blocked 是规划时需封闭的 (from,to) 集合。\n'
    '    allow_N8_N3=True 对应 door_2（D5 黑且 D3 蓝已用尽）额外放行 N8→N3，退回去重读 D4。\n'
    '    punch=True 时按 P3P4_PUNCH_ENABLE 追加"补打卡"平台（见 p3p4_punch_waypoints()），\n'
    '    位置 = 宝物平台之后、S1/S2 之前；line_clue = QR 百位（0/3/4/None）。\n'
    '    """\n'
    '    wp = [start]\n'
    '    if treasure in (2, 3, 4):\n'
    '        wp.append(TREASURE_PF[treasure])\n'
    '    if punch:\n'
    '        wp += p3p4_punch_waypoints(treasure, line_clue)\n'
    '    wp.append("P2")\n')

# ================================================================ map_editor.py
# 1) _punch_on()：放在 _macro_value 之后
rep(EDITOR,
    '    def _macro_value(self, name):\n'
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
rep(EDITOR,
    '    def _append_after_door(self, sections, enter, ab, doors, treasure, mode):\n'
    '        """过门之后：stageAB（平台 A/B）+ 宝物回程。返回可上画布的 path（或 None）。"""\n',
    '    def _append_after_door(self, sections, enter, ab, doors, treasure, mode,\n'
    '                           clue=None, punch=False):\n'
    '        """过门之后：stageAB（平台 A/B）+ 宝物回程。返回可上画布的 path（或 None）。\n'
    '\n'
    '        clue = P1 线索（QR 百位）、punch = P3P4_PUNCH_ENABLE，透传给宝物回程。\n'
    '        """\n')

# 3) _append_after_door 里的 treasure_return 调用
rep(EDITOR,
    '        doors_eff, _read, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure)\n',
    '        doors_eff, _read, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,\n'
    '                                                clue, punch)\n')

# 4) 两处 _append_after_door 调用点
rep(EDITOR,
    '            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode) or []\n'
    '\n'
    '        elif stage.startswith("第一轮·过门"):\n',
    '            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode,\n'
    '                                             clue, punch) or []\n'
    '\n'
    '        elif stage.startswith("第一轮·过门"):\n')

rep(EDITOR,
    '            sections.append(("门区读灯推进（door()，路线写在门里）", trace))\n'
    '            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode) or []\n',
    '            sections.append(("门区读灯推进（door()，路线写在门里）", trace))\n'
    '            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode,\n'
    '                                             clue, punch) or []\n')

# 5) _input_section 加 punch 回显
rep(EDITOR,
    '    def _input_section(self, stage, clue, ab, doors, treasure):\n'
    '        """报告头：把这次的输入原样回显（免得以后分不清这份报告是哪套灯算的）。"""\n',
    '    def _input_section(self, stage, clue, ab, doors, treasure, punch=None):\n'
    '        """报告头：把这次的输入原样回显（免得以后分不清这份报告是哪套灯算的）。"""\n')

rep(EDITOR,
    '        return ("本次输入（这份报告按这套算）",\n'
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

# 6) _clue_route_sections 签名 + 透传
rep(EDITOR,
    '    def _clue_route_sections(self, stage, clue, ab, doors, treasure, mode="full"):\n',
    '    def _clue_route_sections(self, stage, clue, ab, doors, treasure, mode="full",\n'
    '                             punch=False):\n')

rep(EDITOR,
    '              treasure=宝物编号或 None。\n'
    '        返回 (sections, canvas_path, err)：sections=[(标题, 行列表)]；err=(标题, 说明) 或 None。\n'
    '        第一段固定是「本次输入」回显，方便对上报告是哪套灯算的。\n'
    '        """\n'
    '        sections = [self._input_section(stage, clue, ab, doors, treasure)]\n',
    '              treasure=宝物编号或 None；punch=P3P4_PUNCH_ENABLE（一轮回程补打卡 P3/P4）。\n'
    '        返回 (sections, canvas_path, err)：sections=[(标题, 行列表)]；err=(标题, 说明) 或 None。\n'
    '        第一段固定是「本次输入」回显，方便对上报告是哪套灯算的。\n'
    '        """\n'
    '        sections = [self._input_section(stage, clue, ab, doors, treasure, punch)]\n')

rep(EDITOR,
    '            sub, flat, split, err = self._round1_complete(clue, ab, doors, treasure, mode)\n',
    '            sub, flat, split, err = self._round1_complete(clue, ab, doors, treasure, mode,\n'
    '                                                          punch)\n')

# 7) _round1_complete 签名 + 两处调用
rep(EDITOR,
    '    def _round1_complete(self, clue, ab, doors, treasure, mode="full"):\n',
    '    def _round1_complete(self, clue, ab, doors, treasure, mode="full", punch=False):\n')

rep(EDITOR,
    '        doors_eff, read_entry, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure)\n',
    '        doors_eff, read_entry, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,\n'
    '                                                clue, punch)\n')

rep(EDITOR,
    '            wp3, blocked = M.door_return_home_waypoints(start, treasure, allow)\n',
    '            wp3, blocked = M.door_return_home_waypoints(start, treasure, allow,\n'
    '                                                        clue, punch)\n')

# 8) 门区回程分支（_clue_route_sections 内）
rep(EDITOR,
    '            wp, blocked = M.door_return_home_waypoints(start, treasure, allow)\n',
    '            wp, blocked = M.door_return_home_waypoints(start, treasure, allow,\n'
    '                                                       clue, punch)\n')

# 9) 对话框：PUNCH_VALS
rep(EDITOR,
    '        TREASURE_VALS = ["未定", "2 · P1", "3 · P3", "4 · P4", "5 · P5", "6 · P6"]\n',
    '        TREASURE_VALS = ["未定", "2 · P1", "3 · P3", "4 · P4", "5 · P5", "6 · P6"]\n'
    '        PUNCH_VALS = ["跟随 config.h", "强制开", "强制关"]\n')

# 10) 对话框：加下拉 + 提示行下移一行
rep(EDITOR,
    '        treasure = combo(5, "宝物线索", TREASURE_VALS,\n'
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

# 11) 对话框 run()：算 punch、写进 cfg、透传
rep(EDITOR,
    '            # 记住这次的选择（下次打开就是这套；也会随「保存布局」写进 constraints）\n'
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
    for path, edits in EDITS.items():
        with open(path, "rb") as f:
            data = f.read()
        # 先探测该文件当前行尾（.py 在本机已被编辑器养成 CRLF；不要去改它）
        eol = "\r\n" if data.count(b"\r\n") else "\n"
        for old, new in edits:
            ob = old.replace("\n", eol).encode("utf-8")
            nb = new.replace("\n", eol).encode("utf-8")
            cnt = data.count(ob)
            assert cnt == 1, "%s 命中 %d 次（期望 1）:\n%r" % (os.path.basename(path), cnt,
                                                              old[:80])
            data = data.replace(ob, nb)
        crlf, lf = data.count(b"\r\n"), data.count(b"\n") - data.count(b"\r\n")
        assert (lf == 0) if eol == "\r\n" else (crlf == 0), "行尾被搞混了"
        with open(path, "wb") as f:
            f.write(data)
        print("[ok] %-16s +%d 处改动, eol=%s crlf=%d lf=%d"
              % (os.path.basename(path), len(edits), eol.strip() or "LF", crlf, lf))


if __name__ == "__main__":
    main()
