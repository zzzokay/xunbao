# -*- coding: utf-8 -*-
"""补跑：AI_CONTEXT.md + 项目讲解文档/README.md（README.md 上一轮已写成功）。"""
root = "C:/Users/14166/Desktop/MC_32/robotcup/xunbao"


def patch(path, crlf, pairs):
    d = open(path, "rb").read()
    assert d[:3] != b"\xef\xbb\xbf", path + " 意外 BOM"
    ok = (d.count(b"\r\n") == d.count(b"\n")) if crlf else (d.count(b"\r\n") == 0)
    assert ok, path + " 行尾预期不符"
    for i, (o, n) in enumerate(pairs, 1):
        ob = (o.replace("\n", "\r\n") if crlf else o).encode("utf-8")
        nb = (n.replace("\n", "\r\n") if crlf else n).encode("utf-8")
        c = d.count(ob)
        if c != 1:
            raise SystemExit("%s patch %d 命中 %d 次（要求 1），放弃" % (path, i, c))
        d = d.replace(ob, nb)
    ok = (d.count(b"\r\n") == d.count(b"\n")) if crlf else (d.count(b"\r\n") == 0)
    assert ok, path + " 写盘前行尾检查失败"
    open(path, "wb").write(d)
    print("OK", path)


p2 = root + "/地图修改上位机/map_editor/AI_CONTEXT.md"
patch(p2, False, [
    ("界面冒烟测试（223 项）", "界面冒烟测试（233 项）"),
    ("# 期望：223 项 [OK] / 0 FAIL", "# 期望：233 项 [OK] / 0 FAIL"),
    ("**连线模式点两下建边**、",
     "**Shift+点节点=连线（起点=当前选中节点、按住才生效）、双击节点不再连线**、**连线模式点两下建边**、"),
    ("右键节点=开始/完成连线，**Shift+右键=节点菜单**（`_on_node_menu`）。`_on_node_press` 与 `_connect_pick` 共用同一套取点逻辑；改完跑 `_guismoke` 的右键断言。**别把菜单绑回裸右键**（那就又变回\"左键点不中\"的老问题） |",
     "右键节点=开始/完成连线，**Shift+右键=节点菜单**（`_on_node_menu`）。改完跑 `_guismoke` 的右键断言。**别把菜单绑回裸右键**（那就又变回\"左键点不中\"的老问题）。<br>**10-07 起的 Shift+左键节点 = 连线**：`_on_node_press` 的 shift 分支 → `_connect_from_sel(name)`，起点取 `sel_node`（没有则退回 `connect_from`），连完 `select_node(name)` ⇒ 按住 Shift 可链式连；**Shift 只是按住生效的修饰键、不改 `connect_mode`**。<br>**双击节点已不再连线**（`_on_node_double` 只提示）——\"双击 = 进入连线模式\"会让之后普通点几下就自动连出边；**Shift+拖出拉边也已取消**（`_link` 只留残留声明） |"),
])

p3 = root + "/项目讲解文档/README.md"
anchor = "- **Tk 画布：item 绑定返回 `\"break\"` 挡不住 widget 绑定**（本机实测）"
new_bullet = (
 "- **别把\"进入某模式\"绑在\"双击 / 普通点几下\"这类日常动作上**：10-07 前\"**双击节点 = 以它为起点连线**\"\n"
 "  还会顺手把「连线模式」置真 ⇒ 之后**普通点几下不同节点就把边连出来了**，用户报\"连线太容易触发\"。\n"
 "  定下来的操作是：**普通单击 = 选中/拖动**；**按住 Shift = 连线**（起点取\"当前选中的节点\"，点别的点即连，\n"
 "  松开 Shift 回普通；连完选中挪到终点 ⇒ 可按着 Shift 链式连）；**双击节点只提示、不连线**。\n"
 "  ⇒ 连线只剩 `Shift+点节点` 与 `右键点节点` 两个有意图的入口。同理 `A` 键那个 `bind_all` 也是\n"
 "  \"一按就进模式\"，属同类误触源（用户选择保留，但要知道它是）。\n"
) + anchor
patch(p3, True, [(anchor, new_bullet)])

log = (
 "- **2026-10-07**：上位机连线交互收敛（用户报\"连线太容易触发\"）【仅上位机】—— 旧版**双击节点**\n"
 "  （`_on_node_double → start_connect_from`）会顺手把「连线模式」置真，之后普通点几下不同节点就自动连边。\n"
 "  操作定为：**普通单击 = 选中/拖动**；**按住 Shift = 连线**（`_connect_from_sel()`：起点取当前选中节点，\n"
 "  点别的点即连、连完选中挪到终点 ⇒ 可按着 Shift 链式连；松开 Shift 即回普通，**不改 `connect_mode`**）；\n"
 "  **双击节点不再连线**（只提示）；**Shift+从节点拖出拉边已取消**（Shift 改作\"按住 = 连线\"的修饰键，\n"
 "  `_link` 仅留残留声明）。右键点节点（连线）/ Shift+右键（菜单）/ A 键 / 工具栏复选框 按用户要求保留。\n"
 "  `_guismoke` 加 8 项断言（选中起点→Shift 连线→链式→松开回普通→不连自环→双击不连线…）⇒ **233 项 [OK] / 0 FAIL**；\n"
 "  另修 `map_editor/README.md` 一处与代码不符（\"空白处拖 = 平移\"，实际只有中键能平移）（§3.4）"
)
with open(p3, "ab") as f:
    f.write(b"\r\n" + log.replace("\n", "\r\n").encode("utf-8"))
d = open(p3, "rb").read()
assert d.count(b"\r\n") == d.count(b"\n"), "§9 追加后行尾检查失败"
print("OK 追加 §9 ->", p3)
