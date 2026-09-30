# tools/ — 可复用诊断脚本

与 `validate/` 的分工：

- **`validate/`** = 上车前**必跑**的校验（改边/改门/改权重后必须全过，有固定流程）。
- **`tools/`**（本目录）= 排查问题时**按需跑**的诊断/仿真工具，只读源码，不进固件编译，不改任何文件。
- **`tools/ai/`**（子目录）= **能操作工具链**的脚本（编译/烧录/读串口），是唯一会调用外部程序（EIDE 自带
  `unify_builder.exe` / `openocd.exe`）的地方；仍然**不改任何固件源文件**。见 `ai/README.md`。

新增脚本请：① 放在本目录；② 在下面的表里补一行用途。

## 脚本清单

| 脚本 | 干什么 | 什么时候用 | 跑法 |
|---|---|---|---|
| `sim_route_bookkeeping.py` | 状态机仿真：逐跳复刻固件 `route[]` / `map.point` / `nodes` 的推进，每一步校验不变量 `route[map.point-1] == nodes.nextNode.nodenum`，破了就报第一次破的位置。**开机先读 `Mission/config.h` 的 `UPRIGHT_TOUR_ENABLE` 并对 `mission_planner.c` 自检**（三处 `S` 插点 / 开关取值 / `wp` 容量），对不上就报「镜像已过期」并 exit 1；另校验红线「`S1`/`S2` 不得排在宝物平台之前」 | 怀疑**路线记账错位**（`Route_Error_Stop` 死停、车莫名停住）时第一个跑；⚠️ **改了 `mission_planner.c` 的 `wp` 或 `config.h` 的开关之后必跑** | `python3 地图修改上位机/tools/sim_route_bookkeeping.py` |
| `trace_round1.py` | 第一轮逐跳 trace：每跳打印 `edge / map.point / route[point-1] / nextNode / func` | 想知道"某一跳到底走的哪条边、func 是什么" | 直接运行 |
| `trace_rounds.py` | 第一轮 + 第二轮逐跳 trace，标出 `View` / 门 / 波动板等关键 func 的落点 | 定位"经过某个关键点后卡住"（如 N14 直立景点） | 直接运行 |
| `route_sim.py` | 只读镜像 `nav_planner.c` 的 Dijkstra + 门回程，按当前 `config.h` 场次算 `route[]`，并列出 N14 的进出边 | 想核对"规划器**应该**选出哪条路" | 直接运行 |
| `analyze_weight_sensitivity.py` | 扫 `NavObsPenalty[DOOR]` / `NAV_W_TURN` 的候选值，看各自会改掉哪些路线 + 5 个校验脚本是否被破 | 想用**权重**让规划器"别穿门 / 别乱转弯"之前 | 直接运行 |
| `analyze_door_weight_route_diff.py` | 门惩罚改动前后"会动哪些路线"的穷举比对（覆盖固件全部调用点 + `MAP_DEBUG` 全空间） | 改门权重的**影响面**评估 | 直接运行，或 `… 0 100` 自定义前后值 |
| `sim_upright_tour.py` | 直立景点巡回（`S1`/`S2`）路线验证：镜像 `mission_planner.c` 三处插点，算 `UPRIGHT_TOUR_ENABLE=0/1` 两种状态的 `route[]` —— 关态无 `S`（回归基线）、开态 `S` 在 `P3`/`P4` 之后且在宝物平台之后、去掉 `S` 支路后与关态逐跳一致（5700 项） | 开关 `UPRIGHT_TOUR_ENABLE`、或改 `plan_treasure_return` / `route_return_home` / `get_newroute` 的 `wp` 之后 | 直接运行 |
| **`ai/`**（子目录） | **让 AI 自主调试的工具链**：无头编译 / 烧录 / 读串口（`build.py` / `flash.py` / `serial_watch.py`）。**会调工具链、不只是分析**，故单列一目录 | AI 需要「改码→编译→烧录→看现象」闭环时；见 `ai/README.md` | `python 地图修改上位机/tools/ai/build.py --json` |

## 注意事项

- 全部**只读**源码，不写任何固件文件、不改 `route[]` 之外的东西。
- 依赖仓库源码 `Navigation/map_message.c` 与 `地图修改上位机/validate/_weight_calib.py`（部分脚本），**别单独把脚本拷走**。
- `_weight_calib.py` 顶部场地常量默认 `FIELD_COMP`，脚本会按 `Mission/config.h` 的真实场次覆盖；
  不同场地 `LEN_*` / `DOOR_LEN_*` 不同，选路结论可能相反 —— 别跳过这一步。
- 2026-09-26 从 `analyze/` 与仓库根 `_battest_tmp/` 迁入，迁入时已修正脚本内的路径硬编码并逐个跑通（exit=0）。
- ⚠️ **本目录脚本是「手抄镜像」，不会自动跟着 C 代码变**。`sim_route_bookkeeping.py` 已内置源同步自检
  （读 `config.h` 开关 + 比 `mission_planner.c` 的插点，对不上 exit 1），`trace_rounds.py` 复用它所以也跟着同步；
  其余脚本仍靠人工 —— **改 `wp` / 加开关之后，先跑 `sim_route_bookkeeping.py` 看自检过不过**。
