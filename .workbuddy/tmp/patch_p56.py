# -*- coding: utf-8 -*-
"""P56_EXTRA_STOP_ENABLE 补丁：固件 2 处 + sim 镜像 + map_model 镜像。
字节级替换；probe eol；assert 每个 old 串恰好命中 1 次；全部成功才写盘。"""
import pathlib

BASE = pathlib.Path(r"C:/Users/14166/Desktop/MC_32/robotcup/xunbao")

FILES = {
    "config": BASE / "Mission/config.h",
    "mp":     BASE / "Mission/mission_planner.c",
    "sim":    BASE / "地图修改上位机/tools/sim_route_bookkeeping.py",
    "mm":     BASE / "地图修改上位机/map_editor/map_model.py",
}

def probe(path):
    b = path.read_bytes()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n") - crlf
    assert (crlf == 0) or (lf == 0), "%s 混合行尾?" % path
    return "\r\n" if crlf >= lf else "\n"

EDITS = {}   # name -> list of (old, new) in plain \n, converted later

# ---------- 1) Mission/config.h（LF+BOM）：TB_GO_HOME_AT_S 后插入新宏块 ----------
EDITS["config"] = [(
r"""#define TB_GO_HOME_AT_S        165   /* 2:45 起（剩 15s）强制回家 */
""",
r"""#define TB_GO_HOME_AT_S        165   /* 2:45 起（剩 15s）强制回家 */

/* ===================== 一轮宝物=P5/P6 顺路补走 7/8 中未走的平台（2026-10-18，预编译开关） =====================
 * 1 = 一轮宝藏平台在 P5/P6（门东侧）且时间充足时，取完宝先绕去 P7/P8 中【尚未走过的】那个平台
 *     打卡，再过门回家；过门后尾段照旧（补打卡 P3/P4 + S1/S2 的贪分不受影响 —— 两处贪分互不
 *     冲突，本功能在门前先执行、优先级更高）。落点：mission_planner.c plan_treasure_return()。
 *     时间判据在【规划时刻】（P7/P8 读完 OCR 那一刻）查：已用时 + TB_P56_EXTRA_MIN_REMAIN_S
 *     ≤ 180（即剩余 ≥ 阈值）。规划时刻比"拿完宝藏"早约 10~20s（P7/P8→宝物平台赶路 + 取宝
 *     动作），阈值 85 ≈ "拿完宝后剩 70s" + 提前量。开关为 1 时比赛计时器恒启动（本功能要用）。
 * 0 = 新增段不参与编译，与加这段之前一字不差（默认）。
 * ⚠️ 用户指定预编译开关（#if 门控）：宏名写错会静默当 0 = 功能关（方向安全）；上场前在编译
 *    日志确认 mission_planner.c 正常编译。镜像：sim_route_bookkeeping.py 读同一宏；
 *    map_model.treasure_return_waypoints(p56_extra=) 参数已备、UI 接线待做。 */
#define P56_EXTRA_STOP_ENABLE        0
#define TB_P56_EXTRA_MIN_REMAIN_S    85   /* 规划时刻要求的剩余秒数（≈拿完宝后剩 70s + 提前量） */
""")]

# ---------- 2) Mission/mission_planner.c（CRLF）----------
EDITS["mp"] = [
    # 2a) Match_Timer_Start：开关开时恒启动计时器
    (r"""	/* 两个功能（分级贪分 / 硬截止回家）任一需要计时就启动；都为 0 时与加"硬截止"之前一字不差 */
	if (!TIME_BUDGET_ENABLE && !TB_FORCE_HOME_ENABLE) return;
""",
     r"""#if P56_EXTRA_STOP_ENABLE
	/* P56 补走平台要用计时器（规划时刻的剩余时间判据）⇒ 开关开时恒启动 */
#else
	/* 两个功能（分级贪分 / 硬截止回家）任一需要计时就启动；都为 0 时与加"硬截止"之前一字不差 */
	if (!TIME_BUDGET_ENABLE && !TB_FORCE_HOME_ENABLE) return;
#endif
"""),
    # 2b) wp 容量 10 -> 12
    (r"""	u8 wp[10];   /* 补打卡 + 巡回交错后最多 9 个点（start + P5/P6 + 门×2 + 宝物平台 + P3 + S1 + P4 + S2 + P2），10 够 */""",
     r"""	u8 wp[12];   /* 补打卡 + 巡回交错后最多 9 个点（start + P5/P6 + 门×2 + 宝物平台 + P3 + S1 + P4 + S2 + P2）；P56_EXTRA_STOP_ENABLE=1 时再 +1（补走 7/8），留到 12 */"""),
    # 2c) 宝物=P5/P6 平台之后、门节点之前插入补走段（#if 门控）
    (r"""	else if (treasure == 6)
	{
		wp[n++] = P6;
	}
""",
     r"""	else if (treasure == 6)
	{
		wp[n++] = P6;
	}

#if P56_EXTRA_STOP_ENABLE
	/* ★ 宝物在 P5/P6（门东侧）且时间充足：取完宝先绕去 P7/P8 中【尚未走过的】那个
	 *   （start = 一轮去程当过线索平台的那个），再过门回家。必须在门节点【之前】插：
	 *   两个平台都在门东侧，过门后再去 = 走错即结束比赛。过门后尾段贪分照常
	 *   （append_round1_return_tail / round1_exit_recheck 不受影响）—— 两处贪分互不冲突，
	 *   本功能在门前先执行、优先级更高。时间在【规划时刻】查（比"拿完宝藏"早 10~20s，
	 *   阈值已含提前量，见 config.h）；写成加法防无符号下溢。match_start_tick != 0
	 *   = 计时器确实在跑（调试路径没启动就不决策）。
	 *   ⚠️ 回程撞补走平台不会重规划：barrier.c 的 HM/SP 分支有 flag_clue_stage_B==8/7
	 *   门控，补走的正是没当过线索的那个，条件不成立。 */
	if ((treasure == 5 || treasure == 6) && match_start_tick != 0
		&& (Match_Elapsed_S() + TB_P56_EXTRA_MIN_REMAIN_S) <= 180u)
	{
		wp[n++] = (start == P7) ? P8 : P7;   /* 7/8 中尚未走过的那个 */
	}
#endif
"""),
]

# ---------- 3) sim_route_bookkeeping.py（LF）：读宏 + Sim.plan_treasure_return 镜像 ----------
EDITS["sim"] = [
    (r"""_R2_S1_RAW = read_config_flag("ROUND2_S1_ENABLE")
R2_S1 = 1 if _R2_S1_RAW is None else _R2_S1_RAW    # 二轮 S1 单独开关（缺宏按开）
""",
     r"""_R2_S1_RAW = read_config_flag("ROUND2_S1_ENABLE")
R2_S1 = 1 if _R2_S1_RAW is None else _R2_S1_RAW    # 二轮 S1 单独开关（缺宏按开）
_P56_RAW = read_config_flag("P56_EXTRA_STOP_ENABLE")
P56_EXTRA = 0 if _P56_RAW is None else _P56_RAW    # 一轮宝物=P5/P6 补走 7/8 中未走平台（镜像固件 #if 段）
"""),
    (r"""        if self.treasure == 5:
            wp.append("P5")
        elif self.treasure == 6:
            wp.append("P6")
        d2, d3, d4 = self.door_pass[0], self.door_pass[1], self.door_pass[2]
""",
     r"""        if self.treasure == 5:
            wp.append("P5")
        elif self.treasure == 6:
            wp.append("P6")
        # ★ 镜像 plan_treasure_return() 的 P56_EXTRA_STOP_ENABLE 段（固件 #if 预编译开关）：
        #   宝物=P5/P6 → 补走 P7/P8 中尚未走过的那个（start = 一轮当过线索平台的那个）。
        #   时间判据（已用时 + TB_P56_EXTRA_MIN_REMAIN_S ≤ 180）在 sim 不建模（无比赛计时器），
        #   开关开 = 恒插点，只验走法/记账是否被这 1 个点撑爆。
        if P56_EXTRA and self.treasure in (5, 6):
            wp.append("P8" if start == "P7" else "P7")
        d2, d3, d4 = self.door_pass[0], self.door_pass[1], self.door_pass[2]
"""),
]

# ---------- 4) map_model.py（CRLF）：treasure_return_waypoints 加 p56_extra 参数 ----------
EDITS["mm"] = [
    (r"""def treasure_return_waypoints(start, doors, treasure, line_clue=None, punch=False,
                              tour=False, elapsed_s=None):""",
     r"""def treasure_return_waypoints(start, doors, treasure, line_clue=None, punch=False,
                              tour=False, elapsed_s=None, p56_extra=False):"""),
    (r"""    punch=True ⇒ 按 `P3P4_PUNCH_ENABLE` 追加"补打卡"平台；
    tour=True ⇒ 按 `UPRIGHT_TOUR_ENABLE` 追加 S1/S2。
""",
     r"""    punch=True ⇒ 按 `P3P4_PUNCH_ENABLE` 追加"补打卡"平台；
    tour=True ⇒ 按 `UPRIGHT_TOUR_ENABLE` 追加 S1/S2。
    p56_extra=True ⇒ 按 `P56_EXTRA_STOP_ENABLE`（镜像固件 #if 段）在宝物平台之后、门节点之前
    补走 P7/P8 中尚未走过的那个（仅宝物=P5/P6；时间判据在固件里查，这里由调用方决定传不传）。
"""),
    (r"""    if treasure == 5:
        wp.append("P5")          # P5 是 N13 支路
    elif treasure == 6:
        wp.append("P6")          # P6 经 N7/N9 支路
    d2, d3, d4 = doors[0], doors[1], doors[2]
""",
     r"""    if treasure == 5:
        wp.append("P5")          # P5 是 N13 支路
    elif treasure == 6:
        wp.append("P6")          # P6 经 N7/N9 支路
    if p56_extra and treasure in (5, 6):
        wp.append("P8" if start == "P7" else "P7")   # 7/8 中尚未走过的那个
    d2, d3, d4 = doors[0], doors[1], doors[2]
"""),
]

# ---- 执行：全部断言通过才写盘 ----
results = {}
for name, path in FILES.items():
    eol = probe(path)
    data = path.read_bytes().decode("utf-8")
    for i, (old, new) in enumerate(EDITS[name]):
        o = old.replace("\n", eol)
        n = new.replace("\n", eol)
        cnt = data.count(o)
        assert cnt == 1, "%s edit#%d 命中 %d 次（应为 1）" % (name, i, cnt)
        data = data.replace(o, n)
    results[name] = (path, data)
    print("[OK] %s: %d 处替换断言通过 (eol=%r)" % (name, len(EDITS[name]), eol))

for name, (path, data) in results.items():
    path.write_bytes(data.encode("utf-8"))
    print("[WROTE]", path)
print("ALL DONE")
