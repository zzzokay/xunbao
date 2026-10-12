# -*- coding: utf-8 -*-
"""AI 过程脚本 第 2 步：map_editor.py —— 两个对话框加「直立景点巡回 S1/S2」并透传。"""
import os

ME = os.path.join(r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao", "地图修改上位机", "map_editor")
E = os.path.join(ME, "map_editor.py")
EDITS = []


def rep(old, new):
    EDITS.append((old, new))


# ---------------------------------------------------------------- 1) _switch_on 泛化
rep('    def _punch_on(self, choice):\n'
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
    '            return False\n',
    '    def _switch_on(self, macro, choice):\n'
    '        """「跟随 config.h / 强制开 / 强制关」下拉 → bool。\n'
    '\n'
    '        「跟随 config.h」= **直读** `Mission/config.h` 里的该宏（不用 `model.macros` ——\n'
    '        那是布局里的宏快照，载入旧布局时会把这个开关恒钉在旧值上）；另两档是临时试算用。\n'
    '        """\n'
    '        if choice == "强制开":\n'
    '            return True\n'
    '        if choice == "强制关":\n'
    '            return False\n'
    '        try:\n'
    '            return bool(M.eval_c_expr(macro, M.parse_config_macros()))\n'
    '        except Exception:                                        # noqa: BLE001\n'
    '            return False\n'
    '\n'
    '    def _punch_on(self, choice):\n'
    '        """「回程补打卡 P3/P4」下拉 → bool（`P3P4_PUNCH_ENABLE`）。"""\n'
    '        return self._switch_on("P3P4_PUNCH_ENABLE", choice)\n'
    '\n'
    '    def _tour_on(self, choice):\n'
    '        """「直立景点巡回 S1/S2」下拉 → bool（`UPRIGHT_TOUR_ENABLE`）。"""\n'
    '        return self._switch_on("UPRIGHT_TOUR_ENABLE", choice)\n')

# ---------------------------------------------------------------- 2) _input_section
rep('    def _input_section(self, stage, clue, ab, doors, treasure, punch=None):\n',
    '    def _input_section(self, stage, clue, ab, doors, treasure, punch=None, tour=None):\n')

rep('        if punch is not None:\n'
    '            lines.append("回程补打卡 P3/P4（P3P4_PUNCH_ENABLE）= %s%s"\n'
    '                         % ("开" if punch else "关",\n'
    '                            "；缺哪个补哪个（百位 3 补 P4 / 4 补 P3 / 0 两个都补）"\n'
    '                            if punch else "（回程只去宝物平台）"))\n'
    '        return ("本次输入（这份报告按这套算）", lines)\n',
    '        if punch is not None:\n'
    '            lines.append("回程补打卡 P3/P4（P3P4_PUNCH_ENABLE）= %s%s"\n'
    '                         % ("开" if punch else "关",\n'
    '                            "；缺哪个补哪个（百位 3 补 P4 / 4 补 P3 / 0 两个都补）"\n'
    '                            if punch else "（回程只去宝物平台）"))\n'
    '        if tour is not None:\n'
    '            lines.append("直立景点巡回 S1/S2（UPRIGHT_TOUR_ENABLE）= %s%s"\n'
    '                         % ("开" if tour else "关",\n'
    '                            "；一轮宝物 P3→S1、P4→S2；二轮 P3 后绕 S1、P4 后绕 S2"\n'
    '                            if tour else "（不进 S1/S2）"))\n'
    '        return ("本次输入（这份报告按这套算）", lines)\n')

# ---------------------------------------------------------------- 3) _clue_route_sections
rep('    def _clue_route_sections(self, stage, clue, ab, doors, treasure, mode="full",\n'
    '                             punch=False):\n',
    '    def _clue_route_sections(self, stage, clue, ab, doors, treasure, mode="full",\n'
    '                             punch=False, tour=False):\n')

rep('              treasure=宝物编号或 None；punch=P3P4_PUNCH_ENABLE（一轮回程补打卡 P3/P4）。\n',
    '              treasure=宝物编号或 None；punch=P3P4_PUNCH_ENABLE（一轮回程补打卡 P3/P4）；\n'
    '              tour=UPRIGHT_TOUR_ENABLE（直立景点巡回 S1/S2）。\n')

rep('        sections = [self._input_section(stage, clue, ab, doors, treasure, punch)]\n',
    '        sections = [self._input_section(stage, clue, ab, doors, treasure, punch, tour)]\n')

rep('            sub, flat, split, err = self._round1_complete(clue, ab, doors, treasure, mode,\n'
    '                                                          punch)\n',
    '            sub, flat, split, err = self._round1_complete(clue, ab, doors, treasure, mode,\n'
    '                                                          punch, tour)\n')

# ---------------------------------------------------------------- 4) _append_after_door
rep('    def _append_after_door(self, sections, enter, ab, doors, treasure, mode,\n'
    '                           clue=None, punch=False):\n'
    '        """过门之后：stageAB（平台 A/B）+ 宝物回程。返回可上画布的 path（或 None）。\n'
    '\n'
    '        clue = P1 线索（QR 百位）、punch = P3P4_PUNCH_ENABLE，透传给宝物回程。\n'
    '        """\n',
    '    def _append_after_door(self, sections, enter, ab, doors, treasure, mode,\n'
    '                           clue=None, punch=False, tour=False):\n'
    '        """过门之后：stageAB（平台 A/B）+ 宝物回程。返回可上画布的 path（或 None）。\n'
    '\n'
    '        clue = P1 线索（QR 百位）、punch = P3P4_PUNCH_ENABLE、tour = UPRIGHT_TOUR_ENABLE，\n'
    '        都透传给宝物回程。\n'
    '        """\n')

rep('        doors_eff, _read, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,\n'
    '                                                clue, punch)\n',
    '        doors_eff, _read, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,\n'
    '                                                clue, punch, tour)\n')

rep('            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode,\n'
    '                                             clue, punch) or []\n'
    '\n'
    '        elif stage.startswith("第一轮·过门"):\n',
    '            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode,\n'
    '                                             clue, punch, tour) or []\n'
    '\n'
    '        elif stage.startswith("第一轮·过门"):\n')

rep('            sections.append(("门区读灯推进（door()，路线写在门里）", trace))\n'
    '            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode,\n'
    '                                             clue, punch) or []\n',
    '            sections.append(("门区读灯推进（door()，路线写在门里）", trace))\n'
    '            canvas = self._append_after_door(sections, enter, ab, doors, treasure, mode,\n'
    '                                             clue, punch, tour) or []\n')

# ---------------------------------------------------------------- 5) _round1_complete
rep('    def _round1_complete(self, clue, ab, doors, treasure, mode="full", punch=False):\n',
    '    def _round1_complete(self, clue, ab, doors, treasure, mode="full", punch=False,\n'
    '                         tour=False):\n')

rep('        doors_eff, read_entry, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,\n'
    '                                                clue, punch)\n',
    '        doors_eff, read_entry, warn_doors = self._doors_after_entry_read(doors)\n'
    '        wp2, why2 = M.treasure_return_waypoints("P%d" % b, doors_eff, treasure,\n'
    '                                                clue, punch, tour)\n')

rep('            wp3, blocked = M.door_return_home_waypoints(start, treasure, allow,\n'
    '                                                        clue, punch)\n',
    '            wp3, blocked = M.door_return_home_waypoints(start, treasure, allow,\n'
    '                                                        clue, punch, tour)\n')

# ---------------------------------------------------------------- 6) 门区回程分支
rep('            wp, blocked = M.door_return_home_waypoints(start, treasure, allow,\n'
    '                                                       clue, punch)\n',
    '            wp, blocked = M.door_return_home_waypoints(start, treasure, allow,\n'
    '                                                       clue, punch, tour)\n')

# ---------------------------------------------------------------- 7) 第二轮分支（线索对话框）
rep('            wp, why = M.round2_waypoints(doors, treasure if treasure is not None else 0)\n',
    '            wp, why = M.round2_waypoints(doors, treasure if treasure is not None else 0,\n'
    '                                        None, None, tour)\n')

# ---------------------------------------------------------------- 8) _round2_route_sections
rep('    def _round2_route_sections(self, doors, treasure, cruise=None, mode="full", fw_cfg=None):\n',
    '    def _round2_route_sections(self, doors, treasure, cruise=None, mode="full", fw_cfg=None,\n'
    '                               tour=False):\n')

rep('        wp, why = M.round2_waypoints(doors, t, order)\n',
    '        wp, why = M.round2_waypoints(doors, t, order, None, tour)\n')

rep('        fw_cfg = 固件 config.h 的两组顺序（`M.parse_round2_cruise()`；None = 用 self.model.round2）。\n',
    '        fw_cfg = 固件 config.h 的两组顺序（`M.parse_round2_cruise()`；None = 用 self.model.round2）。\n'
    '        tour = UPRIGHT_TOUR_ENABLE（在 P3 后插 S1、P4 后插 S2）。\n')

# ---------------------------------------------------------------- 9) 线索对话框：TOUR_VALS + 控件
rep('        PUNCH_VALS = ["跟随 config.h", "强制开", "强制关"]\n'
    '        light_vals = [M.DOOR_STATE_NAME[s] for s in M.DOOR_STATE_ORDER]\n',
    '        PUNCH_VALS = ["跟随 config.h", "强制开", "强制关"]\n'
    '        TOUR_VALS = ["跟随 config.h", "强制开", "强制关"]\n'
    '        light_vals = [M.DOOR_STATE_NAME[s] for s in M.DOOR_STATE_ORDER]\n')

rep('        punch_sel = combo(6, "回程补打卡 P3/P4", PUNCH_VALS,\n'
    '                          _pick("punch", PUNCH_VALS, PUNCH_VALS[0]))\n'
    '        ttk.Label(frm, text="（回程走哪个门区入口不用选：由上面 4 格门灯自动推；"\n'
    '                            "补打卡 = P3P4_PUNCH_ENABLE，缺哪个补哪个；"\n'
    '                            "这些选择会记住，随「保存布局」一起存，重启也在）",\n'
    '                  foreground="#666666").grid(row=7, column=0, columnspan=2,\n'
    '                                             sticky="w", pady=(6, 0))\n',
    '        punch_sel = combo(6, "回程补打卡 P3/P4", PUNCH_VALS,\n'
    '                          _pick("punch", PUNCH_VALS, PUNCH_VALS[0]))\n'
    '        tour_sel = combo(7, "直立景点巡回 S1/S2", TOUR_VALS,\n'
    '                         _pick("tour", TOUR_VALS, TOUR_VALS[0]))\n'
    '        ttk.Label(frm, text="（回程走哪个门区入口不用选：由上面 4 格门灯自动推；"\n'
    '                            "补打卡 = P3P4_PUNCH_ENABLE（缺哪个补哪个）；"\n'
    '                            "巡回 = UPRIGHT_TOUR_ENABLE（一轮宝物 P3→S1/P4→S2，二轮两个都绕）；"\n'
    '                            "这些选择会记住，随「保存布局」一起存，重启也在）",\n'
    '                  foreground="#666666").grid(row=8, column=0, columnspan=2,\n'
    '                                             sticky="w", pady=(6, 0))\n')

rep('        buttons = ttk.Frame(frm)\n'
    '        buttons.grid(row=8, column=0, columnspan=2, sticky="w", pady=(14, 0))\n',
    '        buttons = ttk.Frame(frm)\n'
    '        buttons.grid(row=9, column=0, columnspan=2, sticky="w", pady=(14, 0))\n')

rep('        dlg.title("线索 / 门灯 / 宝物 → 显示固件会跑的路线")\n'
    '        dlg.geometry("660x430")\n',
    '        dlg.title("线索 / 门灯 / 宝物 → 显示固件会跑的路线")\n'
    '        dlg.geometry("660x490")\n')

# ---------------------------------------------------------------- 10) 线索对话框 run()
rep('            punch = self._punch_on(punch_sel.get())\n'
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
    '                stage.get(), clue, ab, doors, tval, self.cost_mode.get(), punch)\n',
    '            punch = self._punch_on(punch_sel.get())\n'
    '            tour = self._tour_on(tour_sel.get())\n'
    '            # 记住这次的选择（下次打开就是这套；也会随「保存布局」写进 constraints）\n'
    '            self.clue_route_cfg = {\n'
    '                "stage": stage.get(),\n'
    '                "p1clue": p1clue.get(),\n'
    '                "stg": stg.get(),\n'
    '                "doors": [light_vars[i].get() for i in range(4)],\n'
    '                "treasure": tsel,\n'
    '                "punch": punch_sel.get(),\n'
    '                "tour": tour_sel.get(),\n'
    '            }\n'
    '            sections, canvas, err = self._clue_route_sections(\n'
    '                stage.get(), clue, ab, doors, tval, self.cost_mode.get(), punch, tour)\n')

# ---------------------------------------------------------------- 11) 二轮对话框
rep('        dlg.title("第二轮路线（get_newroute）：查看 + 改巡游顺序 + 写回 config.h")\n'
    '        dlg.geometry("740x500")\n',
    '        dlg.title("第二轮路线（get_newroute）：查看 + 改巡游顺序 + 写回 config.h")\n'
    '        dlg.geometry("740x560")\n')

rep('        fw_lbl = ttk.Label(frm, wraplength=694, justify="left",\n'
    '                           text="固件现状（config.h）：…", foreground="#555555")\n'
    '        fw_lbl.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))\n',
    '        fw_lbl = ttk.Label(frm, wraplength=694, justify="left",\n'
    '                           text="固件现状（config.h）：…", foreground="#555555")\n'
    '        fw_lbl.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))\n'
    '\n'
    '        TOUR_VALS = ["跟随 config.h", "强制开", "强制关"]\n'
    '        _ctour = _cfg.get("tour")\n'
    '        tour_sel = tk.StringVar(value=_ctour if _ctour in TOUR_VALS else TOUR_VALS[0])\n'
    '        ttk.Label(frm, text="直立景点巡回 S1/S2").grid(row=7, column=0, sticky="w",\n'
    '                                                       pady=3, padx=(0, 6))\n'
    '        ttk.Combobox(frm, textvariable=tour_sel, values=TOUR_VALS, state="readonly",\n'
    '                     width=36).grid(row=7, column=1, sticky="w", pady=3)\n')

rep('            self.round2_cfg = {"doors": [light_vars[i].get() for i in range(4)],\n'
    '                               "treasure": tsel.get(),\n'
    '                               "cw": _grp_vals(cw_vars),\n'
    '                               "ccw": _grp_vals(ccw_vars),\n'
    '                               "auto": bool(auto_var.get())}\n',
    '            self.round2_cfg = {"doors": [light_vars[i].get() for i in range(4)],\n'
    '                               "treasure": tsel.get(),\n'
    '                               "cw": _grp_vals(cw_vars),\n'
    '                               "ccw": _grp_vals(ccw_vars),\n'
    '                               "auto": bool(auto_var.get()),\n'
    '                               "tour": tour_sel.get()}\n')

rep('            secs, flat, split, err = self._round2_route_sections(\n'
    '                doors, t, order, self.cost_mode.get())\n',
    '            secs, flat, split, err = self._round2_route_sections(\n'
    '                doors, t, order, self.cost_mode.get(), None,\n'
    '                self._tour_on(tour_sel.get()))\n')

rep('        btns = ttk.Frame(frm)\n'
    '        btns.grid(row=7, column=0, columnspan=2, sticky="w", pady=(14, 0))\n',
    '        btns = ttk.Frame(frm)\n'
    '        btns.grid(row=8, column=0, columnspan=2, sticky="w", pady=(14, 0))\n')


def main():
    with open(E, "rb") as f:
        data = f.read()
    eol = "\r\n" if data.count(b"\r\n") else "\n"
    for old, new in EDITS:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "命中 %d 次（期望 1）:\n%r" % (cnt, old[:90])
        data = data.replace(ob, nb)
    with open(E, "wb") as f:
        f.write(data)
    print("[ok] map_editor.py +%d 处, crlf=%d lf=%d"
          % (len(EDITS), data.count(b"\r\n"), data.count(b"\n") - data.count(b"\r\n")))


if __name__ == "__main__":
    main()
