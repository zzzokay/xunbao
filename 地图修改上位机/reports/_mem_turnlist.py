# -*- coding: utf-8 -*-
"""写项目记忆：MEMORY.md 补「左栏=转弯补偿表」约定 + 计数；当日日志追加一节。"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

def load(p):
    return open(p, "rb").read().decode("utf-8")

def save(p, s):
    open(p, "wb").write(s.encode("utf-8"))

M = ".workbuddy/memory/MEMORY.md"
D = ".workbuddy/memory/2026-10-07.md"

M_ANCHOR = "- 表里\"会不会生效\"由 `map.c: Nav_TurnAndAdvance()` 的分支判（不在表里）；固件那条 `STOPTURN` 判据用陀螺实测航向，\n  静态只能按边表角度近似。PR §14.1 那份手写\"死值清单\"已与源码对不上，**以工具/`_selftest` 实时算的为准**。\n"
M_NEW = M_ANCHOR + "- **左栏上半（10-07 起）= 转弯补偿表**（原节点表已删）：每行一个 (入边,出边) 转弯 + **生效值 cm** + 来源，\n  点一行 → 画布高亮该弯、双击 → 打开「⟲ 转弯补偿…」编辑器；数据源 `model.turn_coverage()`，与对话框第③页签同源。\n  节点改在**画布上**选（`_tree_select(\"node\",…)` 直接 return）。README §5。\n"

M_CNT_OLD = "- 改 `map_model.py` 后必跑 `_selftest.py`（含往返零差异）+ `_guismoke.py`（223 项，界面）；"
M_CNT_NEW = "- 改 `map_model.py` 后必跑 `_selftest.py`（含往返零差异）+ `_guismoke.py`（234 项，界面）；"

DAY = ("\n## 左栏「节点表」→「转弯补偿表」【仅上位机】\n\n"
"- **用户要求**：左栏上半的**节点表整块换成转弯补偿表**（选项里选「节点表直接换成补偿」）。\n"
"- **改法**（`map_editor.py`）：\n"
"  - `_build_left()`：删 `tree_nodes`，换 `tree_turn`（列 = 转弯(#0 `上一步→当前→下一步`) / 角 / 分支 / 值cm / 来源；\n"
"    tag 着色 绿=实测、蓝=公式、灰=直行、橙=吃默认）。点一行 → `_on_tree_turn_select()` 设 `turn_focus` + `redraw()`\n"
"    画布高亮；双击 → `turn_comp_dialog()`。\n"
"  - 新增 `_fill_turn_list(cov=None)`（源 = `model.turn_coverage()`，与对话框③覆盖总览**同源**）；`refresh_trees()` 改调它。\n"
"  - 删 `_on_tree_node_select`；`_tree_select(\"node\", …)` 直接 `return`（没有节点树可同步）；`select_node()`（画布选）不受影响。\n"
"  - 对话框 `refresh_head()` 里加 `self._fill_turn_list(cov)` ⇒ 改完补偿左栏表自动刷新。\n"
"- **验证**：`_guismoke` 断言同步（原「节点树 N 行」→「左栏转弯补偿表 N 行=转弯组合数」+ 新增「点一行设 turn_focus」）\n"
"  ⇒ **234 项 [OK] / 0 FAIL**；只读脚本 `reports/_check_left_turn.py` 确认表头/行数/着色/前几行文本（载入 default.json 时 300 行）。\n"
"- **文档同步**：`map_editor/README.md` §5 + §8（计数 233→234、turn 项补一条）、`AI_CONTEXT.md`（计数 + §9 改动指引新增「改左栏上半」）、\n"
"  `项目讲解文档/README.md` §9 追加一行。行尾：map_editor/** LF、讲解文档 CRLF。\n"
"- 补丁脚本：`reports/_patch_left_turnlist.py`、`reports/_patch_docs_turnlist.py`。\n")

edits = [(M, M_ANCHOR, M_NEW), (M, M_CNT_OLD, M_CNT_NEW)]
plan = []
for p, old, new in edits:
    n = load(p).count(old)
    plan.append((p, old, new, n))
    print("[check] %-28s count=%d %s" % (p.split("/")[-1], n, "OK" if n == 1 else "!!"))
if any(x[3] != 1 for x in plan):
    print("未唯一命中，未写盘。"); sys.exit(1)

buf = {}
for p, old, new, n in plan:
    buf[p] = buf.get(p, load(p)).replace(old, new, 1)
for p, s in buf.items():
    save(p, s); print("[write]", p)

s = load(D)
if "左栏「节点表」→「转弯补偿表」" in s:
    print("[skip] 当日日志已记")
else:
    save(D, s + DAY); print("[write]", D, "(+1 section)")
print("DONE")
