# -*- coding: utf-8 -*-
"""「查看代码差异」加「宏定义差异」段（对比 model.macros 与 config.h）。字节级替换，全唯一命中才写盘。"""
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

# ---------- 1. map_model.py：macros_diff / macros_diff_lines ----------
MM_OLD = '''    return defines, field_name


def write_use_field(new_field, path=PATH_CONFIG):
'''
MM_NEW = '''    return defines, field_name


def _norm_macro(v):
    """宏值比较用：压掉多余空白（宏是**文本**，不解释成数字）。"""
    return " ".join(str(v).split())


def macros_diff(cur, src):
    """比较「当前模型的宏」与「config.h 源码的宏」（只读；给「查看代码差异」用）。

    cur / src 均为 {名字: 值文本}（如 {"LEN_B5N19": "150"}）。值按**去空白后的文本**比，
    不拆成数字 —— 因为宏可以是表达式（`(LEN_N22B7 - 20)`）、带后缀（`1.2f`）、甚至是别的宏名。
    返回 dict: add [(名, 当前值)] / dele [(名, 源码值)] / chg [(名, 源码值, 当前值)] / same
    """
    cur = {k: _norm_macro(v) for k, v in (cur or {}).items()}
    src = {k: _norm_macro(v) for k, v in (src or {}).items()}
    add = sorted((k, cur[k]) for k in cur if k not in src)
    dele = sorted((k, src[k]) for k in src if k not in cur)
    chg = sorted((k, src[k], cur[k]) for k in cur if k in src and cur[k] != src[k])
    return {"add": add, "dele": dele, "chg": chg, "same": not (add or dele or chg)}


def macros_diff_lines(td):
    """把 `macros_diff()` 的结果写成差异报告里的几行（纯字符串、无 Tk，便于自检）。"""
    if td.get("same"):
        return ["宏定义差异：无（config.h 里的宏与当前模型一致）"]
    out = ["宏定义差异（config.h，左=源码值，右=当前模型值）："]
    for k, v in td["add"]:
        out.append("  + 新增 %s = %s" % (k, v))
    for k, v in td["dele"]:
        out.append("  - 删除 %s（源码 %s）" % (k, v))
    for k, sv, cv in td["chg"]:
        out.append("  ~ 改值 %s：%s → %s" % (k, sv, cv))
    return out


def write_use_field(new_field, path=PATH_CONFIG):
'''

# ---------- 2. map_editor.py：report_source_diff 加宏段 ----------
ME1_OLD = '''        try:
            source_turn = M.parse_turn_tables()
        except Exception as ex:                                   # noqa: BLE001
            source_turn, turn_err = None, "%s" % ex

        added_nodes = [name for name in current_names if name not in source_names]
'''
ME1_NEW = '''        try:
            source_turn = M.parse_turn_tables()
        except Exception as ex:                                   # noqa: BLE001
            source_turn, turn_err = None, "%s" % ex
        try:
            src_macros, _src_field = M.parse_config_macros()
        except Exception as ex:                                   # noqa: BLE001
            src_macros, macro_err = None, "%s" % ex

        added_nodes = [name for name in current_names if name not in source_names]
'''

ME2_OLD = '''            turn_same = turn_td["same"]
        if (not added_nodes and not removed_nodes and not order_changed and not edge_problems
                and len(self.model.edges) == len(source_rows) and turn_same):
            lines.extend(["", "当前模型与源码内容一致。"])
'''
ME2_NEW = '''            turn_same = turn_td["same"]
        lines.append("")
        if src_macros is None:
            lines.append("宏定义差异：无法读取 config.h（%s）" % macro_err)
            macro_same = False
        else:
            macro_td = M.macros_diff(getattr(self.model, "macros", None) or {}, src_macros)
            lines.extend(M.macros_diff_lines(macro_td))
            macro_same = macro_td["same"]
        if (not added_nodes and not removed_nodes and not order_changed and not edge_problems
                and len(self.model.edges) == len(source_rows) and turn_same and macro_same):
            lines.extend(["", "当前模型与源码内容一致。"])
'''

ME3_OLD = '''        self.status("已生成代码差异报告：%d 项边表差异；转弯补偿%s"
                    % (len(edge_problems), "一致" if turn_same else "有差异"))
'''
ME3_NEW = '''        self.status("已生成代码差异报告：%d 项边表差异；转弯补偿%s；宏定义%s"
                    % (len(edge_problems), "一致" if turn_same else "有差异",
                       "一致" if macro_same else "有差异"))
'''

# ---------- 3. _guismoke.py：macros_diff 断言 ----------
GS_OLD = '''        check(any("转弯补偿差异" in s for s in E.M.turn_diff_lines(_d1)),
              "turn_diff_lines：差异报告里出「转弯补偿差异」段")
    finally:
        _t["stop"][0] = _b0
        _t["consts"]["TURN_L_PIVOT"] = _bL
        _t["calc_enable"] = _bC
'''
GS_NEW = '''        check(any("转弯补偿差异" in s for s in E.M.turn_diff_lines(_d1)),
              "turn_diff_lines：差异报告里出「转弯补偿差异」段")
    finally:
        _t["stop"][0] = _b0
        _t["consts"]["TURN_L_PIVOT"] = _bL
        _t["calc_enable"] = _bC
    # 「查看代码差异」的「宏定义差异」纯函数 macros_diff / macros_diff_lines
    check(E.M.macros_diff(app.model.macros, dict(app.model.macros))["same"],
          "macros_diff：同一份宏自比 ⇒ same=True")
    _mcopy = dict(app.model.macros)
    _kM = sorted(_mcopy)[0]
    _mcopy[_kM] = "__DIFF_TEST__"
    _md = E.M.macros_diff(app.model.macros, _mcopy)
    check(any(k == _kM for k, _s, _c in _md["chg"]) and not _md["same"],
          "macros_diff：改一个宏 ⇒ 报改值（%s）" % (_md["chg"][:3],))
    check(any("宏定义差异" in s for s in E.M.macros_diff_lines(_md)),
          "macros_diff_lines：差异报告里出「宏定义差异」段")
'''

edits = [(MM, MM_OLD, MM_NEW), (ME, ME1_OLD, ME1_NEW), (ME, ME2_OLD, ME2_NEW),
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
