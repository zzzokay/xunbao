#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整推演 D4 黑灯 (DOOR_D4_BACK) 的路线生成逻辑
"""

# 节点映射
NODE_MAP = {
    'N3': 10, 'N4': 11, 'N5': 12, 'N8': 19, 'N10': 24,
    'P1': 1, 'P2': 7, 'P3': 9, 'P4': 14, 'P5': 46, 'P6': 16
}

print("=" * 80)
print("D4 黑灯完整流程推演")
print("=" * 80)

print("\n【前提条件】")
print("- 第二轮回家，从东区回来")
print("- lastNode = N8, nowNode = N3 (正在看 D4 门)")
print("- D4 门是黑灯 (door_pass[2] = NO_PASS = 3)")
print()

print("=" * 80)
print("【步骤1: door() 函数判定】")
print("=" * 80)
print("""
barrier.c:1485:
  else if(nodes.lastNode.nodenum == N8 && nodes.nowNode.nodenum == N3)
      state = DOOR_D4_BACK;

触发 DOOR_D4_BACK 分支
""")

print("=" * 80)
print("【步骤2: 读取门状态】")
print("=" * 80)
print("""
barrier.c:1653:
  door_pass[2] = pass_state;  // 读取 D4 门颜色

假设门状态:
  door_pass[0] = ONE_WAY_PASS (D2 蓝灯)
  door_pass[1] = NO_PASS (D3 黑灯)
  door_pass[2] = NO_PASS (D4 黑灯)
  door_pass[3] = 0 (D5 未读)
""")

print("=" * 80)
print("【步骤3: 执行 door_pass[2] == NO_PASS 分支】")
print("=" * 80)
print("""
barrier.c:1667-1680:

  door_set_pass_node(N8, N5, DOOR_LEN_N5N8, SPEED3);  // 设置 N8->N5 可通行
  door_set_pass_node(N5, N8, DOOR_LEN_N5N8, SPEED3);  // 设置 N5->N8 可通行

  nodes.nowNode = door_retreat(N8, N5, 75);  // 后退 75cm

  door_retreat() 内部:
    1. 后退 75cm
    2. 读取 N8->N5 边: idx = getNextConnectNode(N8, N5)
    3. newNode = Node[idx]
       newNode.nodenum = N5
       newNode.angle = -145°
       newNode.step = 85
    4. 转向 -145°
    5. return newNode

  执行后状态:
    nodes.lastNode.nodenum = N8 (保持不变)
    nodes.nowNode.nodenum = N5 (目标节点)
    nodes.nowNode.angle = -145°
    nodes.nowNode.step = 85
    nodes.nowNode.function = NONE

  nodes.nowNode.function = NONE;
  cross_event |= CROSS_EVENT_DOOR;
  update_route_by_door_4();  // 生成新路线
""")

print("=" * 80)
print("【步骤4: update_route_by_door_4() 生成路线】")
print("=" * 80)
print("""
mission_planner.c:349-372:

#if USE_PLANNER_ROUTE
    (void)plan_after_return_door(0xFF);  // 调用规划器
    return;
#endif

进入 plan_after_return_door(0xFF):
""")

print("=" * 80)
print("【步骤5: plan_after_return_door(0xFF) 执行】")
print("=" * 80)
print("""
mission_planner.c:97-153:

假设 treasure = 3 (宝物在 P3)

wp[n++] = nodes.nowNode.nodenum;  // wp[0] = N5

检查门状态:
  door_pass[0] == CAN_PASS? NO (是 ONE_WAY_PASS)
  door_pass[1] == CAN_PASS? NO (是 NO_PASS)
  door_pass[2] == CAN_PASS? NO (是 NO_PASS)

  door_pass[0] == ONE_WAY_PASS? YES! ✓

执行:
  wp[n++] = N10;  // wp[1] = N10
  if (after_door != 0xFF)  // after_door = 0xFF
      wp[n++] = after_door;
  else
      wp[n++] = N3;  // wp[2] = N3

添加宝物和终点:
  if (treasure != 5 && treasure != 6)
      wp[n++] = target;  // wp[3] = P3
  wp[n++] = P2;  // wp[4] = P2

最终 wp[] = {N5, N10, N3, P3, P2}
""")

print("=" * 80)
print("【步骤6: nav_build_route() 生成实际路线】")
print("=" * 80)
print("""
调用: plan_route_at(0, wp, 5)
  → nav_build_route(route, sizeof(route), wp, 5)

输入必经点: N5 → N10 → N3 → P3 → P2

最短路算法会生成:
  从 N5 到 N10 的最短路径
  + 从 N10 到 N3 的最短路径
  + 从 N3 到 P3 的最短路径
  + 从 P3 到 P2 的最短路径

关键问题: N5 到 N10 的最短路径是什么？

可能的路径:
  选项1: N5 → N4 → N3 → N10
  选项2: N5 → N12 → N10
  选项3: N5 → N8 → N10  ← 如果选这条就有问题！

检查边权重和是否存在:
  N5 → N4: 存在 (map_message.c:62, step=84)
  N5 → N8: 存在 (map_message.c:64, step=85, 但 function=DOOR)
  N5 → N12: 存在 (map_message.c:65, step=110, 但 function=DOOR)

如果最短路算法选择了 N5 → N8 → N10，则:
  route[] = {N4, N3, N10, ..., P3, N3, ..., P2, 0xFF}
         或 {N8, N10, N3, P3, ..., 0xFF}  ← 问题在这！
""")

print("=" * 80)
print("【步骤7: Nav_PostProcess() 设置 nextNode】")
print("=" * 80)
print("""
map.c:483-490:

cross_event &= ~CROSS_EVENT_DOOR;
if (route[map.point] != 0xFF)
    nodes.nextNode = Node[getNextConnectNode(nodes.nowNode.nodenum, route[map.point])];
map.point++;

此时:
  nodes.nowNode.nodenum = N5
  map.point = 0
  route[0] = ???

如果 route[0] = N8:
  nodes.nextNode = Node[getNextConnectNode(N5, N8)]
  → 找到 N5→N8 边
  → nodes.nextNode.nodenum = N8 !!!

这就形成了 N5 → N8 的路径！
""")

print("=" * 80)
print("【步骤8: Navigation() 继续执行】")
print("=" * 80)
print("""
Nav_PostProcess() 后，继续 Navigation() 循环:

状态:
  lastNode = N8
  nowNode = N5 (目标)
  nextNode = N8 (!!!)
  当前角度 = -145° (door_retreat 转的)

开始从当前位置走向 N5:
  - 距离 85cm
  - 到达 N5 时触发 CROSS_EVENT_ARRIVED
  - 调用 Nav_TurnAndAdvance()

Nav_TurnAndAdvance():
  到达 N5，需要转向 nextNode = N8
  N8 的角度 = ANGLE_N8N5 的反向 = 35° (180 - (-145))

  当前角度 = -145°
  目标角度 = 35°
  need2turn(-145°, 35°) = 180° !!!

  因为角度差 = 180°，触发大角度转弯
  → 转 180°！
""")

print("\n" + "=" * 80)
print("【结论】")
print("=" * 80)
print("""
问题根源:
  nav_build_route() 生成 N5 → N10 最短路时，选择了 N5 → N8 → N10

原因可能:
  1. N5 → N8 边虽然是 DOOR，但已被 door_set_pass_node() 设置为可通行
  2. 最短路算法认为 N5 → N8 → N10 比 N5 → N4 → N3 → N10 短
  3. route[0] = N8，导致 nextNode 指向 N8
  4. 从 N5 到 N8 需要转 180°

解决方案:
  1. 检查 nav_build_route() 是否正确避免回头路
  2. 检查 N5 → N8 边的权重是否过低
  3. 或者在 plan_after_return_door() 中不使用 N10 作为中间点
  4. 直接生成 wp[] = {N5, N4, N3, P3, P2}
""")

print("\n" + "=" * 80)
