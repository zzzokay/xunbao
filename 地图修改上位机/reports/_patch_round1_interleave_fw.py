# -*- coding: utf-8 -*-
"""一轮回程：把"补打卡 P3/P4"与"直立景点 S1/S2"改成**交错**，且 S1/S2 判据改为
"跟着这次回程会不会去 P3/P4 走"（不再看宝物值）。

改动（Mission/mission_planner.c，字节级替换）：
  1) 新增文件级小函数 append_round1_return_tail()（放在 #if USE_PLANNER_ROUTE 之前，
     两个回程函数共用）。
  2) plan_treasure_return()：两段 if 块 -> n = append_round1_return_tail(wp, n);
  3) route_return_home()：同上。
  4) 数组注释同步（S1 与 S2 现在可能同时出现）。

⚠️ 每个 old 片段必须恰好命中 1 次；全部成功才写盘。
"""
import io, os, sys

ROOT = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao"
PATH = os.path.join(ROOT, "Mission", "mission_planner.c")


def detect_eol(data: bytes) -> bytes:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    print("EOL: CRLF=%d LF-only=%d" % (crlf, lf))
    return b"\r\n" if crlf >= lf else b"\n"


raw = open(PATH, "rb").read()
eol = detect_eol(raw)
text = raw.decode("utf-8")


def b(s: str) -> str:
    """把片段里的 \\n 换成该文件真实行尾"""
    return s.replace("\n", "\r\n" if eol == b"\r\n" else "\n")


HELPER = b("""/**
 * @brief 一轮回程中"宝物平台之后、P2 之前"的那一段：交错安排补打卡 P3/P4 与直立景点 S1/S2
 * @param wp 必经点数组（调用方已写入宝物平台等前段）
 * @param n  当前已填数量
 * @return 追加后的 n
 * @note  2026-10-16 起 S1/S2 的判据**跟着"这次回程会不会去 P3/P4"走**，不再看宝物值：
 *          会去 P3 = 宝物平台就是 P3，或 补打卡开着且 QR 百位没走过 P3；会去 P4 同理。
 *          ⇒ 补打卡开着时两个景点都绕（3/4 都去）；关掉补打卡自动退回旧行为
 *            （宝物 P3→S1、P4→S2）。
 *        顺序固定 P3 -> S1 -> P4 -> S2，与二轮 get_newroute() 一致（避免交叉绕路）。
 *        ⚠️ 必须在宝物平台【之后】调用：取宝之前去任何平台 = 走错即结束比赛。
 *        ⚠️ 宝物平台本身（treasure==3/4）由调用方在其前面已加，这里只补另一个。
 */
static uint8_t append_round1_return_tail(u8 *wp, uint8_t n)
{
\tuint8_t goP3 = (treasure == 3) ||
\t\t(P3P4_PUNCH_ENABLE && flag_line_clue != 3 && treasure != 3);
\tuint8_t goP4 = (treasure == 4) ||
\t\t(P3P4_PUNCH_ENABLE && flag_line_clue != 4 && treasure != 4);

\tif (goP3 && treasure != 3)       wp[n++] = P3;
\tif (goP3 && UPRIGHT_TOUR_ENABLE) wp[n++] = S1;
\tif (goP4 && treasure != 4)       wp[n++] = P4;
\tif (goP4 && UPRIGHT_TOUR_ENABLE) wp[n++] = S2;
\treturn n;
}

""")

# ---- 1) 插小函数（锚点 = #if USE_PLANNER_ROUTE + 紧随其后的 plan_treasure_return 注释）----
anchor_c = b("""#if USE_PLANNER_ROUTE
/**
 * @brief P7/P8 得到宝物编号后规划回程（含宝物平台）""")
new_c = HELPER + anchor_c

# ---- 2) plan_treasure_return 两段 if 块 ----
old_a = b("""\t/* 一轮回程补打卡 P3/P4（缺哪个补哪个；见 config.h 的 P3P4_PUNCH_ENABLE）。
\t * QR 百位=3 ⇒ 去程已去过 P3、=4 ⇒ 已去过 P4、=0（正常固件默认）⇒ 两个都没去；
\t * 宝物平台就是它时也不重复加（回程本来就要去那儿打卡）。
\t * ⚠️ 必须插在宝物平台【之后】：取宝之前去任何平台 = 走错即结束比赛。
\t * ⚠️ 顺序固定 P3 -> P4，且排在 S1/S2 之前。 */
\tif (P3P4_PUNCH_ENABLE)
\t{
\t\tif (flag_line_clue != 3 && treasure != 3) wp[n++] = P3;
\t\tif (flag_line_clue != 4 && treasure != 4) wp[n++] = P4;
\t}

\t/* 直立景点巡回（S1/S2，见 config.h 的 UPRIGHT_TOUR_ENABLE）：
\t * 一轮【取宝之后】顺路去近的那一个 —— 宝物在 P3 绕 S1，在 P4 绕 S2。
\t * ⚠️ 必须插在宝物平台【之后】：取宝之前去任何平台/直立景点 = 走错即结束比赛。
\t * ⚠️ S1/S2 进边 func 是 View1（不是 View），动作待 do_Upright1()；本开关只管走位。 */
\tif (UPRIGHT_TOUR_ENABLE)
\t{
\t\tif (treasure == 3)      wp[n++] = S1;
\t\telse if (treasure == 4) wp[n++] = S2;
\t}
\twp[n++] = P2;""")
new_a = b("""\t/* 一轮回程：宝物平台之后，交错安排"补打卡 P3/P4"与"直立景点 S1/S2 巡回"。
\t * 判据与顺序见 append_round1_return_tail()（S1/S2 不再依赖宝物值）。 */
\tn = append_round1_return_tail(wp, n);
\twp[n++] = P2;""")

# ---- 3) route_return_home 两段 if 块 ----
old_b = b("""\t/* 宝物在 P5/P6 时本轮已到过，回程直接回家 */
\t/* 一轮回程补打卡 P3/P4：条件与位置同 plan_treasure_return()（取宝之后）。
\t * ⚠️ 两处都要插：回程过门时 door() 会重规划后半段，与本函数各管一段。 */
\tif (P3P4_PUNCH_ENABLE)
\t{
\t\tif (flag_line_clue != 3 && treasure != 3) wp[n++] = P3;
\t\tif (flag_line_clue != 4 && treasure != 4) wp[n++] = P4;
\t}
\t/* 直立景点巡回：条件与位置同 plan_treasure_return()（取宝之后）。
\t * ⚠️ 两处都要插：回程过门时 door() 会重规划后半段，但若该门边去程已被
\t *    door_set_pass_node() 改成 func=NONE，则不进 door()，只有本函数生效。 */
\tif (UPRIGHT_TOUR_ENABLE)
\t{
\t\tif (treasure == 3)      wp[n++] = S1;
\t\telse if (treasure == 4) wp[n++] = S2;
\t}
\twp[n++] = P2;""")
new_b = b("""\t/* 宝物在 P5/P6 时本轮已到过，回程直接回家 */
\t/* 一轮回程：补打卡 P3/P4 + 直立景点 S1/S2 交错，判据与顺序同 plan_treasure_return()。
\t * ⚠️ 两处都要插：回程过门时 door() 会重规划后半段，与本函数各管一段；
\t *    若该门边去程已被 door_set_pass_node() 改成 func=NONE，则不进 door()，只有本函数生效。 */
\tn = append_round1_return_tail(wp, n);
\twp[n++] = P2;""")

# ---- 4) 数组注释 ----
old_d = b("""\tu8 wp[10];   /* 补打卡 P3/P4 后最多 9 个点（start + P5/P6 + 门×2 + 宝物平台 + P3 + P4 + S1|S2 + P2），10 够 */""")
new_d = b("""\tu8 wp[10];   /* 补打卡 + 巡回交错后最多 9 个点（start + P5/P6 + 门×2 + 宝物平台 + P3 + S1 + P4 + S2 + P2），10 够 */""")

old_e = b("""\tu8 wp[8];   /* ⚠️ 原为 wp[3]：插直立景点后 4 个点；再加补打卡 P3/P4 最多 6 个 —— 留到 8 */""")
new_e = b("""\tu8 wp[8];   /* ⚠️ 原为 wp[3]：插直立景点 + 补打卡交错后最多 7 个点 —— 留到 8 */""")

edits = [("C-插入共享小函数", anchor_c, new_c),
         ("A-plan_treasure_return", old_a, new_a),
         ("B-route_return_home", old_b, new_b),
         ("D-wp[10] 注释", old_d, new_d),
         ("E-wp[8] 注释", old_e, new_e)]

ok = True
for name, old, new in edits:
    c = text.count(old)
    print("%-26s count=%d" % (name, c))
    if c != 1:
        ok = False
if not ok:
    print("!! 有片段命中次数 != 1，未写盘")
    sys.exit(1)

for name, old, new in edits:
    text = text.replace(old, new, 1)

out = text.encode("utf-8")
open(PATH, "wb").write(out)
print("已写盘:", PATH, len(raw), "->", len(out))

# 回读校验
chk = open(PATH, "rb").read().decode("utf-8")
for kw in ["append_round1_return_tail(u8 *wp, uint8_t n)",
           "goP3", "goP4",
           "n = append_round1_return_tail(wp, n);"]:
    print("  回读 %-40s x%d" % (kw, chk.count(kw)))
