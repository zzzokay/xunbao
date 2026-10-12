# -*- coding: utf-8 -*-
"""一次性补丁：把「转弯补偿随布局保存」写进对话框提示 + 三份文档。字节级替换，全成功才写盘。
用系统 Python 或托管 Python 均可；不依赖 shell 传参，避免反引号被 bash 吃掉。"""
import io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

def load(p):
    return open(p, "rb").read().decode("utf-8")

def save(p, s):
    open(p, "wb").write(s.encode("utf-8"))

E = [("C:/Users/14166/Desktop/MC_32/robotcup/xunbao", None)]

# ---------------- A. map_editor.py 对话框常驻提示 ----------------
A_P = "地图修改上位机/map_editor/map_editor.py"
A_OLD = (
'        head = ttk.Label(outer, text="", justify="left", foreground="#0d47a1")\n'
'        head.pack(anchor="w", pady=(0, 6))\n')
A_NEW = A_OLD + (
'        ttk.Label(outer, justify="left", foreground="#6d4c41", wraplength=1020, text=(\n'
'            "本页两张补偿表 + 公式参数会随「保存布局 / 布局另存为」一起写进布局 JSON，"\n'
'            "下次「载入布局」自动恢复（与节点位置、边表同等对待，无需单独存）。\\n"\n'
'            "⚠️ 点「重新载入源码」会把补偿重置回 map.c 当前值（只保住节点位置/底图）；"\n'
'            "要落到固件请点右下角「写回 map.c…」。")).pack(anchor="w", pady=(0, 6))\n')

# ---------------- B. map_editor/README.md ----------------
B_P = "地图修改上位机/map_editor/README.md"
B1_OLD = "**布局文件里存了**：所有节点坐标 + 边表 + 底图路径与标定 + 拖动约束设置。"
B1_NEW = ("**布局文件里存了**：所有节点坐标 + 边表 + 底图路径与标定 + 拖动约束设置 "
          "+ **转弯补偿表**（`map.c` 两张表 + 公式参数，见 §5）。")

B3_OLD = "- 「重新载入源码」（同步固件里新改的边表）**不会丢你拖好的位置**（按节点名搬过去）。"
B3_NEW = ("- 「重新载入源码」（同步固件里新改的边表）**不会丢你拖好的位置**（按节点名搬过去）；\n"
          "  ⚠️ 但**转弯补偿**不在保护之列 —— 它会被重置回 `map.c` 的当前值（见 §5）。")

B2_OLD = "- 对话框不会自动写盘；关掉窗口只是取消高亮。\n\n> ⚠️ **分支判定是"
B2_NEW = (
'- 对话框不会自动写盘；关掉窗口只是取消高亮。\n\n'
'> 💾 **补偿随布局保存**：这两张表 + 公式参数 + `TURN_CALC_ENABLE` 会**随「保存布局 / 布局另存为」\n'
'> 一起写进布局 JSON**，「载入布局」自动恢复 —— 与节点位置、边表同等对待，**不用单独存**。\n'
'> ⚠️ 但**点「重新载入源码」会把补偿重置回 `map.c` 的当前值**（该操作只保住节点位置/底图，不保补偿）；\n'
'> 要落到固件仍须点「写回 map.c…」。\n\n'
'> ⚠️ **分支判定是')

# ---------------- C. 地图修改上位机/README.md ----------------
C_P = "地图修改上位机/README.md"
C_OLD = ("- `Navigation/map.c` — **转弯前补偿**两张表（`kTurnTbl[]` / `GetForwardDistanceBeforeGyroTurn`）\n"
         "  + 公式参数 `TURN_L_PIVOT` / `TURN_GATE_CM` / `TURN_D_*`。入口：编辑器左栏\n"
         "  「⟲ 转弯补偿…」（原理见 `项目讲解文档/project_reference.md` §14）")
C_NEW = C_OLD + ("\n  ⚠️ 这两张表 + 公式参数**随「保存布局 / 另存为」存进布局 JSON**；"
                 "点「重新载入源码」会重置回上面的源码值。")

# ---------------- E. project_reference.md §14.8 ----------------
E_P = "项目讲解文档/project_reference.md"
E_OLD = "编辑器侧的坑与不变量写在 `地图修改上位机/map_editor/AI_CONTEXT.md` §6.14 / §7.10 / §10.7。"
E_NEW = (E_OLD + "\r\n"
'- 💾 **随布局保存 / 另存（2026-10-07 明确）**：这两张表 + 公式参数 + `TURN_CALC_ENABLE` 会**随「保存布局 / 布局另存为」\r\n'
'  一起写进布局 JSON** 的 `turn` 段，「载入布局」自动恢复 —— 与节点位置、边表同等对待，**不用单独存**。\r\n'
'  ⚠️ 但**点「重新载入源码」会把补偿重置回 `map.c` 当前值**（该操作只保住节点位置/底图）；要落固件仍须点「写回 map.c…」。')

# ---------------- D. 项目讲解文档/README.md §9 追加一行（CRLF） ----------------
D_P = "项目讲解文档/README.md"
D_LINE = ("- **2026-10-07**：上位机「转弯补偿」持久化（文档 + 对话框提示）【仅上位机】—— 澄清并写进文档："
          "转弯补偿（`map.c` 两张表 + 公式参数 + `TURN_CALC_ENABLE`）**本就随「保存布局 / 布局另存为」"
          "写进布局 JSON**（`to_json`/`load_json` 的 `turn` 段，与节点、边表同等对待；已实测往返一致），"
          "**不用单独存/另存**。在「⟲ 转弯补偿…」对话框顶部加常驻提示，并把一个坑写进文档："
          "**「重新载入源码」只保住节点位置/底图，会把补偿重置回 `map.c` 当前值**（PR §14.8）。")

edits = [(A_P, A_OLD, A_NEW, 1), (B_P, B1_OLD, B1_NEW, 1), (B_P, B2_OLD, B2_NEW, 1),
         (B_P, B3_OLD, B3_NEW, 1),
         (C_P, C_OLD, C_NEW, 1), (E_P, E_OLD, E_NEW, 1)]

plan = []
for p, old, new, exp in edits:
    s = load(p)
    n = s.count(old)
    plan.append((p, old, new, n, exp))
    print("[check] %-44s count=%d (expect %d) %s" % (p, n, exp, "OK" if n == exp else "!!"))

bad = [x for x in plan if x[3] != x[4]]
if bad:
    print("\n有串未唯一命中，未写盘。")
    sys.exit(1)

# 全部通过 -> 写盘
buf = {}
for p, old, new, n, exp in plan:
    buf[p] = buf.get(p, load(p)).replace(old, new, 1)
for p, s in buf.items():
    save(p, s)
    print("[write] %s" % p)

# D：追加
s = load(D_P)
if D_LINE[:40] in s:
    print("[skip] 日志行已存在")
else:
    sep = "\r\n" if s.count("\r\n") and not s.endswith("\n") else "\r\n"
    s2 = s + "\r\n" + D_LINE
    save(D_P, s2)
    print("[write] %s (+1 log line)" % D_P)

# D 的 §9 行说明已包含；顺带广播
print("\nDONE")
