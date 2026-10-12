# -*- coding: utf-8 -*-
"""AI 过程脚本：把 `UPRIGHT_NEED_TREASURE` 加回成真开关。

改动（字节级替换，各自保持原行尾）：
  A. Mission/config.h  (LF + BOM) ：在 UPRIGHT_TOUR_ENABLE 块之前，恢复被 09307f5 删掉的
     `UPRIGHT_NEED_TREASURE` 块，默认 1（= 保持当前"取宝后才做直立景点动作"的行为）。
  B. Mission/barrier.c (CRLF)     ：`if (!treasure_taken)` → `if (UPRIGHT_NEED_TREASURE && !treasure_taken)`
     + 恢复被删掉的说明注释（含"别用 #if 当门控"护栏）。

每个替换 assert 命中恰好 1 次；两个文件都成功才写盘。
"""
import os

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"
CFG = os.path.join(ROOT, "Mission", "config.h")
BAR = os.path.join(ROOT, "Mission", "barrier.c")

# ---------------- A. config.h（LF + BOM） ----------------
CFG_OLD = (
    "/* ===================== 直立景点巡回 S1/S2（View1 通道）=====================\n"
)

CFG_NEW = (
    "/* ===================== 直立景点（View，N14/N16）触发条件 =====================\n"
    " * 1 = 只有\"已经拿到宝藏\"之后才做直立景点动作（一轮取宝后的回程 + 第二轮）；\n"
    " *     一轮去程（还没取宝）经过 N12->N16 / C3->N14 时不做动作，当普通节点直穿。\n"
    " * 0 = 恢复旧行为（边表 func=View 就做，含一轮去程）。\n"
    " * 依据：一轮去程 N5->N12->N13->P5->N13->N12->N16 会在取宝前经过 N16。\n"
    " * 落点与验证见 project_reference.md §11 / README.md §2.14 */\n"
    "#define UPRIGHT_NEED_TREASURE  1\n"
    "\n"
    + CFG_OLD
)

# ---------------- B. barrier.c（CRLF） ----------------
BAR_OLD = (
    "\tif (!treasure_taken)\r\n"
    "\t{\r\n"
    "\t\tprintf(\"[UPRIGHT] skipped: treasure not collected yet\\r\\n\");\r\n"
    "\t\treturn;\r\n"
    "\t}\r\n"
)

BAR_NEW = (
    "\t/* 【取宝门控】一轮去程还没拿到宝藏时不执行直立景点动作：\n"
    "\t   东区入口边 N12->N16 的 func=View，取宝前就会经过它，此时应当只当普通节点直穿，\n"
    "\t   动作留到\"取宝后的回程\"与\"第二轮\"再做（开关 UPRIGHT_NEED_TREASURE，见 config.h）。\n"
    "\t   ⚠️ 判据是 treasure_taken（取宝完成标志），不能用 treasure != 0：\n"
    "\t      treasure 只是线索算出的宝物平台编号，一轮回程 N18->N16 时宝还在平台上。\n"
    "\t   ⚠️ 这里只 return：不写 cross_event、不清 function —— 到达判定交回 ArriveDetect_task，\n"
    "\t      与\"这条边本来就没有景点\"的行为一致。\n"
    "\t   ⚠️ 故意不用 #if：宏名写错 / 头文件没包含时 #if 会静默当 0，护栏白写；\n"
    "\t      写成运行期常量判断，宏没定义会直接编译报错。 */\n"
    "\tif (UPRIGHT_NEED_TREASURE && !treasure_taken)\n"
    "\t{\n"
    "\t\tprintf(\"[UPRIGHT] skipped: treasure not collected yet\\r\\n\");\n"
    "\t\treturn;\n"
    "\t}\n"
).replace("\n", "\r\n")


def patch(path, old, new, eol_name):
    with open(path, "rb") as f:
        data = f.read()
    ob = old.encode("utf-8")
    nb = new.encode("utf-8")
    cnt = data.count(ob)
    assert cnt == 1, "%s 命中 %d 次（期望 1）\n%r" % (path, cnt, old[:80])
    out = data.replace(ob, nb)
    # 行尾自检：不得引入第二种行尾
    crlf = out.count(b"\r\n")
    lf = out.count(b"\n") - crlf
    bom = out[:3] == b"\xef\xbb\xbf"
    with open(path, "wb") as f:
        f.write(out)
    print("[ok] %-24s %s  crlf=%d lf=%d bom=%s  (+%d bytes)"
          % (os.path.basename(path), eol_name, crlf, lf, bom, len(out) - len(data)))
    return out


def main():
    a = patch(CFG, CFG_OLD, CFG_NEW, "LF+BOM")
    assert a.count(b"\r\n") == 0 and a[:3] == b"\xef\xbb\xbf", "config.h 行尾/BOM 被破坏"
    b = patch(BAR, BAR_OLD, BAR_NEW, "CRLF")
    assert b.count(b"\n") - b.count(b"\r\n") == 0, "barrier.c 出现裸 LF"
    print("两个文件都已写盘。")


if __name__ == "__main__":
    main()
