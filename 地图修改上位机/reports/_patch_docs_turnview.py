# -*- coding: utf-8 -*-
"""文档同步：左栏「转弯补偿」表的「显示」下拉；计数 239->241；当日日志。"""
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

R_SHOW_OLD = "  数据与补偿对话框「③ 覆盖总览」同源（`model.turn_coverage()`）—— 在对话框里改完补偿，左栏这张表会跟着刷新。\n"
R_SHOW_NEW = R_SHOW_OLD + ("  **「显示」下拉**（像「边显示」，默认**不显示全部**）：`只看要补偿的`（默认，去掉直行）/ `只看实测` / "
                           "`只看吃默认` / `只看停车转` / `只看陀螺转` / `全部`；\n"
                           "  提示行给出 `当前行数/总转弯组合数`。档位随「保存布局」记住（`constraints.turn_view`）。\n")

R_B_OLD = "  左栏「转弯补偿」表行数=转弯组合数、点一行设 turn_focus 供画布高亮）**、"
R_B_NEW = "  左栏「转弯补偿」表显示档过滤（全部=转弯组合数 / 默认档去直行 / 只看实测）与点一行设 turn_focus）**、"

R_C1_OLD = "新入口在界面上真的可见**（239 项）。"
R_C1_NEW = "新入口在界面上真的可见**（241 项）。"
R_C2_OLD = "| `_guismoke.py` | 界面冒烟测试（239 项；"
R_C2_NEW = "| `_guismoke.py` | 界面冒烟测试（241 项；"

AI_C1_OLD = "| `_guismoke.py` | 界面冒烟测试（239 项）"
AI_C1_NEW = "| `_guismoke.py` | 界面冒烟测试（241 项）"
AI_C2_OLD = "_guismoke.py     # 期望：239 项 [OK] / 0 FAIL"
AI_C2_NEW = "_guismoke.py     # 期望：241 项 [OK] / 0 FAIL"

AI_ROW_OLD = '| **改左栏上半（转弯补偿表 / 边表）** | `App._build_left()` + `_fill_turn_list(cov=None)` + `_on_tree_turn_select()` | ⚠️ 左栏上半**已无节点树**：`tree_nodes` 已删、换成 `tree_turn`（转弯补偿表，源 = `model.turn_coverage()`）；`_tree_select("node", …)` 现在**直接 return**。点一行 → `turn_focus` + 画布高亮，双击 → `turn_comp_dialog()`。改完跑 `_guismoke`（有"行数=转弯组合数 / 点行设 turn_focus"断言） |'
AI_ROW_NEW = '| **改左栏上半（转弯补偿表 / 边表）** | `App._build_left()` + `_fill_turn_list(cov=None)` + `_on_tree_turn_select()`；过滤 `map_model.turn_filter(rows, mode)` / `TURN_LIST_MODES` | ⚠️ 左栏上半**已无节点树**：`tree_nodes` 已删、换成 `tree_turn`（转弯补偿表，源 = `model.turn_coverage()`）；`_tree_select("node", …)` 现在**直接 return**。「显示」下拉（`App.turn_view`，6 档）**默认「只看要补偿的」不显示全部**；档位持久化在 `constraints.turn_view`。点一行 → `turn_focus` + 画布高亮，双击 → `turn_comp_dialog()`。改完跑 `_guismoke`（有"显示档过滤 / 点行设 turn_focus"断言） |'

ME_OLD = "（239 项，界面）"
ME_NEW = "（241 项，界面）"

PR_LINE = ("- **2026-10-07**：左栏「转弯补偿」表加「显示」下拉【仅上位机】—— 该表默认列全部 ~300 个转弯组合太多，"
           "用户要求像「边显示」那样给几档（\"别显示全部的\"）。新增 `map_model.TURN_LIST_MODES`"
           "（只看要补偿的 / 只看实测 / 只看吃默认 / 只看停车转 / 只看陀螺转 / 全部）与纯函数 `turn_filter(rows, mode)`；"
           "左栏加下拉（**默认「只看要补偿的」，去掉直行**），提示行显示 `当前行数/总数`；档位随「保存布局」记在 "
           "`constraints.turn_view`。`_guismoke` 断言随档位更新 ⇒ **241 项 [OK] / 0 FAIL**。")

DAY = ("\n## 左栏「转弯补偿」表加「显示」下拉【仅上位机】\n\n"
"- **用户要求**：那个「转弯补偿」小窗口别显示全部，像编辑器一样给几个选项可选。追问后用户明确指 → **左栏「转弯补偿」表**。\n"
"- **改法**：\n"
"  - `map_model.py` 新增 `TURN_LIST_MODES`（只看要补偿的 / 只看实测 / 只看吃默认 / 只看停车转 / 只看陀螺转 / 全部）"
"+ 纯函数 `turn_filter(rows, mode)`（`只看吃默认` 口径与对话框第③页勾选框一致：默认19/默认0/角度求不出）。\n"
"  - `map_editor.py`：左栏该表上方加 `显示:` 下拉（`App.turn_view`，默认 `TURN_LIST_MODES[0]`）+ 提示行 `N/总 行`；"
"`_fill_turn_list()` 用 `turn_filter` 过滤，`self._turn_rows` 存**过滤后**的行（点行→turn_focus 靠它，索引不会错位）；"
"档位持久化到 `constraints.turn_view`（`_sync_state_to_model` / `_apply_model_background`）。\n"
"  - 微调：提示行加 `wraplength=372`（否则被 380 左栏右边缘裁掉）；「值cm」列 46→54（否则表头折成两行）。\n"
"- **验证**：`_guismoke` 断言改为按档比对（全部 296 行 / 默认档 222 行（去直行）/ 只看实测 22 行 / 过滤后点行仍设 turn_focus）"
"⇒ **241 项 [OK] / 0 FAIL**；截图 `reports/left_turn_list.png` 复看确认下拉不溢出。\n"
"- **文档**：`map_editor/README.md` §5 + §8、`AI_CONTEXT.md`（计数 + 左栏上半行补 `turn_filter`）、`项目讲解文档/README.md` §9 一行、`MEMORY.md` 计数。\n")

edits = [(R, R_SHOW_OLD, R_SHOW_NEW), (R, R_B_OLD, R_B_NEW), (R, R_C1_OLD, R_C1_NEW),
         (R, R_C2_OLD, R_C2_NEW), (AI, AI_C1_OLD, AI_C1_NEW), (AI, AI_C2_OLD, AI_C2_NEW),
         (AI, AI_ROW_OLD, AI_ROW_NEW), (ME, ME_OLD, ME_NEW)]

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
if "左栏「转弯补偿」表加「显示」下拉" in s:
    print("[skip] 当日日志已记")
else:
    save(DY, s + DAY); print("[write]", DY, "(+1 section)")
print("DONE")
