#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看当前 debug 路线配置
显示从 N8 到 N5 的下一个节点信息
"""

# 节点编号映射（从 map.h MapNode 枚举提取）
NODE_MAP = {
    0: 'S1', 1: 'P1', 2: 'N1', 3: 'B1', 4: 'B2', 5: 'B3',
    6: 'N2', 7: 'P2', 8: 'S2', 9: 'P3', 10: 'N3', 11: 'N4',
    12: 'N5', 13: 'N6', 14: 'P4', 15: 'N7', 16: 'P6', 17: 'B8',
    18: 'B9', 19: 'N8', 20: 'C1', 21: 'C2', 22: 'C3', 23: 'N9',
    24: 'N10', 25: 'C4', 26: 'C5', 27: 'B4', 28: 'B5', 29: 'B6',
    30: 'B7', 31: 'N16', 32: 'N18', 33: 'N19', 34: 'P7', 35: 'N20',
    36: 'N22', 37: 'C6', 38: 'C7', 39: 'C8', 40: 'C9', 41: 'P8',
    42: 'N11', 43: 'G1', 44: 'N12', 45: 'N13', 46: 'P5', 47: 'N14',
    48: 'S3', 49: 'N15', 50: 'S4', 51: 'S5', 52: 'B10', 53: 'B11'
}

def get_node_name(num):
    """获取节点名称"""
    return NODE_MAP.get(num, f'Unknown({num})')

def main():
    print("=" * 70)
    print("当前 DEBUG 路线配置分析")
    print("=" * 70)

    # 从 map.c 第 50 行读取的 debug 路线
    # u8 route[100] = {B9,N7,P6,N7,B8,N9, 0XFF};
    debug_route = [18, 15, 16, 15, 17, 23, 0xFF]  # B9,N7,P6,N7,B8,N9

    print("\n【当前 map.c 中的 DEBUG 路线】")
    print("代码位置: map.c:50")
    print("u8 route[100] = {B9,N7,P6,N7,B8,N9, 0XFF};")
    print()

    route_names = []
    for i, node in enumerate(debug_route):
        if node == 0xFF:
            route_names.append('0xFF(结束)')
            break
        route_names.append(get_node_name(node))

    print("路线序列:")
    print(" -> ".join(route_names))
    print()

    # 查找 N8 和 N5
    N8 = 19
    N5 = 12

    print("=" * 70)
    print("【关于 N8 → N5 的路径】")
    print("=" * 70)

    # 检查当前路线中是否包含 N8 和 N5
    if N8 in debug_route:
        idx = debug_route.index(N8)
        print(f"\n[OK] 当前路线包含 N8 (索引 {idx})")
    else:
        print("\n[NO] 当前路线不包含 N8")

    if N5 in debug_route:
        idx = debug_route.index(N5)
        print(f"[OK] 当前路线包含 N5 (索引 {idx})")
    else:
        print("[NO] 当前路线不包含 N5")

    print("\n" + "=" * 70)
    print("【回程过门场景分析】")
    print("=" * 70)

    print("\n根据 barrier.c door() 函数的状态判定逻辑:")
    print("- 第二轮回程过门时，从 N8 到 N5 的触发条件:")
    print("  if(nodes.lastNode.nodenum == N8 && nodes.nowNode.nodenum == N5)")
    print("  → 这对应 DOOR_D4_BACK 状态（回家过 D4 门）")

    print("\n在 map.c GetForwardDistanceBeforeTurn() 中:")
    print("  if (last == N8 && now == N5 && next == N4) return 36;")
    print("  → N8→N5→N4 这条路径前进 36cm 后原地转弯")

    print("\n" + "=" * 70)
    print("【地图边表中的 N8 → N5 配置】")
    print("=" * 70)

    print("\n从 map_message.c NavEdgeTbl[] 查找 N8→N5 边:")
    print("  { N8, N5, STOPTURN|CLEFT, ANGLE_N8N5, DOOR_LEN_N5N8/2, SPEED0, DOOR }")
    print()
    print("边属性:")
    print(f"  - from: N8 (节点 {N8})")
    print(f"  - to: N5 (节点 {N5})")
    print("  - flag: STOPTURN | CLEFT (原地转弯 + 左转)")
    print("  - angle: ANGLE_N8N5 = -145° (宏定义)")
    print("  - step: DOOR_LEN_N5N8/2 (门段长度的一半)")
    print("  - speed: SPEED0")
    print("  - function: DOOR (红绿灯门)")

    print("\n从 config.h 查看门段长度:")
    print("  #define DOOR_LEN_N5N8   170   (学校场地)")
    print("  → DOOR_LEN_N5N8/2 = 85 cm")

    print("\n" + "=" * 70)
    print("【回答你的问题】")
    print("=" * 70)

    print("\n问: 回来过门时 N8 到 N5 下一个节点是什么？")
    print()
    print("答: 根据 map.c GetForwardDistanceBeforeTurn() 和实际路线规划：")
    print()
    print("  N8 → N5 → N4")
    print("       ↑     ↑")
    print("     当前   下一个节点")
    print()
    print("  - lastNode: N8")
    print("  - nowNode: N5 (当前目标节点)")
    print("  - nextNode: N4 (下一个节点)")
    print()
    print("  执行动作:")
    print("  1. 从 N8 沿门段巡线/陀螺仪走 85cm 到达 N5")
    print("  2. 到达 N5 后前进 36cm")
    print("  3. 原地转弯朝向 N4")
    print("  4. 继续前往 N4")

    print("\n" + "=" * 70)
    print("【第二轮路线规划提示】")
    print("=" * 70)

    print("\n第二轮回家路线通常是:")
    print("  ... → N8 → N5 → N4 → N3 → P3 (回家)")
    print()
    print("或根据门的颜色走不同分支:")
    print("  - D4 门绿灯: N8 → N3 → P3")
    print("  - D4 门黑灯: N8 → N5 → N4 → N3 → P3")

    print("\n提示: 第二轮路线由 get_newroute() 和门逻辑动态生成")
    print("      具体路径取决于第一轮记录的门颜色状态")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
