# -*- coding: utf-8 -*-
"""同步文档：Shift 新语义 + 双击不再连线；并把冒烟项数 223 → 230。"""
root = "C:/Users/14166/Desktop/MC_32/robotcup/xunbao"


def patch(path, crlf, pairs):
    d = open(path, "rb").read()
    assert d[:3] != b"\xef\xbb\xbf", path + " 意外 BOM"
    assert (d.count(b"\r\n") == d.count(b"\n")) if crlf else (d.count(b"\r\n") == 0), \
        path + " 行尾预期不符"
    for i, (o, n) in enumerate(pairs, 1):
        ob = (o.replace("\n", "\r\n") if crlf else o).encode("utf-8")
        nb = (n.replace("\n", "\r\n") if crlf else n).encode("utf-8")
        c = d.count(ob)
        if c != 1:
            raise SystemExit("%s patch %d 命中 %d 次（要求 1），放弃" % (path, i, c))
        d = d.replace(ob, nb)
    assert (d.count(b"\r\n") == d.count(b"\n")) if crlf else (d.count(b"\r\n") == 0), \
        path + " 写盘前行尾检查失败"
    open(path, "wb").write(d)
    print("OK", path)


# ================= 1) map_editor/README.md（LF）=================
p1 = root + "/地图修改上位机/map_editor/README.md"
patch(p1, False, [
    # 交互表：Shift 行
    ("| **Shift + 从节点拖出** | 拉一条新边，松手落在目标节点上（备用方式） |\n",
     "| **Shift + 点节点** ⭐ | **连线**：Shift+点一个节点 = 起点；之后**松开 Shift 用普通左键点**另一个节点即成边"
     "（按住 Shift 连点两下也行）。**Shift 只管\"定起点\"，不会留下常驻的「连线模式」**。 |\n"
     "| **Shift + 从节点拖出** | 拉一条新边，松手落在目标节点上（Shift 拖动才会触发；原地松手则按上一行\"定起点\"处理） |\n"),
    # 交互表：双击行
    ("| 双击节点 | 同「右键点节点」（备用；原来只有这条路，左键双击经常点不中） |\n",
     "| 双击节点 | **不再连线**（防误触，只在状态栏提示）；连线请用 **Shift+点节点** 或 右键点节点 |\n"),
    # 取消连线的说明
    ("> **连线怎么取消？** 再右键起点自己 / 点一下空白 / 按 `Esc`，都会放弃待连线的起点。\n",
     "> **连线怎么取消？** 再点一下起点自己（右键 / Shift+左键都行）/ 点一下空白 / 按 `Esc`，都会放弃待连线的起点。\n"),
    # 为什么改成右键 的注：补 10-07 变更
    ("> 右键单击更稳。节点菜单的功能一个没少，只是挪到了 **Shift+右键**。\n",
     "> 右键单击更稳。节点菜单的功能一个没少，只是挪到了 **Shift+右键**。\n"
     "> **10-07 起**：**双击节点不再连线**（太容易误触发）—— 连线只剩 `Shift+点` 与 `右键点` 两个有意图的入口；\n"
     "> 且 `Shift+点` 只是\"定起点\"，**不会**像以前的双击那样顺手把「连线模式」开关打开（那正是\n"
     "> \"只是点了几下不同的点就自动连出边\"的根因）。\n"),
    # 键盘
    ("`Ctrl+Z` 撤销 · `Ctrl+Y` 重做 · `Ctrl+S` **保存布局** · `Delete` 删除选中 · `F1` 帮助\n",
     "`Ctrl+Z` 撤销 · `Ctrl+Y` 重做 · `Ctrl+S` **保存布局** · `Delete` 删除选中 · `F1` 帮助\n"
     "`A` 以**当前选中节点**为起点连线（等价于 Shift+点它）· `Esc` 取消连线起点并关掉「连线模式」\n"),
    # 冒烟覆盖清单
    ("  **连线模式下拖动优先（拖 = 移动/群拖、原地松手 = 选起点、抖动 ≤4px 不误判、残留指针状态自愈）**、\n",
     "  **连线模式下拖动优先（拖 = 移动/群拖、原地松手 = 选起点、抖动 ≤4px 不误判、残留指针状态自愈）**、\n"
     "  **Shift = 连线（只定起点、不留常驻模式、Shift+拖=拉新边、Shift+双击空白仍建节点）、双击节点不再连线**、\n"),
    ("真的可见**（223 项）。\n", "真的可见**（230 项）。\n"),
    ("| `_guismoke.py` | 界面冒烟测试（223 项；",
     "| `_guismoke.py` | 界面冒烟测试（230 项；"),
])

# ================= 2) map_editor/AI_CONTEXT.md（LF）=================
p2 = root + "/地图修改上位机/map_editor/AI_CONTEXT.md"
patch(p2, False, [
    ("界面冒烟测试（223 项）", "界面冒烟测试（230 项）"),
    ("# 期望：223 项 [OK] / 0 FAIL", "# 期望：230 项 [OK] / 0 FAIL"),
    (":**右键连线（含 Shift+右键=菜单、左键也能完成、取消起点）**、",
     ":**右键连线（含 Shift+右键=菜单、左键也能完成、取消起点）**、**Shift = 连线（只定起点、不留常驻模式）**、"),
    ("右键节点=开始/完成连线，**Shift+右键=节点菜单**（`_on_node_menu`）。`_on_node_press` 与 `_connect_pick` 共用同一套取点逻辑；改完跑 `_guismoke` 的右键断言。**别把菜单绑回裸右键**（那就又变回\"左键点不中\"的老问题） |",
     "右键节点=开始/完成连线，**Shift+右键=节点菜单**（`_on_node_menu`）。`_on_node_press` 与 `_connect_pick` 共用同一套取点逻辑；改完跑 `_guismoke` 的右键断言。**别把菜单绑回裸右键**（那就又变回\"左键点不中\"的老问题）。<br>**10-07 起 Shift+左键节点 = 定/续连线起点**（`_on_node_press` 的 shift 分支走 `_link`，拖动优先：`armed` 才拉新边，否则松手当定起点），**双击节点已不再连线**（`_on_node_double` 只提示）—— 因为"双击=进入连线模式"会让之后普通点几下就自动连出边 |"),
])

# ================= 3) 项目讲解文档/README.md（CRLF）=================
p3 = root + "/项目讲解文档/README.md"
anchor = "- **Tk 画布：item 绑定返回 `\"break\"` 挡不住 widget 绑定**（本机实测）"
new_bullet = (
 "- **别把\"进入某模式\"绑在\"双击 / 普通点几下\"这类日常动作上**：10-07 前\"**双击节点 = 以它为起点连线**\"\n"
 "  还会顺手把「连线模式」置真 ⇒ 之后**普通点几下不同节点就把边连出来了**，用户报\"连线太容易触发\"。\n"
 "  已改：双击节点只提示、不动任何状态；连线只保留有明确意图的入口 —— **Shift+点起点** 与 **右键点节点**。\n"
 "  同理 `A` 键那个 `bind_all` 也属于\"一按就进模式\"，保留着但要知道它同样是误触源（用户选择保留）。\n"
) + anchor
patch(p3, True, [(anchor, new_bullet)])

log = (
 "- **2026-10-07**：上位机连线交互收敛（用户报\"连线太容易触发\"）【仅上位机】—— 旧版**双击节点**\n"
 "  （`_on_node_double → start_connect_from`）会顺手把「连线模式」置真，之后普通点几下不同节点就自动连边。\n"
 "  改为：**双击节点不再连线**（只状态栏提示）；**Shift+左键节点 = 定/续连线起点**（`_on_node_press` 的 shift 分支\n"
 "  走\"拖动优先\"：`armed` 才拉新边、原地松手当定起点，沿用 `DRAG_START_PX=4`），且**不再留下常驻「连线模式」**；\n"
 "  右键点节点（连线）/ Shift+右键（菜单）/ A 键 / 工具栏复选框 均按用户要求保留。`_guismoke` 加 7 项断言\n"
 "  （Shift 定起点 / 松开 Shift 后普通点完成 / Shift 点两下 / 双击不再连线 / Shift 抖动容忍…）⇒ **230 项 [OK] / 0 FAIL**；\n"
 "  另修 `map_editor/README.md` 一处与代码不符（\"空白处拖 = 平移\"，实际只有中键能平移）（§3.4）"
)
with open(p3, "ab") as f:
    f.write(b"\r\n" + log.replace("\n", "\r\n").encode("utf-8"))
d = open(p3, "rb").read()
assert d.count(b"\r\n") == d.count(b"\n"), "§9 追加后行尾检查失败"
print("OK 追加 §9 ->", p3)
print("全部文档已更新")
