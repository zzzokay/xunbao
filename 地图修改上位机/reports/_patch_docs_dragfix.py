# -*- coding: utf-8 -*-
"""同步文档：项目讲解文档/README.md（CRLF）+ map_editor/README.md、AI_CONTEXT.md（LF）。"""
def patch(path, crlf, pairs):
    d = open(path, "rb").read()
    assert d[:3] != b"\xef\xbb\xbf", path + " 意外 BOM"
    if crlf:
        assert d.count(b"\r\n") == d.count(b"\n"), path + " 预期全 CRLF"
    else:
        assert d.count(b"\r\n") == 0, path + " 预期全 LF"
    for i, (o, n) in enumerate(pairs, 1):
        ob = (o.replace("\n", "\r\n") if crlf else o).encode("utf-8")
        nb = (n.replace("\n", "\r\n") if crlf else n).encode("utf-8")
        c = d.count(ob)
        if c != 1:
            raise SystemExit("%s patch %d 命中 %d 次（要求 1），放弃" % (path, i, c))
        d = d.replace(ob, nb)
    if crlf:
        assert d.count(b"\r\n") == d.count(b"\n"), path + " 写盘前行尾检查失败"
    else:
        assert d.count(b"\r\n") == 0, path + " 写盘前行尾检查失败"
    open(path, "wb").write(d)
    print("OK", path, len(d), "bytes")


root = "C:/Users/14166/Desktop/MC_32/robotcup/xunbao"
p1 = root + "/项目讲解文档/README.md"

anchor_pit = "- **表里的补偿值\"会不会生效\"不由表决定**：分支判定在 `map.c: Nav_TurnAndAdvance()`\n"
pit_new = (
 "- **「连线模式」开着会无声改掉左键语义**：`_on_node_press()` 原第一行是\n"
 "  `if connect_from or connect_mode:` → `_connect_pick(name)` → `return` ⇒ 连线模式一开，**点节点就不再拖动**\n"
 "  （单拖、Ctrl 框选的群拖一起失效）；而 Ctrl+框选走的是空白画布那条路径、**照旧能选中紫色**，\n"
 "  于是现象是\"框选能选出来、但一拖就全哑\"。而连线模式很容易被无意打开：**双击任意节点**\n"
 "  （`_on_node_double → start_connect_from`）、**按 `A` 键**（`bind_all(\"<Key-a>\")`）、勾工具栏复选框都会打开它。\n"
 "  已改**拖动优先**：按住节点移动 = 拖动（含群拖），按住没动就松手 = 选连线起点（阈值 `DRAG_START_PX=4`px）。\n"
) + anchor_pit

anchor_extra = ("  静态只能按边表角度算 ⇒ 实车以串口日志为准。\n")
extra_new = anchor_extra + (
 "- **Tk 画布：item 绑定返回 `\"break\"` 挡不住 widget 绑定**（本机实测）：节点 `tag_bind(\"<ButtonPress-1>\")`\n"
 "  跑完 `_on_node_press()`（已装好 `_drag`）之后，画布 `bind(\"<ButtonPress-1>\")` ← `_on_bg_press()` **还会被调一次**。\n"
 "  所以它开头那句 `if self._link or self._drag: return \"break\"` **不是多余的** —— 正是靠它兜住刚装好的拖动状态。\n"
 "  ⇒ 想在那里加\"清理残留状态\"，必须先把这次重复调用认出来（同一次按下的 item / widget 绑定 `serial` 相同，\n"
 "  见 `_ev_token()`），否则会把刚装的 `_drag` 当残留清掉。**本次真栽过**：直调处理函数的测试全过，\n"
 "  只有走真事件链才暴露 —— 交互类改动别只靠直调断言。\n"
 "- **残留指针状态会让 Ctrl 框选「永久失效」**：松开鼠标时指针不在画布上（拖到左右面板 / 窗外松手、\n"
 "  拖动中弹了对话框）⇒ 画布收不到 `<ButtonRelease-1>`，`_drag`/`_link`/`_marquee`/`_bg_drag` 残留；\n"
 "  而旧 `_on_bg_press` 见残留就 `return \"break\"`、空白点击又清不掉 ⇒ **本次运行**里框选一直无效且不报任何错。\n"
 "  已加 `_clear_stale_ptr_state()`：每次**新按下**先清残留（用 `_ev_token()` 区分\"新按下\"与\"同一次按下的重复调用\"）。\n"
)

patch(p1, True, [(anchor_pit, pit_new), (anchor_extra, extra_new)])

# §9 只追加一行
log = (
 "- **2026-10-07**：修「群选 / 单拖都拖不动」【仅上位机】—— 根因是工具栏**「连线模式」被无声打开**\n"
 "  （双击节点 / 按 `A` / 勾复选框都会打开），`_on_node_press()` 第一行就把\"点节点\"换成\"选连线起点\" ⇒\n"
 "  单拖与群拖全哑、而 Ctrl+框选走空白路径照旧能选中 → 现象正是\"框选能选出来、一拖就不动\"。改为**拖动优先**\n"
 "  （按住移动 = 拖、原地松手 = 选起点、`DRAG_START_PX=4`）；并被这次改动逼出一个更隐蔽的坑：\n"
 "  **Tk 画布 item 绑定返回 `break` 挡不住 widget 绑定**（`_on_bg_press` 会再被调一次，原来那句\n"
 "  `if _link or _drag: return break` 就是靠它兜住刚装的 `_drag`）⇒ 新增 `_ev_token()` 按 `serial` 认\"同一次按下\"，\n"
 "  并加 `_clear_stale_ptr_state()`，让残留 `_drag`（松开事件丢了）不再永久废掉 Ctrl 框选。\n"
 "  `_guismoke` 新增 4 组断言（拖动优先 / 抖动容忍 / 原地松手仍能连线 / 残留自愈），全套 **223 项 [OK] / 0 FAIL**（§3.4）"
)
with open(p1, "ab") as f:
    f.write(b"\r\n" + log.replace("\n", "\r\n").encode("utf-8"))
d = open(p1, "rb").read()
assert d.count(b"\r\n") == d.count(b"\n"), "§9 追加后行尾检查失败"
print("OK 追加 §9 日志 ->", p1)

p2 = root + "/地图修改上位机/map_editor/README.md"
patch(p2, False, [
    ("| 工具栏「连线模式」 | 勾上后左键点两个节点也能建边；点边则以它的 to 端起继续连 |\n",
     "| 工具栏「连线模式」 | 勾上后左键点两个节点也能建边；点边则以它的 to 端起继续连。<br>**拖动优先**：连线模式下**按住节点拖仍然是移动**（含 Ctrl 框选的群拖），只有\"按住没动就松手\"才算选连线起点。 |\n"),
    ("点空白或点单条边则恢复单选。 |\n",
     "点空白或点单条边则恢复单选。<br>**连线模式开着也照样能用**（拖动优先）。 |\n"),
    ("  **「线索路线…」/「二轮路线…」对话框能否构建、新入口在界面上真的可见**（206 项）。\n",
     "  **连线模式下拖动优先（拖 = 移动/群拖、原地松手 = 选起点、抖动 ≤4px 不误判、残留指针状态自愈）**、\n"
     "  **「线索路线…」/「二轮路线…」对话框能否构建、新入口在界面上真的可见**（223 项）。\n"),
    ("| `_guismoke.py` | 界面冒烟测试（206 项；",
     "| `_guismoke.py` | 界面冒烟测试（223 项；"),
])

p3 = root + "/地图修改上位机/map_editor/AI_CONTEXT.md"
patch(p3, False, [
    ("界面冒烟测试（206 项）", "界面冒烟测试（223 项）"),
    ("# 期望：206 项 [OK] / 0 FAIL", "# 期望：223 项 [OK] / 0 FAIL"),
])
print("全部文档已更新")
