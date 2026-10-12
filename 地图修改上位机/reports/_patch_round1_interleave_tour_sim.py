# -*- coding: utf-8 -*-
"""tools/sim_upright_tour.py：镜像同步到"交错 + S1/S2 跟着 P3/P4 走"。

- 新增读 config.h 的两个开关 + 源同步自检 + round1_tail()（镜像 append_round1_return_tail）。
- tret_wp / home_wp 改调 round1_tail()。
- [2]/[3] 两节改成：A 段测 punch=0 回归基线；B 段测 punch=1 的新判据（clue=0/3/4）。
"""
import os, sys

ROOT = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao"
PATH = os.path.join(ROOT, "地图修改上位机", "tools", "sim_upright_tour.py")

raw = open(PATH, "rb").read()
crlf = raw.count(b"\r\n"); lf = raw.count(b"\n") - crlf
print("EOL: CRLF=%d LF-only=%d" % (crlf, lf))
EOL = "\r\n" if crlf >= lf else "\n"
text = raw.decode("utf-8")


def b(s):
    return s.replace("\n", EOL)


edits = []

# ---------- R1 docstring ----------
edits.append(("R1 docstring", b('''"""直立景点巡回（S1/S2）开关路线验证 —— 只读源码，不改任何文件。

对照 Mission/mission_planner.c 的三处插点（plan_treasure_return / route_return_home /
get_newroute），用 nav_planner 镜像算出 UPRIGHT_TOUR_ENABLE=0/1 两种状态的 route[]：

  · 0（默认，保持现状）：任何路线里都不出现 S 节点 —— 即回归基线。
  · 1（打开）：S1 只在 P3 之后、S2 只在 P4 之后；一轮里 S 必在宝物平台之后
    （规则：取宝前走到其他平台或直立景点 = 直接结束比赛）。
'''), b('''"""直立景点巡回（S1/S2）开关路线验证 —— 只读源码，不改任何文件。

对照 Mission/mission_planner.c 的三处插点（plan_treasure_return / route_return_home /
get_newroute），用 nav_planner 镜像算出 UPRIGHT_TOUR_ENABLE × P3P4_PUNCH_ENABLE 各状态的 route[]：

  · 0（默认，保持现状）：任何路线里都不出现 S 节点 —— 即回归基线。
  · 1（打开）：一轮那两处**交错**成 `P3 -> S1 -> P4 -> S2`（与二轮同序）；S 的判据
    2026-10-16 起**跟着"这次回程会不会去 P3/P4"走**（不再是"宝物就在 P3/P4"）：
      会去 P3 ⇒ 绕 S1；会去 P4 ⇒ 绕 S2。补打卡 P3P4_PUNCH_ENABLE 开着 ⇒ 两个景点都绕。
    一轮里 S 必在对应宝物平台之后（规则：取宝前走到其他平台或直立景点 = 直接结束比赛）。
''')))

# ---------- R2 加开关 + 源同步自检 + round1_tail ----------
edits.append(("R2 开关/自检/round1_tail",
    b('''R2_CW = _cfg_order("CW", ("P5", "P7", "P8", "P6"))
R2_CCW = _cfg_order("CCW", ("P6", "P8", "P7", "P5"))
'''),
    b('''R2_CW = _cfg_order("CW", ("P5", "P7", "P8", "P6"))
R2_CCW = _cfg_order("CCW", ("P6", "P8", "P7", "P5"))


def _cfg_flag(name, default=0):
    """读 config.h 的 #define <name> <十进制>。"""
    m = re.search(r"^\\s*#define\\s+" + re.escape(name) + r"\\s+([0-9]+)\\b", _CFG_TXT, re.M)
    return int(m.group(1)) if m else default


TOUR = _cfg_flag("UPRIGHT_TOUR_ENABLE", 0)
PUNCH = _cfg_flag("P3P4_PUNCH_ENABLE", 0)

# ---- 源同步自检：一轮交错段必须仍集中在共享小函数里（2026-10-16 起的结构）----
SYNC = []
try:
    with open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "Mission",
                           "mission_planner.c"), encoding="utf-8", errors="replace") as _f:
        _MP = _f.read()
except OSError:
    _MP = ""
if not _MP:
    SYNC.append("读不到 Mission/mission_planner.c")
else:
    _mp = re.sub(r"/\\*.*?\\*/", " ", _MP, flags=re.S)
    _mp = re.sub(r"//[^\\n]*", " ", _mp)
    _m = re.search(r"append_round1_return_tail\\s*\\([^;{}]*\\)\\s*\\{", _mp)
    if not _m:
        SYNC.append("mission_planner.c 里找不到 append_round1_return_tail()（一轮交错段落点变了）")
    else:
        _d, _end, _body = 0, None, ""
        for _j in range(_m.end() - 1, len(_mp)):
            if _mp[_j] == "{":
                _d += 1
            elif _mp[_j] == "}":
                _d -= 1
                if _d == 0:
                    _end = _j
                    break
        if _end:
            _body = _mp[_m.end() - 1:_end + 1]
        for _need in ("goP3", "goP4", "P3P4_PUNCH_ENABLE", "UPRIGHT_TOUR_ENABLE"):
            if _need not in _body:
                SYNC.append("append_round1_return_tail() 里缺 %s（判据 / 开关变了）" % _need)
        _ord = [_body.find("wp[n++] = P3;"), _body.find("wp[n++] = S1;"),
                _body.find("wp[n++] = P4;"), _body.find("wp[n++] = S2;")]
        if -1 in _ord or _ord != sorted(_ord):
            SYNC.append("append_round1_return_tail() 的插点顺序不是 P3 -> S1 -> P4 -> S2（偏移 %s）"
                        % _ord)
    if _mp.count("n = append_round1_return_tail(wp, n);") != 2:
        SYNC.append("append_round1_return_tail() 的调用点不是 2 个"
                    "（plan_treasure_return / route_return_home 各一次）")
''')))

# ---------- R3 tret_wp 头 + round1_tail ----------
edits.append(("R3 round1_tail + tret 头",
    b('''def tret_wp(start, door, treasure, tour):
    """镜像 mission_planner.c:plan_treasure_return() 的 wp。"""'''),
    b('''def round1_tail(treasure, clue, punch, tour):
    """镜像 mission_planner.c:append_round1_return_tail()：宝物平台之后、P2 之前的交错段。

    判据（2026-10-16 改）：会去 P3 = 平台就是 P3 或（补打卡开着且百位没走过 P3）；会去 P4 同理。
    顺序固定 P3 -> S1 -> P4 -> S2。返回列表**不含宝物平台本身**（调用方已在更前面加过）。
    """
    go_p3 = (treasure == 3) or (bool(punch) and clue != 3 and treasure != 3)
    go_p4 = (treasure == 4) or (bool(punch) and clue != 4 and treasure != 4)
    out = []
    if go_p3 and treasure != 3:
        out.append("P3")
    if go_p3 and tour:
        out.append("S1")
    if go_p4 and treasure != 4:
        out.append("P4")
    if go_p4 and tour:
        out.append("S2")
    return out


def tret_wp(start, door, treasure, tour, clue=0, punch=False):
    """镜像 mission_planner.c:plan_treasure_return() 的 wp。"""''')))

# ---------- R4 tret_wp 尾 ----------
edits.append(("R4 tret_wp 尾",
    b('''    if treasure not in (5, 6):
        wp.append(target)
    if tour:                                  # ← 新增插点
        if treasure == 3:
            wp.append("S1")
        elif treasure == 4:
            wp.append("S2")
    wp.append("P2")
    return wp'''),
    b('''    if treasure not in (5, 6):
        wp.append(target)
    wp += round1_tail(treasure, clue, punch, tour)   # ← 镜像 append_round1_return_tail()
    wp.append("P2")
    return wp''')))

# ---------- R5 home_wp ----------
edits.append(("R5 home_wp",
    b('''def home_wp(now, treasure, tour):
    """镜像 mission_planner.c:route_return_home() 的 wp。"""
    wp = [now]
    if treasure == 2:
        wp.append("P1")
    elif treasure == 3:
        wp.append("P3")
    elif treasure == 4:
        wp.append("P4")
    if tour:                                  # ← 新增插点
        if treasure == 3:
            wp.append("S1")
        elif treasure == 4:
            wp.append("S2")
    wp.append("P2")
    return wp'''),
    b('''def home_wp(now, treasure, tour, clue=0, punch=False):
    """镜像 mission_planner.c:route_return_home() 的 wp。"""
    wp = [now]
    if treasure == 2:
        wp.append("P1")
    elif treasure == 3:
        wp.append("P3")
    elif treasure == 4:
        wp.append("P4")
    wp += round1_tail(treasure, clue, punch, tour)   # ← 镜像 append_round1_return_tail()
    wp.append("P2")
    return wp''')))

# ---------- R6 头部打印 ----------
edits.append(("R6 头部打印",
    b('''print("=" * 78)
print("直立景点巡回（S1/S2）路线验证 —— 镜像 mission_planner.c 的三处插点")
print("=" * 78)'''),
    b('''print("=" * 78)
print("直立景点巡回（S1/S2）路线验证 —— 镜像 mission_planner.c 的三处插点")
print("UPRIGHT_TOUR_ENABLE=%d ｜ P3P4_PUNCH_ENABLE=%d（读自 Mission/config.h）" % (TOUR, PUNCH))
if SYNC:
    print("★ 源同步自检：不通过 —— 本镜像是旧版，下面的结论不可信：")
    for _p in SYNC:
        print("   - %s" % _p)
else:
    print("源同步自检：通过（交错段在 append_round1_return_tail()、两处调用、顺序 P3->S1->P4->S2）")
print("=" * 78)''')))

# ---------- R7 [2] 一节 ----------
old2 = b('''# ---------- [2] 一轮 plan_treasure_return ----------
print("\\n[2] 一轮 plan_treasure_return()：仅宝物=P3/P4 时插，且必须在宝物平台【之后】")
n_case = n_sol = 0
D_TRET = []
for door in itertools.product((CAN, ONE, NO), repeat=4):
    for tre in (2, 3, 4, 5, 6):
        for start in ("P7", "P8"):
            w0 = tret_wp(start, door, tre, False)
            w1 = tret_wp(start, door, tre, True)
            if w0 is None:
                continue
            n_case += 1
            p0, p1 = plan(w0), plan(w1)
            if p0 is None:
                continue
            n_sol += 1
            tag = f"一轮 {start} t={tre} door={door}"
            check(not has_S(p0), tag + " 关闭态不应有 S", f"{p0}")
            check(p1 is not None, tag + " 打开态应可达")
            if p1 is None:
                continue
            if tre in (3, 4):
                s = "S1" if tre == 3 else "S2"
                plat = "P3" if tre == 3 else "P4"
                check(s in p1, tag + f" 打开态应含 {s}", f"{p1}")
                if s in p1:
                    check(p1.index(s) > p1.index(plat),
                          tag + f" {s} 必须排在宝物平台 {plat} 之后（取宝前去 = 结束比赛）")
                    check(not (p1.index(s) < p1.index(plat)), tag + " 红线：取宝前不得出现 S")
            else:
                check(not has_S(p1), tag + f" 宝物 t={tre} 时不应插 S", f"{p1}")
            check(strip_S(p1) == p0, tag + " 去掉 S 支路后应与关闭态一致",
                  f"\\n          开-去S: {' '.join(strip_S(p1))}\\n          关闭态: {' '.join(p0)}")
            if tre in (3, 4):        # 只拿"真正插了 S"的案例做示例
                EX.setdefault("tret", (start, door, tre, w0, w1, p0, p1))
                D_TRET.append(dist_cm(p1) - dist_cm(p0))
''')
new2 = b('''# ---------- [2] 一轮 plan_treasure_return ----------
print("\\n[2] 一轮 plan_treasure_return()：A 段 punch=0 回归基线；B 段 punch=1 交错 P3->S1->P4->S2")
n_case = n_sol = 0
D_TRET = []
N_PUNCH2 = 0


def _tail_wp_order(wp):
    return [n for n in wp if n in ("P3", "S1", "P4", "S2")]


for door in itertools.product((CAN, ONE, NO), repeat=4):
    for tre in (2, 3, 4, 5, 6):
        for start in ("P7", "P8"):
            w0 = tret_wp(start, door, tre, False)
            if w0 is None:
                continue
            n_case += 1
            p0 = plan(w0)
            if p0 is None:
                continue
            n_sol += 1
            tag = f"一轮 {start} t={tre} door={door}"
            check(not has_S(p0), tag + " 关闭态不应有 S", f"{p0}")
            # --- A. punch=0 + tour=1：旧行为（S 只跟宝物值），回归基线 ---
            w1 = tret_wp(start, door, tre, True, 0, False)
            p1 = plan(w1)
            check(p1 is not None, tag + " 打开态应可达")
            if p1 is not None:
                if tre in (3, 4):
                    s, plat = ("S1", "P3") if tre == 3 else ("S2", "P4")
                    check(s in p1, tag + f" 打开态应含 {s}", f"{p1}")
                    if s in p1:
                        check(p1.index(s) > p1.index(plat),
                              tag + f" {s} 必须排在宝物平台 {plat} 之后（取宝前去 = 结束比赛）")
                else:
                    check(not has_S(p1), tag + f" 宝物 t={tre}（补打卡关）不应插 S", f"{p1}")
                check(strip_S(p1) == p0, tag + " 去掉 S 支路后应与关闭态一致",
                      f"\\n          开-去S: {' '.join(strip_S(p1))}\\n          关闭态: {' '.join(p0)}")
                if tre in (3, 4):        # 只拿"真正插了 S"的案例做示例
                    EX.setdefault("tret", (start, door, tre, w0, w1, p0, p1))
                    D_TRET.append(dist_cm(p1) - dist_cm(p0))
            # --- B. punch=1 + tour=1：新判据（S 跟着"会去 P3/P4"走；顺序交错）---
            for clue in (0, 3, 4):
                w2 = tret_wp(start, door, tre, True, clue, True)
                go3 = (tre == 3) or (clue != 3 and tre != 3)
                go4 = (tre == 4) or (clue != 4 and tre != 4)
                tg2 = tag + f" clue={clue} punch=1"
                N_PUNCH2 += 1
                check(_tail_wp_order(w2) == [n for n in ("P3", "S1", "P4", "S2")
                                             if n in _tail_wp_order(w2)],
                      tg2 + " wp 里交错顺序应为 P3 -> S1 -> P4 -> S2", f"{_tail_wp_order(w2)}")
                check(("S1" in w2) == bool(go3), tg2 + f" S1 应{'在' if go3 else '不在'}（go3={go3}）",
                      f"{w2}")
                check(("S2" in w2) == bool(go4), tg2 + f" S2 应{'在' if go4 else '不在'}（go4={go4}）",
                      f"{w2}")
                p2 = plan(w2)
                check(p2 is not None, tg2 + " 应可达")
                if p2 is None:
                    continue
                check(("S1" in p2) == bool(go3), tg2 + f" route 里 S1 应与 go3 一致（{p2}）")
                check(("S2" in p2) == bool(go4), tg2 + f" route 里 S2 应与 go4 一致（{p2}）")
                if tre in (3, 4):
                    s, plat = ("S1", "P3") if tre == 3 else ("S2", "P4")
                    if s in p2:
                        check(p2.index(s) > p2.index(plat),
                              tg2 + f" {s} 必须排在宝物平台 {plat} 之后")
                if tre not in (3, 4) and go3 and go4:
                    check("S1" in p2 and "S2" in p2,
                          tg2 + " 宝物不在 P3/P4 时（补打卡开）两个景点都该绕", f"{p2}")
                EX.setdefault("punch_interleave", (start, door, tre, clue, w2, p2))
''')
edits.append(("[2] 一节", old2, new2))

# ---------- R8 [3] 一节 ----------
old3 = b('''# ---------- [3] 一轮 route_return_home ----------
print("\\n[3] 一轮 route_return_home()：门口重规划，S 同样在宝物平台之后")
n_case = n_sol = 0
D_HOME = []
for now in ("N3", "N8", "N5"):
    for tre in (2, 3, 4, 5, 6):
        w0 = home_wp(now, tre, False)
        w1 = home_wp(now, tre, True)
        n_case += 1
        p0, p1 = plan(w0), plan(w1)
        if p0 is None:
            continue
        n_sol += 1
        tag = f"门回程 now={now} t={tre}"
        check(not has_S(p0), tag + " 关闭态不应有 S", f"{p0}")
        check(p1 is not None, tag + " 打开态应可达")
        if p1 is None:
            continue
        if tre in (3, 4):
            s = "S1" if tre == 3 else "S2"
            plat = "P3" if tre == 3 else "P4"
            check(s in p1, tag + f" 打开态应含 {s}", f"{p1}")
            if s in p1:
                check(p1.index(s) > p1.index(plat),
                      tag + f" {s} 必须排在宝物平台 {plat} 之后")
        else:
            check(not has_S(p1), tag + f" 宝物 t={tre} 时不应插 S", f"{p1}")
        check(strip_S(p1) == p0, tag + " 去掉 S 支路后应与关闭态一致",
              f"\\n          开-去S: {' '.join(strip_S(p1))}\\n          关闭态: {' '.join(p0)}")
        if tre in (3, 4):
            EX.setdefault("home", (now, tre, w0, w1, p0, p1))
            D_HOME.append(dist_cm(p1) - dist_cm(p0))
''')
new3 = b('''# ---------- [3] 一轮 route_return_home ----------
print("\\n[3] 一轮 route_return_home()：A 段 punch=0 回归基线；B 段 punch=1 交错 P3->S1->P4->S2")
n_case = n_sol = 0
D_HOME = []
N_PUNCH3 = 0
for now in ("N3", "N8", "N5"):
    for tre in (2, 3, 4, 5, 6):
        w0 = home_wp(now, tre, False)
        w1 = home_wp(now, tre, True)
        n_case += 1
        p0 = plan(w0)
        if p0 is None:
            continue
        n_sol += 1
        tag = f"门回程 now={now} t={tre}"
        check(not has_S(p0), tag + " 关闭态不应有 S", f"{p0}")
        # --- A. punch=0 + tour=1：旧行为 ---
        p1 = plan(w1)
        check(p1 is not None, tag + " 打开态应可达")
        if p1 is not None:
            if tre in (3, 4):
                s, plat = ("S1", "P3") if tre == 3 else ("S2", "P4")
                check(s in p1, tag + f" 打开态应含 {s}", f"{p1}")
                if s in p1:
                    check(p1.index(s) > p1.index(plat),
                          tag + f" {s} 必须排在宝物平台 {plat} 之后")
            else:
                check(not has_S(p1), tag + f" 宝物 t={tre}（补打卡关）不应插 S", f"{p1}")
            check(strip_S(p1) == p0, tag + " 去掉 S 支路后应与关闭态一致",
                  f"\\n          开-去S: {' '.join(strip_S(p1))}\\n          关闭态: {' '.join(p0)}")
            if tre in (3, 4):
                EX.setdefault("home", (now, tre, w0, w1, p0, p1))
                D_HOME.append(dist_cm(p1) - dist_cm(p0))
        # --- B. punch=1 + tour=1：新判据 ---
        for clue in (0, 3, 4):
            w2 = home_wp(now, tre, True, clue, True)
            go3 = (tre == 3) or (clue != 3 and tre != 3)
            go4 = (tre == 4) or (clue != 4 and tre != 4)
            tg2 = tag + f" clue={clue} punch=1"
            N_PUNCH3 += 1
            check(_tail_wp_order(w2) == [n for n in ("P3", "S1", "P4", "S2")
                                         if n in _tail_wp_order(w2)],
                  tg2 + " wp 里交错顺序应为 P3 -> S1 -> P4 -> S2", f"{_tail_wp_order(w2)}")
            check(("S1" in w2) == bool(go3), tg2 + f" S1 应{'在' if go3 else '不在'}（go3={go3}）",
                  f"{w2}")
            check(("S2" in w2) == bool(go4), tg2 + f" S2 应{'在' if go4 else '不在'}（go4={go4}）",
                  f"{w2}")
            p2 = plan(w2)
            check(p2 is not None, tg2 + " 应可达")
            if p2 is None:
                continue
            check(("S1" in p2) == bool(go3), tg2 + f" route 里 S1 应与 go3 一致（{p2}）")
            check(("S2" in p2) == bool(go4), tg2 + f" route 里 S2 应与 go4 一致（{p2}）")
            if tre in (3, 4):
                s, plat = ("S1", "P3") if tre == 3 else ("S2", "P4")
                if s in p2:
                    check(p2.index(s) > p2.index(plat), tg2 + f" {s} 必须排在宝物平台 {plat} 之后")
            if tre not in (3, 4) and go3 and go4:
                check("S1" in p2 and "S2" in p2,
                      tg2 + " 宝物不在 P3/P4 时（补打卡开）两个景点都该绕", f"{p2}")
            EX.setdefault("home_punch_interleave", (now, tre, clue, w2, p2))
''')
edits.append(("[3] 一节", old3, new3))

# ---------- R9 示例输出 + 结论 ----------
edits.append(("R9 示例/结论",
    b('''# ==================== 示例输出 ====================
print("\\n" + "=" * 78)
print("示例路线（UPRIGHT_TOUR_ENABLE=1）")
print("=" * 78)'''),
    b('''# ==================== 示例输出 ====================
print("\\n" + "=" * 78)
print("示例路线（UPRIGHT_TOUR_ENABLE=1）")
print("=" * 78)


def show_interleave(title, key):
    if key not in EX:
        return
    e = EX[key]
    if key == "punch_interleave":
        start, door, tre, clue, w2, p2 = e
        print(f"\\n【{title} · 起点={start} 宝物=P{tre} 百位={clue}】")
    else:
        now, tre, clue, w2, p2 = e
        print(f"\\n【{title} · nowNode={now} 宝物=P{tre} 百位={clue}】")
    print(f"  补打卡开的 wp   : {' '.join(w2)}")
    print(f"  补打卡开的 route: {' '.join(p2)}")''')))

edits.append(("R10 结果文字",
    b('''print(f"[OK] 全部通过（{N_CHECK} 项检查）："
      "关闭态无 S（回归基线）· 打开态 S 位置正确且在宝物平台之后 · 去 S 后与关闭态一致")'''),
    b('''show_interleave("一轮 plan_treasure_return（交错）", "punch_interleave")
show_interleave("一轮 route_return_home（交错）", "home_punch_interleave")
print("\\n" + "=" * 78)
if FAILS:
    print(f"[FAIL] {len(FAILS)} 项不通过 / 共 {N_CHECK} 项检查")
    for f in FAILS[:20]:
        print("   -", f)
    sys.exit(1)
print(f"[OK] 全部通过（{N_CHECK} 项检查）："
      "关闭态无 S（回归基线）· punch=0 时旧行为不变 · punch=1 时 S 跟着「会去 P3/P4」走"
      "且交错成 P3->S1->P4->S2 · S 在宝物平台之后 · 去 S 后与关闭态一致")''')))

# 删掉文件末尾原有的"结果"块（会被 R10 替换掉的位置之后重复）
old_tail = b('''# ==================== 结果 ====================
print("\\n" + "=" * 78)
if FAILS:
    print(f"[FAIL] {len(FAILS)} 项不通过 / 共 {N_CHECK} 项检查")
    for f in FAILS[:20]:
        print("   -", f)
    sys.exit(1)
print(f"[OK] 全部通过（{N_CHECK} 项检查）："
      "关闭态无 S（回归基线）· 打开态 S 位置正确且在宝物平台之后 · 去 S 后与关闭态一致")
print("=" * 78)''')
edits.append(("R11 删旧结果块", old_tail, b("")))

ok = True
for name, old, new in edits:
    c = text.count(old)
    print("%-26s count=%d" % (name, c))
    if c != 1:
        ok = False
if not ok:
    print("!! 命中次数 != 1，未写盘")
    sys.exit(1)

for name, old, new in edits:
    text = text.replace(old, new, 1)

# 收尾：把连续 3 个以上空行收敛成 2 个（R11 留下的空档）
text = text.replace(EOL * 4, EOL * 2)
open(PATH, "wb").write(text.encode("utf-8"))
print("已写盘:", PATH)
