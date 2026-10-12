# -*- coding: utf-8 -*-
"""AI 过程脚本：MEMORY.md 行尾从 CRLF 还原成 LF + 更正开关注记；并追加当日日志。"""
import os

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"
M = os.path.join(ROOT, ".workbuddy", "memory", "MEMORY.md")
D = os.path.join(ROOT, ".workbuddy", "memory", "2026-10-07.md")

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

LOG = (
    "\n## 把 `UPRIGHT_NEED_TREASURE` 开关加回【动固件：config.h + barrier.c】\n"
    "\n"
    "- **用户要求**：上一问结论说该开关\"已被删、不可配\"，用户要求加回。\n"
    "- **改法**（字节级替换，eol 各自保持）：\n"
    "  - `Mission/config.h`（**LF+BOM**）→ 在 `UPRIGHT_TOUR_ENABLE` 块前恢复被 `09307f5` 删掉的\n"
    "    `UPRIGHT_NEED_TREASURE` 块，值 `1`。\n"
    "  - `Mission/barrier.c`（**CRLF**）→ `if (!treasure_taken)` ⇒ `if (UPRIGHT_NEED_TREASURE && !treasure_taken)`，\n"
    "    并恢复被删的说明注释（判据是 `treasure_taken` 不是 `treasure!=0`；只 return；**别用 `#if`**）。\n"
    "  - 语义：默认 `1` 与删前的写死版**逐字等价**；改 `0` = 恢复\"边表 `func=View` 就做\"的旧行为。\n"
    "- **验证**：EIDE 无头编译 `ok=true / 0 error / 0 warning`，`compiled` 里确认重编了 `Mission/barrier.c`；\n"
    "  `validate/` 6 个脚本与改动前**逐字一致**（`_check_csr/_check_wp/_check_wp_east/_weight_calib` 的 exit=1\n"
    "  是**既有**问题 —— 用 `stash@{0}` 临时换回旧文件跑同一批脚本对比，输出完全相同，跑完已字节级还原）。\n"
    "  `_selftest.py` 现在只剩 **1** 项既有失败（`N16→N18` 路口左右写反）。\n"
    "- **⚠️ 并发编辑**：期间用户自己也在改固件（`Task/ArriveDetect_task.c` 19:40、`Navigation/map*.{c,h}` 19:40、\n"
    "  `Navigation/map.c` 19:55:42）。`config.h` 里另有**两处不是本次改动**：`MAP_DEBUG` 行尾空格被去掉\n"
    "  （顺带消掉了 `_selftest` 的老失败）、`DOOR_RETREAT_N5N8 63 → 60` —— 都是用户的编辑，**未动、未丢**。\n"
    "- **⚠️ 新发现的行尾坑**：`.workbuddy/memory/MEMORY.md` 被**改成 CRLF**（HEAD 与本次开工时都是 LF）；\n"
    "  已用字节级脚本改回 **LF**。⇒ 用非字节级工具改 memory 下的 .md 时，**要复查行尾**。\n"
    "- 补丁脚本：`reports/_patch_upright_need_treasure.py`、`reports/_patch_docs_upright_need_treasure.py`、\n"
    "  `reports/_finish_memory_and_log.py`；校验基线脚本：`reports/_verify_validate_baseline.py`。\n"
    "- 快照：`stash@{0}` = \"AI-checkpoint 20261007 加回 UPRIGHT_NEED_TREASURE 前\"。\n"
)


def main():
    with open(M, "rb") as f:
        raw = f.read()
    crlf0 = raw.count(b"\r\n")
    text = raw.replace(b"\r\n", b"\n")            # 统一回 LF
    ob = M_OLD.encode("utf-8")
    nb = M_NEW.encode("utf-8")
    assert text.count(ob) == 1, "MEMORY.md 命中 %d 次" % text.count(ob)
    text = text.replace(ob, nb)
    with open(M, "wb") as f:
        f.write(text)
    print("[ok] MEMORY.md: crlf %d -> %d, lf=%d" % (crlf0, text.count(b"\r\n"),
                                                    text.count(b"\n")))

    with open(D, "rb") as f:
        d = f.read()
    assert d.count(b"\r\n") == 0, "当日日志不是 LF"
    with open(D, "wb") as f:
        f.write(d + LOG.encode("utf-8"))
    print("[ok] 2026-10-07.md 追加日志（%d -> %d bytes）" % (len(d), len(d) + len(LOG)))


if __name__ == "__main__":
    main()
