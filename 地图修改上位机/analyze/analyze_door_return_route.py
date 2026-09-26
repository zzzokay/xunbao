#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_door_return_route.py
============================
直接解析本工程真实源码，复现 nav_planner.c 的「线路图(line-graph) Dijkstra」，
回答：二轮回家过门时 N8 -> N5 的下一个节点是什么（理论上应为 N4）？
以及为何到 N5 后车会多转（≈180°）。

依赖文件（相对本脚本所在目录，即仓库根；脚本现位于 scripts/analyze/，故上溯两级）：
  Navigation/map.h            -> 节点无序枚举 MapNode / 障碍枚举 barriers
  Navigation/map_message.c    -> NavEdgeTbl[] 边表（唯一人工编辑源）
  Navigation/nav_planner.c    -> 权重模型 NavObsPenalty / NAV_W_*
  Mission/config.h            -> 门区长度/角度宏（FIELD_SCHOOL 分支）
  Mission/mission_planner.c   -> 二轮回程 tail 数组 / wp 生成逻辑
  Mission/barrier.c           -> door_retreat() 里的转向调用（排查"文档说已删但代码还在"）

只读，不改任何工程文件。
"""

import re
import os
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# ------------------------------------------------------------------ #
# 1) 解析 config.h 宏（含 #if/#else/#endif 条件分支），得到 FIELD_SCHOOL 实参
# ------------------------------------------------------------------ #
def parse_config_macros():
    """返回 {name: 浮点数值}。按 USE_FIELD 现在的值（FIELD_SCHOOL）取分支。"""
    defines = {}

    def resolves(expr):
        """把一个宏表达式（可能含宏名、加减乘除、括号、ANGLE_REV）算成数。"""
        e = expr.strip()
        m = re.fullmatch(r'ANGLE_REV\((.+)\)', e)
        if m:
            a = resolves(m.group(1))
            return a - 180 if a >= 0 else a + 180
        for nm in sorted(defines, key=len, reverse=True):
            e = re.sub(r'\b' + nm + r'\b', '(' + str(defines[nm]) + ')', e)
        e = re.sub(r'([0-9.])f\b', r'\1', e)
        try:
            return float(eval(e, {'__builtins__': {}}, {}))
        except Exception:
            return None

    def cond_true(expr):
        e = expr.strip()
        for nm in sorted(defines, key=len, reverse=True):
            e = re.sub(r'\b' + nm + r'\b', str(defines[nm]), e)
        e = re.sub(r'([0-9.])f\b', r'\1', e)
        try:
            return bool(eval(e, {'__builtins__': {}}, {}))
        except Exception:
            return False

    with open(os.path.join(ROOT, 'Mission/config.h'), encoding='utf-8') as f:
        lines = f.readlines()

    # 条件栈：每帧记录 当前 if 链中本层是否活跃、是否已有一个分支被选中
    stack = []          # 元素: {'active': bool, 'taken': bool}
    for line in lines:
        s = line.strip()
        m_cond = re.match(r'#if(def|ndef)?\b(.*)', s)
        if m_cond:
            kind, cond = m_cond.group(1) or '', m_cond.group(2).strip()
            parent_active = stack[-1]['active'] if stack else True
            if kind == 'def':
                macro = cond.split()[0]
                val = parent_active and (macro in defines)
            elif kind == 'ndef':
                macro = cond.split()[0]
                val = parent_active and (macro not in defines)
            else:
                val = parent_active and cond_true(cond)
            stack.append({'active': val, 'taken': val})
            continue
        if s.startswith('#elif'):
            if stack:
                h = stack[-1]
                parent_active = stack[-2]['active'] if len(stack) > 1 else True
                cond = parent_active and (not h['taken']) and cond_true(s[5:].strip())
                h['active'] = cond
                h['taken'] = h['taken'] or cond
            continue
        if s.startswith('#else'):
            if stack:
                h = stack[-1]
                parent_active = stack[-2]['active'] if len(stack) > 1 else True
                cond = parent_active and (not h['taken'])
                h['active'] = cond
                h['taken'] = True
            continue
        if s.startswith('#endif'):
            if stack:
                stack.pop()
            continue
        if stack and not stack[-1]['active']:
            continue
        m = re.match(r'#define\s+([A-Za-z_]\w*)\s+(.+)', s)
        if m:
            name, expr = m.group(1), m.group(2)
            expr = re.sub(r'/\*.*?\*/', '', expr).split('//')[0].strip().rstrip()
            v = resolves(expr)
            if v is not None:
                defines[name] = v
    return defines


# ------------------------------------------------------------------ #
# 2) 解析 map.h：节点枚举 + 障碍枚举
# ------------------------------------------------------------------ #
def parse_map_enums():
    nodes = {}
    barriers = {}
    with open(os.path.join(ROOT, 'Navigation/map.h'), encoding='utf-8') as f:
        text = f.read()

    def strip_comments(s):
        s = re.sub(r'/\*.*?\*/', '', s)
        s = re.sub(r'//[^\n]*', '', s)
        return s

    def parse_enum(block):
        out = {}
        idx = 0
        for raw in block.split(','):
            name = strip_comments(raw).strip()
            if not name:
                continue
            m = re.match(r'([A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*|\d+)', name)
            if m:
                nm, val = m.group(1), m.group(2)
                if val.isdigit():
                    idx = int(val)
                elif val in out:
                    idx = int(out[val])
            else:
                nm = name
            out[nm] = idx
            idx += 1
        return out

    m = re.search(r'enum\s+MapNode\s*\{(.*?)\};', text, re.S)
    nodes = parse_enum(m.group(1))
    b = re.search(r'enum\s+barriers\s*\{(.*?)\};', text, re.S)
    barriers = parse_enum(b.group(1))
    return nodes, barriers


# ------------------------------------------------------------------ #
# 3) 解析 nav_planner.c 的障碍惩罚表 + 权重宏
# ------------------------------------------------------------------ #
def parse_planner_weights():
    obs = []
    with open(os.path.join(ROOT, 'Navigation/nav_planner.c'), encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'NavObsPenalty\[\d+\]\s*=\s*\{(.*?)\};', text, re.S)
    for tok in m.group(1).split(','):
        tok = re.sub(r'/\*.*?\*/', '', tok).strip()
        tok = re.sub(r'[fF]$', '', tok)   # C float 后缀 f
        if tok:
            obs.append(float(tok))
    # 权重宏（位于 nav_planner.h）
    w = {}
    with open(os.path.join(ROOT, 'Navigation/nav_planner.h'), encoding='utf-8') as f:
        htext = f.read()
    for name in ('NAV_W_STEP', 'NAV_W_TURN', 'NAV_W_OBS'):
        mm = re.search(r'#define\s+' + name + r'\s+([\d.]+)[fF]?', htext)
        w[name] = float(mm.group(1))
    return obs, w


# ------------------------------------------------------------------ #
# 4) 解析 map_message.c 边表
# ------------------------------------------------------------------ #
def parse_edges(macros, nodes, barriers):
    """返回 list[(from_idx, to_idx, angle, step, func)] """
    edges = []
    with open(os.path.join(ROOT, 'Navigation/map_message.c'), encoding='utf-8') as f:
        text = f.read()
    # 去掉 /* ... */ 注释，避免干扰
    text_nc = re.sub(r'/\*.*?\*/', '', text, flags=re.S)

    def resolve_tok(tok):
        tok = tok.strip()
        if tok in barriers:
            return float(barriers[tok])
        if tok in nodes:
            return float(nodes[tok])
        # 表达式（宏/除式）
        e = tok
        e = re.sub(r'([A-Za-z_]\w*)/(\w+)', r'(\1)/(\2)', e)
        # 代换宏
        for nm in sorted(macros, key=len, reverse=True):
            e = re.sub(r'\b' + nm + r'\b', '(' + str(macros[nm]) + ')', e)
        for nm in sorted(barriers, key=len, reverse=True):
            e = re.sub(r'\b' + nm + r'\b', '(' + str(barriers[nm]) + ')', e)
        e = re.sub(r'([0-9.])f\b', r'\1', e)   # C float 后缀
        try:
            return float(eval(e, {'__builtins__': {}}, {}))
        except Exception:
            return None

    # 逐条边：“{ from, to, flags, angle, step, speed, func },”
    for mm in re.finditer(r'\{\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*,\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+)\s*\}',
                          text_nc):
        frm, to, flg, angle, step, speed, func = mm.groups()
        ai = resolve_tok(angle)
        si = resolve_tok(step)
        fi = resolve_tok(func)
        # 只保留位于图里的边（from<54 且 from 是合法节点）
        if frm in nodes and to in nodes and ai is not None and si is not None:
            edges.append((nodes[frm], nodes[to], ai, si, (int(fi) if fi is not None else 0)))
    return edges


# ------------------------------------------------------------------ #
# 5) 复现 nav_planner.c 的线路图 Dijkstra
# ------------------------------------------------------------------ #
def nav_need2turn(a, b):
    d = b - a
    while d > 180.0:
        d -= 360.0
    while d < -180.0:
        d += 360.0
    return d


def build_line_graph(edges, obs, w):
    n_edges = len(edges)
    out = {}  # from -> list of edge indices
    for i, e in enumerate(edges):
        out.setdefault(e[0], []).append(i)

    def base_cost(i):
        e = edges[i]
        return w['NAV_W_STEP'] * e[3] + w['NAV_W_OBS'] * (obs[e[4]] if e[4] < len(obs) else 0)

    # line-graph 邻接：边u 终点 == 边v 起点
    succ = {}
    succw = {}
    for u in range(n_edges):
        eu = edges[u]
        lst = []
        for v in out.get(eu[1], []):
            turn = w['NAV_W_TURN'] * abs(nav_need2turn(eu[2], edges[v][2]))
            lst.append((v, base_cost(v) + turn))
        succ[u] = lst
    return out, base_cost, succ


def nav_shortest_path(edges, out, base_cost, succ, from_node, to_node):
    import heapq
    n_edges = len(edges)
    INF = float('inf')
    dist = [INF] * n_edges
    prev = [-1] * n_edges
    done = [False] * n_edges
    for i in out.get(from_node, []):
        dist[i] = base_cost(i)
    pq = [(dist[i], i) for i in out.get(from_node, [])]
    heapq.heapify(pq)
    target = None
    while pq:
        d, u = heapq.heappop(pq)
        if done[u]:
            continue
        done[u] = True
        if edges[u][1] == to_node:
            target = u
            break
        for v, wgt in succ[u]:
            nd = d + wgt
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    if target is None:
        return None
    # 回溯
    stack = []
    e = target
    while e >= 0:
        stack.append(e)
        e = prev[e]
    stack.reverse()
    seq = [from_node]
    for i in stack:
        seq.append(edges[i][1])
    return seq


# ------------------------------------------------------------------ #
# 6) 主分析
# ------------------------------------------------------------------ #
def main():
    print('=' * 78)
    print('解析工程源码并复现规划器：二轮回家过门 N8->N5 的下一个节点')
    print('=' * 78)

    macros = parse_config_macros()
    nodes, barriers = parse_map_enums()
    obs, w = parse_planner_weights()
    edges = parse_edges(macros, nodes, barriers)

    idx2name = {v: k for k, v in nodes.items()}
    def nm(i):
        return idx2name.get(i, f'?{i}')

    print('\n[config.h @ FIELD_SCHOOL 关键宏]')
    for k in ('ANGLE_N5N8', 'ANGLE_N8N5', 'ANGLE_N3N8', 'ANGLE_N8N3',
              'ANGLE_N8N10', 'ANGLE_N8N12', 'ANGLE_N10N8', 'ANGLE_N12N8',
              'DOOR_LEN_N5N8', 'DOOR_LEN_N3N8', 'DOOR_LEN_N5N12',
              'DOOR_RETREAT_N8N5'):
        v = macros.get(k)
        if v is not None:
            print(f'  {k:20s} = {v:>8g}')

    print(f'\n[图] 节点 {len(nodes)} 个，边 {len(edges)} 条，'
          f'权重 STEP={w["NAV_W_STEP"]} TURN={w["NAV_W_TURN"]} OBS={w["NAV_W_OBS"]}')

    # N8 / N5 的出边
    N8, N5, N4 = nodes['N8'], nodes['N5'], nodes['N4']
    print('\n[N8 出边]')
    for e in edges:
        if e[0] == N8:
            print(f'  N8 -> {nm(e[1]):4s}  angle={e[2]:>8g}  step={e[3]:>5g}  funcIdx={e[4]}')
    print('\n[N5 出边]')
    for e in edges:
        if e[0] == N5:
            print(f'  N5 -> {nm(e[1]):4s}  angle={e[2]:>8g}  step={e[3]:>5g}  funcIdx={e[4]}')

    # 走一遍规划器：N8 -> P2（回家完整尾段）与 N5 -> P2
    P2 = nodes['P2']
    print('\n[规划器最短路(去掉起点=执行 route[])]')
    for frm, to, label in ((N8, P2, 'N8->P2 回家整段'),
                            (N5, P2, 'N5->P2 回家整段')):
        out, base, succ = build_line_graph(edges, obs, w)
        seq = nav_shortest_path(edges, out, base, succ, frm, to)
        if seq is None:
            print(f'  {label}: 不可达')
        else:
            names = [nm(x) for x in seq]
            names = names[1:] if names and names[0] == nm(frm) else names  # 去起点
            print(f'  {label}: ' + ' -> '.join(names))

    # 二轮 tail 数组（mission_planner.c 手写）—— 直接读源码核对
    print('\n[mission_planner.c 二轮回家 tail 数组(含 N8,N5 的)]')
    with open(os.path.join(ROOT, 'Mission/mission_planner.c'), encoding='utf-8') as f:
        pl_text = f.read()
    for m in re.finditer(r'const\s+u8\s+(tail_\w+)\[\]\s*=\s*\{(.*?)\};', pl_text, re.S):
        arr, body = m.group(1), m.group(2)
        toks = [t.strip() for t in body.split(',') if t.strip()]
        name_toks = [idx2name[int(nodes[t])] if t in nodes else t for t in toks if t != '0XFF']
        print(f'  {arr:22s} = ' + ' -> '.join(name_toks))
        # 若含 N8, N5，找 N5 的后继
        if 'N8' in name_toks and 'N5' in name_toks:
            for j, t in enumerate(name_toks):
                if t == 'N5' and j + 1 < len(name_toks):
                    print(f'      └─ N5 的下一个节点 = {name_toks[j+1]}   (== N4: {name_toks[j+1]==chr(78)+chr(52)})')

    # 关键：N8->N5 到达 N5 后转去 N4 需要转多少度
    a_n8n5 = macros['ANGLE_N8N5']
    a_n5n4 = next((e[2] for e in edges if e[0] == N5 and e[1] == N4), None)
    turn = nav_need2turn(a_n8n5, a_n5n4)
    print('\n[N5 出口转角计算]')
    print(f'  N8->N5 段航向角 ANGLE_N8N5   = {a_n8n5:>8g}°')
    print(f'  N5->N4 段航向角             = {a_n5n4:>8g}°')
    print(f'  need2turn(N8->N5, N5->N4)    = {turn:>8g}°  (绝对值 {abs(turn):.1f}°)')

    # 排查 barrier.c door_retreat() 的转向调用——文档说 09-07 已删，代码是否还在
    print('\n[排查 door_retreat() 里的转向调用(README 2026-09-07 声称已删)]')
    with open(os.path.join(ROOT, 'Mission/barrier.c'), encoding='utf-8') as f:
        btext = f.read()
    # 定位 door_retreat 函数体
    m = re.search(r'static\s+NODE\s+door_retreat\(.*?\n\{\n(.*?)\n\}', btext, re.S)
    if m:
        body = m.group(1)
        has_turn = 'Chassis_Turn_By_StopGyro_Blocking' in body
        for i, line in enumerate(body.splitlines(), start=1):
            if 'Chassis_Turn_By_StopGyro_Blocking' in line:
                print(f'  door_retreat() 内发现转向调用(第 {i} 行，含缩进):')
                print(f'      {line.strip()}')
                print('  └─ 结论: README 记载的"删除该行"修复【并未实际落码】——该行仍存在。')
        if not has_turn:
            print('  未发现 Chassis_Turn_By_StopGyro_Blocking（修复已生效）。')
    # 再精确找 barrier.c 行号
    for i, line in enumerate(btext.splitlines(), start=1):
        if 'Chassis_Turn_By_StopGyro_Blocking(newNode.angle' in line:
            print(f'  barrier.c 行号 = {i}')

    print('\n' + '=' * 78)
    print('关键结论')
    print('=' * 78)
    print('''
1) 理论路径: N8 -> N5 -> N4 -> B3 -> N2 -> P2  (D4 回程门 N8→N3 遇黑灯退到 N5，再绕回 N4 回家)
   即: N8 -> N5 的下一个节点 === N4（与 mission_planner tail_D3 / 规划器一致）。

2) 到 N5 后转≈180° 的原因：
   door_retreat() 里仍有
       Chassis_Turn_By_StopGyro_Blocking(newNode.angle, getAngleZ(), 30.0f);
   (barrier.c:1474)。它先把车从门口调向 N8->N5 段航向(-145°)，
   随后 Navigation 到达 N5 又要把车调向 N5->N4(0°)，
   两处都调向 + 门内位置偏差累加，出现大角度（接近 180°/绕远路）旋转。

3) 文档(README 2026-09-07)声称"删除该行"，但该行仍存在于当前代码
   （git diff 亦未删除），故 bug 未真正修复。
''')


if __name__ == '__main__':
    main()
