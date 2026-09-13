# -*- coding: utf-8 -*-
"""
转弯补偿改造的**静态自检**（不编译、不依赖 Keil）：把最容易出错的地方逐条查一遍。
本机没有主机 C 编译器，所以能自动查的都查掉，剩下的才交给 Keil。

  python scripts/analyze/analyze_turn_comp_selfcheck.py
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
def rd(p): return open(os.path.join(ROOT, p), encoding='utf-8', errors='replace').read()

mapc = rd('Navigation/map.c')
maph = rd('Navigation/map.h')
taskc = rd('Task/ArriveDetect_task.c')
taskh = rd('Task/ArriveDetect_task.h')
cfgh = rd('Mission/config.h')

fails = []
def chk(cond, ok_msg, bad_msg):
    print(('  [OK]   ' if cond else '  [FAIL] ') + (ok_msg if cond else bad_msg))
    if not cond: fails.append(bad_msg)

print('=== 1. 符号只能有一处定义（L6200E 就是这么来的）===')
defs = []
for p in ('Navigation/map.c', 'Task/ArriveDetect_task.c', 'Mission/barrier.c'):
    for i, ln in enumerate(rd(p).splitlines(), 1):
        if re.match(r'\s*(volatile\s+)?uint8_t\s+arrive_method\s*=', ln):
            defs.append('%s:%d' % (p, i))
chk(len(defs) == 1, 'arrive_method 定义点 1 处（%s）' % defs[0],
    'arrive_method 定义点 %d 处：%s（必须恰好 1 处）' % (len(defs), defs))

print('=== 2. 声明可见性 ===')
chk('extern volatile uint8_t arrive_method;' in maph, 'map.h 有 extern 声明', 'map.h 缺 extern 声明')
chk(re.search(r'#include\s*"map\.h"', mapc) is not None, 'map.c include 了 map.h（能拿到 ARRIVE_* 与 extern）',
    'map.c 没 include map.h')
chk(re.search(r'#include\s*"map\.h"', taskc) is not None, 'ArriveDetect_task.c include 了 map.h（能拿到 ARRIVE_*）',
    'ArriveDetect_task.c 没 include map.h')
chk(re.search(r'#include\s*"config\.h"', maph) is not None, 'map.h include 了 config.h（TURN_CALC_ENABLE 可见）',
    'map.h 没 include config.h → TURN_CALC_ENABLE 不可见')
chk(re.search(r'#include\s*[<"]math\.h[>"]', mapc) is not None, 'map.c include 了 math.h（cosf/fabsf）', 'map.c 缺 math.h')

print('=== 3. 判据枚举与函数原型一致 ===')
for name in ('ARRIVE_NONE', 'ARRIVE_DLEFT', 'ARRIVE_DRIGHT', 'ARRIVE_CLEFT', 'ARRIVE_MCLEFT',
             'ARRIVE_MCRIGHT', 'ARRIVE_CRIGHT', 'ARRIVE_MORELED', 'ARRIVE_AWHITE',
             'ARRIVE_MUL2SING', 'ARRIVE_MUL2MUL'):
    chk(name in maph, '%s 已在 map.h 定义' % name, '%s 未定义' % name)
proto = 'uint8_t deal_arrive(volatile SCANER *scaner, uint32_t node_flag, uint8_t *out_method);'
chk(proto in taskh, 'ArriveDetect_task.h 的 deal_arrive 原型已是三参', 'deal_arrive 原型没同步（仍是两参）')
chk(re.search(r'uint8_t\s+deal_arrive\s*\(\s*volatile SCANER \*scaner,\s*uint32_t node_flag,\s*uint8_t \*out_method\s*\)', taskc) is not None,
    'ArriveDetect_task.c 的 deal_arrive 定义是三参', 'deal_arrive 定义没改成三参')

print('=== 4. deal_arrive 的每处 return 1 都带上了判据 ===')
body = taskc[taskc.index('uint8_t deal_arrive'):]
r1 = re.findall(r'return 1;', body)
# 注意：复位语句是 *out_method = ARRIVE_NONE（未命中时），不能算进"命中的判据"
setm = re.findall(r'\*out_method\s*=\s*ARRIVE_(?!NONE)\w+', body)
chk(len(r1) == len(setm) == 10, 'return 1 共 %d 处、命中的判据赋值 %d 处（应各 10 处）' % (len(r1), len(setm)),
    'return 1 有 %d 处但命中判据只写了 %d 处（漏写会让公式用错 d）' % (len(r1), len(setm)))
chk(len(re.findall(r'\*out_method\s*=\s*ARRIVE_NONE', body)) == 1,
    '未命中时把 out_method 复位为 ARRIVE_NONE（1 处）',
    '未命中时没复位 out_method（或复位了多次）')

print('=== 5. 表里用到的节点号必须 < 实际节点数 ===')
eb = re.search(r'enum MapNode \{(.*?)\n\};', maph, re.S).group(1)
eb = re.sub(r'//[^\n]*', '', eb); eb = re.sub(r'/\*.*?\*/', '', eb, flags=re.S)
names = [x.strip() for x in eb.split(',') if x.strip()]
NUM = {n: i for i, n in enumerate(names)}
m = re.search(r'kTurnTbl\[\]\s*=\s*\{(.*?)\n\};', mapc, re.S)
rows = re.findall(r'\{\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*([-\d.]+)\s*\}', m.group(1)) if m else []
chk(len(rows) == 13, 'kTurnTbl 有 13 行', 'kTurnTbl 行数 = %d（应为 13）' % len(rows))
used = set()
for (a, b, c, v) in rows: used.update((a, b, c))
bad = [n for n in used if NUM.get(n, 999) >= len(names)]
chk(not bad, '表里 %d 个节点号全部 < %d（最大 %d）' % (len(used), len(names), max(NUM[n] for n in used)),
    '表里有越界/写错的节点名：%s' % bad)
chk('MAP_NODE_LIMIT' in mapc and re.search(r'#define\s+MAP_NODE_LIMIT\s+%d' % len(names), mapc) is not None,
    'MAP_NODE_LIMIT 已定义且等于真实节点数 %d' % len(names),
    'MAP_NODE_LIMIT 未定义或与真实节点数 %d 不符' % len(names))

print('=== 6. 不能引用不存在的符号 ===')
for sym in ('NAV_NODE_COUNT',):
    chk(sym not in mapc, 'map.c 未引用未定义的 %s' % sym, 'map.c 引用了不存在的 %s' % sym)
for sym in ('NAV_MAX_NODES',):
    chk(sym in rd('Navigation/nav_planner.h'), '%s 确有定义（nav_planner.h）' % sym, '%s 无定义' % sym)

print('=== 7. 公式实现细节 ===')
# Tier2 代码块：从 "#if TURN_CALC_ENABLE" 到该函数结尾的 "return 19;"
t2 = mapc[mapc.index('#if TURN_CALC_ENABLE'):mapc.index('return 19;', mapc.index('#if TURN_CALC_ENABLE'))]
# ⚠️ 必须**先剥注释**再查字符串：那段注释里正好写着"不能读 nodes.nowNode.step/function"，
#    不剥注释会把警示语本身当成违规（这个检查第一版就是这么误报的）。
t2c = re.sub(r'/\*.*?\*/', '', t2, flags=re.S)
t2c = re.sub(r'//[^\n]*', '', t2c)
chk('cosf(' in mapc, '用的是 cosf（单精度）', '没用 cosf')
chk(re.search(r'\bcos\s*\(', mapc) is None, '没有误用 double 版 cos', '发现 double 版 cos（M7 会拖慢）')
chk('#if TURN_CALC_ENABLE' in mapc and '#define TURN_CALC_ENABLE' in cfgh,
    'TURN_CALC_ENABLE 开关在 config.h 定义、在 map.c 生效', 'TURN_CALC_ENABLE 开关不完整')
chk('Node_Lookup(last)' in t2c and 'getNextConnectNode' not in t2c,
    'Tier2 用 Node_Lookup(last) 取入边原始属性（没误用 getNextConnectNode 当下标）',
    'Tier2 可能误用了 getNextConnectNode 的返回值当下标')
chk('nodes.nowNode.step' not in t2c and 'nodes.nowNode.function' not in t2c,
    'Tier2 没有读 nodes.nowNode.step/function，用的是 in->step / in->function（原始值）',
    'Tier2 读了 nodes.nowNode.step/function（会被 door_set_pass_node 改写，判断会错）')

print()
print('结果：%s' % ('全部通过 ✓' if not fails else ('%d 项失败 ✗' % len(fails))))
for f in fails: print('   - ' + f)
sys.exit(0 if not fails else 1)
