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
    mm = re.search(r"#define\s+USE_FIELD\s+([A-Za-z_]\w*)", src)
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
        m2 = re.match(r"^USE_FIELD\s*==\s*(\w+)$", e)
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


def write_use_field(new_field, path=PATH_CONFIG):
    """切换 config.h 的 USE_FIELD（FIELD_COMP / FIELD_SCHOOL）。

    只改 `#ifndef USE_FIELD` 块里那一行，不动其它。返回新 field_name。
    """
    if new_field not in ("FIELD_COMP", "FIELD_SCHOOL"):
        raise ParseError("场地只能是 FIELD_COMP 或 FIELD_SCHOOL，不是 %r" % new_field)
    src = open(path, encoding="utf-8").read()
    pattern = re.compile(r"(#ifndef\s+USE_FIELD\s*\n#define\s+USE_FIELD\s+)(\w+)(\s*\n#endif)")
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
             ("N3", "N8"), ("N8", "N3"), ("N3", "N10"), ("N10", "N3")]

# 宝物编号 -> 回程前要绕去取的平台（5/6 在东区已取过，见 plan_treasure_return）
TREASURE_PF = {2: "P1", 3: "P3", 4: "P4", 5: "P5", 6: "P6"}


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
                         else "；蓝额外放行 N10→N3（回程走 D5）")))
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
    """镜像 barrier.c:door() 的【回家路上过门】两个分支（D5_BACK: N10→N3、D4_BACK: N8→N3）。

    返回 (steps, hazards)：steps=[(门, 读灯的边, 灯状态, 判定, 动作)]；
    hazards=[提示文本]，例如"这个灯组合在 door() 里没有匹配分支"。
    """
    d2, d3, d4, d5 = doors[0], doors[1], doors[2], doors[3]
    steps, hazards = [], []

    # ---------- DOOR_D5_BACK：N10 -> N3 ----------
    if d5 == CAN_PASS:
        steps.append(("D5", "N10→N3", d5, "绿 → 过门",
                      "door_set_pass_node(N10,N3)（step=36, SPEED3），nowNode 落在 N3 ⇒ "
                      "update_route_by_door_1() = route_return_home(起点 N3, 门区 8 边全禁)"))
    elif d2 == ONE_WAY_PASS:
        steps.append(("D5", "N10→N3", d5, "非绿（else 分支；D2 是蓝、单相已用尽）→ 退回重读",
                      "route[0]=N3; route[1]=0xFF（door() 内部手写）+ door_retreat(N10,N8) "
                      "⇒ nowNode 变成 N10→N8 ⇒ 车由 N8→N3 在 N8→N3 上重读 D4"))
    elif d2 == NO_PASS and d3 == ONE_WAY_PASS:
        steps.append(("D5", "N10→N3", d5, "非绿（else 分支；D2 黑、D3 蓝已用尽）→ 退回",
                      "door_retreat(N10,N8) + 放行 N3↔N8 ⇒ update_route_by_door_2() "
                      "= route_return_home(起点 N8, 额外放行 N8→N3)"))
    else:
        steps.append(("D5", "N10→N3", d5, "非绿 → ⚠ door() 里没有匹配分支", "什么都不做"))
        hazards.append("D5 非绿时 door() 只处理「D2=蓝」或「D2=黑且 D3=蓝」两种组合；"
                       "当前组合两边都不满足 ⇒ 不置 cross_event、不改 route[] "
                       "⇒ Navigation() 会重跑同一段并再次触发 door()，**可能反复重读这扇门**。")

    # ---------- DOOR_D4_BACK：N8 -> N3 ----------
    if d4 == CAN_PASS:
        steps.append(("D4(回程)", "N8→N3", d4, "绿 → 过门",
                      "放行 N3↔N8；nowNode = N8→N3（step=36, SPEED3, function=NONE）+ "
                      "motor_pid_clear() ⇒ update_route_by_door_3() = route_return_home(起点 N3)"))
    else:
        steps.append(("D4(回程)", "N8→N3", d4, "非绿（else 分支：黑/蓝）→ 退回",
                      "先放行 N8↔N5（必须！否则 retreat 读到旧值会二次触发 door()）+ "
                      "door_retreat(N8,N5) ⇒ update_route_by_door_4() "
                      "= route_return_home(起点 N5)"))
    return steps, hazards


def door_read_hops(doors):
    """进门读灯时，**除了直接过门之外还要多走的节点**（退回重读），只挑边表里真实存在的边。

    第一轮 P1 之后的手写数组一律以 N12 结尾（= 在 N5→N12 上读 D2），所以这里返回的 hops
    直接接在 N12 后面即可拼成连续路径：
      D2 能过      → []                          （过门落在 N12）
      D2 黑、D3 能过 → ["N8"]                      （N12→N8 是真实边；物理上是退回后重走 N5→N8）
      D2 黑、D3 黑、D4 能过 → ["N8","N5","N4","N3","N8"]（N8→N5→N4→N3→N8 全是真实边）
    返回 (hops, enter_node, err)。
    """
    d2, d3, d4 = doors[0], doors[1], doors[2]
    if can_pass(d2):
        return [], "N12", None
    if can_pass(d3):
        return ["N8"], "N8", None
    if can_pass(d4):
        return ["N8", "N5", "N4", "N3", "N8"], "N8", None
    return [], None, "D2/D3/D4 全不能过 → 固件 barrier.c:door() 会 CarBrake_Stop()"


def door_back_chain(doors, door_edge):
    """回程在 `door_edge` 上撞到 BACK 门时，镜像 door() 的 D5_BACK / D4_BACK 分支。

    door_edge ∈ {("N10","N3"), ("N8","N3")}（这两条是"回家路上"读的门）。
    返回 (hops, start, allow, note)：
      hops  = 走 route_return_home 之前还要经过的节点（如退回 N8 后由 N8→N3 重读 D4）；
      start/allow 交给 door_return_home_waypoints()。
    ⚠️ 注意两个 BACK 分支的 else 是**"非绿"**（黑和蓝都走），不是只有黑。
    """
    d2, d3, d4, d5 = doors[0], doors[1], doors[2], doors[3]
    if door_edge == ("N10", "N3"):                       # DOOR_D5_BACK
        if d5 == CAN_PASS:
            return [], "N3", False, "D5 绿 ⇒ update_route_by_door_1()（起点 N3）"
        if d2 == ONE_WAY_PASS:
            # route[0]=N3; route[1]=0xFF ⇒ 退回 N8，再由 N8→N3 重读 D4（DOOR_D4_BACK）
            if d4 == CAN_PASS:
                return (["N8", "N3"], "N3", False,
                        "D5 非绿 + D2 蓝 ⇒ route[0]=N3、退回 N8 ⇒ N8→N3 重读 D4 得绿 ⇒ "
                        "update_route_by_door_3()（起点 N3）")
            return (["N8", "N3", "N5"], "N5", False,
                    "D5 非绿 + D2 蓝 ⇒ route[0]=N3、退回 N8 ⇒ N8→N3 重读 D4 非绿 ⇒ "
                    "退回 N5 ⇒ update_route_by_door_4()（起点 N5）")
        if d2 == NO_PASS and d3 == ONE_WAY_PASS:
            return ([], "N8", True,
                    "D5 非绿 + D2 黑 + D3 蓝 ⇒ 退回 N8 ⇒ update_route_by_door_2()"
                    "（起点 N8，放行 N8→N3）")
        return ([], "N3", False,
                "⚠ D5 非绿且 D2/D3 组合在 door() 里没有匹配分支（不置 cross_event，"
                "可能反复重读这扇门）——下面按 D5 绿的结果占位，仅作示意")
    # DOOR_D4_BACK：N8 → N3
    if d4 == CAN_PASS:
        return [], "N3", False, "D4 回程绿 ⇒ update_route_by_door_3()（起点 N3）"
    return (["N5"], "N5", False,
            "D4 回程非绿 ⇒ 放行 N8↔N5、退回 N5 ⇒ update_route_by_door_4()（起点 N5）")


def treasure_return_waypoints(start, doors, treasure):
    """镜像 plan_treasure_return()：在 P7/P8 读到宝物编号后的回程 wp。"""
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
        wp += ["N10", "N3"]      # 回程需经 D5
    else:
        return None, "D2/D3/D4 都不能过（固件会 CarBrake_Stop）"
    if treasure not in (5, 6):
        wp.append(TREASURE_PF[treasure])
    wp.append("P2")
    return wp, None


def door_return_home_waypoints(start, treasure, allow_N8_N3=False):
    """镜像 mission_planner.c:route_return_home()：门区 8 条边全禁 + wp={当前节点,[宝物平台],P2}。

    返回 (wp, blocked)，blocked 是规划时需封闭的 (from,to) 集合。
    allow_N8_N3=True 对应 door_2（D5 黑且 D3 蓝已用尽）额外放行 N8→N3，退回去重读 D4。
    """
    wp = [start]
    if treasure in (2, 3, 4):
        wp.append(TREASURE_PF[treasure])
    wp.append("P2")
    blocked = set(DOOR_ZONE)
    if allow_N8_N3:
        blocked.discard(("N8", "N3"))
    return wp, blocked


def round2_firmware_cruise(treasure):
    """固件 get_newroute() 里写死的第二轮巡游顺序（宝物=6 时反向 ⇒ 逆时针）。"""
    return ["P6", "P8", "P7", "P5"] if treasure == 6 else ["P5", "P7", "P8", "P6"]


def round2_waypoints(doors, treasure, cruise=None):
    """镜像 get_newroute()（USE_PLANNER_ROUTE=1）：第二轮完整 wp。

    doors = door_pass[0..3]（D2/D3/D4/D5）；treasure 只用来定巡游方向（6=逆时针）。
    cruise = 自定义巡游顺序（P5~P8 各一次，顺序就是走法）；None = 固件默认顺序。
    ⚠️ 门区那个"多保留的 N8"跟的是**巡游首站**：固件里就是 p6_first（首站=P6）才留，
       自定义顺序首站是 P6 时同理（平台交换后改顺序，门节点跟着变）。
    固件在这些组合下会 CarBrake_Stop，此时返回 (None, 原因)。
    """
    d2, d3, d4, d5 = doors[0], doors[1], doors[2], doors[3]
    if cruise is None:
        cruise = round2_firmware_cruise(treasure)
    else:
        cruise = list(cruise)
    tour_from_p6 = (cruise[0] == "P6")
    wp = ["N2", "P1", "P3", "P4", "N5"]
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
        try:
            m.turn = parse_turn_tables()
        except Exception as ex:                                    # noqa: BLE001
            m.turn = {"stop": [], "gyro": [], "consts": dict(TURN_CONST_DEFAULTS),
                      "calc_enable": None, "stop_default": TURN_STOP_DEFAULT,
                      "gyro_default": TURN_GYRO_DEFAULT,
                      "warnings": ["解析 map.c 的转弯补偿失败：%s" % ex]}
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
