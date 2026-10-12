# -*- coding: utf-8 -*-
"""2026-10-07 README（项目讲解文档，CRLF）补丁：§2.22 补修说明 + §9 追加日志。"""
import sys

P = r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao/项目讲解文档/README.md"
b = open(P, "rb").read()
crlf = b.count(b"\r\n"); lf = b.count(b"\n") - crlf
assert crlf and not lf, "unexpected eol: crlf=%d lf=%d" % (crlf, lf)
E = "\r\n"
t = b.decode("utf-8")

# ---- §2.22 末尾补一条 ----
anchor22 = (
    "      （含「写回只动沙箱副本 / 真实 `config.h` SHA256 不变」）。" + E +
    E +
    "## 3. 地图修改上位机（`地图修改上位机/`）"
)
assert t.count(anchor22) == 1, "anchor22 hits %d" % t.count(anchor22)
add22 = (
    "      （含「写回只动沙箱副本 / 真实 `config.h` SHA256 不变」）。" + E +
    "    - **2026-10-07 补修**：「线索路线…」的「第二轮·完整路线」分支此前把 `cfg` 传 `None` ⇒ 显示的巡游" + E +
    "      顺序**永远是出厂默认**、不跟 `config.h` 走（车上真走配置的顺序，纯上位机显示错）；已改为现场" + E +
    "      `parse_round2_cruise()`，段落标题带出实际顺序（「巡游 P5→…」）。⚠️ `_guismoke` 的二轮断言已改成" + E +
    "      从 `config.h` 现值推导，写回自定义顺序后测试仍成立。" + E +
    E +
    "## 3. 地图修改上位机（`地图修改上位机/`）"
)
t = t.replace(anchor22, add22)

# ---- §9 追加一行 ----
assert t.endswith(E), "file must end with CRLF"
add9 = (
    "- 2026-10-07（晚）：修「线索路线…→第二轮·完整路线」不吃 config.h 二轮顺序的显示 bug"
    "（`_clue_route_sections` 二轮分支把 `cfg` 传 `None` 落回出厂默认；改现场 `parse_round2_cruise()`、"
    "标题带出实际顺序，`_guismoke` 二轮断言改从 config.h 现值推导）；顺带把被 22:03 写回覆盖回默认的"
    "自定义巡游顺序（CW P5→P8→P7→P6 / CCW P6→P7→P8→P5）用 `splice_round2_cruise` 恢复进 config.h"
    "（先备份）。`_selftest` 全过、`_guismoke` 全过、`sim_route_bookkeeping` 源同步自检过。"
)
t = t + add9 + E

open(P, "wb").write(t.encode("utf-8"))
print("OK: §2.22 补修说明 + §9 日志已追加")
