"""sim_route_bookkeeping.py — 状态机仿真：复刻固件的 route[]/map.point/nodes 推进，定位 Route_Error_Stop

背景
----
现场现象：第一轮回程经过 N14（`B10→N14`，func=View）做完直立动作后**静默停住**（无播报）。
三个"卡死停车"里有两个会播报（丢线保护 30 / 横滚 31），`Route_Error_Stop()`（map.c:187）虽写了
播报 33，但语音表只排到 29 —— 30/31/33 很可能根本没录音 ⇒ "没播报"排除不掉它。

`Route_Error_Stop` 只有一个触发源：`getNextConnectNode(nownode, nextnode)` 查不到边。
而边表本身我已全量验证过（108 条边全能被 CSR 解析、节点编号都 < 54）⇒ 只可能是**运行时
`route[]`/`map.point`/`nodes.nextNode` 错位**，把错的节点号喂了进去。

本脚本就是把固件那套记账**逐条搬过来**跑一遍，在每一步校验不变量：

    route[map.point - 1] == nodes.nextNode.nodenum   （或 == 0xFF：这条路已到头）

一旦哪一步破了不变量，后面迟早会把错的节点号喂给 `getNextConnectNode` → 死停。
脚本会打印**第一次破不变量的位置 + 上下文**，并指出还能撑几跳才炸。

镜像的固件函数（逐条对照源码）
------------------------------
  map.c          : mapInit() / Navigation() 的推进 / Nav_TurnAndAdvance() / Nav_PostProcess()
  nav_planner.c  : nav_build_route() / nav_plan_waypoints()（复用 _weight_calib）/ nav_set_edge_blocked()
  mission_planner: update_route_at_P1() / update_route_at_door_for_stageAB() /
                   plan_treasure_return() / route_return_home() / get_newroute()
  barrier.c      : door() 的 D2 / D5_BACK / D4_BACK 三个分支（只镜像会改 route/nowNode 的部分）

只读脚本：不改任何固件文件、不写 route[] 之外的任何东西。用法：
    python3 scripts/analyze/sim_route_bookkeeping.py
"""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, "..", "validate"))
import _weight_calib as W                                          # noqa: E402

# ⚠️ _weight_calib 顶部的场地常量默认 FIELD_COMP，必须按 Mission/config.h 的真实场次覆盖
# （README 特别警告过：不同场地 LEN_*/DOOR_LEN_* 不同，N3→P4 的选路结论会相反）
W.sync_field_from_config()

F_DOOR = W.FUNC["DOOR"]
F_UPSTAGE = W.FUNC["UpStage"]
F_BSOUTPOLE = W.FUNC["BSoutPole"]
F_BHM = W.FUNC["BHM"]

ROUTE_LEN = 100
SENT = 0xFF
IDX = W.NODE_IDX
NAME = {v: k for k, v in IDX.items()}
EDGES = W.parse_graph()
ADJ = W.build_adj(EDGES)

# ---- 固件权重（nav_planner.c：长度 1.0、转角 NAV_W_TURN=0.6、障碍 1.0）----
W_LEN, W_TURN, W_OBS = 1.0, 0.6, 1.0

# ---- door() 用到的通行语义（barrier.h）----
CAN_PASS, NO_PASS, ONE_WAY_PASS = 2, 1, 3
DOOR_ZONE = [("N5", "N12"), ("N12", "N5"), ("N5", "N8"), ("N8", "N5"),
             ("N3", "N8"), ("N8", "N3"), ("N3", "N10"), ("N10", "N3")]


def can_pass(s):
    return s in (CAN_PASS, ONE_WAY_PASS)


class RouteError(Exception):
    """镜像 Route_Error_Stop：getNextConnectNode 查不到边"""


class Sim:
    def __init__(self, clue=3, stage_a=5, stage_b=7, door_true=None, treasure=0):
        # 固件 map.c: u8 route[100] = {B1,N1,P1,N1,B2,N4,N5,0XFF}; 其余为 0（= S1）
        self.route = [0] * ROUTE_LEN
        for i, nm in enumerate(["B1", "N1", "P1", "N1", "B2", "N4", "N5"]):
            self.route[i] = IDX[nm]
        self.route[7] = SENT
        self.point = 0
        self.last = self.now = self.nxt = None
        self.blocked = set()
        self.clue = clue
        self.stage_a, self.stage_b = stage_a, stage_b
        # 两套门状态（关键）：
        #   door_true = 物理灯色（固件 DEBUG=1 时 = barrier.c:74 的 debug_door_pass）
        #   door_pass = **车已经读到的**（barrier.c:72 初值全 0；只在走过对应读灯边时才被填）
        self.door_true = list(door_true or [ONE_WAY_PASS, CAN_PASS, CAN_PASS, NO_PASS, NO_PASS])
        self.door_pass = [0, 0, 0, 0, 0]
        self.treasure = treasure
        self.routetime = 0
        self.door_event = False
        self.finished = False
        # 镜像 Node[].function 的可变部分：door_set_pass_node() 会把该边 function 改成 NONE
        self.func_override = {}
        self.trace = []            # (跳数, now边, map.point, route[point-1], nextNode目标)
        self.violations = []
        self.steps = 0

    # ---------------------------------------------------------------- 基础镜像
    def edge(self, a, b):
        """返回一条边（a/b 可为节点名或编号）"""
        ai = a if isinstance(a, int) else IDX[a]
        bi = b if isinstance(b, int) else IDX[b]
        for e in EDGES:
            if e["from"] == ai and e["to"] == bi:
                return e
        return None

    def eff_func(self, e):
        """边的当前 function：镜像 Node[].function（door_set_pass_node 会把它改成 NONE）"""
        return self.func_override.get((e["from"], e["to"]), e["func"])

    def get_next(self, from_idx, to_idx):
        """镜像 getNextConnectNode：查不到边就 Route_Error_Stop"""
        if from_idx >= 54:
            raise RouteError("节点编号越界 %d -> %d" % (from_idx, to_idx))
        for e in EDGES:                       # CSR 只是索引重排，语义 == 遍历出边
            if e["from"] == from_idx and e["to"] == to_idx:
                return e
        raise RouteError("无边 %s -> %s(%d -> %d)"
                         % (NAME.get(from_idx, from_idx), NAME.get(to_idx, to_idx),
                            from_idx, to_idx))

    def plan_seq(self, wp_names):
        """镜像 nav_plan_waypoints（含被禁边），返回 [wp0, hop, ..., last, None(哨兵)]"""
        edges = [e for e in EDGES if (NAME[e["from"]], NAME[e["to"]]) not in self.blocked]
        adj = W.build_adj(edges)
        seq = W.plan_via_waypoints(edges, adj, wp_names, W_LEN, W_TURN, W_OBS)
        if seq is None:
            raise RouteError("规划失败（被禁边后不可达）：%s" % wp_names)
        return list(seq) + [None]             # None = 0xFF 哨兵

    def build_route_at(self, offset, wp_names):
        """镜像 nav_build_route(&route[offset], ...)：跳过起点，含 0xFF 哨兵"""
        if offset >= ROUTE_LEN:
            raise RouteError("offset 越界 %d" % offset)
        seq = self.plan_seq(wp_names)
        n = 0
        for node in seq[1:]:                  # 跳过起点
            self.route[offset + n] = SENT if node is None else IDX[node]
            n += 1
        return n

    def load_route_at(self, offset, arr):
        """镜像 load_route_at（手写数组，遇 0xFF 停）"""
        for i, x in enumerate(arr):
            self.route[offset + i] = SENT if x is None else IDX[x]
            if x is None:
                break

    # ---------------------------------------------------------------- 不变量校验
    def check(self, tag):
        expect = SENT if self.nxt is None else self.nxt["to"]
        got = self.route[self.point - 1]
        ok = (got == expect)
        self.trace.append((self.steps, "%s->%s" % (NAME[self.now["from"]], NAME[self.now["to"]]),
                           self.point, NAME.get(got, got), NAME.get(expect, expect), ok))
        if not ok and len(self.violations) < 3:
            self.violations.append((tag, self.steps, self.point, got, expect))
        return ok

    # ---------------------------------------------------------------- map.c 镜像
    def map_init(self, first=False):
        """镜像 mapInit()：重规划 N2→P1→N5，nowNode=P2→N2，nextNode= 按 route[point] 取"""
        self.blocked = set()
        self.build_route_at(0, ["N2", "P1", "N5"])
        self.point = 0
        self.last = None
        self.now = self.edge("P2", "N2")
        if self.route[self.point] != SENT:
            self.nxt = self.get_next(self.now["to"], self.route[self.point])
        self.point += 1
        if first:
            self.check("mapInit")

    def turn_and_advance(self):
        """镜像 Nav_TurnAndAdvance()"""
        if self.route[self.point - 1] != SENT:
            self.last = self.now
            self.now = self.nxt
            if self.route[self.point] != SENT:
                self.nxt = self.get_next(self.now["to"], self.route[self.point])
            else:
                self.nxt = None               # 固件里是"留着旧值"，但下一拍必进 route 结束分支
            self.point += 1
        else:
            self.finished = True              # CarBrake(); map.routetime++
            self.routetime += 1

    def post_process(self):
        """镜像 Nav_PostProcess()：door() 已改写 route[]/nowNode，这里补 nextNode + point++"""
        if self.route[self.point] != SENT:
            self.nxt = self.get_next(self.now["to"], self.route[self.point])
        else:
            self.nxt = None
        self.point += 1

    # ---------------------------------------------------------------- mission_planner 镜像
    def update_route_at_P1(self):
        if self.clue == 3:
            self.load_route_at(0, ["B1", "N1", "P1", "N1", "B2", "N4", "N3", "P3",
                                   "N3", "N4", "N5", "N12", None])
        elif self.clue == 4:
            self.load_route_at(0, ["B1", "N1", "P1", "N1", "B2", "N4", "N5", "N6",
                                   "P4", "N6", "N5", "N12", None])
        elif self.clue == 0:
            self.load_route_at(0, ["B1", "N1", "P1", "N1", "B2", "N4", "N5", "N12", None])

    def update_route_at_door_for_stageAB(self):
        self.build_route_at(0, [NAME[self.now["to"]], "P%d" % self.stage_a, "P%d" % self.stage_b])

    def plan_treasure_return(self, start):
        wp = [start]
        if self.treasure == 5:
            wp.append("P5")
        elif self.treasure == 6:
            wp.append("P6")
        d2, d3, d4 = self.door_pass[0], self.door_pass[1], self.door_pass[2]
        if d2 == CAN_PASS:
            wp += ["N12", "N5"]
        elif d3 == CAN_PASS:
            wp += ["N8", "N5"]
        elif d4 == CAN_PASS:
            wp += ["N8", "N3"]
        elif ONE_WAY_PASS in (d2, d3, d4):
            wp += ["N10", "N3"]
        else:
            raise RouteError("D2/D3/D4 都不能过 → 固件 CarBrake_Stop")
        if self.treasure not in (5, 6):
            wp.append({2: "P1", 3: "P3", 4: "P4"}[self.treasure])
        wp.append("P2")
        # ★ 关键：写 offset = map.point - 1，且不碰 map.point
        self.build_route_at(self.point - 1, wp)
        first = self.route[self.point - 1]
        if first != SENT:
            self.nxt = self.get_next(self.now["to"], first)
        return wp

    def route_return_home(self, allow_N8_N3=False):
        for a, b in DOOR_ZONE:
            self.blocked.add((a, b))
        if allow_N8_N3:
            self.blocked.discard(("N8", "N3"))
        wp = [NAME[self.now["to"]]]
        if self.treasure == 2:
            wp.append("P1")
        elif self.treasure == 3:
            wp.append("P3")
        elif self.treasure == 4:
            wp.append("P4")
        wp.append("P2")
        self.build_route_at(0, wp)            # ★ offset = 0
        return wp

    def get_newroute(self):
        """镜像 get_newroute()（USE_PLANNER_ROUTE=1）：二轮固定 P1/P3/P4 → 进门 → 巡游 → 回程

        ⚠️ 门梯用的是 **door_pass（车已经读到的）**，不是物理灯色；未读 = 0 会让分支落空。"""
        self.map_init()                                    # get_newroute 内部先调 mapInit()
        self.blocked = set()                               # Clear_door(): nav_clear_blocked()
        for a, b in DOOR_ZONE:                             # Clear_door(): 8 条门边 function=NONE
            self.func_override[(IDX[a], IDX[b])] = W.FUNC["NONE"]
        # upright_Set() 只改 function，不动 route

        wp = ["N2", "P1", "P3", "P4", "N5"]
        if can_pass(self.door_pass[0]):
            wp.append("N12")
        elif can_pass(self.door_pass[1]):
            wp.append("N8")
        elif can_pass(self.door_pass[2]):
            wp.append("N3")
            if self.treasure == 6:
                wp.append("N8")
        else:
            raise RouteError("二轮进门：D2/D3/D4 都不可过 → CarBrake_Stop")

        wp += (["P6", "P8", "P7", "P5"] if self.treasure == 6
               else ["P5", "P7", "P8", "P6"])

        d0, d1, d2, d3 = self.door_pass[0], self.door_pass[1], self.door_pass[2], self.door_pass[3]
        if d0 == CAN_PASS:
            wp.append("N5")
        elif d0 == ONE_WAY_PASS and d3 == CAN_PASS:
            wp.append("N10")
        elif d0 == ONE_WAY_PASS and d3 == NO_PASS and d2 == CAN_PASS:
            wp.append("N8")
        elif d0 == ONE_WAY_PASS and d3 == NO_PASS and d2 == NO_PASS:
            wp += ["N8", "N5"]
        elif d0 == NO_PASS and d1 == CAN_PASS:
            wp += ["N8", "N5"]
        elif d0 == NO_PASS and d1 == ONE_WAY_PASS and d3 == CAN_PASS:
            wp.append("N10")
        elif d0 == NO_PASS and d1 == ONE_WAY_PASS and d3 == NO_PASS:
            wp.append("N8")
        elif d0 == NO_PASS and d1 == NO_PASS and d2 == CAN_PASS:
            wp.append("N8")
        elif d0 == NO_PASS and d1 == NO_PASS and d2 == ONE_WAY_PASS:
            wp.append("N10")
        else:
            raise RouteError("二轮回程：门状态组合无匹配分支 → CarBrake_Stop")
        wp.append("P2")
        self.build_route_at(0, wp)
        self.routetime = 2
        self.finished = False
        return wp

    # ---------------------------------------------------------------- barrier.c 镜像（只留门）
    def door(self, state):
        """镜像 door()：只保留会改 route[]/nowNode 的分支。

        ⚠️ 读灯语义：颜色来自 door_true（物理），但只有在**走过这条读灯边**时才写进 door_pass
        —— 车不知道它没读过的门（door_pass 未读 = 0 ≠ 黑灯）。"""
        self.point = 0
        self.route[0] = SENT
        if state == "D2":                                   # 读灯边 N5→N12
            self.door_pass[0] = self.door_true[0]
            if not can_pass(self.door_pass[0]):
                raise RouteError("D2 黑 → 应退回重读 D3（本次场景不涉及）")
            self.now = self.edge("N5", "N12")               # door_set_pass_node(N5,N12)
            self.func_override[(IDX["N5"], IDX["N12"])] = W.FUNC["NONE"]
            self.update_route_at_door_for_stageAB()
            self.door_event = True
        elif state == "D5_BACK":                            # 读灯边 N10→N3
            self.door_pass[3] = self.door_true[3]
            if self.door_pass[3] == CAN_PASS:               # update_route_by_door_1()
                self.now = self.edge("N10", "N3")
                self.func_override[(IDX["N10"], IDX["N3"])] = W.FUNC["NONE"]
                self.route_return_home(False)
            elif self.door_pass[0] == ONE_WAY_PASS:         # 蓝灯已用尽 → 退回 N8 重读 D4
                self.route[0] = IDX["N3"]
                self.route[1] = SENT
                self.now = self.edge("N10", "N8")           # door_retreat(N10,N8)
            elif self.door_pass[0] == NO_PASS and self.door_pass[1] == ONE_WAY_PASS:
                self.now = self.edge("N10", "N8")           # update_route_by_door_2()
                self.route_return_home(True)
            else:
                raise RouteError("D5 非绿且 D2/D3 组合无匹配分支")
            self.door_event = True
        elif state == "D4_BACK":                            # 读灯边 N8→N3
            self.door_pass[2] = self.door_true[2]
            if self.door_pass[2] == CAN_PASS:               # update_route_by_door_3()
                self.now = self.edge("N8", "N3")
                self.func_override[(IDX["N8"], IDX["N3"])] = W.FUNC["NONE"]
                self.route_return_home(False)
            else:                                           # update_route_by_door_4()
                self.now = self.edge("N8", "N5")
                self.route_return_home(False)
            self.door_event = True

    # ---------------------------------------------------------------- 跑
    def run_edge(self):
        """走一条边：先跑 func 钩子（NEAR_END），再到点推进"""
        self.steps += 1
        frm, to = NAME[self.now["from"]], NAME[self.now["to"]]
        func = self.eff_func(self.now)
        state = None
        if func == F_DOOR:
            if (frm, to) == ("N5", "N12"):
                state = "D2"
            elif (frm, to) == ("N10", "N3"):
                state = "D5_BACK"
            elif (frm, to) == ("N8", "N3"):
                state = "D4_BACK"
            else:
                raise RouteError("门边 %s->%s 无匹配状态" % (frm, to))
        elif to == "P1" and func == F_UPSTAGE:
            self.route_rewrite_hook = "P1"
        elif to == "P7" and func == F_BSOUTPOLE:
            self.route_rewrite_hook = "P7"
        elif to == "P8" and func == F_BHM:
            self.route_rewrite_hook = "P8"

        if state is not None:
            self.door(state)
            self.post_process()
        else:
            hook = getattr(self, "route_rewrite_hook", None)
            self.route_rewrite_hook = None
            if hook == "P1":
                # Stage() 里 WaitFor_QR 那段有 `treasure == 0` 前置：第二次到 P1（宝物平台）时
                # 宝物已定，不会再改路线（改了就会把回程路线冲掉、绕回原点）
                if self.treasure == 0:
                    self.update_route_at_P1()
            elif hook == "P7":
                if self.routetime == 0 and self.stage_b == 7:
                    self.treasure = self.treasure or 2      # treasure=clue_A+clue_B=2
                    self.plan_treasure_return("P7")
            elif hook == "P8":
                if self.routetime == 0 and self.stage_b == 8:
                    self.treasure = self.treasure or 2
                    self.plan_treasure_return("P8")
            self.turn_and_advance()
        self.check("after %s->%s" % (frm, to))

    def run(self, limit=200, verbose=False):
        guard = 0
        while not self.finished and guard < limit:
            guard += 1
            self.run_edge()
            if verbose:
                print("   %s" % self._line())
        return self.finished

    def _line(self):
        s, e, p, got, exp, ok = self.trace[-1]
        return "%-3d %-9s point=%-3d route[point-1]=%-5s nextNode=%-5s %s" % (
            s, e, p, got, exp, "" if ok else "★不变量破!")


def run_case(title, clue, stage_a, stage_b, door_true, treasure):
    print("=" * 78)
    print("%s   （线索=%s 平台=%s/%s 物理灯色 D2..D5=%s 宝物=%s）"
          % (title, clue, stage_a, stage_b, door_true, treasure))
    sim = Sim(clue=clue, stage_a=stage_a, stage_b=stage_b, door_true=door_true, treasure=treasure)
    rnd = "第一轮"
    try:
        sim.map_init()
        done = sim.run()
        print("  [%s] %d 跳，%s（routetime=%d，车读到的门=%s）"
              % (rnd, sim.steps, "路线走完" if done else "★ 到上限还没走完",
                 sim.routetime, sim.door_pass))
        if done and sim.routetime == 1:
            rnd = "第二轮"
            base = sim.steps
            wp2 = sim.get_newroute()
            print("  [%s] wp: %s" % (rnd, " ".join(wp2)))
            done2 = sim.run(limit=300)
            print("  [%s] %d 跳，%s（routetime=%d）"
                  % (rnd, sim.steps - base, "路线走完" if done2 else "★ 到上限还没走完",
                     sim.routetime))
    except RouteError as ex:
        print("  ★★ [%s] Route_Error_Stop 复现：%s" % (rnd, ex))
        print("     停在：%s" % (sim._line() if sim.trace else "(还没开始)"))
    print("  不变量破坏次数：%d" % len(sim.violations))
    for tag, step, point, got, exp in sim.violations:
        print("     - 第 %d 跳（%s）：map.point=%d route[point-1]=%s 应为 %s"
              % (step, tag, point, NAME.get(got, got), NAME.get(exp, exp)))
    print()


if __name__ == "__main__":
    # 现场配置：DEBUG 预设门色 D2蓝 D3绿 D4绿 D5黑；QR/clue 预设 3/5/7；
    # treasure 初值为 0（固件 barrier.c:94），到 P7/P8 平台才由 clue_A+clue_B 算出 = 2 → 宝物在 P1
    run_case("第一轮（真实预设）", 3, 5, 7,
             [ONE_WAY_PASS, CAN_PASS, CAN_PASS, NO_PASS, NO_PASS], 0)
