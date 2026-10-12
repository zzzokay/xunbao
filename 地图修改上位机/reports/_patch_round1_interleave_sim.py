# -*- coding: utf-8 -*-
"""sim_route_bookkeeping.py：镜像与源同步自检跟着"一轮交错"改。

- Sim 类：新增 round1_return_tail()，plan_treasure_return / route_return_home 改调它。
- _sync_check()：①③④⑤ 重写为对齐新结构（helper + 两处调用）。
- 报告文字 & 对比表跟着更新。
"""
import os, sys

ROOT = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao"
PATH = os.path.join(ROOT, "地图修改上位机", "tools", "sim_route_bookkeeping.py")

raw = open(PATH, "rb").read()
crlf = raw.count(b"\r\n"); lf = raw.count(b"\n") - crlf
print("EOL: CRLF=%d LF-only=%d" % (crlf, lf))
EOL = "\r\n" if crlf >= lf else "\n"
text = raw.decode("utf-8")


def b(s):
    return s.replace("\n", EOL)


# ---------- 1) Sim: 新增 round1_return_tail() ----------
old_s1 = b('''    def plan_treasure_return(self, start):
        wp = [start]''')
new_s1 = b('''    def round1_return_tail(self):
        """镜像固件 append_round1_return_tail()：宝物平台之后、P2 之前的交错段。

        判据（2026-10-16 改）：会去 P3 = 平台就是 P3 或（补打卡开着且百位没走过 P3）；
        会去 P4 同理。⇒ S1/S2 不再依赖宝物值。
        顺序固定 P3 -> S1 -> P4 -> S2（与二轮 get_newroute() 一致）。
        """
        go_p3 = (self.treasure == 3) or (self.punch and self.clue != 3
                                         and self.treasure != 3)
        go_p4 = (self.treasure == 4) or (self.punch and self.clue != 4
                                         and self.treasure != 4)
        out = []
        if go_p3 and self.treasure != 3:   # 宝物平台那一次已在更前面加过
            out.append("P3")
        if go_p3 and self.tour:
            out.append("S1")
        if go_p4 and self.treasure != 4:
            out.append("P4")
        if go_p4 and self.tour:
            out.append("S2")
        return out

    def plan_treasure_return(self, start):
        wp = [start]''')

# ---------- 2) 两处调用（文本相同，应命中 2 次）----------
old_s2 = b('''        if self.punch:     # ← 镜像 mission_planner.c 的 P3P4_PUNCH_ENABLE 块
            if self.clue != 3 and self.treasure != 3:   wp.append("P3")
            if self.clue != 4 and self.treasure != 4:   wp.append("P4")
        if self.tour:      # ← 镜像 mission_planner.c 的 UPRIGHT_TOUR_ENABLE 块
            if self.treasure == 3:      wp.append("S1")
            elif self.treasure == 4:    wp.append("S2")
        wp.append("P2")''')
new_s2 = b('''        wp += self.round1_return_tail()   # ← 镜像 append_round1_return_tail()
        wp.append("P2")''')

# ---------- 3) _sync_check ① ----------
old_c1 = b('''    # ① 一轮两处：开关块里必须是 treasure==3 给 S1 / treasure==4 给 S2
    for fn in ("plan_treasure_return", "route_return_home"):
        body = _fn_body(MP_CODE, fn)
        if body is None:
            SYNC_PROBLEMS.append("%s() 找不到了" % fn)
            continue
        blks = _guarded(body, TOUR_MACRO)
        if len(blks) != 1:
            SYNC_PROBLEMS.append("%s() 里 if (%s) 块有 %d 个，镜像假设 1 个"
                                 % (fn, TOUR_MACRO, len(blks)))
            continue
        for cond, stmt in (("treasure == 3", "wp[n++] = S1;"),
                           ("treasure == 4", "wp[n++] = S2;")):
            if cond not in blks[0] or stmt not in blks[0]:
                SYNC_PROBLEMS.append("%s() 的开关块里缺 %s + %s" % (fn, cond, stmt))
''')
new_c1 = b('''    # ① 一轮交错段的**唯一落点** = 辅助函数 append_round1_return_tail()。
    #    2026-10-16 起 S1/S2 的判据改成"跟着会去 P3/P4 走"，两个回程函数不再各写一份。
    _helper = _fn_body(MP_CODE, "append_round1_return_tail")
    _r2 = _fn_body(MP_CODE, "get_newroute") or ""
    if _helper is None:
        SYNC_PROBLEMS.append(
            "append_round1_return_tail() 找不到了 —— 一轮 P3/S1/P4/S2 交错段应集中在这里")
    else:
        for need in ("goP3", "goP4", "treasure == 3", "treasure == 4",
                     "flag_line_clue != 3", "flag_line_clue != 4",
                     PUNCH_MACRO, TOUR_MACRO):
            if need not in _helper:
                SYNC_PROBLEMS.append(
                    "append_round1_return_tail() 里缺 %s（S1/S2 判据应跟着 P3/P4 走）" % need)
        _order = [_helper.find("wp[n++] = P3;"), _helper.find("wp[n++] = S1;"),
                  _helper.find("wp[n++] = P4;"), _helper.find("wp[n++] = S2;")]
        if -1 in _order or _order != sorted(_order):
            SYNC_PROBLEMS.append(
                "append_round1_return_tail() 的插点顺序不是 P3 -> S1 -> P4 -> S2（偏移 %s）"
                % _order)
    for fn in ("plan_treasure_return", "route_return_home"):
        body = _fn_body(MP_CODE, fn)
        if body is None:
            SYNC_PROBLEMS.append("%s() 找不到了" % fn)
            continue
        if "append_round1_return_tail(wp, n)" not in body:
            SYNC_PROBLEMS.append("%s() 没调用 append_round1_return_tail()" % fn)
        for macro in (TOUR_MACRO, PUNCH_MACRO):
            if _guarded(body, macro):
                SYNC_PROBLEMS.append(
                    "%s() 里还留着 if (%s) 块 —— 应改走 append_round1_return_tail()"
                    % (fn, macro))
''')

# ---------- 4) _sync_check ③ ----------
old_c3 = b('''    # ③ 反向：源码里每一处 S 赋值都必须落在我们认得的开关块内，多出来 = 镜像过期
    guarded_all = " ".join(_guarded(MP_CODE, TOUR_MACRO))
    for stmt in ("wp[n++] = S1;", "wp[n++] = S2;"):
        if MP_CODE.count(stmt) != guarded_all.count(stmt):
            SYNC_PROBLEMS.append(
                "mission_planner.c 里有 %d 处 %s，只有 %d 处在 if (%s) 块里"
                "（开关外的插点，镜像覆盖不到）"
                % (MP_CODE.count(stmt), stmt, guarded_all.count(stmt), TOUR_MACRO))
''')
new_c3 = b('''    # ③ 反向：源码里每一处 S 赋值都必须和 UPRIGHT_TOUR_ENABLE 写在同一行
    #    （裸 if (UPRIGHT_TOUR_ENABLE) 或 if (goPx && UPRIGHT_TOUR_ENABLE)），
    #    多出来 = 开关外的插点，镜像覆盖不到。
    for stmt in ("wp[n++] = S1;", "wp[n++] = S2;"):
        n_all = MP_CODE.count(stmt)
        n_ok = sum(1 for ln in MP_CODE.splitlines() if stmt in ln and TOUR_MACRO in ln)
        if n_all != n_ok:
            SYNC_PROBLEMS.append(
                "mission_planner.c 里有 %d 处 %s，只有 %d 处与 %s 同行"
                "（开关外的插点，镜像覆盖不到）" % (n_all, stmt, n_ok, TOUR_MACRO))
''')

# ---------- 5) _sync_check ④ ----------
old_c4 = b('''    # ④ 一轮回程补打卡 P3/P4（P3P4_PUNCH_ENABLE）：一轮两处，条件 = 百位/宝物平台去过就跳过
    if _PUNCH_RAW is None:
        SYNC_PROBLEMS.append("config.h 里找不到 #define %s" % PUNCH_MACRO)
    for fn in ("plan_treasure_return", "route_return_home"):
        body = _fn_body(MP_CODE, fn)
        if body is None:
            continue
        blks = _guarded(body, PUNCH_MACRO)
        if len(blks) != 1:
            SYNC_PROBLEMS.append("%s() 里 if (%s) 块有 %d 个，镜像假设 1 个"
                                 % (fn, PUNCH_MACRO, len(blks)))
            continue
        for cond, stmt in (("flag_line_clue != 3", "wp[n++] = P3;"),
                           ("flag_line_clue != 4", "wp[n++] = P4;")):
            if cond not in blks[0] or stmt not in blks[0]:
                SYNC_PROBLEMS.append("%s() 的补打卡块里缺 %s + %s" % (fn, cond, stmt))
    _r2 = _fn_body(MP_CODE, "get_newroute") or ""
    if _guarded(_r2, PUNCH_MACRO):
        SYNC_PROBLEMS.append(
            "get_newroute() 里也出现 %s —— 二轮本来就固定走 P3/P4，不该再插" % PUNCH_MACRO)
''')
new_c4 = b('''    # ④ 反向：除二轮 get_newroute()（本来就固定走 P3/P4）以外，一轮里的 P3/P4 赋值
    #    必须与 goP3/goP4 同行 —— 而 goP3/goP4 的定义受 P3P4_PUNCH_ENABLE 管（见 ①）。
    if _PUNCH_RAW is None:
        SYNC_PROBLEMS.append("config.h 里找不到 #define %s" % PUNCH_MACRO)
    _mp_no_r2 = MP_CODE.replace(_r2, " ") if _r2 else MP_CODE
    for stmt, var in (("wp[n++] = P3;", "goP3"), ("wp[n++] = P4;", "goP4")):
        n_all = _mp_no_r2.count(stmt)
        n_ok = sum(1 for ln in _mp_no_r2.splitlines() if stmt in ln and var in ln)
        if n_all != n_ok:
            SYNC_PROBLEMS.append(
                "一轮里有 %d 处 %s 没跟 %s 同行（补打卡判据漏了）" % (n_all - n_ok, stmt, var))
    if _guarded(_r2, PUNCH_MACRO):
        SYNC_PROBLEMS.append(
            "get_newroute() 里出现 %s —— 二轮本来就固定走 P3/P4，不该再插" % PUNCH_MACRO)
''')

# ---------- 6) _sync_check ⑤ ----------
old_c5 = b('''    # ⑤ wp 容量：nowNode + 宝物平台 + P3/P4 + S + P2 = 6
    body = _fn_body(MP_CODE, "route_return_home") or ""
    m = re.search(r"u8\\s+wp\\s*\\[\\s*(\\d+)\\s*\\]", body)
    if not m:
        SYNC_PROBLEMS.append("route_return_home() 里找不到 u8 wp[N]")
    elif int(m.group(1)) < 6:
        SYNC_PROBLEMS.append(
            "route_return_home() 的 wp[%s] 装不下 nowNode+平台+P3+P4+S+P2（需 >=6）"
            % m.group(1))
''')
new_c5 = b('''    # ⑤ wp 容量：route_return_home 需 7（nowNode + 平台 + P3 + S1 + P4 + S2 + P2）；
    #    plan_treasure_return 需 9（start + P5/P6 + 门×2 + 平台 + P3 + S1 + P4 + S2 + P2）。
    for fn, need in (("route_return_home", 7), ("plan_treasure_return", 9)):
        m = re.search(r"u8\\s+wp\\s*\\[\\s*(\\d+)\\s*\\]", _fn_body(MP_CODE, fn) or "")
        if not m:
            SYNC_PROBLEMS.append("%s() 里找不到 u8 wp[N]" % fn)
        elif int(m.group(1)) < need:
            SYNC_PROBLEMS.append(
                "%s() 的 wp[%s] 装不下交错后的 %d 个点" % (fn, m.group(1), need))
''')

# ---------- 7) 报告文字 ----------
old_p1 = b('''        print("源同步自检：通过（S1/S2 三处 + P3/P4 两处插点 / 两个开关取值 / wp 容量 /"
              " ROUND2_CRUISE_* 巡游顺序 均与 mission_planner.c + config.h 一致）")''')
new_p1 = b('''        print("源同步自检：通过（一轮交错段 append_round1_return_tail + 二轮 S1/S2 插点 /"
              " 两个开关取值 / wp 容量 / ROUND2_CRUISE_* 巡游顺序 均与"
              " mission_planner.c + config.h 一致）")''')

old_p2 = b('''    print("P3P4_PUNCH_ENABLE：一轮「门回程」wp 对比（关 → 开）"
          "　※ P3/P4 插在宝物平台之后、P2 之前")
    for _clue, _tre in ((3, 2), (4, 2), (0, 2), (0, 3), (0, 4)):
        _row = []
        for _p in (0, 1):
            _s = Sim(clue=_clue, treasure=_tre, punch=_p)
            try:
                _s.map_init()
                _row.append(" ".join(_s.route_return_home()))
            except RouteError as _ex:
                _row.append("★ %s" % _ex)
        print("  线索=%s 宝物=%s  关: %-30s 开: %s"
              % (_clue, {2: "P1", 3: "P3", 4: "P4", 5: "P5", 6: "P6"}[_tre],
                 _row[0], _row[1]))''')
new_p2 = b('''    print("一轮「门回程」wp 对比（补打卡关 → 开）※ 巡回开关开着时交错成"
          " P3->S1->P4->S2，都在宝物平台之后、P2 之前")
    for _clue, _tre in ((3, 2), (4, 2), (0, 2), (0, 3), (0, 4)):
        _row = []
        for _p in (0, 1):
            _s = Sim(clue=_clue, treasure=_tre, punch=_p, tour=1)
            try:
                _s.map_init()
                _row.append(" ".join(_s.route_return_home()))
            except RouteError as _ex:
                _row.append("★ %s" % _ex)
        print("  线索=%s 宝物=%s  关: %-38s 开: %s"
              % (_clue, {2: "P1", 3: "P3", 4: "P4", 5: "P5", 6: "P6"}[_tre],
                 _row[0], _row[1]))''')

edits = [("1-Sim 助函数", old_s1, new_s1, 1),
         ("2-两处调用", old_s2, new_s2, 2),
         ("3-sync①", old_c1, new_c1, 1),
         ("4-sync③", old_c3, new_c3, 1),
         ("5-sync④", old_c4, new_c4, 1),
         ("6-sync⑤", old_c5, new_c5, 1),
         ("7-报告文字", old_p1, new_p1, 1),
         ("8-对比表", old_p2, new_p2, 1)]

ok = True
for name, old, new, exp in edits:
    c = text.count(old)
    print("%-14s count=%d (期望 %d)" % (name, c, exp))
    if c != exp:
        ok = False
if not ok:
    print("!! 命中次数不符，未写盘")
    sys.exit(1)

for name, old, new, exp in edits:
    text = text.replace(old, new, exp)

open(PATH, "wb").write(text.encode("utf-8"))
print("已写盘:", PATH)
