# -*- coding: utf-8 -*-
"""
临时分析（只看不改）：检验"step（本段里程长度）"是不是被硬补偿吸收掉的第二变量。
map.c 的到达检测启动条件：里程 >= 0.7 * nowNode.step（门节点 0.8）。
如果 step 很小(1~18cm)，0.7*step 只有 1~13cm —— 车会"按里程到位"，根本不是按视觉检测到的线到位。
"""
import re, os, math, statistics

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
exec(open(os.path.join(HERE, 'analyze_turn_comp_base.py'), encoding='utf-8').read().split('# ---------------- 5.')[0])

def step_of(e):
    s = str(e)
    for k, v in MAC.items(): s = re.sub(r'\b%s\b' % re.escape(k), ('(%r)' % v), s)
    try: return float(eval(s))
    except Exception: return float('nan')
SPEED = {'SPEED0':25, 'SPEED1':36, 'SPEED2':45, 'SPEED25':55, 'SPEED3':60, 'SPEED4':70, 'SPEED5':75}
for r in rows:
    r['stepn'] = step_of(r['step']); r['m'] = r['cand'][0] if r['cand'] else 'NONE'
    r['a'], r['b'], r['c'] = r['tri'].split('->')
    e_in = next((x for x in edges if x['frm'] == r['a'] and x['to'] == r['b']), None)
    r['spd'] = SPEED.get(e_in['spd'], float('nan')) if e_in else float('nan')
    r['func_in'] = e_in['fun'] if e_in else '?'

def pearson(xs, ys):
    n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
    sx = math.sqrt(sum((x-mx)**2 for x in xs)); sy = math.sqrt(sum((y-my)**2 for y in ys))
    return 0.0 if sx == 0 or sy == 0 else sum((x-mx)*(y-my) for x, y in zip(xs, ys))/(sx*sy)

V = [r['v'] for r in rows]
print('=' * 104)
print('一、相关性')
print('=' * 104)
for nm, f in [('入边 step', lambda r: r['stepn']), ('入边速度', lambda r: r['spd']),
              ('1-cosφ', lambda r: 1-math.cos(math.radians(r['phi']))), ('转弯角', lambda r: r['phi'])]:
    xs = [f(r) for r in rows]
    print('  %-10s Pearson=%+.3f' % (nm, pearson(xs, V)))

print('\n' + '=' * 104)
print('二、按 step 分档看补偿值（step 小 = 车靠里程到位，不是靠视觉检测到位）')
print('=' * 104)
buckets = [('<=18cm（里程到位）', lambda s: s <= 18), ('19~60cm', lambda s: 18 < s <= 60),
           ('61~130cm', lambda s: 60 < s <= 130), ('>130cm', lambda s: s > 130)]
for nm, f in buckets:
    sel = [r for r in rows if f(r['stepn'])]
    if sel:
        print('  %-18s n=%2d  值=%s  中位=%.0f' % (
            nm, len(sel), [int(r['v']) for r in sorted(sel, key=lambda z: z['stepn'])],
            statistics.median([r['v'] for r in sel])))

print('\n' + '=' * 104)
print('三、区分"两类点"：')
print('    A 类：step 足够大（>=19cm）→ 到达是靠视觉检测到的线，补偿 = 几何差值')
print('    B 类：step <= 18cm → 到达是靠里程 0.7*step 触发的，补偿里混了"段长误差"')
print('=' * 104)
A = [r for r in rows if r['stepn'] > 18]
B = [r for r in rows if r['stepn'] <= 18]
def stat(sel, nm):
    if not sel: return
    vs = [r['v'] for r in sel]
    print('  %-6s n=%2d  值=%s' % (nm, len(sel), [int(v) for v in sorted(vs)]))
    # 每组内 值 与 1-cosφ 的相关
    print('         值 vs 1-cosφ  Pearson=%+.3f' % pearson([1-math.cos(math.radians(r['phi'])) for r in sel], vs))
stat(A, 'A类'); stat(B, 'B类')

print('\n  A 类逐条（看是不是干净的 几何关系）:')
print('  %-18s %5s %6s %6s %8s %8s' % ('三元组', '值', '转弯', 'step', '1-cosφ', '值/(1-c)'))
for r in sorted(A, key=lambda z: -z['phi']):
    g = 1-math.cos(math.radians(r['phi']))
    print('  %-18s %5.0f %6.0f %6.0f %8.3f %8.1f' % (r['tri'], r['v'], r['phi'], r['stepn'], g, r['v']/g))
print('\n  B 类逐条:')
print('  %-18s %5s %6s %6s %8s' % ('三元组', '值', '转弯', 'step', '0.7*step'))
for r in sorted(B, key=lambda z: z['stepn']):
    print('  %-18s %5.0f %6.0f %6.0f %8.1f' % (r['tri'], r['v'], r['phi'], r['stepn'], 0.7*r['stepn']))

print('\n' + '=' * 104)
print('四、只用 A 类（视觉到位的那批）重拟合 判据+夹角，看能不能闭合')
print('=' * 104)
def med(v): return sorted(v)[len(v)//2]
def loo(keep, Ls, keyf, label):
    best = None
    for L in Ls:
        base = lambda r: L*(1-math.cos(math.radians(r['phi'])))
        def pred(r, rest):
            sel = [x['v']-base(x) for x in rest if keyf(x) == keyf(r)]
            return base(r) + (med(sel) if sel else med([x['v'] for x in rest]))
        e = [abs(pred(r, keep[:i]+keep[i+1:])-r['v']) for i, r in enumerate(keep)]
        v = sum(e)/len(e)
        if best is None or v < best[0]: best = (v, L)
    L = best[1]
    base = lambda r: L*(1-math.cos(math.radians(r['phi'])))
    d = {}
    for r in keep: d.setdefault(keyf(r), []).append(r['v']-base(r))
    dmed = {k: med(v) for k, v in d.items()}
    ae = [abs(base(r)+dmed[keyf(r)]-r['v']) for r in keep]
    print('  %-34s n=%2d L=%4.1f  训练MAE=%5.2f LOO-MAE=%5.2f' % (label, len(keep), L, sum(ae)/len(ae), best[0]))
    return L, dmed
Ls = [x*0.5 for x in range(0, 161)]
loo(A, Ls, lambda r: r['m'], 'A类: 判据+夹角')
loo(A, Ls, lambda r: 'ALL', 'A类: 只有夹角')
loo(rows, Ls, lambda r: r['m'], '全部: 判据+夹角')
