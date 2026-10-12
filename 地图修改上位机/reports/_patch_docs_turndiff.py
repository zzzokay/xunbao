# -*- coding: utf-8 -*-
"""文档同步：把「查看代码差异」新增的「转弯补偿差异」写进 README/AI_CONTEXT/讲解文档，并更新计数 234→239。"""
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

R_SEC_OLD = "| info | 孤立节点（没有任何边） |\n"
R_SEC_NEW = ("| info | 孤立节点（没有任何边） |\n\n"
             "**「查看代码差异」按钮**（工具栏第 2 行，只读）把**当前模型 vs 固件源码**比一遍：\n"
             "枚举节点、边表、`NAV_EDGE_COUNT`，**以及转弯补偿** —— 表1/表2 的 **新增 / 删除 / 改值** + 公式参数 + "
             "`TURN_CALC_ENABLE` 开关（源 `model.turn` 对比 `M.parse_turn_tables()`）。\n"
             "它比的是**源码**，所以顺手能看出\"启动自动载入的布局 / 补偿表是不是已经和固件不一样了\"。\n"
             "纯函数 `M.turn_diff()` / `M.turn_diff_lines()` 负责算与排版（无 Tk，`_guismoke` 有断言）。\n")

R_C1_OLD = "新入口在界面上真的可见**（234 项）。"
R_C1_NEW = "新入口在界面上真的可见**（239 项）。"
R_C2_OLD = "| `_guismoke.py` | 界面冒烟测试（234 项；"
R_C2_NEW = "| `_guismoke.py` | 界面冒烟测试（239 项；"

AI_C1_OLD = "| `_guismoke.py` | 界面冒烟测试（234 项）"
AI_C1_NEW = "| `_guismoke.py` | 界面冒烟测试（239 项）"
AI_C2_OLD = "_guismoke.py     # 期望：234 项 [OK] / 0 FAIL"
AI_C2_NEW = "_guismoke.py     # 期望：239 项 [OK] / 0 FAIL"

AI_TURN_OLD = "| **改转弯补偿表 / 公式参数（`map.c`）** | `map_model.parse_turn_tables()` / `turn_coverage()` / `turn_table_status()` / `turn_branch()` / `export_turn_*()` / `splice_turn_tables()` / `turn_rows_equal()`；"
AI_TURN_NEW = "| **改转弯补偿表 / 公式参数（`map.c`）** | `map_model.parse_turn_tables()` / `turn_coverage()` / `turn_table_status()` / `turn_branch()` / `export_turn_*()` / `splice_turn_tables()` / `turn_rows_equal()` / `turn_diff()` / `turn_diff_lines()`（后两个给「查看代码差异」的「转弯补偿差异」段）；"

ME_OLD = "- 改 `map_model.py` 后必跑 `_selftest.py`（含往返零差异）+ `_guismoke.py`（234 项，界面）；"
ME_NEW = "- 改 `map_model.py` 后必跑 `_selftest.py`（含往返零差异）+ `_guismoke.py`（239 项，界面）；"

PR_LINE = ("- **2026-10-07**：「查看代码差异」加上「转弯补偿差异」段【仅上位机】—— 原「查看代码差异」只比 enum + 边表 + "
           "`NAV_EDGE_COUNT`，**从没读 `map.c`**，所以补偿改了看不出来（用户问\"差异里为什么没有补偿\"）。"
           "新增纯函数 `map_model.turn_diff()`（按三元组配对：表1/表2 的新增/删除/改值 + 公式参数 + `TURN_CALC_ENABLE`）"
           "与 `turn_diff_lines()`（排版），`report_source_diff()` 调它们输出一段「转弯补偿差异」。"
           "写回入口**维持现状**（仍走「写回 map.c…」）。`_guismoke` 加 5 条断言 ⇒ **239 项 [OK] / 0 FAIL**。")

edits = [(R, R_SEC_OLD, R_SEC_NEW), (R, R_C1_OLD, R_C1_NEW), (R, R_C2_OLD, R_C2_NEW),
         (AI, AI_C1_OLD, AI_C1_NEW), (AI, AI_C2_OLD, AI_C2_NEW), (AI, AI_TURN_OLD, AI_TURN_NEW),
         (ME, ME_OLD, ME_NEW)]

plan = []
for p, old, new in edits:
    n = load(p).count(old)
    plan.append((p, old, new, n))
    print("[check] %-18s count=%d %s | %s" % (p.split("/")[-1], n,
          "OK" if n == 1 else "!!", old.strip().splitlines()[0][:42]))
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
print("DONE")
