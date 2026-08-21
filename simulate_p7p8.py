# -*- coding: utf-8 -*-
"""
精确模拟 Navigation() 的节点推进逻辑，验证 P7/P8 宝物回家路线的拼接
按 map.c / barrier.c 的真实代码逻辑逐步执行
"""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

NAMES = ["S1","P1","N1","B1","B2","B3","N2","P2","S2","P3","N3","N4","N5","N6","P4",
         "N7","P6","B8","B9","N8","C1","C2","C3","N9","N10","N12","N13","P5","N14","S3",
         "S4","N15","S5","C4","C5","B4","B5","B6","B7","N16","N18","N19","P7","N20","N22",
         "C6","C7","C8","C9","P8","N11","G1","B10","B11"]
IDX = {n:i for i,n in enumerate(NAMES)}

def idxlist(lst):
    return [v if v == 0xFF else IDX[v] for v in lst]

src = open(r"Application/map_message.c", encoding="utf-8").read()
m = re.search(r"NODE\s+Node\[132\]\s*=\s*\{(.*?)\};", src, re.S)
body_nc = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)
entries = []
depth = 0; cur = ""
for ch in body_nc:
    if ch == '{': depth += 1
    if depth > 0: cur += ch
    if ch == '}':
        depth -= 1
        if depth == 0: entries.append(cur); cur = ""

def first_ident(e):
    t = re.findall(r"\b(S\d+|P\d+|N\d+|B\d+|C\d+|G1)\b", e)
    return t[0] if t else None
targets = [first_ident(e) for e in entries]

CN = [1,1,3,2,2,2,3,1,1,1, 5,4,4,4,1,3,1,2,2,4, 2,2,2,4,6,6,4,1,3,1,
      1,3,1,2,2,2,2,2,2,3, 3,3,2,3,3,2,2,2,3,1, 2,2,2,2]
ADDR = [0,1,2,5,7,9,11,14,15,16, 17,22,26,30,34,35,38,39,41,43, 47,49,51,53,57,63,69,73,74,77,
        78,79,82,83,85,87,89,91,93,95, 98,101,104,106,109,112,114,116,118,121, 122,124,126,128]

# 连接表（含每条边的 function）
EDGES = {}  # (src, dst) -> dict(angle, step, speed, function, flag)
for s in range(54):
    for i in range(ADDR[s], ADDR[s] + CN[s]):
        e = entries[i]
        toks = re.split(r"[{},]", e)
        toks = [t.strip() for t in toks if t.strip()]
        dst = toks[0]
        func = None
        for t in toks[1:]:
            if t in ("NONE","UpStage","Bridge","Hill","SM","View","View1","BACK","BSoutPole","QQB","BLBS","BLBL","DOOR","BHM","IGNORE","Special_node","DOOR1","UpStageHome","LBHill"):
                func = t
        EDGES[(s, IDX[dst])] = {"function": func}

class State:
    def __init__(self, route):
        self.route = (route + [0xFF] * 100)[:100]  # u8 route[100] 数组
        self.point = 0
        self.routetime = 0
        self.lastNode = None       # (src, dst)
        self.nowNode = None        # (src, dst)
        self.nextNode = None
        self.cross = 0

def getNext(s, a, b):
    """模拟 getNextConnectNode + 兜底"""
    if (a, b) not in EDGES:
        return None  # 兜底死停
    return (a, b)

def mapInit(s):
    s.point = 0
    e = getNext(s, IDX["P2"], IDX["N2"])
    s.nowNode = e
    if s.route[s.point] != 0xFF:
        s.nextNode = getNext(s, s.nowNode[1], s.route[s.point])
    s.point += 1

def advance(s, where):
    """模拟 Nav_TurnAndAdvance 的节点推进（忽略转弯动作）"""
    if s.route[s.point - 1] != 0xFF:
        s.lastNode = s.nowNode
        s.nowNode = s.nextNode
        if s.route[s.point] != 0xFF:
            nxt = getNext(s, s.nowNode[1], s.route[s.point])
            if nxt is None:
                print(f"  💥 {where}: 推进到 {NAMES[s.nowNode[1]]} 时 nextNode 查 {NAMES[s.nowNode[1]]}->{NAMES[s.route[s.point]]} 失败 → Route_Error_Stop 死停车!")
                return False
            s.nextNode = nxt
        s.point += 1
        return True
    else:
        s.routetime += 1
        print(f"  🏁 {where}: 路线结束 (route[{s.point-1}]=0xFF)，routetime={s.routetime}")
        return True

def postProcess(s):
    """Nav_PostProcess: 门结果后推进"""
    if s.route[s.point] != 0xFF:
        nxt = getNext(s, s.nowNode[1], s.route[s.point])
        if nxt is None:
            print(f"  💥 Nav_PostProcess: {NAMES[s.nowNode[1]]}->{NAMES[s.route[s.point]]} 失败 → 死停车!")
            return False
        s.nextNode = nxt
    s.point += 1
    return True

def load_route_at(s, offset, arr):
    for i, v in enumerate(arr):
        s.route[offset + i] = v
        if v == 0xFF: break

def drive_to(s, target_name, max_steps=80, label=""):
    """模拟行驶：逐步 advance 直到 nowNode 目标为 target 或路线结束"""
    for k in range(max_steps):
        if s.nowNode is None or s.nowNode[1] == IDX[target_name]:
            return True
        # 到达当前边终点 → 触发 advance
        if not advance(s, f"{label} step{k}"):
            return False
    print(f"  ⚠️ {label}: 步数超限")
    return False

def run_scenario(name, clueA, clueB, door, treasure_case_route_start):
    print(f"\n===== 场景: {name} =====")
    # 一轮初始 route
    r = [IDX["B1"],IDX["N1"],IDX["P1"],IDX["N1"],IDX["B2"],IDX["N4"],IDX["N5"],0xFF]
    s = State(r)
    mapInit(s)
    # 行驶到 P1（QR 平台）
    # 简化：直接按 update_route_at_P1 的 flag_line_clue==3 路线重写
    r3 = [IDX["B1"],IDX["N1"],IDX["P1"],IDX["N1"],IDX["B2"],IDX["N4"],IDX["N3"],IDX["P3"],
          IDX["N3"],IDX["N4"],IDX["N5"],IDX["N12"],0xFF]
    load_route_at(s, 0, r3)
    # 行驶到门边 N5→N12
    if not drive_to(s, "N5", label="一轮至N5"): return
    # door(): D2 CAN_PASS → nowNode=(N5→N12), route 重置, update_route_at_door_for_stageAB
    s.point = 0
    s.route[0] = 0xFF
    if door == "D2":
        s.nowNode = (IDX["N5"], IDX["N12"])
    elif door == "D3":
        s.nowNode = (IDX["N5"], IDX["N8"])
    elif door == "D4":
        s.nowNode = (IDX["N3"], IDX["N8"])
    if clueA == 5 and clueB == 7:
        if door == "D2":
            load_route_at(s, 0, idxlist(["N13","P5","N13","N12","N16","N18","B5","N19","C6","B7","N22","C9","P7","C9",0xFF]))
        else:
            s.route[0] = IDX["N12"]
            load_route_at(s, 1, idxlist(["N13","P5","N13","N12","N16","N18","B5","N19","C6","B7","N22","C9","P7","C9",0xFF]))
    elif clueA == 5 and clueB == 8:
        if door == "D2":
            load_route_at(s, 0, idxlist(["N13","P5","N13","N12","N11","N10","N9","C3","N14","B10","C7","C8","B11","C4","N20","P8","N20",0xFF]))
        else:
            s.route[0] = IDX["N12"]
            load_route_at(s, 1, idxlist(["N13","P5","N13","N12","N11","N10","N9","C3","N14","B10","C7","C8","B11","C4","N20","P8","N20",0xFF]))
    elif clueA == 6 and clueB == 7:
        if door == "D2":
            s.route[0] = IDX["N11"]; s.route[1] = IDX["N10"]
            load_route_at(s, 2, idxlist(["N9","B9","N7","P6","N7","B8","N9","C3","N14","B10","C7","C8","B11","C4","N20","B6","N22","C9","P7","C9",0xFF]))
        else:
            s.route[0] = IDX["N10"]
            load_route_at(s, 1, idxlist(["N9","B9","N7","P6","N7","B8","N9","C3","N14","B10","C7","C8","B11","C4","N20","B6","N22","C9","P7","C9",0xFF]))
    elif clueA == 6 and clueB == 8:
        if door == "D2":
            s.route[0] = IDX["N11"]; s.route[1] = IDX["N10"]
            load_route_at(s, 2, idxlist(["N9","B9","N7","P6","N7","B8","N9","C3","N14","B10","C7","C8","B11","C4","N20","P8","N20",0xFF]))
        else:
            s.route[0] = IDX["N10"]
            load_route_at(s, 1, idxlist(["N9","B9","N7","P6","N7","B8","N9","C3","N14","B10","C7","C8","B11","C4","N20","P8","N20",0xFF]))
    if not postProcess(s): return
    # 行驶到 P7/P8 平台（在平台上触发宝物回家路线）
    plat = "P7" if clueB == 7 else "P8"
    if not drive_to(s, plat, label=f"一轮至{plat}"): return
    # 平台上加载宝物回家路线（update_route_at_P7/P8_for_treasure, D2 green, treasure=3..6）
    home_route = idxlist(treasure_case_route_start)
    print(f"  在 {plat} 处加载回家路线起点 {treasure_case_route_start[0]} (map.point={s.point}, route[{s.point}]原值={NAMES[s.route[s.point]] if s.route[s.point]!=0xFF else '0xFF'})")
    load_route_at(s, s.point, home_route)
    # 继续行驶，看是否能走到 P2 回家
    ok = True
    for k in range(60):
        # 触发当前边终点推进
        if not advance(s, f"{plat}回家 step{k}"):
            ok = False; break
        if s.route[s.point-1] == 0xFF:
            break
        if s.nowNode[1] == IDX["P2"]:
            print(f"  ✅ 回到 P2（第{k+1}次推进），routetime={s.routetime}")
            return
    if ok:
        print(f"  ⚠️ 未到 P2 就结束/异常: 最后节点 {NAMES[s.nowNode[1]]}")

# ==================== 二轮全程模拟 ====================
def sim_round2(name, door_pass_state, treasure):
    """door_pass_state: 0=D2,1=D3,2=D4,3=D5 (CAN_PASS/ONE_WAY_PASS/NO_PASS)"""
    print(f"\n===== 二轮模拟: {name} (treasure={treasure}) =====")
    r = [IDX["B1"],IDX["N1"],IDX["P1"],0xFF]
    s = State(r)
    s.routetime = 1
    # get_newroute(): load {B1,N1,P1}, mapInit, Clear_door, build_round2_route
    load_route_at(s, 0, idxlist(["B1","N1","P1",0xFF]))
    mapInit(s)

    pre   = ["B1","N1","P1","N1","B2","N4","N3","P3","N3","N4","N5","N6","P4","N6","N5"]
    tour  = ["N13","P5","N13","N12","N16","N18","B5","N19","C6","B7","N22","C9","P7","C9","N22","B6","N20","P8","N20","C4","B11","C8","C7","B10","N14","C3","N9","B9","N7","P6","N7","B8","N9","N10"]
    tour_p6 = ["N9","B9","N7","P6","N7","B8","N9","C3","N14","B10","C7","C8","B11","C4","N20","P8","N20","B6","N22","C9","P7","C9","N22","B7","C6","N19","B5","N18","N16","N12","N13","P5","N13","N12"]
    use_tour = tour_p6 if treasure == 6 else tour
    entry_D2  = ["N12","N11","N10"] if treasure == 6 else ["N12"]
    entry_D3  = ["N8","N10"] if treasure == 6 else ["N8","N12"]
    entry_far = ["N4","N3","N8","N10"] if treasure == 6 else ["N4","N3","N8","N12"]
    tail_p6_D2 = ["N5","N4","B3","N2","P2"]
    tail_p6_D5 = ["N11","N10","N3","N4","B3","N2","P2"]

    d2, d3, d4, d5 = door_pass_state
    if d2 == "CAN":
        entry, tail = entry_D2, (tail_p6_D2 if treasure == 6 else ["N11","N12","N5","N4","B3","N2","P2"])
    elif d2 == "ONE" and d5 == "CAN":
        entry, tail = entry_D2, (tail_p6_D5 if treasure == 6 else ["N3","N4","B3","N2","P2"])
    elif d2 == "ONE" and d5 == "NO" and d4 == "CAN":
        entry, tail = entry_D2, ["N8","N3","N4","B3","N2","P2"]
    elif d2 == "ONE" and d5 == "NO" and d4 == "NO":
        entry, tail = entry_D2, ["N8","N5","N4","B3","N2","P2"]
    elif d2 == "NO" and d3 == "CAN":
        entry, tail = entry_D3, ["N8","N5","N4","B3","N2","P2"]
    elif d2 == "NO" and d3 == "ONE" and d5 == "CAN":
        entry, tail = entry_D3, (tail_p6_D5 if treasure == 6 else ["N3","N4","B3","N2","P2"])
    elif d2 == "NO" and d3 == "ONE" and d5 == "NO":
        entry, tail = entry_D3, ["N8","N3","N4","B3","N2","P2"]
    elif d2 == "NO" and d3 == "NO" and d4 == "CAN":
        entry, tail = entry_far, ["N8","N3","N4","B3","N2","P2"]
    elif d2 == "NO" and d3 == "NO" and d4 == "ONE":
        entry, tail = entry_far, (tail_p6_D5 if treasure == 6 else ["N3","N4","B3","N2","P2"])
    else:
        print("  💥 门状态组合无匹配分支 → CarBrake_Stop"); return

    full = pre + entry + use_tour + tail
    # build_round2_route 从 0 写
    load_route_at(s, 0, idxlist(full + [0xFF]))
    s.routetime = 2

    # 行驶：每次到达当前边终点就 advance；检查是否到 P2 且路线结束
    visited = []
    for k in range(120):
        if s.nowNode[1] == IDX["P2"] and s.route[s.point - 1] == 0xFF:
            break
        if not advance(s, f"二轮 step{k}"):
            return
        if s.routetime > 2:
            break
    else:
        print(f"  ⚠️ 步数超限, 最后节点 {NAMES[s.nowNode[1]]}, routetime={s.routetime}")
        return
    if s.routetime == 3:
        print(f"  ✅ 二轮跑完：到达 P2 后 routetime=3，小车停在终点（共推进 {k+1} 次）")
    elif s.nowNode[1] == IDX["P2"]:
        print(f"  ✅ 到达 P2（routetime={s.routetime}），等待下一轮推进触发结束")
    else:
        print(f"  ⚠️ 异常结束: {NAMES[s.nowNode[1]]}, routetime={s.routetime}")

sim_round2("D2双向,CAN,宝物=5", ("CAN","NO","NO","NO"), 5)
sim_round2("D2双向,CAN,宝物=6", ("CAN","NO","NO","NO"), 6)
sim_round2("D2单进,D5回,宝物=5", ("ONE","NO","NO","CAN"), 5)
sim_round2("D3双向,宝物=5", ("NO","CAN","NO","NO"), 5)
sim_round2("D3单进,D4回,宝物=6", ("NO","ONE","NO","NO"), 6)
sim_round2("最外进,D4回,宝物=5", ("NO","NO","CAN","NO"), 5)
sim_round2("最外进,D5回,宝物=6", ("NO","NO","ONE","NO"), 6)

# ==================== 一轮 P7/P8 宝物回家验证 ====================
run_scenario("一轮A=5,B=7,D2绿,宝物=5", 5, 7, "D2", ["N22","B7","C6","N19","B5","N18","N16","N12","N13","P5","N13","N12","N5","N4","B3","N2","P2",0xFF])
run_scenario("一轮A=5,B=8,D2绿,宝物=5", 5, 8, "D2", ["C4","B11","C8","C7","B10","N14","C3","N9","N10","N11","N12","N13","P5","N13","N12","N5","N4","B3","N2","P2",0xFF])
run_scenario("一轮A=6,B=7,D2绿,宝物=6", 6, 7, "D2", ["N22","B6","N20","C4","B11","C8","C7","B10","N14","C3","N9","B9","N7","P6","N7","B8","N9","N10","N11","N12","N5","N4","B3","N2","P2",0xFF])
run_scenario("一轮A=5,B=7,D3绿,宝物=5", 5, 7, "D3", ["N22","B7","C6","N19","B5","N18","N16","N12","N13","P5","N13","N12","N8","N5","N4","B3","N2","P2",0xFF])
run_scenario("一轮A=6,B=8,D2绿,宝物=6", 6, 8, "D2", ["B6","N22","B7","C6","N19","B5","N18","N16","N12","N13","P5","N13","N12","N11","N10","N3","N4","B3","N2","P2",0xFF])
