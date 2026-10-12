# -*- coding: utf-8 -*-
"""AI 过程脚本 第 4 步：文档同步（S1/S2 巡回也进了上位机）。"""
import os

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"
P = os.path.join(ROOT, "项目讲解文档", "README.md")
R = os.path.join(ROOT, "地图修改上位机", "map_editor", "README.md")
A = os.path.join(ROOT, "地图修改上位机", "map_editor", "AI_CONTEXT.md")
M = os.path.join(ROOT, ".workbuddy", "memory", "MEMORY.md")
D = os.path.join(ROOT, ".workbuddy", "memory", "2026-10-07.md")

S19 = (
    "    - **上位机（地图修改上位机）也镜像了这个开关**（2026-10-07 补）：`map_model.upright_tour_waypoints()` +\n"
    "      `treasure_return_waypoints()` / `door_return_home_waypoints()` / `round2_waypoints()` 的 `tour` 参数；\n"
    "      「线索路线…」与「二轮路线…」两个对话框都加了「直立景点巡回 S1/S2」下拉（跟随 config.h / 强制开 / 强制关）。\n"
    "      开了之后**画布上能直接看到绕 S1/S2 的路线**（`S1`/`S2` 在边表里有边：`N3→S1`、`N6→S2`，能规划能画）。\n"
)

S9 = (
    "- **2026-10-07**：上位机补镜像「直立景点巡回 S1/S2」【仅上位机】—— 之前 `UPRIGHT_TOUR_ENABLE` 只在固件与\n"
    "`tools/sim_*` 里有镜像，**编辑器完全没有**（打开开关也看不到路线）。现在 `map_model` 加纯函数\n"
    "`upright_tour_waypoints()`，`treasure_return_waypoints` / `door_return_home_waypoints` / `round2_waypoints`\n"
    "各加 `tour` 参数；「线索路线…」与「二轮路线…」各加「直立景点巡回 S1/S2」下拉（跟随 config.h / 强制开 / 强制关），\n"
    "与「回程补打卡 P3/P4」同一套 `_switch_on()`。两个开关一起开时顺序 = 宝物平台 → 补打卡 → 巡回 → P2（与固件一致）。\n"
    "`_guismoke` **280 项（279 OK / 1 项既有 FAIL）**（§2.19）\n"
)

R1_OLD = ("  **宝物线索**（P1~P6）、**回程补打卡 P3/P4**（`P3P4_PUNCH_ENABLE`：跟随 config.h / 强制开 / 强制关）。\n")
R1_NEW = ("  **宝物线索**（P1~P6）、**回程补打卡 P3/P4**（`P3P4_PUNCH_ENABLE`）、**直立景点巡回 S1/S2**\n"
          "  （`UPRIGHT_TOUR_ENABLE`）—— 后两个都是「跟随 config.h / 强制开 / 强制关」三档下拉；\n"
          "  「直立景点巡回」在「二轮路线…」对话框里也有（二轮固定 P3 后绕 S1、P4 后绕 S2）。\n")

R2_OLD = ("  **回程补打卡 P3/P4（纯函数缺哪个补哪个 / 跟随 config.h / 门回程 wp 顺序 / 规划路线真的绕到 P4、P3）**\n"
          "  （273 项；**当前 272 OK / 1 FAIL**：`D5黑+D4绿` 那条是**既有**的（边表/权重 WIP），不是本功能引入的）。\n")
R2_NEW = ("  **回程补打卡 P3/P4（纯函数缺哪个补哪个 / 跟随 config.h / 门回程 wp 顺序 / 规划路线真的绕到 P4、P3）**、\n"
          "  **直立景点巡回 S1/S2（一轮宝物 P3→S1 / P4→S2；二轮 P3 后 S1、P4 后 S2；跟随 config.h；规划路线真的经过 S1）**\n"
          "  （280 项；**当前 279 OK / 1 FAIL**：`D5黑+D4绿` 那条是**既有**的（边表/权重 WIP），不是本功能引入的）。\n")

R3_OLD = "| `_guismoke.py` | 界面冒烟测试（273 项；"
R3_NEW = "| `_guismoke.py` | 界面冒烟测试（280 项；"

A1_OLD = "| `_guismoke.py` | 界面冒烟测试（273 项），"
A1_NEW = "| `_guismoke.py` | 界面冒烟测试（280 项），"

A2_OLD = "python 地图修改上位机/map_editor/_guismoke.py     # 273 项（当前 272 OK / 1 FAIL：`D5黑+D4绿` 那条既有 WIP）\n"
A2_NEW = "python 地图修改上位机/map_editor/_guismoke.py     # 280 项（当前 279 OK / 1 FAIL：`D5黑+D4绿` 那条既有 WIP）\n"

A3_OLD = "改完跑 `_guismoke` 的「round-1 return: extra P3/P4 punch」段 + `sim_route_bookkeeping.py` |\n"
A3_NEW = (A3_OLD +
          "| **改「直立景点巡回 S1/S2」（`UPRIGHT_TOUR_ENABLE`）** | 固件 `config.h` 的 `UPRIGHT_TOUR_ENABLE` + "
          "`mission_planner.c` **三处**（`plan_treasure_return` / `route_return_home` / `get_newroute`）；镜像 "
          "`M.upright_tour_waypoints(treasure)` + `treasure_return_waypoints` / `door_return_home_waypoints` / "
          "`round2_waypoints` 的 `tour` 参数；界面 `App._switch_on()` / `_tour_on()` + 两个对话框的 `TOUR_VALS` | "
          "见 `项目讲解文档/README.md` §2.19。**一轮只用宝物判据**（P3→S1、P4→S2），**二轮固定两个都绕**；落点都在"
          "宝物平台 / 补打卡**之后**、`P2` 之前（两开关同开时顺序 = 平台 → 补打卡 → 巡回）。`S1`/`S2` 的 `func` 是 "
          "`View1`、`map_function()` 无 `case View1` ⇒ **只走位不得分**。改完跑 `_guismoke` 的"
          "「round-1/2: upright tour S1/S2」段 + `tools/sim_upright_tour.py` |\n")

M_OLD = ("  `S1/S2` 的 func 是 `View1` 且 `map_function()` 无 `case` ⇒ 目前只走位不得分。README §2.19。\n")
M_NEW = (M_OLD +
         "  **上位机已镜像**（10-07）：`M.upright_tour_waypoints()` + 三个函数的 `tour` 参数 + 两个对话框的\n"
         "  「直立景点巡回 S1/S2」下拉（跟随 config.h / 强制开 / 强制关）⇒ **画布能画出绕 S1/S2 的路线**。\n")

LOG = (
    "\n## 上位机补镜像「直立景点巡回 S1/S2」【仅上位机】\n"
    "\n"
    "- **用户问**：「回家顺便打卡 P3P4 和 S1S2 两个开关有没有加到上位机，能不能路线显示出来」。\n"
    "  查证：**P3/P4 补打卡已在**（能显示）；**S1/S2 巡回完全没有**（`map_model` 里一行 S1/S2 逻辑都没有，\n"
    "  只有固件 + `tools/sim_*` 有镜像）⇒ 打开 `UPRIGHT_TOUR_ENABLE` 也看不到路线。\n"
    "- **改法**：\n"
    "  - `map_model.py`：新增 `upright_tour_waypoints(treasure)`（一轮 P3→S1 / P4→S2、其余不绕）；\n"
    "    `treasure_return_waypoints` / `door_return_home_waypoints` 各加 `tour`；`round2_waypoints` 加 `tour`\n"
    "    （P3 后插 S1、P4 后插 S2）。**默认 False ⇒ 老调用点行为不变**。\n"
    "  - `map_editor.py`：`_punch_on` 泛化成 `_switch_on(macro, choice)` + `_punch_on` / `_tour_on` 两个薄封装；\n"
    "    `tour` 透传 `_clue_route_sections` / `_round1_complete` / `_append_after_door` / 第二轮分支 / `_round2_route_sections`；\n"
    "    两个对话框各加「直立景点巡回 S1/S2」下拉（`TOUR_VALS`），线索对话框行号 +1、窗口高 430→490，二轮 500→560。\n"
    "  - `_guismoke.py`：线索对话框下拉数 9→10、`_cfg_want` 加 `tour`；**原来写死「当前 P3P4_PUNCH_ENABLE=0 ⇒ 关」\n"
    "    的两条断言改成从 config.h 读当前值再比**（用户已把该开关改成 1，写死就会假失败）；加 6 条 S1/S2 断言。\n"
    "- **验证**：`_guismoke` **279 OK / 1 FAIL**（唯一 FAIL 是既有 `D5黑+D4绿`/`N8` 那条）；`_selftest` 1 项既有；\n"
    "  `sim_route_bookkeeping.py` 源同步自检通过（含 ROUND2_CRUISE_*）；EIDE 编译 0 error / 0 warning。\n"
    "  关键证据：`_guismoke` 里「开了巡回后的门回程路线真的经过 S1」= `N3→P3→N3→S1→N3→N4→B3→N2→P2` ⇒ **画得出来**。\n"
    "- 补丁脚本：`reports/_patch_model_upright_tour.py` / `_patch_editor_upright_tour.py` / `_patch_guismoke_tour.py` /\n"
    "  `_patch_docs_tour.py`。\n"
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


apply(P, [("      ③ 改完跑 `tools/sim_upright_tour.py`（关态无 `S`、开态 `S` 在平台之后、去掉 `S` 支路后与关态逐跳一致，5700 项）。\n",
           "      ③ 改完跑 `tools/sim_upright_tour.py`（关态无 `S`、开态 `S` 在平台之后、去掉 `S` 支路后与关态逐跳一致，5700 项）。\n" + S19)], "\r\n")
append(P, S9, "\r\n")
apply(R, [(R1_OLD, R1_NEW), (R2_OLD, R2_NEW), (R3_OLD, R3_NEW)], "\n")
apply(A, [(A1_OLD, A1_NEW), (A2_OLD, A2_NEW), (A3_OLD, A3_NEW)], "\n")
apply(M, [(M_OLD, M_NEW)], "\n")
append(D, LOG, "\n")
print("全部文档补丁已写盘。")
