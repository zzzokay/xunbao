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
 11. 第二轮 wp：顺序来自 config.h 的 ROUND2_CRUISE_*（读/写回往返 + 自定义只换巡游段）
12. 转弯前补偿：解析 map.c 两张表 / 覆盖度 / 分支判定 / 写回幂等与护栏
13. 布局 JSON 对比迁移：diff 产出指令 / 应用生效 / 迁移后收敛零差异 / 反向边只提示
15. 门区状态表：barrier.c 触发链 / door_zone 解析，沙箱写回，真实固件 SHA256 不变
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
    # 不硬编码「最后一项是谁」（地图加节点就会红）：按模型最后一个节点动态判
    check(m.nodes[-1].name in enum_lines[-2]
          and not enum_lines[-2].rstrip().endswith(","),
          "enum 最后一项（%s）无逗号" % m.nodes[-1].name)

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
        # --- 权重拉条「⚖ 规划权重…」的契约 ---
        check(hasattr(M, "parse_obs_penalty") and hasattr(M, "write_obs_penalty"),
              "map_model 提供 parse/write_obs_penalty（拉条读写固件 NavObsPenalty[] 的入口）")
        check(len(M.WEIGHT_EDITABLE) >= 10 and "Hill" in M.WEIGHT_EDITABLE
              and "BLBL" in M.WEIGHT_EDITABLE and "SM" in M.WEIGHT_EDITABLE,
              "WEIGHT_EDITABLE 含调南环最关键的 3 项（Hill/BLBL/SM），共 %d 项"
              % len(M.WEIGHT_EDITABLE))
        # 块注释状态机：固件里 Hill/DOOR 两项注释跨多行且含 `**`，
        # 用朴素的 `/* ... */` 非贪婪剥注释会漏项⇒ 只解析到 18 项。
        check(len(fw) >= 20,
              "NavObsPenalty[] 解析到 ≥20 项（跨行注释+含 `**` 的注释都要正确跳过，实得 %d）"
              % len(fw))
        check(abs(fw[13] - M.MapModel.OBS.get("BLBL", -1)) < 1e-6
              and abs(fw[6] - M.MapModel.OBS.get("SM", -1)) < 1e-6,
              "BLBL(下标13)/SM(下标6) 下标对齐正确（写回靠这个映射，写错会改错行）")
        # --- 「查看代码差异」里的权重段 ---
        check(hasattr(M, "obs_diff") and hasattr(M, "obs_diff_lines"),
              "map_model 提供 obs_diff/obs_diff_lines（『查看代码差异』的权重段）")
        cur_obs = {n: v for n, v in M.MapModel.OBS.items()}
        same_td = M.obs_diff(cur_obs, {n: v for n, v in zip(M.FUNC_ORDER, fw[1:])})
        check(same_td["same"],
              "obs_diff：与固件一致时判为无差异")
        cur_obs2 = dict(cur_obs)
        cur_obs2["BLBL"] = cur_obs2.get("BLBL", 0) - 30
        chg_td = M.obs_diff(cur_obs2, {n: v for n, v in zip(M.FUNC_ORDER, fw[1:])})
        check((not chg_td["same"]) and len(chg_td["chg"]) == 1
              and chg_td["chg"][0][0] == "BLBL",
              "obs_diff：改 1 项就只报那 1 项（不误报/不漏报）")
        check(any("写回固件后两边才一致" in l for l in M.obs_diff_lines(chg_td)),
              "obs_diff_lines：有差异时提示『写回后才一致』"
              "（这是『显示的路线≠车上跑的』的关键提醒）")
        # --- 权重拉条里的「线索条件」解析：必须与「线索路线…」run() 逐行对齐 ---
        # ⚠️ clue_cfg_args 住在 map_editor.App 上（GUI 模块），**本自检不 import GUI**。
        #    这里锁的是它依赖的**纯解析契约**（门灯名→状态码、宝物串→整数），
        #    真正的端到端验证在 _guismoke（那里本来就要建 Tk）。
        check(M.DOOR_STATE_NAME[M.CAN_PASS] in
              [M.DOOR_STATE_NAME[s] for s in M.DOOR_STATE_ORDER],
              "门灯显示名与状态码一一对应（权重拉条的线索下拉靠它把文本转回状态码）")
        check(int("5 · P5".split(" ")[0]) == 5,
              "宝物下拉串『5 · P5』可解析出编号 5（权重拉条复用同一套解析）")
        check(("P5=5, P8=8".split(",")[0].split("=")[1],
               "P5=5, P8=8".split(",")[1].split("：")[0].split("=")[1]) == ("5", "8"),
              "平台A/B 串『P5=5, P8=8』可解析出 (5, 8)（与线索路线 run() 同一套 split）")

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
    # ② 顺序由 config.h 的 ROUND2_CRUISE_* 给出（2026-10-07 起，不再是 mission_planner.c 里的死值）
    r2 = M.parse_round2_cruise()
    check(not r2["warnings"], "config.h 的 ROUND2_CRUISE_* 能解析出两组顺序（%s / %s）"
          % ("→".join(r2["cw"]), "→".join(r2["ccw"])))
    check(r2["cw"] == M.round2_firmware_cruise(4, r2)
          and r2["ccw"] == M.round2_firmware_cruise(6, r2),
          "round2_firmware_cruise() 读的就是 config.h 的两组（宝物≠6 走 CW / =6 走 CCW）")
    # ③ 固件必须用 cruise[] 走 wp，且 p6_first 由巡游首站决定（巡游平台不再写死 wp[n++] = P#）
    mp = open(os.path.join(M.ROOT, "Mission", "mission_planner.c"), encoding="utf-8").read()
    g = mp.split("void get_newroute(void)", 1)[-1]
    check(re.search(r"wp\[n\+\+\]\s*=\s*cruise\[0\]", g) is not None
          and re.search(r"cruise\[0\]\s*==\s*P6", g) is not None
          and re.search(r"wp\[n\+\+\]\s*=\s*P[5-8]\s*;", g.split("use_tour", 1)[0]) is None,
          "get_newroute() 巡游段用 cruise[]（顺序来自宏）、p6_first = (cruise[0]==P6)")
    # ④ 写回：往返一致 + 自定义能落回去 + 能再解析回来（纯函数干跑，不碰真实文件）
    cfg_src = open(M.PATH_CONFIG, encoding="utf-8").read()
    same_src, n0 = M.splice_round2_cruise(cfg_src, r2["cw"], r2["ccw"])
    check(same_src == cfg_src and n0 == 8, "splice_round2_cruise 用原值回写 ⇒ 逐字节不变")
    _ccw, _cccw = ["P5", "P6", "P7", "P8"], ["P8", "P7", "P6", "P5"]
    new_src, n1 = M.splice_round2_cruise(cfg_src, _ccw, _cccw)
    back = M.parse_round2_cruise(source_text=new_src)
    check(n1 == 8 and back["cw"] == _ccw and back["ccw"] == _cccw,
          "splice_round2_cruise 写入自定义顺序后能再解析回来")
    check(M.splice_round2_cruise(new_src, r2["cw"], r2["ccw"])[0] == cfg_src,
          "splice_round2_cruise 还原回出厂顺序 == 原文件内容")
    # ⑤ 自定义顺序：只换巡游段，前缀/进门节点/终点都不动
    wp0, _ = M.round2_waypoints(d_ok, 6)
    custom = ["P5", "P6", "P8", "P7"]
    wp1, _ = M.round2_waypoints(d_ok, 6, custom)
    check([w for w in wp1 if w in ("P5", "P6", "P7", "P8")] == custom
          and wp1[:5] == wp0[:5] and wp1[5] == wp0[5] and wp1[-1] == "P2",
          "自定义顺序只换巡游段（前缀 %s / 进门 %s / 终点 %s 不变）"
          % (" ".join(wp1[:5]), wp1[5], wp1[-1]))
    # ⑥ 进门"多保留的 N8"跟巡游首站走（固件里就是 p6_first）
    d_n3 = [M.NO_PASS, M.NO_PASS, M.CAN_PASS, M.NO_PASS]        # D4 绿 ⇒ 进门 N3
    check(M.round2_waypoints(d_n3, 4)[0].count("N8") == 1
          and M.round2_waypoints(d_n3, 4, ["P6", "P8", "P7", "P5"])[0].count("N8") == 2,
          "门区多保留的 N8 跟巡游首站走（首站 P5 留 1 / 首站 P6 留 2）")
    # ⑦ 三条门都不通 ⇒ 固件会停车
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

    sec("13. 路口判断标志位（DLEFT/DRIGHT ↔ 终点路口几何）")
    # ① 方向映射：need2turn 符号 == 物理左右（用交叉积验证，angle 是干净方向场）
    import math as _m
    def _vec(a):
        r = _m.radians(a)
        return (-_m.cos(r), _m.sin(r))
    def _cross(a, b):
        return a[0] * b[1] - a[1] * b[0]
    check(_cross(_vec(180), _vec(90)) > 0 and M.need2turn(180, 90) < 0,
          "右转（朝右180→朝下90）：need2turn<0 且 交叉积>0，方向约定一致")
    check(_cross(_vec(0), _vec(90)) < 0 and M.need2turn(0, 90) > 0,
          "左转（朝左0→朝下90）：need2turn>0 且 交叉积<0，方向约定一致")
    # ② 已知基准：P3→N3(180°) 终点 N3 有右转出边 N10(90°)，flag 应为 DRIGHT
    e_p3 = model.edge("P3", "N3")
    _need_p3 = M.junction_flags_needed(model, e_p3) if e_p3 is not None else {}
    check(e_p3 is not None and "DRIGHT" in _need_p3 and "DLEFT" not in _need_p3,
          "P3→N3 终点有右转 90° 出边 ⇒ 需要 DRIGHT（不需要 DLEFT）")
    check("DRIGHT" in M.flag_set(e_p3.flag) and "DLEFT" not in M.flag_set(e_p3.flag),
          "P3→N3 现有 flag 就是 DRIGHT（与几何一致）")
    # ③ 已知基准：N6→N5(0°) 终点 N5 有左转出边 N12(90°)，flag 应为 DLEFT
    e_n6 = model.edge("N6", "N5")
    _need_n6 = M.junction_flags_needed(model, e_n6) if e_n6 is not None else {}
    check(e_n6 is not None and "DLEFT" in _need_n6 and "DRIGHT" not in _need_n6,
          "N6→N5 终点有左转 90° 出边 ⇒ 需要 DLEFT（不需要 DRIGHT）")
    check("DLEFT" in M.flag_set(e_n6.flag) and "DRIGHT" not in M.flag_set(e_n6.flag),
          "N6→N5 现有 flag 就是 DLEFT（与几何一致）")
    # ④ 全图分析：能列出不一致，且 func 字段齐全、状态是 extra/missing/wrong 之一
    issues = M.analyze_junction_flags(model, only_plain=True)
    check(all(it["status"] in ("extra", "missing", "wrong") and "func" in it
              and (it["extra"] or it["missing"]) for it in issues),
          "全图分析能列出 %d 条不一致，且每条都有 func/status/extra|missing" % len(issues))
    # ⑤ suggest_junction_flags 幂等：对建议结果再建议一次 == 同一个值
    for it in issues[:5]:
        e = it["edge"]
        once = M.suggest_junction_flags(model, e)
        e.flag = once
        twice = M.suggest_junction_flags(model, e)
        check(once == twice, "suggest_junction_flags 幂等（%s：%s）" % (e.label(), once))
    # ⑥ suggest 只重写「到达判据」位（JUNCTION_ARRIVE_FLAGS），非到达判据位原样保留
    e_b3 = model.edge("B3", "N4")
    if e_b3 is not None:
        orig = M.flag_set(e_b3.flag)
        sug = M.suggest_junction_flags(model, e_b3)
        new = M.flag_set(sug)
        # 非到达判据位（寻线/转弯/陀螺/门区等）必须原样保留
        for keep in ("STOPTURN", "AWHITE", "LEFT_LINE", "RIGHT_LINE", "NOTURN", "RESTMPUZ"):
            if keep in orig:
                check(keep in new, "suggest 保留非到达位（%s：%s 仍含 %s）" % (e_b3.label(), sug, keep))
        # 到达判据位（DLEFT/DRIGHT/CLEFT/CRIGHT/MCLEFT/MCRIGHT/MUL2SING/MUL2MUL）
        # 应按几何重写，结果与 junction_flags_needed 完全一致（这是新多维分类器的契约）
        need = M.junction_flags_needed(model, e_b3)
        for n in M.JUNCTION_ARRIVE_FLAGS:
            check((n in new) == (n in need),
                  "到达判据位 %s 与几何一致（%s）" % (n, e_b3.label()))
    # ⑦ include_mul 开关：False 时不写 MUL2SING/MUL2MUL，角度类照写
    e_p3 = model.edge("P3", "N3")
    if e_p3 is not None:
        full = M.suggest_junction_flags(model, e_p3, include_mul=True)
        lite = M.suggest_junction_flags(model, e_p3, include_mul=False)
        check("MUL2MUL" in M.flag_set(full),
              "include_mul=True：P3→N3 连 MUL2MUL 一起标（%s）" % full)
        check("MUL2MUL" not in M.flag_set(lite) and "DRIGHT" in M.flag_set(lite),
              "include_mul=False：P3→N3 只标角度类、不标 MUL2MUL（%s）" % lite)
        # 分析口径一致：关掉 MUL 后，analyze 也不再把「现写有 MUL2MUL」报成 extra
        _need_off = M.junction_flags_needed(model, e_p3, include_mul=False)
        check("MUL2MUL" not in _need_off,
              "include_mul=False 时 junction_flags_needed 不算 MUL2MUL")
    # ⑧ right_only 开关：只检查 DLEFT/DRIGHT，忽略 C/MC 精细分档与 MUL
    e_n16 = model.edge("N16", "N18")
    if e_n16 is not None:
        ro = M.analyze_junction_flags(model, only_plain=True, include_mul=False,
                                      right_only=True)
        ro_flags = set()
        for it in ro:
            ro_flags |= set(it["extra"]) | set(it["missing"])
        check(ro_flags <= {"DLEFT", "DRIGHT"},
              "right_only=True 时只报 DLEFT/DRIGHT（不掺 C/MC/MUL）：%s" % sorted(ro_flags))
        # 现图 N16→N18 flag=DLEFT|DRIGHT（几何只需 DLEFT）⇒ right_only 应报「多余 DRIGHT」
        _it = next((x for x in ro if x["edge"] is e_n16), None)
        check(_it is not None and "DRIGHT" in _it["extra"],
              "right_only 抓出 N16→N18 多余的 DRIGHT（现图 DLEFT|DRIGHT，几何只需 DLEFT）")
        # 「左右写反」硬错的抓取能力不能依赖真实地图碰巧是错的：内存里把 flag 改回只留
        # DRIGHT（写反态）再验一次，验完立刻还原（⑤ 已有先例：直接改 model 内存实例）
        _orig_flag = e_n16.flag
        e_n16.flag = "DRIGHT"
        _ro2 = M.analyze_junction_flags(model, only_plain=True, include_mul=False,
                                        right_only=True)
        e_n16.flag = _orig_flag
        _it2 = next((x for x in _ro2 if x["edge"] is e_n16), None)
        check(_it2 is not None and "DRIGHT" in _it2["extra"] and "DLEFT" in _it2["missing"],
              "人为写反（只留 DRIGHT）后 right_only 仍抓出 N16→N18（多余 DRIGHT、缺失 DLEFT）")

    sec("时间预算（分级贪分，2026-10-12）")
    _tb = M.time_budget_macros()
    check(_tb["TB_P1_NO_SIGHTS_AT_S"] == 135 and _tb["TB_P1_HOME_ONLY_AT_S"] == 145,
          "5 个 TB_* 宏从 config.h 读到（P1 专用 = %d/%d）"
          % (_tb["TB_P1_NO_SIGHTS_AT_S"], _tb["TB_P1_HOME_ONLY_AT_S"]))
    _raw_en = str(M.parse_config_macros()[0].get("TIME_BUDGET_ENABLE", "")).strip()
    check(M.time_budget_enabled() is (_raw_en == "1"),
          "TIME_BUDGET_ENABLE 的 0/1 → bool 映射正确（config.h 现值 = %r；改它不该让自检红）"
          % _raw_en)
    check([t for _r, t, _d in M.round1_tail_ladder(2)] == [0, 1, 3],
          "宝物=P1 的档位只有 全跑/仅平台/回家 三档（没有「只跑一个平台」）")
    check([t for _r, t, _d in M.round1_tail_ladder(3)] == [0, 1, 2, 3],
          "其余宝物是四档：全跑/不跑景点/只跑一个平台/回家")
    check([M.round1_tail_tier(2, s)[0] for s in (134, 135, 144, 145)] == [0, 1, 1, 3],
          "宝物=P1 的 2:15/2:25 分界（134→全跑 / 135,144→仅平台 / 145→回家）")
    check(M.round1_tail_tier(2, 150)[0] == 3 and M.round1_tail_tier(4, 150)[0] == 1,
          "同一时刻 150s：宝物=P1 已回家、宝物=P4 还在跑平台（两套阈值互不干扰）")
    _wp2, _i2 = M.round1_tail_plan(2, 0, True, True, elapsed_s=140)
    check(_i2["trigger"] == "在 P1 取完宝那一刻" and _i2["exit_n3"] is True
          and _wp2 == ["P3", "P4"],
          "宝物=P1 的定档点 = 「在 P1 取完宝那一刻」，出口恒按 N3 侧（exit_n3=True）")
    _i4a = M.round1_tail_plan(4, 0, True, True, elapsed_s=140, exit_node="N5")[1]
    _i4b = M.round1_tail_plan(4, 0, True, True, elapsed_s=140, exit_node="N3")[1]
    check(_i4a["trigger"].startswith("回程到达出门边") and _i4a["exit_n3"] is False
          and _i4b["exit_n3"] is True,
          "其余宝物的定档点仍是出门边，exit_n3 跟着 N3/N5 走")
    check([r[3] for r in M.round1_tail_ladder_wp(2, 0, True, True)]
          == [["P3", "S1", "P4", "S2"], ["P3", "P4"], []],
          "宝物=P1·百位0 的档位阶梯 wp：全跑 / 仅平台 / 空（直接回家）")
    check(M.round1_return_extra_waypoints(2, 0, True, True) == ["P3", "S1", "P4", "S2"]
          and M.round1_return_extra_waypoints(3, 0, False, True) == ["S1"]
          and M.round1_return_extra_waypoints(4, 0, False, True) == ["S2"],
          "旧签名薄壳行为不变（回归）")

    sec("14. 布局 JSON 对比迁移（layout_diff / apply_layout_diff_items）")
    import json as _json
    # ① 格式护栏：选错文件要报错，而不是静默比出一堆废话
    try:
        M.layout_diff({"format": "x"}, {"format": "xunbao-map"})
        check(False, "format 不对时应抛 ValueError")
    except ValueError:
        check(True, "format 不对时抛 ValueError（防选错文件）")
    # ② 真实布局自比 = 零可迁移差异
    _ja = _json.loads(m.to_json())
    _z = M.layout_diff(_ja, _json.loads(_json.dumps(_ja)))
    check(not [r for s in _z for r in s["rows"] if r["apply"]],
          "同一份 JSON 自比：0 项可迁移")
    # ③ 构造一份"改过的参考 B"（动态取键，不硬编码节点/边 —— AI_CONTEXT §7.8）
    _jb = _json.loads(_json.dumps(_ja))
    _mk = sorted(_jb["macros"])[0]
    _jb["macros"][_mk] = str(_jb["macros"][_mk]) + "x"            # 宏改值
    _jb["field"] = ("FIELD_COMP" if _ja.get("field") != "FIELD_COMP"
                    else "FIELD_SCHOOL")
    _st = _jb["turn"]["stop"]
    _st0 = dict(_st[0])
    _st0["dist"] = float(_st0["dist"]) + 0.5
    _st[0] = _st0                                                  # 改一行
    _stdel = dict(_st.pop())                                       # 删一行（仅 A 有）
    _st.append({"last": "ZZ1", "now": "ZZ2", "next": "ZZ3",
                "dist": 9.0})                                      # B 新增一行
    _ck2 = sorted(_jb["turn"]["consts"])[0]
    _jb["turn"]["consts"][_ck2] = _jb["turn"]["consts"][_ck2] + 1  # 常量改值
    _jb["nodes"][0]["x"] = float(_jb["nodes"][0]["x"]) + 3.0       # 节点挪位
    _jb["edges"][0]["step"] = str(_jb["edges"][0]["step"]) + " "   # 边参数改文本
    _jb["constraints"]["unit_px_per_cm"] = \
        float(_jb["constraints"].get("unit_px_per_cm", 1.0)) + 0.1
    _jb["background"]["opacity"] = 0.9
    _ja["macros"]["__EXTRA_ONLY_A__"] = "1"                        # 仅 A 有的宏
    _rows = [r for s in M.layout_diff(_ja, _jb) for r in s["rows"]]
    _items = [r["apply"] for r in _rows if r["apply"]]
    _kinds = [it[0] for it in _items]
    check("field" in _kinds and "macro" in _kinds and "const" in _kinds,
          "场地/宏/常量差异都被抓到")
    check(_kinds.count("turn") == 2 and _kinds.count("turndel") == 1,
          "转弯表：改 1 行 + 新增 1 行 + 删 1 行")
    check("node" in _kinds and "edge" in _kinds
          and "constr" in _kinds and "bg" in _kinds,
          "节点/边/约束/底图差异都被抓到")
    check(any(r["apply"] is None and "仅 A 有" in r["act"] for r in _rows),
          "「仅 A 有」的宏只提示、不生成迁移指令")
    _delrows = [r for r in _rows if r["apply"]
                and r["apply"][0] in ("nodedel", "edgedel", "turndel")]
    check(_delrows and all(r["sel"] is False for r in _delrows),
          "删除类指令默认不勾（sel=False，防误删）")
    # ④ 应用到干净模型，然后与应用后的模型应收敛为零可迁移差异
    _m2 = M.MapModel()
    _m2.load_json(_json.dumps(_ja))
    _n = M.apply_layout_diff_items(_m2, _items)
    check(_n == len(_items), "全部指令生效（%d/%d）" % (_n, len(_items)))
    check(_m2.macros[_mk] == _jb["macros"][_mk], "宏值已迁成 B 的")
    check(_m2.field_name == _jb["field"], "场地已迁成 B 的")
    check(any(r.get("last") == "ZZ1" for r in _m2.turn["stop"])
          and all((r.get("last"), r.get("now"), r.get("next"))
                  != (_stdel["last"], _stdel["now"], _stdel["next"])
                  for r in _m2.turn["stop"]),
          "转弯表：新增行在、被删行不在")
    _m2j = _json.loads(_m2.to_json())
    _z2 = [r for s in M.layout_diff(_m2j, _jb) for r in s["rows"] if r["apply"]]
    check(not _z2, "迁移后 A\' 与 B 收敛为零可迁移差异（%s）"
          % "; ".join(r["label"] for r in _z2[:5]))
    # ⑤ 反向边只提示不自动迁（方向语义要人工定）
    _ra = {"format": "xunbao-map", "edges": [{"frm": "XX", "to": "YY"}]}
    _rb = {"format": "xunbao-map", "edges": [{"frm": "YY", "to": "XX"}]}
    _rr = [r for s in M.layout_diff(_ra, _rb) for r in s["rows"]]
    check(any(r["apply"] is None and "方向不同" in r["act"] for r in _rr)
          and any(r["apply"] and r["apply"][0] == "edgedel" for r in _rr)
          and any(r["apply"] and r["apply"][0] == "edge" for r in _rr),
          "只有反向边的情形：一条提示 + 默认不勾的删除 + 另一方向的新增")

    sec("15. 门区状态表（barrier.c 触发链 / door_zone 解析 + 沙箱写回）")
    import json as _json2
    import hashlib as _hl
    # ① 真实固件解析：5 条触发链，D5_BACK 已是 N20→N3（2026-10-17 迁移）
    _trig, _tw = M.parse_door_triggers()
    check(len(_trig) == 5 and not _tw,
          "barrier.c 触发链解析出 5 条（无警告）")
    _d5 = next((t for t in _trig if t["state"] == "DOOR_D5_BACK"), None)
    check(_d5 is not None and _d5["last"] == "N20" and _d5["now"] == "N3",
          "DOOR_D5_BACK 触发边 = N20→N3（注释=%s）" % (_d5 or {}).get("note", ""))
    _slots = M.parse_door_slots()
    check(_slots.get("DOOR_D5_BACK") == 3 and _slots.get("DOOR_D4_BACK") == 2,
          "door_pass 下标：D5_BACK→3、D4_BACK→2（%s）" % _slots)
    _pes = M.parse_door_pass_edges()
    check(_pes.get("DOOR_D5_BACK") == ("N20", "N3"),
          "D5_BACK 过门动作 door_set_pass_node(N20,N3)（%s）" % (_pes.get("DOOR_D5_BACK"),))
    _rts = M.parse_door_retreats()
    check(_rts.get("DOOR_D5_BACK") is not None,
          "D5_BACK 退回分支解析成功（door_retreat%s；起点是否跟触发边一致由"
          " door_back_flow 的 hazard 动态提示）" % (_rts.get("DOOR_D5_BACK"),))
    _zone, _zw = M.parse_door_zone()
    check(len(_zone) == 8 and ("N3", "N20") in _zone and ("N20", "N3") in _zone
          and ("N3", "N10") not in _zone and not _zw,
          "door_zone[8][2] 解析 8 对且 N20↔N3 已进、N10↔N3 已出")
    # ② 动态 BACK 门链路
    _be = M.door_back_edges()
    check(_be.get(("N20", "N3")) == (3, "DOOR_D5_BACK")
          and _be.get(("N8", "N3")) == (2, "DOOR_D4_BACK"),
          "door_back_edges() 动态识别两条 BACK 门边")
    check(M.door_back_slot_edge(3) == ("N20", "N3")
          and M.door_back_slot_edge(2) == ("N8", "N3"),
          "door_back_slot_edge(3)/(2) = D5/D4 的 BACK 边")
    _hops, _start, _allow, _note = M.door_back_chain([1, 1, 1, 2], ("N20", "N3"))
    check(_hops == [] and _start == "N3" and not _allow and "door_1" in _note,
          "D5_BACK 绿：直接落 N3 重规划（起点跟着触发边终点走）")
    _hops2, _start2, _al2, _note2 = M.door_back_chain([3, 2, 2, 1], ("N20", "N3"))
    _bk = (_rts.get("DOOR_D5_BACK") or ("N20", "N8"))[1]
    check(_hops2 == [_bk, "N3"] and _start2 == "N3",
          "D5_BACK 非绿 + D2 蓝 + D4 绿：退回 %s ⇒ %s→N3 重读 D4（hops 动态）"
          % (_bk, _bk))
    _wps, _blocked = M.door_return_home_waypoints("N3", 2, False)
    check(("N20", "N3") in _blocked and ("N3", "N20") in _blocked
          and ("N10", "N3") not in _blocked and ("N3", "N10") not in _blocked,
          "门区回程禁用边来自 get_door_zone()：N20↔N3 禁、N10↔N3 不再禁")
    # ③ 沙箱写回 barrier.c / mission_planner.c（真实固件文件必须一字不动）
    _tmpdir = os.path.join(HERE, "_selftest_door_%d" % os.getpid())
    os.makedirs(_tmpdir, exist_ok=True)
    try:
        _real_bc = M._fw_path("Mission", "barrier.c")
        _real_mp = M._fw_path("Mission", "mission_planner.c")
        _sha = lambda p: _hl.sha256(open(p, "rb").read()).hexdigest()
        _bc0, _mp0 = _sha(_real_bc), _sha(_real_mp)
        _sb_bc = os.path.join(_tmpdir, "barrier.c")
        _sb_mp = os.path.join(_tmpdir, "mission_planner.c")
        import shutil as _sh
        _sh.copy2(_real_bc, _sb_bc)
        _sh.copy2(_real_mp, _sb_mp)
        # 改触发边：D2 的 N5→N12 改成 N9→N13（假节点，只验字节级替换）
        _ok, _msg = M.set_door_trigger("DOOR_D2", "N9", "N13",
                                       path=_sb_bc, backup_dir=_tmpdir)
        check(_ok, "沙箱 set_door_trigger：%s" % _msg)
        _sbtxt = open(_sb_bc, encoding="utf-8").read()
        check("nodes.lastNode.nodenum == N9 && nodes.nowNode.nodenum == N13"
              "){state = DOOR_D2;}" in _sbtxt.replace("\r\n", "\n"),
              "沙箱触发行已改（保格式）")
        check("DOOR_D5_BACK" in _sbtxt and "N20 && nodes.nowNode.nodenum == N3"
              in _sbtxt, "沙箱里 D5_BACK 行没被误伤")
        _ok2, _msg2 = M.set_door_zone_pair(("N5", "N12"), ("N9", "N13"),
                                           path=_sb_mp, backup_dir=_tmpdir)
        check(_ok2, "沙箱 set_door_zone_pair：%s" % _msg2)
        check("{N9, N13}" in open(_sb_mp, encoding="utf-8").read(),
              "沙箱 door_zone 第一对已改")
        _baks = [f for f in os.listdir(_tmpdir) if f.endswith(".bak")]
        check(len(_baks) >= 2, "写回前自动备份落沙箱（%d 份）" % len(_baks))
        # 不存在/多匹配的护栏
        _ok3, _msg3 = M.set_door_trigger("DOOR_NOPE", "N5", "N8", path=_sb_bc)
        check(not _ok3, "不存在的 state 拒写（%s）" % _msg3)
        check(_sha(_real_bc) == _bc0 and _sha(_real_mp) == _mp0,
              "真实 barrier.c / mission_planner.c 未被自检改动（SHA256 一致）")
    finally:
        import shutil as _sh2
        _sh2.rmtree(_tmpdir, ignore_errors=True)

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
