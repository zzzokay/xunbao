# -*- coding: utf-8 -*-
"""map_model.py：一轮回程镜像改成"交错 + S1/S2 跟着 P3/P4 走"。

1) upright_tour_waypoints(treasure) -> upright_tour_waypoints(treasure, line_clue=None, punch=False)
   语义改为"这次回程会去哪些直立景点"（会去 P3⇒S1、会去 P4⇒S2）。
2) 新增 round1_return_extra_waypoints()：宝物平台之后、P2 之前的交错段（P3->S1->P4->S2）。
3) treasure_return_waypoints / door_return_home_waypoints 两处调用改用它。

⚠️ 每个 old 片段必须恰好命中 1 次；全部成功才写盘。
"""
import os, sys

ROOT = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao"
PATH = os.path.join(ROOT, "地图修改上位机", "map_editor", "map_model.py")

raw = open(PATH, "rb").read()
crlf = raw.count(b"\r\n"); lf = raw.count(b"\n") - crlf
print("EOL: CRLF=%d LF-only=%d" % (crlf, lf))
EOL = "\r\n" if crlf >= lf else "\n"
text = raw.decode("utf-8")


def b(s):
    return s.replace("\n", EOL)


old1 = b('''def upright_tour_waypoints(treasure):
    """镜像 mission_planner.c 的 `UPRIGHT_TOUR_ENABLE` 一轮那两处：宝物 P3 绕 S1、P4 绕 S2。

    其余宝物值一轮不绕（二轮"固定两个都绕"由 round2_waypoints() 自己插）。
    ⚠️ S1/S2 的进边 `func` 是 `View1`、`map_function()` 里没有 `case View1`
       ⇒ **只走位、不做动作、不得分**。
    """
    if treasure == 3:
        return ["S1"]
    if treasure == 4:
        return ["S2"]
    return []
''')
new1 = b('''def upright_tour_waypoints(treasure, line_clue=None, punch=False):
    """镜像 mission_planner.c 一轮回程的 `UPRIGHT_TOUR_ENABLE`：这次回程**【会绕哪些直立景点】**。

    判据（2026-10-16 改）：**跟着"这次回程会不会去 P3/P4"走**，不再只看宝物值 ——
      会去 P3 ⇒ 绕 S1；会去 P4 ⇒ 绕 S2。其中
        "会去 P3" = 宝物平台就是 P3，或 补打卡（punch）开着且 QR 百位没走过 P3。
      ⇒ punch 开着时两个景点都绕（3/4 都去）；punch 关则退回旧行为（宝物 P3→S1、P4→S2）。
    返回 ["S1"] / ["S2"] / ["S1","S2"] / []（S1 恒在 S2 之前，与 P3->S1->P4->S2 同序）。
    ⚠️ S1/S2 的进边 `func` 是 `View1`、`map_function()` 里没有 `case View1`
       ⇒ **只走位、不做动作、不得分**。
    ⚠️ 二轮"固定两个都绕"由 round2_waypoints() 自己插，不走本函数。
    """
    go_p3 = (treasure == 3) or (punch and line_clue != 3 and treasure != 3)
    go_p4 = (treasure == 4) or (punch and line_clue != 4 and treasure != 4)
    out = []
    if go_p3:
        out.append("S1")
    if go_p4:
        out.append("S2")
    return out


def round1_return_extra_waypoints(treasure, line_clue, punch=False, tour=False):
    """镜像一轮回程（plan_treasure_return / route_return_home）**宝物平台之后、P2 之前**的交错段。

    顺序固定 **P3 -> S1 -> P4 -> S2**（与二轮 get_newroute() 一致，避免交叉绕路）。
    S1/S2 跟着"会去 P3/P4"走（同 upright_tour_waypoints()），所以**不再依赖宝物值**：
    补打卡开着时两个景点都绕，关掉则退回旧行为（宝物 P3→S1、P4→S2）。
    返回列表**不含宝物平台本身**（调用方已在更前面加过）。
    """
    punch_list = p3p4_punch_waypoints(treasure, line_clue) if punch else []
    tours = upright_tour_waypoints(treasure, line_clue, punch) if tour else []
    out = []
    if "P3" in punch_list:
        out.append("P3")
    if "S1" in tours:
        out.append("S1")
    if "P4" in punch_list:
        out.append("P4")
    if "S2" in tours:
        out.append("S2")
    return out
''')

old2 = b('''    punch=True ⇒ 按 `P3P4_PUNCH_ENABLE` 追加"补打卡"平台（见 p3p4_punch_waypoints()）；
    tour=True ⇒ 按 `UPRIGHT_TOUR_ENABLE` 追加 S1/S2（见 upright_tour_waypoints()）。
    两者都在**宝物平台之后、P2 之前**，且 **punch 先于 tour**（与固件里的书写顺序一致）。
    line_clue = QR 百位（0/3/4/None）。
    """''')
new2 = b('''    punch=True ⇒ 按 `P3P4_PUNCH_ENABLE` 追加"补打卡"平台；
    tour=True ⇒ 按 `UPRIGHT_TOUR_ENABLE` 追加 S1/S2。
    两者都在**宝物平台之后、P2 之前**，且按 **P3 -> S1 -> P4 -> S2 交错**
    （见 round1_return_extra_waypoints()；S1/S2 跟着"会去 P3/P4"走，不再依赖宝物值）。
    line_clue = QR 百位（0/3/4/None）。
    """''')

old3 = b('''    if treasure not in (5, 6):
        wp.append(TREASURE_PF[treasure])
    if punch:
        wp += p3p4_punch_waypoints(treasure, line_clue)
    if tour:
        wp += upright_tour_waypoints(treasure)
    wp.append("P2")''')
new3 = b('''    if treasure not in (5, 6):
        wp.append(TREASURE_PF[treasure])
    wp += round1_return_extra_waypoints(treasure, line_clue, punch, tour)
    wp.append("P2")''')

old4 = b('''    punch=True ⇒ 按 `P3P4_PUNCH_ENABLE` 追加"补打卡"平台；tour=True ⇒ 按
    `UPRIGHT_TOUR_ENABLE` 追加 S1/S2（两者都在宝物平台之后、P2 之前，punch 先于 tour）。
    line_clue = QR 百位（0/3/4/None）。
    """''')
new4 = b('''    punch=True ⇒ 按 `P3P4_PUNCH_ENABLE` 追加"补打卡"平台；tour=True ⇒ 按
    `UPRIGHT_TOUR_ENABLE` 追加 S1/S2（两者在宝物平台之后、P2 之前，按
    P3->S1->P4->S2 交错；S1/S2 跟着"会去 P3/P4"走）。
    line_clue = QR 百位（0/3/4/None）。
    """''')

old5 = b('''    if treasure in (2, 3, 4):
        wp.append(TREASURE_PF[treasure])
    if punch:
        wp += p3p4_punch_waypoints(treasure, line_clue)
    if tour:
        wp += upright_tour_waypoints(treasure)
    wp.append("P2")''')
new5 = b('''    if treasure in (2, 3, 4):
        wp.append(TREASURE_PF[treasure])
    wp += round1_return_extra_waypoints(treasure, line_clue, punch, tour)
    wp.append("P2")''')

edits = [("1-upright_tour_waypoints 定义", old1, new1),
         ("2-treasure_return 文档串", old2, new2),
         ("3-treasure_return 调用", old3, new3),
         ("4-door_return 文档串", old4, new4),
         ("5-door_return 调用", old5, new5)]

ok = True
for name, old, new in edits:
    c = text.count(old)
    print("%-30s count=%d" % (name, c))
    if c != 1:
        ok = False
if not ok:
    print("!! 有片段命中次数 != 1，未写盘")
    sys.exit(1)

for name, old, new in edits:
    text = text.replace(old, new, 1)

open(PATH, "wb").write(text.encode("utf-8"))
print("已写盘:", PATH)

chk = open(PATH, "rb").read().decode("utf-8")
for kw in ["def upright_tour_waypoints(treasure, line_clue=None, punch=False):",
           "def round1_return_extra_waypoints(treasure, line_clue, punch=False, tour=False):",
           "wp += round1_return_extra_waypoints(treasure, line_clue, punch, tour)"]:
    print("  回读 %-70s x%d" % (kw, chk.count(kw)))
print("  旧调用残留 p3p4_punch_waypoints 调用点 x%d（应为 0）" % chk.count("wp += p3p4_punch_waypoints"))
print("  旧调用残留 upright_tour_waypoints(treasure) x%d（应为 0）" % chk.count("wp += upright_tour_waypoints(treasure)"))
