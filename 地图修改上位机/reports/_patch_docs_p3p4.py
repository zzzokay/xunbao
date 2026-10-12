# -*- coding: utf-8 -*-
"""AI 过程脚本：同步「一轮回程补打卡 P3/P4」的文档。

行尾：项目讲解文档/README.md = CRLF；其余 = LF。每个替换 assert 命中恰好 1 次。
"""
import os

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"
P = os.path.join(ROOT, "项目讲解文档", "README.md")
R = os.path.join(ROOT, "地图修改上位机", "map_editor", "README.md")
A = os.path.join(ROOT, "地图修改上位机", "map_editor", "AI_CONTEXT.md")
T = os.path.join(ROOT, "地图修改上位机", "tools", "README.md")
M = os.path.join(ROOT, ".workbuddy", "memory", "MEMORY.md")
D = os.path.join(ROOT, ".workbuddy", "memory", "2026-10-07.md")

S21 = (
    "21. **一轮回程「补打卡」P3/P4：开关 `P3P4_PUNCH_ENABLE`（默认关）；「去过」有两个口径，别合并。**（2026-10-07 新增）\n"
    "    - **它解决什么**：一轮去程只在 `flag_line_clue`（QR 百位）=3 去 P3、=4 去 P4；而**正常固件里它的初值是 0**\n"
    "      （`barrier.c:82`，只有 `DEBUG=1` 才是 3）⇒ 现场常常**一个 P3/P4 都没打卡**。打开本开关后，一轮**取宝之后**的回家腿把没去的补上。\n"
    "    - **判据（缺哪个补哪个）**：`flag_line_clue != 3 && treasure != 3` 才补 `P3`；`!= 4 && treasure != 4` 才补 `P4`。\n"
    "      两个「去过」的判据是**去程百位**与**宝物平台本身**（回程去宝物平台时已经在那儿打卡了）—— 它们**不是同一个东西**，\n"
    "      也**不能**用 `treasure != 0` 代替（那是 §2.14 的老坑）。\n"
    "    - **落点**：`mission_planner.c` **两处** —— `plan_treasure_return()`（P7/P8 读到宝物后的回程腿）与\n"
    "      `route_return_home()`（过门回程）；位置都在**宝物平台之后、`S1/S2`（`UPRIGHT_TOUR_ENABLE`）之前**，顺序固定 `P3 -> P4`；\n"
    "      `route_return_home()` 的 `wp[6] -> wp[8]`（最坏 nowNode + 宝物平台 + P3 + P4 + S + P2 = 6 个点）。\n"
    "      ⚠️ **两处都得插**：回程过门时 `door()` 会重规划后半段，与本函数各管一段（同 §2.19）。\n"
    "    - ⚠️ **`P3 -> P4` 只是「补打卡内部」的顺序**：宝物平台**必须排在最前**（取宝之前去任何平台 = 走错即结束比赛）\n"
    "      ⇒ 宝物 = P4 时实际走法是 `P4 -> P3`（先取宝、再补 P3），不是 `P3 -> P4`。\n"
    "    - ⚠️ **打开会改掉门回程路线** ⇒ `validate/_check_door_perm.py` 的 12 条 golden 只在开关**关**的时候成立\n"
    "      （**默认就是关**，所以改动后它照样 12/12 通过；哪天把它打开，那 12 条要按新语义重算）。\n"
    "    - **上位机镜像**：`map_model.p3p4_punch_waypoints(treasure, line_clue)` +\n"
    "      `treasure_return_waypoints()/door_return_home_waypoints()` 的 `line_clue`/`punch` 参数；\n"
    "      「线索路线…」对话框新增「回程补打卡 P3/P4」下拉（**跟随 config.h** / 强制开 / 强制关）。\n"
    "    - **仿真**：`tools/sim_route_bookkeeping.py` 的源同步自检已扩到本开关（两处插点 / 二轮不该有 / `wp` 容量 ≥ 6），\n"
    "      启动时打印开关取值 + 一张「门回程 wp 对比表」（关 → 开）。\n"
    "\n"
)

S9 = (
    "- **2026-10-07**：一轮回程加「补打卡 P3/P4」开关 `P3P4_PUNCH_ENABLE`（`config.h`，**默认 0 = 现状不变**）—— 取宝后的回家腿"
    "把去程没去的 P3/P4 补上（缺哪个补哪个：百位=3 补 P4 / =4 补 P3 / =0 两个都补；宝物平台本身不重复加），顺序固定 P3→P4、"
    "排在 S1/S2 之前；`mission_planner.c` 两处插点（`plan_treasure_return` / `route_return_home`）+ `route_return_home` 的 "
    "`wp[6]→wp[8]`。EIDE 无头编译 **0 error / 0 warning**；`validate/` 8 个脚本与改动前一致（`_check_door_perm.py` 仍 **12/12**，"
    "因为开关默认关）；上位机镜像（`map_model` 纯函数 + 「线索路线…」对话框新下拉）与 `tools/sim_route_bookkeeping.py` 源同步自检"
    "同步扩到本开关；`_guismoke` **266 项（265 OK / 1 项既有 FAIL：N8 那条，属边表/权重 WIP）**（§2.21）\n"
)

R_OLD = "  **宝物线索**（P1~P6）。四个「阶段」各镜像固件里一条确定的代码路径：\n"
R_NEW = ("  **宝物线索**（P1~P6）、**回程补打卡 P3/P4**（`P3P4_PUNCH_ENABLE`：跟随 config.h / 强制开 / 强制关）。\n"
         "  四个「阶段」各镜像固件里一条确定的代码路径：\n")

R_COUNT_OLD = "  **小车动画（入口可见 / 起跑与暂停 / 沿路线推进 / 循环取模 / 停止后清干净）**（261 项）。\n"
R_COUNT_NEW = ("  **小车动画（入口可见 / 起跑与暂停 / 沿路线推进 / 循环取模 / 停止后清干净）**、\n"
               "  **回程补打卡 P3/P4（纯函数缺哪个补哪个 / 跟随 config.h / 门回程 wp 顺序 / 规划路线真的绕到 P4、P3）**\n"
               "  （266 项：265 OK / 1 项**既有** FAIL —— 就是 `N8` 那条，属边表/权重 WIP）。\n")

R_TAB_OLD = "| `_guismoke.py` | 界面冒烟测试（261 项；**绝不碰 `layouts/*.json` 与真实 `map.c`**，且固定跑固件源码地图） |\n"
R_TAB_NEW = "| `_guismoke.py` | 界面冒烟测试（266 项；**绝不碰 `layouts/*.json` 与真实 `map.c`**，且固定跑固件源码地图） |\n"

A_29_OLD = "| `_guismoke.py` | 界面冒烟测试（261 项），**全程沙箱，绝不碰真实布局 / 真实 `map.c`** | 见 §7 隔离规则 |\n"
A_29_NEW = "| `_guismoke.py` | 界面冒烟测试（266 项），**全程沙箱，绝不碰真实布局 / 真实 `map.c`** | 见 §7 隔离规则 |\n"

A_314_OLD = "python 地图修改上位机/map_editor/_guismoke.py     # 期望：261 项 [OK] / 0 FAIL\n"
A_314_NEW = ("python 地图修改上位机/map_editor/_guismoke.py     # 期望：266 项（265 OK / 1 项既有 FAIL）\n")

A_ROW_OLD = "改完跑 `_guismoke` 的「route animation (car)」段 |\n"
A_ROW_NEW = (
    "改完跑 `_guismoke` 的「route animation (car)」段 |\n"
    "| **改一轮回程「补打卡 P3/P4」** | 固件 `config.h` 的 `P3P4_PUNCH_ENABLE` + `mission_planner.c` **两处**插点"
    "（`plan_treasure_return` / `route_return_home`）；镜像 `M.p3p4_punch_waypoints(treasure, line_clue)` + "
    "`treasure_return_waypoints(..., line_clue, punch)` / `door_return_home_waypoints(..., line_clue, punch)`；"
    "界面 `App._punch_on()` + 对话框 `PUNCH_VALS`；仿真 `tools/sim_route_bookkeeping.py` 的自检 | "
    "见 `项目讲解文档/README.md` §2.21。**「去过」有两个口径**：去程 QR 百位（`flag_line_clue`）与**宝物平台本身**"
    "（`treasure`）—— 别合并、更别拿 `treasure != 0` 代替。打开会改门回程路线 ⇒ `validate/_check_door_perm.py` 的 12 golden "
    "只在开关**关**时成立。改完跑 `_guismoke` 的「round-1 return: extra P3/P4 punch」段 + `sim_route_bookkeeping.py` |\n")

T_OLD = ("**开机先读 `Mission/config.h` 的 `UPRIGHT_TOUR_ENABLE` 并对 `mission_planner.c` 自检**"
         "（三处 `S` 插点 / 开关取值 / `wp` 容量），对不上就报「镜像已过期」并 exit 1；"
         "另校验红线「`S1`/`S2` 不得排在宝物平台之前」")
T_NEW = ("**开机先读 `Mission/config.h` 的 `UPRIGHT_TOUR_ENABLE` / `P3P4_PUNCH_ENABLE` 并对 `mission_planner.c` 自检**"
         "（`S` 三处 + `P3`/`P4` 两处插点 / 两个开关取值 / `wp` 容量），对不上就报「镜像已过期」并 exit 1；"
         "另校验红线「`S1`/`S2` 不得排在宝物平台之前」，并打印「补打卡」开关下的门回程 wp 对比表")

M_OLD = ("- **回程去 P3/P4 宝物平台**（`route_return_home` 的 `treasure==3→P3` / `==4→P4`、`plan_treasure_return`\n"
         "  的 `target`）是**老逻辑**（09-11 提交 `31d69a5` 起就这��），**没有开关**、硬编码。\n")
M_NEW = (M_OLD +
         "- `P3P4_PUNCH_ENABLE=0`（**10-07 新增**，默认关）：一轮**取宝之后**的回家腿把去程没去的 P3/P4 **补打卡**\n"
         "  （缺哪个补哪个：百位=3 补 P4 / =4 补 P3 / =0 两个都补；宝物平台本身不重复加）。落点 `mission_planner.c`\n"
         "  **两处**（`plan_treasure_return` / `route_return_home`），顺序固定 P3→P4、排在 S1/S2 之前；\n"
         "  `route_return_home` 的 `wp[6]→wp[8]`。⚠️ 宝物平台必须排最前 ⇒ 宝物=P4 时实际走 **P4→P3**。\n"
         "  打开会改门回程 ⇒ `validate/_check_door_perm.py` 的 12 golden 只在**关**时成立。\n"
         "  镜像：`M.p3p4_punch_waypoints()` + 对话框「回程补打卡 P3/P4」下拉；`sim_route_bookkeeping.py` 自检已覆盖。README §2.21。\n")

LOG = (
    "\n## 新增开关 `P3P4_PUNCH_ENABLE`（一轮回程补打卡 P3/P4）【固件 + 上位机】\n"
    "\n"
    "- **用户要求**：一轮回程时，**3 和 4（P3/P4）没走就都补打卡完再回家**；上位机和固件都改。\n"
    "  追问后定：**缺哪个补哪个**、开关名 `P3P4_PUNCH_ENABLE`、**默认关 0**、顺序 **P3→P4**（排在 S1/S2 之前）。\n"
    "- **固件**：`Mission/config.h`（LF+BOM）加开关块；`Mission/mission_planner.c`（CRLF）**两处**插点\n"
    "  （`plan_treasure_return` / `route_return_home`，都在宝物平台之后、S1/S2 之前）+ `route_return_home` 的 `wp[6]→wp[8]`\n"
    "  （最坏 6 个点）。判据 = `flag_line_clue != 3/4 && treasure != 3/4`（两个「去过」口径：去程百位 + 宝物平台）。\n"
    "- **上位机**：`map_model.py` 新增纯函数 `p3p4_punch_waypoints()`，`treasure_return_waypoints()` /\n"
    "  `door_return_home_waypoints()` 加 `line_clue`/`punch` 参数（**默认关 ⇒ 老调用点行为不变**）；\n"
    "  `map_editor.py`：`App._punch_on()`（「跟随 config.h」**直读 config.h**，不用布局里的宏快照）+ 对话框第 5 个下拉\n"
    "  `PUNCH_VALS`（跟随 config.h / 强制开 / 强制关）+ punch 透传到 `_clue_route_sections`/`_round1_complete`/`_append_after_door`。\n"
    "- **仿真**：`tools/sim_route_bookkeeping.py` 自检扩到本开关（两处插点 / 二轮不该有 / `wp` ≥ 6）+ 打印门回程 wp 对比表。\n"
    "- **验证**：EIDE 无头编译 **0 error / 0 warning**（`compiled` 含 `mission_planner.c`）；`validate/` 8 个脚本与改动前一致\n"
    "  （`_check_door_perm.py` 仍 **12/12** —— 开关默认关）；`_guismoke.py` **265 [OK] / 1 既有 FAIL**（N8 那条，\n"
    "  已用 stash@{0} 换回改动前版本对比过：改动前也是 1 FAIL ⇒ 既有，源于用户改边表/权重）；\n"
    "  wp 对比表（关 → 开）：线索3/宝物P1 `N2 P1 P2`→`N2 P1 P4 P2`；线索4 `→N2 P1 P3 P2`；线索0 `→N2 P1 P3 P4 P2`；\n"
    "  宝物P4 → `N2 P4 P2`→`N2 P4 P3 P2`（**宝物平台在前**，符合「取宝后才能去别的平台」）。\n"
    "- **⚠️ 顺手发现的行尾问题（重要）**：`地图修改上位机/**/*.py` 现在**都是 CRLF**（本会话开始时 `map_editor.py` 是 LF，\n"
    "  mtime 显示 19:21/19:46 被外部——编辑器保存——改过）。补丁脚本已改成**先探测 eol 再替换**，没有去改它们的行尾；\n"
    "  但**上位机 .py 的行尾约定事实上已经变了**，谁在意请自己统一。\n"
    "- 补丁脚本：`reports/_patch_fw_p3p4_punch.py` / `_patch_pc_p3p4_punch.py` / `_patch_pc_p3p4_punch2.py` /\n"
    "  `_patch_guismoke_p3p4.py` / `_patch_sim_p3p4*.py` / `_patch_docs_p3p4.py`；\n"
    "  对比脚本：`reports/_verify_guismoke_baseline.py`。快照：`stash@{0}` = \"加回 UPRIGHT_NEED_TREASURE 前\"。\n"
)


def apply(path, edits, eol):
    with open(path, "rb") as f:
        data = f.read()
    for old, new in edits:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "%s 命中 %d 次（期望 1）:\n%r" % (os.path.basename(path), cnt, old[:70])
        data = data.replace(ob, nb)
    with open(path, "wb") as f:
        f.write(data)
    crlf, lf = data.count(b"\r\n"), data.count(b"\n") - data.count(b"\r\n")
    print("[ok] %-14s crlf=%d lf=%d" % (os.path.basename(path), crlf, lf))


def append(path, text, eol):
    with open(path, "rb") as f:
        d = f.read()
    with open(path, "wb") as f:
        f.write(d + text.replace("\n", eol).encode("utf-8"))
    print("[ok] %-14s 追加 %d bytes" % (os.path.basename(path), len(text.encode("utf-8"))))


apply(P, [("## 3. 地图修改上位机（`地图修改上位机/`）\n", S21 + "## 3. 地图修改上位机（`地图修改上位机/`）\n")], "\r\n")
append(P, S9, "\r\n")
apply(R, [(R_OLD, R_NEW), (R_COUNT_OLD, R_COUNT_NEW), (R_TAB_OLD, R_TAB_NEW)], "\n")
apply(A, [(A_29_OLD, A_29_NEW), (A_314_OLD, A_314_NEW), (A_ROW_OLD, A_ROW_NEW)], "\n")
apply(T, [(T_OLD, T_NEW)], "\n")
apply(M, [(M_OLD, M_NEW)], "\n")
append(D, LOG, "\n")
print("全部文档补丁已写盘。")
