# -*- coding: utf-8 -*-
"""微调：提示行加 wraplength（别被裁）+ 缩短文案；「值cm」列加宽（表头别换行）。"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

def load(p):
    return open(p, "rb").read().decode("utf-8")

def save(p, s):
    open(p, "wb").write(s.encode("utf-8"))

ME = "地图修改上位机/map_editor/map_editor.py"

E1_OLD = '''        self.lbl_turn_hint = ttk.Label(top, foreground="#666666", text="")
        self.lbl_turn_hint.pack(anchor="w", padx=4)
'''
E1_NEW = '''        self.lbl_turn_hint = ttk.Label(top, foreground="#666666", wraplength=372, text="")
        self.lbl_turn_hint.pack(anchor="w", padx=4)
'''

E2_OLD = '''        self.tree_turn.column("#0", width=132)
        self.tree_turn.column("ang", width=46, anchor="e", stretch=False)
        self.tree_turn.column("br", width=34, anchor="center", stretch=False)
        self.tree_turn.column("val", width=46, anchor="e", stretch=False)
        self.tree_turn.column("src", width=58, anchor="w", stretch=False)
'''
E2_NEW = '''        self.tree_turn.column("#0", width=126)
        self.tree_turn.column("ang", width=46, anchor="e", stretch=False)
        self.tree_turn.column("br", width=34, anchor="center", stretch=False)
        self.tree_turn.column("val", width=54, anchor="e", stretch=False)
        self.tree_turn.column("src", width=58, anchor="w", stretch=False)
'''

E3_OLD = '''            self.lbl_turn_hint.configure(
                text="%d 行（共 %d 个转弯组合）· 点一行 = 画布高亮 / 双击 = 打开补偿编辑器"
                     % (len(rows), cov["stats"]["total"]))
'''
E3_NEW = '''            self.lbl_turn_hint.configure(
                text="%d/%d 行（点一行 = 高亮，双击 = 编辑）"
                     % (len(rows), cov["stats"]["total"]))
'''

edits = [(ME, E1_OLD, E1_NEW), (ME, E2_OLD, E2_NEW), (ME, E3_OLD, E3_NEW)]
plan = []
for p, old, new in edits:
    n = load(p).count(old)
    plan.append((p, old, new, n))
    print("[check] count=%d %s | %s" % (n, "OK" if n == 1 else "!!",
                                        old.strip().splitlines()[0][:46]))
if any(x[3] != 1 for x in plan):
    print("未唯一命中，未写盘。"); sys.exit(1)
buf = {}
for p, old, new, n in plan:
    buf[p] = buf.get(p, load(p)).replace(old, new, 1)
for p, s in buf.items():
    save(p, s); print("[write]", p)
print("DONE")
