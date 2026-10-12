# -*- coding: utf-8 -*-
"""AI 过程脚本：把「行尾漂移」这条坑记进日志与长期笔记。"""
import os

ROOT = r"C:\Users\14166\Desktop\MC_32\robotcup\xunbao"
M = os.path.join(ROOT, ".workbuddy", "memory", "MEMORY.md")
D = os.path.join(ROOT, ".workbuddy", "memory", "2026-10-07.md")

LOG = (
    "- **追加发现（行尾漂移，值得记）**：同一时段 `地图修改上位机/map_editor/README.md` 与 `AI_CONTEXT.md`\n"
    "  也被**改成 CRLF**（mtime 19:51:41 / 19:51:45，恰在用户发消息前几秒 ⇒ 外部编辑器重写，非本次改动）。\n"
    "  按约定（`地图修改上位机/**/*.md` = LF）已用**字节级** `CRLF->LF` 改回，内容未变（只去 `\\r`）。\n"
    "  ⇒ 结论：**每轮收尾都要回读行尾**，非字节级工具（编辑器保存 / Edit 类工具 / 宿主）会**静默**改 eol，\n"
    "  而 `git diff` 被 `core.autocrlf=true` 藏住，看不见。\n"
)

M_OLD = (
    "- ⚠️ **判断行尾别用 `grep -c $'\\r$'`**（本机对 LF 文件误报成全 CRLF），`git diff` 也被 `core.autocrlf=true` 藏差异。\n"
    "  直接数：`d=open(p,'rb').read(); crlf=d.count(b'\\r\\n'); lf=d.count(b'\\n')-crlf`。\n"
)
M_NEW = (
    "- ⚠️ **判断行尾别用 `grep -c $'\\r$'`**（本机对 LF 文件误报成全 CRLF），`git diff` 也被 `core.autocrlf=true` 藏差异。\n"
    "  直接数：`d=open(p,'rb').read(); crlf=d.count(b'\\r\\n'); lf=d.count(b'\\n')-crlf`。\n"
    "- ⚠️ **每轮收尾都要回读行尾**：非字节级工具（**编辑器保存**、Edit 类工具、宿主）会把 LF **静默**变 CRLF ——\n"
    "  本会话 `地图修改上位机/map_editor/README.md`、`AI_CONTEXT.md`（约定 LF）与 `.workbuddy/memory/MEMORY.md`\n"
    "  都中过（后两者已字节级改回）。**只有字节级替换（read_bytes→replace→write_bytes）才可控。**\n"
)


def main():
    with open(D, "rb") as f:
        d = f.read()
    with open(D, "wb") as f:
        f.write(d + LOG.encode("utf-8"))
    print("[ok] 日志追加 %d bytes" % len(LOG.encode("utf-8")))

    with open(M, "rb") as f:
        raw = f.read()
    assert raw.count(b"\r\n") == 0, "MEMORY.md 又变 CRLF 了"
    ob, nb = M_OLD.encode("utf-8"), M_NEW.encode("utf-8")
    assert raw.count(ob) == 1, "MEMORY.md 命中 %d 次" % raw.count(ob)
    with open(M, "wb") as f:
        f.write(raw.replace(ob, nb))
    print("[ok] MEMORY.md 补一条行尾护栏")


if __name__ == "__main__":
    main()
