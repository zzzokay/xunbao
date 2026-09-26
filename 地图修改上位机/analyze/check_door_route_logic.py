#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 DOOR_D4_BACK 场景下的路线生成逻辑
分析 plan_after_return_door(0xFF) 在不同门状态下的行为
"""

print("=" * 80)
print("D4 回程门 (DOOR_D4_BACK) 路线生成分析")
print("=" * 80)

print("\n【触发条件】")
print("lastNode == N8 && nowNode == N3")
print("即：从 N8 到 N3，看 D4 门")

print("\n【door_pass[] 数组说明】")
print("door_pass[0] = D2 门状态")
print("door_pass[1] = D3 门状态")
print("door_pass[2] = D4 门状态")
print("door_pass[3] = D5 门状态")
print()
print("值: CAN_PASS=1 (绿灯), ONE_WAY_PASS=2 (蓝灯), NO_PASS=3 (黑灯)")

print("\n" + "=" * 80)
print("【plan_after_return_door(0xFF) 逻辑】")
print("=" * 80)

print("""
从 mission_planner.c:97-153 分析:

wp[n++] = nodes.nowNode.nodenum;  // 起点是当前节点 N5 (door_retreat 返回后)

if (door_pass[0] == CAN_PASS)              // D2 绿灯
    wp[n++] = N5;

else if (door_pass[1] == CAN_PASS)         // D3 绿灯
    wp[n++] = N8;
    wp[n++] = N5;

else if (door_pass[2] == CAN_PASS)         // D4 绿灯
    wp[n++] = N8;
    wp[n++] = N3;

else if (door_pass[0] == ONE_WAY_PASS ||   // D2/D3/D4 任一蓝灯
         door_pass[1] == ONE_WAY_PASS ||
         door_pass[2] == ONE_WAY_PASS)
    wp[n++] = N10;
    if (after_door != 0xFF)
        wp[n++] = after_door;
    else
        wp[n++] = N3;

else                                        // 所有门都是黑灯
    CarBrake_Stop();  // 停车！
    return 0;
""")

print("\n" + "=" * 80)
print("【问题场景】")
print("=" * 80)

print("""
DOOR_D4_BACK 触发时，已经：
  - D2 门看过了 (可能绿/蓝/黑)
  - D3 门看过了 (可能绿/蓝/黑)
  - D4 门正在看 (当前是黑灯)

如果 door_pass[] = {NO_PASS, NO_PASS, NO_PASS, 0, 0}
即 D2黑, D3黑, D4黑

则 plan_after_return_door() 会：
  1. 检查 door_pass[0] == CAN_PASS? NO
  2. 检查 door_pass[1] == CAN_PASS? NO
  3. 检查 door_pass[2] == CAN_PASS? NO
  4. 检查是否有单向通行? NO
  5. 执行 else 分支 -> CarBrake_Stop()  停车！
""")

print("\n" + "=" * 80)
print("【实际场景分析】")
print("=" * 80)

print("""
根据 barrier.c:1667-1680 DOOR_D4_BACK NO_PASS 处理:

1. door_set_pass_node(N8, N5, ...)  // 设置 N8->N5 可通行
2. door_set_pass_node(N5, N8, ...)  // 设置 N5->N8 可通行
3. nodes.nowNode = door_retreat(N8, N5, 75)  // 后退到 N5
4. nodes.nowNode.function = NONE
5. cross_event |= CROSS_EVENT_DOOR
6. update_route_by_door_4()  // 调用路线规划

update_route_by_door_4() 调用:
  plan_after_return_door(0xFF)

此时 nodes.nowNode.nodenum = N5 (door_retreat 返回的)

所以 wp[0] = N5 (起点)

接下来根据门状态生成路线...
""")

print("\n" + "=" * 80)
print("【可能的错误】")
print("=" * 80)

print("""
问题1: nodes.nowNode.nodenum 是什么？
  door_retreat(N8, N5, 75) 返回的是 N8->N5 边的信息
  但 nodes.nowNode.nodenum 是目标节点编号 = N5

  所以 wp[0] = N5 是对的

问题2: 如果 D2/D3 都不是绿灯会怎样？
  假设 door_pass[] = {ONE_WAY_PASS, NO_PASS, NO_PASS, ...}

  满足 door_pass[0] == ONE_WAY_PASS 条件
  执行:
    wp[n++] = N10;
    wp[n++] = N3;  (because after_door == 0xFF)

  结果: wp[] = {N5, N10, N3, target, P2}

  这会生成: N5 -> N10 -> N3 -> ... 的路线

  但 N5 -> N10 没有直接的边！会走最短路算法
  可能生成: N5 -> N4 -> N3 -> N10 -> ...
  或者: N5 -> N12 -> N10 -> ...

问题3: 如果生成的路线有问题？
  最短路算法 nav_build_route() 可能生成:
    N5 -> N8 -> N10 -> N3 -> ...

  这就有 N5 -> N8 的边！

  如果 nodes.nextNode 被设置为 N8，
  那就变成 N5 -> N8 的循环了！
""")

print("\n" + "=" * 80)
print("【关键检查点】")
print("=" * 80)

print("""
需要检查:

1. door_retreat(N8, N5, 75) 返回后:
   - nodes.lastNode = ? (应该还是 N8)
   - nodes.nowNode = ? (应该是 N5)
   - nodes.nextNode = ? (还未设置，或者是旧值)

2. update_route_by_door_4() 生成的 route[] 是什么？
   第一个元素是什么？

3. Nav_PostProcess() 会设置:
   nodes.nextNode = Node[getNextConnectNode(N5, route[0])]

   如果 route[0] = N8，就会找 N5->N8 边
   但这是错的！应该是 N5->N4

4. 可能的原因:
   - plan_after_return_door() 生成的 wp[] 不对
   - nav_build_route() 生成的路线包含回头路
   - route[] 被错误设置
""")

print("\n" + "=" * 80)
print("【建议调试】")
print("=" * 80)

print("""
1. 在 update_route_by_door_4() 开始打印:
   printf("D4_BACK: treasure=%d, doors=[%d,%d,%d]\\n",
          treasure, door_pass[0], door_pass[1], door_pass[2]);

2. 在 plan_after_return_door() 中打印生成的 wp[]:
   printf("wp: ");
   for (i = 0; i < n; i++) printf("%d ", wp[i]);
   printf("\\n");

3. 在 nav_build_route() 后打印生成的 route[]:
   printf("route: ");
   for (i = 0; i < 10 && route[i] != 0xFF; i++) printf("%d ", route[i]);
   printf("\\n");

4. 在 Nav_PostProcess() 中打印:
   printf("PostProc: nowNode=%d, route[%d]=%d, nextNode=%d\\n",
          nodes.nowNode.nodenum, map.point, route[map.point],
          nodes.nextNode.nodenum);
""")

print("\n" + "=" * 80)
