# -*- coding: utf-8 -*-
"""当日日志追加 + 行尾自检。"""
import os, sys

os.chdir("C:/Users/14166/Desktop/MC_32/robotcup/xunbao")
D = ".workbuddy/memory/2026-10-07.md"
DAY = ("\n## 「查看代码差异」加「转弯补偿差异」段【仅上位机】\n\n"
"- **背景**：用户问\"为什么写回 map.c 要单独一个按钮、差异里也没显示补偿\"。核实：主「写回固件」只写 "
"`map_message.c`/`map.h`/`map_message.h`；补偿在 `Navigation/map.c` 故单独写回；而 `report_source_diff()` "
"只比 enum+边表+`NAV_EDGE_COUNT`，**从没读 `map.c`** ⇒ 补偿差异看不见。用户选 **A：只加差异对比（只读），写回入口维持现状**。\n"
"- **改法**：`map_model.py` 新增 `turn_diff(cur, src)`（按 (last,now,next) 配对，报 表1/表2 新增/删除/改值 + "
"`TURN_*` 公式参数 + `TURN_CALC_ENABLE`；**不看行序**）+ `turn_diff_lines(td)`（排版，纯字符串无 Tk）。"
"`map_editor.report_source_diff()` 调它们，在边表段后加一段「转弯补偿差异」，并把\"内容一致\"的判据也纳入 `turn_same`。\n"
"- **验证**：`_guismoke` 加 5 条断言（same / 改值 / 公式参数 / 开关 / 报告含该段）⇒ **239 项 [OK] / 0 FAIL**；"
"`_selftest` 仍只 1 项**既有**失败（`N16→N18` 路口写反，10-02 起，与本次无关）；端到端脚本 `reports/_check_turndiff.py` "
"实跑 `report_source_diff()` 并把报告文本存 `reports/转弯补偿差异_报告示例.txt`。\n"
"- **文档**：`map_editor/README.md` §7 新增「查看代码差异」说明 + 计数 234→239；`AI_CONTEXT.md` 计数 + turn 行补 "
"`turn_diff/turn_diff_lines`；`项目讲解文档/README.md` §9 一行；`MEMORY.md` 计数。行尾照旧。\n")

s = open(D, "rb").read().decode("utf-8")
if "查看代码差异」加「转弯补偿差异" in s:
    print("[skip] 已记")
else:
    open(D, "wb").write((s + DAY).encode("utf-8"))
    print("[write]", D, "(+1 section)")

print("--- 行尾自检 ---")
for p in ["地图修改上位机/map_editor/map_model.py", "地图修改上位机/map_editor/map_editor.py",
          "地图修改上位机/map_editor/_guismoke.py", "地图修改上位机/map_editor/README.md",
          "地图修改上位机/map_editor/AI_CONTEXT.md", "项目讲解文档/README.md",
          ".workbuddy/memory/MEMORY.md", ".workbuddy/memory/2026-10-07.md"]:
    d = open(p, "rb").read()
    crlf = d.count(b"\r\n"); lf = d.count(b"\n") - crlf
    print("  %-40s CRLF=%-4d LF=%-5d" % (p, crlf, lf))
