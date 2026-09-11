# scripts/ — 工程辅助 Python 脚本

> **用途**：把所有 `.py` 辅助脚本从仓库根收拢至此，按用途分两类。**只读/校验，不进固件**；执行层固件（`Navigation/`、`Mission/`、`Application/`）不依赖它们，仅仓库根 `MDK-ARM/update_keil_project.py` 留在原处。
> **本地跑**：在**仓库根**执行，或按提示加路径；脚本内部已改为相对 `scripts/` 上一两级自动定位仓库根，换机器/换路径不用改。

---

## `validate/` — 上真车前必跑的校验（`pre-commit` 也会自动触发其中三个）

| 脚本 | 作用 | 什么时候跑 | exit |
|------|------|-----------|------|
| `_weight_calib.py` | 从 `map_message.c` 的 `NavEdgeTbl[]` 解析图；校验所有参考路线相邻节点皆有合法边；edge 状态(line-graph) Dijkstra 复现 仅长度/长度+转角/长度+转角+障碍 三种成本模型的路线。**基准回归工具**。 | 改边或权重后 | 0=全过 1=有差异 |
| `_check_csr.py` | 镜像 `nav_planner.c` 的 `nav_init()` 自动构建 CSR（`ConnectionNum/Address/Node[]`），验证 `getNextConnectNode` 能解析全部参考边 + 8 条门边。 | 增删边后 | 0=连通 1=缺边 |
| `_check_wp.py` | 镜像 `nav_plan_waypoints`，对若干必经点组合验证"删掉某个必经点不改路线"（`build_wp` 新旧两版路线一致）。 | 改 `wp` 必经点后 | 0=一致 1=不一致 |
| `_check_door_logic.py` | **门逻辑表驱动校验**（新增，重点排查门区问题）：① 所有 `DOOR` 功能边要么命中 `door()` 状态匹配表、要么在驱动前被 `Clear_door()` 清成 `NONE`（二者皆无才报缺口，避免把"回程边必先清 NONE"误判成 bug）；② 对 D2/D3/D4 每种颜色组合镜像 `plan_after_return_door` 生成回程路线，检查是否 `CarBrake_Stop`/断链；③ D4 回程黑灯退到 N5 后下一跳必须 `N4` 且转角 `need2turn(-145°,0°)=145°`。 | 改门逻辑后 | 0=通过 1=发现问题 |

> `_check_csr.py` / `_check_wp.py` 都 `import _weight_calib`，三者必须同目录（现都在 `scripts/validate/`）。`_weight_calib` 的 `BASE` 已上溯两级指向仓库根，才会去读 `Navigation/map_message.c`。

## `analyze/` — 诊断/排查用（只读，非回归校验）

| 脚本 | 作用 | 备注 |
|------|------|------|
| `analyze_door_return_route.py` | **解析真实源码**复现 `nav_planner.c` 线路图 Dijkstra，回答过门 `N8→N5` 下一节点（=N4）与 N5 处转角为何≈180°；读取的是当前 `map.h`/`map_message.c`/`config.h`(学校场地)/`barrier.c`。**最可信、常维护**。 | 新增 |
| `analyze_door_bug.py` | 早期打印式分析 D4 回程 `door_retreat` 后退+转向的冲突（文本输出，非解析源码）。 | 历史 |
| `analyze_n8_n5_turn.py` | 早期打印式逐步分解 `N8→N5→N4` 执行流程、查找 N5->N4 边角度。 | 历史 |
| `check_door_route_logic.py` | 早期打印式分析 `DOOR_D4_BACK` 与 `plan_after_return_door` 的分支可行性。 | 历史 |
| `check_route.py` | 早期打印当前 DEBUG 路线（`route[100]`）与 `GetForwardDistanceBeforeTurn` 中 `N8→N5→N4` 的前进距离。 | 使用了**过时/硬编码** NODE_MAP，仅参考 |
| `trace_d4_black.py` | 打印式完整推演 D4 黑灯(`DOOR_D4_BACK`)的路线生成逻辑。 | 历史，含硬编码节点映射 |

> ⚠️ `analyze/` 下除 `analyze_door_return_route.py` 外的几个为历史排查脚本，里面**节点编号映射可能过时/硬编码**（与当前 `map.h` 不一致时结论仅供参考）；改动前请以 `validate/` 的校验脚本 + 当前源码为准。

---

## 运行示例（在仓库根）

```bash
# 上真车前必跑
python3 scripts/validate/_weight_calib.py
python3 scripts/validate/_check_csr.py
python3 scripts/validate/_check_wp.py
python3 scripts/validate/_check_door_logic.py

# 排查门区
python3 scripts/analyze/analyze_door_return_route.py
```
