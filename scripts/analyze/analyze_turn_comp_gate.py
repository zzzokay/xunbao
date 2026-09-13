# -*- coding: utf-8 -*-
"""
临时分析（只看不改）：加上"5cm 闸门"后重算。

规则（最终版）：
  Tier1  表里有这条三元组                     → 用实测值
  Tier2  规则命中 且 |公式 − 实测| <= 5cm     → 用公式
  Tier3  其它                                 → 保持原默认 19
"""
import re, os, math, statistics

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
exec(open(os.path.join(HERE, 'analyze_turn_comp_base.py'), encoding='utf-8').read().split('# ---------------- 5.')[0])

FLAT = {'NONE', 'DOOR'}
GATE = 5.0
def step_of(e):
    s = str(e)
    for k, v in MAC.items(): s = re.sub(r'\b%s\b' % re.escape(k), ('(%r)' % v), s)
    try: return float(eval(s))
    except Exception: return float('nan')
def med(v): return sorted(v)[len(v) // 2]
def n2t(a, b):
    d = b - a
    while d > 180: d -= 360
    while d <= -180: d += 360
    return d

T1, T1m = {}, {}
for r in rows:
    r['m'] = r['cand'][0] if r['cand'] else 'NONE'
    a, b, c = r['tri'].split('->')
    T1[(a, b, c)] = r['v']; T1m[(a, b, c)] = r['m']
    e_in = next((x for x in edges if x['frm'] == a and x['to'] == b), None)
    r['func_in'] = e_in['fun'] if e_in else '?'
    r['stepn'] = step_of(e_in['step']) if e_in else float('nan')
    r['elig'] = (r['func_in'] in FLAT) and (r['stepn'] >= 20) and (100 <= r['phi'] < 178)

elig = [r for r in rows if r['elig']]
print('规则命中的实测条目（用于定 L 和 d）: %d 条' % len(elig))

def build(L):
    d = {}
    for r in elig: d.setdefault(r['m'], []).append(r['v'] - L*(1-math.cos(math.radians(r['phi']))))
    dmed = {k: med(v) for k, v in d.items()}
    dfl = med([x for v in d.values() for x in v])
    return dmed, dfl

print('\n' + '=' * 100)
print('一、L 扫描：看哪条会被 5cm 闸门挡住')
print('=' * 100)
print('%-5s %-9s %s' % ('L', '闸门挡掉', '挡掉的条目(实测→公式, 差)'))
for L in [10.0, 12.0, 14.0, 16.0, 17.0, 18.0, 19.0, 20.0]:
    dmed, dfl = build(L)
    blocked = []
    for r in elig:
        f = L*(1-math.cos(math.radians(r['phi']))) + dmed.get(r['m'], dfl)
        if abs(f - r['v']) > GATE: blocked.append((r['tri'], r['v'], f))
    print('%-5.1f %-9d %s' % (L, len(blocked),
          '  '.join('%s(%.0f→%.1f,%+.1f)' % (t, v, f, f-v) for t, v, f in blocked)))

L = 19.0
dmed, dfl = build(L)
print('\n选定 L=%.1f   d(判据)=%s   d(缺省)=%+.0f' % (
    L, ' '.join('%s:%+.0f' % (k, dmed[k]) for k in sorted(dmed, key=lambda z: -dmed[z])), dfl))

def formula(phi, m): return L*(1-math.cos(math.radians(phi))) + dmed.get(m, dfl)

print('\n' + '=' * 100)
print('二、规则命中的 9 条实测条目：闸门判定')
print('=' * 100)
print('%-18s %6s %-9s %8s %8s %8s  %s' % ('三元组', '转弯', '判据', '实测', '公式', '差', '闸门'))
for r in sorted(elig, key=lambda z: -z['phi']):
    f = formula(r['phi'], r['m'])
    ok = abs(f - r['v']) <= GATE
    print('%-18s %6.0f %-9s %8.0f %8.1f %+8.1f  %s' % (
        r['tri'], r['phi'], r['m'], r['v'], f, f - r['v'], '✓通过' if ok else '✗挡住→保留原值'))

# ---- 枚举全部停车转组合，套用最终规则 ----
def branch(e_in, phi):
    return 'stop' if (('STOPTURN' in e_in['flag'] and phi > 30) or phi >= 90) else 'gyro'
def calc_ok(e_in, phi):
    return (e_in['fun'] in FLAT) and (step_of(e_in['step']) >= 20) and (100 <= phi < 178)

allt = []
for e_in in edges:
    try: a1 = float(MAC.get(e_in['ang'], e_in['ang']))
    except Exception: continue
    for e_out in edges:
        if e_out['frm'] != e_in['to']: continue
        try: a2 = float(MAC.get(e_out['ang'], e_out['ang']))
        except Exception: continue
        phi = abs(n2t(a1, a2))
        if branch(e_in, phi) == 'stop': allt.append((e_in, e_out, phi))

res = []
for (e_in, e_out, phi) in allt:
    key = (e_in['frm'], e_in['to'], e_out['to'])
    m = next((n for (n, b) in METHODS if any(FLAGV.get(t.strip(), 0) & b for t in e_in['flag'].split('|'))), 'NONE')
    f = formula(phi, m)
    if key in T1:
        if calc_ok(e_in, phi) and abs(f - T1[key]) <= GATE:
            res.append((key, phi, m, f, 'T2 公式', ''))
        else:
            why = '实测值，已保留'
            if calc_ok(e_in, phi): why = '|公式−实测|=%.1f>5，保留原值' % abs(f - T1[key])
            res.append((key, phi, m, float(T1[key]), 'T1 实测', why))
    elif calc_ok(e_in, phi):
        res.append((key, phi, m, f, 'T2 公式', '原本吃 19'))
    else:
        why = ('障碍/平台' if e_in['fun'] not in FLAT else
               ('step<20' if step_of(e_in['step']) < 20 else
                ('180°折返' if phi >= 178 else '转弯<100°')))
        res.append((key, phi, m, 19.0, 'T3 默认19', why))

n2 = sum(1 for r in res if r[4].startswith('T2'))
n1 = sum(1 for r in res if r[4].startswith('T1'))
n3 = sum(1 for r in res if r[4].startswith('T3'))
print('\n' + '=' * 100)
print('三、最终覆盖率（停车转组合共 %d 个）' % len(res))
print('=' * 100)
print('  Tier1 实测值      : %3d (%.0f%%)' % (n1, 100*n1/len(res)))
print('  Tier2 公式算出    : %3d (%.0f%%)  ← 这些原本一律吃 19' % (n2, 100*n2/len(res)))
print('  Tier3 保留默认 19 : %3d (%.0f%%)' % (n3, 100*n3/len(res)))

print('\n' + '=' * 100)
print('四、T2 最终清单（公式算出、且过 5cm 闸门）')
print('=' * 100)
print('%-20s %6s %-9s %8s' % ('三元组', '转弯', '判据', 'Δ'))
for key, phi, m, v, tier, why in sorted([r for r in res if r[4].startswith('T2')], key=lambda z: -z[1]):
    print('%-20s %6.0f %-9s %8.1f' % ('%s->%s->%s' % key, phi, m, v))

print('\n' + '=' * 100)
print('五、被闸门挡下来的条目（保留原值）')
print('=' * 100)
for key, phi, m, v, tier, why in res:
    if '闸门' in why or '>5' in why:
        print('  %-20s 转弯=%3.0f  %s' % ('%s->%s->%s' % key, phi, why))

print('\n' + '=' * 100)
print('六、安全检查：T2 算出来的值都在合理区间吗（0~70cm，且不超过"下一段长度"）')
print('=' * 100)
bad = []
for key, phi, m, v, tier, why in res:
    if not tier.startswith('T2'): continue
    if v < 0 or v > 70: bad.append((key, phi, v, '越界'))
print('  越界/为负的: %d 条' % len(bad))
for k, p, v, w in bad: print('    %s->%s->%s 转弯=%.0f Δ=%.1f %s' % (k[0], k[1], k[2], p, v, w))
vals = sorted(v for _, _, _, v, t, _ in res if t.startswith('T2'))
print('  T2 值分布: min=%.1f 中位=%.1f max=%.1f' % (vals[0], med(vals), vals[-1]))
print('  对比：T3 默认 19；T1 实测范围 %.0f~%.0f' % (min(T1.values()), max(T1.values())))

print('\n' + '=' * 100)
print('七、分档统计：每个 Δ 值区间有多少条')
print('=' * 100)
import collections
c = collections.Counter()
for _, _, _, v, t, _ in res:
    if t.startswith('T2'): c[int(v // 10) * 10] += 1
for k in sorted(c): print('  %2d~%2d cm : %d 条' % (k, k + 9, c[k]))
