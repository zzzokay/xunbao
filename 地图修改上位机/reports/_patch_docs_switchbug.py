# -*- coding: utf-8 -*-
"""AI 过程脚本：文档/笔记 —— 记「跟随 config.h 恒等于关」这个坑 + 项数刷新。

⚠️ AI_CONTEXT §9 是 markdown 表格：单元格**必须单行**，别往行里插换行（会把表格拆掉）。
"""
import os

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"
P = os.path.join(ROOT, "项目讲解文档", "README.md")
R = os.path.join(ROOT, "地图修改上位机", "map_editor", "README.md")
A = os.path.join(ROOT, "地图修改上位机", "map_editor", "AI_CONTEXT.md")
M = os.path.join(ROOT, ".workbuddy", "memory", "MEMORY.md")
D = os.path.join(ROOT, ".workbuddy", "memory", "2026-10-07.md")

R_OLD = """  （282 项；**当前 281 OK / 1 FAIL**：`D5黑+D4绿` 那条是**既有**的（边表/权重 WIP），不是本功能引入的）。
"""
R_NEW = """  **两个开关下拉直接显示 config.h 当前值**（`跟随 config.h（当前：开/关）`，免得「跟随了却不知是开是关」）
  （284 项；**当前 283 OK / 1 FAIL**：`D5黑+D4绿` 那条是**既有**的（边表/权重 WIP），不是本功能引入的）。
"""

R2_OLD = """| `_guismoke.py` | 界面冒烟测试（282 项；"""
R2_NEW = """| `_guismoke.py` | 界面冒烟测试（284 项；"""

A1_OLD = """| `_guismoke.py` | 界面冒烟测试（282 项），"""
A1_NEW = """| `_guismoke.py` | 界面冒烟测试（284 项），"""

A2_OLD = """python 地图修改上位机/map_editor/_guismoke.py     # 282 项（当前 281 OK / 1 FAIL：`D5黑+D4绿` 那条既有 WIP）
"""
A2_NEW = """python 地图修改上位机/map_editor/_guismoke.py     # 284 项（当前 283 OK / 1 FAIL：`D5黑+D4绿` 那条既有 WIP）
"""

A3_OLD = """改完跑 `_guismoke` 的「round-1/2: upright tour S1/S2」段 + `tools/sim_upright_tour.py` |
"""
A3_NEW = """改完跑 `_guismoke` 的「round-1/2: upright tour S1/S2」段 + `tools/sim_upright_tour.py`。⚠️ 三条硬规矩：① **`M.parse_config_macros()` 返回 `(macros, field_name)` 二元组**，取宏要 `[0]`；② **别写 `except: return False`** —— 踩过：开关下拉的「跟随 config.h」漏了 `[0]`，`eval_c_expr` 抛的异常被吞掉 ⇒ **恒等于「关」**（用户报「S1/S2 路线没画出来」）；③ 断言**别与实现同源**（那次 `_guismoke` 调的是同一个错 API ⇒ 两边一起错 ⇒ 自测假通过），现在多一条**独立**校验（按文本读 config.h 的 0/1）|
"""

M_OLD = """  右边整段看不见（用户报「打开不能完整显示内容」）。长文本记得 `wraplength`。`_guismoke` 有断言守着。
"""
M_NEW = """  右边整段看不见（用户报「打开不能完整显示内容」）。长文本记得 `wraplength`。`_guismoke` 有断言守着。
- ⚠️ **`M.parse_config_macros()` 返回 `(macros, field_name)` 二元组** —— 取宏要 `[0]`；**别用 `except: return False` 吞异常**。
  踩过（10-07）：开关下拉的「跟随 config.h」漏了 `[0]` ⇒ `eval_c_expr` 抛 TypeError 被吞 ⇒ **恒等于「关」**，
  用户把 `config.h` 打开成 1、下拉留在跟随档也什么都不发生（报「S1/S2 路线没画出来」）。
  ⇒ 断言**别与实现同源**（那次 `_guismoke` 调同一个错 API，两边一起错 ⇒ 假通过）；现在有一条**独立**校验。
"""

S9 = """- **2026-10-07**：修「跟随 config.h」恒等于「关」【仅上位机】—— 用户报「S1/S2 路线没画出来，实际规划也没有 S1/S2（第一轮回程）」。
查证：镜像与插点都**是对的**（`tour=True` + 宝物 P3/P4 时 `route[]` 里确实有 `S1`/`S2`；`reports/_diag_s1_in_route.py`），
问题在**开关没生效**：`_switch_on()` 里 `M.parse_config_macros()` **返回 `(macros, field_name)` 二元组**，漏了 `[0]`
⇒ `eval_c_expr` 抛异常被 `except: return False` **吞掉** ⇒ 「跟随 config.h」**恒为关**（`config.h` 里其实是 1）。
而 `_guismoke` 的断言调的是同一个错 API ⇒ **两边一起错、自测假通过**。改法：取 `[0]`、异常改成**报状态栏**不再静默、
断言换**独立**口径（按文本读 config.h 的 0/1），并让下拉文字直接显示 `跟随 config.h（当前：开/关）`。
另：一轮回程绕 S1/S2 **只在宝物 = P3 / P4 时**（固件规则 `treasure==3→S1` / `==4→S2`），宝物在 P1/P5/P6/未定时**本来就不绕**。
端到端（跟随=开）：宝物 未定/P1/P5/P6 → `S1/S2=无` 而 `P3、P4 都在`；宝物 P3 → `S1`；宝物 P4 → `S2`。
`_guismoke` ⇒ **284 项（283 OK / 1 项既有 FAIL）**。
"""

LOG = """
## 修「跟随 config.h」恒等于关（用户报 S1/S2 没画出来）【仅上位机】

- **用户报**：「S1S2 的路线没有画出来，实际规划的路线好像也没有 S1 和 S2，就第一轮回程的时候」。
- **先查镜像**（`reports/_diag_s1_in_route.py`）：**镜像是对的** —— `tour=True` 且宝物=P3/P4 时，
  三个「第一轮」阶段的 `route[]` 里都有 S1/S2（如门区回程 宝物=P3 ⇒ `N3 → P3 → S1 → P2`）。
- **真因**：`App._switch_on()` 里 `M.parse_config_macros()` 返回 **(macros, field_name) 二元组**，漏了 `[0]`
  ⇒ `eval_c_expr(macro, tuple)` 抛 `TypeError` ⇒ 被 `except Exception: return False` **静默吞掉**
  ⇒ **「跟随 config.h」恒等于关**。用户那会儿 `config.h` 里已经是 1，所以跟着走一路不生效。
  ⚠️ 更坏的是：`_guismoke` 那两条断言**调的是同一个错 API** ⇒ 两边一起错 ⇒ 自测**假通过**（上一轮我汇报「当前=0」就是假的）。
- **改法**：① `_switch_on` 取 `macros, _field = M.parse_config_macros()` 用 `[0]`；
  ② 异常不再静默 —— 改成 `self.status("⚠ 读 config.h 的 X 失败（按关处理）")`；
  ③ `_guismoke` 的读值补 `[0]`，并新增一条**独立**校验（按文本拆 config.h 的 `#define X 0/1`，不走 `parse_config_macros`）；
  ④ 下拉文字直接显示当前值：`跟随 config.h（当前：开）`。
- **端到端**（`reports/_diag_e2e_switch.py`，按对话框默认档）：宝物 未定/P1/P5/P6 ⇒ `S1/S2=无`（P3、P4 都在）；
  宝物 **P3 ⇒ S1**、**P4 ⇒ S2**。⇒ 与固件规则一致：**一轮只有宝物在 P3/P4 才绕**。
- **验证**：`_guismoke` **283 OK / 1 既有 FAIL**（`D5黑+D4绿`）。
- 脚本：`reports/_patch_switch_show_current.py` / `_patch_switch_follow_cfg_bug.py` /
  `_diag_s1_in_route.py` / `_diag_e2e_switch.py`。
"""


def apply(path, edits, eol):
    with open(path, "rb") as f:
        data = f.read()
    for old, new in edits:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "%s 命中 %d 次:\n%r" % (os.path.basename(path), cnt, old[:80])
        data = data.replace(ob, nb)
    with open(path, "wb") as f:
        f.write(data)
    print("[ok] %-14s crlf=%d lf=%d" % (os.path.basename(path), data.count(b"\r\n"),
                                        data.count(b"\n") - data.count(b"\r\n")))


def append(path, text, eol):
    with open(path, "rb") as f:
        d = f.read()
    with open(path, "wb") as f:
        f.write(d + text.replace("\n", eol).encode("utf-8"))
    print("[ok] %-14s 追加" % os.path.basename(path))


apply(R, [(R_OLD, R_NEW), (R2_OLD, R2_NEW)], "\n")
apply(A, [(A1_OLD, A1_NEW), (A2_OLD, A2_NEW), (A3_OLD, A3_NEW)], "\n")
apply(M, [(M_OLD, M_NEW)], "\n")
append(P, S9, "\r\n")
append(D, LOG, "\n")
print("文档补丁已写盘。")
