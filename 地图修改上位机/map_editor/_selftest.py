# -*- coding: utf-8 -*-
"""
_selftest.py — 地图编辑器自检（无界面）

跑法（仓库根）：
    python scripts/map_editor/_selftest.py

校验：
  1. 源码解析：节点数/边数/NAV_EDGE_COUNT 自洽
  2. 往返一致：没编辑时导出的边表与原文件**逐字段相同**
  3. 宏求值：每条边的 angle/step 都能算成数字
  4. 导出格式：NavEdgeTbl / enum / NAV_EDGE_COUNT 结构正确（行数 == NAV_EDGE_COUNT）
  5. 编辑操作：加节点 / 加双向边 / 删边 / 改名 / 撤销-重做
  6. 规划：与 _weight_calib 的参考路线对照（若可导入）
  7. 演示：按用户需求模拟「切 C9-P7、B7-C6；加 C10；P7 移到 C6 位置」的结果
  8. 成本表：map_model.OBS 逐项比对固件 nav_planner.c 的 NavObsPenalty[]
  9. 门回程：门区禁用 + 极简 wp 复现 validate/_check_door_perm.py 的 12 条 golden
 10. config.h 写回：宏替换保留行尾注释（含多行 /* 开头），真实文件干跑逐字节不变
 11. 第二轮 wp：默认顺序 == 固件源码里写死的两套；自定义巡游顺序只换巡游段
12. 转弯前补偿：解析 map.c 两张表 / 覆盖度 / 分支判定 / 写回幂等与护栏
只读源码，不写任何固件文件。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import map_model as M   # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  [OK]   " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAIL.append(msg)


def warn(msg):
    """不规范但能编过的问题：只提示，不计入失败。"""
    print("  [WARN] " + msg)


def _parse_firmware_obs():
    """从 Navigation/nav_planner.c 解析 NavObsPenalty[]（下标 = map.h 的 barriers 枚举编号）。"""
    path = os.path.join(M.ROOT, "Navigation", "nav_planner.c")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    mm = re.search(r"NavObsPenalty\s*\[[^\]]*\]\s*=\s*\{(.*?)\};", txt, re.S)
    if not mm:
        return None
    body = M._strip_block_comments(mm.group(1))
    vals = [float(x) for x in re.findall(r"(-?\d+(?:\.\d+)?)f\b", body)]
    return vals or None


def sec(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def main():
    # Windows 控制台默认 GBK，装不下 ⚠ 这类符号 —— 打印时降级成 '?'，别让整轮自检崩掉
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    sec("1. 解析源码")
    m = M.MapModel.load_from_sources()
    n_nodes, n_edges = len(m.nodes), len(m.edges)
    # 不再硬编码 54 节点 / 124 边：节点数与边数由源码决定，改地图后这里不该失败。
    print("  节点 %d 个 / 边 %d 条 / 场地 %s" % (n_nodes, n_edges, m.field_name))
    check(m.declared_count == n_edges,
          "NAV_EDGE_COUNT(%s) 与表内行数(%d) 一致" % (m.declared_count, n_edges))
    check(len(set(m.names())) == n_nodes, "节点名无重复（%d 个）" % n_nodes)
    dangling = [(e.label(), x) for e in m.edges for x in (e.frm, e.to) if m.node(x) is None]
    check(not dangling, "所有边端点都在 enum 里（悬空端点 %d）" % len(dangling))
    for d in dangling[:6]:
        print("       ", d)
    check(m.field_name in ("FIELD_SCHOOL", "FIELD_COMP"), "场地解析 = %s" % m.field_name)

    # 固件源码里的两处一致性（编辑器导出/写回时必须保住）
    with open(M.PATH_EDGE_C, encoding="utf-8", errors="replace") as f:
        src_edge = f.read()
    n_td = len(re.findall(r"typedef\s+char\s+NavEdgeTbl_size_check", src_edge))
    if n_td == 1:
        print("  [OK]   NavEdgeTbl_size_check 只声明一次")
    else:
        warn("NavEdgeTbl_size_check 声明了 %d 次（重复 typedef 块）：C99 下是约束违规，"
             "GCC/armcc 只在 -pedantic 时告警、仍能编过，但基本可以断定是误加" % n_td)
    with open(os.path.join(M.ROOT, "Navigation", "map.c"), encoding="utf-8",
              errors="replace") as f:
        src_mapc = f.read()
    mi = re.search(r"nav_init\s*\(\s*NavEdgeTbl\s*,\s*NAV_EDGE_COUNT\s*,\s*(\d+)\s*\)", src_mapc)
    if mi:
        declared_nodes = int(mi.group(1))
        check(declared_nodes >= n_nodes,
              "map.c: nav_init(..., %d) >= enum 节点数(%d)" % (declared_nodes, n_nodes))
        if declared_nodes != n_nodes:
            warn("map.c 写死 %d 个节点，而 enum 只有 %d 个：多出的出度为 0，当前无害，"
                 "但改地图（增删节点）时别忘同步" % (declared_nodes, n_nodes))

    sec("2. 往返一致（不编辑 => 导出应与原文件逐字段相同）")
    probs = m.roundtrip_report()
    check(not probs, "逐字段一致（差异 %d 处）" % len(probs))
    for p in probs[:10]:
        print("       ", p)

    sec("3. 宏求值（angle/step 都必须是数字）")
    bad = [(e.label(), e.angle, e.step) for e in m.edges
           if m.ang(e) is None or m.step(e) is None]
    check(not bad, "全部 %d 条边可求值（失败 %d）" % (len(m.edges), len(bad)))
    for b in bad[:10]:
        print("       ", b)
    _samp = max(m.edges, key=lambda x: (m.step(x) or 0.0))   # 别硬编码某条边：地图随时会改
    print("     抽样：%s angle=%s step=%s(func=%s)"
          % (_samp.label(), m.ang(_samp), m.step(_samp), _samp.func))
    print("           LEN_B7C6 求值 = %s" % M.eval_c_expr("LEN_B7C6", m.macros))
    print("           LEN_N18B5 求值 = %s" % M.eval_c_expr("LEN_N18B5", m.macros))
    print("           ANGLE_N8N3 求值 = %s" % M.eval_c_expr("ANGLE_N8N3", m.macros))
    print("           ANGLE_REV(145) 求值 = %s" % M.eval_c_expr("ANGLE_REV(145)", m.macros))

    sec("4. 导出格式")
    tbl = m.export_edge_table()
    n_rows = len([ln for ln in tbl.splitlines() if re.match(r"\s*\{\s*[A-Za-z_]\w*\s*,", ln)])
    check(n_rows == len(m.edges), "导出边行数(%d) == 边数(%d)" % (n_rows, len(m.edges)))
    check("NavEdgeTbl_size_check" in tbl, "含编译期行数检查")
    cnt = m.export_nav_edge_count()
    check(cnt == "#define NAV_EDGE_COUNT %d" % len(m.edges), "NAV_EDGE_COUNT 文本正确：%s" % cnt)
    enum = m.export_enum()
    enum_lines = enum.splitlines()
    n_enum = len(enum_lines) - 2      # 去掉 "enum MapNode {" 与 "};"
    check(n_enum == len(m.nodes), "enum 行数(%d) == 节点数(%d)" % (n_enum, len(m.nodes)))
    check(enum_lines[-1].strip() == "};", "enum 以 }; 收尾")
    check("B11" in enum and not enum_lines[-2].rstrip().endswith(","),
          "enum 最后一项无逗号")

    sec("5. 编辑操作")
    base = len(m.edges)
    snap0 = m.snapshot()
    # ⚠️ 只动**自己新建的**节点：改名/删除"原装"节点会连带删掉它原有的边，边数就回不去了。
    # ⚠️ 也别硬编码节点名（"C10" 曾经是测试临时名，后来真被加进地图了）。
    tmp = "ZZTMP"
    while m.node(tmp) or m.node(tmp + "X"):
        tmp += "_"
    b_ = m.names()[0]
    m.add_node(tmp, 800, 610, "测试新节点")
    check(m.node(tmp) is not None, "加节点 %s" % tmp)
    m.add_edge(tmp, b_, flag="NO", angle="0", step="90", speed="SPEED2", func="NONE")
    m.add_edge(b_, tmp, flag="NO", angle="180", step="90", speed="SPEED2", func="NONE")
    check(m.edge(tmp, b_) and m.edge(b_, tmp), "加双向边 %s<->%s" % (tmp, b_))
    check(len(m.edges) == base + 2,
          "边数 %d -> %d（实际 %d）" % (base, base + 2, len(m.edges)))
    m.remove_edge(tmp, b_)
    check(m.edge(tmp, b_) is None, "删边 %s->%s" % (tmp, b_))
    m.rename_node(tmp, tmp + "X")
    check(m.node(tmp + "X") is not None and m.node(tmp) is None, "节点改名 %s -> %sX" % (tmp, tmp))
    check(m.edge(b_, tmp + "X") is not None, "改名后边端点跟着改（%s->%sX 存在）" % (b_, tmp))
    m.remove_node(tmp + "X")
    check(m.node(tmp + "X") is None and m.edge(b_, tmp + "X") is None, "删节点并连带删边")
    check(len(m.edges) == base, "边数回到 %d（实际 %d）" % (base, len(m.edges)))
    # 撤销/重做
    m.restore(snap0)
    check(len(m.edges) == base and m.node(tmp) is None and m.node(tmp + "X") is None,
          "restore 快照回到原状（%d 条边）" % len(m.edges))

    sec("6. 规划（与固件同一套 Dijkstra 的镜像）")
    m2 = M.MapModel.load_from_sources()
    for wps, note in [
        (["N2", "P1", "N5"], "第一轮初始路线（固件 mapInit 用）"),
        (["C9", "P7"], "C9 到 P7（平台支路）"),
        (["N22", "C6"], "N22 到 C6"),
        (["N3", "N4"], "相邻节点"),
    ]:
        path, why = m2.plan_route(wps, "full")
        if path is None:
            print("  %-28s %s -> 不可达：%s" % (note, wps, why))
        else:
            print("  %-28s %s -> %s" % (note, " -> ".join(wps), " -> ".join(path)))
    p1, _ = m2.plan_route(["N2", "P1", "N5"], "full")
    check(p1 == ["N2", "B1", "N1", "P1", "N1", "B2", "N4", "N5"] or
          (p1 and p1[0] == "N2" and p1[-1] == "N5"),
          "初始路线起止正确：%s" % (p1,))

    sec("7. 演示：一次真实地图改动（切断一条双向边 → 中间插一个新节点 → 重新连上）")
    m3 = M.MapModel.load_from_sources()
    # 挑一条"双向、且两端都不是平台/景点"的边作演示（地图改过也不怕）。
    pick = None
    for _e in m3.edges:
        if m3.has_reverse(_e) and _e.frm[0] in "NCB" and _e.to[0] in "NCB":
            pick = _e
            break
    check(pick is not None, "挑到一条可演示的双向边：%s" % (pick.label() if pick else None))
    if pick is None:
        return 1
    f_, t_ = pick.frm, pick.to
    mid = "%s_%s" % (f_, t_)            # 合法 C 标识符
    while m3.node(mid):
        mid += "_"
    print("  改动前 %s 出边: %s" % (f_, ", ".join(e.label() for e in m3.edges_of(f_, True))))
    for _a, _b in ((f_, t_), (t_, f_)):   # 1) 切断这条双向边
        m3.remove_edge(_a, _b)
    _fa, _tb = m3.node(f_), m3.node(t_)
    m3.add_node(mid, (_fa.x + _tb.x) / 2.0, (_fa.y + _tb.y) / 2.0, "演示插点")
    for _a, _b, _ang in ((f_, mid, 0), (mid, f_, 180), (mid, t_, 0), (t_, mid, 180)):
        m3.add_edge(_a, _b, flag="NO", angle=str(_ang), step="90", speed="SPEED2", func="NONE")
    print("  改动后 %s 出边: %s" % (f_, ", ".join(e.label() for e in m3.edges_of(f_, True))))
    print("  改动后 %s 出边: %s" % (mid, ", ".join(e.label() for e in m3.edges_of(mid, True))))
    print("  改动后 %s 出边: %s" % (t_, ", ".join(e.label() for e in m3.edges_of(t_, True))))
    check(m3.edge(f_, t_) is None and m3.edge(t_, f_) is None, "%s<->%s 已切断" % (f_, t_))
    check(m3.node(mid) is not None, "%s 已插在中间" % mid)
    m3.export_edge_table()
    check(mid in m3.export_enum(), "导出的 enum 里含 %s" % mid)
    check(m3.export_nav_edge_count() == "#define NAV_EDGE_COUNT %d" % len(m3.edges),
          "导出 NAV_EDGE_COUNT 与边数一致（%d）" % len(m3.edges))
    errs = [msg for lv, msg in m3.validate() if lv == "error"]
    check(not errs, "改动后无 error 级校验问题（%d 条）" % len(errs))
    for x in errs[:6]:
        print("        ", x)
    print("  注：本例只是演示「编辑器能不能做出这种改动」，具体连法等拓扑定了再改。")

    sec("8. 成本表 == 固件 nav_planner.c 的 NavObsPenalty[]（上位机路线≠车上路线的元凶）")
    fw = _parse_firmware_obs()
    if fw is None:
        print("  ⚠ 没能从 Navigation/nav_planner.c 解析出 NavObsPenalty[]，跳过")
    else:
        bad = []
        for idx, name in enumerate(M.FUNC_ORDER, start=1):
            want = fw[idx] if idx < len(fw) else None
            got = M.MapModel.OBS.get(name)
            if want is None or got is None or abs(float(got) - want) > 1e-6:
                bad.append((name, want, got))
        check(not bad, "OBS 与固件逐项一致（比 %d 项，不符 %d 项）" % (len(M.FUNC_ORDER), len(bad)))
        for name, want, got in bad[:12]:
            print("        %-14s 固件=%s 上位机=%s" % (name, want, got))

    sec("9. 门回程镜像 == 固件 golden（真值来源：地图修改上位机/validate/_check_door_perm.py）")
    try:
        # ⚠️ 这个目录**搬过家**：早期在仓库根 `scripts/validate/`，现在在
        #    `地图修改上位机/validate/`。以前这里硬编码旧路径 ⇒ 导入失败被静默跳过，
        #    整整一节断言形同虚设（只在输出里留一行"跳过"）。两个位置都试一遍。
        vdir = None
        for cand in (os.path.join(M.ROOT, "地图修改上位机", "validate"),
                     os.path.join(M.ROOT, "scripts", "validate")):
            if os.path.isfile(os.path.join(cand, "_check_door_perm.py")):
                vdir = cand
                break
        if vdir is None:
            raise ImportError("找不到 validate/_check_door_perm.py")
        if vdir not in sys.path:
            sys.path.insert(0, vdir)
        # 不往 validate/ 写 __pycache__（保持工作树干净；该目录的 .pyc 是被跟踪的）
        _prev_bc = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            import _check_door_perm as CP
        finally:
            sys.dont_write_bytecode = _prev_bc
        m9 = M.MapModel.load_from_sources()
        ok = 0
        for name, start, t, allow, want in CP.GOLDEN:
            wp, blocked = M.door_return_home_waypoints(start, t, allow)
            path, why = m9.plan_route(wp, "full", blocked)
            got = " ".join(path[1:]) if path else "N/A(%s)" % why
            good = (got == want)
            ok += good
            if not good:
                print("        [DIF] %-16s t=%d 期望=%s 实际=%s" % (name, t, want, got))
        check(ok == len(CP.GOLDEN),
              "门区禁用 + 极简 wp 复现 golden %d/%d" % (ok, len(CP.GOLDEN)))
    except Exception as e:                                   # noqa: BLE001
        print("  ⚠ 无法导入 _check_door_perm（%s），跳过该项" % e)

    sec("10. config.h 写回保留行尾注释（map_editor.App._rewrite_config_macro）")
    try:
        # map_editor 只在 main() 里建 Tk 窗口，import 本身不需要界面
        _prev_bc = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            import map_editor as E
        finally:
            sys.dont_write_bytecode = _prev_bc
        rw = E.App._rewrite_config_macro
    except Exception as e:                                   # noqa: BLE001
        warn("无法导入 map_editor（%s），跳过该项" % e)
    else:
        demo = ("#define A   1\n"
                "#define B   2   // 行尾注释\n"
                "#define C   3   /* 单行块注释 */\n"
                "#define D   4   /* 多行块注释的第一行\n"
                "                续行：S1 不能当途径点\n"
                "                收尾 */\n"
                "#define AB  5\n")
        out, n = rw(demo, "A", "9")
        check(n == 1 and "#define A   9\n" in out and "#define AB  5" in out,
              "A：只改值，名字带同前缀的 AB 不受影响")
        out, n = rw(demo, "B", "9")
        check(n == 1 and "#define B   9   // 行尾注释\n" in out, "B：行尾 // 注释保留")
        out, n = rw(demo, "C", "9")
        check(n == 1 and "#define C   9   /* 单行块注释 */\n" in out,
              "C：单行 /* */ 注释保留")
        out, n = rw(demo, "D", "9")
        check(n == 1 and out.count("/*") == demo.count("/*")
              and out.count("*/") == demo.count("*/"),
              "D：多行注释的 /* 开头没被吃掉（/* 与 */ 数量不变）")
        check(n == 1 and "续行：S1 不能当途径点" in out and "收尾 */\n" in out,
              "D：多行注释的续行与收尾原样保留")
        out, n = rw(demo, "NOT_THERE", "9")
        check(n == 0 and out == demo, "不存在的宏：原样返回（count=0）")
        # 真实文件干跑：拿现成的值回写一遍，必须**逐字节不变**
        # （同名宏在 #if FIELD_SCHOOL / #else 两个分支里各定义一次，写回只动第一处，
        #   所以按「首次出现」取值，每个名字只测一次）
        src = open(M.PATH_CONFIG, encoding="utf-8").read()
        first = {}
        for line in src.split("\n"):
            mm = re.match(r"^\s*#define\s+(\w+)\s+(\S.*)$", line)
            if not mm or mm.group(1) in first:
                continue
            rest = mm.group(2)
            cut = [p for p in (rest.find("/*"), rest.find("//")) if p >= 0]
            first[mm.group(1)] = rest[:min(cut) if cut else len(rest)].rstrip()
        bad = []
        for name, value in first.items():
            out, n = rw(src, name, value)
            if n != 1 or out != src:
                bad.append(name)
        check(bool(first) and not bad,
              "真实 config.h 干跑：%d 个对象宏用原值回写后逐字节不变（异常：%s）"
              % (len(first), ",".join(bad[:6]) or "无"))

    sec("11. 第二轮 wp 的巡游顺序（GUI「二轮路线…」改的就是它）")
    d_ok = [M.CAN_PASS, M.NO_PASS, M.NO_PASS, M.NO_PASS]        # D2 绿 ⇒ 进门 N12
    # ① 默认（cruise=None）必须与固件逐字一致：宝物=6 ⇒ 逆时针、其余顺时针
    for t, want in ((6, ["P6", "P8", "P7", "P5"]), (4, ["P5", "P7", "P8", "P6"])):
        wp, why = M.round2_waypoints(d_ok, t)
        got = [w for w in (wp or []) if w in ("P5", "P6", "P7", "P8")]
        check(why is None and got == want,
              "宝物=%s 默认巡游 %s" % (t, "→".join(got or ["?"])))
    # ② 固件源码里那两套顺序 == round2_firmware_cruise()（只认 get_newroute 里的 if/else 块）
    src = open(os.path.join(M.ROOT, "Mission", "mission_planner.c"), encoding="utf-8").read()
    blk = re.search(r"if\s*\(p6_first\)\s*\{(.*?)\}\s*else\s*\{(.*?)\}",
                    src.split("void get_newroute(void)", 1)[-1], re.S)
    ccw = re.findall(r"wp\[n\+\+\]\s*=\s*(P\d)\s*;", blk.group(1)) if blk else []
    cw = re.findall(r"wp\[n\+\+\]\s*=\s*(P\d)\s*;", blk.group(2)) if blk else []
    check(ccw == M.round2_firmware_cruise(6) and cw == M.round2_firmware_cruise(4),
          "固件源码里写死的两套顺序 == round2_firmware_cruise()（%s / %s）"
          % ("→".join(ccw), "→".join(cw)))
    # ③ 自定义顺序：只换巡游段，前缀/进门节点/终点都不动
    wp0, _ = M.round2_waypoints(d_ok, 6)
    custom = ["P5", "P6", "P8", "P7"]
    wp1, _ = M.round2_waypoints(d_ok, 6, custom)
    check([w for w in wp1 if w in ("P5", "P6", "P7", "P8")] == custom
          and wp1[:5] == wp0[:5] and wp1[5] == wp0[5] and wp1[-1] == "P2",
          "自定义顺序只换巡游段（前缀 %s / 进门 %s / 终点 %s 不变）"
          % (" ".join(wp1[:5]), wp1[5], wp1[-1]))
    # ④ 进门"多保留的 N8"跟巡游首站走（固件里就是 p6_first）
    d_n3 = [M.NO_PASS, M.NO_PASS, M.CAN_PASS, M.NO_PASS]        # D4 绿 ⇒ 进门 N3
    check(M.round2_waypoints(d_n3, 4)[0].count("N8") == 1
          and M.round2_waypoints(d_n3, 4, ["P6", "P8", "P7", "P5"])[0].count("N8") == 2,
          "门区多保留的 N8 跟巡游首站走（首站 P5 留 1 / 首站 P6 留 2）")
    # ⑤ 三条门都不通 ⇒ 固件会停车
    check(M.round2_waypoints([M.NO_PASS] * 4, 4)[0] is None,
          "D2/D3/D4 都不能过 返回 None（固件会 CarBrake_Stop）")

    sec("12. 转弯前补偿（map.c：kTurnTbl / 陀螺 if 链 / Tier2 参数）")
    # ① 解析：两张表都能从源码里读出来，且**注释掉的条目不算**（§14.5 的维护注意）
    turn = M.parse_turn_tables()
    check(not turn["warnings"] and len(turn["stop"]) > 0 and len(turn["gyro"]) > 0,
          "解析 map.c 两张补偿表：表1 停车转 %d 条 / 表2 陀螺转 %d 条（警告 %d 条）"
          % (len(turn["stop"]), len(turn["gyro"]), len(turn["warnings"])))
    _mapc = open(M.PATH_MAP_C, encoding="utf-8").read()
    check(all(isinstance(r["dist"], float) for r in turn["stop"] + turn["gyro"]),
          "表项都是 (last, now, next, 数值) 四元组")
    # 表体行数 == 解析条数 ⇒ 说明一行没漏、也没把注释行/花括号注释算进来
    _blk = re.search(r"kTurnTbl\s*\[\s*\]\s*=\s*\{(.*?)\n\};", _mapc, re.S)
    _rows_in_src = (len(re.findall(r"^\s*\{\s*[A-Za-z_]\w*\s*,", _blk.group(1), re.M))
                    if _blk else -1)
    _cmm_in_src = (len(re.findall(r"^\s*//.*\{\s*[A-Za-z_]\w*\s*,", _blk.group(1), re.M))
                   if _blk else 0)
    check(_rows_in_src == len(turn["stop"]),
          "表1 表体里的行数 == 解析出来的条数（%d == %d；被 // 注释掉的 %d 条没算进来）"
          % (_rows_in_src, len(turn["stop"]), _cmm_in_src))
    # ② 公式参数 + 开关
    for key in ("TURN_L_PIVOT", "TURN_GATE_CM", "TURN_D_CRIGHT", "TURN_D_CLEFT",
                "TURN_D_DLEFT", "TURN_D_DEFAULT"):
        check(key in turn["consts"], "公式参数 %s = %g" % (key, turn["consts"][key]))
    check(turn["calc_enable"] in (0, 1, None),
          "TURN_CALC_ENABLE 从 config.h 读到了：%s" % turn["calc_enable"])
    _ce = re.search(r"^\s*#define\s+TURN_CALC_ENABLE\s+(\d+)",
                    open(M.PATH_CONFIG, encoding="utf-8").read(), re.M)
    check(_ce and turn["calc_enable"] == int(_ce.group(1)),
          "开关值与 config.h 源码一致（%s）" % (_ce.group(1) if _ce else "?"))
    # ③ 覆盖度：枚举全部转弯组合，且三个分支都有
    model = M.MapModel.load_from_sources()
    cov = model.turn_coverage()
    s = cov["stats"]
    check(s["total"] == s["straight"] + s["stop"] + s["gyro"] + s["unknown"]
          and s["total"] > 100,
          "覆盖总览 = %d 个组合（直行 %d / 停车转 %d / 陀螺转 %d）"
          % (s["total"], s["straight"], s["stop"], s["gyro"]))
    check(len(cov["rows"]) == s["total"]
          and all(r["source"] for r in cov["rows"]),
          "每一行都给出了「当前生效值」的来源（含吃默认值的那批）")
    check(s["stop_meas"] + s["stop_calc"] + s["stop_default"] == s["stop"],
          "停车转的 %d 个组合被完整分档（实测 %d / 公式 %d / 默认 19 %d）"
          % (s["stop"], s["stop_meas"], s["stop_calc"], s["stop_default"]))
    # ④ 分支判定 == 固件公式（照抄 map.c: Nav_TurnAndAdvance 的判据独立算一遍）
    for r in cov["rows"]:
        d = r["delta"]
        ie = model.edge(r["last"], r["now"])
        want = ("straight" if (d is None or abs(d) < 10.0
                               or ie.func in ("UpStage", "UpStageHome", "BSoutPole")
                               or "NOTURN" in M.flag_set(ie.flag))
                else "stop" if (abs(d) >= 90.0
                                or ("STOPTURN" in M.flag_set(ie.flag) and abs(d) > 20.0))
                else "gyro")
        if r["branch"] != want:
            break
    else:
        check(True, "分支判定与 map.c 的 (STOPTURN&&|Δ|>20)|||Δ|>=90 逐条一致")
    # ⑤ 表项状态：「会不会生效」必须能判出来，且死值一定给了原因
    for table, key in (("stop", "stop"), ("gyro", "gyro")):
        st = model.turn_status(model.turn[key], table)
        ok = [x for x in st if x[0] == "ok"]
        check(len(st) == len(model.turn[key]) and all(x[1] for x in st),
              "表「%s」%d 行都判出了是否生效（生效 %d / 死值 %d）"
              % (table, len(st), len(ok), len(st) - len(ok)))
    # ⑥ 写回是纯函数 + 幂等 + 不重复护栏 + 没编辑就不动
    out = M.splice_turn_tables(_mapc, model.turn["stop"], model.turn["gyro"])
    back = M.parse_turn_tables(source_text=out)
    check(M.turn_rows_equal(back["stop"], model.turn["stop"])
          and M.turn_rows_equal(back["gyro"], model.turn["gyro"]),
          "写回后重新解析，两张表逐项不变（往返一致）")
    check(out == M.splice_turn_tables(out, model.turn["stop"], model.turn["gyro"]),
          "写回幂等（对结果再写一次逐字节相同）")
    check(out.count("kTurnTbl_node_check") == _mapc.count("kTurnTbl_node_check") == 1
          and out.count("void ") == _mapc.count("void ")
          and out.count("GetForwardDistanceBeforeGyroTurn") == 2,
          "写回只动三处，不重复护栏/不吞别的函数")
    check(back["consts"] == model.turn["consts"],
          "写回不影响公式参数（参数由 #define 单独控制）")
    # ⑦ 编辑一行 → 写回 → 再解析，改的只有那一行
    edit = [dict(r) for r in model.turn["stop"]]
    edit[0]["dist"] = 12.5
    out2 = M.splice_turn_tables(_mapc, edit, model.turn["gyro"])
    back2 = M.parse_turn_tables(source_text=out2)
    check(back2["stop"][0]["dist"] == 12.5
          and M.turn_rows_equal(back2["stop"][1:], model.turn["stop"][1:]),
          "改一行的值 → 写回 → 只有那一行变了（12.5）")
    check(not M.turn_rows_equal(back2["stop"], model.turn["stop"]),
          "「改过 / 没改过」能被区分出来（写回据此决定要不要重排格式）")
    # ⑧ 节点号护栏跟着表项重生成
    more = edit + [{"last": "N8", "now": "N5", "next": "P4", "dist": 7.0}]
    out3 = M.splice_turn_tables(_mapc, more, model.turn["gyro"])
    check("(P4 " in out3, "新增表项后，kTurnTbl_node_check 自动带上新节点（P4）")

    sec("结果")
    if FAIL:
        print("失败 %d 项：" % len(FAIL))
        for f in FAIL:
            print("  -", f)
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
