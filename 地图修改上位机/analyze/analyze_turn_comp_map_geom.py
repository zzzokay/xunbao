# -*- coding: utf-8 -*-
"""
临时分析（只看不改）：
1) 用地图像素坐标算每条边的真实走向，检验"表里 angle = 真实走向 + 固定偏移"是否成立
2) 若成立，用真实几何算每个转弯节点的"入边/出边夹角"和"路中心线横向错位 b"
3) 用几何模型 Δ = L − (b + w/2)/sinφ 重新拟合 22 条硬补偿
"""
import re, os, math

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))

# ---- 节点像素坐标（读自 寻宝地图/节点图.jpg，1012x632 预览坐标系；只用于角度） ----
P = {
 'S1': (115,40), 'P1': (330,37), 'B1': (480,30), 'N1': (390,30), 'B2': (425,85),
 'B3': (515,88), 'N2': (580,30), 'P2': (695,35), 'S2': (905,55),
 'P3': (100,137), 'N3': (370,140), 'N4': (513,143), 'N5': (645,143), 'N6': (737,122),
 'P4': (890,137), 'C1': (700,200), 'D4': (425,212), 'D3': (565,200), 'N8': (513,253),
 'D2': (620,258), 'D1': (700,240), 'N7': (213,190), 'N9': (213,352), 'N10': (348,348),
 'N12': (645,340), 'N13': (737,340), 'P5': (890,358), 'C3': (85,340), 'N14': (85,403),
 'S3': (150,408), 'S4': (310,403), 'N15': (370,415), 'S5': (645,403), 'N16': (675,433),
 'C4': (185,443), 'C5': (370,460), 'N18': (645,470), 'B5': (785,443), 'N19': (890,440),
 'C6': (890,495), 'B6': (512,558), 'N22': (577,565), 'C9': (722,610), 'P7': (880,592),
 'C7': (88,590), 'C8': (178,610), 'B11': (255,512), 'B7': (785,495), 'N20': (418,512),
 'P8': (95,510), 'N11': (490,340), 'G1': (825,605), 'B10': (68,570),
 'B8': (175,265), 'B9': (258,265), 'P6': (213,285),
}

def load_edges():
    src = open(os.path.join(ROOT, 'Navigation', 'map_message.c'), encoding='utf-8').read()
    body = src[src.index('NavEdgeTbl[NAV_EDGE_COUNT] = {'):]; body = body[:body.index('};')]
    out = []
    for m in re.finditer(r'\{\s*([A-Z0-9_]+)\s*,\s*([A-Z0-9_]+)\s*,\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*([A-Za-z0-9_]+)\s*\}', body):
        out.append(dict(frm=m.group(1), to=m.group(2), flag=m.group(3).strip(),
                        ang=m.group(4).strip(), step=m.group(5).strip()))
    return out
E = load_edges()
MACRO = {'ANGLE_N3N8':145,'ANGLE_N5N8':35,'ANGLE_N8N12':145,'ANGLE_N8N10':35,
         'ANGLE_N8N3':-35,'ANGLE_N8N5':-145,'ANGLE_N12N8':-35,'ANGLE_N10N8':-145}
CFG = {'DOOR_LEN_N5N8':170,'DOOR_LEN_N8N12':170,'DOOR_LEN_N3N8':170,
       'DOOR_LEN_N5N12':170,'DOOR_LEN_N3N10':170,'DOOR_LEN_N8N10':170}
def num(s):
    s2 = s
    for k, v in {**MACRO, **CFG}.items():
        s2 = re.sub(r'\b%s\b' % k, str(v), s2)
    try: return float(eval(s2))
    except Exception: return None

# ---- 1. 真实走向 vs 表里 angle ----
K = 0.884   # px/cm（仅用于长度，不影响角度）
def geo(a, b):
    dx = P[b][0] - P[a][0]; dy = -(P[b][1] - P[a][1])
    return math.degrees(math.atan2(dx, dy)) % 360
def tab(a, b):
    e = next((x for x in E if x['frm'] == a and x['to'] == b), None)
    return None if e is None else MACRO.get(e['ang'], num(e['ang']))
def angdiff(a, b):
    d = (a - b) % 360
    return d - 360 if d > 180 else d

print('=' * 100)
print('一、表里 angle 与地图真实走向的偏差（若近似为常数，说明只是参考系差）')
print('=' * 100)
diffs = []
for e in E:
    a, b = e['frm'], e['to']
    if a in P and b in P:
        t = MACRO.get(e['ang'], num(e['ang']))
        if t is None: continue
        d = angdiff(geo(a, b), t)
        diffs.append(d)
        print('  %-6s->%-6s  图上=%7.1f  表里=%7.0f  偏差=%+7.1f' % (a, b, geo(a, b), t, d))
import statistics
print('\n  偏差中位数 = %+.1f°  标准差 = %.1f°  极差 = %.1f°' % (
    statistics.median(diffs), statistics.pstdev(diffs), max(diffs) - min(diffs)))
OFF = statistics.median(diffs)
print('  → 取 OFF=%+.1f° 作为参考系偏移' % OFF)
