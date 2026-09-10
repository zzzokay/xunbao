#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析 N8→N5 转180度问题
"""

print("=" * 80)
print("N8 → N5 转180度问题分析")
print("=" * 80)

print("\n【问题描述】")
print("现象: 回家过门时，从 N8 到达 N5 后，车转了 180 度而不是正常转向 N4")
print()

print("=" * 80)
print("【问题根源分析】")
print("=" * 80)

print("\n1. door() 函数处理 DOOR_D4_BACK (barrier.c:1652-1681)")
print("-" * 80)

print("""
当 D4 门是黑灯时（door_pass[2] == NO_PASS）：

代码执行流程 (barrier.c:1667-1680):
  1. door_set_pass_node(N8, N5, DOOR_LEN_N5N8, SPEED3);  // 修改 N8→N5 边
  2. door_set_pass_node(N5, N8, DOOR_LEN_N5N8, SPEED3);  // 修改 N5→N8 边
  3. nodes.nowNode = door_retreat(N8, N5, DOOR_RETREAT_N8N5);  // 后退并转向
  4. nodes.nowNode.function = NONE;
  5. cross_event |= CROSS_EVENT_DOOR;
  6. update_route_by_door_4();  // 设置新路线
""")

print("\n2. door_retreat() 函数的问题 (barrier.c:1465-1476)")
print("-" * 80)

print("""
door_retreat(N8, N5, DOOR_RETREAT_N8N5) 执行:
  1. 后退 DOOR_RETREAT_N8N5 = 75cm (config.h:84)
  2. idx = getNextConnectNode(N8, N5);  // 查找 N8→N5 边
  3. NODE newNode = Node[idx];          // 读取 N8→N5 的节点信息
  4. Chassis_Turn_By_StopGyro_Blocking(newNode.angle, getAngleZ(), 30.0f);
     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
     【这里是问题！】转向 newNode.angle
  5. return newNode;
""")

print("\n3. N8→N5 边的角度配置 (map_message.c:91)")
print("-" * 80)

print("""
{ N8, N5, STOPTURN|CLEFT, ANGLE_N8N5, DOOR_LEN_N5N8/2, SPEED0, DOOR }

关键参数:
  - angle: ANGLE_N8N5 = -145° (config.h:105)
  - 这是从 N8 前往 N5 时的朝向角度
""")

print("\n4. 问题分析")
print("-" * 80)

print("""
【错误流程】
  当前位置: 在 N8 门口，刚看完 D4 门（黑灯）
  期望行为: 后退，然后转向去 N5

  实际执行:
    1. door_retreat(N8, N5, 75) 被调用
    2. 后退 75cm ✓
    3. 读取 N8→N5 边: newNode.angle = -145°
    4. 转向 -145°  ← 【这是问题！】
       ▶ -145° 是从 N8 到 N5 的前进方向
       ▶ 但此时车已经在 N8，还没到 N5
       ▶ 转向 -145° 就朝向了 N5
    5. nodes.nowNode = newNode (N8→N5 边信息)
    6. 执行 Nav_TurnAndAdvance()

  Navigation 继续:
    - nowNode = N5 (目标是 N5)
    - nextNode = N4 (从 route 读取)
    - 到达 N5 后，需要转向 N4
    - N4 相对于 N5 的角度: 0° (map_message.c:58)
    - 当前角度: -145° (刚才 door_retreat 转的)
    - 需要转的角度: need2turn(-145°, 0°) = 145°
    - 但是因为 N8→N5 边有 STOPTURN 标志
    - 触发原地转弯条件 (map.c:444-446):
       fabsf(need2turn(getAngleZ(), nodes.nextNode.angle)) > 30°
    - 执行原地转弯，但可能转了接近180°！
""")

print("\n5. 根本原因")
print("-" * 80)

print("""
【核心问题】
  door_retreat() 函数在后退后，直接转向 newNode.angle

  ▶ newNode.angle 是从 a 到 b 的【边的角度】
  ▶ 但 door_retreat 是在门口后退，还没开始走这条边
  ▶ 直接转向边的角度，导致后续导航判断出现大角度偏差
""")

print("\n" + "=" * 80)
print("【解决方案】")
print("=" * 80)

print("""
方案1: door_retreat() 后退时不转向，让 Navigation 自己处理转向
----------------------------------------------------------------------
修改 barrier.c door_retreat() 函数:

static NODE door_retreat(uint8_t a, uint8_t b, float dis)
{
    uint8_t idx;
    Chassis_DriveDistance_Blocking(is_Gyro, dis, -SPEED2, getAngleZ(), 0);
    idx = getNextConnectNode(a, b);
    if (idx == ROUTE_NOT_FOUND) return (NODE){0};
    NODE newNode = Node[idx];
    Chassis_Brake();
    // 【删除这行】Chassis_Turn_By_StopGyro_Blocking(newNode.angle, getAngleZ(), 30.0f);
    return newNode;
}

优点: 让导航系统统一处理转向逻辑，不会产生角度冲突
缺点: 需要确保 Navigation 转向逻辑正确


方案2: 修改 GetForwardDistanceBeforeTurn 的补偿距离
----------------------------------------------------------------------
减少 N8→N5→N4 的前进补偿距离，避免过度前进导致的角度混乱

map.c:228 修改:
  if (last == N8 && now == N5 && next == N4) return 40;  // 改小
                                                      ↓
  if (last == N8 && now == N5 && next == N4) return 0;   // 到达就转


方案3: 修改 N8→N5 边的 flag，去掉 STOPTURN
----------------------------------------------------------------------
map_message.c:91:
  { N8, N5, STOPTURN|CLEFT, ANGLE_N8N5, DOOR_LEN_N5N8/2, SPEED0, DOOR }
                ↓
  { N8, N5, CLEFT, ANGLE_N8N5, DOOR_LEN_N5N8/2, SPEED0, DOOR }

让车用陀螺仪边走边转，而不是原地转弯
""")

print("\n" + "=" * 80)
print("【推荐方案】")
print("=" * 80)

print("""
推荐使用【方案1】: 删除 door_retreat() 中的转向

理由:
  1. door_retreat() 只负责后退到安全位置
  2. 转向交给 Navigation 的统一逻辑处理
  3. 避免在两个地方都处理转向导致的角度冲突
  4. 其他门的 retreat 逻辑也可以统一简化

修改位置: barrier.c:1474
删除: Chassis_Turn_By_StopGyro_Blocking(newNode.angle, getAngleZ(), 30.0f);
""")

print("\n" + "=" * 80)
