# -*- coding: utf-8 -*-
"""AI 过程脚本：给「小车动画」特性同步文档（字节级替换，保持各自行尾）。

- 地图修改上位机/map_editor/README.md   → LF
- 地图修改上位机/map_editor/AI_CONTEXT.md → LF
- 项目讲解文档/README.md                → CRLF
- .workbuddy/memory/MEMORY.md           → LF
- .workbuddy/memory/2026-10-07.md       → LF
每个替换都 assert 命中恰好 1 次，全部成功才写盘。
"""
import os
import sys

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"

EDITS = []   # (path, mode('replace'|'append'), old, new)


def rep(path, old, new):
    EDITS.append((path, "replace", old, new))


def app(path, text):
    EDITS.append((path, "append", None, text))


# ---------------------------------------------------------------- README (map_editor)
R = os.path.join(ROOT, "地图修改上位机", "map_editor", "README.md")

rep(R,
    '  选只看单段会画不出线，状态栏会说明原因。细节见下面「第一轮·完整路线」是怎么拼的 → **画布**。\n',
    '  选只看单段会画不出线，状态栏会说明原因。细节见下面「第一轮·完整路线」是怎么拼的 → **画布**。\n'
    '\n'
    '  - **「▶ 小车动画」**（2026-10-07 新增）：让一辆小车**沿当前规划好的路线匀速跑起来**，循环播放；\n'
    '    右边「⏹」停止、**倍速**滑条 0.2~4.0x。**纯画布动画** —— 不改 `route[]`、不改模型、不动固件。\n'
    '    - 车头**朝向随行进方向转**（前风挡浅蓝、车尾拖一小截浅红尾迹），车上方标出**正在驶向的节点名**。\n'
    '    - 进度按"占全长比例"存 ⇒ **缩放/平移/旋转、乃至拖动节点，车都立刻走在正确的位置**；\n'
    '      速度按**屏幕像素/秒**算（基准 220px/s）⇒ 放大缩小时"看起来一样快"。\n'
    '    - 路线一改（重新规划）⇒ 从新起点**重播**；`清路线` 会**顺带停掉**动画。\n'
    '    - ⚠️ 播放前得先有一条 ≥2 节点的路线（先点「规划路线 / 常规路线 / 线索路线…」）。\n')

rep(R,
    '  **「线索路线…」/「二轮路线…」对话框能否构建、新入口在界面上真的可见**（245 项）。',
    '  **「线索路线…」/「二轮路线…」对话框能否构建、新入口在界面上真的可见**、\n'
    '  **小车动画（入口可见 / 起跑与暂停 / 沿路线推进 / 循环取模 / 停止后清干净）**（254 项）。')

rep(R,
    '| `_guismoke.py` | 界面冒烟测试（245 项；**绝不碰 `layouts/*.json` 与真实 `map.c`**，且固定跑固件源码地图） |',
    '| `_guismoke.py` | 界面冒烟测试（254 项；**绝不碰 `layouts/*.json` 与真实 `map.c`**，且固定跑固件源码地图） |')

# ---------------------------------------------------------------- AI_CONTEXT
A = os.path.join(ROOT, "地图修改上位机", "map_editor", "AI_CONTEXT.md")

rep(A,
    '| `_guismoke.py` | 界面冒烟测试（245 项），**全程沙箱，绝不碰真实布局 / 真实 `map.c`** | 见 §7 隔离规则 |',
    '| `_guismoke.py` | 界面冒烟测试（254 项），**全程沙箱，绝不碰真实布局 / 真实 `map.c`** | 见 §7 隔离规则 |')

rep(A,
    'python 地图修改上位机/map_editor/_guismoke.py     # 期望：245 项 [OK] / 0 FAIL',
    'python 地图修改上位机/map_editor/_guismoke.py     # 期望：254 项 [OK] / 0 FAIL')

rep(A,
    '     `值 min~max`，不是一个确定数；`TURN_CALC_ENABLE=1` 时公式是**静默生效**的。\n'
    '\n'
    '---\n',
    '     `值 min~max`，不是一个确定数；`TURN_CALC_ENABLE=1` 时公式是**静默生效**的。\n'
    '\n'
    '15. **路线动画（小车）只准"画"，不准"改"**（`App._anim_*`）：它沿 `self.route` 匀速跑，但\n'
    '   `self.route` / `route_split` / 模型 / 固件**一个都不动**；停止 / 清路线后必须把画布上的图元\n'
    '   清干净（都打 `tags="anim"`，`_anim_clear()` 按 id + 按标签双保险）。三个关键设计：\n'
    '   - **进度存"占全长比例" `anim_frac`**（不是绝对像素）⇒ 缩放 / 平移 / 旋转 / 拖节点都不会让车跳位；\n'
    '     几何每帧从 `self.route` 现算，所以**任何"设置 route"的地方都不用额外通知动画**\n'
    '     （`_anim_tick` 用 `anim_route_key` 快照比对，路线变了就自动从起点重播）。\n'
    '   - **速度按屏幕像素/秒**（`ANIM_BASE_PX_PER_SEC` × 倍速）⇒ 观感与缩放无关。\n'
    '   - **画在 `redraw()` 末尾**（`_anim_draw()`）⇒ 缩放 / 平移 / 拖动时车跟着走；\n'
    '     `clear_route()` / `_on_close()` 必须 `anim_stop()`（前者防沿空路线报错，后者防关窗后\n'
    '     `after` 回调报 `TclError`）。\n'
    '   改完跑 `_guismoke` 的「route animation (car)」段（起跑 / 暂停 / 推进 / 循环取模 / 清干净）。\n'
    '\n'
    '---\n')

rep(A,
    '| **改路线配色/去程回程分色** | `ROUTE_COLOR` / `ROUTE_COLOR_BACK` / `_draw_route()` + `App.route_split`；画布过滤 `ROUTE_VIEW_MODES` / `App.route_view` / `_route_view_changed()` / `_route_split_ok()` | 分色只在"完整路线"生效；`route_split` 必须在所有设置 `self.route` 的地方一起复位，见 §6.10。**过滤只影响绘制，不改 `self.route`**；`_route_split_ok()` 为假（未分色）时只看单段 ⇒ 一段都不画 + 状态栏说明，不许瞎画 |\n',
    '| **改路线配色/去程回程分色** | `ROUTE_COLOR` / `ROUTE_COLOR_BACK` / `_draw_route()` + `App.route_split`；画布过滤 `ROUTE_VIEW_MODES` / `App.route_view` / `_route_view_changed()` / `_route_split_ok()` | 分色只在"完整路线"生效；`route_split` 必须在所有设置 `self.route` 的地方一起复位，见 §6.10。**过滤只影响绘制，不改 `self.route`**；`_route_split_ok()` 为假（未分色）时只看单段 ⇒ 一段都不画 + 状态栏说明，不许瞎画 |\n'
    '| **改路线动画（小车）** | `App.anim_toggle/anim_resume/anim_pause/anim_stop` + `_anim_tick`（定时推进）+ `_anim_draw`（画小车）+ `_route_screen_polyline` / `_polyline_metrics` / `_point_at_frac` / `_polyline_slice` / `_car_sprite_pts`；常量 `CAR_*` / `ANIM_*`；入口在左栏「路线规划」面板 | 见 §6.15。**纯绘制**：不改 `self.route`、不改模型、不进固件；`redraw()` 末尾挂钩、`clear_route()`/`_on_close()` 里 `anim_stop()`。改完跑 `_guismoke` 的「route animation (car)」段 |\n')

# ---------------------------------------------------------------- 讲解文档 §9（CRLF）
P = os.path.join(ROOT, "项目讲解文档", "README.md")
app(P,
    '\r\n- **2026-10-07**：地图编辑器加「小车动画」【仅上位机】—— 让小车沿**规划好的路线**匀速跑起来（循环、可暂停/停止、倍速 0.2~4x），带朝向的小车图形 + 正在驶向的节点名 + 车尾尾迹。纯画布动画：不改 `route[]`/模型/固件；进度按"占全长比例"存（缩放/平移/旋转/拖节点都不跳位），速度按屏幕 px/s（`ANIM_BASE_PX_PER_SEC`=220）。入口在左栏「路线规划」面板（`▶ 小车动画` / `⏹` / 倍速滑条）。`_guismoke` 加 9 条断言 ⇒ **254 项 [OK] / 0 FAIL**。\r\n')

# ---------------------------------------------------------------- MEMORY.md
M = os.path.join(ROOT, ".workbuddy", "memory", "MEMORY.md")
rep(M,
    '- 改 `map_model.py` 后必跑 `_selftest.py`（含往返零差异）+ `_guismoke.py`（245 项，界面）；',
    '- 改 `map_model.py` 后必跑 `_selftest.py`（含往返零差异）+ `_guismoke.py`（254 项，界面）；')

# ---------------------------------------------------------------- 当日日志
D = os.path.join(ROOT, ".workbuddy", "memory", "2026-10-07.md")
app(D,
    '\n## 上位机加「小车动画」【仅上位机】\n'
    '\n'
    '- **用户要求**：现在的路线仿真是静态折线，想加一个"小车的移动动画"（选定：匀速 / 循环+可暂停停止 / 带朝向的小车）。\n'
    '- **改法**（全在 `map_editor.py`，纯绘制，**不改 `self.route`/模型/固件**）：\n'
    '  - 左栏「路线规划」面板加一行：`▶ 小车动画`（点击变 `⏸ 暂停`）/ `⏹` 停止 / `倍速` tk.Scale 0.2~4.0。\n'
    '  - 新增常量 `CAR_COLOR/CAR_OUTLINE/CAR_GLASS/CAR_WHEEL/CAR_TRAIL`、`ANIM_BASE_PX_PER_SEC=220`、\n'
    '    `ANIM_INTERVAL_MS=20`、`ANIM_TRAIL_PX=70`；模块函数 `_flat_pts()`。\n'
    '  - 新增方法：`_route_screen_polyline / _polyline_metrics / _point_at_frac / _polyline_slice / _car_sprite_pts`\n'
    '    （几何，静态方法，可无界面单测）+ `_anim_clear/_anim_draw/_anim_tick/anim_toggle/anim_resume/anim_pause/anim_stop/_set_anim_btn/_anim_speed_changed`。\n'
    '  - 关键设计：**进度存"占全长比例" `anim_frac`**（缩放/平移/旋转/拖节点都不跳位）；**速度按屏幕 px/s**（观感与缩放无关）；\n'
    '    `_anim_tick` 用 `anim_route_key` 快照比对 ⇒ **任何"设置 route"的地方都不用额外通知动画**（路线变了自动从起点重播）。\n'
    '  - 挂钩：`redraw()` 末尾调 `_anim_draw()`（缩放/平移/拖动时车跟着走）；`clear_route()` 与 `_on_close()` 里 `anim_stop()`\n'
    '    （前者防沿空路线报错，后者防关窗后 `after` 回调报 `TclError`）。图元统一 `tags="anim"`，按 id+标签双保险清理。\n'
    '- **验证**：`_guismoke.py` 加 9 条断言（→ **254 项 [OK] / 0 FAIL**）；另用 PIL 按同一套几何/配色把小车渲染成 PNG 复核造型\n'
    '  （发现并修掉"轮子被车身盖成小黑三角"）。`_selftest.py` 仍是**既有 2 项失败**（`config.h` 的 `MAP_DEBUG` 行尾空格、\n'
    '  `N16→N18` 路口左右写反），与本次无关（本次只动 `map_editor.py`，已用快照 diff 确认 +262 行、0 删除）。\n'
    '- **文档同步**：`map_editor/README.md`（§5 新增小节 + §8/§10 计数 245→254）、`AI_CONTEXT.md`（§6.15 新不变量 +\n'
    '  §9 索引行 + 计数）、`项目讲解文档/README.md` §9 一行、`.workbuddy/memory/MEMORY.md` 计数。行尾：map_editor/** LF、讲解文档 CRLF。\n'
    '- 备份：`git stash create` 快照见 `stash@{0}`（"AI-checkpoint 20261007 小车动画前"）；补丁脚本 `reports/_patch_docs_car_anim.py`。\n')


def main():
    touched = {}
    for path, mode, old, new in EDITS:
        with open(path, "rb") as f:
            data = f.read()
        if path not in touched:
            eol = b"\r\n" if data.count(b"\r\n") > 0 else b"\n"
            touched[path] = (data, eol)
    # 逐个替换，全部成功后统一写盘
    for path, mode, old, new in EDITS:
        data, eol = touched[path]
        if mode == "append":
            if eol == b"\r\n":
                payload = new.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
            else:
                payload = new.replace("\r\n", "\n").encode("utf-8")
            touched[path] = (data + payload, eol)
            print("[append] %s +%d bytes" % (os.path.basename(path), len(payload)))
        else:
            ob = old.replace("\r\n", "\n").encode("utf-8")
            if eol == b"\r\n":
                ob = old.encode("utf-8")
                nb = new.encode("utf-8")
            else:
                nb = new.replace("\r\n", "\n").encode("utf-8")
            cnt = data.count(ob)
            assert cnt == 1, "命中 %d 次（期望 1）：%s :: %r" % (
                cnt, os.path.basename(path), old[:60])
            touched[path] = (data.replace(ob, nb), eol)
            print("[replace] %s" % os.path.basename(path))
    for path, (data, eol) in touched.items():
        with open(path, "wb") as f:
            f.write(data)
    print("所有文档补丁已写盘。")


if __name__ == "__main__":
    main()
