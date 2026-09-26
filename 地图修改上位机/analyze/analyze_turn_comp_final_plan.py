# -*- coding: utf-8 -*-
"""
临时分析（只看不改）：最终方案设计
  Tier 1  已有实测值        → 原样保留（0 误差，绝不覆盖）
  Tier 2  可算（规则命中）  → 用公式 Δ = L(1-cosφ) + d(判据)
  Tier 3  不可算            → 保留原来会走到的默认值（19 / 0）
并列出 Tier 2 与 Tier 3 具体覆盖哪些组合。
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

MACANG = {'ANGLE_N3N8': 145.0, 'ANGLE_N5N8': 35.0, 'ANGLE_N8N12': 145.0, 'ANGLE_N8N10': 35.0,
          'ANGLE_N8N3': -35.0, 'ANGLE_N8N5': -145.0, 'ANGLE_N12N8': -35.0, 'ANGLE_N10N8': -145.0}
def ang_of(e):
    v = e['ang']
    if v in MACANG: return MACANG[v]
    if v in MAC: return float(MAC[v])
    try: return float(v)
    except Exception: return None
def n2t(a, b):
    d = b - a
    while d > 180: d -= 360
    while d <= -180: d += 360
    return d

# Tier1：现有生效条目 + 其判据
T1, T1m = {}, {}
for r in rows:
    r['stepn'] = step_of(r['step']); r['m'] = r['cand'][0] if r['cand'] else 'NONE'
    a, b, c = r['tri'].split('->')
    T1[(a, b, c)] = r['v']
    T1m[(a, b, c)] = r['m']

# 可算的 9 条 → 定 L 和 d
calc = [r for r in rows if r['m'] and 1 - math.cos(math.radians(r['phi'])) > 0]
FLATROWS = []
for r in rows:
    a, b, c = r['tri'].split('->')
    e_in = next((x for x in edges if x['frm'] == a and x['to'] == b), None)
    if e_in and e_in['fun'] in FLAT and step_of(e_in['step']) >= 20 and r['phi'] >= 100 and r['phi'] < 178:
        FLATROWS.append(r)
L = 19.0
d = {}
for r in FLATROWS: d.setdefault(r['m'], []).append(r['v'] - L * (1 - math.cos(math.radians(r['phi']))))
def med(v): return sorted(v)[len(v) // 2]
DMED = {k: med(v) for k, v in d.items()}
DFALL = med([r['v'] - L * (1 - math.cos(math.radians(r['phi']))) for r in FLATROWS])
print('拟合结果: L=%.1f   d(判据)=%s   d(缺省)=%+.0f' % (
    L, ' '.join('%s:%+.0f' % (k, DMED[k]) for k in sorted(DMED, key=lambda z: -DMED[z])), DFALL))

def dist(phi, m):
    return L * (1 - math.cos(math.radians(phi))) + DMED.get(m, DFALL)

def rule(e_in, phi):
    """返回 (可算?, 原因, 判据)"""
    if e_in['fun'] not in FLAT:
        return False, '入边在障碍/平台上(func=%s)' % e_in['fun'], None
    if step_of(e_in['step']) < 20:
        return False, '入边 step=%.0fcm<20，里程提前放行' % step_of(e_in['step']), None
    if phi < 100:
        return False, '转弯只有 %.0f°，走陀螺不停车转分支' % phi, None
    if phi >= 178:
        return False, '接近 180° 原路折返', None
    return True, '平地+视觉到位+大角度', None

# 枚举全部停车转组合
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
        if not need_stop: continue
        allt.append((e_in, e_out, abs(t)))

def m_of(e_in):
    v = 0
    for tok in e_in['flag'].split('|'):
        v |= FLAGV.get(tok.strip(), 0)
    for (n, b) in METHODS:
        if v & b: return n
    return 'NONE'

t1 = t2 = t3 = 0
r2, r3 = [], []
for (e_in, e_out, phi) in allt:
    key = (e_in['frm'], e_in['to'], e_out['to'])
    if key in T1:
        t1 += 1; continue
    ok, why, _ = rule(e_in, phi)
    if ok:
        t2 += 1; r2.append((key, phi, m_of(e_in), dist(phi, m_of(e_in))))
    else:
        t3 += 1; r3.append((key, phi, why))

print('\n' + '=' * 108)
print('覆盖率（边表里所有"需要停车转"的组合，共 %d 个）' % len(allt))
print('=' * 108)
print('  Tier1 有实测值（原样保留）      : %3d 个 (%.0f%%)' % (t1, 100*t1/len(allt)))
print('  Tier2 可算（公式给出）          : %3d 个 (%.0f%%)' % (t2, 100*t2/len(allt)))
print('  Tier3 不可算（保留默认 19）     : %3d 个 (%.0f%%)' % (t3, 100*t3/len(allt)))

print('\n' + '=' * 108)
print('Tier2 明细：这些组合原本只能吃默认 19，现在能算出来')
print('=' * 108)
print('%-18s %6s %-9s %8s' % ('三元组', '转弯', '判据', '算得Δ'))
for key, phi, m, v in sorted(r2, key=lambda z: -z[1]):
    print('%-18s %6.0f %-9s %8.1f' % ('%s->%s->%s' % key, phi, m, v))

print('\n' + '=' * 108)
print('Tier3 明细：仍然只能保留原值，按原因归类')
print('=' * 108)
import collections
g = collections.defaultdict(list)
for key, phi, why in r3: g[why.split('(')[0].split('，')[0]].append((key, phi))
for why, lst in sorted(g.items(), key=lambda z: -len(z[1])):
    print('  %-46s %3d 个，例：%s' % (why, len(lst), ', '.join('%s->%s->%s' % k for k, _ in lst[:3])))

print('\n' + '=' * 108)
print('风险检查：Tier2 的公式值，和"万一其实有实测值"的差别（只在 9 条有名义值的上比）')
print('=' * 108)
print('%-18s %8s %8s %8s' % ('三元组', '原值', '公式', '差'))
for r in sorted(FLATROWS, key=lambda z: -z['phi']):
    f = dist(r['phi'], r['m'])
    print('%-18s %8.0f %8.1f %+8.1f' % (r['tri'], r['v'], f, f - r['v']))
