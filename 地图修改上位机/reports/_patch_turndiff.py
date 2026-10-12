# -*- coding: utf-8 -*-
"""A 方案：在「查看代码差异」里加「转弯补偿差异」段（对比 model.turn 与 map.c）。
字节级替换，全部唯一命中才写盘。"""
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

# ---------- 1. map_model.py：加 turn_diff / turn_diff_lines ----------
MM_OLD = '''        if abs(float(x.get("dist", 0) or 0) - float(y.get("dist", 0) or 0)) > 1e-9:
            return False
    return True


def turn_table_status(model, rows, table, turn=None):
'''

MM_NEW = '''        if abs(float(x.get("dist", 0) or 0) - float(y.get("dist", 0) or 0)) > 1e-9:
            return False
    return True


def turn_diff(cur, src):
    """比较「当前模型的补偿」与「map.c 源码的补偿」（只读；给「查看代码差异」用）。

    cur / src 均为 {"stop": [...], "gyro": [...], "consts": {...}, "calc_enable": 0/1}。
    按 (last, now, next) 三元组配对 —— **不看行序**（生效值由三元组查表决定，与表里行序无关）。
    返回 dict:
      stop_add / stop_del          [(三元组, 值)]（新增 / 删除）
      stop_chg                     [(三元组, 源码值, 当前值)]
      gyro_add / gyro_del / gyro_chg   同上（表2）
      const_chg                    [(名字, 源码值, 当前值)]（TURN_* 公式参数）
      calc_chg                     None 或 (源码, 当前)（TURN_CALC_ENABLE 开关）
      same                         以上全空 ⇒ True
    """
    cur = cur or {}
    src = src or {}

    def index(rows):
        out = {}
        for r in rows or []:
            out[(r.get("last"), r.get("now"), r.get("next"))] = float(r.get("dist", 0) or 0)
        return out

    def cmp_one(cur_rows, src_rows):
        ci, si = index(cur_rows), index(src_rows)
        add = sorted((k, ci[k]) for k in ci if k not in si)
        dele = sorted((k, si[k]) for k in si if k not in ci)
        chg = sorted((k, si[k], ci[k]) for k in ci
                     if k in si and abs(ci[k] - si[k]) > 1e-9)
        return add, dele, chg

    s_add, s_del, s_chg = cmp_one(cur.get("stop"), src.get("stop"))
    g_add, g_del, g_chg = cmp_one(cur.get("gyro"), src.get("gyro"))

    sc = dict(src.get("consts") or {})
    cc = dict(cur.get("consts") or {})
    const_chg = []
    for name in sorted(TURN_CONST_DEFAULTS):
        sv, cv = sc.get(name), cc.get(name)
        if sv is None or cv is None:
            continue
        if abs(float(sv) - float(cv)) > 1e-9:
            const_chg.append((name, float(sv), float(cv)))

    sce, cce = src.get("calc_enable"), cur.get("calc_enable")
    calc_chg = None
    if sce is not None and cce is not None and int(sce) != int(cce):
        calc_chg = (int(sce), int(cce))

    same = not (s_add or s_del or s_chg or g_add or g_del or g_chg
                or const_chg or calc_chg)
    return {"stop_add": s_add, "stop_del": s_del, "stop_chg": s_chg,
            "gyro_add": g_add, "gyro_del": g_del, "gyro_chg": g_chg,
            "const_chg": const_chg, "calc_chg": calc_chg, "same": same}


def turn_diff_lines(td):
    """把 `turn_diff()` 的结果写成差异报告里的几行（纯字符串、无 Tk，便于自检）。"""
    if td.get("same"):
        return ["转弯补偿差异：无（表1/表2、公式参数、TURN_CALC_ENABLE 都与 map.c 一致）"]

    def tri(k):
        return "%s→%s→%s" % tuple(k)

    out = ["转弯补偿差异（左=map.c 源码值，右=当前模型值）："]
    for tag, label, add, dele, chg in (
            ("表1", "停车转", td["stop_add"], td["stop_del"], td["stop_chg"]),
            ("表2", "陀螺转", td["gyro_add"], td["gyro_del"], td["gyro_chg"])):
        for k, v in add:
            out.append("  + 新增 %s %s：%s = %g" % (tag, label, tri(k), v))
        for k, v in dele:
            out.append("  - 删除 %s %s：%s（源码 %g）" % (tag, label, tri(k), v))
        for k, sv, cv in chg:
            out.append("  ~ 改值 %s %s：%s  %g → %g" % (tag, label, tri(k), sv, cv))
    for name, sv, cv in td["const_chg"]:
        out.append("  ~ 公式参数 %s：%g → %g" % (name, sv, cv))
    if td["calc_chg"]:
        sv, cv = td["calc_chg"]
        out.append("  ~ 开关 TURN_CALC_ENABLE：%d → %d（%s）"
                   % (sv, cv, "启用「能算就算」公式" if cv else "关闭，回到原行为"))
    return out


def turn_table_status(model, rows, table, turn=None):
'''

# ---------- 2. map_editor.py：report_source_diff 加补偿段 ----------
ME_OLD = '''            source_rows, declared_count = M.parse_edge_table()
        except Exception as ex:
            messagebox.showerror("读取差异失败", "%s" % ex, parent=self)
            return

        added_nodes = [name for name in current_names if name not in source_names]'''

ME_NEW = '''            source_rows, declared_count = M.parse_edge_table()
        except Exception as ex:
            messagebox.showerror("读取差异失败", "%s" % ex, parent=self)
            return
        try:
            source_turn = M.parse_turn_tables()
        except Exception as ex:                                   # noqa: BLE001
            source_turn, turn_err = None, "%s" % ex

        added_nodes = [name for name in current_names if name not in source_names]'''

ME2_OLD = '''        if not added_nodes and not removed_nodes and not order_changed and not edge_problems \\
                and len(self.model.edges) == len(source_rows):
            lines.extend(["", "当前模型与源码内容一致。"])
'''
ME2_NEW = '''        lines.append("")
        if source_turn is None:
            lines.append("转弯补偿差异：无法读取 map.c / config.h（%s）" % turn_err)
            turn_same = False
        else:
            turn_td = M.turn_diff(getattr(self.model, "turn", None) or {}, source_turn)
            lines.extend(M.turn_diff_lines(turn_td))
            turn_same = turn_td["same"]
        if (not added_nodes and not removed_nodes and not order_changed and not edge_problems
                and len(self.model.edges) == len(source_rows) and turn_same):
            lines.extend(["", "当前模型与源码内容一致。"])
'''

ME3_OLD = '''        self.status("已生成代码差异报告：%d 项边表差异" % len(edge_problems))'''
ME3_NEW = '''        self.status("已生成代码差异报告：%d 项边表差异；转弯补偿%s"
                    % (len(edge_problems), "一致" if turn_same else "有差异"))'''

# ---------- 3. _guismoke.py：加 turn_diff 断言 ----------
GS_OLD = '''    check(E.M.turn_rows_equal(_src_t["stop"], _t["stop"])
          and E.M.turn_rows_equal(_src_t["gyro"], _t["gyro"]),
          "没编辑过 ⇒ 表项与源码逐项相同（所以「写回」会整段跳过，不产生格式 diff）")
'''
GS_NEW = GS_OLD + '''    # 「查看代码差异」里的「转弯补偿差异」用的纯函数 turn_diff / turn_diff_lines
    _d0 = E.M.turn_diff(app.model.turn, _src_t)
    check(_d0["same"] and not _d0["const_chg"] and _d0["calc_chg"] is None,
          "turn_diff：模型补偿与 map.c 一致 ⇒ same=True")
    _b0 = dict(_t["stop"][0])
    _bL = _t["consts"]["TURN_L_PIVOT"]
    _bC = _t["calc_enable"]
    try:
        _t["stop"][0]["dist"] = 999.0
        _t["consts"]["TURN_L_PIVOT"] = 21.0
        _t["calc_enable"] = 1
        _d1 = E.M.turn_diff(app.model.turn, _src_t)
        check(len(_d1["stop_chg"]) == 1 and abs(_d1["stop_chg"][0][2] - 999.0) < 1e-9,
              "turn_diff：改一行补偿值 ⇒ 报 1 条改值（%s）" % (_d1["stop_chg"],))
        check(any(n == "TURN_L_PIVOT" and abs(c - 21.0) < 1e-9
                  for n, _s, c in _d1["const_chg"]),
              "turn_diff：报公式参数变化（%s）" % (_d1["const_chg"],))
        check(_d1["calc_chg"] == (int(_src_t["calc_enable"] or 0), 1),
              "turn_diff：报 TURN_CALC_ENABLE 开关变化（%s）" % (_d1["calc_chg"],))
        check(any("转弯补偿差异" in s for s in E.M.turn_diff_lines(_d1)),
              "turn_diff_lines：差异报告里出「转弯补偿差异」段")
    finally:
        _t["stop"][0] = _b0
        _t["consts"]["TURN_L_PIVOT"] = _bL
        _t["calc_enable"] = _bC
'''

edits = [(MM, MM_OLD, MM_NEW), (ME, ME_OLD, ME_NEW), (ME, ME2_OLD, ME2_NEW),
         (ME, ME3_OLD, ME3_NEW), (GS, GS_OLD, GS_NEW)]

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
