# -*- coding: utf-8 -*-
"""文档同步：差异报告新增「宏定义差异」；计数 241->244；当日日志。"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

def load(p):
    return open(p, "rb").read().decode("utf-8")

def save(p, s):
    open(p, "wb").write(s.encode("utf-8"))

R = "地图修改上位机/map_editor/README.md"
AI = "地图修改上位机/map_editor/AI_CONTEXT.md"
PR = "项目讲解文档/README.md"
ME = ".workbuddy/memory/MEMORY.md"
DY = ".workbuddy/memory/2026-10-07.md"

R_SEC_OLD = '''**「查看代码差异」按钮**（工具栏第 2 行，只读）把**当前模型 vs 固件源码**比一遍：
枚举节点、边表、`NAV_EDGE_COUNT`，**以及转弯补偿** —— 表1/表2 的 **新增 / 删除 / 改值** + 公式参数 + `TURN_CALC_ENABLE` 开关（源 `model.turn` 对比 `M.parse_turn_tables()`）。
它比的是**源码**，所以顺手能看出"启动自动载入的布局 / 补偿表是不是已经和固件不一样了"。
纯函数 `M.turn_diff()` / `M.turn_diff_lines()` 负责算与排版（无 Tk，`_guismoke` 有断言）。
'''
R_SEC_NEW = '''**「查看代码差异」按钮**（工具栏第 2 行，只读）把**当前模型 vs 固件源码**比一遍，共四段：
枚举节点、边表、`NAV_EDGE_COUNT`、**宏定义（`config.h`）**、**转弯补偿**。
- **转弯补偿**：表1/表2 的 **新增 / 删除 / 改值** + 公式参数 + `TURN_CALC_ENABLE` 开关（源 `model.turn` 对比 `M.parse_turn_tables()`）。
- **宏定义**：`config.h` 里宏的 **新增 / 删除 / 改值**（源 `model.macros` 对比 `M.parse_config_macros()`）。
  按**去空白后的文本**比 —— 宏可能是表达式（`(LEN_N22B7 - 20)`）、带后缀（`1.2f`）或别的宏名，**不拆成数字**。
它比的是**源码**，所以顺手能看出"启动自动载入的布局 / 补偿表 / 宏是不是已经和固件不一样了"。
纯函数 `M.turn_diff()` / `M.turn_diff_lines()` / `M.macros_diff()` / `M.macros_diff_lines()` 负责算与排版（无 Tk，`_guismoke` 有断言）。
'''

R_C1_OLD = "新入口在界面上真的可见**（241 项）。"
R_C1_NEW = "新入口在界面上真的可见**（244 项）。"
R_C2_OLD = "| `_guismoke.py` | 界面冒烟测试（241 项；"
R_C2_NEW = "| `_guismoke.py` | 界面冒烟测试（244 项；"

AI_C1_OLD = "| `_guismoke.py` | 界面冒烟测试（241 项）"
AI_C1_NEW = "| `_guismoke.py` | 界面冒烟测试（244 项）"
AI_C2_OLD = "_guismoke.py     # 期望：241 项 [OK] / 0 FAIL"
AI_C2_NEW = "_guismoke.py     # 期望：244 项 [OK] / 0 FAIL"

AI_MAC_OLD = "| 改宏解析 | `parse_config_macros()` / `_CExpr` | 见 §6.4 两个坑；求值器不要改回 `eval`+文本替换 |"
AI_MAC_NEW = "| 改宏解析 | `parse_config_macros()` / `_CExpr`；差异对比 `macros_diff()` / `macros_diff_lines()` | 见 §6.4 两个坑；求值器不要改回 `eval`+文本替换。「查看代码差异」的宏段按**去空白文本**比（宏可以是表达式 / 带后缀 / 别的宏名，别拆数字） |"

ME_OLD = "（241 项，界面）"
ME_NEW = "（244 项，界面）"

PR_LINE = ("- **2026-10-07**：「查看代码差异」再加上「宏定义差异」段【仅上位机】—— 上一轮补了转弯补偿；这轮用户要求\"宏定义啥的也"
           "显示进去\"。新增纯函数 `map_model.macros_diff()`（按**去空白文本**比 `model.macros` 与 `config.h` 的 "
           "`parse_config_macros()`：新增/删除/改值）/ `macros_diff_lines()`；`report_source_diff()` 输出「宏定义差异」段，"
           "\"内容一致\"判据纳入 `macro_same`。`_guismoke` 加 3 条断言 ⇒ **244 项 [OK] / 0 FAIL**。")

DAY = ("\n## 「查看代码差异」加「宏定义差异」段【仅上位机】\n\n"
"- **用户要求**：差异里把**宏定义**也显示进去。\n"
"- **改法**：`map_model.py` 新增 `macros_diff(cur, src)`（cur/src = {名字: 值文本}，按**去空白文本**比 —— 宏可能是表达式 "
"`(LEN_N22B7 - 20)`、带后缀 `1.2f`、或别的宏名，**不拆数字**）+ `macros_diff_lines()`。`map_editor.report_source_diff()` "
"增 `M.parse_config_macros()` 取源码宏，在转弯补偿段后输出「宏定义差异」段，并把\"内容一致\"判据加上 `macro_same`。\n"
"- **验证**：`_guismoke` +3（自比 same / 改一个宏报改值 / 报告含该段）⇒ **244 项 [OK] / 0 FAIL**；端到端脚本 "
"`reports/_check_turndiff.py` 实跑并把报告存 `reports/查看代码差异_报告示例.txt`。\n"
"- **实测顺带发现**：`default.json` 布局里的宏快照与当前 `config.h` 已有出入（`UPRIGHT_NEED_TREASURE` 只在模型里有；"
"`OCR_HEAD_NEAR_LEFT/RIGHT`、`LEN_B5N19` 等值不同）—— 正是这个功能要暴露的。\n"
"- **文档**：`map_editor/README.md` §7 + 计数 241→244、`AI_CONTEXT.md`（计数 + 改宏解析行）、`项目讲解文档/README.md` §9、`MEMORY.md`。\n")

edits = [(R, R_SEC_OLD, R_SEC_NEW), (R, R_C1_OLD, R_C1_NEW), (R, R_C2_OLD, R_C2_NEW),
         (AI, AI_C1_OLD, AI_C1_NEW), (AI, AI_C2_OLD, AI_C2_NEW), (AI, AI_MAC_OLD, AI_MAC_NEW),
         (ME, ME_OLD, ME_NEW)]

plan = []
for p, old, new in edits:
    n = load(p).count(old)
    plan.append((p, old, new, n))
    print("[check] %-18s count=%d %s | %s" % (p.split("/")[-1], n,
          "OK" if n == 1 else "!!", old.strip().splitlines()[0][:40]))
if any(x[3] != 1 for x in plan):
    print("\n有串未唯一命中，未写盘。"); sys.exit(1)

buf = {}
for p, old, new, n in plan:
    buf[p] = buf.get(p, load(p)).replace(old, new, 1)
for p, s in buf.items():
    save(p, s); print("[write]", p)

s = load(PR)
if PR_LINE[:34] in s:
    print("[skip] 日志行已存在")
else:
    save(PR, s + "\r\n" + PR_LINE); print("[write]", PR, "(+1 log line)")

s = load(DY)
if "加「宏定义差异」段" in s:
    print("[skip] 当日日志已记")
else:
    save(DY, s + DAY); print("[write]", DY, "(+1 section)")
print("DONE")
