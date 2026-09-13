# -*- coding: utf-8 -*-
"""
临时分析（只看不改）：最终方案——"能算就算、不能算保留原值"，并给出完整影响面。

可算判据（三条同时满足）：
  R1 传感器仍在平地：入边 func ∈ {NONE, DOOR}
     （排除 QQB/SM/BHM/Hill/Bridge/BLBS/BLBL/View/… —— 板子离地，检测时刻不可预测）
  R2 到达由"视觉检测到线"触发：入边 step >= 20cm
     （step<=18cm 时 0.7*step 会提前放行，补偿实际在补段长）
  R3 进入停车原地转分支且几何项显著：|转弯| >= 100°
"""
import re, os, math, statistics

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
exec(open(os.path.join(HERE, 'analyze_turn_comp_base.py'), encoding='utf-8').read().split('# ---------------- 5.')[0])

FLAT = {'NONE', 'DOOR'}
def step_of(e):
    s = str(e)
    for k, v in MAC.items(): s = re.sub(r'\b%s\b' % re.escape(k), ('(%r)' % v), s)
    try: return float(eval(s))
    except Exception: return float('nan')

# 建立"补偿知识库"：现有生效条目
KNOW = {}
for r in rows:
    r['stepn'] = step_of(r['step']); r['m'] = r['cand'][0] if r['cand'] else 'NONE'
    a, b, c = r['tri'].split('->')
    e_in = next((x for x in edges if x['frm'] == a and x['to'] == b), None)
    r['func_in'] = e_in['fun'] if e_in else '?'
    r['R1'] = r['func_in'] in FLAT
    r['R2'] = r['stepn'] >= 20
    r['R3'] = r['phi'] >= 100
    r['calc'] = r['R1'] and r['R2'] and r['R3']
    KNOW[(a, b, c)] = r['v']

print('=' * 112)
print('一、修正判据后的分类')
print('=' * 112)
print('%-18s %5s %6s %-8s %6s  %-4s %-4s %-4s  %s' % ('三元组', '值', '转弯', '入边func', 'step', 'R1', 'R2', 'R3', '结论'))
for r in sorted(rows, key=lambda z: (not z['calc'], -z['phi'])):
    print('%-18s %5.0f %6.0f %-8s %6.0f  %-4s %-4s %-4s  %s' % (
        r['tri'], r['v'], r['phi'], r['func_in'], r['stepn'],
        '✓' if r['R1'] else '✗', '✓' if r['R2'] else '✗', '✓' if r['R3'] else '✗',
        '★可算' if r['calc'] else '保留原值 %.0f' % r['v']))
calc = [r for r in rows if r['calc']]
print('\n  可算 %d 条 / 保留原值 %d 条' % (len(calc), len(rows) - len(calc)))

print('\n' + '=' * 112)
print('二、可算的那批反解 L')
print('=' * 112)
Ls = []
for r in sorted(calc, key=lambda z: -z['phi']):
    g = 1 - math.cos(math.radians(r['phi'])); L = r['v'] / g; Ls.append(L)
    print('  %-18s 值=%3.0f 转弯=%3.0f  1-cosφ=%.3f  反解L=%5.1f  %s' % (r['tri'], r['v'], r['phi'], g, L, r['m']))
print('  L 中位=%.1f 均值=%.1f  范围 %.1f~%.1f' % (statistics.median(Ls), sum(Ls)/len(Ls), min(Ls), max(Ls)))

def med(v): return sorted(v)[len(v)//2]
L = 19.0
d = {}
for r in calc: d.setdefault(r['m'], []).append(r['v'] - L*(1-math.cos(math.radians(r['phi']))))
dmed = {k: med(v) for k, v in d.items()}
print('\n  取 L=19.0（与现有默认值一致），d(判据): %s' % ' '.join('%s:%+.0f' % (k, dmed[k]) for k in sorted(dmed, key=lambda z: -dmed[z])))
def formula(r):
    return L*(1-math.cos(math.radians(r['phi']))) + dmed.get(r['m'], med([x['v'] for x in calc]))

print('\n' + '=' * 112)
print('三、逐条：原值 / 公式 / 采用哪个 / 改用公式后变化多少')
print('=' * 112)
print('%-18s %5s %-8s %8s %8s  %-10s %8s' % ('三元组', '转弯', '判据', '原值', '公式', '采用', '变化'))
worst = []
for r in sorted(rows, key=lambda z: -z['phi']):
    f = formula(r)
    if r['calc']:
        use, src, delta = f, '★公式', f - r['v']
    else:
        use, src, delta = r['v'], '原值', 0.0
    worst.append((abs(delta), r['tri'], delta))
    print('%-18s %5.0f %-8s %8.0f %8.1f  %-10s %+8.1f' % (r['tri'], r['phi'], r['m'], r['v'], f, src, delta))

print('\n' + '=' * 112)
print('四、影响面：改用公式后，哪些点会明显变化（>5cm）')
print('=' * 112)
for a, t, dl in sorted(worst, reverse=True):
    if a > 5: print('  %-18s 变化 %+.1f cm' % (t, dl))
print('  其余变化都在 ±5cm 以内')

print('\n' + '=' * 112)
print('五、覆盖面扩大：现在"没有条目、只能吃默认 19"的组合，规则命中后能算出来吗')
print('=' * 112)

def n2t(a, b):
    dd = b - a
    while dd > 180: dd -= 360
    while dd <= -180: dd += 360
    return dd
def ang_of(e):
    v = e['ang']
    if v in ('ANGLE_N3N8',): return 145.0
    if v in ('ANGLE_N5N8',): return 35.0
    if v in ('ANGLE_N8N12',): return 145.0
    if v in ('ANGLE_N8N10',): return 35.0
    if v in ('ANGLE_N8N3',): return -35.0
    if v in ('ANGLE_N8N5',): return -145.0
    if v in ('ANGLE_N12N8',): return -35.0
    if v in ('ANGLE_N10N8',): return -145.0
    for k, vv in MAC.items():
        if v == k: return float(vv)
    try: return float(v)
    except Exception: return None

allt = []
for e_in in edges:
    ai = ang_of(e_in)
    if ai is None: continue
    for e_out in edges:
        if e_out['frm'] != e_in['to']: continue
        ao = ang_of(e_out)
        if ao is None: continue
        t = n2t(ai, ao)
        stop = 'STOPTURN' in e_in['flag']
        need_stop = (stop and abs(t) > 30) or abs(t) >= 90
        if not need_stop or abs(t) < 100: continue
        st = step_of(e_in['step'])
        allt.append(dict(tri='%s->%s->%s' % (e_in['frm'], e_in['to'], e_out['to']),
                         phi=abs(t), func=e_in['fun'], st=st, known=(e_in['frm'], e_in['to'], e_out['to']) in KNOW))
hit = [x for x in allt if x['func'] in FLAT and x['st'] >= 20]
print('  边表里需要"停车转且转弯>=100°"的组合共 %d 个' % len(allt))
print('  其中规则命中（平地 + step>=20）: %d 个（%.0f%%）' % (len(hit), 100*len(hit)/len(allt)))
print('  命中里"已有实测值"的: %d 个，其余 %d 个将首次获得一个算出来的值' % (
    sum(1 for x in hit if x['known']), sum(1 for x in hit if not x['known'])))
print('\n  规则命中但当前无实测值的组合（这些将首次不再吃默认 19）：')
for x in sorted([x for x in hit if not x['known']], key=lambda z: -z['phi'])[:25]:
    print('    %-18s 转弯=%3.0f 入边func=%-6s step=%3.0f' % (x['tri'], x['phi'], x['func'], x['st']))
