# -*- coding: utf-8 -*-
"""把「flag 判据位 ↔ 循迹板灯位」对照写进两份讲解文档（字节级替换，保持 CRLF）。全部命中才写盘。"""
import os

DOC = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao\项目讲解文档"
CRLF = "\r\n"
README = "README.md"
PR = "project_reference.md"


def load(p):
    return open(os.path.join(DOC, p), "rb").read().decode("utf-8")


def save(p, text):
    open(os.path.join(DOC, p), "wb").write(text.encode("utf-8"))


patches = []

# ---------- README §5 新增第 11 条 ----------
old5 = ("    反过来 **`angle` 是干净的**：52 个双向段里 **49 段严格互为反向**（差 180°），"
        "可直接当几何量用（详见 `project_reference.md` §14.9）。" + CRLF)
new5 = old5 + (
    "11. **`flag` 里每个「到达判据位」都对应循迹板上具体的那几路灯**（板装在**车头**，"
    "`detail` 的 **bit15 = 最左 1 号灯 … bit0 = 最右 16 号灯**；"
    "依据 `scaner.c` 的 `line_weight_default[16]` 从左到右是 −3…+3、"
    "`calc_track_all()` 用 `line_weight[i]` 配 `detail >> (sensorNum-1-i)`）。"
    "完整对照表见 `project_reference.md` §6。三条最容易记错的：" + CRLF +
    "    - `DLEFT`/`DRIGHT` = **左/右各 6 灯里 ≥5 灯亮**（不是「任意一侧」）；「全板 ≥5」是 `MORELED`。" + CRLF +
    "    - `AWHITE` 名叫「全白」，**实际查的是正中间连续 10 灯**（`0x1FF8`）。" + CRLF +
    "    - ⚠️ `CRIGHT` 的源码注释写「右起 2 和 3 灯」，但代码 `detail & 0xc` = bit2/bit3 = **左起 13/14 号** —— "
    "**差一位，以代码为准**。" + CRLF +
    "    历史教训：`DLEFT`/`DRIGHT` 曾在 P6 被放宽，现场把「斜线亮 4 灯」当成右直线 ⇒ 提前转弯"
    "（见 `交接专用文档（新人先看我）.md` 开头第 2 条）。" + CRLF)
patches.append((README, old5, new5))

# ---------- README §9 追加一行 ----------
old9 = ("（实车吃默认 19），且 `N10`(deg=10) 是主干枢纽里唯一无条目的（§5.10 / §6.1 / PR §14.9）" + CRLF)
new9 = old9 + (
    "- **2026-09-29**：把「`flag` 到达判据位 ↔ 循迹板灯位」的对照第一次写进文档【仅文档】—— "
    "确认 `detail` 的 **bit15 = 最左 1 号灯、bit0 = 最右 16 号灯**"
    "（依据 `scaner.c` 的 `line_weight_default[16]` = −3…+3 与 `calc_track_all()` 的 "
    "`line_weight[i] ↔ detail>>(sensorNum-1-i)`），据此列出 10 条判据各自看哪几路灯；"
    "顺带查出 **`CRIGHT` 的源码注释「右起 2 和 3 灯」与代码 `0xc`（= 左起 13/14 号）差一位**，"
    "以及 `AWHITE` 名为「全白」实查正中连续 10 灯（`0x1FF8`）（§5.11 / PR §6）" + CRLF)
patches.append((README, old9, new9))

# ---------- PR §6 末尾追加灯位对照 ----------
old6 = ("三条链路各自「一轮干等 `MAIXCAM_QR/OCR/COLOR_WAIT_TICKS`(800/800/1000)」，"
        "但**轮内每约 0.48s 重发一次模式指令**（`barrier.c` 顶部的 `MAIXCAM_RESEND_TICKS_3MS`/`_2MS`）"
        "⇒ 轮内 open 次数 1→5，见 `README.md` §2.20。" + CRLF)
new6 = old6 + CRLF + (
    "**16 路灯位 ↔ 到达判据（`deal_arrive()`）** —— 循迹板装在**车头**，"
    "`detail` 的 **bit15 = 最左（1 号灯）… bit0 = 最右（16 号灯）**"
    "（依据：`scaner.c` 的 `line_weight_default[16]` 从左到右是 −3…+3，"
    "`calc_track_all()` 用 `line_weight[i]` 配 `detail >> (sensorNum-1-i)`）。" + CRLF + CRLF +
    "| 判据位 | 掩码 | 看的灯（左→右 1~16） | 触发条件 |" + CRLF +
    "|---|---|---|---|" + CRLF +
    "| `DLEFT` | `0xFC00` | 1~6（左 6） | 这 6 里 ≥5 亮 且 `ledNum ≥ 5` |" + CRLF +
    "| `DRIGHT` | `0x003F` | 11~16（右 6） | 这 6 里 ≥5 亮 且 `ledNum ≥ 5` |" + CRLF +
    "| `CLEFT` | `0x6000` | **2 或 3** | 任一亮 且 `4 ≤ ledNum ≤ 7` |" + CRLF +
    "| `MCLEFT` | `0x8000` | **1（最左单灯）** | 亮 且 `4 ≤ ledNum ≤ 7` |" + CRLF +
    "| `MCRIGHT` | `0x0001` | **16（最右单灯）** | 亮 且 `4 ≤ ledNum ≤ 7` |" + CRLF +
    "| `CRIGHT` | `0x000C` | **13 或 14** | 任一亮 且 `4 ≤ ledNum ≤ 7` |" + CRLF +
    "| `MORELED` | — | 不挑位置 | `ledNum ≥ 5` |" + CRLF +
    "| `AWHITE` | `0x1FF8` | **4~13（正中间 10 灯）全亮** | `ledNum ≥ 10` |" + CRLF +
    "| `MUL2SING` | — | 时序（看 `lineNum`） | 连续 >4 帧 `lineNum>1 && ledNum≥4` → 再变 `lineNum==1` |" + CRLF +
    "| `MUL2MUL` | — | 时序（看 `lineNum`） | 多 → 单 → 多，三段各 >4 帧 |" + CRLF + CRLF +
    "⚠️ `CRIGHT` 的源码注释写「右起 2 和 3 灯」，但掩码 `0xc` = bit2/bit3 = **左起 13/14 号** —— "
    "**注释与代码差一位，以代码为准**。" + CRLF +
    "⚠️ `MC*`/`C*` 这四条都带 `4 ≤ ledNum ≤ 7`：**先要求「车确实压着主线」** 才认岔路。"
    "这条是踩出来的 —— `DLEFT`/`DRIGHT` 曾在 P6 被放宽，现场把「斜线亮 4 灯」当成右直线 ⇒ 提前转弯"
    "（见 `交接专用文档（新人先看我）.md` 开头第 2 条）。" + CRLF +
    "⚠️ **命中顺序 = `deal_arrive()` 的 if 链顺序 = 优先级**："
    "`DLEFT → DRIGHT → CLEFT → MCLEFT → MCRIGHT → CRIGHT → MORELED → AWHITE → MUL2SING → MUL2MUL`"
    "（多判据同时成立时，先命中的才写进 `arrive_method`，§14 的补偿 `d` 就按它选档）。" + CRLF)
patches.append((PR, old6, new6))

# ---------- 执行（全部命中才写盘）----------
texts = {}
for fname, old, new in patches:
    if fname not in texts:
        texts[fname] = load(fname)
    n = texts[fname].count(old)
    assert n == 1, "锚点命中 %d 次（应为 1）：%s / %r" % (n, fname, old[:60])
    texts[fname] = texts[fname].replace(old, new)
    print("[ok] %s <- %r..." % (fname, old[:38]))

for fname, text in texts.items():
    d = text.encode("utf-8")
    crlf = d.count(b"\r\n")
    lf = d.count(b"\n") - crlf
    assert lf == 0, "%s 出现 %d 个裸 LF" % (fname, lf)
    save(fname, text)
    print("[write] %s  (%d 行 CRLF, 0 裸 LF)" % (fname, crlf))
print("done")
