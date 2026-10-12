# -*- coding: utf-8 -*-
"""AI 过程脚本：同步「加回 UPRIGHT_NEED_TREASURE」的文档。

- 项目讲解文档/README.md                → CRLF（§2.14 补一条护栏 + §9 追加一行）
- .workbuddy/memory/MEMORY.md           → LF（更正"开关已不存在"的说法）
- .workbuddy/memory/2026-10-07.md       → LF（追加当日日志）
每个替换 assert 命中恰好 1 次，全部成功才写盘。
"""
import os

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"


def apply(path, edits, eol):
    """edits: [(old, new)] ；old 用 \\n 写，写盘前统一转成该文件 eol。"""
    with open(path, "rb") as f:
        data = f.read()
    for old, new in edits:
        ob = old.replace("\n", eol).encode("utf-8")
        nb = new.replace("\n", eol).encode("utf-8")
        cnt = data.count(ob)
        assert cnt == 1, "%s 命中 %d 次（期望 1）:\n%r" % (path, cnt, old[:70])
        data = data.replace(ob, nb)
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    with open(path, "wb") as f:
        f.write(data)
    print("[ok] %s crlf=%d lf=%d" % (os.path.basename(path), crlf, lf))


P = os.path.join(ROOT, "项目讲解文档", "README.md")
M = os.path.join(ROOT, ".workbuddy", "memory", "MEMORY.md")
D = os.path.join(ROOT, ".workbuddy", "memory", "2026-10-07.md")

# ---------------- 项目讲解文档 §2.14 + §9（CRLF） ----------------
S214_OLD = (
    "会被提前放行。\n"
    "\n"
    "15. **MaixCam"
)
S214_NEW = (
    "会被提前放行。\n"
    "    - ⚠️ **别把本开关删成\"写死\"**：09-30 的 `09307f5` 曾把 `UPRIGHT_NEED_TREASURE` 从 `config.h` 删掉、\n"
    "      只留 `if (!treasure_taken)`，而本节仍写着\"开关在 config.h\" ⇒ **代码与文档对不上**（10-07 已恢复）。\n"
    "      自查一行：`grep -n UPRIGHT_NEED_TREASURE Mission/config.h Mission/barrier.c` —— 必须**各有一处**\n"
    "      （`config.h` 是定义、`barrier.c` 是判断）；只在 `barrier.c` 出现 = 又被删成写死了。\n"
    "\n"
    "15. **MaixCam"
)

S9_NEW = (
    "- **2026-10-07**：把 `UPRIGHT_NEED_TREASURE` 开关**加回**【动固件】—— 09-30 的 `09307f5` 曾把它从 "
    "`config.h` 删掉、把\"取宝后才做直立景点动作\"的门控写死成 `barrier.c:do_Upright()` 开头的 `if (!treasure_taken)`"
    "（当时没同步 §2.14 ⇒ 代码与文档对不上）。现在 `config.h` 恢复 `#define UPRIGHT_NEED_TREASURE  1`、"
    "`barrier.c` 改回 `if (UPRIGHT_NEED_TREASURE && !treasure_taken)`（**运行期常量判断**，不用 `#if`）；"
    "默认 `1` 与删前行为**逐字等价**，改 `0` 即恢复\"边表 `func=View` 就做\"的旧行为。"
    "EIDE 无头编译 **0 error / 0 warning**（`compiled` 里确认重编了 `Mission/barrier.c`）；"
    "`validate/` 6 个脚本改动前后输出**完全一致**（4 个 exit=1 是既有的边表/权重问题）。\n"
)

apply(P, [(S214_OLD, S214_NEW)], "\r\n")
# §9 追加在文件末尾
with open(P, "rb") as f:
    _d = f.read()
assert _d.endswith(b"\r\n"), "讲解文档末尾不是 CRLF"
with open(P, "wb") as f:
    f.write(_d + S9_NEW.replace("\n", "\r\n").encode("utf-8"))
print("[ok] README.md §9 追加一行")

# ---------------- MEMORY.md（LF） ----------------
M_OLD = (
    "- ⚠️ **`UPRIGHT_NEED_TREASURE` 这个开关已经不存在了**（09-30 提交 `09307f5` 从 `config.h` 删掉）：\n"
    "  \"取宝后才做直立景点动作\"的门控被**写死**成 `barrier.c:do_Upright()` 开头的\n"
    "  `if (!treasure_taken) { printf(\"[UPRIGHT] skipped…\"); return; }`（`treasure_taken` 由\n"
    "  `Stage_CollectTreasure()` 置位）⇒ **不可再配**。讲解文档 §2.14 / PR §5.1 / 交接文档里\n"
    "  \"开关在 config.h（当前 1）\"的说法**已过时**。\n"
)
M_NEW = (
    "- `UPRIGHT_NEED_TREASURE=1`（**10-07 加回**）：直立景点（`View`，N14/N16）**取宝门控**。判据是\n"
    "  `barrier.c` 的 `treasure_taken`（`Stage_CollectTreasure()` 置位），**不是 `treasure`**；落点 =\n"
    "  `barrier.c:do_Upright()` 开头的 `if (UPRIGHT_NEED_TREASURE && !treasure_taken) { …return; }`。\n"
    "  必须写成**运行期常量判断**（别用 `#if`：宏名写错 / 头文件没包含会静默当 0，护栏白写）。README §2.14。\n"
    "  ⚠️ 09-30 的 `09307f5` 曾删掉本开关、只留 `if (!treasure_taken)`（当时文档没跟着改）；10-07 已恢复。\n"
)
apply(M, [(M_OLD, M_NEW)], "\n")

# ---------------- 当日日志（LF，追加） ----------------
LOG = (
    "\n## 把 `UPRIGHT_NEED_TREASURE` 开关加回【动固件：config.h + barrier.c】\n"
    "\n"
    "- **用户要求**：上一个问题结论说该开关\"已被删、不可配\"，用户要求加回。\n"
    "- **改法**（字节级替换，eol 各自保持）：\n"
    "  - `Mission/config.h`（**LF+BOM**）→ 在 `UPRIGHT_TOUR_ENABLE` 块前恢复被 `09307f5` 删掉的\n"
    "    `UPRIGHT_NEED_TREASURE` 块，值 `1`。\n"
    "  - `Mission/barrier.c`（**CRLF**）→ `if (!treasure_taken)` ⇒ `if (UPRIGHT_NEED_TREASURE && !treasure_taken)`，\n"
    "    并恢复被删的说明注释（判据是 `treasure_taken` 不是 `treasure!=0`；只 return；**别用 `#if`**）。\n"
    "  - 语义：默认 `1` 与删前（写死版）**逐字等价**；改 `0` 恢复\"边表 `func=View` 就做\"的旧行为。\n"
    "- **验证**：EIDE 无头编译 `ok=true / 0 error / 0 warning`，`compiled` 里确认重编了 `Mission/barrier.c`；\n"
    "  `validate/` 6 个脚本与改动前**逐字一致**（`_check_csr/_check_wp/_check_wp_east/_weight_calib` 的 exit=1\n"
    "  是既有问题——用 `stash@{0}` 换回旧文件跑同一批脚本对比过，输出完全相同，跑完已字节级还原）。\n"
    "  `_selftest.py` 现在只剩 **1** 项既有失败（`N16→N18` 路口左右写反）。\n"
    "- **⚠️ 并发编辑提醒**：期间用户自己也在改固件（`Task/ArriveDetect_task.c` 19:40、`Navigation/map*.{c,h}` 19:40、\n"
    "  `Navigation/map.c` 19:55:42）。`config.h` 里另有**两处不是本次改动**的内容：`MAP_DEBUG` 那行的**行尾空格被去掉**\n"
    "  （顺带消掉了 `_selftest` 的老失败）与 `DOOR_RETREAT_N5N8 63 → 60`——都是用户的编辑，**未动、未丢**。\n"
    "- 补丁脚本：`reports/_patch_upright_need_treasure.py`；校验基线脚本：`reports/_verify_validate_baseline.py`。\n"
    "- 快照：`stash@{0}` = \"AI-checkpoint 20261007 加回 UPRIGHT_NEED_TREASURE 前\"。\n"
)
with open(D, "rb") as f:
    _d = f.read()
with open(D, "wb") as f:
    f.write(_d + LOG.encode("utf-8"))
print("[ok] 2026-10-07.md 追加日志")
