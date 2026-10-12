# -*- coding: utf-8 -*-
"""AI 过程脚本：文档同步 —— 对话框被裁的坑 + 项数 280→282。"""
import os

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"
P = os.path.join(ROOT, "项目讲解文档", "README.md")
R = os.path.join(ROOT, "地图修改上位机", "map_editor", "README.md")
A = os.path.join(ROOT, "地图修改上位机", "map_editor", "AI_CONTEXT.md")
M = os.path.join(ROOT, ".workbuddy", "memory", "MEMORY.md")
D = os.path.join(ROOT, ".workbuddy", "memory", "2026-10-07.md")

R1_OLD = ("  **直立景点巡回 S1/S2（一轮宝物 P3→S1 / P4→S2；二轮 P3 后 S1、P4 后 S2；跟随 config.h；规划路线真的经过 S1）**\n"
          "  （280 项；**当前 279 OK / 1 FAIL**：`D5黑+D4绿` 那条是**既有**的（边表/权重 WIP），不是本功能引入的）。\n")
R1_NEW = ("  **直立景点巡回 S1/S2（一轮宝物 P3→S1 / P4→S2；二轮 P3 后 S1、P4 后 S2；跟随 config.h；规划路线真的经过 S1）**、\n"
          "  **两个对话框装得下内容**（按内容自适应尺寸，防「加控件后被裁」）\n"
          "  （282 项；**当前 281 OK / 1 FAIL**：`D5黑+D4绿` 那条是**既有**的（边表/权重 WIP），不是本功能引入的）。\n")

R2_OLD = "| `_guismoke.py` | 界面冒烟测试（280 项；"
R2_NEW = "| `_guismoke.py` | 界面冒烟测试（282 项；"

A1_OLD = "| `_guismoke.py` | 界面冒烟测试（280 项），"
A1_NEW = "| `_guismoke.py` | 界面冒烟测试（282 项），"

A2_OLD = "python 地图修改上位机/map_editor/_guismoke.py     # 280 项（当前 279 OK / 1 FAIL：`D5黑+D4绿` 那条既有 WIP）\n"
A2_NEW = "python 地图修改上位机/map_editor/_guismoke.py     # 282 项（当前 281 OK / 1 FAIL：`D5黑+D4绿` 那条既有 WIP）\n"

A3_OLD = ("改完跑 `_guismoke` 的「round-1/2: upright tour S1/S2」段 + `tools/sim_upright_tour.py` |\n")
A3_NEW = (A3_OLD +
          "| **改对话框（加/挪控件、改行数）** | 搭界面的 `App.plan_clue_route_dialog()` / `plan_round2_route_dialog()` 等；"
          "尺寸统一走模块函数 `_fit_dialog(dlg, frm, minw, minh)` | ⚠️ **别写死 `dlg.geometry(\"WxH\")`**："
          "内容一超过它就被裁（踩过：「线索路线…」写死 660x430，后来加了两行长提示 ⇒ 内容宽 **1348px** 挤进 660px 窗口，"
          "右边整段看不见，用户报「窗口打开不能完整显示内容」）。`_fit_dialog()` 按**内容实测 `req`** 定尺寸 + `minsize`，"
          "并夹到屏幕内；长文本要自己加 `wraplength`。`_guismoke` 有「两个对话框装得下内容」断言守着 |\n")

M_OLD = ("- **路线标记复位统一走 `App._reset_route_marks()`**（管 `route_split` + `route_dim_edges`）；\n"
         "  任何设置 `self.route` 的地方都要调它，别再散落写 `route_split = None`。\n")
M_NEW = (M_OLD +
         "\n## 上位机 UI 护栏\n"
         "\n"
         "- ⚠️ **对话框尺寸别写死**：一律走模块函数 `_fit_dialog(dlg, frm, minw, minh)`（按内容实测 `req` 自适应 + `minsize`，\n"
         "  并夹到屏幕内）。踩过：「线索路线…」写死 `660x430`，后来加了两行长提示 ⇒ 内容 **1348px** 挤进 660px 窗口，\n"
         "  右边整段看不见（用户报「打开不能完整显示内容」）。长文本记得 `wraplength`。`_guismoke` 有断言守着。\n")

S9 = (
    "- **2026-10-07**：修「线索路线…」对话框内容被裁【仅上位机】—— 用户报「窗口打开不能完整显示内容」。实测：内容宽\n"
    "**1348px** 却挤在写死 `660x430` 的窗口里（根因 = 上一轮加的那两行长提示**没设 `wraplength`**，被拉成 1324px 一行）。\n"
    "改法：① 提示行加 `wraplength=620`（→ 619px×2 行）；② 新增模块函数 `_fit_dialog(dlg, frm, minw, minh)`，两个对话框都改成\n"
    "**按内容实测 `req` 自适应尺寸 + `minsize`**（并夹到屏幕内），以后加控件不会再被裁。`_guismoke` 加 2 条「装得下内容」\n"
    "断言 ⇒ **282 项（当前 281 OK / 1 项既有 FAIL）**。\n"
)

LOG = (
    "\n## 修「线索路线…」对话框内容被裁【仅上位机】\n"
    "\n"
    "- **用户报**：「那个现在线索的窗口打开不能完整显示内容」。\n"
    "- **实测**（脚本量 `winfo_req*` vs `winfo_*`）：窗口写死 `660x490`，**内容 req 宽 1348px**；\n"
    "  根因 = 提示行缺 `wraplength` ⇒ 被拉成 **1324px 一行**，右边整段看不见。这是**我上一轮加长提示时引入的**。\n"
    "- **改法**：① 提示行 `wraplength=620, justify=\"left\"`（req → 619x55，两行）；\n"
    "  ② 新增模块函数 `_fit_dialog(dlg, frm, minw, minh)`：按内容 `req` 自适应 + `minsize` + 夹到屏幕内；\n"
    "  线索对话框（660x490→实测 670x490）与二轮对话框（740x560→req 683x363 不变）都接上。\n"
    "- **验证**：逐行量过 —— **0 行超出窗口底边**，内容 646x397 ≤ 窗口 670x490（二轮 683x363 ≤ 740x560）。\n"
    "  `_guismoke` 加 2 条防回归断言（「两个对话框装得下内容」）⇒ **281 OK / 1 既有 FAIL**。\n"
    "- **教训**：**对话框尺寸别写死**，用 `_fit_dialog()`；长文本必须 `wraplength`（已写进 MEMORY 与 AI_CONTEXT §9）。\n"
    "- 脚本：`reports/_diag_dlg_size.py`（量尺寸）/ `_patch_dlg_fit.py` / `_patch_guismoke_dlgfit.py`。\n"
)


def apply(path, edits, eol):
    with open(path, "rb") as f:
        data = f.read()
    for old, new in edits:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "%s 命中 %d 次:\n%r" % (os.path.basename(path), cnt, old[:70])
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


apply(R, [(R1_OLD, R1_NEW), (R2_OLD, R2_NEW)], "\n")
apply(A, [(A1_OLD, A1_NEW), (A2_OLD, A2_NEW), (A3_OLD, A3_NEW)], "\n")
apply(M, [(M_OLD, M_NEW)], "\n")
append(P, S9, "\r\n")
append(D, LOG, "\n")
print("文档补丁已写盘。")
