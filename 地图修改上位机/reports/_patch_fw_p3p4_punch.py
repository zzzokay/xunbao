# -*- coding: utf-8 -*-
"""AI 过程脚本：固件新增 `P3P4_PUNCH_ENABLE`（一轮回程补打卡 P3/P4）。

改动（字节级替换，各自保持行尾）：
  A. Mission/config.h        (LF+BOM) ：加开关块，默认 0。
  B. Mission/mission_planner.c (CRLF) ：
     - plan_treasure_return() 与 route_return_home() 各插一段"缺哪个补哪个"的 P3/P4；
     - wp 容量：plan_treasure_return 注明上限、route_return_home wp[6] -> wp[8]。
每个替换 assert 命中恰好 1 次，两个文件都成功才写盘。
"""
import os

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"
CFG = os.path.join(ROOT, "Mission", "config.h")
MP = os.path.join(ROOT, "Mission", "mission_planner.c")

PUNCH_BODY = (
    "if (P3P4_PUNCH_ENABLE)\n"
    "{\n"
    "if (flag_line_clue != 3 && treasure != 3) wp[n++] = P3;\n"
    "if (flag_line_clue != 4 && treasure != 4) wp[n++] = P4;\n"
    "}\n"
)

# ---------------- A. config.h ----------------
CFG_OLD = "#define UPRIGHT_TOUR_ENABLE  0\n"
CFG_NEW = (
    "#define UPRIGHT_TOUR_ENABLE  0\n"
    "\n"
    "/* ===================== 一轮回程补打卡 P3/P4 =====================\n"
    " * 1 = 一轮【取宝之后】的回家腿，把去程没去的 P3/P4 补上再回家（**缺哪个补哪个**）：\n"
    " *     QR 百位=3（去过 P3）只补 P4、=4（去过 P4）只补 P3、\n"
    " *     =0（正常固件默认，一轮去程根本不经过 P3/P4）两个都补；\n"
    " *     宝物平台正好是它时不重复加（回程本来就要去那儿打卡）。\n"
    " *     顺序固定 P3 -> P4，且排在 S1/S2（UPRIGHT_TOUR_ENABLE）之前。\n"
    " * 0 = 完全保持原行为（回程只去宝物平台）。\n"
    " * ⚠️ 打开会改掉门回程路线 ⇒ validate/_check_door_perm.py 的 12 条 golden 不再适用（需按新语义重算）。 */\n"
    "#define P3P4_PUNCH_ENABLE  0\n"
)

# ---------------- B. mission_planner.c（CRLF） ----------------
MP_EDITS = []

# B1) wp[10] 注明上限
MP_EDITS.append((
    "\tu8 wp[10];\n"
    "\tuint8_t n = 0;\n"
    "\tuint8_t target;\n",
    "\tu8 wp[10];   /* 补打卡 P3/P4 后最多 9 个点（start + P5/P6 + 门×2 + 宝物平台 + P3 + P4 + S1|S2 + P2），10 够 */\n"
    "\tuint8_t n = 0;\n"
    "\tuint8_t target;\n",
))

# B2) route_return_home 的 wp[6] -> wp[8]
MP_EDITS.append((
    "\tu8 wp[6];   /* ⚠️ 原为 wp[3]：插直立景点后最多 4 个点，3 会溢出（踩栈） */\n",
    "\tu8 wp[8];   /* ⚠️ 原为 wp[3]：插直立景点后 4 个点；再加补打卡 P3/P4 最多 6 个 —— 留到 8 */\n",
))

# B3) 插点①：plan_treasure_return（宝物平台之后、S1/S2 之前）
MP_EDITS.append((
    "\t/* 添加非特殊平台的宝物目标 */\n"
    "\tif (treasure != 5 && treasure != 6)\n"
    "\t\twp[n++] = target;\n"
    "\n"
    "\t/* 直立景点巡回（S1/S2，见 config.h 的 UPRIGHT_TOUR_ENABLE）：\n",
    "\t/* 添加非特殊平台的宝物目标 */\n"
    "\tif (treasure != 5 && treasure != 6)\n"
    "\t\twp[n++] = target;\n"
    "\n"
    "\t/* 一轮回程补打卡 P3/P4（缺哪个补哪个；见 config.h 的 P3P4_PUNCH_ENABLE）。\n"
    "\t * QR 百位=3 ⇒ 去程已去过 P3、=4 ⇒ 已去过 P4、=0（正常固件默认）⇒ 两个都没去；\n"
    "\t * 宝物平台就是它时也不重复加（回程本来就要去那儿打卡）。\n"
    "\t * ⚠️ 必须插在宝物平台【之后】：取宝之前去任何平台 = 走错即结束比赛。\n"
    "\t * ⚠️ 顺序固定 P3 -> P4，且排在 S1/S2 之前。 */\n"
    "\tif (P3P4_PUNCH_ENABLE)\n"
    "\t{\n"
    "\t\tif (flag_line_clue != 3 && treasure != 3) wp[n++] = P3;\n"
    "\t\tif (flag_line_clue != 4 && treasure != 4) wp[n++] = P4;\n"
    "\t}\n"
    "\n"
    "\t/* 直立景点巡回（S1/S2，见 config.h 的 UPRIGHT_TOUR_ENABLE）：\n",
))

# B4) 插点②：route_return_home（宝物平台之后、S1/S2 之前）
MP_EDITS.append((
    "\t/* 宝物在 P5/P6 时本轮已到过，回程直接回家 */\n"
    "\t/* 直立景点巡回：条件与位置同 plan_treasure_return()（取宝之后）。\n",
    "\t/* 宝物在 P5/P6 时本轮已到过，回程直接回家 */\n"
    "\t/* 一轮回程补打卡 P3/P4：条件与位置同 plan_treasure_return()（取宝之后）。\n"
    "\t * ⚠️ 两处都要插：回程过门时 door() 会重规划后半段，与本函数各管一段。 */\n"
    "\tif (P3P4_PUNCH_ENABLE)\n"
    "\t{\n"
    "\t\tif (flag_line_clue != 3 && treasure != 3) wp[n++] = P3;\n"
    "\t\tif (flag_line_clue != 4 && treasure != 4) wp[n++] = P4;\n"
    "\t}\n"
    "\t/* 直立景点巡回：条件与位置同 plan_treasure_return()（取宝之后）。\n",
))


def patch(path, edits, eol):
    with open(path, "rb") as f:
        data = f.read()
    for old, new in edits:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "%s 命中 %d 次（期望 1）:\n%r" % (path, cnt, old[:70])
        data = data.replace(ob, nb)
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    with open(path, "wb") as f:
        f.write(data)
    print("[ok] %-22s crlf=%d lf=%d bom=%s" % (os.path.basename(path), crlf, lf,
                                               data[:3] == b"\xef\xbb\xbf"))


def main():
    patch(CFG, [(CFG_OLD, CFG_NEW)], "\n")
    with open(CFG, "rb") as f:
        c = f.read()
    assert c.count(b"\r\n") == 0 and c[:3] == b"\xef\xbb\xbf", "config.h 行尾/BOM 被破坏"
    patch(MP, MP_EDITS, "\r\n")
    with open(MP, "rb") as f:
        m = f.read()
    assert m.count(b"\n") - m.count(b"\r\n") == 0, "mission_planner.c 出现裸 LF"
    assert m.count(b"P3P4_PUNCH_ENABLE") == 3, "mission_planner.c 里应有 3 处引用"
    print("两个固件文件都已写盘。")


if __name__ == "__main__":
    main()
