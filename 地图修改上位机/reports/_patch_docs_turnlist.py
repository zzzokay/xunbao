# -*- coding: utf-8 -*-
"""文档同步：左栏节点表 -> 转弯补偿表。字节级替换，全部唯一命中才写盘。"""
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

R_OLD = "**左栏上 = 总览**：节点表（#序号 / 类型 / 出度入度）+ 边表。点一行＝选中并高亮。"
R_NEW = '''**左栏上 = 总览**：**转弯补偿表**（10-07 起替代了原来的节点表）+ 边表。

- **转弯补偿表**：地图里每个 (入边, 出边) 转弯组合一行 —— `上一步→当前→下一步` / 转弯角 / 分支 /
  **当前生效补偿值 cm** / 来源。颜色：**绿=实测（表1/表2）、蓝=Tier2 公式、灰=直行、橙=吃默认**。
  **点一行 = 画布上高亮这个弯**（洋红折线 + 当前节点套圈）；**双击一行 = 打开「⟲ 转弯补偿…」编辑器**。
  数据与补偿对话框「③ 覆盖总览」同源（`model.turn_coverage()`）—— 在对话框里改完补偿，左栏这张表会跟着刷新。
  ⚠️ **节点表已移除**：节点改在**画布上点/拖**选中（属性面板照旧）；要在列表里选节点就用画布框选。

- **边表**：点一行＝选中并高亮。'''

R_TURN_OLD = '''  **转弯前补偿（解析 map.c 两张表 / 覆盖总览分档 / 分支判定逐条对拍 / 写回幂等 + 只动三处 /
  真写回路径落在沙箱副本上且真实 map.c SHA256 不变 / 对话框四页签 / 画布高亮）**、'''
R_TURN_NEW = '''  **转弯前补偿（解析 map.c 两张表 / 覆盖总览分档 / 分支判定逐条对拍 / 写回幂等 + 只动三处 /
  真写回路径落在沙箱副本上且真实 map.c SHA256 不变 / 对话框四页签 / 画布高亮 /
  左栏「转弯补偿」表行数=转弯组合数、点一行设 turn_focus 供画布高亮）**、'''

R_N1_OLD = "新入口在界面上真的可见**（233 项）。"
R_N1_NEW = "新入口在界面上真的可见**（234 项）。"

R_N2_OLD = "| `_guismoke.py` | 界面冒烟测试（233 项；"
R_N2_NEW = "| `_guismoke.py` | 界面冒烟测试（234 项；"

AI_29_OLD = "| `_guismoke.py` | 界面冒烟测试（233 项）"
AI_29_NEW = "| `_guismoke.py` | 界面冒烟测试（234 项）"

AI_291_OLD = "_guismoke.py     # 期望：233 项 [OK] / 0 FAIL"
AI_291_NEW = "_guismoke.py     # 期望：234 项 [OK] / 0 FAIL"

AI_TAB_OLD = '''| **改「转弯补偿」对话框的页签/控件** | `App.turn_comp_dialog()`（`build_table_tab()` / `redraw_cov()` / `apply_consts()`） | 入口在**左栏「边显示」那一行**（不是工具栏 —— 那里宽度吃紧，见 §7.9）；`_guismoke` 有"入口 `winfo_ismapped()`"断言 |'''
AI_TAB_NEW = AI_TAB_OLD + '''
| **改左栏上半（转弯补偿表 / 边表）** | `App._build_left()` + `_fill_turn_list(cov=None)` + `_on_tree_turn_select()` | ⚠️ 左栏上半**已无节点树**：`tree_nodes` 已删、换成 `tree_turn`（转弯补偿表，源 = `model.turn_coverage()`）；`_tree_select("node", …)` 现在**直接 return**。点一行 → `turn_focus` + 画布高亮，双击 → `turn_comp_dialog()`。改完跑 `_guismoke`（有"行数=转弯组合数 / 点行设 turn_focus"断言） |'''

PR_LINE = ("- **2026-10-07**：上位机左栏节点表 → 转弯补偿表【仅上位机】—— 按用户要求把左栏上半的**节点表整块换成"
           "「转弯补偿」表**（源 = `model.turn_coverage()`，与补偿对话框第③页签同源）：每行 = 一个 (入边,出边) 转弯"
           "（上一步→当前→下一步 / 转弯角 / 分支 / 生效值cm / 来源），**点一行 → 画布高亮该弯，双击 → 打开"
           "「⟲ 转弯补偿…」**；对话框改完补偿后左栏表自动刷新（`refresh_head()` 调 `_fill_turn_list()`）。"
           "同时删掉 `tree_nodes` / `_on_tree_node_select`（`_tree_select(\"node\",…)` 直接 return），节点改在画布上选。"
           "`_guismoke` 断言同步（节点树行数 → 转弯补偿表行数 + 点行设 turn_focus）⇒ **234 项 [OK] / 0 FAIL**。")

edits = [(R, R_OLD, R_NEW), (R, R_TURN_OLD, R_TURN_NEW), (R, R_N1_OLD, R_N1_NEW),
         (R, R_N2_OLD, R_N2_NEW), (AI, AI_29_OLD, AI_29_NEW), (AI, AI_291_OLD, AI_291_NEW),
         (AI, AI_TAB_OLD, AI_TAB_NEW)]

plan = []
for p, old, new in edits:
    n = load(p).count(old)
    plan.append((p, old, new, n))
    print("[check] %-16s count=%d %s | %s" % (p.split("/")[-1], n,
          "OK" if n == 1 else "!!", old.strip().splitlines()[0][:44]))

if any(x[3] != 1 for x in plan):
    print("\n有串未唯一命中，未写盘。")
    sys.exit(1)

buf = {}
for p, old, new, n in plan:
    buf[p] = buf.get(p, load(p)).replace(old, new, 1)
for p, s in buf.items():
    save(p, s)
    print("[write] %s" % p)

s = load(PR)
if PR_LINE[:36] in s:
    print("[skip] 日志行已存在")
else:
    save(PR, s + "\r\n" + PR_LINE)
    print("[write] %s (+1 log line)" % PR)
print("\nDONE")
