# -*- coding: utf-8 -*-
"""文档同步：显示档加「只看实测停车转」；计数 244->245；当日日志。"""
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

R_MODES_OLD = "**「显示」下拉**（像「边显示」，默认**不显示全部**）：`只看要补偿的`（默认，去掉直行）/ `只看实测` / `只看吃默认` / `只看停车转` / `只看陀螺转` / `全部`；"
R_MODES_NEW = "**「显示」下拉**（像「边显示」，默认**不显示全部**）：`只看要补偿的`（默认，去掉直行）/ `只看实测` / `只看实测停车转`（仅表1 `kTurnTbl`）/ `只看吃默认` / `只看停车转` / `只看陀螺转` / `全部`；"

R_C1_OLD = "新入口在界面上真的可见**（244 项）。"
R_C1_NEW = "新入口在界面上真的可见**（245 项）。"
R_C2_OLD = "| `_guismoke.py` | 界面冒烟测试（244 项；"
R_C2_NEW = "| `_guismoke.py` | 界面冒烟测试（245 项；"

AI_C1_OLD = "| `_guismoke.py` | 界面冒烟测试（244 项）"
AI_C1_NEW = "| `_guismoke.py` | 界面冒烟测试（245 项）"
AI_C2_OLD = "_guismoke.py     # 期望：244 项 [OK] / 0 FAIL"
AI_C2_NEW = "_guismoke.py     # 期望：245 项 [OK] / 0 FAIL"

AI_ROW_OLD = "「显示」下拉（`App.turn_view`，6 档）**默认「只看要补偿的」不显示全部**"
AI_ROW_NEW = "「显示」下拉（`App.turn_view`，7 档）**默认「只看要补偿的」不显示全部**"

ME_OLD = "（244 项，界面）"
ME_NEW = "（245 项，界面）"

PR_LINE = ("- **2026-10-07**：左栏「转弯补偿」显示档加「只看实测停车转」【仅上位机】—— 只列**表1 `kTurnTbl`（停车转）的实测行**，"
           "与「只看实测」（表1+表2）区分开，便于专盯停车转那张表。`TURN_LIST_MODES` 由 6 档变 7 档；下拉加宽到 width=17（放得下档名）。"
           "`_guismoke` 加 1 条断言 ⇒ **245 项 [OK] / 0 FAIL**。")

DAY = ("\n## 左栏「转弯补偿」显示档加「只看实测停车转」【仅上位机】\n\n"
"- **用户要求**：显示档多一个「只看实测停车转」。\n"
"- **改法**：`TURN_LIST_MODES` 插入 `只看实测停车转`（放在 `只看实测` 之后）；`turn_filter()` 加一支 `source == \"表1 实测\"`"
"（= 停车转那张表的实测行，排除表2 陀螺转）。左栏下拉 width 14→17（档名 7 个字，别被裁）。\n"
"- **验证**：`_guismoke` 断言 `只看实测停车转` = 15 行（表1 全 15 条）且 `<= 只看实测` 的 22 行 ⇒ **245 项 [OK] / 0 FAIL**；"
"截图 `reports/left_turn_list.png`（选中该档）确认下拉完整不裁。\n"
"- **文档**：`map_editor/README.md` §5 档位列表 + 计数 244→245、`AI_CONTEXT.md`（计数 + 6 档→7 档）、`项目讲解文档/README.md` §9、`MEMORY.md`。\n")

edits = [(R, R_MODES_OLD, R_MODES_NEW), (R, R_C1_OLD, R_C1_NEW), (R, R_C2_OLD, R_C2_NEW),
         (AI, AI_C1_OLD, AI_C1_NEW), (AI, AI_C2_OLD, AI_C2_NEW), (AI, AI_ROW_OLD, AI_ROW_NEW),
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
if "显示档加「只看实测停车转」" in s:
    print("[skip] 当日日志已记")
else:
    save(DY, s + DAY); print("[write]", DY, "(+1 section)")
print("DONE")
