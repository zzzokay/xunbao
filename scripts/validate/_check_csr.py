# -*- coding: utf-8 -*-
"""校验：从 map_message.c 的 NavEdgeTbl[] 自动构建的 CSR（ConnectionNum/Address/Node）
能否被 getNextConnectNode 正确解析全部参考边与门边。增删边后必跑。只读，不改代码。"""
import _weight_calib as W
import sys

edges = W.parse_graph()

# 1) 镜像 map_message.c 的 nav_graph_init：按 from 分组构建 CSR
conn = [0]*54
for e in edges:
    conn[e["from"]] += 1
addr = [0]*55
for v in range(54):
    addr[v+1] = addr[v] + conn[v]
node = [None]*132
cur = addr[:54]
for e in edges:
    p = cur[e["from"]]; cur[e["from"]] += 1
    node[p] = e["to"]

def getNextConnectNode(f, t):
    if f >= 54: return None
    for i in range(addr[f], addr[f]+conn[f]):
        if node[i] == t: return i
    return None

# 2) 校验参考路线每条相邻边
ok = bad = 0
for name, path in W.REF.items():
    for i in range(len(path)-1):
        r = getNextConnectNode(W.NODE_IDX[path[i]], W.NODE_IDX[path[i+1]])
        if r is None:
            bad += 1; print(f"  [缺边] {name}: {path[i]}->{path[i+1]}")
        else:
            ok += 1
print(f"getNextConnectNode(自动CSR) 解析参考边: 成功 {ok}, 失败 {bad}")
addr_ok = (addr[54]==len(edges))
print(f"addr[54]={addr[54]} 应==NAV_EDGE_COUNT={len(edges)}: {'OK' if addr_ok else 'MISMATCH'}")

# 3) 校验 8 条门边
door_bad = 0
for (a,b) in [("N5","N12"),("N12","N5"),("N5","N8"),("N8","N5"),("N3","N8"),("N8","N3"),("N3","N10"),("N10","N3")]:
    r = getNextConnectNode(W.NODE_IDX[a], W.NODE_IDX[b])
    ok_str = 'OK' if r is not None else 'MISSING'
    if r is None: door_bad += 1
    print(f"  door边 {a}->{b}: {ok_str}")

all_ok = (bad == 0 and addr_ok and door_bad == 0)
sys.exit(0 if all_ok else 1)  # 返回 exit code：全部通过=0，失败=1
