#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新分析 N8->N5 转180度问题
"""

print("=" * 80)
print("重新分析 N8->N5->N4 转向问题")
print("=" * 80)

print("\n【场景回顾】")
print("D4 门黑灯，从 N8 后退到 N5，期望转向 N4，但实际转了 180 度")

print("\n" + "=" * 80)
print("【执行流程分解】")
print("=" * 80)

print("""
1. door() 检测到 DOOR_D4_BACK (barrier.c:1652)
   条件: lastNode == N8 && nowNode == N3
   处理: D4 门黑灯 (door_pass[2] == NO_PASS)

2. 执行 door_retreat(N8, N5, 75) (barrier.c:1676)
   - 后退 75cm
   - 读取 N8->N5 边: angle = -145°
   - 转向 -145° (朝向 N5 方向)
   - 返回 N8->N5 的 NODE 信息

3. 设置 nodes.nowNode = 返回的 NODE
   - nodes.lastNode = N8 (保持不变)
   - nodes.nowNode = N5 (目标节点)
   - nodes.nowNode.angle = -145°
   - nodes.nowNode.step = 85cm (DOOR_LEN_N5N8/2)
   - nodes.nowNode.flag = STOPTURN | CLEFT
   - nodes.nowNode.function = NONE (被设置)

4. 调用 update_route_by_door_4()
   设置 route[0] = N4 (下一个目标)

5. cross_event |= CROSS_EVENT_DOOR
   触发 Nav_PostProcess() (map.c:483-490)

6. Nav_PostProcess() 执行:
   - 清除 CROSS_EVENT_DOOR
   - 读取 route[map.point] = route[0] = N4
   - nodes.nextNode = Node[getNextConnectNode(N5, N4)]
   - map.point++
""")

print("\n" + "=" * 80)
print("【关键问题点】")
print("=" * 80)

print("""
问题1: door() 函数在哪里被调用？
   答: 从 map.c:575 map_function(nodes.nowNode.function)
       当 nodes.nowNode.function == DOOR 时调用

问题2: DOOR_D4_BACK 的触发条件
   barrier.c:1485:
   else if(nodes.lastNode.nodenum == N8 && nodes.nowNode.nodenum == N3)
       state = DOOR_D4_BACK;

   注意: 这是 lastNode=N8, nowNode=N3 时触发
   但代码处理的是退到 N5！

问题3: door_retreat(N8, N5, 75) 后的状态
   - 物理位置: 从 N8 门区后退了 75cm
   - 朝向角度: -145° (N8->N5 方向)
   - nodes.nowNode = N8->N5 边的信息
   - nodes.lastNode = 还是 N8

问题4: 后续 Navigation 如何处理？
   从 door() 返回后，cross_event 有 CROSS_EVENT_DOOR 标志
   Navigation() 会调用 Nav_PostProcess()

   Nav_PostProcess() 设置 nextNode = N4
   然后继续 Navigation() 的正常流程

问题5: 从 N8 走到 N5 的过程
   - 当前角度: -145° (door_retreat 转的)
   - 目标节点: N5
   - nowNode.step = 85cm
   - 到达 N5 时触发 CROSS_EVENT_ARRIVED
   - 调用 Nav_TurnAndAdvance()
""")

print("\n" + "=" * 80)
print("【Nav_TurnAndAdvance 转向逻辑】")
print("=" * 80)

print("""
map.c:408-481 Nav_TurnAndAdvance():

到达 N5 时的状态:
  - lastNode = N8
  - nowNode = N5 (刚到达)
  - nextNode = N4 (从 route 读取)
  - 当前角度: -145° (从 N8 走过来的角度)

转向判断 (map.c:444-454):
  条件: (nodes.nowNode.flag & STOPTURN
         && fabsf(need2turn(getAngleZ(), nodes.nextNode.angle)) > 30.0f)
         || fabsf(need2turn(nodes.nowNode.angle, nodes.nextNode.angle)) >= 90.0f

  N8->N5 边的 flag 包含 STOPTURN
  nextNode.angle = N5->N4 边的角度

  问题: N5->N4 的角度是多少？
""")

print("\n" + "=" * 80)
print("【查找 N5->N4 边的角度】")
print("=" * 80)

print("""
从 map_message.c:62 查找:
  { N5, N4, RIGHT_LINE|Temp_L|MUL2SING, 0, 84, SPEED3, NONE }

  N5->N4 边的角度 = 0°

所以转向逻辑:
  当前角度: -145°
  目标角度: 0°
  need2turn(-145°, 0°) = 145°

  因为 > 30°，触发 STOPTURN 原地转弯

  执行:
    1. 前进补偿: GetForwardDistanceBeforeTurn(N8, N5, N4) = 40cm
    2. 原地转弯: Chassis_Turn_By_StopGyro_Blocking(0°, -145°, 30.0f)
       需要转 145°
""")

print("\n" + "=" * 80)
print("【为什么看起来转了 180°？】")
print("=" * 80)

print("""
可能的原因:

1. GetForwardDistanceBeforeTurn(N8, N5, N4) = 40
   返回值是 40cm (map.c:228)
   但这个值可能不对！

   - 从 N8 到 N5 的距离是 85cm (DOOR_LEN_N5N8/2)
   - 到达 N5 后再前进 40cm
   - 可能已经偏离了正常位置

2. N5->N4 的角度计算
   - N5->N4 边的角度是 0°
   - 但 nodes.nextNode 是通过 getNextConnectNode(N5, N4) 获取的
   - 需要确认 nextNode.angle 是否正确

3. 转向方向判断
   - need2turn(-145°, 0°) = 145°
   - Chassis_Turn_By_StopGyro_Blocking 应该转 145°
   - 如果转向逻辑有误，可能转成了 -215° (360° - 145° = 215°)
   - 看起来就像转了 180° (实际是转错了方向)

4. 角度 normalization
   - -145° + 145° = 0° (正确)
   - 但如果中间有角度归一化问题，可能导致转向异常
""")

print("\n" + "=" * 80)
print("【真正的问题】")
print("=" * 80)

print("""
我怀疑问题在于:

1. GetForwardDistanceBeforeTurn(N8, N5, N4) 返回 40
   这个值太大了！

   从 N8 后退 75cm 后开始走向 N5
   走 85cm 到达 N5
   然后又前进 40cm

   --> 可能已经过了 N5 节点，位置偏移导致后续转向混乱

2. 或者 door_retreat 后退的距离和位置不对
   导致到达 N5 时的判断出问题

建议修改:
  map.c:228 将 return 40 改小
  if (last == N8 && now == N5 && next == N4) return 10;  // 改成 10 或更小
""")

print("\n" + "=" * 80)
print("【推荐修改】")
print("=" * 80)

print("""
修改 map.c:228:
  if (last == N8 && now == N5 && next == N4) return 40;
                                                   ↓
  if (last == N8 && now == N5 && next == N4) return 10;

或者直接改成 0:
  if (last == N8 && now == N5 && next == N4) return 0;

原因:
  - 从门区退回后的位置本身就不稳定
  - 不需要太多补偿距离
  - 减少补偿可以避免位置偏移
""")

print("\n" + "=" * 80)
