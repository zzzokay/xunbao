# -*- coding: utf-8 -*-
"""端到端：改几个补偿值 → 调 report_source_diff() → 读对话框文本 + 截图。（只读源码，不写任何文件）"""
import os, sys
HERE = os.path.dirname(os.path.split(os.path.abspath(__file__))[0])   # reports 的上级 = 地图修改上位机
sys.path.insert(0, os.path.join(HERE, "map_editor"))
os.chdir(os.path.join(HERE, "map_editor"))
import map_editor as E
import tkinter as tk

app = E.App()
app.geometry("1500x920+80+60")
app.update()

# 制造差异：改一行补偿值 + 改公式参数 + 开开关 + 改两个宏
t = app.model.turn
t["stop"][0]["dist"] = 40.0
t["consts"]["TURN_L_PIVOT"] = 22.0
t["calc_enable"] = 1
app.model.macros["LEN_B5N19"] = "160"
app.model.macros["DOOR_LEN_N5N12"] = "180"

app.report_source_diff()
app.update()
app.after(400, lambda: None)
app.update()

# 找那个报告窗口，读文本
top = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
print("报告窗口数:", len(top))
if top:
    dlg = top[-1]
    txt = [c for c in dlg.winfo_children() if isinstance(c, tk.Text)][0]
    content = txt.get("1.0", "end")
    print("--- 报告文本（转弯补偿 / 宏定义 两段）---")
    keep = False
    for ln in content.splitlines():
        if ln.startswith("转弯补偿差异"):
            keep = True
        if keep:
            print(ln)
    # 把报告全文落盘（这条路径真实产出的文本）
    out = os.path.join(HERE, "reports", "转弯补偿差异_报告示例.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(content)
    print("SAVED", out)
app.destroy()
