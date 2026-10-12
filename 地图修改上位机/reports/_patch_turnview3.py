# -*- coding: utf-8 -*-
"""左栏「转弯补偿」显示档加「只看实测停车转」（仅表1 实测）。字节级替换，全唯一命中才写盘。"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

def load(p):
    return open(p, "rb").read().decode("utf-8")

def save(p, s):
    open(p, "wb").write(s.encode("utf-8"))

MM = "地图修改上位机/map_editor/map_model.py"
ME = "地图修改上位机/map_editor/map_editor.py"
GS = "地图修改上位机/map_editor/_guismoke.py"

# 1. 档位列表 + 新档过滤
MM1_OLD = '''TURN_LIST_MODES = ("只看要补偿的", "只看实测", "只看吃默认", "只看停车转", "只看陀螺转", "全部")
'''
MM1_NEW = '''TURN_LIST_MODES = ("只看要补偿的", "只看实测", "只看实测停车转", "只看吃默认",
                   "只看停车转", "只看陀螺转", "全部")
'''

MM2_OLD = '''    if mode == "只看实测":
        return [r for r in rows if r["source"] in ("表1 实测", "表2 实测")]
'''
MM2_NEW = '''    if mode == "只看实测":
        return [r for r in rows if r["source"] in ("表1 实测", "表2 实测")]
    if mode == "只看实测停车转":
        return [r for r in rows if r["source"] == "表1 实测"]      # 仅表1 kTurnTbl（停车转）
'''

# 2. 下拉加宽（多了 7 个字的档名）
ME1_OLD = '''        tvc = ttk.Combobox(trow, textvariable=self.turn_view, width=14,
'''
ME1_NEW = '''        tvc = ttk.Combobox(trow, textvariable=self.turn_view, width=17,
'''

# 3. 冒烟：新档断言
GS_OLD = '''    app.turn_view.set("只看实测")
    app._fill_turn_list()
    _exp2 = len(E.M.turn_filter(_cov["rows"], "只看实测"))
    check(len(app.tree_turn.get_children()) == _exp2,
          "「只看实测」= %d 行（表1/表2 命中）" % _exp2)
'''
GS_NEW = '''    app.turn_view.set("只看实测")
    app._fill_turn_list()
    _exp2 = len(E.M.turn_filter(_cov["rows"], "只看实测"))
    check(len(app.tree_turn.get_children()) == _exp2,
          "「只看实测」= %d 行（表1/表2 命中）" % _exp2)
    app.turn_view.set("只看实测停车转")
    app._fill_turn_list()
    _exp3 = len(E.M.turn_filter(_cov["rows"], "只看实测停车转"))
    check(len(app.tree_turn.get_children()) == _exp3 and 0 < _exp3 <= _exp2,
          "「只看实测停车转」= %d 行（仅表1 停车转实测，<= 实测 %d）" % (_exp3, _exp2))
'''

edits = [(MM, MM1_OLD, MM1_NEW), (MM, MM2_OLD, MM2_NEW), (ME, ME1_OLD, ME1_NEW),
         (GS, GS_OLD, GS_NEW)]
plan = []
for p, old, new in edits:
    n = load(p).count(old)
    plan.append((p, old, new, n))
    print("[check] %-16s count=%d %s | %s" % (p.split("/")[-1], n,
          "OK" if n == 1 else "!!", old.strip().splitlines()[0][:44]))
if any(x[3] != 1 for x in plan):
    print("\n有串未唯一命中，未写盘。"); sys.exit(1)
buf = {}
for p, old, new, n in plan:
    buf[p] = buf.get(p, load(p)).replace(old, new, 1)
for p, s in buf.items():
    save(p, s); print("[write]", p)
print("DONE")
