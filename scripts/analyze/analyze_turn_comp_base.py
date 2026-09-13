# -*- coding: utf-8 -*-
"""
临时分析（只看不改）：用"判据 + 夹角 + 边残差"的方案去拟合 Navigation/map.c 现有硬补偿，
给出 MAE / 中位误差 / 最大误差 / 留一法(LOO) 交叉验证，判断这条路能拟合到什么程度。

物理一阶模型：
    车前进 Δ 后原地转 φ，让传感器板中心落回"新路段中心线"。
    Δ = L·(1 - cosφ)  +  方法项(判据命中时刻的固有提前量)  +  该节点的几何残差
"""
import re, os, math, itertools

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))

# ---------------- 1. 解宏 ----------------
def load_macros():
    txt = open(os.path.join(ROOT, 'Mission', 'config.h'), encoding='utf-8').read()
    txt += '\n' + open(os.path.join(ROOT, 'Navigation', 'map_message.h'), encoding='utf-8').read()
    lines = [re.sub(r'/\*.*?\*/', '', ln) for ln in txt.splitlines()]
    M = {'FIELD_COMP': 0, 'FIELD_SCHOOL': 1}
    raws = {}
    for ln in lines:
        m = re.match(r'\s*#define\s+(\w+)\s+(.+?)\s*$', ln)
        if not m: continue
        name, expr = m.group(1), m.group(2).strip()
        if name == 'ANGLE_REV' or '(' in name: continue
        raws[name] = expr
    for _ in range(12):
        changed = False
        for name, expr in list(raws.items()):
            if name in M: continue
            e = expr
            def rev(mm):
                a = mm.group(1)
                if a in M:
                    v = M[a]
                    return '(%r)' % ((v - 180) if v >= 0 else (v + 180))
                return mm.group(0)
            e = re.sub(r'ANGLE_REV\(\s*\(?\s*([A-Za-z0-9_]+)\s*\)?\s*\)', rev, e)
            for k, v in M.items():
                e = re.sub(r'\b%s\b' % re.escape(k), ('(%r)' % v), e)
            e = re.sub(r'(\d)f\b', r'\1', e)
            if re.fullmatch(r'[-+*/(). \d]+', e):
                try:
                    M[name] = eval(e); changed = True
                except Exception:
                    pass
        if not changed: break
    return M

MAC = load_macros()
def ang_expr(e):
    e = e.strip()
    m = re.fullmatch(r'ANGLE_REV\((.+)\)', e)
    if m:
        v = ang_expr(m.group(1))
        return None if v is None else ((v - 180) if v >= 0 else (v + 180))
    if e in MAC: return float(MAC[e])
    try: return float(e)
    except ValueError: return None

# ---------------- 2. 边表 ----------------
src = open(os.path.join(ROOT, 'Navigation', 'map_message.c'), encoding='utf-8').read()
body = src[src.index('NavEdgeTbl[NAV_EDGE_COUNT] = {'):]; body = body[:body.index('};')]
edges = []
for m in re.finditer(r'\{\s*([A-Z0-9_]+)\s*,\s*([A-Z0-9_]+)\s*,\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*([A-Za-z0-9_]+)\s*\}', body):
    frm, to, flag, ang, step, spd, fun = [x.strip() for x in m.groups()]
    edges.append(dict(frm=frm, to=to, flag=flag, ang=ang, step=step, spd=spd, fun=fun))
def find(f, t):
    for e in edges:
        if e['frm'] == f and e['to'] == t: return e
def n2t(a, b):
    d = b - a
    if d > 180: d -= 360
    elif d <= -180: d += 360
    return d

# ---------------- 3. 判据（与 ArriveDetect_task.c 的 if 链同序） ----------------
METHODS = [('DLEFT', 1 << 1), ('DRIGHT', 1 << 2), ('CLEFT', 1 << 3), ('MCLEFT', 1 << 13),
           ('MCRIGHT', 1 << 14), ('CRIGHT', 1 << 4), ('MORELED', 1 << 18), ('AWHITE', 1 << 7),
           ('MUL2SING', 1 << 5), ('MUL2MUL', 1 << 6)]
FLAGV = {}
maph = open(os.path.join(ROOT, 'Navigation', 'map.h'), encoding='utf-8').read()
for m in re.finditer(r'#define\s+(\w+)\s+\(1<<(\d+)\)', maph):
    FLAGV[m.group(1)] = 1 << int(m.group(2))
FLAGV['NO'] = 1; FLAGV['NONE'] = 1
def enabled(flag_expr):
    v = 0
    for tok in flag_expr.split('|'):
        v |= FLAGV.get(tok.strip(), 0)
    return [n for (n, b) in METHODS if v & b]

# ---------------- 4. 两张硬补偿表 ----------------
mapc = open(os.path.join(ROOT, 'Navigation', 'map.c'), encoding='utf-8').read()
def parse_tbl(name):
    seg = mapc[mapc.index(name):]; seg = seg[:seg.index('\n}')]
    out = []
    for l in seg.splitlines():
        m = re.search(r'if\s*\(\s*last\s*==\s*(\w+)\s*&&\s*now\s*==\s*(\w+)\s*&&\s*next\s*==\s*(\w+)\s*\)\s*return\s*([-\d.]+)', l)
        if m: out.append((m.group(1), m.group(2), m.group(3), float(m.group(4))))
    return out
t_stop, t_gyro = parse_tbl('GetForwardDistanceBeforeTurn'), parse_tbl('GetForwardDistanceBeforeGyroTurn')

rows, dead = [], []
for tbl_name, tbl, default in (('停车转', t_stop, 19.0), ('陀螺转', t_gyro, 0.0)):
    for (l, n, x, v) in tbl:
        ei, eo = find(l, n), find(n, x)
        if ei is None or eo is None:
            dead.append(('边表无此组合', l, n, x, v)); continue
        ai, ao = ang_expr(ei['ang']), ang_expr(eo['ang'])
        if ai is None or ao is None:
            dead.append(('角度未解开', l, n, x, v)); continue
        t = n2t(ai, ao)
        stop = 'STOPTURN' in ei['flag']
        real = '停车转' if ((stop and abs(t) > 30) or abs(t) >= 90) else '陀螺转'
        if real != tbl_name:
            dead.append(('表项不生效(实际走%s)' % real, l, n, x, v)); continue
        rows.append(dict(tri='%s->%s->%s' % (l, n, x), edge='%s->%s' % (l, n), now=n, nxt=x,
                         phi=abs(t), signed=t, v=v, default=default,
                         cand=enabled(ei['flag']), flag=ei['flag'], func=ei['fun'], step=ei['step']))

print('=' * 112)
print('数据点：生效的硬补偿 %d 条    被丢掉/无效的表项 %d 条' % (len(rows), len(dead)))
for d in dead: print('   [丢] %-24s %s->%s->%s = %.0f' % (d[0], d[1], d[2], d[3], d[4]))
print('=' * 112)

# ---------------- 5. 各种模型 ----------------
def metrics(pred_fn, label, npar):
    errs = [pred_fn(r) - r['v'] for r in rows]
    ae = [abs(e) for e in errs]
    mae = sum(ae) / len(ae)
    med = sorted(ae)[len(ae) // 2]
    # LOO：逐点留出，用其余点重估参数（这里对常量项做近似：用其余点的同一 key 中位数）
    loo = []
    for i, r in enumerate(rows):
        rest = rows[:i] + rows[i + 1:]
        p = pred_fn(r, rest)
        loo.append(abs(p - r['v']))
    print('%-42s 参数=%-3d MAE=%5.2f  中位=%5.2f  最大=%5.2f  LOO-MAE=%5.2f' % (
        label, npar, mae, med, max(ae), sum(loo) / len(loo)))
    return mae, loo

def mk_mean(key_fn, base=0.0, ang_L=0.0, sin_k=0.0):
    """返回预测函数：base + L(1-cosφ) + k·sinφ + key组的中位数"""
    def fit(rest):
        d = {}
        for r in rest:
            k = key_fn(r)
            d.setdefault(k, []).append(r['v'] - ang_L * (1 - math.cos(math.radians(r['phi']))) - sin_k * math.sin(math.radians(r['phi'])))
        return {k: sorted(v)[len(v) // 2] for k, v in d.items()}
    def pred(r, rest=None):
        d = fit(rest if rest is not None else rows)
        return ang_L * (1 - math.cos(math.radians(r['phi']))) + sin_k * math.sin(math.radians(r['phi'])) + d.get(key_fn(r), base)
    return pred

# 扫 L / k，取 MAE 最小
def scan(key_fn, tag, base=0.0, scan_sin=False):
    best = None
    for L in [x * 0.5 for x in range(0, 121)]:
        for k in ([x * 0.5 for x in range(-12, 13)] if scan_sin else [0.0]):
            pred = mk_mean(key_fn, base, L, k)
            ae = [abs(pred(r) - r['v']) for r in rows]
            mae = sum(ae) / len(ae)
            if best is None or mae < best[0]: best = (mae, L, k, pred)
    return best

print()
scan(lambda r: 'ALL', 'ALL')
b1 = (None, 0, 0, mk_mean(lambda r: 'ALL', 0, 0, 0)); metrics(b1[3], '基线0：全局单一常量', 1)
b2 = scan(lambda r: 'ALL', 'angle'); metrics(b2[3], '基线1：只用夹角  L(1-cosφ)  (L=%.1f)' % b2[1], 2)
b3 = scan(lambda r: r['cand'][0] if r['cand'] else 'NONE', 'method'); metrics(b3[3], '基线2：只用判据  每判据常量  (L=%.1f)' % b3[1], 7)
b4 = scan(lambda r: r['cand'][0] if r['cand'] else 'NONE', 'method+angle', scan_sin=True)
metrics(b4[3], '模型A：判据 + 夹角  (L=%.1f, sin=%.1f)' % (b4[1], b4[2]), 8)
b5 = scan(lambda r: r['edge'], 'edge')
metrics(b5[3], '模型B：入边 + 夹角  (L=%.1f)' % b5[1], len(set(r['edge'] for r in rows)) + 1)
b6 = scan(lambda r: r['edge'] + '|' + (r['cand'][0] if r['cand'] else 'NONE'), 'edge+method')
metrics(b6[3], '模型C：入边 + 判据  (L=%.1f)' % b6[1], 20)
b7 = mk_mean(lambda r: r['tri'], 0, 0, 0)
metrics(b7, '上界：直接查 (last,now,next) 三元组（现有做法）', len(rows))

print('\n' + '=' * 112)
print('模型A（判据 + 夹角）逐点对照   L=%.1f' % b4[1])
print('=' * 112)
print('%-18s %6s %5s %-10s %8s %8s %9s' % ('三元组', '转弯°', '实测', '判据', '几何项', '判据项', '预测-实测'))
meth = {}
for r in rows:
    k = r['cand'][0] if r['cand'] else 'NONE'
    meth.setdefault(k, []).append(r['v'] - b4[1] * (1 - math.cos(math.radians(r['phi']))))
for k in meth: meth[k] = sorted(meth[k])[len(meth[k]) // 2]
for r in sorted(rows, key=lambda z: -z['phi']):
    k = r['cand'][0] if r['cand'] else 'NONE'
    g = b4[1] * (1 - math.cos(math.radians(r['phi']))); b = meth.get(k, 0.0)
    print('%-18s %6.1f %5.0f %-10s %8.1f %8.1f %+9.1f' % (r['tri'], r['phi'], r['v'], k, g, b, g + b - r['v']))

print('\n各判据拟合出的常量项（cm）:')
for k, v in sorted(meth.items(), key=lambda z: -z[1]):
    print('  %-10s %6.1f   (样本 %d)' % (k, v, sum(1 for r in rows if (r['cand'][0] if r['cand'] else 'NONE') == k)))

# 同判据内的散度：这是模型A 的误差来源
print('\n按"判据"分组的实测值（组内散度 = 模型A 无法解释的部分）:')
grp = {}
for r in rows:
    grp.setdefault(r['cand'][0] if r['cand'] else 'NONE', []).append((r['tri'], r['phi'], r['v']))
for k, vs in sorted(grp.items(), key=lambda z: -max(x[2] for x in z[1])):
    if len(vs) > 1:
        print('  %-10s 值=%s  → 极差 %.0f cm' % (k, [int(x[2]) for x in vs], max(x[2] for x in vs) - min(x[2] for x in vs)))

print('\n按"转弯角"分组（同样角度下的散度）:')
grp2 = {}
for r in rows: grp2.setdefault(round(r['phi']), []).append((r['tri'], r['v'], r['cand'][0] if r['cand'] else 'NONE'))
for k, vs in sorted(grp2.items()):
    if len(vs) > 1:
        print('  %3d°  值=%s  → 极差 %.0f cm' % (k, [int(x[1]) for x in vs], max(x[1] for x in vs) - min(x[1] for x in vs)))
