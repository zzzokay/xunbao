# -*- coding: utf-8 -*-
"""
"转弯前补偿距离"改造的校验（只读 + 临时文件，不进固件）。

本机没有主机 C 编译器、WSL 无发行版、arm-none-eabi-gdb 也没有 `target sim`，
**无法在 PC 上执行 ARM 代码**，所以不做运行期验证，而做两件可判定的事：

  1. 保真性：从 Navigation/map.c 抽取 GetForwardDistanceBeforeTurn() 与 kTurnTbl[]，
     断言抽取结果与原函数**仅差 5 处已声明替换 + 1 处表扫描展开**，且**可逆还原后逐字一致**。
     ⇒ 保证"校验对象就是真代码"，而不是手抄副本。
  2. 语法：把抽出的真实代码 + 逐例调用，用 arm-none-eabi-gcc -Wall -Wextra 编译。
  3. 数值：python 侧按同一套公式独立算出用例期望值并打印（供人工复核 / 实车对照）。

  python scripts/analyze/_tmp_probe.py
"""
import os, re, math, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, 'Navigation', 'map.c')
src = open(SRC, encoding='utf-8').read()

def grab(pat, what):
    m = re.search(pat, src, re.S)
    assert m, 'grab failed: ' + what
    return m.group(1)

macros   = grab(r'(#define TURN_D_CRIGHT.*?#define TURN_GATE_CM\s*\([^)]*\))', 'TURN macros')
tbl_code = grab(r'(static const struct \{ u8 last, now, next; float dist; \} kTurnTbl\[\] = \{.*?\};)', 'kTurnTbl')
func_src = grab(r'(static float GetForwardDistanceBeforeTurn\(u8 last, u8 now, u8 next\)\s*\{.*?\n\})',
                'GetForwardDistanceBeforeTurn')
print('[1] 从 %s 抽取：TURN 宏 %d 行 / kTurnTbl %d 行 / 函数体 %d 行'
      % (os.path.relpath(SRC, ROOT).replace('\\', '/'), macros.count('\n') + 1,
         tbl_code.count('\n') + 1, func_src.count('\n') + 1))

# ---------- 节点名 → 编号：按 C 的真实枚举规则（注释掉的成员不占编号） ----------
maph = open(os.path.join(ROOT, 'Navigation', 'map.h'), encoding='utf-8').read()
enum_body = re.search(r'enum MapNode \{(.*?)\n\};', maph, re.S).group(1)
enum_body = re.sub(r'//[^\n]*', '', enum_body)          # ⚠️ 必须先剥注释再切逗号
enum_body = re.sub(r'/\*.*?\*/', '', enum_body, flags=re.S)
NAMES = [x.strip() for x in enum_body.split(',') if x.strip()]
NUM = {n: i for i, n in enumerate(NAMES)}
assert NUM.get('S1') == 0 and NUM['N3'] < NUM['N4'] < NUM['N5'] < NUM['N8'], '枚举解析异常'
print('[2] map.h 枚举 %d 个真实成员（%s=%d … %s=%d）；抽查 N4=%d N8=%d P8=%d B11=%d'
      % (len(NAMES), NAMES[0], NUM[NAMES[0]], NAMES[-1], NUM[NAMES[-1]],
         NUM['N4'], NUM['N8'], NUM['P8'], NUM['B11']))
print('    ⚠️ 与 project_reference.md §9.2 的编号表不一致（那份是旧版），以 map.h 为准')
node_defs = ['#define %-6s %d' % (n, NUM[n]) for n in NAMES]

# ---------- 表行 ----------
rows = re.findall(r'\{\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*([-\d.]+)\s*\}', tbl_code)
assert rows, 'kTurnTbl 解析为空'
print('[3] kTurnTbl %d 行：%s' % (len(rows), ', '.join('%s->%s->%s=%s' % r for r in rows)))

# ---------- 保真性：恰好这 5 处替换，且可逆 ----------
SUBS = [
    ('static float GetForwardDistanceBeforeTurn(u8 last, u8 now, u8 next)',
     'static float calc_src(u8 last, u8 now, u8 next, u8 IN_FUNC, u16 IN_STEP, float PHI, u8 arrive_method)'),
    ('fabsf(need2turn(nodes.nowNode.angle, nodes.nextNode.angle))', 'PHI'),
    ('const NODE *in = Node_Lookup(last);', '/* 入边属性由参数给出 */'),
    ('in->function', 'IN_FUNC'),
    ('in->step', 'IN_STEP'),
]
func_code = func_src
for a, b in SUBS:
    assert a in func_code, '保真性失败：函数体里找不到待替换片段 %r' % a
    func_code = func_code.replace(a, b)

scan_pat = re.compile(
    r'for \(i = 0; i < \(u8\)\(sizeof\(kTurnTbl\) / sizeof\(kTurnTbl\[0\]\)\); i\+\+\)\s*'
    r'\{.*?\n\t\}', re.S)
m = scan_pat.search(func_src)
assert m, '保真性失败：找不到 kTurnTbl 扫描块'
scan_orig = m.group(0)

def fv(v):
    return ('%sf' % v) if ('.' in str(v)) else ('%s.0f' % v)
def tbl_expr():
    e = '0.0f'
    for (l, n, x, v) in rows:
        e = '((last==%s && now==%s && next==%s) ? %s : %s)' % (l, n, x, fv(v), e)
    return e
def found_expr():
    e = '0'
    for (l, n, x, v) in rows:
        e = '((last==%s && now==%s && next==%s) ? 1 : %s)' % (l, n, x, e)
    return e
repl = 'meas  = %s;\n\tfound = %s;\n\t' % (tbl_expr(), found_expr())
func_code, n_scan = scan_pat.subn(lambda mm: repl, func_code, count=1)
assert n_scan == 1, '保真性失败：kTurnTbl 扫描块替换命中 %d 次' % n_scan

# 可逆还原（`in->step` 是 `u16 IN_STEP` 的子串，所以按整体替换做还原）
back = func_code.replace(repl, scan_orig)
for a, b in SUBS:
    back = back.replace(b, a)
assert back == func_src, '保真性失败：可逆还原后与原文不一致'
print('[4] 保真性 ✓ 仅差 %d 处已声明替换 + 1 处表扫描展开；可逆还原逐字一致' % len(SUBS))

# ---------- 用例与期望值（python 侧同式独立计算） ----------
L, GATE, PI_F = 19.0, 5.0, 3.14159265
DMAP = {11: 11.0, 3: -4.0, 1: -5.0}          # ARRIVE_CRIGHT / CLEFT / DLEFT
NONE, DOOR = 1, 13
MEAS = {(NUM[l], NUM[n], NUM[x]): float(v) for (l, n, x, v) in rows}

def expect(last, now, nxt, func, step, phi, method):
    meas = MEAS.get((last, now, nxt))
    ok_rule = (func in (NONE, DOOR)) and step >= 20 and 100.0 <= phi < 178.0
    if ok_rule:
        c = L * (1.0 - math.cos(phi * PI_F / 180.0)) + DMAP.get(method, -4.0)
        if meas is None or abs(c - meas) <= GATE:
            return c, ('T2 公式(无实测)' if meas is None else 'T2 公式(过闸门)')
    if meas is not None:
        return meas, 'T1 实测'
    return 19.0, 'T3 默认19'

CASES = [
    (NUM['C4'], NUM['N20'], NUM['P8'],  NONE, 170, 155.0, 11, '闸门挡回：公式47.2 vs 实测35'),
    (NUM['N4'], NUM['N3'],  NUM['N8'],  NONE, 108, 145.0,  1, '闸门挡回：公式29.6 vs 实测20'),
    (NUM['N8'], NUM['N5'],  NUM['N4'],  DOOR, 100, 145.0,  3, '闸门挡回：公式30.6 vs 实测36'),
    (NUM['N10'],NUM['N9'],  NUM['B9'],  NONE, 156, 165.0, 11, '过闸门：实测48 vs 公式48.4'),
    (NUM['N8'], NUM['N3'],  NUM['N4'],  DOOR, 100, 145.0,  3, '过闸门：实测30 vs 公式30.6'),
    (NUM['N3'], NUM['N4'],  NUM['B2'],  NONE, 130, 140.0,  3, '过闸门：实测30 vs 公式29.6'),
    (NUM['N20'],NUM['C4'],  NUM['B11'], NONE, 180, 125.0,  3, '过闸门：实测25 vs 公式25.9'),
    (NUM['N5'], NUM['N8'],  NUM['N12'], DOOR, 100, 110.0,  1, '过闸门：实测20 vs 公式20.5'),
    (NUM['S1'], NUM['N3'],  NUM['S1'],  NONE, 216, 175.0,  1, '无实测 → 公式'),
    (NUM['B2'], NUM['N1'],  NUM['B2'],  NONE,  40, 170.0, 11, '无实测 → 公式'),
    (NUM['N6'], NUM['N5'],  NUM['N6'],  NONE, 114, 100.0,  1, '无实测 → 公式'),
    (NUM['C4'], NUM['N20'], NUM['C4'],  NONE, 170, 170.0, 11, '无实测 → 公式'),
    (NUM['P3'], NUM['N3'],  NUM['N8'],  NONE, 246,  35.0,  2, 'T3 转弯<100 → 用实测6'),
    (NUM['C7'], NUM['C8'],  NUM['B11'], NONE, 108, 180.0,  0, 'T3 178°+无实测 → 默认19'),
    (NUM['B2'], NUM['N4'],  NUM['B2'],  NONE,  12, 180.0,  0, 'T3 step<20+无实测 → 默认19'),
    (NUM['B3'], NUM['N2'],  NUM['P2'],  NONE,  40, 180.0,  0, 'T3 障碍+无实测 → 默认19'),
    (NUM['N1'], NUM['P1'],  NUM['N1'],  NONE, 104, 180.0,  0, 'T3 无实测+180° → 默认19'),
    (NUM['B8'], NUM['N9'],  NUM['C3'],  NONE,   1, 160.0,  3, 'T3 step=1 → 用实测0'),
    (NUM['B9'], NUM['N7'],  NUM['P6'],  NONE,   5, 170.0,  1, 'T3 step=5 → 用实测25'),
]

calls, table = [], []
for i, (last, now, nxt, func, step, phi, method, why) in enumerate(CASES):
    exp, tag = expect(last, now, nxt, func, step, phi, method)
    calls.append('\tacc += calc_src(%d, %d, %d, %d, %d, %.1ff, %d);   /* %s | 期望 %.2f | %s */'
                 % (last, now, nxt, func, step, phi, method, tag, exp, why))
    table.append((i, tag, phi, step, func, method, exp, why))

probe = (
    '/* AUTO-GENERATED by scripts/analyze/_tmp_probe.py —— 离线校验用，不进固件、不进 Keil 工程。\n'
    ' * 下面的 TURN 宏 / kTurnTbl / 函数体**逐字抽取自 Navigation/map.c**（脚本里有可逆的保真性断言）。\n'
    ' * 编译：arm-none-eabi-gcc -std=c99 -Wall -Wextra -O0 -c _probe_gen.c\n'
    ' * 说明：只做语法与保真性校验，不在 PC 上执行（本机无主机编译器 / 无 qemu / 无 gdb-sim）。 */\n'
    '#include <math.h>\n'
    'typedef unsigned char u8;\ntypedef unsigned short u16;\ntypedef unsigned int u32;\n\n'
    'enum { ARRIVE_NONE=0, ARRIVE_DLEFT, ARRIVE_DRIGHT, ARRIVE_CLEFT, ARRIVE_MCLEFT,\n'
    '       ARRIVE_MCRIGHT, ARRIVE_CRIGHT, ARRIVE_MORELED, ARRIVE_AWHITE,\n'
    '       ARRIVE_MUL2SING, ARRIVE_MUL2MUL };\n'
    '#define NONE 1\n#define DOOR 13\n'
    'typedef struct _node { u8 nodenum; u32 flag; float angle; u16 step; float speed; u8 function; } NODE;\n\n'
    '/* ===== 节点编号（按 map.h 的 enum MapNode 真实规则）===== */\n'
    + '\n'.join(node_defs) + '\n\n'
    '/* ===== 以下逐字来自 Navigation/map.c ===== */\n'
    + macros + '\n\n' + tbl_code + '\n\n' + func_code + '\n\n'
    '/* ===== 逐例调用（编译检查类型/语法）===== */\n'
    'volatile float probe_acc;\n'
    'void probe_calls(void)\n{\n\tfloat acc = 0.0f;\n'
    + '\n'.join(calls) + '\n\tprobe_acc = acc;\n}\n'
)

out = os.path.join(HERE, '_probe_gen.c')
open(out, 'w', encoding='utf-8').write(probe)

r = subprocess.run(['arm-none-eabi-gcc', '-std=c99', '-Wall', '-Wextra', '-O0', '-c',
                    '-o', os.path.join(HERE, '_probe_gen.o'), out],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
print('[5] 生成 %s；arm-none-eabi-gcc -c exit=%d' % (os.path.basename(out), r.returncode))
for s in (r.stdout, r.stderr):
    if s and s.strip():
        print(s.strip())
print()
print('%-4s %-24s %6s %5s %-6s %-10s %8s  %s'
      % ('#', '类别', 'phi', 'step', 'func', 'method', '期望值', '说明'))
for (i, tag, phi, step, func, method, exp_v, why) in table:
    print('%-4d %-24s %6.1f %5d %-6d %-10d %8.2f  %s' % (i, tag, phi, step, func, method, exp_v, why))
print()
ok = r.returncode == 0
print('结论：保真性 + 语法 %s' % ('PASS' if ok else 'FAIL'))
if ok:
    print('（数值正确性由 python 侧同式独立计算，见上表；实车对比才是最终判据）')
sys.exit(0 if ok else 1)
