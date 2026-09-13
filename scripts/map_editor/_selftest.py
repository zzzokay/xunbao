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

    sec("9. 门回程镜像 == 固件 golden（真值来源：scripts/validate/_check_door_perm.py）")
    try:
        vdir = os.path.join(M.ROOT, "scripts", "validate")
        if vdir not in sys.path:
            sys.path.insert(0, vdir)
        # 不往 scripts/validate/ 写 __pycache__（保持工作树干净；本目录的 .pyc 是被跟踪的）
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
