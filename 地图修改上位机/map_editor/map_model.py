# -*- coding: utf-8 -*-
"""
map_model.py — 寻宝地图「源码解析 / 数据模型 / 校验 / 规划 / 导出」核心（与界面无关）

唯一数据源仍是固件的两个文件：
  Navigation/map.h          ->  enum MapNode（节点名 → 索引）
  Navigation/map_message.c  ->  NavEdgeTbl[]（边表，唯一人工编辑源）
  Mission/config.h          ->  LEN_*/DOOR_LEN_*/ANGLE_* 宏（边表里用宏写 step/angle）

本模块只读源码；所有修改都发生在内存模型里，再由 export_* 生成文本。
"""
import os
import re
import json
import math
import datetime

# ---------------------------------------------------------------- 仓库路径

def find_root(start=None):
    """从脚本位置向上找仓库根（含 Navigation/map_message.c 的那一层）。"""
    here = os.path.dirname(os.path.abspath(start or __file__))
    cur = here
    for _ in range(6):
        if os.path.isfile(os.path.join(cur, "Navigation", "map_message.c")):
            return cur
        cur = os.path.dirname(cur)
    return os.path.dirname(os.path.dirname(here))


ROOT = find_root()
PATH_MAP_H = os.path.join(ROOT, "Navigation", "map.h")
PATH_EDGE_C = os.path.join(ROOT, "Navigation", "map_message.c")
PATH_MSG_H = os.path.join(ROOT, "Navigation", "map_message.h")
PATH_CONFIG = os.path.join(ROOT, "Mission", "config.h")
# 「转弯前补偿」两张表都写在 map.c 里（不像边表那样单独一个文件）
PATH_MAP_C = os.path.join(ROOT, "Navigation", "map.c")
# 路径规划权重表 NavObsPenalty[]（唯一数据源，改这里等于改固件）
PATH_NAV_C = os.path.join(ROOT, "Navigation", "nav_planner.c")


# ---------------------------------------------------------------- flag / func 名字表
# 与 Navigation/map.h 的 #define 一一对应（只用于界面勾选与校验，不改变固件）
FLAG_ORDER = [
    "NO", "NONE",                                                             # 1<<0
    "DLEFT", "DRIGHT", "CLEFT", "CRIGHT",                                      # 1<<1..4
    "MUL2SING", "MUL2MUL", "AWHITE",                                            # 1<<5..7
    "RESTMPUZ", "STOPTURN", "SLOWDOWN",                                         # 1<<8..10
    "LEFT_LINE", "RIGHT_LINE", "MCLEFT", "MCRIGHT",                             # 1<<11..14
    "DRIFT", "L_follow", "R_follow", "MORELED", "NEAR_CENTER",                  # 1<<15..19
    "NOTURN", "INGNORE", "Temp_L", "Temp_R", "TEMP_NEAR_CENTER",                # 1<<20..24
]
FLAG_ORDER_SORT = {n: i for i, n in enumerate(FLAG_ORDER)}

FUNC_ORDER = [
    "NONE", "UpStage", "Bridge", "Hill", "LBHill", "SM", "View", "View1", "BACK",
    "BSoutPole", "QQB", "BLBS", "BLBL", "DOOR", "BHM", "IGNORE", "Special_node",
    "DOOR1", "UpStageHome",
]

# 常用速度档（在 Application/chassis_api.h；界面给下拉，也允许填数字）
SPEED_NAMES = ["SPEED0", "SPEED1", "SPEED2", "SPEED25", "SPEED3", "SPEED4", "SPEED5"]

NODE_KIND_ORDER = ["S", "P", "N", "C", "B", "G", "D"]


def node_kind(name):
    """按命名前缀分类：P=平台, S=景点, N=普通节点, C=拐点/分支, B=桥/障碍, G/D=其它。"""
    m = re.match(r"^([A-Za-z]+)", name or "")
    k = (m.group(1) if m else "")[:2].upper()
    for p, kind in (("P", "P"), ("S", "S"), ("C", "C"), ("B", "B"), ("N", "N"), ("G", "G")):
        if k.startswith(p):
            return kind
    return "?"


# ---------------------------------------------------------------- 源码解析

def _strip_line_comment(line):
    i = line.find("//")
    return line if i < 0 else line[:i]


def _strip_block_comments(text):
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


class ParseError(Exception):
    pass


def parse_map_enum(path=PATH_MAP_H):
    """解析 map.h 的 enum MapNode。返回 [(name, comment, index), ...]（按出现顺序）。

    索引 = 出现顺序（枚举不给初值），与固件一致。
    """
    src = open(path, encoding="utf-8").read()
    m = re.search(r"enum\s+MapNode\s*\{(.*?)\}\s*;", src, re.S)
    if not m:
        raise ParseError("map.h 里找不到 enum MapNode")
    body = m.group(1)
    out = []
    idx = 0
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        cm = re.search(r"//\s*(.*)$", line)
        comment = cm.group(1).strip() if cm else ""
        part = _strip_line_comment(line).strip().rstrip(",").strip()
        for tok in part.split(","):
            tok = tok.strip()
            if not tok:
                continue
            cmt = comment
            if "=" in tok:                     # 万一将来加了显式初值
                name, val = tok.split("=", 1)
                name = name.strip()
                try:
                    idx = int(val.strip(), 0)
                except ValueError:
                    pass
            else:
                name = tok
            if not re.match(r"^[A-Za-z_]\w*$", name):
                continue
            out.append((name, cmt, idx))
            idx += 1
    if not out:
        raise ParseError("enum MapNode 解析为空")
    return out


# ---------------------------------------------------------------- C 表达式求值
# 自己写递归下降：不用 eval + 文本替换，避免 ANGLE_N8N3 这类名字被
# 子串替换成 ANGLE_(...)_N8N3（_ 是 \w，\b 拦不住）。

_TOKEN_RE = re.compile(r"\s*(?:(\d+)|([A-Za-z_]\w*)|(.))")


class _CExpr:
    def __init__(self, text, macros):
        self.macros = macros
        self.toks = []
        for m in _TOKEN_RE.finditer(text or ""):
            if m.group(1):
                self.toks.append(("num", int(m.group(1))))
            elif m.group(2):
                self.toks.append(("id", m.group(2)))
            else:
                self.toks.append(("op", m.group(3)))
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def eat(self, val=None):
        t = self.peek()
        if val is not None and t[1] != val:
            raise ValueError("期望 %r，实际 %r" % (val, t[1]))
        self.i += 1
        return t

    # expr := term (('+'|'-') term)*
    def expr(self):
        v = self.term()
        while True:
            k, s = self.peek()
            if k == "op" and s in "+-":
                self.eat()
                r = self.term()
                v = v + r if s == "+" else v - r
            else:
                return v

    # term := unary (('*'|'/') unary)*
    def term(self):
        v = self.unary()
        while True:
            k, s = self.peek()
            if k == "op" and s in "*/":
                self.eat()
                r = self.unary()
                if s == "*":
                    v = v * r
                else:
                    if r == 0:
                        raise ValueError("除零")
                    v = v / r
            else:
                return v

    # unary := ('-'|'+') unary | atom
    def unary(self):
        k, s = self.peek()
        if k == "op" and s in "+-":
            self.eat()
            v = self.unary()
            return -v if s == "-" else v
        return self.atom()

    # atom := num | id | id '(' expr ')' | '(' expr ')'
    def atom(self):
        k, s = self.eat()
        if k == "num":
            return float(s)
        if k == "id":
            if s == "ANGLE_REV":
                self.eat("(")
                v = self.expr()
                self.eat(")")
                return (v - 180.0) if v >= 0 else (v + 180.0)
            if s in self.macros:
                return _CExpr(self.macros[s], self.macros).parse()
            raise ValueError("未知标识符 %s" % s)
        if k == "op" and s == "(":
            v = self.expr()
            self.eat(")")
            return v
        raise ValueError("无法解析的记号 %r" % (s,))

    def parse(self):
        v = self.expr()
        if self.i != len(self.toks):
            raise ValueError("表达式尾部多余记号")
        return v


def eval_c_expr(expr, macros):
    """把 C 表达式（可含 config.h 的宏与 ANGLE_REV）求值成数字；失败返回 None。"""
    if expr is None:
        return None
    e = str(expr).strip()
    if not e:
        return None
    try:
        return _CExpr(e, macros).parse()
    except Exception:
        return None


def parse_config_macros(path=PATH_CONFIG, source_text=None):
    """把 config.h 解析成「宏 -> 表达式」字典（按当前 USE_FIELD 展开）。

    返回 (macros, field_name)。macros 里只有对象宏（ANGLE_REV 由求值器内置）。
    """
    src = source_text if source_text is not None else open(path, encoding="utf-8").read()
    # 先整体去掉块注释：config.h 里有跨行 /* ... */（如 VIA_POINT 那条），
    # 逐行 strip 会把 "*/" 留在表达式里导致该宏求值失败。
    src = _strip_block_comments(src)

    consts = {}
    for name in ("FIELD_COMP", "FIELD_SCHOOL"):
        mm = re.search(r"#define\s+%s\s+(\d+)" % name, src)
        if mm:
            consts[name] = int(mm.group(1))
    mm = re.search(r"#define\s+USE_FIELD_?\s+([A-Za-z_]\w*)", src)
    if not mm:
        raise ParseError("config.h 里找不到 USE_FIELD")
    field_tok = mm.group(1)
    field = consts.get(field_tok)
    if field is None:
        try:
            field = int(field_tok, 0)
        except ValueError:
            field = 0
    field_name = "FIELD_SCHOOL" if field == consts.get("FIELD_SCHOOL", 1) else "FIELD_COMP"

    def eval_cond(expr):
        e = expr.strip()
        m2 = re.match(r"^USE_FIELD_?\s*==\s*(\w+)$", e)
        if m2:
            return consts.get(m2.group(1), 0) == field
        m2 = re.match(r"^(\d+)\s*==\s*(\d+)$", e)
        if m2:
            return int(m2.group(1)) == int(m2.group(2))
        e2 = e
        for k, v in consts.items():
            e2 = re.sub(r"\b%s\b" % k, str(v), e2)
        try:
            return bool(eval(e2, {"__builtins__": {}}, {}))
        except Exception:
            return True

    defines = {}
    stack = []          # [[外层是否 active, 该链上是否已命中过]]
    active = True
    for raw in src.splitlines():
        line = raw.strip()
        if line.startswith("#if"):
            cond = eval_cond(line[3:])
            stack.append([active, bool(cond)])
            active = active and bool(cond)
            continue
        if line.startswith("#elif"):
            prev_active, taken = stack[-1]
            cond = eval_cond(line[5:])
            stack[-1][1] = taken or bool(cond)
            active = prev_active and (not taken) and bool(cond)
            continue
        if line.startswith("#else"):
            prev_active, taken = stack[-1]
            stack[-1][1] = True
            active = prev_active and (not taken)
            continue
        if line.startswith("#endif"):
            if stack:
                active = stack.pop()[0]
            continue
        if not active:
            continue
        # 函数宏的 '(' 必须紧贴宏名。不能写成 name + 可选 '(args)'：
        # "#define LEN_N18B5   (LEN_N22B7 - 20)" 里的括号会被当成参数表吃掉，
        # body 变空 -> 宏被误判成函数宏丢弃。故用「紧贴括号=函数宏 | 其余=对象宏」两分支。
        m2 = re.match(r"#define\s+([A-Za-z_]\w*)\(", line)
        if m2:
            continue                      # 函数宏（本项目只有 ANGLE_REV，已内置在求值器里）
        m2 = re.match(r"#define\s+([A-Za-z_]\w*)\s+(.*?)\s*$", line)
        if not m2:
            continue
        name, body = m2.group(1), m2.group(2)
        body = _strip_line_comment(body).strip()
        if body:
            defines[name] = body

    return defines, field_name


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


# ============================== 路径规划权重（NavObsPenalty[]）========================
# 固件 Navigation/nav_planner.c 的 `static const float NavObsPenalty[20]`，下标 = map.h 的
# barriers 枚举值，含义=「过这类障碍的等效 cm 代价」。规划器 cost = W_STEP*step + W_OBS*penalty
# + W_TURN*|转角|，所以**改这几个数就能改变走哪条路**（不需要改 wp必经点）。
#
# ⚠️ 三处必须同步（_selftest.py 第 8 节会逐项比对，不一致就红）：
#   ① Navigation/nav_planner.c 的 NavObsPenalty[]   ← 本模块读写的就是它（唯一数据源）
#   ② 本文件MapModel.OBS                             ← 上位机自己算路线用
#   ③ validate/_weight_calib.py 的 OBS_PENALTY       ← 回归校验用
# 上位机改完 ① 会自动同步 ②（同一进程内），③ 是独立脚本需手动或由「写回」一并处理。

# 只暴露"人能看懂名字 + 会真实影响路线"的项；下标 0/16/17/18 恒为 0，不给拉条。
WEIGHT_EDITABLE = [
    "UpStage", "Bridge", "Hill", "LBHill", "SM", "View", "View1",
    "BSoutPole", "QQB", "BLBS", "BLBL", "DOOR", "BHM", "UpStageHome",
]
WEIGHT_HINT = {
    "Hill":  "山地/楼梯。调高→更愿意走平路（南环）；调低→更愿意爬楼梯。",
    "BLBL":  "长波动板。调低→南环变便宜（南环有 2 段长波）。",
    "BLBS":  "短波动板。",
    "SM":    "刀山。调高→更避开 N12→N11 这条刀山近路。",
    "View":  "景点支路。调高→更不把景点当捷径。",
    "View1": "直立景点支路。",
    "DOOR":  "门。固定开销（停车+读灯500ms）；调高→更不穿门。",
    "Bridge": "桥。",
    "UpStage": "平台（去完要往返）。",
    "UpStageHome": "回家平台。",
    "BHM":   "高山。",
    "QQB":   "跷跷板（单相）。",
    "BSoutPole": "南极。",
    "LBHill": "小山地。",
    "BACK":  "后退桩（别动，必须远大于其它）。",
}

def parse_obs_penalty(path=None):
    """解析固件 NavObsPenalty[] → {func_name: float}（按 FUNC_ORDER 的枚举下标）。

    与 _selftest.py 第 8 节的解析口径保持一致（下标 0 恒 0，16/17/18 也恒 0）。
    解析不到就raise ParseError，**不静默返回默认值** —— 静默会让上位机显示的路线
    和车上跑的完全无关却毫无提示（这个坑已经踩过：OBS 与固件不同步）。
    """
    # ⚠️ 用 `path=None` + 运行时读全局，**不要**写 `path=PATH_NAV_C`：
    #    默认值在函数**定义时**就绑定了，之后再改模块变量（测试重定向到副本）不生效。
    path = path or PATH_NAV_C
    try:
        src = open(path, encoding="utf-8").read()
    except OSError as e:
        raise ParseError("打不开 %s：%s" % (path, e))
    m = re.search(r"NavObsPenalty\s*\[[^\]]*\]\s*=\s*\{", src)
    if not m:
        raise ParseError("nav_planner.c 里找不到 NavObsPenalty[] 初始化")
    end = src.find("};", m.end())
    if end < 0:
        raise ParseError("NavObsPenalty[] 没有闭合的 };")
    body = src[m.end():end]
    vals = _scan_obs_body(body)
    if len(vals) < 20:
        raise ParseError("NavObsPenalty[] 只解析到 %d 项（应≥20），源码格式可能变了"
                         % len(vals))
    # FUNC_ORDER 是**列表**，下标正好 = 固件注释里的 barriers 枚举编号（NONE=1 … UpStageHome=19），
    # 也就是 NavObsPenalty[] 的下标（0 是"空"）。所以 vals[i] 对应 FUNC_ORDER[i-1]。
    return {name: vals[idx + 1] for idx, name in enumerate(FUNC_ORDER)
            if idx + 1 < len(vals)}


def _scan_obs_lines(body, eol="\n"):
    r"""把 NavObsPenalty[] 的表体拆成 [(行号, 数值 or None, 该行原文)]。

    ★ 用**块注释状态机**而不是逐行 `find("/*")` / `re.sub` —— 两个坑都踩过：
      ① 注释正文含 `**`（非贪婪的 `/* ... */` 会提前终止，把后面整行当注释吞掉
         ⇒ 只解析到 18 项，Hill/DOOR 两行凭空消失）；
      ② Hill/DOOR 两项的注释**跨多行**（`/* 4 Hill …` 一直到 `*/` 才结束），
         续行里没有 `/*`，逐行剥注释会把 `· N12→N20 ：要到 Hill <= 200 才翻` 当成候选行。
      只有"处于注释外 + 该行以数值+逗号开头"才算一个权重项。
    """
    out = []
    in_block = False
    for i, line in enumerate(body.split(eol)):
        s = line.strip()
        if not s:
            out.append((i, None, line))
            continue
        if in_block:
            out.append((i, None, line))
            j = s.find("*/")
            if j >= 0:
                in_block = False
            continue
        # 注释外：先取 /* 之前的代码部分
        k = s.find("/*")
        code = (s[:k] if k >= 0 else s).strip()
        if k >= 0 and s.find("*/", k) < 0:
            in_block = True                      # 注释跨行，本行只有开头
        vm = re.match(r"^(-?\d+(?:\.\d+)?)f?\s*,?$", code)
        out.append((i, (float(vm.group(1)) if vm else None), line))
    return out


def _scan_obs_body(body):
    """便捷封装：只要数值列表（按出现顺序）。"""
    return [v for _i, v, _l in _scan_obs_lines(body) if v is not None]


def write_obs_penalty(values, path=None, backup_dir=None):
    """把 {func_name: float} 写回固件 NavObsPenalty[]。

    * **只改数字**，注释/缩进/顺序/换行一律按原样重排回去（改一个数不该产生 20 行 diff）。
    * 行尾按文件原样探测（nav_planner.c 是 LF），**不用文本模式写**，避免 Windows 上被改成 CRLF。
    * 返回 [(func_name, old, new), ...] 表示真正变了的项。
    """
    if not isinstance(values, dict):
        raise ValueError("values 应为 {func_name: 数字}")
    path = path or PATH_NAV_C        # 见 parse_obs_penalty 的同名注释（默认值绑定时机）
    raw = open(path, "rb").read()
    crlf = raw.count(b"\r\n")
    lf_only = raw.count(b"\n") - crlf
    eol = "\r\n" if crlf >= lf_only else "\n"
    src = raw.decode("utf-8")
    m = re.search(r"NavObsPenalty\s*\[[^\]]*\]\s*=\s*\{", src)
    if not m:
        raise ParseError("nav_planner.c 里找不到 NavObsPenalty[] 初始化")
    end = src.find("};", m.end())
    if end < 0:
        raise ParseError("NavObsPenalty[] 没有闭合的 };")
    body = src[m.end():end]

    lines = body.split(eol)
    scanned = _scan_obs_lines(body, eol)
    # 遍历时要用「这是第几个权重项」当枚举下标（不是行号）——跨行注释会让行号 ≠ 下标
    changed = []
    seq = -1
    for (li, oldv, raw_line) in scanned:
        if oldv is None:
            continue
        seq += 1
        if seq >= 20:
            break
        # 下标 = barriers 枚举值（seq 0 = 下标 0 的"空"）
        name = FUNC_ORDER[seq - 1] if 1 <= seq <= len(FUNC_ORDER) else None
        if name is None or name not in values:
            continue
        newv = float(values[name])
        if newv < 0:
            raise ValueError("%s 的权重不能为负（%r）" % (name, newv))
        if abs(newv - oldv) < 1e-9:
            continue
        # 只换数字：保留原缩进 + 原行尾注释（本项注释都在同一行，跨行注释不动）
        stripped = raw_line.strip()
        k = stripped.find("/*")
        comment = stripped[k:].strip() if k >= 0 else ""
        indent = raw_line[:len(raw_line) - len(raw_line.lstrip())]
        tail = (", " + comment) if comment else ","
        lines[li] = "%s%s%s" % (indent, _fmt_obs(newv), tail)
        changed.append((name, oldv, newv))

    if not changed:
        return []
    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(backup_dir, "nav_planner.c.%s.bak" % stamp), "wb") as f:
            f.write(raw)          # 备份保持原字节
    new_src = src[:m.end()] + eol.join(lines) + src[end:]
    with open(path, "wb") as f:
        f.write(new_src.encode("utf-8"))     # 二进制写，行尾不会被转换
    return changed


def _fmt_obs(v):
    """权重数字格式：整数就写整数（与固件里 `230.0f` 这种写法对齐写成 `230.0f`）。"""
    if abs(v - round(v)) < 1e-9:
        return "%d.0f" % int(round(v))
    return ("%.4f" % v).rstrip("0") + "f"


def load_obs_from_firmware(path=None):
    """读固件 → 同时刷新 MapModel.OBS，让上位机立刻按固件权重算路线。"""
    vals = parse_obs_penalty(path)
    MapModel.OBS.update({k: v for k, v in vals.items() if k in MapModel.OBS})
    return vals


def sync_obs_to_model(values):
    """把权重写进 MapModel.OBS（只更新存在的键，不新增枚举名）。"""
    if not isinstance(values, dict):
        raise ValueError("values 应为 {func_name: 数字}")
    n = 0
    for k, v in values.items():
        if k in MapModel.OBS and isinstance(MapModel.OBS.get(k), (int, float)):
            MapModel.OBS[k] = float(v)
            n += 1
    return n


def obs_diff(cur, src):
    """比较「当前模型的规划权重」与「nav_planner.c 源码的 NavObsPenalty[]」（只读）。

    与 macros_diff / turn_diff 同构：返回 dict(add/dele/chg/same)，但**只比 chg**——
    权重是固定 20 项的表，不存在"新增/删除一项"这种可能，键集固定，
    真正要报的只有"哪几项的值被改了"。
    ⚠️ 浮点按 1e-6 容差比：解析出来是 230.0，用户拖条是 230，直接 == 也能过，
       但走一遍 round() 更稳（拖条是 IntVar，天然整数）。
    """
    cur = {k: float(v) for k, v in (cur or {}).items() if _is_num(v)}
    src = {k: float(v) for k, v in (src or {}).items() if _is_num(v)}
    chg = []
    for name in FUNC_ORDER:                     # 按固件里的固定顺序，不排序
        if name not in cur or name not in src:
            continue
        if abs(cur[name] - src[name]) > 1e-6:
            chg.append((name, src[name], cur[name]))
    return {"chg": chg, "same": not chg}


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def obs_diff_lines(td):
    """把 `obs_diff()` 的结果写成差异报告里的几行（纯字符串、无 Tk，便于自检）。"""
    if td.get("same"):
        return ["规划权重差异：无（MapModel.OBS 与 nav_planner.c 的 NavObsPenalty[] 一致）"]
    out = ["规划权重差异（nav_planner.c NavObsPenalty[]，左=源码值，右=当前模型值）："]
    for name, sv, cv in td["chg"]:
        out.append("  ~ %s：%g → %g" % (name, sv, cv))
    out.append("  ⇒ 当前模型显示的路线已按【当前值】算；固件仍按【源码值】跑。"
               "写回固件后两边才一致。")
    return out


def write_use_field(new_field, path=PATH_CONFIG):
    """切换 config.h 的 USE_FIELD（FIELD_COMP / FIELD_SCHOOL）。

    只改 `#ifndef USE_FIELD` 块里那一行，不动其它。返回新 field_name。
    """
    if new_field not in ("FIELD_COMP", "FIELD_SCHOOL"):
        raise ParseError("场地只能是 FIELD_COMP 或 FIELD_SCHOOL，不是 %r" % new_field)
    src = open(path, encoding="utf-8").read()
    pattern = re.compile(r"(#ifndef\s+USE_FIELD_?\s*\n#define\s+USE_FIELD_?\s+)(\w+)(\s*\n#endif)")
    m = pattern.search(src)
    if not m:
        raise ParseError("config.h 里找不到 #ifndef USE_FIELD / #define USE_FIELD / #endif 块")
    if m.group(2) == new_field:
        return new_field
    new_src = src[:m.start(2)] + new_field + src[m.end(2):]
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_src)
    return new_field


_EDGE_ROW_RE = re.compile(
    r"\{\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*,\s*(.*?)\s*\}\s*,?\s*(?:/\*\s*(.*?)\s*\*/)?\s*$"
)


def parse_edge_table(path=PATH_EDGE_C):
    """解析 NavEdgeTbl[]。返回 (rows, declared_count)。

    每行 -> dict(from, to, flag, angle, step, speed, func, comment)
    文本字段原样保留（没编辑过就原样导出，保证"不改 = 不产生差异"）。
    """
    src = open(path, encoding="utf-8").read()
    m = re.search(r"NavEdgeTbl\s*\[[^\]]*\]\s*=\s*\{", src)
    if not m:
        raise ParseError("map_message.c 里找不到 NavEdgeTbl[] 初始化")
    start = m.end()
    end = src.index("};", start)
    body = src[start:end]

    declared = None
    try:
        cm = re.search(r"#define\s+NAV_EDGE_COUNT\s+(\d+)",
                       open(PATH_MSG_H, encoding="utf-8").read())
        if cm:
            declared = int(cm.group(1))
    except OSError:
        pass

    rows = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("/*") or "{" not in line:
            continue
        mm = _EDGE_ROW_RE.search(line)
        if not mm:
            continue
        frm, to, rest, comment = mm.group(1), mm.group(2), mm.group(3), mm.group(4)
        parts = [p.strip() for p in rest.split(",")]
        if len(parts) < 5:
            continue
        # flag 可能因为源码里写成 "CLEFT| DLEFT | DRIGHT" 而含逗号（历史笔误）：
        # 取末 4 段作为 angle/step/speed，倒数第 5 段起是 flag
        func, speed, step, angle = parts[-1], parts[-2], parts[-3], parts[-4]
        flag = ", ".join(parts[:-4])
        cmt = (comment or "").strip()
        # 去掉行尾注释里重复的 "A->B" 前缀（导出时统一写成 "A->B（原注释）"）
        cmt = re.sub(r"^%s\s*->\s*%s\s*" % (re.escape(frm), re.escape(to)), "", cmt).strip()
        rows.append({
            "from": frm, "to": to, "flag": flag, "angle": angle,
            "step": step, "speed": speed, "func": func, "comment": cmt,
        })
    return rows, declared


# ---------------------------------------------------------------- 转弯前补偿（map.c）
# 语义 / 背景 / 参数可信度见 `项目讲解文档/project_reference.md` §14。
#
# 固件里"转弯前补偿距离"由**两张表**决定（都在 Navigation/map.c，不在边表里）：
#   ① kTurnTbl[]                        停车原地转分支（GetForwardDistanceBeforeTurn）
#   ② GetForwardDistanceBeforeGyroTurn  陀螺不停车转分支（一条 if 链 + 默认 return 0）
# 外加"能算就算"（Tier2）公式的 4 个参数，也是 map.c 顶部的 #define：
#   TURN_L_PIVOT / TURN_GATE_CM / TURN_D_{CRIGHT,CLEFT,DLEFT,DEFAULT}
#
# ⚠️ 两张表的**分支判定不在表里**：`Nav_TurnAndAdvance()` 按
#      (STOPTURN 标志 && |转弯|>20°) || |转弯|>=90°
#    选分支 ⇒ 表里存着、但当前地图走不到那个分支的条目就是**死值**
#    （project_reference §14.1 列的 8 条就是这么来的）。
#    所以编辑器必须把"表项会不会生效"算出来给用户看，不能只列表面值。

TURN_STOP_DEFAULT = 19.0     # 停车转分支都没命中时的兜底（map.c 的 `return 19`）
TURN_GYRO_DEFAULT = 0.0      # 陀螺转分支的兜底（map.c 的 `return 0`）

# 公式参数的默认值（解析不到就用它，保证界面不炸）
TURN_CONST_DEFAULTS = {
    "TURN_L_PIVOT": 19.0,      # 旋转中心→传感器板中心 纵向距离
    "TURN_GATE_CM": 5.0,       # 5cm 闸门：|公式-实测| > 它就不用公式
    "TURN_D_CRIGHT": 11.0,
    "TURN_D_CLEFT": -4.0,
    "TURN_D_DLEFT": -5.0,
    "TURN_D_DEFAULT": -4.0,
}
# 判据 → 该判据用的 d。map.c 只区分 CRIGHT / CLEFT / DLEFT 三种，其余一律走 DEFAULT。
# 判据编号见 Navigation/map.h 的 enum ARRIVE_*（ArriveDetect_task.c 写、map.c 只读）。
TURN_ARRIVE_D = {
    "ARRIVE_CRIGHT": "TURN_D_CRIGHT",
    "ARRIVE_CLEFT": "TURN_D_CLEFT",
    "ARRIVE_DLEFT": "TURN_D_DLEFT",
}

# 分支判据（镜像 map.c: Nav_TurnAndAdvance 里那三个魔数）
TURN_STRAIGHT_TOL = 10.0     # |Δ| < 10° ⇒ 直行通过，不走任何补偿
TURN_STOPTURN_TOL = 20.0     # 带 STOPTURN 且 |Δ| > 20° ⇒ 停车原地转
TURN_ANGLE_STOP = 90.0       # |Δ| >= 90° ⇒ 一律停车原地转
TURN_NOTURN_FUNCS = ("UpStage", "UpStageHome", "BSoutPole")   # 平台类：结束时朝向已对准


def _blank_block_comments(text):
    """把 `/* ... */` 挖成空白，但**保留其中的换行数**。

    ⚠️ 不能用 `_strip_block_comments()`（它把整块替换成一个空格 ⇒ 跨行注释会把后面的行
    并到前一行上），本模块后面要**按行**解析表项，行结构必须保住。
    """
    return re.sub(r"/\*.*?\*/",
                  lambda m: " " * (0 if "\n" in m.group(0) else 1)
                            + "\n" * m.group(0).count("\n"),
                  text, flags=re.S)


def flag_set(flag):
    """把边表里的 flag 文本切成集合（`A|B|C` 或历史笔误 `A, B` 都吃得下）。"""
    return {p.strip() for p in re.split(r"[|,]", flag or "") if p.strip()}


def need2turn(a, b):
    """镜像固件 `nav_planner.c: nav_need2turn()` —— 从 a 转到 b 需要转多少度，归一化到 (-180,180]。"""
    if a is None or b is None:
        return None
    d = b - a
    while d > 180.0:
        d -= 360.0
    while d < -180.0:
        d += 360.0
    return d


# ---------------------------------------------------------------- 路口判断标志位（多维分类）
#
# 到达路口时，固件 `ArriveDetect_task.c: deal_arrive()` 依据**循迹板 16 灯的「灯位图案」**
# （bit15 = 最左 1 号灯 … bit0 = 最右 16 号灯，板装车头）来区分路口类型 —— 本质是**路口几何
# 形状**，与车「接下来往哪转」无关（用户 2026-10-02 澄清）。
#
# 10 条判据的灯位图案 ↔ 路口几何（固件真相）：
#   DLEFT  (0xFC00) 左 6 灯 ≥5 亮   → 车头**左侧整片横向白线**   → 左**直角**弯（横线，⊥ 行进方向）
#   DRIGHT (0x003F) 右 6 灯 ≥5 亮   → 车头**右侧整片横向白线**   → 右**直角**弯
#   CLEFT  (0x6000) 左 2/3 灯亮      → 左前**斜线**               → 左**斜岔路**（斜线 45°）
#   CRIGHT (0x000C) 左 13/14 灯亮    → 右前**斜线**               → 右**斜岔路**
#   MCLEFT (0x8000) 最左 1 灯亮      → 岔线**极靠外**             → 左**急弯/小半径**
#   MCRIGHT(0x0001) 最右 1 灯亮      → 岔线**极靠外**             → 右**急弯/小半径**
#   MUL2SING        lineNum 多→单    → 线数**由多变一**           → 汇入/收窄
#   MUL2MUL         lineNum 多→单→多 → 线数**多→多**             → 十字/多岔
#   AWHITE (0x1FF8) 正中 10 灯全亮    → 整幅**全白横带**          → 门区/全横线（特殊）
#   MORELED         不挑位置 ≥5 亮    → 兜底「很多灯」             → 非特异性
#
# 静态几何能可靠反推的只有「灯位图案」里**由角度决定**的那部分：岔线方向与行进方向的夹角
# θ = |need2turn(入边角, 出边角)| 决定岔线是「斜线 / 横线 / 急弯靠边」。据此分档（见下方
# 常量，分界依据 = 边表真实角度分布聚类 + 灯位几何推导，project_reference §6）：

# 有「特殊到达检测语义」的 flag 组合：即使 func=NONE，只要 flag 里带这些位，就说明这条边的
# 到达检测不是标准路口（例：P6→N7 func=NONE 但带 AWHITE=门区全白横带 + STOPTURN 停车转，
# 它的 DLEFT|DRIGHT 组合是作者有意写「双向都检测」——车头朝向不定，不该按普通路口套左右直角弯）。
JUNCTION_SPECIAL_FLAGS = {"AWHITE", "MUL2SING", "MUL2MUL"}

# 有「特殊到达检测语义」的 func：这些边的到达判据不是标准路口（门区用 AWHITE/多判据、
# 直立景点 View/回家 BACK、跷跷板 QQB/SM、平台类靠 map_function 内部动作），
# 一键修复默认**跳过**它们，避免误改。用户主动框选时仍可强制处理。
JUNCTION_SPECIAL_FUNCS = {
    "DOOR", "DOOR1", "View", "View1", "BACK", "QQB", "SM", "BHM", "BLBL", "BLBS",
    "BSoutPole", "UpStage", "UpStageHome", "Bridge", "Hill", "LBHill",
    "IGNORE", "Special_node",
}


def is_plain_edge(edge):
    """是否为「普通路口边」：func 不在特殊列表，且 flag 里不带特殊到达检测位。

    例：P6→N7 的 func=NONE，但 flag 带 AWHITE（门区检测），到达判据另有用途，跳过。
    """
    if (edge.func or "") in JUNCTION_SPECIAL_FUNCS:
        return False
    if flag_set(edge.flag) & JUNCTION_SPECIAL_FLAGS:
        return False
    return True


# ---- 弯道分档阈值（°），θ = |need2turn(入边角, 出边角)| --------------------------------
# 依据：边表真实转角分布聚类 —— 0°(31 条，直行) / 90°(41 条主峰，直角) / 125~145°(19 条，
# 大角度急弯) / 30~70°(散落，斜线) / 15~25°(2~5 条，缓弯)。灯位几何：斜线点亮中段 2/3 灯、
# 横线铺满半幅 6 灯、越靠边的岔线点亮的灯越靠外。
JUNCTION_STRAIGHT_TOL = 20.0    # θ ≤ 20°：直行/缓弯，不产生横向路口线，无路口标志
JUNCTION_DIAG_MIN = 20.0        # 20° < θ ≤ 70°：斜线岔路 → CLEFT/CRIGHT（点亮中段灯）
JUNCTION_DIAG_MAX = 70.0
JUNCTION_RIGHT_MIN = 70.0       # 70° < θ ≤ 110°：直角弯 → DLEFT/DRIGHT（横线铺满半幅）
JUNCTION_RIGHT_MAX = 110.0
JUNCTION_SHARP_MIN = 110.0      # 110° < θ ≤ 150°：大角度急弯 → MCLEFT/MCRIGHT（岔线极靠外）
JUNCTION_SHARP_MAX = 150.0
JUNCTION_UTURN_TOL = 150.0      # θ > 150°：原路折返（平台/景点内部转身），不算路口，排除

# MUL 系列（线数变化）无法从单个角度静态判出，用**拓扑**近似：
#   出边数 ≥ 3 且主线延续 → 十字/多岔 → 倾向 MUL2MUL
#   出边数 2~4 且存在直行延续 → 汇入 → 倾向 MUL2SING
JUNCTION_MUL2MUL_BRANCHES = 3   # 终点非折返出边 ≥ 该数，判为多岔（MUL2MUL 的拓扑特征）
JUNCTION_MUL2SING_BRANCHES = 2  # 终点非折返出边 ≥ 该数且主线延续，判为汇入（MUL2SING）


def classify_turn_angle(d):
    """把单个转弯角 d（need2turn，带符号方向）分类成弯道类型。

    返回 (category, side)：
      category ∈ {'straight','diag','right','sharp','uturn'} —— 直行/斜线/直角/急弯/折返
      side     ∈ {'left','right',None} —— 转向侧（d>0 左、d<0 右、0 无）
    这是「角度 → 灯位图案」的核心映射，见模块头注释的分档依据。
    """
    ad = abs(d)
    side = "left" if d > 0 else ("right" if d < 0 else None)
    if ad <= JUNCTION_STRAIGHT_TOL:
        return "straight", None
    if ad <= JUNCTION_DIAG_MAX:
        return "diag", side
    if ad <= JUNCTION_RIGHT_MAX:
        return "right", side
    if ad <= JUNCTION_SHARP_MAX:
        return "sharp", side
    return "uturn", None


def junction_turns(model, edge):
    """返回 `edge` 终点处所有「非折返出边」的转弯角列表 [(出边对象, need2turn), ...]。

    折返（≈180°，原路返回进平台/景点）不产生横向路口线，予以排除；
    也排除回 `edge.frm` 的原路反向边（`door_retreat` 那类）。
    角度求值失败的出边一并排除（返回 None 的条目不出现）。
    """
    out = []
    ang_in = model.ang(edge)
    if ang_in is None:
        return out
    for o in model.edges_of(edge.to, True):
        if o.to == edge.frm:
            continue
        a = model.ang(o)
        if a is None:
            continue
        d = need2turn(ang_in, a)
        if d is None or abs(d) >= JUNCTION_UTURN_TOL:
            continue
        out.append((o, d))
    return out


def junction_flags_needed(model, edge, include_mul=True):
    """根据 `edge` 终点处的路口几何，算出「应该写哪几个**到达判据标志**」（多维）。

    覆盖全部角度类判据（DLEFT/DRIGHT/CLEFT/CRIGHT/MCLEFT/MCRIGHT）+ 拓扑类（MUL2SING/MUL2MUL）。
    返回 dict，键 = 标志名，值 = 触发它的证据（(出边名, 转角) 或拓扑说明），无需要的键不出现。
    这是旧版「只返回 (need_dleft, need_dright)」的升级 —— 每类弯道各有判定条件。

    include_mul=False 时**不算 MUL2SING/MUL2MUL**（线数时序判据，拓扑近似可靠性低，
    默认让用户显式开启才写，见 project_reference §6「到达判据的几何语义」）。
    """
    turns = junction_turns(model, edge)
    need = {}
    # 角度类：一条出边 → 一个判据（按 classify_turn_angle 分档）
    for o, d in turns:
        cat, side = classify_turn_angle(d)
        if cat == "straight" or cat == "uturn":
            continue
        if cat == "right":
            flag = "DLEFT" if side == "left" else "DRIGHT"
        elif cat == "diag":
            flag = "CLEFT" if side == "left" else "CRIGHT"
        elif cat == "sharp":
            flag = "MCLEFT" if side == "left" else "MCRIGHT"
        else:
            continue
        need.setdefault(flag, []).append((o.to, round(d, 1)))
    # 拓扑类：线数变化（多岔 / 汇入）—— 用终点非折返出边数近似（可选，可靠性低）
    if include_mul:
        n_branch = len(turns)
        if n_branch >= JUNCTION_MUL2MUL_BRANCHES:
            need.setdefault("MUL2MUL", []).append(("多岔%d" % n_branch, None))
        elif n_branch >= JUNCTION_MUL2SING_BRANCHES:
            need.setdefault("MUL2SING", []).append(("汇入%d" % n_branch, None))
    return need


# 与路口几何强相关的「到达判据」标志名（angle 类 + 拓扑类）。
# 不含寻线/转弯/陀螺等非到达判据（LEFT_LINE/RIGHT_LINE/STOPTURN/RESTMPUZ/Temp_* 等）。
JUNCTION_ARRIVE_FLAGS = ("DLEFT", "DRIGHT", "CLEFT", "CRIGHT", "MCLEFT", "MCRIGHT",
                         "MUL2SING", "MUL2MUL")


def analyze_junction_flags(model, only_plain=False, include_mul=True, right_only=False):
    """全图路口判据一致性检查（多维）。

    only_plain=True 时只检查「普通路口边」（func 是 NONE），跳过门区/景点/跷跷板等特殊边
    —— 那些边的到达判据可能另有用途（检测组合），自动判断不可靠。

    include_mul=False 时**不检查 MUL2SING/MUL2MUL**（线数时序判据，拓扑近似可靠性低），
    与 junction_flags_needed 同口径 —— 否则「关掉 MUL 自动写」后校验仍会报 MUL 缺失，自相矛盾。

    right_only=True 时**只检查 DLEFT/DRIGHT（直角左右）**，忽略 CLEFT/CRIGHT/MCLEFT/MCRIGHT
    （斜线/急弯的精细分档）—— 这是唯一能静态可靠判出的确定性信号；C/MC 是岔线方向的细分，
    固件作者手写时不会精确到这种程度，把它们当 warn 会大面积误报（用户 2026-10-02 反馈）。

    返回 [{
        edge, func, need, has, extra, missing,
        status: 'extra' | 'missing' | 'wrong',
    }, ...]，只包含 status != 'ok' 的边。
    `need` 是 junction_flags_needed 的完整结果（含证据），`has` 是边表现在写的判据集合。
    """
    if right_only:
        check_flags = ("DLEFT", "DRIGHT")
    else:
        check_flags = JUNCTION_ARRIVE_FLAGS
    out = []
    for e in model.edges:
        if only_plain and not is_plain_edge(e):
            continue
        fs = flag_set(e.flag)
        has = {n for n in check_flags if n in fs}
        need = {n: v for n, v in junction_flags_needed(model, e, include_mul=include_mul).items()
                if n in check_flags}
        extra = sorted(has - set(need))
        missing = sorted(set(need) - has)
        if not extra and not missing:
            continue
        status = "wrong" if (extra and missing) else ("extra" if extra else "missing")
        out.append({"edge": e, "func": e.func,
                    "need": need, "has": has,
                    "status": status, "extra": extra, "missing": missing})
    return out


def suggest_junction_flags(model, edge, include_mul=True, right_only=False):
    """给定边，返回「修正到达判据之后的 flag 文本」。

    对角度类 + 拓扑类判据（JUNCTION_ARRIVE_FLAGS）按几何重写；其它 flag（寻线/转弯/陀螺/
    斜线以外的特殊位）原样保留。顺序按 FLAG_ORDER 重排，保证确定性。

    include_mul=False 时**不写 MUL2SING/MUL2MUL**（这两个是线数时序判据，静态只能拓扑近似、
    可靠性低，默认让用户显式勾选才写）。角度类（D/C/MC 系列）始终按几何写。

    right_only=True 时**只重写 DLEFT/DRIGHT**，CLEFT/CRIGHT/MCLEFT/MCRIGHT 与 MUL 类
    原样保留（它们的静态推断可靠性低，改起来容易把能跑通的地图改坏）。
    """
    fs = flag_set(edge.flag)
    if right_only:
        rewrite = ("DLEFT", "DRIGHT")
    else:
        rewrite = JUNCTION_ARRIVE_FLAGS
    for n in rewrite:
        fs.discard(n)
    need = junction_flags_needed(model, edge, include_mul=include_mul)
    fs |= {n for n in need if n in rewrite}
    ordered = [n for n in FLAG_ORDER if n in fs]
    return "|".join(ordered) if ordered else "NO"


def turn_branch(delta, flag="", func="NONE"):
    """静态判定转弯分支（镜像 map.c: Nav_TurnAndAdvance 的判据）。

    ⚠️ 固件第一条 STOPTURN 判据用的是**陀螺实测航向** `getAngleZ()`，静态算不出来 ——
    这里只用边表角度（`nodes.nowNode.angle` vs `nextNode.angle`），所以判成 'stop' 里
    混了"要陀螺也偏称"的那一支。返回：
      'straight' 直行（|Δ|<10 ／ NOTURN ／ 平台类 function）
      'stop'     停车原地转 → 查表1（kTurnTbl）
      'gyro'     陀螺不停车转 → 查表2（if 链）
      'unknown'  角度求值失败
    """
    if delta is None:
        return "unknown"
    if abs(delta) < TURN_STRAIGHT_TOL:
        return "straight"
    if func in TURN_NOTURN_FUNCS:
        return "straight"
    if "NOTURN" in flag_set(flag):
        return "straight"
    if abs(delta) >= TURN_ANGLE_STOP:
        return "stop"
    if "STOPTURN" in flag_set(flag) and abs(delta) > TURN_STOPTURN_TOL:
        return "stop"
    return "gyro"


_STOP_ROW_RE = re.compile(
    r"\{\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*,\s*"
    r"(-?\d+(?:\.\d+)?)[fF]?\s*\}\s*,?")
_GYRO_ROW_RE = re.compile(
    r"if\s*\(\s*last\s*==\s*([A-Za-z_]\w*)\s*&&\s*now\s*==\s*([A-Za-z_]\w*)\s*&&\s*"
    r"next\s*==\s*([A-Za-z_]\w*)\s*\)\s*return\s+(-?\d+(?:\.\d+)?)[fF]?\s*;")


def parse_turn_tables(path=None, source_text=None):
    """解析 map.c 的「转弯前补偿」两张表 + 公式参数 + 开关。

    返回 dict:
      stop / gyro      [{last, now, next, dist}]（**按源码顺序**，未做去重）
      consts           {TURN_*: 数值}（解析不到的键用 TURN_CONST_DEFAULTS 补齐）
      calc_enable      0 / 1（config.h 的 TURN_CALC_ENABLE；读不到为 None）
      stop_default / gyro_default
      warnings         [str]
      raw              {"stop_block": 原表体文本, "gyro_block": 原函数体文本}

    ⚠️ **必须先剥注释再匹配**：map.c 里注释掉的条目（如 `// { N13, N18, B5, 60 },`）
       会被简单正则当成生效项 —— 这正是 project_reference §14.5 记的那条维护注意。
    """
    path = path or PATH_MAP_C
    text = source_text if source_text is not None else open(path, encoding="utf-8").read()
    lines = [_strip_line_comment(l) for l in _blank_block_comments(text).splitlines()]
    joined = "\n".join(lines)

    out = {"stop": [], "gyro": [], "consts": {}, "calc_enable": None,
           "stop_default": TURN_STOP_DEFAULT, "gyro_default": TURN_GYRO_DEFAULT,
           "warnings": [], "raw": {}}

    # ---- 表1：kTurnTbl[] ----
    m = re.search(r"kTurnTbl\s*\[\s*\]\s*=\s*\{", joined)
    if not m:
        out["warnings"].append("map.c 里找不到 kTurnTbl[] 的初始化")
    else:
        close = _match_brace(joined, joined.index("{", m.start()))
        body = joined[m.end():close] if close > 0 else ""
        out["raw"]["stop_block"] = body
        for ln in body.splitlines():
            mm = _STOP_ROW_RE.search(ln)
            if mm:
                out["stop"].append({"last": mm.group(1), "now": mm.group(2),
                                    "next": mm.group(3), "dist": float(mm.group(4))})

    # ---- 表2：GetForwardDistanceBeforeGyroTurn() 的 if 链 ----
    m2 = re.search(r"GetForwardDistanceBeforeGyroTurn\s*\([^)]*\)\s*\{", joined)
    if not m2:
        out["warnings"].append("map.c 里找不到 GetForwardDistanceBeforeGyroTurn()")
    else:
        close = _match_brace(joined, joined.index("{", m2.start()))
        body = joined[m2.end():close] if close > 0 else ""
        out["raw"]["gyro_block"] = body
        for ln in body.splitlines():
            r = _GYRO_ROW_RE.search(ln)
            if r:
                out["gyro"].append({"last": r.group(1), "now": r.group(2),
                                    "next": r.group(3), "dist": float(r.group(4))})

    # ---- 公式参数（map.c 顶部的 #define）----
    for name, dflt in TURN_CONST_DEFAULTS.items():
        dm = re.search(r"^[ \t]*#define[ \t]+" + name + r"[ \t]+([^\r\n]*)", joined, re.M)
        val = dflt
        if dm:
            vm = re.search(r"-?\d+(?:\.\d+)?", dm.group(1))
            if vm:
                val = float(vm.group(0))
            else:
                out["warnings"].append("#define %s 的值解析不出来，用默认 %g" % (name, dflt))
        out["consts"][name] = val

    # ---- 开关（在 Mission/config.h，不在 map.c）----
    try:
        macros, _field = parse_config_macros()
        expr = macros.get("TURN_CALC_ENABLE")
        if expr is not None:
            out["calc_enable"] = int(float(eval_c_expr(str(expr), macros)))
    except Exception:                                              # noqa: BLE001
        out["calc_enable"] = None

    return out


def _match_brace(text, i):
    """text[i] == '{' ⇒ 返回与它配对的 '}' 的下标；找不到返回 -1。

    比"非贪婪匹配到第一个 `}`"可靠：将来有人给 if 链加了大括号也不会截错。
    （本文件这两段里没有字符串字面量/字符常量，纯计数足够。）
    """
    if i < 0 or i >= len(text) or text[i] != "{":
        return -1
    depth = 0
    for j in range(i, len(text)):
        ch = text[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return j
    return -1


def _fmt_num(v):
    """数字 → C 文本：整数写整数（`25`），小数最少位（`12.5`）。"""
    f = float(v)
    if abs(f - round(f)) < 1e-9:
        return str(int(round(f)))
    return ("%.4f" % f).rstrip("0").rstrip(".")


def export_turn_stop_rows(rows, eol="\r\n", indent="\t"):
    """生成 kTurnTbl[] 的**表体**（不含 `{` 与 `};`）：每行 `\\t{ A, B, C, 25 },`。"""
    body = eol.join("%s{ %s, %s, %s, %s },"
                    % (indent, r["last"], r["now"], r["next"], _fmt_num(r["dist"]))
                    for r in rows)
    return eol + body + eol


def export_turn_gyro_chain(rows, eol="\r\n", indent="\t"):
    """生成 GetForwardDistanceBeforeGyroTurn() 的**函数体**（if 链 + 末尾默认 return）。"""
    lines = ["%sif (last == %s && now == %s && next == %s) return %s;"
             % (indent, r["last"], r["now"], r["next"], _fmt_num(r["dist"]))
             for r in rows]
    lines.append("%sreturn %s; // 默认不前进，走原逻辑未修改"
                 % (indent, _fmt_num(TURN_GYRO_DEFAULT)))
    return eol + eol.join(lines) + eol


def export_turn_node_check(names, eol="\r\n", per_line=3, name_width=3):
    """生成 kTurnTbl_node_check 的表达式体（节点号 < MAP_NODE_LIMIT 的编译期护栏）。

    ⚠️ **必须一起重生成**：guard 里逐个列出表里用到的节点名，新增了一个表里没有的节点
    却忘了改这里，护栏就漏了那个节点（编译照样过，只在车上才发现写错节点号）。
    """
    names = list(names)
    if not names:
        return "1"
    parts = ["(%s < MAP_NODE_LIMIT)" % n.ljust(name_width) for n in names]
    lines = []
    for i in range(0, len(parts), per_line):
        chunk = parts[i:i + per_line]
        head = (i == 0)
        lines.append(("" if head else " ") + " && ".join(chunk) +
                     (" &&" if i + per_line < len(parts) else ""))
    body = eol.join("\t" + l for l in lines)
    return body + " ? 1 : -1"


def splice_turn_tables(src, stop_rows, gyro_rows, eol=None, node_names=None):
    """把两张表写回 map.c 源码（**纯函数**，便于自检干跑）。

    只替换三处，其余（注释、宏、别的函数）一律沿用原文件：
      ① `kTurnTbl[] = {` … `};`  的**表体**
      ② `typedef char kTurnTbl_node_check[` … `];` 的**表达式体**（护栏跟随表项）
      ③ `GetForwardDistanceBeforeGyroTurn()` 的**函数体**
    表外的注释块（含"2026-09-12 清掉 4 条…"那段说明）原样保留。
    """
    if eol is None:
        eol = "\r\n" if "\r\n" in src else "\n"
    out = src

    # ① 停车转表体
    m = re.search(r"kTurnTbl\s*\[\s*\]\s*=\s*\{", out)
    if not m:
        raise ParseError("map.c 里找不到 kTurnTbl[] 的初始化")
    open_i = out.index("{", m.start())
    close_i = _match_brace(out, open_i)
    if close_i < 0:
        raise ParseError("kTurnTbl[] 的花括号不配对")
    out = out[:open_i + 1] + export_turn_stop_rows(stop_rows, eol) + out[close_i:]

    # ② 节点号护栏（跟着表里用到的节点名走）
    m2 = re.search(r"typedef\s+char\s+kTurnTbl_node_check\s*\[", out)
    if m2:
        open_i = out.index("[", m2.start())
        close_i = out.index("]", open_i)
        if node_names is None:
            node_names = []
            for r in list(stop_rows) + list(gyro_rows or []):
                for k in ("last", "now", "next"):
                    if r.get(k) and r[k] not in node_names:
                        node_names.append(r[k])
        out = (out[:open_i + 1]
               + eol + export_turn_node_check(node_names, eol)
               + out[close_i:])

    # ③ 陀螺转 if 链
    m3 = re.search(r"GetForwardDistanceBeforeGyroTurn\s*\([^)]*\)\s*\{", out)
    if not m3:
        raise ParseError("map.c 里找不到 GetForwardDistanceBeforeGyroTurn()")
    open_i = out.index("{", m3.start())
    close_i = _match_brace(out, open_i)
    if close_i < 0:
        raise ParseError("GetForwardDistanceBeforeGyroTurn() 的花括号不配对")
    out = out[:open_i + 1] + export_turn_gyro_chain(gyro_rows, eol) + out[close_i:]
    return out


def turn_rows_equal(a, b):
    """两串表项是否逐项相同（顺序 + 三元组 + 值）。"""
    a, b = a or [], b or []
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if (x.get("last"), x.get("now"), x.get("next")) != \
           (y.get("last"), y.get("now"), y.get("next")):
            return False
        if abs(float(x.get("dist", 0) or 0) - float(y.get("dist", 0) or 0)) > 1e-9:
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


# 左栏「转弯补偿」表的显示档（像「边显示」那样只显示一类；默认第一档 = 不显示全部）
TURN_LIST_MODES = ("只看要补偿的", "只看实测", "只看实测停车转", "只看吃默认",
                   "只看停车转", "只看陀螺转", "全部")
_TURN_DEFAULT_SRCS = ("Tier3 默认 19", "默认 0", "角度求不出（宏没定义）")


def turn_filter(rows, mode):
    """按显示档过滤 `turn_coverage()` 的行（纯函数，界面与自检共用）。

    ⚠️ 「只看吃默认」的口径 = 对话框第③页那个勾选框：默认 19 / 默认 0 / 角度求不出。
    """
    rows = rows or []
    if mode == "只看要补偿的":
        return [r for r in rows if r["branch"] != "straight"]
    if mode == "只看实测":
        return [r for r in rows if r["source"] in ("表1 实测", "表2 实测")]
    if mode == "只看实测停车转":
        return [r for r in rows if r["source"] == "表1 实测"]      # 仅表1 kTurnTbl（停车转）
    if mode == "只看吃默认":
        return [r for r in rows if r["source"] in _TURN_DEFAULT_SRCS]
    if mode == "只看停车转":
        return [r for r in rows if r["branch"] == "stop"]
    if mode == "只看陀螺转":
        return [r for r in rows if r["branch"] == "gyro"]
    return list(rows)                      # 「全部」或未知档 ⇒ 不过滤


def turn_table_status(model, rows, table, turn=None):
    """判断表里每一行在**当前地图**上到底会不会生效（画面上必须能看出来）。

    返回 [(status, detail)]，status ∈
      'ok'      会生效（三元组存在 且 分支正好落在本表）
      'branch'  死值：三元组存在，但当前地图走的是**另一个**分支
      'edge'    死值：边表里根本没有 last→now 或 now→next 这条边
      'unknown' 角度/长度求不出来（宏没定义等）
    """
    out = []
    for r in rows:
        last, now, nxt = r.get("last"), r.get("now"), r.get("next")
        ie = model.edge(last, now)
        oe = model.edge(now, nxt)
        if ie is None or oe is None:
            out.append(("edge", "边表里没有 %s→%s" % (last, now) if ie is None
                        else "边表里没有 %s→%s" % (now, nxt)))
            continue
        delta = need2turn(model.ang(ie), model.ang(oe))
        br = turn_branch(delta, ie.flag, ie.func)
        if br == "unknown":
            out.append(("unknown", "角度求不出来（宏没定义？）"))
        elif br != table:
            out.append(("branch", "当前走「%s」分支 ⇒ 本表不生效（%s）"
                        % (TURN_BRANCH_NAME.get(br, br),
                           "直行" if br == "straight" else "另一张表")))
        else:
            out.append(("ok", "Δ=%.1f°" % delta))
    return out


TURN_BRANCH_NAME = {"straight": "直行", "stop": "停车原地转", "gyro": "陀螺不停车转",
                    "unknown": "未知"}


def turn_coverage(model, turn=None):
    """枚举地图里所有 (入边, 出边) 转弯组合，算出**当前生效的补偿值**。

    与固件的对应关系：
      入边 = `nodes.nowNode`（`last→now` 那条边，flag/step/function 都取它）
      出边 = `nodes.nextNode`，Δ = need2turn(入边.angle, 出边.angle)
    返回 dict(rows=[...], stats={...})；每行：
      last/now/next/delta/branch/in_step/in_func/value/source/note
    ⚠️ 与固件一样，**补偿值只由三元组 + 入边属性决定**，与出边的 step 无关。
    """
    turn = turn if turn is not None else (getattr(model, "turn", None) or {})
    stop_rows = turn.get("stop") or []
    gyro_rows = turn.get("gyro") or []
    consts = dict(TURN_CONST_DEFAULTS)
    consts.update(turn.get("consts") or {})
    calc_on = bool(turn.get("calc_enable"))
    stop_map = {(r["last"], r["now"], r["next"]): r["dist"] for r in stop_rows}
    gyro_map = {(r["last"], r["now"], r["next"]): r["dist"] for r in gyro_rows}
    L = float(consts["TURN_L_PIVOT"])
    dvals = sorted({float(consts[k]) for k in
                    ("TURN_D_CRIGHT", "TURN_D_CLEFT", "TURN_D_DLEFT", "TURN_D_DEFAULT")})

    rows = []
    for now in model.names():
        ins = [e for e in model.edges if e.to == now]
        outs = [e for e in model.edges if e.frm == now]
        if not ins or not outs:
            continue
        for ie in ins:
            a_in = model.ang(ie)
            for oe in outs:
                delta = need2turn(a_in, model.ang(oe))
                br = turn_branch(delta, ie.flag, ie.func)
                row = {"last": ie.frm, "now": now, "next": oe.to, "delta": delta,
                       "branch": br, "in_step": model.step(ie), "in_func": ie.func,
                       "value": None, "source": "", "note": ""}
                if br == "unknown":
                    row["source"] = "角度求不出（宏没定义）"
                elif br == "straight":
                    row["source"] = "直行（不走补偿）"
                elif br == "stop":
                    key = (ie.frm, now, oe.to)
                    if key in stop_map:
                        row["value"] = stop_map[key]
                        row["source"] = "表1 实测"
                    elif (calc_on and ie.func in ("NONE", "DOOR")
                          and row["in_step"] is not None and row["in_step"] >= 20
                          and delta is not None and 100.0 <= abs(delta) < 178.0):
                        base = L * (1.0 - math.cos(math.radians(abs(delta))))
                        vals = sorted(round(base + d, 1) for d in dvals)
                        row["source"] = "Tier2 公式"
                        row["value"] = vals[0] if vals[0] == vals[-1] else None
                        row["note"] = ("判据 d∈[%.1f,%.1f] ⇒ 值 %.1f~%.1f"
                                       % (dvals[0], dvals[-1], vals[0], vals[-1]))
                    else:
                        row["value"] = TURN_STOP_DEFAULT
                        row["source"] = "Tier3 默认 19"
                else:                                   # gyro
                    key = (ie.frm, now, oe.to)
                    if key in gyro_map:
                        row["value"] = gyro_map[key]
                        row["source"] = "表2 实测"
                    else:
                        row["value"] = TURN_GYRO_DEFAULT
                        row["source"] = "默认 0"
                rows.append(row)

    def cnt(pred):
        return sum(1 for r in rows if pred(r))

    stats = {
        "total": len(rows),
        "straight": cnt(lambda r: r["branch"] == "straight"),
        "stop": cnt(lambda r: r["branch"] == "stop"),
        "gyro": cnt(lambda r: r["branch"] == "gyro"),
        "unknown": cnt(lambda r: r["branch"] == "unknown"),
        "stop_meas": cnt(lambda r: r["source"] == "表1 实测"),
        "stop_calc": cnt(lambda r: r["source"] == "Tier2 公式"),
        "stop_default": cnt(lambda r: r["source"] == "Tier3 默认 19"),
        "gyro_meas": cnt(lambda r: r["source"] == "表2 实测"),
        "gyro_default": cnt(lambda r: r["source"] == "默认 0"),
    }
    return {"rows": rows, "stats": stats}


def turn_coverage_text(cov):
    """把覆盖度统计写成给人看的一段话（对话框与自检共用）。"""
    s = cov["stats"]
    return ("地图里共有 %d 个 (入边,出边) 转弯组合：直行 %d / 停车转 %d / 陀螺转 %d%s。\n"
            "停车转里：表1 实测 %d、公式 Tier2 %d、吃默认 19 的有 %d 个。\n"
            "陀螺转里：表2 实测 %d、吃默认 0 的有 %d 个。"
            % (s["total"], s["straight"], s["stop"], s["gyro"],
               "、无法判定 %d" % s["unknown"] if s["unknown"] else "",
               s["stop_meas"], s["stop_calc"], s["stop_default"],
               s["gyro_meas"], s["gyro_default"]))


# ---------------------------------------------------------------- 数据模型

class Node:
    __slots__ = ("name", "comment", "index", "x", "y")

    def __init__(self, name, comment="", index=0, x=0.0, y=0.0):
        self.name = name
        self.comment = comment
        self.index = index          # 仅供显示；导出 enum 时按列表顺序重排
        self.x = float(x)
        self.y = float(y)

    @property
    def kind(self):
        return node_kind(self.name)

    def to_dict(self):
        return {"name": self.name, "comment": self.comment, "x": self.x, "y": self.y}

    @staticmethod
    def from_dict(d):
        return Node(d.get("name", "?"), d.get("comment", ""), 0,
                    d.get("x", 0.0), d.get("y", 0.0))


class Edge:
    __slots__ = ("frm", "to", "flag", "angle", "step", "speed", "func", "comment", "tag")

    def __init__(self, frm, to, flag="NO", angle="0", step="0", speed="SPEED0",
                 func="NONE", comment="", tag=None):
        self.frm = frm
        self.to = to
        self.flag = flag          # 文本（可含位或表达式）
        self.angle = angle        # 文本（可含 ANGLE_* 宏）
        self.step = step          # 文本（可含 LEN_*/DOOR_LEN_* 宏）
        self.speed = speed        # 文本（SPEED0..5 或数字）
        self.func = func
        self.comment = comment
        self.tag = tag            # 界面用的稳定 id

    def key(self):
        return (self.frm, self.to)

    def label(self):
        return "%s -> %s" % (self.frm, self.to)

    def to_dict(self):
        return {k: getattr(self, k) for k in
                ("frm", "to", "flag", "angle", "step", "speed", "func", "comment", "tag")}

    @staticmethod
    def from_dict(d):
        return Edge(d.get("frm"), d.get("to"), d.get("flag", "NO"), d.get("angle", "0"),
                    d.get("step", "0"), d.get("speed", "SPEED0"), d.get("func", "NONE"),
                    d.get("comment", ""), d.get("tag"))


# ---------------------------------------------------------------- 门 / 线索 / 宝物（镜像固件分支）
# 通行语义与 Mission/barrier.h 一致（与具体颜色解耦）：绿=能过、蓝=单相、黑=不能过。
CAN_PASS = 2        # 绿
ONE_WAY_PASS = 3    # 蓝
NO_PASS = 1         # 黑
DOOR_STATE_NAME = {CAN_PASS: "绿(能过)", ONE_WAY_PASS: "蓝(单相)",
                   NO_PASS: "黑(不能过)", 0: "未读"}
DOOR_STATE_ORDER = [CAN_PASS, ONE_WAY_PASS, NO_PASS, 0]
# door_pass[] 下标 -> 门名（barrier.c door() 的 DoorState）
DOOR_SLOT_NAME = ["D2", "D3", "D4", "D5"]

# 门区 8 条通行边：与 mission_planner.c 的 door_zone[8][2] / Clear_door() 是同一组
DOOR_ZONE = [("N5", "N12"), ("N12", "N5"), ("N5", "N8"), ("N8", "N5"),
             ("N3", "N8"), ("N8", "N3"), ("N3", "N20"), ("N20", "N3")]
# ⚠️ 上面只是**解析失败时的兜底**；运行时用 get_door_zone() 从 mission_planner.c 解析。
#
# ---------------------------------------------------------------- 门区状态表（barrier.c 触发链 / mission_planner.c door_zone，可解析可写回）
# 2026-10-17 起，BACK 门（回程过门）的触发边不再硬编码 N10→N3 / N8→N3：
# 从 barrier.c door() 开头的 if-else 链**解析**（固件改触发边，上位机自动跟上）；
# 解析失败回退 DOOR_TRIG_FALLBACK / DOOR_BACK_FALLBACK。
# 「🚧 门区状态表…」对话框（map_editor）可改触发边 / door_zone 并写回（自动备份）。
DOOR_TRIG_FALLBACK = [
    {"state": "DOOR_D2", "last": "N5", "now": "N12", "note": "看D2"},
    {"state": "DOOR_D3", "last": "N5", "now": "N8", "note": "看D3"},
    {"state": "DOOR_D4", "last": "N3", "now": "N8", "note": "看D4"},
    {"state": "DOOR_D4_BACK", "last": "N8", "now": "N3", "note": "回家过D4: N8→N3"},
    {"state": "DOOR_D5_BACK", "last": "N20", "now": "N3", "note": "回家过D5: N20→N3"},
]
DOOR_BACK_FALLBACK = {("N20", "N3"): (3, "DOOR_D5_BACK"),
                      ("N8", "N3"): (2, "DOOR_D4_BACK")}
_DOOR_TRIG_CACHE = None
_DOOR_SLOTS_CACHE = None
_DOOR_ZONE_CACHE = None


def _fw_path(*parts):
    """固件源文件路径（ROOT = 仓库根）。"""
    return os.path.join(ROOT, *parts)


def parse_door_triggers(path=None):
    """解析 barrier.c door() 的触发链 → ([{state,last,now,note}], warnings)。"""
    p = path or _fw_path("Mission", "barrier.c")
    warns = []
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except OSError as ex:
        return [], ["读不到 barrier.c：%s" % ex]
    out = []
    for m in re.finditer(
            r"nodes\.lastNode\.nodenum\s*==\s*(\w+)\s*&&\s*nodes\.nowNode\.nodenum"
            r"\s*==\s*(\w+)\s*\)\s*\{\s*state\s*=\s*(DOOR_\w+)\s*;\s*\}"
            r"(?:\s*/\*\s*(.*?)\s*\*/)?", txt):
        out.append({"state": m.group(3), "last": m.group(1),
                    "now": m.group(2), "note": (m.group(4) or "").strip()})
    if not out:
        warns.append("barrier.c 里没解析到 door() 触发链（格式变了？）")
    return out, warns


def door_triggers(force=False):
    """触发链（缓存）。返回 [{state,last,now,note}]；解析失败回退 DOOR_TRIG_FALLBACK。"""
    global _DOOR_TRIG_CACHE
    if force or _DOOR_TRIG_CACHE is None:
        trig, _w = parse_door_triggers()
        _DOOR_TRIG_CACHE = trig or [dict(x) for x in DOOR_TRIG_FALLBACK]
    return _DOOR_TRIG_CACHE


def parse_door_slots(path=None, force=False):
    """case DOOR_x 块内 `door_pass[i] = pass_state` ⇒ {state: i}（i = 门位下标）。"""
    global _DOOR_SLOTS_CACHE
    if path is None and not force and _DOOR_SLOTS_CACHE is not None:
        return _DOOR_SLOTS_CACHE
    p = path or _fw_path("Mission", "barrier.c")
    with open(p, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    out = {}
    for m in re.finditer(r"case\s+(DOOR_\w+)\s*:(.*?)break;", txt, re.S):
        mm = re.search(r"door_pass\[(\d+)\]\s*=\s*pass_state", m.group(2))
        if mm:
            out[m.group(1)] = int(mm.group(1))
    if path is None:
        _DOOR_SLOTS_CACHE = out
    return out


def parse_door_pass_edges(path=None):
    """每个 case 块里首个 door_set_pass_node(A, B, …) ⇒ {state: (A, B)}（过门动作的边）。"""
    p = path or _fw_path("Mission", "barrier.c")
    with open(p, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    out = {}
    for m in re.finditer(r"case\s+(DOOR_\w+)\s*:(.*?)break;", txt, re.S):
        mm = re.search(r"door_set_pass_node\(\s*(\w+)\s*,\s*(\w+)\s*,", m.group(2))
        if mm:
            out[m.group(1)] = (mm.group(1), mm.group(2))
    return out


def parse_door_retreats(path=None):
    """每个 case 块里首个 door_retreat(A, B, …) ⇒ {state: (A, B)}（读灯失败退回的边）。"""
    p = path or _fw_path("Mission", "barrier.c")
    with open(p, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    out = {}
    for m in re.finditer(r"case\s+(DOOR_\w+)\s*:(.*?)break;", txt, re.S):
        mm = re.search(r"door_retreat\(\s*(\w+)\s*,\s*(\w+)\s*,", m.group(2))
        if mm:
            out[m.group(1)] = (mm.group(1), mm.group(2))
    return out


def door_back_edges(force=False):
    """BACK 门（回程过门）触发边 {(last,now): (door_pass 位, state)}。

    回程路线识别「这条边要读哪盏门灯」都用它，**别再硬编码边对**
    （2026-10-17 D5 从 N10→N3 挪到 N20→N3 就是这么跟上的）。
    """
    out = {}
    slots = parse_door_slots(force=force)
    for t in door_triggers(force=force):
        if t["state"].endswith("_BACK"):
            out[(t["last"], t["now"])] = (slots.get(t["state"], 3), t["state"])
    return out or dict(DOOR_BACK_FALLBACK)


def door_back_slot_edge(slot, force=False):
    """door_pass 位 → BACK 门触发边 (last,now)；没有返回 None。"""
    for edge, (s, _st) in door_back_edges(force=force).items():
        if s == slot:
            return edge
    return None


def set_door_trigger(state, last, now, path=None, backup_dir=None):
    """把 barrier.c 触发链里 state 的 (last,now) 改成新值（保缩进/行尾注释，字节级替换）。

    返回 (ok, msg)。backup_dir 给定时先落 barrier.c.<时间戳>.bak（原字节）。
    """
    p = path or _fw_path("Mission", "barrier.c")
    with open(p, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as ex:
        return False, "barrier.c 不是 UTF-8：%s" % ex
    pat = re.compile(
        r"(nodes\.lastNode\.nodenum\s*==\s*)(\w+)"
        r"(\s*&&\s*nodes\.nowNode\.nodenum\s*==\s*)(\w+)"
        r"(\s*\)\s*\{\s*state\s*=\s*" + re.escape(state) + r"\s*;\s*\})")
    hits = pat.findall(text)
    if len(hits) != 1:
        return False, "触发链里 %s 匹配到 %d 处（应为 1），未改动" % (state, len(hits))
    new_text = pat.sub(lambda m: "%s%s%s%s%s" % (
        m.group(1), last, m.group(3), now, m.group(5)), text, count=1)
    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(backup_dir, "barrier.c.%s.bak" % stamp), "wb") as f:
            f.write(raw)          # 备份保持原字节
    with open(p, "wb") as f:
        f.write(new_text.encode("utf-8"))
    global _DOOR_TRIG_CACHE
    _DOOR_TRIG_CACHE = None
    return True, "%s 触发边改为 %s→%s" % (state, last, now)


def parse_door_zone(path=None):
    """解析 mission_planner.c 的 door_zone[8][2] → ([(a, b)], warnings)。"""
    p = path or _fw_path("Mission", "mission_planner.c")
    warns = []
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except OSError as ex:
        return [], ["读不到 mission_planner.c：%s" % ex]
    m = re.search(r"door_zone\s*\[\s*\d+\s*\]\s*\[\s*\d+\s*\]\s*=\s*\{(.*?)\}\s*;",
                  txt, re.S)
    if not m:
        return [], ["mission_planner.c 里没解析到 door_zone[8][2]"]
    pairs = re.findall(r"\{\s*(\w+)\s*,\s*(\w+)\s*\}", m.group(1))
    return [(a, b) for a, b in pairs], warns


def get_door_zone(force=False):
    """门区禁用边（door_zone[8][2] 的镜像，缓存）；解析失败回退 DOOR_ZONE 常量。"""
    global _DOOR_ZONE_CACHE
    if force or _DOOR_ZONE_CACHE is None:
        pairs, _w = parse_door_zone()
        _DOOR_ZONE_CACHE = pairs or list(DOOR_ZONE)
    return _DOOR_ZONE_CACHE


def set_door_zone_pair(old, new, path=None, backup_dir=None):
    """把 door_zone[8][2] 里的一对 (a,b) 换成 (c,d)。返回 (ok, msg)。"""
    p = path or _fw_path("Mission", "mission_planner.c")
    with open(p, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    pat = re.compile(r"\{\s*" + re.escape(old[0]) + r"\s*,\s*" + re.escape(old[1])
                     + r"\s*\}")
    hits = pat.findall(text)
    if len(hits) != 1:
        return False, "door_zone 里 %s→%s 匹配到 %d 处（应为 1），未改动" % (
            old[0], old[1], len(hits))
    new_text = pat.sub("{%s, %s}" % (new[0], new[1]), text, count=1)
    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(backup_dir, "mission_planner.c.%s.bak" % stamp), "wb") as f:
            f.write(raw)
    with open(p, "wb") as f:
        f.write(new_text.encode("utf-8"))
    global _DOOR_ZONE_CACHE
    _DOOR_ZONE_CACHE = None
    return True, "door_zone 里 %s→%s 改为 %s→%s" % (old[0], old[1], new[0], new[1])

# 宝物编号 -> 回程前要绕去取的平台（5/6 在东区已取过，见 plan_treasure_return）
TREASURE_PF = {2: "P1", 3: "P3", 4: "P4", 5: "P5", 6: "P6"}

# ---------------------------------------------------------------- 第二轮巡游顺序（config.h 可读写）
# 固件 get_newroute() 的巡游段顺序**不再写死在 mission_planner.c**，而是读 config.h 的
# 8 个宏（CW = 宝物!=6 / CCW = 宝物==6）；上位机「二轮路线…」可读源码 + 写回。
ROUND2_CRUISE_PF = ("P5", "P6", "P7", "P8")          # 东区 4 个巡游平台
ROUND2_CW_MACROS = ("ROUND2_CRUISE_CW_1", "ROUND2_CRUISE_CW_2",
                    "ROUND2_CRUISE_CW_3", "ROUND2_CRUISE_CW_4")
ROUND2_CCW_MACROS = ("ROUND2_CRUISE_CCW_1", "ROUND2_CRUISE_CCW_2",
                     "ROUND2_CRUISE_CCW_3", "ROUND2_CRUISE_CCW_4")
ROUND2_CW_DEFAULT = ("P5", "P7", "P8", "P6")          # 出厂/缺宏时的顺时针（宝物 != 6）
ROUND2_CCW_DEFAULT = ("P6", "P8", "P7", "P5")         # 出厂/缺宏时的逆时针（宝物 == 6）


def round2_cruise_defaults():
    """出厂（config.h 缺宏时）的两组巡游顺序。"""
    return {"cw": list(ROUND2_CW_DEFAULT), "ccw": list(ROUND2_CCW_DEFAULT),
            "warnings": []}


def parse_round2_cruise(path=None, source_text=None):
    """从 `Mission/config.h` 读第二轮巡游顺序（ROUND2_CRUISE_CW_* / _CCW_*）。

    返回 {"cw": [4 平台名], "ccw": [4 平台名], "warnings": [str]}。
    ⚠️ 缺宏 / 值不是平台名 / 组内有重复 ⇒ 记 warning 并**整组退回出厂默认**（不抛异常，
       因为是只读展示 + 写回前预览；真出错时用户能看见 warnings）。
    """
    out = round2_cruise_defaults()
    try:
        macros, _field = parse_config_macros(path or PATH_CONFIG, source_text)
    except Exception as ex:                                        # noqa: BLE001
        out["warnings"].append("读取 config.h 失败：%s" % ex)
        return out
    for key, names, dflt in (("cw", ROUND2_CW_MACROS, ROUND2_CW_DEFAULT),
                             ("ccw", ROUND2_CCW_MACROS, ROUND2_CCW_DEFAULT)):
        vals, ok = [], True
        for i, mac in enumerate(names):
            v = macros.get(mac)
            if v is None:
                out["warnings"].append("config.h 里没有 %s ⇒ 该组用出厂默认 %s"
                                       % (mac, "→".join(dflt)))
                ok = False
                break
            v = str(v).strip()
            if v not in ROUND2_CRUISE_PF:
                out["warnings"].append("%s = %r 不是平台名（只认 %s）⇒ 该组用出厂默认"
                                       % (mac, v, "/".join(ROUND2_CRUISE_PF)))
                ok = False
                break
            vals.append(v)
        if ok and len(set(vals)) != len(ROUND2_CRUISE_PF):
            out["warnings"].append("%s 组里 4 个平台有重复（%s）⇒ 该组用出厂默认"
                                   % (key.upper(), "→".join(vals)))
            ok = False
        if ok:
            out[key] = vals
    return out


def _rewrite_define_value(src, name, value):
    """把 `#define name <value>` 的 value 换掉，**保留行尾注释**。返回 (新源码, 替换处数)。

    与 `map_editor.App._rewrite_config_macro` 同一套正则（那边是实例方法，这里做成纯函数
    便于自检干跑）。⚠️ 中间那段必须是非贪婪且**把行尾注释单独成组**，否则
    `#define X  1 /* 说明…` 会把注释一起吃掉、留下孤立 `*/`（2026-09-15 编挂整份工程）。
    """
    pattern = re.compile(r"^(\s*#define\s+" + re.escape(name) + r"\s+)" +
                         r"([^\r\n]*?)" +
                         r"([ \t]*(?:/\*|//)[^\r\n]*)?" +
                         r"(\r?\n|$)", re.M)
    return pattern.subn(lambda m: m.group(1) + value + (m.group(3) or "") + m.group(4),
                        src, count=1)


def splice_round2_cruise(src, cw, ccw):
    """把两组巡游顺序写回 config.h 源码（**纯函数**，不落盘，便于自检干跑）。

    只改 ROUND2_CRUISE_CW_* / _CCW_* 这 8 个 `#define` 的值（其余一字不动，行尾注释原样保留）。
    返回 (新源码, 替换处数)。值为平台名文本（如 `P5`）。
    """
    cw, ccw = list(cw or []), list(ccw or [])
    if len(cw) != 4 or len(ccw) != 4:
        raise ParseError("两组巡游顺序各需 4 个平台，收到 cw=%r ccw=%r" % (cw, ccw))
    for grp in (cw, ccw):
        if sorted(grp) != sorted(ROUND2_CRUISE_PF):
            raise ParseError("巡游组必须是 %s 各一次，收到 %r" % ("/".join(ROUND2_CRUISE_PF), grp))
    total = 0
    for names, vals in ((ROUND2_CW_MACROS, cw), (ROUND2_CCW_MACROS, ccw)):
        for mac, val in zip(names, vals):
            src, n = _rewrite_define_value(src, mac, val)
            total += n
    return src, total


def can_pass(state):
    """镜像 Can_Pass()：绿或蓝都算可通行。"""
    return state == CAN_PASS or state == ONE_WAY_PASS


def p1_route(clue):
    """镜像 Mission/mission_planner.c:update_route_at_P1()（手写数组，不走规划器）。

    返回 route[] 内容（不含起点 N2，0xFF 由调用方补）；clue 不在 {0,3,4} 时固件不改路线，返回 None。
    """
    if clue == 3:
        return ["B1", "N1", "P1", "N1", "B2", "N4", "N3", "P3", "N3", "N4", "N5", "N12"]
    if clue == 4:
        return ["B1", "N1", "P1", "N1", "B2", "N4", "N5", "N6", "P4", "N6", "N5", "N12"]
    if clue == 0:
        return ["B1", "N1", "P1", "N1", "B2", "N4", "N5", "N12"]
    return None


def stageab_waypoints(enter_node, clue_a, clue_b):
    """镜像 update_route_at_door_for_stageAB()：wp = {当前节点, 平台A, 平台B}。"""
    if (clue_a, clue_b) not in ((5, 7), (5, 8), (6, 7), (6, 8)):
        return None, "平台 A/B 线索组合固件会 CarBrake_Stop（只支持 5/6 × 7/8）"
    return [enter_node, "P%d" % clue_a, "P%d" % clue_b], None


def stageab_enter_node(doors):
    """过门后 nodes.nowNode 落在哪：镜像 barrier.c:door() 把 door_set_pass_node() 的返回值
    赋给 nodes.nowNode —— D2 能过 → N12；否则退回 N5→N8 读 D3、再退到 N3→N8 读 D4，最终都落在 N8。
    三种灯全不能过时固件 CarBrake_Stop，返回 None。"""
    if can_pass(doors[0]):
        return "N12"
    if can_pass(doors[1]) or can_pass(doors[2]):
        return "N8"
    return None


# door() 里"去撞下一扇门"用的手写字面数组（mission_planner.c: door1route）
DOOR1ROUTE = ["N3", "N8"]


def door_read_flow(doors):
    """镜像 barrier.c:door() 的【进门读灯推进】：D2 → (退回) → D3 → (退回) → D4。

    返回 (steps, enter_node, err)：
      steps = [(门, 读灯的边, 灯状态, 判定, 动作/手写路线)]，只含**实际会被读到**的门；
      enter_node = 过门后 nodes.nowNode 落在哪（N12 / N8）；没过成则 None；
      err = None 或固件会停车的原因。

    ⚠️ 这里出现的路线全部写在 door() 内部，不经过规划器 —— 上位机以前完全不显示它们。
    """
    d2, d3, d4 = doors[0], doors[1], doors[2]
    steps = []
    # --- D2：车走到 N5->N12 这条 DOOR 边上读灯 ---
    if can_pass(d2):
        steps.append(("D2", "N5→N12", d2, "能过 → 过门",
                      "door_set_pass_node(N5,N12) 后赋给 nodes.nowNode ⇒ 过门落在 N12"
                      + ("（并放行 N12→N5）" if d2 == CAN_PASS else "（蓝=单相，不放行 N12→N5）")))
        return steps, "N12", None
    steps.append(("D2", "N5→N12", d2, "不能过 → 退回重读",
                  "door_retreat(N5,N8) 后退 DOOR_RETREAT_N5N8 ⇒ nowNode 变成 N5→N8，"
                  "开到 N8 在 N5→N8 上读 D3"))
    # --- D3：车走到 N5->N8 读灯 ---
    if can_pass(d3):
        steps.append(("D3", "N5→N8", d3, "能过 → 过门",
                      "door_set_pass_node(N5,N8) 后赋给 nodes.nowNode ⇒ 过门落在 N8"
                      + ("（并放行 N8→N5）" if d3 == CAN_PASS else "（蓝=单相，不放行 N8→N5）")))
        return steps, "N8", None
    steps.append(("D3", "N5→N8", d3, "不能过 → 退回重读",
                  "door_retreat(N5,N4) 后退 DOOR_RETREAT_N5N4，并 load_route_at(0, door1route) "
                  "⇒ route[] = {N3, N8}（door() 内部手写）⇒ 车由 N5→N4→N3→N8，"
                  "在 N3→N8 上读 D4"))
    # --- D4：车走到 N3->N8 读灯 ---
    if can_pass(d4):
        steps.append(("D4", "N3→N8", d4, "能过 → 过门",
                      "door_set_pass_node(N3,N8) 后赋给 nodes.nowNode ⇒ 过门落在 N8"
                      + ("；绿额外放行 N8→N3" if d4 == CAN_PASS
                         else "；蓝额外预设 %s→%s（回程走 D5）"
                              % (door_back_slot_edge(3) or ("N20", "N3")))))
        return steps, "N8", None
    steps.append(("D4", "N3→N8", d4, "不能过 → 死停",
                  "barrier.c:door() 的 DOOR_D4 分支直接 CarBrake_Stop()（不返回）"))
    return steps, None, "D2/D3/D4 全不能过 → 固件 CarBrake_Stop()，走不下去"


def door_read_names(doors):
    """进门读灯时**真的会被读到**的门名集合。

    门是按边顺序读的（N5→N12 读 D2、N5→N8 读 D3、N3→N8 读 D4）。D2 能过就直接落 N12，
    N5→N8 这条边根本不会走 ⇒ **D3 读不到**，固件里 door_pass[1] 一直是初值 0。
    """
    steps, _enter, _err = door_read_flow(doors)
    return {s[0] for s in steps}


def doors_known_only(doors, known):
    """把 `known` 之外的门置 0（= 固件 door_pass[] 初值，**未读 ≠ 黑灯**）。

    固件的梯子（plan_treasure_return / get_newroute）把 0 当"非绿非黑"处理，
    跟"设成黑"是两种不同结果 —— 所以不能让对话框里填的值直接进梯子。
    """
    out = list(doors)
    for i, name in enumerate(DOOR_SLOT_NAME):
        if i < len(out) and name not in known:
            out[i] = 0
    return out


def door_back_flow(doors):
    """镜像 barrier.c:door() 的【回家路上过门】两个 BACK 分支（触发边从 barrier.c 解析）。

    返回 (steps, hazards)：steps=[(门, 读灯的边, 灯状态, 判定, 动作)]；
    hazards=[提示文本]，例如"这个灯组合在 door() 里没有匹配分支"、
    "触发边已改但退回分支还是旧边（D5 挪位后要重新设计退回策略）"。
    """
    d2, d3, d4, d5 = doors[0], doors[1], doors[2], doors[3]
    steps, hazards = [], []

    e5 = door_back_slot_edge(3) or ("N20", "N3")
    e4 = door_back_slot_edge(2) or ("N8", "N3")
    pe = parse_door_pass_edges()
    p5 = pe.get("DOOR_D5_BACK") or e5
    rt = parse_door_retreats()
    r5 = rt.get("DOOR_D5_BACK") or ("N10", "N8")
    r4 = rt.get("DOOR_D4_BACK") or ("N8", "N5")
    t5 = "%s→%s" % e5
    t4 = "%s→%s" % e4

    # ---------- DOOR_D5_BACK（触发边 = t5）----------
    if d5 == CAN_PASS:
        steps.append(("D5", t5, d5, "绿 → 过门",
                      "door_set_pass_node(%s,%s, DOOR_LEN_%s%s)（step=36, SPEED3），"
                      "nowNode 落在 %s ⇒ update_route_by_door_1() = "
                      "route_return_home(起点 %s, 门区 8 边全禁)"
                      % (p5[0], p5[1], p5[0], p5[1], e5[1], e5[1])))
    elif d2 == ONE_WAY_PASS:
        steps.append(("D5", t5, d5, "非绿（else 分支；D2 是蓝、单相已用尽）→ 退回重读",
                      "route[0]=N3; route[1]=0xFF（door() 内部手写）+ door_retreat(%s,%s) "
                      "⇒ nowNode 变成 %s→%s ⇒ 车由 %s→%s 在 %s→%s 上重读 D4"
                      % (r5[0], r5[1], r5[0], r5[1], r5[1], e5[1], r5[1], e5[1])))
    elif d2 == NO_PASS and d3 == ONE_WAY_PASS:
        steps.append(("D5", t5, d5, "非绿（else 分支；D2 黑、D3 蓝已用尽）→ 退回",
                      "door_retreat(%s,%s) + 放行 N3↔N8 ⇒ update_route_by_door_2() "
                      "= route_return_home(起点 %s, 额外放行 %s→%s)"
                      % (r5[0], r5[1], r5[1], r5[1], e5[1])))
    else:
        steps.append(("D5", t5, d5, "非绿 → ⚠ door() 里没有匹配分支", "什么都不做"))
        hazards.append("D5 非绿时 door() 只处理「D2=蓝」或「D2=黑且 D3=蓝」两种组合；"
                       "当前组合两边都不满足 ⇒ 不置 cross_event、不改 route[] "
                       "⇒ Navigation() 会重跑同一段并再次触发 door()，**可能反复重读这扇门**。")

    # 触发边改了、退回分支没跟 ⇒ 黑/蓝灯时车会按旧几何倒车/转向（2026-10-17 D5 挪位实况）
    if r5[0] != e5[0]:
        hazards.append("⚠ D5_BACK 触发边是 %s→%s，但读灯失败的退回分支还是 "
                       "door_retreat(%s,%s) —— D5 挪位后，黑/蓝灯的退回策略要重新设计"
                       "（door_retreat 会按旧几何倒车再转向，车会走错）。"
                       % (e5[0], e5[1], r5[0], r5[1]))

    # ---------- DOOR_D4_BACK（触发边 = t4）----------
    if d4 == CAN_PASS:
        steps.append(("D4(回程)", t4, d4, "绿 → 过门",
                      "放行 %s↔%s；nowNode = %s→%s（step=36, SPEED3, function=NONE）+ "
                      "motor_pid_clear() ⇒ update_route_by_door_3() = "
                      "route_return_home(起点 %s)"
                      % (e4[1], e4[0], e4[0], e4[1], e4[1])))
    else:
        steps.append(("D4(回程)", t4, d4, "非绿（else 分支：黑/蓝）→ 退回",
                      "先放行 %s↔%s（必须！否则 retreat 读到旧值会二次触发 door()）+ "
                      "door_retreat(%s,%s) ⇒ update_route_by_door_4() "
                      "= route_return_home(起点 %s)"
                      % (r4[0], r4[1], r4[0], r4[1], r4[1])))
    return steps, hazards

def door_read_hops(doors):
    """进门读灯时，**退回重读那一段真正开过的节点**（全部是边表里的真实边）。

    ⚠️ 物理事实（barrier.c: DOOR_D2 → NO_PASS → door_retreat(N5,N8,DOOR_RETREAT_N5N8)）：
    车沿 P1 手写数组开到**N5→N12 这条 DOOR 边的中点**（step = DOOR_LEN_N5N12/2）就停下读 D2，
    **从来没真正到过 N12**；读出黑就 `Chassis_DriveDistance_Blocking(-SPEED2)` 倒车 63cm 退回 N5 一侧，
    转身面向 N5→N8，再沿 **N5→N8** 去读 D3。所以"退回去"的真实路径是 **N5→N8**，不是 N12→N8。
    （旧实现为了让 hops 能直接接在 P1 数组末尾的 N12 后面，用 N12→N8 近似 ——
      图上就会凭空多画一条车没走过的 N12→N8 斜线，而真正的 N5→N8 反而没画出来。）

    返回 (hops, enter_node, err)，**hops 不含 N5**（调用方已经站在 N5 上，直接接即可）：
      D2 能过→ []                                  （过门落在 N12）
      D2 黑、D3 能过        → ["N8"]（N5→N8 读 D3）
      D2 黑、D3 黑、D4 能过  → ["N8","N5","N4","N3","N8"]
                             （N5→N8 读 D3 → 退 N5 → door1route={N3,N8} 走 N5→N4→N3→N8 读 D4）
      D2/D3/D4 全不能过 → 固件 CarBrake_Stop()
    """
    d2, d3, d4 = doors[0], doors[1], doors[2]
    if can_pass(d2):
        return [], "N12", None
    if can_pass(d3):
        return ["N8"], "N8", None
    if can_pass(d4):
        return ["N8", "N5", "N4", "N3", "N8"], "N8", None
    return [], None, "D2/D3/D4 全不能过 → 固件 barrier.c:door() 会 CarBrake_Stop()"


def door_read_dim_edges(doors):
    """门区里"只开半程去读灯、没真正走过去"的边，供界面画成淡色（不进 self.route）。

    D2 的灯装在 N5→N12 这条边的中点（DOOR_LEN_N5N12/2）：D2 能过时车**确实**开过去了，
    那时 N5→N12 就是主线的一部分，不需要单独画；只有 **D2 不能过**时，车开到中点读完就得倒车退回，
    这一趟是"探灯"而不是"过门"，画成淡色才不会和真正的路线混淆。
    同理 D3 黑时，N5→N8 也只是"开到中点读 D3"（读完还要退 N5 走 door1route）⇒ 同样淡色。

    返回 [(from, to)]，画布上按这些边补淡色虚线。
    """
    d2, d3, d4 = doors[0], doors[1], doors[2]
    out = []
    if not can_pass(d2):
        out.append(("N5", "N12"))        # 开到 D2 门中点读灯，读不到 → 倒车退回
    if not can_pass(d2) and not can_pass(d3):
        out.append(("N5", "N8"))         # 开到 D3 门中点读灯，读不到 → 还要退 N5 走 door1route
    return out


def door_back_chain(doors, door_edge):
    """回程在 `door_edge` 上撞到 BACK 门时，镜像 door() 的 BACK 分支。

    door_edge 必须是触发链里的 BACK 边（见 door_back_edges()；2026-10-17 起
    **不再硬编码 N10→N3 / N8→N3** —— D5 已挪到 N20→N3，触发边跟着 barrier.c 走）。
    返回 (hops, start, allow, note)：
      hops  = 走 route_return_home 之前还要经过的节点（如退回 N8 后由 N8→N3 重读 D4）；
      start/allow 交给 door_return_home_waypoints()。
    ⚠️ 两个 BACK 分支的 else 是**"非绿"**（黑和蓝都走），不是只有黑。
    """
    d2, d3, d4, d5 = doors[0], doors[1], doors[2], doors[3]
    be = door_back_edges().get(tuple(door_edge))
    slot = be[0] if be else 3
    land = door_edge[1]                     # 过门后落在的节点 = 触发边终点
    r5 = parse_door_retreats().get("DOOR_D5_BACK") or ("N10", "N8")
    back_n = r5[1]                          # D5 读灯失败退回到的节点（现仍 N8，待重设计）
    if slot == 3:                           # ---- D5_BACK ----
        if d5 == CAN_PASS:
            return [], land, False, "D5 绿 ⇒ update_route_by_door_1()（起点 %s）" % land
        if d2 == ONE_WAY_PASS:
            # route[0]=land; route[1]=0xFF ⇒ 退回 back_n，再由 back_n→land 重读 D4（D4_BACK）
            if d4 == CAN_PASS:
                return ([back_n, land], land, False,
                        "D5 非绿 + D2 蓝 ⇒ route[0]=%s、退回 %s ⇒ %s→%s 重读 D4 得绿 ⇒ "
                        "update_route_by_door_3()（起点 %s）"
                        % (land, back_n, back_n, land, land))
            return ([back_n, land, "N5"], "N5", False,
                    "D5 非绿 + D2 蓝 ⇒ route[0]=%s、退回 %s ⇒ %s→%s 重读 D4 非绿 ⇒ "
                    "退回 N5 ⇒ update_route_by_door_4()（起点 N5）"
                    % (land, back_n, back_n, land))
        if d2 == NO_PASS and d3 == ONE_WAY_PASS:
            return ([], back_n, True,
                    "D5 非绿 + D2 黑 + D3 蓝 ⇒ 退回 %s ⇒ update_route_by_door_2()"
                    "（起点 %s，放行 %s→%s）" % (back_n, back_n, back_n, land))
        return ([], land, False,
                "⚠ D5 非绿且 D2/D3 组合在 door() 里没有匹配分支（不置 cross_event，"
                "可能反复重读这扇门）——下面按 D5 绿的结果占位，仅作示意")
    # ---- D4_BACK ----
    if d4 == CAN_PASS:
        return [], land, False, "D4 回程绿 ⇒ update_route_by_door_3()（起点 %s）" % land
    return (["N5"], "N5", False,
            "D4 回程非绿 ⇒ 放行 N8↔N5、退回 N5 ⇒ update_route_by_door_4()（起点 N5）")

def p3p4_punch_waypoints(treasure, line_clue):
    """镜像 mission_planner.c 的 `P3P4_PUNCH_ENABLE` 段：一轮回程要"补打卡"的平台。

    **缺哪个补哪个**：QR 百位 = 3 ⇒ 去程已去过 P3、= 4 ⇒ 已去过 P4、
    0 / None ⇒ 两个都没去；宝物平台正好是它时也不重复加（回程本来就要去那儿打卡）。
    顺序固定 P3 -> P4。返回平台名列表（可能为空）。
    """
    out = []
    if line_clue != 3 and treasure != 3:
        out.append("P3")
    if line_clue != 4 and treasure != 4:
        out.append("P4")
    return out


def upright_tour_waypoints(treasure, line_clue=None, punch=False):
    """镜像 mission_planner.c 一轮回程的 `UPRIGHT_TOUR_ENABLE`：这次回程**【会绕哪些直立景点】**。

    判据（2026-10-07 改）：**跟着"这次回程会不会去 P3/P4"走**，不再只看宝物值 ——
      会去 P3 ⇒ 绕 S1；会去 P4 ⇒ 绕 S2。其中
        "会去 P3" = 宝物平台就是 P3，或 补打卡（punch）开着且 QR 百位没走过 P3。
      ⇒ punch 开着时两个景点都绕（3/4 都去）；punch 关则退回旧行为（宝物 P3→S1、P4→S2）。
    返回 ["S1"] / ["S2"] / ["S1","S2"] / []（S1 恒在 S2 之前，与 P3->S1->P4->S2 同序）。
    ⚠️ S1/S2 的进边 `func` 是 `View1`、`map_function()` 里没有 `case View1`
       ⇒ **只走位、不做动作、不得分**。
    ⚠️ 二轮"固定两个都绕"由 round2_waypoints() 自己插，不走本函数。
    """
    go_p3 = (treasure == 3) or (punch and line_clue != 3 and treasure != 3)
    go_p4 = (treasure == 4) or (punch and line_clue != 4 and treasure != 4)
    out = []
    if go_p3:
        out.append("S1")
    if go_p4:
        out.append("S2")
    return out


# ================= 比赛时间预算（出门 / 取宝后 分级贪分）=================
# 与固件 Mission/mission_planner.c 的 round1_tail_tier_of() 一一对应（2026-10-12）。
# 阈值**读 Mission/config.h**（读不到才用下面的默认），避免这里硬编码与固件漂移。
TB_MACROS = ("TB_NO_SIGHTS_AT_S", "TB_ONE_PLAT_AT_S", "TB_HOME_ONLY_AT_S",
             "TB_P1_NO_SIGHTS_AT_S", "TB_P1_HOME_ONLY_AT_S")
TB_FALLBACK = {"TB_NO_SIGHTS_AT_S": 145, "TB_ONE_PLAT_AT_S": 155,
               "TB_HOME_ONLY_AT_S": 160,
               "TB_P1_NO_SIGHTS_AT_S": 135, "TB_P1_HOME_ONLY_AT_S": 145}
TIER_NAME = {0: "全跑", 1: "不跑 S1/S2（只补平台）", 2: "只跑一个平台", 3: "直接回家"}


def mmss(sec):
    """秒 → 「2:25」这种写法（报告用）。"""
    s = int(sec)
    return "%d:%02d" % (s // 60, s % 60)


def time_budget_macros(cfg=None):
    """5 个时间预算宏 → dict[str,int]。cfg = parse_config_macros()[0]，None 就现读。"""
    src = cfg
    if src is None:
        try:
            src, _f = parse_config_macros()
        except Exception:
            src = {}
    out = dict(TB_FALLBACK)
    for k in TB_MACROS:
        try:
            v = int(str((src or {}).get(k)).strip())
            if v > 0:
                out[k] = v
        except (TypeError, ValueError):
            pass
    return out


def time_budget_enabled(cfg=None):
    """镜像 config.h 的 TIME_BUDGET_ENABLE（=0 时固件不裁剪、也不算时）。"""
    src = cfg
    if src is None:
        try:
            src, _f = parse_config_macros()
        except Exception:
            return True
    return str((src or {}).get("TIME_BUDGET_ENABLE", "1")).strip() == "1"


def round1_tail_tier(treasure, elapsed_s, tb=None):
    """镜像 mission_planner.c:round1_tail_tier_of()。返回 (tier, 说明)。

    tier：0=全跑 / 1=仅平台（不跑 S1/S2）/ 2=只跑一个平台 / 3=直接回家。
    ⚠️ 两套阈值（2026-10-12 用户口径）：
      宝物=P1(2)：< TB_P1_NO_SIGHTS 全跑；该值~TB_P1_HOME_ONLY 仅 P3、P4；≥ 直接回家。
      其余宝物  ：通用 TB_NO_SIGHTS / TB_ONE_PLAT / TB_HOME_ONLY 三档。
    elapsed_s=None ⇒ 不裁剪（= 固件 TIME_BUDGET_ENABLE=0 或计时器没启动）。
    """
    tb = tb or time_budget_macros()
    if elapsed_s is None:
        return 0, "未启用时间裁剪（elapsed_s=None）"
    if treasure == 2:
        p, q = tb["TB_P1_NO_SIGHTS_AT_S"], tb["TB_P1_HOME_ONLY_AT_S"]
        if elapsed_s < p:
            return 0, "宝物=P1：< %s 全跑" % mmss(p)
        if elapsed_s < q:
            return 1, "宝物=P1：%s~%s 仅 P3、P4" % (mmss(p), mmss(q))
        return 3, "宝物=P1：≥ %s 直接回家" % mmss(q)
    a, b, c = tb["TB_NO_SIGHTS_AT_S"], tb["TB_ONE_PLAT_AT_S"], tb["TB_HOME_ONLY_AT_S"]
    if elapsed_s < a:
        return 0, "< %s 全跑" % mmss(a)
    if elapsed_s < b:
        return 1, "%s~%s 不跑 S1/S2" % (mmss(a), mmss(b))
    if elapsed_s < c:
        return 2, "%s~%s 只跑一个平台" % (mmss(b), mmss(c))
    return 3, "≥ %s 直接回家" % mmss(c)


def round1_tail_ladder(treasure, tb=None):
    """该宝物值下的「档位阶梯」：[(时间范围文本, tier, 该档做什么)]（供报告/对话框列出）。"""
    tb = tb or time_budget_macros()
    if treasure == 2:
        p, q = tb["TB_P1_NO_SIGHTS_AT_S"], tb["TB_P1_HOME_ONLY_AT_S"]
        return [("< %s" % mmss(p), 0, "全跑：P3、P4 + S1、S2"),
                ("%s ~ %s" % (mmss(p), mmss(q)), 1, "仅 P3、P4（两个平台必去，不跑 S1/S2）"),
                ("≥ %s" % mmss(q), 3, "直接回家")]
    a, b, c = tb["TB_NO_SIGHTS_AT_S"], tb["TB_ONE_PLAT_AT_S"], tb["TB_HOME_ONLY_AT_S"]
    return [("< %s" % mmss(a), 0, "全跑：P3、P4 + S1、S2"),
            ("%s ~ %s" % (mmss(a), mmss(b)), 1, "不跑 S1/S2（只补平台）"),
            ("%s ~ %s" % (mmss(b), mmss(c)), 2, "只跑一个平台"),
            ("≥ %s" % mmss(c), 3, "直接回家")]


def round1_tail_plan(treasure, line_clue, punch=False, tour=False,
                     elapsed_s=None, exit_node=None, tb=None, tier=None):
    """一轮【宝物平台 / 出门点之后、P2 之前】的尾段。返回 (wp, info)。

    info = {"tier","tier_name","trigger","exit_n3","reason","tb"}。
    ⚠️ **定档点**（固件 round1_exit_recheck() 的两个触发点，2026-10-12）：
      宝物=P1 → 在 P1 平台【取完宝那一刻】（barrier.c 的 Stage() 调它）；
                此时出门节点无意义，exit_n3 恒传 1（P1 之后先西 P3、再东 P4）。
      其余宝物 → 回程到达四条出门边（N10→N3 / N8→N3 / N12→N5 / N8→N5）那一刻。
    tier 传了就直接用（给「档位阶梯」逐档取 wp）；返回的 wp **不含宝物平台本身**。
    """
    tb = tb or time_budget_macros()
    if tier is None:
        tier, reason = round1_tail_tier(treasure, elapsed_s, tb)
    else:
        reason = "（指定档位）"
    if treasure == 2:
        trigger = "在 P1 取完宝那一刻"
        exit_n3 = True
    else:
        trigger = "回程到达出门边（N3/N5）那一刻"
        exit_n3 = (exit_node == "N3")

    punch_list = p3p4_punch_waypoints(treasure, line_clue) if punch else []
    tours = upright_tour_waypoints(treasure, line_clue, punch) if tour else []
    out = []
    if tier == 3:                      # 直接回家
        pass
    elif tier == 2:                    # 只跑一个平台：出门 N3 选 P3，其余选 P4
        if exit_n3:
            if "P3" in punch_list:
                out.append("P3")
            elif "P4" in punch_list:
                out.append("P4")
        else:
            if "P4" in punch_list:
                out.append("P4")
            elif "P3" in punch_list:
                out.append("P3")
    elif tier == 1:                    # 不跑 S1/S2：只补平台（出门侧优先）
        if exit_n3:
            if "P3" in punch_list:
                out.append("P3")
            if "P4" in punch_list:
                out.append("P4")
        else:
            if "P4" in punch_list:
                out.append("P4")
            if "P3" in punch_list:
                out.append("P3")
    elif treasure == 4:                # 全跑：沿途岔口重排
        if "S2" in tours:
            out.append("S2")
        if "P3" in punch_list:
            out.append("P3")
        if "S1" in tours:
            out.append("S1")
    else:                              # 全跑：基础序
        if "P3" in punch_list:
            out.append("P3")
        if "S1" in tours:
            out.append("S1")
        if "P4" in punch_list:
            out.append("P4")
        if "S2" in tours:
            out.append("S2")
    info = {"tier": tier, "tier_name": TIER_NAME[tier], "trigger": trigger,
            "exit_n3": exit_n3, "reason": reason, "tb": tb,
            "punch_list": punch_list, "tours": tours}
    return out, info


def round1_tail_ladder_wp(treasure, line_clue, punch=False, tour=False, tb=None,
                          exit_node="N3"):
    """档位阶梯 + 每档的 wp：[(时间范围, tier, 该档做什么, wp)]（对话框/报告用）。"""
    tb = tb or time_budget_macros()
    rows = []
    for rng, tier, desc in round1_tail_ladder(treasure, tb):
        wp, _info = round1_tail_plan(treasure, line_clue, punch, tour,
                                     exit_node=exit_node, tb=tb, tier=tier)
        rows.append((rng, tier, desc, wp))
    return rows


def round1_return_extra_waypoints(treasure, line_clue, punch=False, tour=False,
                                  elapsed_s=None, exit_node=None, tb=None):
    """（薄壳，兼容旧签名）只返回 wp；要看档位/定档点请用 round1_tail_plan()。"""
    return round1_tail_plan(treasure, line_clue, punch, tour,
                            elapsed_s, exit_node, tb)[0]


def time_budget_rule_lines(cfg=None):
    """规则说明（读 config.h 现值）：总开关 + 两套阈值 + 两套档位。对话框直接用。"""
    tb = time_budget_macros(cfg)
    en = time_budget_enabled(cfg)
    out = ["TIME_BUDGET_ENABLE = %s%s" % ("1" if en else "0",
           "" if en else "（=0 ⇒ 完全不裁剪，尾段恒为全量）"),
           "阈值（读 Mission/config.h）：TB_NO_SIGHTS/TB_ONE_PLAT/TB_HOME_ONLY = %d/%d/%d"
           " ｜ TB_P1_NO_SIGHTS/TB_P1_HOME_ONLY = %d/%d"
           % (tb["TB_NO_SIGHTS_AT_S"], tb["TB_ONE_PLAT_AT_S"], tb["TB_HOME_ONLY_AT_S"],
              tb["TB_P1_NO_SIGHTS_AT_S"], tb["TB_P1_HOME_ONLY_AT_S"]),
           ""]
    for title, tre in (("通用：宝物 P3/P4/P5/P6（定档点 = 回程到达出门边 N3/N5 那一刻）", 3), ("宝物在 P1：定档点 = 在 P1 平台取完宝那一刻（出口恒按 N3 侧，先西 P3 再东 P4）", 2)):
        out.append(title)
        for rng, tier, desc in round1_tail_ladder(tre, tb):
            out.append("    %-11s %s" % (rng, desc))
    return out


def treasure_return_waypoints(start, doors, treasure, line_clue=None, punch=False,
                              tour=False, elapsed_s=None):
    """镜像 plan_treasure_return()：在 P7/P8 读到宝物编号后的回程 wp。

    punch=True ⇒ 按 `P3P4_PUNCH_ENABLE` 追加"补打卡"平台；
    tour=True ⇒ 按 `UPRIGHT_TOUR_ENABLE` 追加 S1/S2。
    两者都在**宝物平台之后、P2 之前**，且按 **P3 -> S1 -> P4 -> S2 交错**
    （见 round1_return_extra_waypoints()；S1/S2 跟着"会去 P3/P4"走，不再依赖宝物值）。
    line_clue = QR 百位（0/3/4/None）。
    """
    if treasure not in TREASURE_PF:
        return None, "宝物线索未定/非法（固件会 CarBrake_Stop）"
    wp = [start]
    if treasure == 5:
        wp.append("P5")          # P5 是 N13 支路
    elif treasure == 6:
        wp.append("P6")          # P6 经 N7/N9 支路
    d2, d3, d4 = doors[0], doors[1], doors[2]
    # ⚠️ N12 只在 D2 分支：D2 的门是 N5<->N12，规划层看不见门颜色，靠必经点把车赶到 D2 门口。
    #    D3/D4 的门在 N8 上，wp 已钉死 N8，多加 N12 只会绕路（多 170cm + 经 N10->N11 刀山）。
    if d2 == CAN_PASS:
        wp += ["N12", "N5"]
    elif d3 == CAN_PASS:
        wp += ["N8", "N5"]
    elif d4 == CAN_PASS:
        wp += ["N8", "N3"]
    elif ONE_WAY_PASS in (d2, d3, d4):
        _e5 = door_back_slot_edge(3) or ("N20", "N3")
        wp += [_e5[0], _e5[1]]   # 回程需经 D5（必经点 = 触发链里 D5_BACK 的起点）
    else:
        return None, "D2/D3/D4 都不能过（固件会 CarBrake_Stop）"
    if treasure not in (5, 6):
        wp.append(TREASURE_PF[treasure])
    wp += round1_return_extra_waypoints(treasure, line_clue, punch, tour,
                                        elapsed_s=elapsed_s, exit_node=wp[-1])
    wp.append("P2")
    return wp, None


def door_return_home_waypoints(start, treasure, allow_N8_N3=False,
                               line_clue=None, punch=False, tour=False,
                               elapsed_s=None):
    """镜像 mission_planner.c:route_return_home()：门区 8 条边全禁 + wp={当前节点,[宝物平台],P2}。

    返回 (wp, blocked)，blocked 是规划时需封闭的 (from,to) 集合。
    allow_N8_N3=True 对应 door_2（D5 黑且 D3 蓝已用尽）额外放行 N8→N3，退回去重读 D4。
    punch=True ⇒ 按 `P3P4_PUNCH_ENABLE` 追加"补打卡"平台；tour=True ⇒ 按
    `UPRIGHT_TOUR_ENABLE` 追加 S1/S2（两者在宝物平台之后、P2 之前，按
    P3->S1->P4->S2 交错；S1/S2 跟着"会去 P3/P4"走）。
    line_clue = QR 百位（0/3/4/None）。
    """
    wp = [start]
    if treasure in (2, 3, 4):
        wp.append(TREASURE_PF[treasure])
    wp += round1_return_extra_waypoints(treasure, line_clue, punch, tour,
                                        elapsed_s=elapsed_s, exit_node=start)
    wp.append("P2")
    blocked = set(get_door_zone())
    if allow_N8_N3:
        blocked.discard(("N8", "N3"))
    return wp, blocked


def round2_firmware_cruise(treasure, cfg=None):
    """固件 get_newroute() 的第二轮巡游顺序：宝物=6 走 CCW 组，否则走 CW 组。

    cfg = `parse_round2_cruise()` 的结果（或 MapModel.round2）；None ⇒ 用出厂默认。
    ⚠️ 顺序来自 **config.h 的 ROUND2_CRUISE_* 宏**（2026-10-07 起，不再写死在
       mission_planner.c 里），所以传 cfg 才能反映车上真实走法。
    """
    cfg = cfg or {}
    if treasure == 6:
        return list(cfg.get("ccw") or ROUND2_CCW_DEFAULT)
    return list(cfg.get("cw") or ROUND2_CW_DEFAULT)


def round2_waypoints(doors, treasure, cruise=None, cfg=None, tour=False, s1=True):
    """镜像 get_newroute()（USE_PLANNER_ROUTE=1）：第二轮完整 wp。

    doors = door_pass[0..3]（D2/D3/D4/D5）；treasure 只用来定巡游方向（6=逆时针）。
    cruise = 自定义巡游顺序（P5~P8 各一次，顺序就是走法）；None = 固件当前顺序
             （由 cfg 的 CW/CCW 组按宝物值选，cfg=None 用出厂默认）。
    tour=True ⇒ 按 UPRIGHT_TOUR_ENABLE 在 P3 后插 S1、P4 后插 S2（S1 还受
    s1=ROUND2_S1_ENABLE 门控；map_editor 传 _r2_s1_on() 直读 config，默认 True）。
    cfg = `parse_round2_cruise()` 的结果（固件 config.h 里的两组顺序）。
    ⚠️ 门区那个"多保留的 N8"跟的是**巡游首站**：固件里就是首站=P6 才留，
       自定义顺序首站是 P6 时同理（平台交换后改顺序，门节点跟着变）。
    固件在这些组合下会 CarBrake_Stop，此时返回 (None, 原因)。
    """
    d2, d3, d4, d5 = doors[0], doors[1], doors[2], doors[3]
    if cruise is None:
        cruise = round2_firmware_cruise(treasure, cfg)
    else:
        cruise = list(cruise)
    tour_from_p6 = (cruise[0] == "P6")
    wp = ["N2", "P1", "P3"]
    if tour and s1:                # ← 镜像二轮插点（UPRIGHT_TOUR_ENABLE && ROUND2_S1_ENABLE）
        wp.append("S1")            #   N3 支路；ROUND2_S1_ENABLE=0（config.h）可单独关
    wp.append("P4")
    if tour:
        wp.append("S2")            #   N6 支路
    wp.append("N5")
    # 进门：只留真正要过的那扇门
    if can_pass(d2):
        wp.append("N12")
    elif can_pass(d3):
        wp.append("N8")
    elif can_pass(d4):
        wp.append("N3")
        if tour_from_p6:
            wp.append("N8")      # 首站=P6（逆时针）时两个门节点都要保留
    else:
        return None, "D2/D3/D4 都不能过（固件会 CarBrake_Stop）"
    # 巡游：只写 P5~P8，方向由顺序决定
    wp += cruise
    # 回程：只留要过的那扇门
    if d2 == CAN_PASS:
        wp.append("N5")
    elif d2 == ONE_WAY_PASS and d5 == CAN_PASS:
        wp.append("N10")
    elif d2 == ONE_WAY_PASS and d5 == NO_PASS and d4 == CAN_PASS:
        wp.append("N8")
    elif d2 == ONE_WAY_PASS and d5 == NO_PASS and d4 == NO_PASS:
        wp += ["N8", "N5"]       # ⚠️ N5 不可删
    elif d2 == NO_PASS and d3 == CAN_PASS:
        wp += ["N8", "N5"]       # ⚠️ N5 不可删
    elif d2 == NO_PASS and d3 == ONE_WAY_PASS and d5 == CAN_PASS:
        wp.append("N10")
    elif d2 == NO_PASS and d3 == ONE_WAY_PASS and d5 == NO_PASS:
        wp.append("N8")
    elif d2 == NO_PASS and d3 == NO_PASS and d4 == CAN_PASS:
        wp.append("N8")
    elif d2 == NO_PASS and d3 == NO_PASS and d4 == ONE_WAY_PASS:
        wp.append("N10")
    else:
        return None, "回程门状态组合固件会 CarBrake_Stop"
    wp.append("P2")
    return wp, None


class MapModel:
    """整张地图的内存模型 + 校验 + 规划 + 导出。"""

    def __init__(self):
        self.nodes = []                 # [Node]
        self.edges = []                 # [Edge]
        self.macros = {}                # config.h 展开后的宏
        self.field_name = "?"
        self.declared_count = None
        self.dirty = False
        self._tag_seq = 1
        # 转弯前补偿：map.c 的两张表 + 公式参数（与边表一样，是"可编辑 + 可写回"的数据）
        self.turn = {"stop": [], "gyro": [], "consts": dict(TURN_CONST_DEFAULTS),
                     "calc_enable": None, "warnings": [],
                     "stop_default": TURN_STOP_DEFAULT, "gyro_default": TURN_GYRO_DEFAULT}
        # 第二轮巡游顺序：config.h 的 ROUND2_CRUISE_* 两组（也是"可读 + 可写回"的数据）
        self.round2 = round2_cruise_defaults()

    # -------------------------------------------------- 载入
    @staticmethod
    def load_from_sources(with_positions=True):
        m = MapModel()
        m.macros, m.field_name = parse_config_macros()
        enum = parse_map_enum()
        coords = load_seed_positions() if with_positions else {}
        for i, (name, comment, idx) in enumerate(enum):
            x, y = coords.get(name, (60 + (i % 8) * 110, 640 + (i // 8) * 80))
            n = Node(name, comment, idx, x, y)
            if name in MISSING_SEED:
                n.comment = (n.comment + " [坐标估计]").strip()
            m.nodes.append(n)
        rows, declared = parse_edge_table()
        for r in rows:
            m.edges.append(Edge(r["from"], r["to"], r["flag"], r["angle"], r["step"],
                                r["speed"], r["func"], r["comment"], tag=m._new_tag()))
        m.declared_count = declared
        # ★ 规划权重也从**固件**读（Navigation/nav_planner.c 的 NavObsPenalty[]），
        #   覆盖类里那份硬编码的 OBS —— 否则改了固件权重、忘了改这里，
        #   上位机显示的路线会和车上跑的悄悄不一致（_selftest 第 8 节专门盯这个）。
        #   读失败保留类里的默认值，但把原因记进 m.obs["warnings"]，不静默。
        m.obs = {"warnings": []}
        try:
            for _k, _v in parse_obs_penalty().items():
                if _k in MapModel.OBS:
                    MapModel.OBS[_k] = _v
        except Exception as ex:                                    # noqa: BLE001
            m.obs["warnings"].append(
                "解析 nav_planner.c 的 NavObsPenalty[] 失败，规划权重沿用内置默认值"
                "（可能与固件不符，显示的路线未必是车上跑的）：%s" % ex)
        try:
            m.turn = parse_turn_tables()
        except Exception as ex:                                    # noqa: BLE001
            m.turn = {"stop": [], "gyro": [], "consts": dict(TURN_CONST_DEFAULTS),
                      "calc_enable": None, "stop_default": TURN_STOP_DEFAULT,
                      "gyro_default": TURN_GYRO_DEFAULT,
                      "warnings": ["解析 map.c 的转弯补偿失败：%s" % ex]}
        try:
            m.round2 = parse_round2_cruise()
        except Exception as ex:                                    # noqa: BLE001
            m.round2 = round2_cruise_defaults()
            m.round2["warnings"].append("解析 config.h 的二轮巡游顺序失败：%s" % ex)
        m.dirty = False
        return m

    # -------------------------------------------------- 转弯前补偿（map.c）
    def turn_status(self, rows, table):
        """表里每一行在当前地图上会不会生效 → [(status, detail)]（见 turn_table_status）。"""
        return turn_table_status(self, rows, table, self.turn)

    def turn_coverage(self):
        """枚举地图里所有 (入边,出边) 转弯组合 + 当前生效值。"""
        return turn_coverage(self, self.turn)

    def splice_turn_tables(self, src, eol=None):
        """把 self.turn 的两张表写回 map.c 源码（纯函数；不落盘）。"""
        return splice_turn_tables(src, self.turn.get("stop") or [],
                                  self.turn.get("gyro") or [], eol=eol)

    def _new_tag(self):
        self._tag_seq += 1
        return "e%d" % self._tag_seq

    # -------------------------------------------------- 查询
    def node(self, name):
        for n in self.nodes:
            if n.name == name:
                return n
        return None

    def node_index(self, name):
        for i, n in enumerate(self.nodes):
            if n.name == name:
                return i
        return -1

    def names(self):
        return [n.name for n in self.nodes]

    def edge(self, frm, to):
        for e in self.edges:
            if e.frm == frm and e.to == to:
                return e
        return None

    def edges_of(self, name, outgoing=True):
        return [e for e in self.edges if (e.frm if outgoing else e.to) == name]

    def has_reverse(self, e):
        return self.edge(e.to, e.frm) is not None

    def out_neighbors(self, name):
        return [e.to for e in self.edges if e.frm == name]

    def ang(self, e):
        return eval_c_expr(e.angle, self.macros)

    def step(self, e):
        return eval_c_expr(e.step, self.macros)

    # -------------------------------------------------- 编辑
    def add_node(self, name, x, y, comment=""):
        if self.node(name):
            raise ValueError("节点 %s 已存在" % name)
        if not re.match(r"^[A-Za-z_]\w*$", name):
            raise ValueError("节点名必须是合法 C 标识符：%r" % name)
        n = Node(name, comment, len(self.nodes), x, y)
        self.nodes.append(n)
        self.dirty = True
        return n

    def remove_node(self, name, remove_edges=True):
        n = self.node(name)
        if not n:
            return False
        self.nodes.remove(n)
        if remove_edges:
            self.edges = [e for e in self.edges if e.frm != name and e.to != name]
        self.dirty = True
        return True

    def rename_node(self, old, new):
        if old == new:
            return True
        if self.node(new):
            raise ValueError("节点 %s 已存在" % new)
        if not re.match(r"^[A-Za-z_]\w*$", new):
            raise ValueError("节点名必须是合法 C 标识符：%r" % new)
        self.node(old).name = new
        for e in self.edges:
            if e.frm == old:
                e.frm = new
            if e.to == old:
                e.to = new
        self.dirty = True
        return True

    def add_edge(self, frm, to, flag="NO", angle="0", step="0", speed="SPEED0",
                 func="NONE", comment=""):
        if not self.node(frm) or not self.node(to):
            raise ValueError("边端点不存在：%s -> %s" % (frm, to))
        if frm == to:
            raise ValueError("不允许自环：%s" % frm)
        if self.edge(frm, to):
            raise ValueError("边 %s -> %s 已存在" % (frm, to))
        e = Edge(frm, to, flag, angle, step, speed, func, comment, tag=self._new_tag())
        self.edges.append(e)
        self.dirty = True
        return e

    def remove_edge(self, frm, to):
        before = len(self.edges)
        self.edges = [e for e in self.edges if not (e.frm == frm and e.to == to)]
        if len(self.edges) != before:
            self.dirty = True
            return True
        return False

    def move_node(self, name, x, y):
        n = self.node(name)
        if n:
            n.x, n.y = float(x), float(y)
            self.dirty = True

    # -------------------------------------------------- 序列化（撤销/存档）
    def snapshot(self):
        return json.dumps({
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "tag_seq": self._tag_seq,
        }, ensure_ascii=False, sort_keys=True)

    def restore(self, snap):
        d = json.loads(snap)
        self.nodes = [Node.from_dict(x) for x in d["nodes"]]
        self.edges = [Edge.from_dict(x) for x in d["edges"]]
        self._tag_seq = d.get("tag_seq", 1)
        self.dirty = True

    def to_json(self):
        return json.dumps({
            "format": "xunbao-map",
            "version": 2,
            "field": self.field_name,
            "macros": {k: v for k, v in self.macros.items()},
            "background": dict(getattr(self, "background", {}) or {}),
            "constraints": dict(getattr(self, "constraints", {}) or {}),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "turn": {"stop": [dict(r) for r in self.turn.get("stop") or []],
                     "gyro": [dict(r) for r in self.turn.get("gyro") or []],
                     "consts": dict(self.turn.get("consts") or {}),
                     "calc_enable": self.turn.get("calc_enable")},
        }, ensure_ascii=False, indent=1)

    def load_json(self, text):
        d = json.loads(text)
        self.nodes = [Node.from_dict(x) for x in d.get("nodes", [])]
        self.edges = [Edge.from_dict(x) for x in d.get("edges", [])]
        for e in self.edges:
            if not e.tag:
                e.tag = self._new_tag()
        self.field_name = d.get("field", self.field_name)
        self.macros.update(d.get("macros", {}))
        # 转弯补偿表（老布局里没有这个键 ⇒ 保持从源码读到的值）
        t = d.get("turn")
        if isinstance(t, dict):
            for k in ("stop", "gyro", "consts", "calc_enable"):
                if k in t and t[k] is not None:
                    if k == "consts":
                        self.turn["consts"].update(t[k])
                    else:
                        self.turn[k] = t[k]
        # 底图标定 / 拖动约束（界面写、界面读；核心层不解释其内容）
        self.background = d.get("background", {}) or {}
        self.constraints = d.get("constraints", {}) or {}
        self.dirty = True

    # -------------------------------------------------- 校验
    def validate(self):
        """返回 [(级别, 消息)]；级别 'error' / 'warn' / 'info'。"""
        out = []
        names = set(self.names())
        seen = {}
        for i, e in enumerate(self.edges, 1):
            if e.frm not in names:
                out.append(("error", "第 %d 行：from 节点 %s 不在 enum MapNode 里" % (i, e.frm)))
            if e.to not in names:
                out.append(("error", "第 %d 行：to 节点 %s 不在 enum MapNode 里" % (i, e.to)))
            if e.frm == e.to:
                out.append(("error", "第 %d 行：自环 %s->%s" % (i, e.frm, e.to)))
            if e.key() in seen:
                out.append(("error", "重复边 %s，第 %d 行与第 %d 行"
                            % (e.label(), seen[e.key()], i)))
            seen[e.key()] = i
            if e.func not in FUNC_ORDER and not re.match(r"^\d+$", e.func or ""):
                out.append(("warn", "第 %d 行：function=%s 不在已知列表" % (i, e.func)))
            for tok in re.split(r"[|,\s]+", e.flag or ""):
                tok = tok.strip()
                if tok and not re.match(r"^\d+$", tok) and tok not in FLAG_ORDER:
                    out.append(("warn", "第 %d 行：flag 里的 %s 不认识" % (i, tok)))
            if eval_c_expr(e.angle, self.macros) is None:
                out.append(("warn", "第 %d 行：angle=%s 无法解析成数字" % (i, e.angle)))
            if eval_c_expr(e.step, self.macros) is None:
                out.append(("warn", "第 %d 行：step=%s 无法解析成数字" % (i, e.step)))

        used = set()
        for e in self.edges:
            used.add(e.frm)
            used.add(e.to)
        for n in self.nodes:
            if n.name not in used:
                out.append(("info", "孤立节点 %s（没有任何边）" % n.name))

        # 已知设计如此的单向边（跷跷板 B8/B9、刀山 N10→N12），不报警
        _KNOWN_ONEWAY = {("N7", "B8"), ("B8", "N9"), ("B9", "N7"), ("N9", "B9"), ("N10", "N12")}
        for e in self.edges:
            if not self.has_reverse(e):
                if (e.frm, e.to) not in _KNOWN_ONEWAY:
                    out.append(("warn", "单向边 %s（没有反向边 %s）" % (e.label(), e.to + "->" + e.frm)))

        for n in self.nodes:
            outs = len(self.edges_of(n.name, True))
            ins = len(self.edges_of(n.name, False))
            if outs == 0 and ins == 1:
                out.append(("warn", "节点 %s 只有入边没有出边（车到这儿没路走）" % n.name))
            if outs == 1 and ins == 0:
                out.append(("warn", "节点 %s 只有出边没有入边" % n.name))

        # 路口判断标志位（到达判据）与终点路口几何的一致性。
        # 只查普通边（func=NONE）；门区/景点/跷跷板等特殊边另有到达检测语义，不套此规则。
        # 默认保守口径 right_only=True + include_mul=False：只报 DLEFT/DRIGHT（直角左右）的
        # 确定性错误 —— 这是唯一能静态可靠判出的信号。C/MC（斜线/急弯精细分档）与 MUL（线数
        # 时序判据）要么固件作者手写时本就不会精确匹配、要么靠 if 链优先级覆盖，把它们当 warn
        # 会大面积误报（用户 2026-10-02 反馈「地图能跑通却有 50 条警告」）。
        for it in analyze_junction_flags(self, only_plain=True, include_mul=False,
                                         right_only=True):
            e = it["edge"]
            detail = "、".join(
                (["多余 " + "+".join(it["extra"])] if it["extra"] else [])
                + (["缺失 " + "+".join(it["missing"])] if it["missing"] else []))
            out.append(("warn", "边 %s：路口标志与几何不符（%s）；建议 %s" % (
                e.label(), detail, suggest_junction_flags(self, e, include_mul=False,
                                                          right_only=True))))
        if not out:
            out.append(("info", "校验通过：%d 个节点 / %d 条边" % (len(self.nodes), len(self.edges))))
        return out

    # -------------------------------------------------- 规划（与固件同一套 Dijkstra）
    NAV_W_TURN = 0.6
    # 逐项对齐 nav_planner.c 的 NavObsPenalty[]（键 = barriers 枚举名）。
    # ⚠️ 漏改过：Bridge/Hill/LBHill/SM/View/View1/BACK/BSoutPole/QQB/BHM 曾被写成 0、
    #    BLBL 曾写成 70，导致上位机把桥/山/楼梯/景点/跷跷板/波动板当免费捷径，
    #    "显示的路线"和车上跑的不是一条。_selftest.py 的第 8 节会自动比对固件源码，别再手改。
    # ⚠️ `Hill` 2026-09-13 由 300 降到 230（用户要求：N8→C9 走楼梯、N12→N20 仍走南环；
    #    各对翻转阈值不同：N8→C9 ≤239 才翻、N12→N20 ≤200 才翻，取中间 230）。
    OBS = {"NONE": 0, "UpStage": 60, "Bridge": 300, "Hill": 230, "LBHill": 50,
           "SM": 120, "View": 100, "View1": 100, "BACK": 1000, "BSoutPole": 90,
           "QQB": 80, "BLBS": 70, "BLBL": 50, "DOOR": 60, "BHM": 90,
           "IGNORE": 0, "Special_node": 0, "DOOR1": 0, "UpStageHome": 60}

    def node_io_roles(self, name):
        """该节点的 (入口动作, 出口动作)。

        平台在边表里就是"一条进边带平台动作（`UpStage`/`UpStageHome`/`BSoutPole`/`BHM`…）
        + 一条出边"。多条进/出边时优先取 `func != NONE` 的那条（动作就写在它上面）。
        """
        def pick(lst):
            for e in lst:
                if e.func and e.func != "NONE":
                    return e.func
            return lst[0].func if lst else "NONE"

        return pick(self.edges_of(name, False)), pick(self.edges_of(name, True))

    def swap_platforms(self, a, b, swap_xy=False, dry_run=False):
        """**平台快速交换**：把 a、b 两个节点的名字互换。

        * **只改 `from`/`to`**：`angle`/`step`/`flag`/`speed` 一个都不动 ⇒ **长度不变**；
        * 每条相关边的 `func` 换成"**新名字那个平台**"的入口/出口动作 ⇒ **function 随平台切换**；
        * `swap_xy=True` 时连图上坐标也一起换（默认 False：位置不动，"其他沿用原来的"）。

        例：`swap_platforms("P5","P7")` ⇒ 原来 `N13→P5(step=80,UpStage)` 变成 `N13→P7(step=80,**BSoutPole**)`，
        原来 `B7→P7(step=10,BSoutPole)` 变成 `B7→P5(step=10,**UpStage**)`。

        `dry_run=True` 只返回变更说明、不改模型（界面用它做预览）。
        出错抛 `ValueError`（界面直接显示）。
        """
        if a == b:
            raise ValueError("两个平台不能是同一个：%s" % a)
        na, nb = self.node(a), self.node(b)
        if na is None:
            raise ValueError("地图里没有节点 %s" % a)
        if nb is None:
            raise ValueError("地图里没有节点 %s" % b)
        if self.edge(a, b) is not None or self.edge(b, a) is not None:
            raise ValueError("%s 与 %s 之间有直接边，交换会有歧义（那条边算谁的？），"
                             "请先删掉它再交换" % (a, b))
        in_a, out_a = self.node_io_roles(a)
        in_b, out_b = self.node_io_roles(b)
        a_ins = list(self.edges_of(a, False))
        a_outs = list(self.edges_of(a, True))
        b_ins = list(self.edges_of(b, False))
        b_outs = list(self.edges_of(b, True))

        # 名字映射（改名前先算好，说明文本要用新名字）
        plan = []                                   # (edge, 新from, 新to)
        for e in (a_ins + a_outs + b_ins + b_outs):
            nf = b if e.frm == a else (a if e.frm == b else e.frm)
            nt = b if e.to == a else (a if e.to == b else e.to)
            plan.append((e, nf, nt))
        # func：**坐在 a 位置的那些边**现在叫 b 了 ⇒ 用 b 的入口/出口动作；反之亦然
        want = []
        for e in a_ins:
            want.append((e, in_b, b))
        for e in a_outs:
            want.append((e, out_b, b))
        for e in b_ins:
            want.append((e, in_a, a))
        for e in b_outs:
            want.append((e, out_a, a))

        newlabel = {e.tag: (nf, nt) for e, nf, nt in plan}
        changes = ["改名  %-14s ⇒ %s → %s" % ("%s→%s" % (e.frm, e.to), nf, nt)
                   for e, nf, nt in plan
                   if (e.frm, e.to) != (nf, nt)]
        changes += ["func  %-14s %-11s → %-11s（%s 的动作）"
                    % ("%s→%s" % newlabel[e.tag], e.func, w, owner)
                    for e, w, owner in want if e.func != w]
        if swap_xy:
            changes.append("坐标  %s ↔ %s 互换（%.0f,%.0f ↔ %.0f,%.0f）"
                           % (a, b, na.x, na.y, nb.x, nb.y))
        if dry_run:
            return changes

        for e, nf, nt in plan:                      # ① 只改 from/to，其它字段一个不动
            e.frm, e.to = nf, nt
        for e, w, _owner in want:                   # ② func 随平台切换
            e.func = w
        if swap_xy:
            na.x, nb.x = nb.x, na.x
            na.y, nb.y = nb.y, na.y
        self.dirty = True
        return changes

    def plan_route(self, waypoints, cost_mode="full", blocked=None):
        """必经点最短路。返回 (path, None) 或 (None, 原因)。

        blocked: 规划时需封闭的 (from,to) 集合，镜像 nav_set_edge_blocked()；
                 门回程用 door_return_home_waypoints() 生成。
        """
        if not waypoints:
            return None, "没有必经点"
        for w in waypoints:
            if not self.node(w):
                return None, "必经点 %s 不存在" % w
        full = []
        for i in range(len(waypoints) - 1):
            if waypoints[i] == waypoints[i + 1]:
                continue
            seg, why = self._dijkstra(waypoints[i], waypoints[i + 1], cost_mode, blocked)
            if seg is None:
                return None, "%s -> %s 不可达" % (waypoints[i], waypoints[i + 1])
            full.extend(seg if not full else seg[1:])
        return (full or [waypoints[0]]), None

    def _dijkstra(self, src, dst, mode, blocked=None):
        import heapq
        if src == dst:
            return [src], None
        blocked = set(blocked or ())

        def w_obs(e):
            return self.OBS.get(e.func, 0) if mode == "full" else 0

        def turn_cost(pe, e):
            if pe is None or mode == "len":
                return 0.0
            a1, a2 = self.ang(pe), self.ang(e)
            if a1 is None or a2 is None:
                return 0.0
            d = (a2 - a1) % 360.0
            if d > 180:
                d -= 360
            return abs(d) * self.NAV_W_TURN

        INF = float("inf")
        best = {}
        prev = {}
        pq = []
        for e in self.edges_of(src, True):
            if (e.frm, e.to) in blocked:      # 镜像 nav_shortest_path：被禁边不作为起点
                continue
            c = (self.step(e) or 0.0) + w_obs(e)
            st = (e.to, e.tag)
            if c < best.get(st, INF):
                best[st] = c
                # (起点, None)：回溯到它再查 prev 会得到 None，循环自然结束
                prev[st] = (src, None)
                heapq.heappush(pq, (c, e.to, e.tag))
        by_tag = {e.tag: e for e in self.edges}
        while pq:
            c, u, tag = heapq.heappop(pq)
            if c > best.get((u, tag), INF) + 1e-9:
                continue
            if u == dst:
                path = [u]
                st = (u, tag)
                while prev.get(st) is not None:
                    pu, ptag = prev[st]
                    path.append(pu)
                    st = (pu, ptag)
                path.reverse()
                return path, None
            pe = by_tag.get(tag)
            for e in self.edges_of(u, True):
                if (e.frm, e.to) in blocked:  # 镜像 nav_shortest_path：被禁边不参与松弛
                    continue
                nc = c + (self.step(e) or 0.0) + w_obs(e) + turn_cost(pe, e)
                st2 = (e.to, e.tag)
                if nc < best.get(st2, INF) - 1e-9:
                    best[st2] = nc
                    # 前驱统一记成 (上一跳所在节点, 上一跳的边 tag)；
                    # 起点的前驱在初始化时写 None（表示"没有更前面的节点了"）。
                    prev[st2] = (u, tag)
                    heapq.heappush(pq, (nc, e.to, e.tag))
        return None, "不可达"

    # -------------------------------------------------- 导出
    def export_enum(self):
        """生成 enum MapNode（按当前节点列表顺序重排索引）。"""
        lines = ["enum MapNode {\t//MapNode"]
        for i, n in enumerate(self.nodes):
            cmt = ("//%d" % i) if not n.comment else ("//%d\t%s" % (i, n.comment))
            lines.append("\t%s,\t%s" % (n.name, cmt))
        lines[-1] = lines[-1].rstrip(",")     # 最后一项不带逗号（原文件风格）
        return "\n".join(lines) + "\n};"

    def _fmt_edge_row(self, e):
        toks = [t.strip() for t in re.split(r"[|,]", e.flag or "") if t.strip()]
        flag_txt = "|".join(toks) if toks else "NO"
        row = "    { %s, %s, %s, %s, %s, %s, %s }," % (
            e.frm, e.to, flag_txt, e.angle, e.step, e.speed, e.func)
        cmt = (e.comment or "").strip()
        if cmt:
            row = "%-56s /* %s->%s %s */" % (row, e.frm, e.to, cmt)
        return row

    def export_edge_table(self, with_header=True):
        """生成 NavEdgeTbl[] 的完整 C 文本。"""
        out = []
        if with_header:
            out.append("/* ---- 由 scripts/map_editor/map_editor.py 导出（%s）---- */"
                       % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
        out.append("const NavEdge NavEdgeTbl[NAV_EDGE_COUNT] = {")
        order = {n.name: i for i, n in enumerate(self.nodes)}
        groups = {}
        for e in self.edges:
            groups.setdefault(e.frm, []).append(e)
        for name in sorted(groups.keys(), key=lambda k: order.get(k, 9999)):
            out.append("")
            out.append("    /* ========== %s ========== */" % name)
            for e in groups[name]:
                out.append(self._fmt_edge_row(e))
        out.append("};")
        out.append("")
        out.append("/* 编译期检查：NavEdgeTbl 行数必须与 NAV_EDGE_COUNT 一致（改漏立即编译报错）")
        out.append("   使用 C99 兼容技巧：负数组大小在编译期报错 */")
        out.append("typedef char NavEdgeTbl_size_check[(sizeof(NavEdgeTbl)/sizeof(NavEdge) == "
                   "NAV_EDGE_COUNT) ? 1 : -1];")
        out.append("")
        out.append("/* Node[]/ConnectionNum[]/Address[] 已移至 nav_planner.c 统一构建，"
                   "nav_graph_init() 已废弃 */")
        return "\n".join(out) + "\n"

    def export_edges_only(self):
        """只导出表体（从第一行边到最后一行边，带分组注释），方便手工粘回。"""
        txt = self.export_edge_table(with_header=False)
        lines = txt.splitlines()
        # 去掉 const 行与尾部 sizeof 检查
        keep = []
        for ln in lines:
            if ln.startswith("const NavEdge"):
                continue
            if ln.startswith("/* 编译期检查") or ln.startswith("typedef char NavEdgeTbl_size_check"):
                continue
            if ln.startswith("   使用 C99 兼容技巧"):
                continue
            if ln.startswith("/* Node[]/ConnectionNum"):
                continue
            if ln.strip() == "};":
                continue
            keep.append(ln)
        return "\n".join(keep).strip("\n") + "\n"

    def export_nav_edge_count(self):
        return "#define NAV_EDGE_COUNT %d" % len(self.edges)

    def export_route_array(self, path):
        """把一条路线导出成 route[100] 初始化（map.c 的 MAP_DEBUG 用）。"""
        if not path:
            return "u8 route[100] = {0XFF};"
        return "u8 route[100] = {%s, 0XFF};" % ", ".join(path)

    def export_debug_macros(self, first, via, end):
        return "\n".join([
            "#define FIRST_POINT   %s" % first,
            "#define VIA_POINT     %s" % (via if via and via != "0" else "0"),
            "#define END_POINT     %s" % end,
        ])

    def export_connectivity(self):
        lines = ["%-6s %-6s %-6s %-8s %-8s %-8s %s" %
                 ("from", "to", "ang", "step", "speed", "func", "flag")]
        for e in self.edges:
            lines.append("%-6s %-6s %-6s %-8s %-8s %-8s %s" % (
                e.frm, e.to, e.angle, e.step, e.speed, e.func, e.flag))
        return "\n".join(lines) + "\n"

    def export_eval_report(self):
        """把每条边的 angle/step 求值结果打出来（自检宏是否都解析成功）。"""
        lines = ["%-6s %-6s %10s %10s  %s" % ("from", "to", "angle", "step", "func")]
        bad = 0
        for e in self.edges:
            a, s = self.ang(e), self.step(e)
            if a is None or s is None:
                bad += 1
            lines.append("%-6s %-6s %10s %10s  %s" % (
                e.frm, e.to, "ERR" if a is None else "%.1f" % a,
                "ERR" if s is None else "%.1f" % s, e.func))
        lines.append("")
        lines.append("求值失败 %d 条 / 共 %d 条" % (bad, len(self.edges)))
        return "\n".join(lines) + "\n"

    # -------------------------------------------------- 兼容性自检
    def roundtrip_report(self):
        """对照原文件，逐行比较「原边表」与「重新导出」的差异。"""
        rows, _ = parse_edge_table()
        orig = {}
        for r in rows:
            orig[(r["from"], r["to"])] = r
        mine = {}
        for e in self.edges:
            mine[e.key()] = e
        problems = []
        for k, r in orig.items():
            if k not in mine:
                problems.append("丢失边 %s->%s" % k)
                continue
            e = mine[k]
            exp_flag = "|".join(t.strip() for t in re.split(r"[|,]", r["flag"]) if t.strip())
            got_flag = "|".join(t.strip() for t in re.split(r"[|,]", e.flag or "") if t.strip())
            for fld, want, got in (("flag", exp_flag, got_flag), ("angle", r["angle"], e.angle),
                                   ("step", r["step"], e.step), ("speed", r["speed"], e.speed),
                                   ("func", r["func"], e.func)):
                if want != got:
                    problems.append("%s->%s 字段 %s: 原=%r 现=%r" % (k[0], k[1], fld, want, got))
        for k in mine:
            if k not in orig:
                problems.append("新增边 %s->%s" % k)
        return problems


# ---------------------------------------------------------------- 初始坐标种子
# 读自 寻宝地图/节点图.jpg（1012x632 预览坐标系）；纯界面用途，不参与固件。
SEED_POSITIONS = {
    'S1': (197, 77), 'P1': (565, 72), 'B1': (821, 60), 'N1': (667, 60), 'B2': (727, 154),
    'B3': (881, 160), 'N2': (992, 60), 'P2': (1189, 69), 'S2': (1549, 103),
    'P3': (171, 243), 'N3': (633, 249), 'N4': (878, 254), 'N5': (1104, 254), 'N6': (1261, 218),
    'P4': (1523, 243), 'C1': (1198, 351), 'D4': (727, 372), 'D3': (967, 351), 'N8': (878, 442),
    'D2': (1061, 450), 'D1': (1198, 420), 'N7': (364, 334), 'N9': (364, 611), 'N10': (595, 604),
    'N12': (1104, 591), 'N13': (1261, 591), 'P5': (1523, 622), 'C3': (145, 591), 'N14': (145, 699),
    'S3': (257, 707), 'S4': (530, 699), 'N15': (633, 719), 'S5': (1104, 699), 'N16': (1155, 750),
    'C4': (317, 767), 'C5': (633, 796), 'N18': (1104, 813), 'B5': (1343, 767), 'N19': (1523, 762),
    'C6': (1523, 856), 'B6': (876, 964), 'N22': (987, 976), 'C9': (1235, 1053), 'P7': (1506, 1022),
    'C7': (151, 1019), 'C8': (305, 1053), 'B11': (436, 885), 'B7': (1343, 856), 'N20': (715, 885),
    'P8': (163, 882), 'N11': (838, 591), 'G1': (1412, 1044), 'B10': (116, 984),
    'B8': (299, 462), 'B9': (441, 462), 'P6': (364, 497),
    # ↓ 这 6 个节点在 节点图.jpg 上**没有画**，坐标是估的：
    #    用"相邻边的表里 angle"做联合最小二乘求解，再结合图上相对方位微调。
    #    ⚠️ 精度上限 ≈ ±50px：把图上已画的节点当未知重解一遍，平均也偏 52px，
    #    这就是节点图（示意图）本身的不准程度。所以这几个点**按你觉得对的位置拖**即可，
    #    拖动只改示意图位置，**不影响任何 step/angle 数值**。
    'C6': (1455, 830), 'C7': (188, 1001), 'C8': (294, 1046),
    'G1': (1376, 1044), 'C2': (1205, 447), 'B4': (359, 693),
}

# 没有画在节点图上的节点（界面会提示"坐标是估的，可拖"）
MISSING_SEED = ("C6", "C7", "C8", "G1", "C2", "B4")


def load_seed_positions():
    return dict(SEED_POSITIONS)


# ---------------------------------------------------------------- 布局 JSON 对比 / 迁移
# 「⇋ JSON 对比…」的纯计算部分（无 Tk，_selftest 有专节守着）。
# 方向约定：a = 基准（当前布局），b = 参考（要把 b 的值迁到 a 一侧）。
# 设计护栏：
#  - layout_diff() 只产出「差异行 + 指令」，apply_layout_diff_items() 才真正改模型，
#    两段都能脱离 GUI 单测；
#  - 删除类指令（删节点/删边/删补偿行）sel=False 默认不勾，防误删；
#  - 「仅当前有」的宏不给迁移（宏被边表 angle/step 引用，删了 eval 会失败）；
#  - 参考里只有反向边（b 有 Y→X 而 a 只有 X→Y）只提示、不自动迁（方向语义要人工定）；
#  - 迁移前的完整快照由界面层落盘（宏/转弯表/约束不在撤销栈里，撤销救不回来）。

def _diff_txt(v, limit=46):
    """值 → 对比对话框里显示的短文本。"""
    if v is None:
        return "(无)"
    if isinstance(v, bool):
        s = "开" if v else "关"
    elif isinstance(v, float):
        s = "%g" % v
    elif isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False)
    else:
        s = str(v)
    s = s.replace("\n", " ")
    return s if len(s) <= limit else s[:limit - 1] + "…"


_EDGE_DIFF_FIELDS = ("flag", "angle", "step", "speed", "func", "comment")
_NODE_DIFF_FIELDS = ("x", "y", "comment")


def _num_eq(x, y):
    try:
        return abs(float(x) - float(y)) < 1e-9
    except (TypeError, ValueError):
        return x == y


def layout_diff(a, b):
    """对比两份布局 JSON（json.loads 后的 dict）。

    返回 [section]；section = {"name": 节名, "same": 相同项数, "rows": [row]}；
    row = {"label","cur","ref","sel","act","apply"}：
      - apply=None → 仅提示行，不参与迁移；
      - 否则 apply = 指令元组，交给 apply_layout_diff_items()。
    格式不对（format != "xunbao-map"）抛 ValueError。
    """
    for tag, d in (("A", a), ("B", b)):
        if not isinstance(d, dict) or d.get("format") != "xunbao-map":
            raise ValueError("%s 不是布局 JSON（format 字段不对，或选错了文件）" % tag)
    secs = []

    def _sec(name):
        s = {"name": name, "same": 0, "rows": []}
        secs.append(s)
        return s

    def _row(sec, label, cur, ref, act, apply_, sel=True):
        sec["rows"].append({"label": label, "cur": cur, "ref": ref,
                            "act": act, "apply": apply_, "sel": sel})

    # ① 场地（USE_FIELD，影响所有 LEN_*/ANGLE_* 宏的取值）
    s = _sec("场地")
    va, vb = a.get("field"), b.get("field")
    if va != vb:
        _row(s, "USE_FIELD", _diff_txt(va), _diff_txt(vb),
             "改成 B 的场地", ("field", vb))
    else:
        s["same"] += 1

    # ② 宏（config.h 快照：LEN_*/ANGLE_*/ROUND2_CRUISE_*……）
    s = _sec("宏")
    ma, mb = a.get("macros") or {}, b.get("macros") or {}
    for k in sorted(set(ma) | set(mb)):
        va, vb = ma.get(k), mb.get(k)
        if va == vb:
            s["same"] += 1
        elif k not in mb:
            _row(s, k, _diff_txt(va), "(无)",
                 "仅 A 有（不迁移：删宏会让边表求值失败）", None)
        else:
            _row(s, k, _diff_txt(va), _diff_txt(vb), "改成 B 的值",
                 ("macro", k, vb))

    # ③ 转弯补偿（两张表 + 公式常量 + 计算开关）
    s = _sec("转弯补偿")
    ta, tb = a.get("turn") or {}, b.get("turn") or {}
    va, vb = ta.get("calc_enable"), tb.get("calc_enable")
    if va != vb:
        _row(s, "TURN_CALC_ENABLE", _diff_txt(va), _diff_txt(vb),
             "改成 B 的值", ("calc", vb))
    else:
        s["same"] += 1
    ca, cb = ta.get("consts") or {}, tb.get("consts") or {}
    for k in sorted(set(ca) | set(cb)):
        va, vb = ca.get(k), cb.get(k)
        if va == vb:
            s["same"] += 1
        elif k not in cb:
            _row(s, "常量 " + k, _diff_txt(va), "(无)", "仅 A 有（保留）", None)
        else:
            _row(s, "常量 " + k, _diff_txt(va), _diff_txt(vb), "改成 B 的值",
                 ("const", k, vb))
    for tbl in ("stop", "gyro"):
        la = {(r.get("last"), r.get("now"), r.get("next")): r
              for r in (ta.get(tbl) or [])}
        lb = {(r.get("last"), r.get("now"), r.get("next")): r
              for r in (tb.get(tbl) or [])}
        tname = "停车转" if tbl == "stop" else "陀螺转"
        for k in sorted(set(la) | set(lb), key=lambda x: tuple(str(v) for v in x)):
            ra, rb = la.get(k), lb.get(k)
            if ra is not None and rb is not None and _num_eq(ra.get("dist"), rb.get("dist")):
                s["same"] += 1
                continue
            label = "%s: %s→%s→%s" % ((tname,) + tuple(str(v) for v in k))
            if rb is None:
                _row(s, label, _diff_txt(ra and ra.get("dist")), "(无)",
                     "删掉这行补偿", ("turndel", tbl) + tuple(k), sel=False)
            else:
                _row(s, label, _diff_txt(ra and ra.get("dist")),
                     _diff_txt(rb.get("dist")),
                     "新增这行补偿" if ra is None else "改成 B 的值",
                     ("turn", tbl, dict(rb)))

    # ④ 约束 / ⑤ 底图标定（界面态；clue_route/round2_route 这类整键一起迁）
    for name, key, ap in (("约束", "constraints", "constr"),
                          ("底图标定", "background", "bg")):
        s = _sec(name)
        da_, db_ = a.get(key) or {}, b.get(key) or {}
        for k in sorted(set(da_) | set(db_)):
            va, vb = da_.get(k), db_.get(k)
            if va == vb:
                s["same"] += 1
            elif k not in db_:
                _row(s, k, _diff_txt(va), "(无)", "仅 A 有（保留）", None)
            else:
                _row(s, k, _diff_txt(va), _diff_txt(vb), "改成 B 的值",
                     (ap, k, vb))

    # ⑥ 节点（坐标 / 备注；新增 / 删除）
    s = _sec("节点")
    na = {n.get("name"): n for n in (a.get("nodes") or [])}
    nb = {n.get("name"): n for n in (b.get("nodes") or [])}

    def _npos(n):
        return "x=%s y=%s %s" % (_diff_txt(n.get("x"), 10), _diff_txt(n.get("y"), 10),
                                 _diff_txt(n.get("comment"), 18))

    for name in sorted(set(na) | set(nb)):
        ra, rb = na.get(name), nb.get(name)
        if ra is not None and rb is not None:
            if all((_num_eq(ra.get(f), rb.get(f)) if f != "comment"
                    else ra.get(f) == rb.get(f)) for f in _NODE_DIFF_FIELDS):
                s["same"] += 1
            else:
                _row(s, name, _npos(ra), _npos(rb),
                     "改成 B 的坐标/备注", ("node", name, dict(rb)))
        elif rb is not None:
            _row(s, name, "(无)", _npos(rb),
                 "新增节点（它的边要在「边」节一起勾）", ("node", name, dict(rb)))
        else:
            _row(s, name, _npos(ra), "(无)",
                 "从当前删除（连带它的边）", ("nodedel", name), sel=False)

    # ⑦ 边（参数逐字段比；方向按 frm→to 精确配对）
    s = _sec("边")
    ea = {(e.get("frm"), e.get("to")): e for e in (a.get("edges") or [])}
    eb = {(e.get("frm"), e.get("to")): e for e in (b.get("edges") or [])}

    def _eparams(e):
        return " / ".join("%s=%s" % (f, _diff_txt(e.get(f), 14))
                          for f in _EDGE_DIFF_FIELDS)


    for k in sorted(set(ea) | set(eb), key=lambda x: tuple(str(v) for v in x)):
        ra, rb = ea.get(k), eb.get(k)
        if ra is not None and rb is not None:
            changed = [f for f in _EDGE_DIFF_FIELDS if ra.get(f) != rb.get(f)]
            if not changed:
                s["same"] += 1
            else:
                _row(s, "%s→%s" % k,
                     " / ".join("%s=%s" % (f, _diff_txt(ra.get(f), 14)) for f in changed),
                     " / ".join("%s=%s" % (f, _diff_txt(rb.get(f), 14)) for f in changed),
                     "改成 B 的参数", ("edge", k[0], k[1], dict(rb)))
        elif rb is not None:
            _row(s, "%s→%s" % k, "(无)", _eparams(rb), "新增边",
                 ("edge", k[0], k[1], dict(rb)))
        else:
            _row(s, "%s→%s" % k, _eparams(ra), "(无)", "从当前删除这条边",
                 ("edgedel", k[0], k[1]), sel=False)
            if (k[1], k[0]) in eb:
                _row(s, "%s→%s" % k, "A 里是这个方向",
                     "B 里是 %s→%s" % (k[1], k[0]),
                     "两边方向不同，请人工核对（不自动迁）", None)
    return secs


def apply_layout_diff_items(model, items):
    """把 layout_diff() 产出的指令应用到 MapModel。返回实际生效的条数。

    纯函数（不碰 Tk、不碰文件）；界面层负责撤销点 + 迁移前快照 + 刷新。
    """
    n = 0
    for it in items:
        kind = it[0]
        if kind == "field":
            model.field_name = it[1]
            n += 1
        elif kind == "macro":
            model.macros[it[1]] = it[2]
            n += 1
        elif kind == "const":
            model.turn["consts"][it[1]] = it[2]
            n += 1
        elif kind == "calc":
            model.turn["calc_enable"] = it[1]
            n += 1
        elif kind == "turn":
            tbl, row = it[1], it[2]
            lst = model.turn.setdefault(tbl, [])
            key = (row.get("last"), row.get("now"), row.get("next"))
            for i, r in enumerate(lst):
                if (r.get("last"), r.get("now"), r.get("next")) == key:
                    lst[i] = dict(row)
                    break
            else:
                lst.append(dict(row))
            n += 1
        elif kind == "turndel":
            tbl, k = it[1], tuple(it[2:5])
            lst = model.turn.get(tbl) or []
            keep = [r for r in lst
                    if (r.get("last"), r.get("now"), r.get("next")) != k]
            if len(keep) != len(lst):
                model.turn[tbl] = keep
                n += 1
        elif kind == "constr":
            if not isinstance(getattr(model, "constraints", None), dict):
                model.constraints = {}
            model.constraints[it[1]] = it[2]
            n += 1
        elif kind == "bg":
            if not isinstance(getattr(model, "background", None), dict):
                model.background = {}
            model.background[it[1]] = it[2]
            n += 1
        elif kind == "node":
            name, d = it[1], it[2]
            nd = model.node(name)
            if nd is not None:
                if "x" in d:
                    nd.x = float(d["x"])
                if "y" in d:
                    nd.y = float(d["y"])
                if "comment" in d:
                    nd.comment = d["comment"]
            else:
                model.nodes.append(Node.from_dict(dict(d, name=name)))
            n += 1
        elif kind == "nodedel":
            name = it[1]
            if model.node(name) is not None:
                model.nodes = [x for x in model.nodes if x.name != name]
                model.edges = [e for e in model.edges
                               if e.frm != name and e.to != name]
                n += 1
        elif kind == "edge":
            frm, to, d = it[1], it[2], it[3]
            ed = model.edge(frm, to)
            if ed is not None:
                for f in _EDGE_DIFF_FIELDS:
                    if f in d:
                        setattr(ed, f, d[f])
            else:
                d2 = dict(d)
                d2["frm"], d2["to"], d2["tag"] = frm, to, None
                e2 = Edge.from_dict(d2)
                if not e2.tag:
                    e2.tag = model._new_tag()
                model.edges.append(e2)
            n += 1
        elif kind == "edgedel":
            ed = model.edge(it[1], it[2])
            if ed is not None:
                model.edges.remove(ed)
                n += 1
    if n:
        model.dirty = True
    return n



# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    m = MapModel.load_from_sources()
    print("ROOT =", ROOT)
    print("field =", m.field_name)
    print("nodes = %d, edges = %d, NAV_EDGE_COUNT = %s"
          % (len(m.nodes), len(m.edges), m.declared_count))
    probs = m.roundtrip_report()
    print("roundtrip problems =", len(probs))
    for p in probs[:20]:
        print("   ", p)
    ev = m.export_eval_report()
    print(ev.splitlines()[-2])
    print("---- validate ----")
    for lvl, msg in m.validate()[:20]:
        print("[%s] %s" % (lvl, msg))
    print("---- C9 / C6 / B7 / P7 ----")
    for name in ("C9", "C6", "B7", "P7", "G1"):
        outs = m.edges_of(name, True)
        print("%-4s 出边: %s" % (name, ", ".join(
            "%s(%.0f/%.0f/%s)" % (e.to, m.ang(e) or 0, m.step(e) or 0, e.func) for e in outs)))
