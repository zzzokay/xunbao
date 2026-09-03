# -*- coding: utf-8 -*-
"""权重标定/回归基准工具（Phase0）：
- 从 map_message.c 解析图（修正：保留真实零长度障碍边，滤掉空桩行）
- 校验所有现有路线：相邻节点都存在合法边
- 边状态(line-graph) Dijkstra，分别跑 仅长度 / 长度+转角 / 长度+转角+障碍 三种成本模型
- 输出每条参考路径是否被复现，以及未复现时的实际最短路径（用于判断该处是否需要 waypoint 约束）
本脚本只读代码，不参与固件编译。
"""
import os, re, math, sys, heapq, collections

BASE = os.path.dirname(os.path.abspath(__file__))   # 脚本所在目录 = 仓库根（相对定位，换机器/换路径不用改）
# 数据现为单一来源：map_message.c 的 NavEdgeTbl[]（自描述，含 from）。改读它。
GRAPH_C = os.path.join(BASE, "Application", "map_message.c")

NODE_IDX = {
 "S1":0,"P1":1,"N1":2,"B1":3,"B2":4,"B3":5,"N2":6,"P2":7,"S2":8,"P3":9,
 "N3":10,"N4":11,"N5":12,"N6":13,"P4":14,"N7":15,"P6":16,"B8":17,"B9":18,"N8":19,
 "C1":20,"C2":21,"C3":22,"N9":23,"N10":24,"N12":25,"N13":26,"P5":27,"N14":28,"S3":29,
 "S4":30,"N15":31,"S5":32,"C4":33,"C5":34,"B4":35,"B5":36,"B6":37,"B7":38,"N16":39,
 "N18":40,"N19":41,"P7":42,"N20":43,"N22":44,"C6":45,"C7":46,"C8":47,"C9":48,"P8":49,
 "N11":50,"G1":51,"B10":52,"B11":53,
}
IDX2NAME = {v:k for k,v in NODE_IDX.items()}
FUNC = {"NONE":1,"UpStage":2,"Bridge":3,"Hill":4,"LBHill":5,"SM":6,"View":7,"View1":8,
        "BACK":9,"BSoutPole":10,"QQB":11,"BLBS":12,"BLBL":13,"DOOR":14,"BHM":15,
        "IGNORE":16,"Special_node":17,"DOOR1":18,"UpStageHome":19}
FUNC2NAME = {v:k for k,v in FUNC.items()}

# ===== 场地切换开关（与 map_message.h 的 USE_FIELD 同步，需保持一致）=====
FIELD_COMP, FIELD_SCHOOL = 0, 1
USE_FIELD = FIELD_COMP   # 切换场地改这里：比赛=0，学校=1

if USE_FIELD == FIELD_SCHOOL:
    # —— 学校场地实测值（TODO: 待填，先抄比赛值占位）——
    _DOOR_LEN = [("N5N12",220),("N5N8",200),("N8N10",200),("N3N10",220),("N3N8",200),("N8N12",200)]
    _LEN      = [("N22B7",200),("N18B5",180),("B5N19",72),("B7C6",72)]
    _ANGLE    = [("N3N8",145),("N5N8",35),("N8N12",145),("N8N10",35)]
else:
    # —— 比赛场地（现状）——
    _DOOR_LEN = [("N5N12",220),("N5N8",200),("N8N10",200),("N3N10",220),("N3N8",200),("N8N12",200)]
    _LEN      = [("N22B7",200),("N18B5",180),("B5N19",72),("B7C6",72)]
    _ANGLE    = [("N3N8",145),("N5N8",35),("N8N12",145),("N8N10",35)]

MACROS = {}
for n,v in _DOOR_LEN:
    MACROS[f"DOOR_LEN_{n}"] = v
for n,v in _LEN:
    MACROS[f"LEN_{n}"] = v
for n,v in _ANGLE:
    MACROS[f"ANGLE_{n}"] = v
MACROS["ANGLE_N8N3"]  = MACROS["ANGLE_N3N8"] - 180
MACROS["ANGLE_N8N5"]  = MACROS["ANGLE_N5N8"] - 180
MACROS["ANGLE_N12N8"] = MACROS["ANGLE_N8N12"] - 180
MACROS["ANGLE_N10N8"] = MACROS["ANGLE_N8N10"] - 180

def eval_expr(expr):
    e = (expr or "").strip()
    if e == "":
        return None
    e2 = re.sub(r"/\*.*?\*/", "", e)
    for name in sorted(MACROS, key=len, reverse=True):
        v = MACROS[name]
        e2 = e2.replace(name, str(int(v) if float(v).is_integer() else v))
    e2 = re.sub(r"/\*.*?\*/", "", e2)
    if not re.fullmatch(r"[0-9+\-*/(). ]+", e2):
        return None
    try:
        return float(eval(e2, {"__builtins__":{}}, {}))
    except Exception:
        return None

def parse_graph():
    """解析 nav_graph_data.c 的 NavEdgeTbl[]（自描述边表，含 from）。返回边列表。"""
    txt = open(GRAPH_C, encoding="utf-8", errors="replace").read()
    mblk = re.search(r"NavEdge\s+NavEdgeTbl\[.*?\]\s*=\s*\{(.*?)\};", txt, re.S)
    body = mblk.group(1)
    pattern = re.compile(r"\{([^{}]*)\}", re.S)   # 每个 { ... } 是一条边
    edges = []
    for m in pattern.finditer(body):
        item = re.sub(r"/\*.*?\*/", "", m.group(1)).strip()
        if not item: continue
        parts = [p.strip() for p in item.split(",")]
        if len(parts) < 7: continue   # 空桩行过滤
        from_name = parts[0]; to_name = parts[1]
        if from_name not in NODE_IDX or to_name not in NODE_IDX:
            continue
        angle = eval_expr(parts[3])
        step  = eval_expr(parts[4])
        func_tok = parts[6]
        func = FUNC.get(func_tok, 0)
        if func_tok.isdigit(): func = int(func_tok)
        if step is None: step = 0.0
        edges.append({"from":NODE_IDX[from_name],"to":NODE_IDX[to_name],
                      "angle":(angle if angle is not None else 0.0),
                      "step":float(step),"func":func})
    return edges

def need2turn(a, b):
    d = (b - a) % 360.0
    if d > 180: d -= 360.0
    if d < -180: d += 360.0
    return abs(d)

# ============ 参考路线（取自 map.c / barrier.c 真实数组，去掉 0xFF）============
REF = {
 "R1_init":    ["B1","N1","P1","N1","B2","N4","N5"],
 "door1":      ["N3","N8"],
 "door6":      ["N4","B3","N2","P2"],
 "door7":      ["N8","N3","N4","B3","N2","P2"],
 "door11":     ["N5","N4","B3","N2","P2"],
 "rout_57":    ["N13","P5","N13","N12","N16","N18","B5","N19","C6","B7","N22","C9","P7","C9"],
 "rout_58":    ["N13","P5","N13","N12","N11","N10","N9","C3","N14","B10","C7","C8","B11","C4","N20","P8","N20"],
 "rout_67":    ["N9","B9","N7","P6","N7","B8","N9","C3","N14","B10","C7","C8","B11","C4","N20","B6","N22","C9","P7","C9"],
 "rout_68":    ["N9","B9","N7","P6","N7","B8","N9","C3","N14","B10","C7","C8","B11","C4","N20","P8","N20"],
 "R2_pre":     ["B1","N1","P1","N1","B2","N4","N3","P3","N3","N4","N5","N6","P4","N6","N5"],
 "R2_tour":    ["N13","P5","N13","N12","N16","N18","B5","N19","C6","B7","N22","C9","P7","C9","N22","B6","N20","P8","N20","C4","B11","C8","C7","B10","N14","C3","N9","B9","N7","P6","N7","B8","N9","N10"],
 "R2_tour_p6": ["N9","B9","N7","P6","N7","B8","N9","C3","N14","B10","C7","C8","B11","C4","N20","P8","N20","B6","N22","C9","P7","C9","N22","B7","C6","N19","B5","N18","N16","N12","N13","P5","N13","N12"],
 "entry_D2_p6":["N12","N11","N10"],
 "entry_D3_p6":["N8","N10"],
 "entry_far_p6":["N4","N3","N8","N10"],
}

def build_adj(edges):
    adj = collections.defaultdict(list)
    for i,e in enumerate(edges):
        adj[e["from"]].append(i)
    return adj

# ============ 边状态 Dijkstra ============
def dijkstra(edges, adj, src_node, dst_node, W_len=1.0, W_turn=0.0, W_obs=0.0):
    """状态 = 到达 src_node 所用的入边。为简化起点用“任意离开 src_node 的边”。”
    返回 (实际路径节点序列, 总成本) 或 (None, None)."""
    # 起点没有入边；我们建模为：从 src_node 出发，每条出边作为初始状态，成本 = base(f)
    E = len(edges)
    INF = float("inf")
    # dist to a state = (edge_index). Represent reaching node edge["to"] via edge.
    dist = [INF]*E
    prev = [None]*E   # prev state edge index
    pq = []
    for i in adj.get(src_node, []):
        c = W_len*edges[i]["step"] + W_obs*obs_w(edges[i]["func"])
        dist[i] = c
        heapq.heappush(pq, (c, i))
    # 目标：到达 dst_node（以某条入边到达 dst_node）
    if src_node == dst_node:
        return [src_node], 0.0
    best = INF; best_edge = None
    while pq:
        d, ei = heapq.heappop(pq)
        if d > dist[ei]: continue
        e = edges[ei]
        if e["to"] == dst_node:
            if d < best:
                best = d; best_edge = ei
            # 不 break，因为可能还有其他更优；但为性能若很多同目标，继续
        # 扩展：从 e 的 to 节点出发的所有出边 f
        for fj in adj.get(e["to"], []):
            f = edges[fj]
            turn = W_turn * need2turn(e["angle"], f["angle"])
            nd = d + W_len*f["step"] + W_obs*obs_w(f["func"]) + turn
            if nd < dist[fj]:
                dist[fj] = nd
                prev[fj] = ei
                heapq.heappush(pq, (nd, fj))
    if best_edge is None:
        return None, None
    # 回溯
    path_rev = []
    cur = best_edge
    while cur is not None:
        path_rev.append(edges[cur]["to"])
        # 起点标记：我们把“该边从 src_node 出发”的边 prev 为 None；但要保留起点
        cur = prev[cur]
    path_rev.append(src_node)
    path = list(reversed(path_rev))
    # 去除可能的“同节点相邻重复”（当某条边 angle=0 短边等）
    dedup = []
    for p in path:
        if not dedup or dedup[-1]!=p:
            dedup.append(p)
    return dedup, best

# 障碍/风险权重（单位：等效厘米）。0=NONE。这些是“额外惩罚”，叠加在 step 上。
# 数值初步取自“该障碍越难/越慢/越失败率高，penalty 越大”。
# 后续由下方 waypoint 段回归微调。
OBS_PENALTY = {
    0:0.0,            # 空
    1:0.0,            # NONE
    2:60.0,           # UpStage 平台>去完要回，考虑爬坡
    3:40.0,           # Bridge 桥
    4:30.0,           # Hill 山
    5:50.0,           # LBHill
    6:120.0,          # SM 刀山（round2 刻意避开 N11）
    7:100.0,          # View 景点支路（不应被当作捷径绕进去）
    8:100.0,          # View1 景点支路
    9:1000.0,         # BACK 后退桩（绝不该被选为前进路径）
    10:90.0,          # BSoutPole 南极
    11:80.0,          # QQB 跷跷板
    12:60.0,          # BLBS 短波动板
    13:70.0,          # BLBL 长波动板
    14:0.0,           # DOOR 门：应由门状态硬过滤，不靠权重
    15:90.0,          # BHM 高山
    16:0.0,           # IGNORE
    17:0.0,           # Special_node
    18:0.0,           # DOOR1
    19:60.0,          # UpStageHome
}
def obs_w(func):
    return OBS_PENALTY.get(func, 0.0)

def names(seq):
    return [IDX2NAME[x] for x in seq] if seq else None

def validate_ref(edges, adj):
    print("=== 校验参考路线的每条相邻边是否存在 ===")
    ok = True
    for name, path in REF.items():
        missing = []
        for i in range(len(path)-1):
            a, b = NODE_IDX[path[i]], NODE_IDX[path[i+1]]
            if not any(edges[j]["from"]==a and edges[j]["to"]==b for j in adj.get(a, [])):
                missing.append(f"{path[i]}->{path[i+1]}")
        if missing:
            ok = False
            print(f"  [缺边] {name}: {', '.join(missing)}")
        else:
            print(f"  [OK]   {name}")
    return ok

def run_ref_dijkstra(edges, adj, W_len, W_turn, W_obs):
    print(f"\n=== Dijkstra 复现（W_len={W_len}, W_turn={W_turn}, W_obs={W_obs}）===")
    match = 0; tot = 0
    for name, path in REF.items():
        exp = [NODE_IDX[x] for x in path]
        got, cost = dijkstra(edges, adj, exp[0], exp[-1], W_len, W_turn, W_obs)
        tot += 1
        if got == exp:
            match += 1
            print(f"  [匹配] {name}")
        else:
            print(f"  [差异] {name}")
            print(f"         期望: {' '.join(path)}")
            print(f"         实际: {' '.join(names(got)) if got else 'N/A'}")
    print(f"  匹配 {match}/{tot}")

def split_at_waypoints(edges, adj, ref_path, waypoints, W_len, W_turn, W_obs, label):
    """把参考路径在 waypoint 处切开，每一段用 Dijkstra 从起点到终点，比对是否等于参考子段。"""
    print(f"\n=== [必经点细分] {label}（W_turn={W_turn}）===")
    path = [NODE_IDX[x] for x in ref_path]
    # waypoints 以节点名给出；在参考路径中定位其下标（出现多次取第一次/按序）
    idxs = []
    for w in waypoints:
        wv = NODE_IDX[w]
        # 找到 path 中 >= 上一个 idx 的第一个 wv
        start = idxs[-1]+1 if idxs else 0
        found = None
        for k in range(start, len(path)):
            if path[k]==wv:
                found = k; break
        if found is None:
            idxs.append(len(path)-1)
        else:
            idxs.append(found)
    seg = [0] + idxs + [len(path)-1]
    all_ok = True
    for i in range(len(seg)-1):
        a = path[seg[i]]; b = path[seg[i+1]]
        if a == b:
            continue   # 起点==终点（如最后一站就是终点），跳过零长度段
        sub_ref = path[seg[i]:seg[i+1]+1]
        got, cost = dijkstra(edges, adj, a, b, W_len, W_turn, W_obs)
        if got == sub_ref:
            print(f"  [OK] {IDX2NAME[a]}→{IDX2NAME[b]} : {' '.join(names(got))}")
        else:
            all_ok = False
            print(f"  [差] {IDX2NAME[a]}→{IDX2NAME[b]} : 期望 {' '.join(names(sub_ref))}")
            print(f"                             实际 {' '.join(names(got)) if got else 'N/A'}")
    return all_ok

# 每条参考路线对应的“必经点”列表（首尾自动由 route 首尾决定；这里只给中间的强制过点）
# 说明：门(DOOR)的作用退化为“必经点入口/出口”，如 far 入口强制经 N8；平台即必经点；跷跷板为单相已由边集体现。
REF_WP = {
 "R1_init":    ["P1"],
 "door1":      ["N8"],
 "door6":      ["P2"],
 "door7":      ["P2"],
 "door11":     ["P2"],
 "rout_57":    ["P5","P7"],
 "rout_58":    ["P5","P8"],
 "rout_67":    ["P6","P7"],
 "rout_68":    ["P6","P8"],
 "R2_pre":     ["P1","P3","P4"],
 "R2_tour":    ["P5","P7","P8","P6"],
 "R2_tour_p6": ["P6","P8","P7","P5"],
 "entry_D2_p6":["N10"],
 "entry_D3_p6":["N10"],
 "entry_far_p6":["N8","N10"],
}

def full_verify(edges, adj, W_len, W_turn, W_obs):
    print(f"\n===== 全量必经点复现（W_len={W_len}, W_turn={W_turn}, W_obs={W_obs}）=====")
    tot = ok = 0
    for name, path in REF.items():
        wps = REF_WP[name]
        r = split_at_waypoints(edges, adj, path, wps, W_len, W_turn, W_obs, name)
        tot += 1
        if r: ok += 1
        print(f"  => {name}: {'复现' if r else '有差异'}")
    print(f"  总计 {ok}/{tot} 条路线复现")
    return ok == tot

def plan_via_waypoints(edges, adj, wps, W_len, W_turn, W_obs):
    """镜像 C 的 nav_plan_waypoints：相邻必经点最短路径，去重连接点，返回完整节点序列。"""
    # 去掉相邻重复必经点（如 [N3,N8,N8] -> [N3,N8]）
    wp = []
    for w in wps:
        if not wp or wp[-1] != w:
            wp.append(w)
    route = []
    for i in range(len(wp)-1):
        seg, _ = dijkstra(edges, adj, NODE_IDX[wp[i]], NODE_IDX[wp[i+1]], W_len, W_turn, W_obs)
        if seg is None:
            return None
        segnames = names(seg)
        if route and segnames[0] == route[-1]:
            route.extend(segnames[1:])
        else:
            route.extend(segnames)
    return route

def full_route_verify(edges, adj, W_len, W_turn, W_obs):
    print(f"\n===== 完整 route 输出核对（nav_plan_waypoints 镜像，W_len={W_len}, W_turn={W_turn}, W_obs={W_obs}）=====")
    ok = 0; tot = 0
    for name, path in REF.items():
        wps = [path[0]] + REF_WP[name] + [path[-1]]
        got = plan_via_waypoints(edges, adj, wps, W_len, W_turn, W_obs)
        if got is None:
            print(f"  [ERR] {name}: 无路"); continue
        tot += 1
        if got == path:
            ok += 1
            print(f"  [匹配] {name}")
        else:
            print(f"  [差异] {name}")
            print(f"         期望: {' '.join(path)}")
            print(f"         实际: {' '.join(got)}")
    print(f"  完整route匹配 {ok}/{tot}")

def build_route_mirror(edges, adj, wps, W_len, W_turn, W_obs):
    """镜像 C 的 nav_build_route：规划含起点路径，去掉起点(保留0xFF)"""
    full = plan_via_waypoints(edges, adj, wps, W_len, W_turn, W_obs)
    if full is None:
        return None
    # full 无 0xFF；这里 route 期望 = full[1:]（起点在 full[0]）
    return full[1:]

def build_route_verify(edges, adj, W_len, W_turn, W_obs):
    print("\n===== nav_build_route 输出核对 =====")
    cases = [
        ("R1_init", ["N2","P1","N5"], ["B1","N1","P1","N1","B2","N4","N5"]),
        ("R2_pre", ["N2","P1","P3","P4","N5"], ["B1","N1","P1","N1","B2","N4","N3","P3","N3","N4","N5","N6","P4","N6","N5"]),
    ]
    for name, wps, exp in cases:
        got = build_route_mirror(edges, adj, wps, W_len, W_turn, W_obs)
        ok = (got == exp)
        print(f"  [{ '匹配' if ok else '差异' }] {name}: {' '.join(got) if got else 'N/A'}")
        if not ok:
            print(f"        期望: {' '.join(exp)}")

if __name__ == "__main__":
    edges = parse_graph()
    adj = build_adj(edges)
    print(f"解析出 {len(edges)} 条边；节点 {len(adj)} 个")
    validate_ref(edges, adj)

    W_len, W_turn, W_obs = 1.0, 0.6, 1.0

    print("\n=== 整条路线 Dijkstra（无 waypoint 约束，观察哪些需要约束）===")
    run_ref_dijkstra(edges, adj, W_len, W_turn, W_obs)

    print("\n++++++++++++++ 全量必经点细分（真实设计） ++++++++++++++")
    allok = full_verify(edges, adj, W_len, W_turn, W_obs)

    print("\n=== 权重灵敏度（关掉转角/障碍，看是否仍复现 → 判断权重是否承重）===")
    for turn, obs in [(0.0,0.0),(0.6,1.0)]:
        full_verify(edges, adj, W_len, turn, obs)

    print("\n++++++++++++++ 完整 route 拼接核对 ++++++++++++++")
    full_route_verify(edges, adj, W_len, W_turn, W_obs)

    print("\n++++++++++++++ nav_build_route 输出（去掉起点 route[]）核对 ++++++++++++++")
    build_route_verify(edges, adj, W_len, W_turn, W_obs)
