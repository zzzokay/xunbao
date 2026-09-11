# 方案：给规划器加"运行时门边权限"，把门回程穷举路线换成最短路

> 状态：**待实施**（阶段 A 已完成：`d44f954` 落库 → `e62d21f` 零风险去重 → `a7d1750` 删废值；见 `项目讲解文档/README.md` 2026-09-11 晚）
> 证据：本文 §2 的 12/12 复现结论由 `scripts/validate/_weight_calib.py` 的 Python 图镜像实测得出（临时探针脚本已删，可照 §2.3 复跑）

## Context

`Mission/mission_planner.c` 里仍有三处**穷举路线**：

| 位置 | 内容 | 规模 |
|------|------|------|
| `update_route_by_door_1~4()` | 12 条内联数组 + `door1route`/`door7route`/`door_return_via_N4` 3 个全局数组 | ~90 行 |
| `update_route_at_P1()` | 3 条"含已消耗前缀"的完整数组 | 19 行 |
| `plan_treasure_return()` | 4 分支门梯（`N12,N5` / `N12,N8,N5` / `N12,N8,N3` / `N10,N3`） | 68 行 |
| `get_newroute()` | 进东区 4 分支 + **回程 8 分支门梯** | ~108 行 |
| `#if !USE_PLANNER_ROUTE` 兜底块 | `pre/tour/tour_p6/entry_*/tail_*` 共 12 条数组 | ~127 行（不参与编译） |

根因**不是**规划器不会算，而是**规划器不知道哪扇门现在能过**：

- 边表里 `N3↔N8`、`N5↔N8`、`N5↔N12` 都是普通双向边；
- 门颜色只在**执行层**体现（`door_set_pass_node()` 改 `Node[].function/speed/step`）；
- **规划层**的线路图权重 `lg_w` 在 `nav_init()` 启动时就算死了（`nav_planner.c:119-154`），运行时看不到门状态 → Dijkstra 会理直气壮地穿一扇红灯门。

历史上 2026-09-08 的"180° 掉头"只是次生现象：`plan_after_return_door()` 把 `wp` 写成了 `{nodes.nowNode(=N5), N8, N5}`，拼出 `N5→N8→N5`。

## 1. 权限语义（最容易搞错，按现有 `door()` 反推）

| 门状态 | 规划器应看到 |
|--------|--------------|
| **未读** | **可走** —— "得走过去才能读到颜色"，所以出程 wp 里冲门那一段必须保留（如 `update_route_at_P1` 结尾的 `N5,N12`） |
| 绿 `CAN_PASS` | 双向可走 |
| 蓝 `ONE_WAY_PASS` | 只允许**去程那个方向**；回程方向禁用 |
| 黑 `NO_PASS` | 双向禁用 |
| 二轮 `Clear_door()` | 只关掉了"代码重触发 `door()`"，**物理门的黑/蓝约束仍在** → 同一张表继续用 |

门的 4 对（`N5↔N12`、`N5↔N8`、`N3↔N8`、`N3↔N10`）+ 方向，就是这张表的全部内容。

## 2. 已验证结论

### 2.1 门回程 12 条手写数组 = 规划器最短路（12/12 逐字一致）

在"按 §1 禁用门边"的图上，取 `wp = {当前节点, [宝物平台], P2}` 跑最短路（`W_len=1.0, W_turn=0.6, W_obs=1.0`，镜像 `NAV_W_*`）：

| 入口 | start | treasure=5/6, 3, 4, 2 | 结果 |
|------|-------|------------------------|------|
| `door_1`/`door_3` | N3 | `{N3,P2}` / `{N3,P3,P2}` / `{N3,P4,P2}` / `{N3,P1,P2}` | 4/4 一致 |
| `door_2`（D3 蓝已消耗 → 禁 `N8→N5`，D4 未读 → 放行 `N8→N3`） | N8 | 同上换 N8 | 4/4 一致 |
| `door_4` | N5 | 同上换 N5 | 4/4 一致 |

`door_2` 那条尤其能说明问题：**允许未读的 D4、禁用用过的蓝门 D3** → Dijkstra 自动选出 `N8→N3`（去重读 D4），与手写的 `door7route` 完全吻合。

### 2.2 另外两处门梯也是冗余

- `update_route_at_P1`：`wp={P1,P3,N5,N12}` / `{P1,P4,N5,N12}` / `{P1,N5,N12}` 三条全部逐字复现（3/3）。
- `plan_treasure_return`：4 个门分支（D2绿/D3绿/D4绿/仅D5蓝）的**显式门必经点与极简 wp 输出完全相同**（4/4）→ `N12/N5/N8/N3/N10` 这些必经点全部冗余。

### 2.3 复跑方法

用 `scripts/validate/_weight_calib.py` 的 `parse_graph()` / `plan_via_waypoints()`：

1. 取出边表里 `func == DOOR` 的 6 条边（`N3→N8`、`N5→N8`、`N5→N12`、`N8→N3`、`N8→N5`、`N10→N3`）；
2. 按用例构造 `blocked` 集合，从 `adj` 里剔除这些边；
3. `plan_via_waypoints(edges, adj_after_block, wps, 1.0, 0.6, 1.0)`，去掉首节点后与手写数组比对。

## 3. 改动设计

### 3.1 规划层（`Navigation/nav_planner.c/h`，~20 行）

```c
void nav_set_edge_blocked(uint8_t from, uint8_t to, uint8_t blocked);  /* 运行时禁/放一条边 */
void nav_clear_blocked(void);                                          /* 清空（二轮/重规划前） */
```
- 内部 `static uint8_t s_blocked[NAV_MAX_EDGES];`，`nav_set_edge_blocked` 用 `nav_find_edge()` 定位边号
  （**`nav_find_edge()` 目前零调用、正好在这里派上用场**）；
- Dijkstra 松弛循环里 `if (s_blocked[v]) continue;`（`v` = 后继边号，O(1)，不重建 `lg_w`）；
- 起点初始化同样跳过被禁边。

### 3.2 任务层（`Mission/`）

- `door()` 每次读完颜色后调用一次 `door_apply_permissions()`（新函数，表驱动，~20 行）：把 `door_pass[0..3]` + 当前阶段映射成 §1 的禁用集合；
- 然后**统一**用：
  ```c
  set_route_from_here(wp = {nodes.nowNode.nodenum, [宝物平台], P2});
  ```
  替换 `update_route_by_door_1~4`（4 个入口合成 1 个，因为都读 `nodes.nowNode.nodenum`）；
- `plan_treasure_return()` 删掉门梯，只留 `switch(treasure)` 查表选宝物平台；
- `get_newroute()` 回程 8 分支 → 同一张表 + 保留 `p6_first` 的巡游方向翻转；进东区的 `N12`/`N10` 锚点**先保留**（未证明纯冗余）。

### 3.3 顺带统一 route 写入约定（消除两处隐患）

现状 3 套写法：

| 调用点 | 写法 | 隐患 |
|--------|------|------|
| `door()` / `get_newroute()` | `map.point=0`（或 `mapInit()`）+ 写 offset 0 | 无 |
| `update_route_at_P1()` | 写 offset 0，**把已消耗前缀 `B1,N1,P1,N1` 原样重抄一遍**对齐索引 | 隐含依赖 `map.point` 恰为 4；`mapInit()` 的规划结果一变就错位，最坏 `getNextConnectNode` 失配 → `Route_Error_Stop` 死停 |
| `plan_treasure_return()` | 写 `offset = map.point-1` | 静默依赖"新路线首跳 == 原 `nextNode`"（只有 P7/P8 出边唯一才成立），且不刷新 `nodes.nextNode` |

统一为 `set_route_from_here(const u8 *wp, uint8_t n)`：内部自己算 offset + 刷新 `nodes.nextNode`，让"从这里开始走这条路"成为一个动作。

## 4. 实施顺序（按"阶段"读，不是按 S 编号）

> 每步都必须能在 Keil V5.32 编过 + 4 个校验脚本全过之后再进下一步。

### 阶段 A —— 已完成
- A1 `d44f954`：把工作树既有改动落库（建图统一 / include 短写 / 死代码清理）。
- A2 `e62d21f`：零风险去重（`door_1`≡`door_3` 合并、`ret_via_P1` 抽公共、删死分支、`sizeof` 修正、删 `nav_stitch` 等）。
- A3 `a7d1750`：删两处废值（`select_speed_stage()` 残留声明、`N13→C2` 退化桩，`NAV_EDGE_COUNT` 125→124）。

### 阶段 B —— 收益最大：把门回程穷举换成最短路（本文档主体）

| 子步 | 做什么 | 固件行为变化 | 验证 |
|------|--------|--------------|------|
| **B1** | 只往 `nav_planner` 加 `nav_set_edge_blocked()/nav_clear_blocked()`，**不接线**；同时新建 `scripts/validate/_check_door_perm.py`，把 12 条手写数组当"标准答案"，断言"权限表 + 极简 wp"能逐字复现 | **零变化**（新函数没人调用） | 新脚本 12/12 |
| **B2** | 接线：`door()` 读完颜色后调用 `door_apply_permissions()` 更新禁用集合；`update_route_by_door_1~4` 四合一为 `set_route_from_here({当前节点,[宝物平台],P2})`；删 `door1route/door7route/door_return_via_N4` + 12 条内联数组 | 门回程路线**逐字不变** | 新脚本 12/12 + 原 4 脚本 |
| **B3** | 同一套表再吃掉 `plan_treasure_return()` 的 4 分支门梯、`get_newroute()` 的 8 分支回程梯 | 路线逐字不变 | 新脚本扩展到门状态组合 |

### 阶段 C —— 数据驱动（把剩余 if 链/魔法数字搬进边表；与 B 独立，可单独做）

- `Clear_door()` 的 8 条调用 → 4 对 × 2 方向表 + 循环；
- `map.c:GetForwardDistanceBeforeTurn()/…GyroTurn()` 两条 `(last,now,next)→距离` if 链 → 边表字段；
- `map.c:Check_And_Apply_SpeedUp()` 的 4 个三元组 → 边表 flag 位。

> ⚠️ 顺序建议：C 里的"门回程查表化"（`door_2/door_4` 的 `if(treasure==…)` 链）**不要单独做**——那些函数在 B2 里就被删了，先做等于给待删代码做美容。

### 阶段 D —— 决定兜底块去留

`#if !USE_PLANNER_ROUTE` 的 ~127 行（`pre/tour/tour_p6/entry_*/tail_*`）：要么删掉、`USE_PLANNER_ROUTE` 只剩 1 档；要么保留，但**切回 0 之前必须先恢复 `rout_57/58/67/68`**（已在 09-11 删除）。

## 5. 风险 / 不要动的地方

- **`door()` 的状态机**（`lastNode/nowNode` 精确匹配）必须留：那是"何时停车读颜色"的物理时序，规划器替代不了。
- **`nav_obs_penalty` 权重别顺手改**：`N11=120` 避刀山、`Bridge/Hill=300` 逼南环，源码注释里有临界区间（240~360）。
- **二轮 `p6_first` 顺序翻转保留**：跷跷板单向 + 收尾位置要求。
- 每步之后必须能在 MDK（Keil V5.32）编过；本机只有 `arm-none-eabi-gcc`，因 Keil RVDS 端口的 `__asm{}` 无法整工程语法检查，只能用 `-fsyntax-only` + 桩头文件检查单个 TU。

## 6. 收益预估

`Mission/mission_planner.c` 591 行 → ~250 行（含删掉 127 行不参与编译的兜底块），
12 条手写门回程数组归零，且"穿门掉头"从"靠人写对"变成"结构上不可能"。
