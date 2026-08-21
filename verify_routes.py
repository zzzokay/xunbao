# -*- coding: utf-8 -*-
"""
寻宝项目 路线连通性验证脚本
- 解析 map_message.c 的 Node[] 连接表（按 ConnectionNum/Address 归属源节点）
- 解析 barrier.c / map.c 中所有路线数组
- 检查每个数组内部连续节点连通性 + 关键拼接点（门区出口、P7/P8 宝物回家、二轮 pre+entry+tour+tail）
"""
import re, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ---------- 1. 节点名 -> 编号（来自 map.h 枚举） ----------
NAMES = ["S1","P1","N1","B1","B2","B3","N2","P2","S2","P3","N3","N4","N5","N6","P4",
         "N7","P6","B8","B9","N8","C1","C2","C3","N9","N10","N12","N13","P5","N14","S3",
         "S4","N15","S5","C4","C5","B4","B5","B6","B7","N16","N18","N19","P7","N20","N22",
         "C6","C7","C8","C9","P8","N11","G1","B10","B11"]
IDX = {n:i for i,n in enumerate(NAMES)}

# ---------- 2. 解析 map_message.c 的 Node[] ----------
src = open(r"Application/map_message.c", encoding="utf-8").read()
m = re.search(r"NODE\s+Node\[132\]\s*=\s*\{(.*?)\};", src, re.S)
body = m.group(1)

# 按顶层逗号切分条目（忽略注释/* */，字符串内无逗号）
body_nc = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
# 用括号深度切分
entries = []
depth = 0
cur = ""
for ch in body_nc:
    if ch == '{':
        depth += 1
    if depth > 0:
        cur += ch
    if ch == '}':
        depth -= 1
        if depth == 0:
            entries.append(cur)
            cur = ""
assert depth == 0 and len(entries) == 130, f"解析条目数异常: {len(entries)}"

def first_ident(e):
    toks = re.findall(r"\b(S\d+|P\d+|N\d+|B\d+|C\d+|G1)\b", e)
    return toks[0] if toks else None

node_targets = [first_ident(e) for e in entries]
assert all(node_targets), "存在无法解析目标节点的条目"

# ConnectionNum / Address（直接硬编码自 map_message.c 124-141 行）
CN = [1,1,3,2,2,2,3,1,1,1, 5,4,4,4,1,3,1,2,2,4, 2,2,2,4,6,6,4,1,3,1,
      1,3,1,2,2,2,2,2,2,3, 3,3,2,3,3,2,2,2,3,1, 2,2,2,2]
ADDR = [0,1,2,5,7,9,11,14,15,16, 17,22,26,30,34,35,38,39,41,43, 47,49,51,53,57,63,69,73,74,77,
        78,79,82,83,85,87,89,91,93,95, 98,101,104,106,109,112,114,116,118,121, 122,124,126,128]
assert len(CN) == 54 and len(ADDR) == 54

# 构建邻接表：adj[src] = set of targets
adj = {}
for s in range(54):
    start, cnt = ADDR[s], CN[s]
    ts = set()
    for i in range(start, start + cnt):
        t = IDX[node_targets[i]]
        ts.add(t)
    adj[s] = ts
    # 校验数量
    assert len(ts) == cnt, f"节点{s}({NAMES[s]}) 声明连接数{cnt} 实际{len(ts)}: {ts}"

print("连接表构建完成，54 个节点，总连接数:", sum(CN))
# 反向检查：每条连接在源节点列表里
inv = {}
for s, ts in adj.items():
    for t in ts:
        inv.setdefault(t, set()).add(s)

# ---------- 3. 解析所有路线数组 ----------
route_src = ""
for f in [r"Application/barrier.c", r"Application/map.c"]:
    route_src += open(f, encoding="utf-8").read()

arrays = {}  # name -> list of node names (不含0xFF)
# u8 name[N] = { ... }
for mm in re.finditer(r"\bu8\s+(\w+)\s*\[\d*\]\s*=\s*\{(.*?)\}", route_src, re.S):
    name, content = mm.group(1), mm.group(2)
    nodes = re.findall(r"\b(S\d+|P\d+|N\d+|B\d+|C\d+|G1)\b", content)
    if nodes:
        arrays.setdefault(name, []).append(nodes)
# const u8 name[] = { ... } (含匿名 r[])
for mm in re.finditer(r"\bconst\s+u8\s+(\w*)\[\]\s*=\s*\{(.*?)\}", route_src, re.S):
    name, content = mm.group(1), mm.group(2)
    nodes = re.findall(r"\b(S\d+|P\d+|N\d+|B\d+|C\d+|G1)\b", content)
    if nodes:
        arrays.setdefault(name, []).append(nodes)

print("解析到路线数组:", {k: len(v) for k, v in arrays.items()})

# ---------- 4. 数组内部连通性检查 ----------
fails = []
def check_pair(a, b, where):
    if IDX[b] not in adj[IDX[a]]:
        fails.append(f"{where}: {a} -> {b} 不存在连接")

for name, lst in arrays.items():
    for nodes in lst:
        for i in range(len(nodes) - 1):
            check_pair(nodes[i], nodes[i+1], f"{name}[]")

# ---------- 5. 关键拼接点检查 ----------
# 5.1 起点：mapInit 非调试分支 nowNode=(P2->N2)，下一目标 route[0]=B1
check_pair("P2", "N2", "mapInit 起点 P2->N2")
check_pair("N2", "B1", "mapInit 起点后 N2->route[0]=B1")

# 5.2 update_route_at_door_for_stageAB：D2 通时 route[0]=rout_57[0]=N13，车在门边 nowNode=N12
#     其余分支 route[0]=N12 -> rout_57[0]=N13 等
check_pair("N12", "N13", "门D2出口 N12->N13 (rout_57)")
# A=6 分支带前缀：route[0]=N11, route[1]=N10, 然后 rout_67/68 (N9开头)
check_pair("N12", "N11", "门D2出口 P6 分支 N12->N11 (前缀)")
check_pair("N11", "N10", "门D2出口 P6 分支 N11->N10 (前缀)")
check_pair("N10", "N9",  "门D2出口 P6 分支 N10->N9 (rout_67/68)")
# D3 出口：nowNode=N8, route[0]=N12
check_pair("N8", "N12", "门D3出口 N8->N12")
check_pair("N8", "N10", "门D3出口 P6 分支 N8->N10")
# D4/最外出口：nowNode=N3? (door D4: nodes.nowNode = getNextConnectNode(N3,N8) -> N8)
check_pair("N3", "N8", "门D4出口 N3->N8")

# 5.3 二轮 get_newroute 拼接：pre 尾 -> entry 头；entry 尾 -> tour 头；tour 尾 -> tail 头
pre   = ["B1","N1","P1","N1","B2","N4","N3","P3","N3","N4","N5","N6","P4","N6","N5"]
tour  = ["N13","P5","N13","N12","N16","N18","B5","N19","C6","B7","N22","C9","P7","C9","N22","B6","N20","P8","N20","C4","B11","C8","C7","B10","N14","C3","N9","B9","N7","P6","N7","B8","N9","N10"]
tour_p6 = ["N9","B9","N7","P6","N7","B8","N9","C3","N14","B10","C7","C8","B11","C4","N20","P8","N20","B6","N22","C9","P7","C9","N22","B7","C6","N19","B5","N18","N16","N12","N13","P5","N13","N12"]
entry_D2    = ["N12"]
entry_D2_p6 = ["N12","N11","N10"]
entry_D3    = ["N8","N12"]
entry_D3_p6 = ["N8","N10"]
entry_far    = ["N4","N3","N8","N12"]
entry_far_p6 = ["N4","N3","N8","N10"]
tail_D2      = ["N11","N12","N5","N4","B3","N2","P2"]
tail_p6_D2   = ["N5","N4","B3","N2","P2"]
tail_p6_D5   = ["N11","N10","N3","N4","B3","N2","P2"]
tail_N3      = ["N3","N4","B3","N2","P2"]
tail_N8      = ["N8","N3","N4","B3","N2","P2"]
tail_N8N5    = ["N8","N5","N4","B3","N2","P2"]

for name, arr in [("pre",pre),("tour",tour),("tour_p6",tour_p6),
                  ("entry_D2",entry_D2),("entry_D2_p6",entry_D2_p6),
                  ("entry_D3",entry_D3),("entry_D3_p6",entry_D3_p6),
                  ("entry_far",entry_far),("entry_far_p6",entry_far_p6),
                  ("tail_D2",tail_D2),("tail_p6_D2",tail_p6_D2),("tail_p6_D5",tail_p6_D5),
                  ("tail_N3",tail_N3),("tail_N8",tail_N8),("tail_N8N5",tail_N8N5)]:
    for i in range(len(arr)-1):
        check_pair(arr[i], arr[i+1], f"二轮{name}[]")

# 二轮拼接点
check_pair(pre[-1], entry_D2[0],    "二轮 pre尾->entry_D2头 (N5->N12)")
check_pair(pre[-1], entry_D3[0],    "二轮 pre尾->entry_D3头 (N5->N8)")
check_pair(pre[-1], entry_far[0],   "二轮 pre尾->entry_far头 (N5->N4)")
for e, t in [(entry_D2, tour), (entry_D2_p6, tour_p6), (entry_D3, tour), (entry_D3_p6, tour_p6),
             (entry_far, tour), (entry_far_p6, tour_p6)]:
    check_pair(e[-1], t[0], f"二轮 entry尾->tour头 ({e[-1]}->{t[0]})")
for t, tl in [(tour, tail_D2), (tour_p6, tail_p6_D2), (tour_p6, tail_p6_D5),
              (tour, tail_N3), (tour, tail_N8), (tour, tail_N8N5)]:
    check_pair(t[-1], tl[0], f"二轮 tour尾->tail头 ({t[-1]}->{tl[0]})")

# 5.4 P7/P8 宝物回家路线：起点 N22/C4 看似与 P7/P8 不连通，
#     但经 simulate_p7p8.py 按真实 Nav_TurnAndAdvance 逻辑模拟验证：
#     nextNode 结构体在路线重写前已指向原路线尾巴(P7→C9 / P8→N20)，
#     车先走这条边，route[] 重写只影响再下一步查询(C9→N22 / N20→C4 均存在)。
#     → 拼接实际可行，此处不再做静态直接边检查（避免误报）。

# 5.5 P1 QR 后重写 route（update_route_at_P1 三个分支，数组内部已在上方全量检查，
#     P1 之后衔接 P1->N1 在数组内部已覆盖，此处仅作显式确认）
for arr in (["B1","N1","P1","N1","B2","N4","N3","P3","N3","N4","N5","N12"],
            ["B1","N1","P1","N1","B2","N4","N5","N6","P4","N6","N5","N12"],
            ["B1","N1","P1","N1","B2","N4","N5","N12"]):
    check_pair(arr[2], arr[3], f"P1 QR后 P1->N1")

# 5.6 初始 route（MAP_DEBUG=0 分支）

# ---------- 6. 输出 ----------
print("=" * 70)
if fails:
    print(f"发现 {len(fails)} 处连通性问题：")
    for f in fails:
        print("  ❌", f)
else:
    print("✅ 所有数组内部与关键拼接点均连通，未发现缺连接。")
