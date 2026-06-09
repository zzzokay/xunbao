# 方案：将 D1~D5 加入地图节点

## Context

当前门检测（D2~D5）的处理方式存在架构问题：门作为路径中间的"埋伏"（不在节点表里），`door()` 被迫手动构造 `nodesr.nowNode`、`step`、`flag`、`speed` 等导航参数，职责边界模糊。用户希望将 D1~D5 正式加入 `map_message.c` 的节点表，让门检测回归纯粹的"读颜色 → 写 route[]"职责，节点切换由 map.c 的 `Cross()` 循环统一处理。

## 地图关系

```
N6 → C1 → D1 → N13     （原 N6 → C1 → N13，中途加 D1）
N5 → D2 → N12          （原 N5 → N12，D2 替换 DOOR 函数）
N5 → D3 → N8           （原 N5 → N8，D3 替换 DOOR 函数）
N3 → D4 → N8           （原 N3 → N8，D4 替换 DOOR 函数）
N3 → D5 → N10          （原 N3 → N10，D5 替换 DOOR 函数）
```

## 改动清单

### 1. map.h — 添加 D1~D5 枚举

在 `MapNode` 枚举末尾（G1=51 之后）添加：
```c
D1 = 52,  // N6→C1→D1→N13
D2 = 53,  // N5→D2→N12
D3 = 54,  // N5→D3→N8
D4 = 55,  // N3→D4→N8
D5 = 56,  // N3→D5→N10
```
现有枚举值在 G1=51 结束，D1~D5 = 52~56。需同步 `ConnectionNum` 和 `Address` 数组长度（从 52→57）。

### 2. map_message.c — 添加 D 节点到 Node[] 表

每个 D 节点需要：
- 到前一个节点的连接（退回用）
- 到后一个节点的连接（前进用）
- `function = DOOR` 以触发 `door()`

D2 示例：
```c
/*D2 53*/  {N5, ..., step, speed, DOOR},  // 到 N5
           {N12, ..., step, speed, NONE},  // 到 N12
```
其他 D 节点类似。step 写小一点（30~50），依靠节点检测标志位来确认到达。

**需要更新 N3、N5、N6、N8、N10、N12、C1、N13 的连接表**，把原来带 `DOOR` 函数的那条连接替换成指向 D 节点的普通连接。

### 3. map_message.c — 更新 ConnectionNum 和 Address

从 52 个元素扩展到 57 个。Address[57]=126+(各 D 节点的连接数)。

### 4. barrier.c — 简化 door() 状态机

核心变化：`door()` **不再手动构造节点**，只做三件事：
1. 读颜色
2. 写 `route[]`
3. 设 `nodesr.flag |= 0x20/0x80`

删除所有形如：
```c
nodesr.nowNode = Node[getNextConnectNode(...)];
nodesr.nowNode.step = ...;
nodesr.nowNode.flag = ...;
```
改为仅设置 route 和 flag。物理转向（`Chassis_Turn_By_StopGyro_Blocking`）保留。

**D2_RED（示例）**：
```c
// 改前
route[0] = N8;
Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 180, getAngleZ());
nodesr.nowNode = Node[getNextConnectNode(N12, N5)];  // ❌
nodesr.nowNode.step = 70;                            // ❌
nodesr.nowNode.flag = STOPTURN | DRIGHT | DLEFT;     // ❌
nodesr.nowNode.speed = SPEED4;                       // ❌
nodesr.flag |= 0x20;

// 改后
route[0] = N5;       // 退回 N5（D2→N5 由节点表提供连接）
route[1] = 0xFF;     // 路径结束，等待 door() 下次调用再设
Chassis_Turn_By_StopGyro_Blocking(getAngleZ() + 180, getAngleZ());
nodesr.flag |= 0x20;
```

**D2_GREEN（示例）**：
```c
// 改前
nodesr.nowNode = Node[getNextConnectNode(N5, N12)];  // ❌
nodesr.nowNode.flag = DLEFT | DRIGHT | LEFT_LINE;     // ❌
nodesr.nowNode.step = 120;                            // ❌
nodesr.nowNode.speed = SPEED2;                        // ❌
nodesr.nowNode.function = NONE;                       // ❌
update_route_by_QR();
nodesr.flag |= 0x80;

// 改后
update_route_by_QR();    // 由节点表提供 step/flag/speed
nodesr.flag |= 0x80;
```

### 5. 更新 `update_route_for_stage34()` 中的路线

三个分支（flag_line_clue=0/3/4）末尾都有 `...N5, N12, 0xFF`，需改为 `...N5, D2, N12, 0xFF`。

### 6. 其他 route update 函数（如适用）

检查 `update_route_by_QR()`、`update_rout_by_treasure_7/8()` 等函数是否直接引用 N5→N12、N3→N8、N5→N8、N3→N10 等连接。如引用则加入对应的 D 节点。

### 7. map.c — 检查 0x20/0x80 处理

现有两条 handler（line 556-573）已经能以 route[] 驱动导航，不需要修改。为 door() 设置的 flag 能被正常处理。

## 不修改的内容

- `getNextConnectNode()` — 已经泛化，node number 是什么不重要
- `Cross()` 主循环 — 逻辑不变，D 节点只是多了几个中间站
- `Door_ReadColor()` — 刚刚重构完，保持现有设计
- `map_function(DOOR)` case — 继续调 `door()`
- 所有 `doorXroute[]` 数组 — 如果 D 节点提供了到达后续节点的连接，这些数组内容可以不变

## 风险与注意事项

1. **`door()` 状态机与物理位置的关系**：目前 door() 依赖调用次数推进状态，而不管实际物理位置。改成 D 节点后，door() 的调用时机与物理位置同步（到达 D2 才处理 D2）。但状态机的跨状态决策（如"D2黄 → 以后还要看 D5"）仍然需要 static state 变量。

2. **退回路径**：D2_RED 时先退到 N5，再从 N5 走 D3。door() 需要连续两次设 route[]（第一次退回 N5，第二次再去 D3）。需要确认 map.c 的循环能在 N5 停下来再次调 door()。

3. **step 值**：用户说"距离写小一点有节点检测"，所以 step 可以设得保守（30~50），依赖 flag 到达检测而非距离走完。

## 验证

1. 编译通过（MDK-ARM）
2. 正常模式（`DEBUG=0, MAIN_DEBUG=0`）：小车走完整路线，门检测正常
3. 调试模式（`DEBUG=1`）：预设门颜色，遍历所有 12 条路线组合
4. 主要测试场景：
   - D2 绿灯 → 继续到 N12，正常走 QR 规划
   - D2 黄灯 → 到 D5，测试 D5 绿/红分支
   - D2 红灯 → 退回 N5 → D3，测试 D3 绿/红分支
   - D2 红 D3 红 → 到 D4，测试 D4 绿/黄分支
