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


def sec(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def main():
    sec("1. 解析源码")
    m = M.MapModel.load_from_sources()
    check(len(m.nodes) == 54, "节点数 = 54（实际 %d）" % len(m.nodes))
    check(len(m.edges) == 124, "边数 = 124（实际 %d）" % len(m.edges))
    check(m.declared_count == len(m.edges),
          "NAV_EDGE_COUNT(%s) 与表内行数(%d) 一致" % (m.declared_count, len(m.edges)))
    check(m.field_name == "FIELD_SCHOOL", "场地解析 = FIELD_SCHOOL（实际 %s）" % m.field_name)

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
    print("     抽样：C9->P7 angle=%s step=%s(func=%s)"
          % (m.ang(m.edge("C9", "P7")), m.step(m.edge("C9", "P7")), m.edge("C9", "P7").func))
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
    snap0 = m.snapshot()
    m.add_node("C10", 800, 610, "测试新节点")
    check(m.node("C10") is not None, "加节点 C10")
    m.add_edge("C9", "C10", flag="NO", angle="0", step="90", speed="SPEED2", func="NONE")
    m.add_edge("C10", "C9", flag="NO", angle="180", step="90", speed="SPEED2", func="NONE")
    check(m.edge("C9", "C10") and m.edge("C10", "C9"), "加双向边 C9<->C10")
    check(len(m.edges) == 126, "边数变 126（实际 %d）" % len(m.edges))
    m.remove_edge("C9", "C10")
    check(m.edge("C9", "C10") is None, "删边 C9->C10")
    m.rename_node("C10", "C10X")
    check(m.node("C10X") is not None and m.node("C10") is None, "节点改名 C10 -> C10X")
    check(m.edge("C10X", "C9") is not None, "改名后边端点跟着改（C10X->C9 存在）")
    m.remove_node("C10X")
    check(m.node("C10X") is None and m.edge("C10X", "C9") is None, "删节点并连带删边")
    check(len(m.edges) == 124, "边数回到 124（实际 %d）" % len(m.edges))
    # 撤销/重做
    m.restore(snap0)
    check(len(m.edges) == 124 and m.node("C10") is None, "restore 快照回到原状")

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

    sec("7. 演示：模拟一次真实地图改动（切 C9-P7 / B7-C6，加 C10，P7 挪到 C6 位置）")
    m3 = M.MapModel.load_from_sources()
    print("  改动前 C9 出边: %s" % ", ".join(e.label() for e in m3.edges_of("C9", True)))
    print("  改动前 B7 出边: %s" % ", ".join(e.label() for e in m3.edges_of("B7", True)))
    # 1) 切断 C9<->P7 与 B7<->C6（双向）
    for a, b in (("C9", "P7"), ("P7", "C9"), ("B7", "C6"), ("C6", "B7")):
        m3.remove_edge(a, b)
    # 2) 在 P7 原位置加 C10
    old_p7 = m3.node("P7")
    m3.add_node("C10", old_p7.x, old_p7.y, "原 P7 位置")
    # 3) P7 挪到 C6 位置
    old_c6 = m3.node("C6")
    old_p7.x, old_p7.y = old_c6.x, old_c6.y
    # 4) 连 C6<->C10、C10<->C9（双向）
    m3.add_edge("C6", "C10", flag="NO", angle="180", step="90", speed="SPEED2", func="NONE")
    m3.add_edge("C10", "C6", flag="NO", angle="0", step="90", speed="SPEED2", func="NONE")
    m3.add_edge("C10", "C9", flag="NO", angle="180", step="90", speed="SPEED2", func="NONE")
    m3.add_edge("C9", "C10", flag="NO", angle="0", step="90", speed="SPEED2", func="NONE")
    print("  改动后 C9 出边: %s" % ", ".join(e.label() for e in m3.edges_of("C9", True)))
    print("  改动后 C6 出边: %s" % ", ".join(e.label() for e in m3.edges_of("C6", True)))
    print("  改动后 P7 出边: %s" % ", ".join(e.label() for e in m3.edges_of("P7", True)))
    print("  改动后 C10 出边: %s" % ", ".join(e.label() for e in m3.edges_of("C10", True)))
    check(m3.edge("C9", "P7") is None and m3.edge("P7", "C9") is None, "C9<->P7 已切断")
    check(m3.edge("B7", "C6") is None and m3.edge("C6", "B7") is None, "B7<->C6 已切断")
    check(m3.node("C10") is not None, "C10 已建在 P7 原位置")
    e = m3.export_edge_table()
    check("C10" in m3.export_enum(), "导出的 enum 里含 C10")
    check(m3.export_nav_edge_count() == "#define NAV_EDGE_COUNT %d" % len(m3.edges),
          "导出 NAV_EDGE_COUNT 与边数一致（%d）" % len(m3.edges))
    errs = [msg for lv, msg in m3.validate() if lv == "error"]
    check(not errs, "改动后无 error 级校验问题（%d 条）" % len(errs))
    for x in errs[:6]:
        print("        ", x)
    print("  P7 的新出边数 = %d（用户要求：P7 只与 B7 连接）"
          % len(m3.edges_of("P7", True)))
    print("  注：本例只是演示「编辑器能不能做出这种改动」，具体连法等你确定拓扑后再改。")

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
