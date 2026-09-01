import _weight_calib as W
import re

# 1) 镜像 nav_graph_init：从 NavEdgeTbl 构建 ConnectionNum/Address/Node[CSR]
edges = W.parse_graph()  # 已是 from/to/angle/step/func
# 按 from 计数，重建 CSR 顺序
from collections import defaultdict
byfrom = defaultdict(list)
for e in edges:
    byfrom[e["from"]].append(e)
# 保持 NavEdgeTbl 数组顺序（_weight_calib 是按 from 排序读的），这里按 from 排序组内顺序用原序
# 用与 nav_graph_init 相同的“按表顺序放置”逻辑：
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
        if node[i] == t:
            return i
    return None

# 2) 校验所有参考路线的每条相邻边都能被 getNextConnectNode 找到
ok = bad = 0
for name, path in W.REF.items():
    for i in range(len(path)-1):
        r = getNextConnectNode(W.NODE_IDX[path[i]], W.NODE_IDX[path[i+1]])
        if r is None:
            bad += 1
            print(f"  [缺边] {name}: {path[i]}->{path[i+1]}")
        else:
            ok += 1
print(f"getNextConnectNode(自动CSR) 解析参考边: 成功 {ok}, 失败 {bad}")
print(f"连接总数(addr[54])={addr[54]}  应与 NAV_EDGE_COUNT={len(edges)} 一致: {'OK' if addr[54]==len(edges) else 'MISMATCH'}")

# 3) 校验 door_set_pass_node 需要修改的门边也能被找到
for (a,b) in [("N5","N12"),("N12","N5"),("N5","N8"),("N8","N5"),("N3","N8"),("N8","N3"),("N3","N10"),("N10","N3")]:
    r = getNextConnectNode(W.NODE_IDX[a], W.NODE_IDX[b])
    print(f"  door边 {a}->{b}: {'OK' if r is not None else 'MISSING'}")
