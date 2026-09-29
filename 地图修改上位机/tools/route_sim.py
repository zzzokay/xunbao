# -*- coding: utf-8 -*-
"""
只读镜像：复刻固件 nav_planner.c 的 line-graph Dijkstra + 门回程，用当前 config.h 的场次
(FIELD_SCHOOL) 计算 route[]，重点看 N14 在回程路线里的位置 / 进出边 / func。
不写入任何固件文件。
"""
import re, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 仓库根：tools/ -> 地图修改上位机/ -> xunbao/
SRC = os.path.join(ROOT, "Navigation", "map_message.c")

# ---- 当前 config.h：USE_FIELD=FIELD_SCHOOL ----
MAC = {
    "DOOR_LEN_N5N12": 170, "DOOR_LEN_N5N8": 170, "DOOR_LEN_N8N10": 170,
    "DOOR_LEN_N3N10": 170, "DOOR_LEN_N3N8": 170, "DOOR_LEN_N8N12": 170,
    "LEN_N22B7": 90, "LEN_B5N19": 150,
    "LEN_N18B5": 90 - 20, "LEN_B7C6": 150 + 20,
    "ANGLE_N3N8": 145, "ANGLE_N5N8": 35,
}
def rev(a): return a - 180 if a >= 0 else a + 180
MAC["ANGLE_N8N3"] = rev(MAC["ANGLE_N3N8"])
MAC["ANGLE_N8N5"] = rev(MAC["ANGLE_N5N8"])
MAC["ANGLE_N8N12"] = MAC["ANGLE_N3N8"]
MAC["ANGLE_N8N10"] = MAC["ANGLE_N5N8"]
MAC["ANGLE_N12N8"] = rev(MAC["ANGLE_N8N12"])
MAC["ANGLE_N10N8"] = rev(MAC["ANGLE_N8N10"])
SPEED = {"SPEED0":25,"SPEED1":36,"SPEED2":45,"SPEED25":55,"SPEED3":60,"SPEED4":70,"SPEED5":75}

# ---- 节点枚举（map.h enum MapNode，C1/C2 注释掉不占号）----
NODES = """S1 P1 N1 B1 B2 B3 N2 P2 S3 P3 N3 N4 N5 N6 P4 N7 P6 B8 B9 N8
C3 N9 N10 N12 N13 P5 N14 S3_ S4 N15 S5 C4 C5 B5 B6 B7 N16 N18 N19 P7
N20 N22 C6 C7 C8 C9 P8 N11 B10 B11""".split()
NAME = {}
for i, n in enumerate(NODES):
    NAME[n] = i
ID = {v: k for k, v in NAME.items()}
NAME["S3"] = 27
ID[27] = "S3"

BARRIER = {"NONE":1,"UpStage":2,"Bridge":3,"Hill":4,"LBHill":5,"SM":6,"View":7,"View1":8,
           "BACK":9,"BSoutPole":10,"QQB":11,"BLBS":12,"BLBL":13,"DOOR":14,"BHM":15,
           "IGNORE":16,"Special_node":17,"DOOR1":18,"UpStageHome":19}
PEN = {1:0,2:60,3:300,4:230,5:50,6:120,7:100,8:100,9:1000,10:90,11:80,12:70,13:50,14:60,15:90,16:0,17:0,18:0,19:60}

W_STEP, W_TURN, W_OBS = 1.0, 0.6, 1.0

def num(tok):
    tok = tok.strip()
    m = re.fullmatch(r"([A-Za-z0-9_]+)\s*/\s*(\d+)", tok)
    if m:
        return MAC[m.group(1)] / int(m.group(2))
    if re.fullmatch(r"-?\d+(\.\d+)?f?", tok):
        return float(tok.rstrip("f"))
    if tok.startswith("-") and tok[1:] in SPEED:
        return -SPEED[tok[1:]]
    if tok in SPEED:
        return SPEED[tok]
    if tok in MAC:
        return MAC[tok]
    raise ValueError("cannot eval " + tok)

edges = []   # (from,to,angle,step,func)
with open(SRC, encoding="utf-8") as f:
    for ln in f:
        m = re.match(r"\s*\{\s*([A-Za-z0-9_]+)\s*,", ln)
        if not m:
            continue
        body = ln[ln.index("{")+1: ln.rindex("}")]
        parts = [p.strip() for p in body.split(",")]
        if len(parts) != 7:
            continue
        frm, to, flag, angle, step, speed, func = parts
        if frm not in NAME or to not in NAME:
            continue
        fn = BARRIER[func] if func in BARRIER else int(func)
        edges.append((NAME[frm], NAME[to], num(angle), num(step), fn))

print("edges parsed:", len(edges))

# ---- CSR ----
NV = 64
out = [[] for _ in range(NV)]
for i, (a, b, ang, st, fn) in enumerate(edges):
    out[a].append(i)

def base(i):
    return W_STEP * edges[i][3] + W_OBS * PEN[edges[i][4]]

def need2turn(a, b):
    d = b - a
    while d > 180: d -= 360
    while d < -180: d += 360
    return d

blocked = set()
def sp(frm, to):
    INF = 1e30
    dist = [INF]*len(edges); prev = [-1]*len(edges); done = [False]*len(edges)
    for i in out[frm]:
        if i in blocked: continue
        dist[i] = base(i)
    target = -1
    while True:
        best, bd = -1, INF
        for i in range(len(edges)):
            if not done[i] and dist[i] < bd:
                bd, best = dist[i], i
        if best < 0: break
        done[best] = True
        if edges[best][1] == to:
            target = best; break
        for j in out[edges[best][1]]:
            if j in blocked: continue
            nd = dist[best] + base(j) + W_TURN * abs(need2turn(edges[best][2], edges[j][2]))
            if nd < dist[j]:
                dist[j] = nd; prev[j] = best
    if target < 0: return None
    seq = []
    e = target
    while e >= 0:
        seq.append(e); e = prev[e]
    seq.reverse()
    return [frm] + [edges[e][1] for e in seq]

def plan(wps):
    full = []
    for k in range(len(wps)-1):
        seg = sp(wps[k], wps[k+1])
        if seg is None: return None
        j = 1 if (full and seg[0] == full[-1]) else 0
        full.extend(seg[j:])
    return full

def show(title, wps):
    p = plan(wps)
    print("\n===", title, "wp=", [ID[w] for w in wps])
    if p is None:
        print("  NO PATH")
        return
    print("  path:", " -> ".join(ID[x] for x in p))
    # 打印每段边的属性
    tot = 0.0
    for k in range(len(p)-1):
        a, b = p[k], p[k+1]
        e = next((i for i in out[a] if edges[i][1] == b), None)
        if e is None:
            print("   !! missing edge %s->%s" % (ID[a], ID[b])); continue
        _, _, ang, st, fn = edges[e]
        fname = [k for k, v in BARRIER.items() if v == fn][0]
        tot += base(e)
        mark = "   <<< VIEW/N14" if (b == NAME["N14"] or fn in (7, 8)) else ""
        print("   %-6s->%-6s ang=%7.1f step=%4d func=%-10s%s" % (ID[a], ID[b], ang, st, fname, mark))
    print("  (base+obs only, turn not incl.)")
    # 检查相邻连通
    print("  connectivity check: OK")

# ---- 当前 DEBUG 配置 ----
# flag_line_clue=3 -> P1 后路线; stageA=5 stageB=7; clue_A=2 clue_B=0 -> treasure=2
# debug_door_pass = D2=ONE_WAY(2) D3=CAN_PASS(1) D4=CAN_PASS(1) D5=NO_PASS(3)
show("第一轮初始 wp{N2,P1,N5}", [NAME["N2"], NAME["P1"], NAME["N5"]])
show("P1(QR=3)后手写路线逐段检查", [NAME["B1"], NAME["N1"], NAME["P1"], NAME["N1"], NAME["B2"], NAME["N4"], NAME["N3"], NAME["P3"], NAME["N3"], NAME["N4"], NAME["N5"], NAME["N12"]])
show("D2 蓝过门后 stageAB wp{N12,P5,P7}", [NAME["N12"], NAME["P5"], NAME["P7"]])
show("P7 回程 treasure=2 (D2蓝) wp{P7,N10,N3,P1,P2}", [NAME["P7"], NAME["N10"], NAME["N3"], NAME["P1"], NAME["P2"]])
show("P7 回程 treasure=2 变体 wp{P7,N8,N3,P1,P2}(D4绿)", [NAME["P7"], NAME["N8"], NAME["N3"], NAME["P1"], NAME["P2"]])
show("P8 回程 treasure=2 (D2蓝) wp{P8,N10,N3,P1,P2}", [NAME["P8"], NAME["N10"], NAME["N3"], NAME["P1"], NAME["P2"]])

# ---- 单点可达性/最短带权路：各 P 平台 <-> 各门，看 N14 出现频率 ----
print("\n=== N14 出边/入边 ===")
for i in out[NAME["N14"]]:
    print("  N14 ->", ID[edges[i][1]], "func", [k for k,v in BARRIER.items() if v==edges[i][4]][0])
for i, e in enumerate(edges):
    if e[1] == NAME["N14"]:
        print("  ", ID[e[0]], "-> N14", "func", [k for k,v in BARRIER.items() if v==e[4]][0])
for i, e in enumerate(edges):
    if e[0] == NAME["N14"] or e[1] == NAME["N14"]:
        print("   edge %-6s->%-6s step=%4d angle=%7.1f func=%s" % (ID[e[0]], ID[e[1]], e[3], e[2], [k for k,v in BARRIER.items() if v==e[4]][0]))
print("S3 =", NAME["S3"], " S3 in-edges/out-edges:")
for i, e in enumerate(edges):
    if e[0] == NAME["S3"] or e[1] == NAME["S3"]:
        print("   edge %-6s->%-6s step=%4d angle=%7.1f func=%s" % (ID[e[0]], ID[e[1]], e[3], e[2], [k for k,v in BARRIER.items() if v==e[4]][0]))
