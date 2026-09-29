# map_editor 项目参考 — 给 AI / 接任者读

> **读者对象**：**给 AI 读**。配合 `README.md`（给人看的使用说明）一起。
> 本文档只写**现状 + 怎么改 + 别踩什么坑**，不记流水账；改动历史见 `项目讲解文档/README.md`。
> **完整仓库背景**先读 `项目讲解文档/project_reference.md`（那里讲固件三层架构、边表语义、验证脚本）。

---

## 1. 这是什么 / 边界

把固件里的地图（`Navigation/map.h` 的 `enum MapNode` + `Navigation/map_message.c` 的
`NavEdgeTbl[]`）画成可拖拽的图，改完导出 C 代码或直接写回源码。

**硬边界（务必遵守）**：
- **纯辅助工具，不进固件**。`Navigation/`、`Mission/`、`Application/`、`Motor/` 都不依赖它；
  反过来它**只读**固件源码（写回必须显式点按钮 + 自动备份）。
- **不参与任何长度/角度计算**。图上距离只是示意图；**真值只认边表里的 `step` / `angle` 数值**。
- 依赖：Python 3 + tkinter（自带）；底图旋转/缩放用 `pillow`。

---

## 2. 文件与职责

| 文件 | 职责 | 改动风险 |
|------|------|---------|
| `map_model.py` | **核心（无 GUI）**：解析固件源码、数据模型、校验、Dijkstra、C 代码导出、出厂坐标 | 改这里**必须重跑** `_selftest.py`（有"往返零差异"护栏） |
| `map_editor.py` | tkinter 界面：画布绘制/交互、面板、对话框、布局存取、写回固件 | 改这里重跑 `_guismoke.py` |
| `_selftest.py` | 无界面自检：解析 / **往返一致** / 宏求值 / 导出格式 / 编辑 / 规划 | — |
| `_guismoke.py` | 界面冒烟测试（185 项），**全程沙箱，绝不碰真实布局** | 见 §7 隔离规则 |
| `analyze_layout.py` | 只读分析：位置精度、单位长度 K、角度一致性 | — |
| `analyze_unit_length.py` | 只读分析：`图上px ÷ step` 分布，定 K 上界 | — |
| `solve_missing_nodes.py` | 用边表角度反解"图上没画"的节点坐标（离线工具） | — |
| `layouts/default.json` | 默认布局，**启动自动载入**，优先级高于出厂坐标 | 见 §7 安全 |
| `layouts/snapshots/` | 每次保存前的自动快照（保留最近 30 份） | — |

---

## 3. 数据流

```
固件源码（唯一真值来源）
  Navigation/map.h          -> parse_map_enum()      -> [Node(name,comment,index)]
  Navigation/map_message.c  -> parse_edge_table()    -> [Edge(from,to,flag,angle,step,speed,func,comment)]
  Mission/config.h          -> parse_config_macros() -> {宏名: 表达式}  （按 USE_FIELD 展开分支）
                                   |
                                   v
                        MapModel（内存模型）
                     /          |            \
          validate()      plan_route()      export_*()
          校验面板        路线规划            C代码/JSON
                                   |
                                   v
                  （可选）patch_firmware_dialog() 写回固件（先备份）
```

**关键点：`Edge` 的 `flag/angle/step/speed/func` 都存"文本"**（如 `ANGLE_N3N8`、`LEN_B7C6/1`，
甚至 `DOOR_LEN_N3N8/2`），求值走 `eval_c_expr(expr, macros)`。
→ 这样**没编辑过的字段导出时逐字还原**，"打开→导出"零差异可断言（`roundtrip_report()`）。

---

## 4. 坐标系与角度（最容易搞错的地方）

### 4.1 三套坐标
| 坐标 | 含义 |
|------|------|
| **世界坐标** | `map_model.SEED_POSITIONS` / `Node.x,y`：**`节点图.jpg` 原图的像素坐标（1729×1080）**，y 向下 |
| **视图坐标** | 世界坐标经 `ROT_MATRIX` 旋转后的显示坐标 |
| **屏幕坐标** | 视图坐标经 `scale/ox/oy` 缩放平移（`w2s` / `s2w`） |

**历史坑**：`SEED_POSITIONS` 早先是**预览图（1012 宽）**坐标，而底图是原图（1729 宽），
差 **1.7112 倍** → 底图整体偏移。现已全部换算到原图像素系（依据：图上 P1/P2 方框中心实测）。

### 4.2 视图旋转
```python
ROT_MATRIX = {"0°": (1,0,0,1), "90°": (0,1,-1,0), "180°": (-1,0,0,-1), "270°": (0,-1,1,0)}
view = (a*x + b*y, c*x + d*y)      # 逆变换 = 转置
```
- **0° 必须是恒等**（历史上 0° 档曾把 y 取反，把节点翻到负坐标区 → "底图/节点对不上"）。
- 底图用 `BackgroundManager.set_rotation()` 同步 `PIL transpose`，**节点和图必须一起转**。
- **默认 0°**（用户确认"原图角度是对的"）。

### 4.3 拖动吸附（`snap_mode`，取代了旧 `lock_angle`）

工具栏「吸附」下拉三档（`SNAP_MODES`）：

| 模式 | `_edge_pref_dirs()` 返回 | 说明 |
|------|------------------------|------|
| **吸附水平/竖直**（`SNAP_DEFAULT`） | `AXIS_ANGLES` = 0/90/180/−90 的方向向量 | 用户要求：更偏好水平/竖直，"到一定范围就自动吸附" |
| 跟随角度表 | 边表 `angle + DRAG_ANGLE_OFFSET` | 旧行为 |
| 自由 | `[]` | 不做方向约束（长度约束仍可单独生效） |

**吸附是"按范围确定性"的，不是靠权重**（`solve_drag_position()` 里）：
- 方向离**最近的轴** `≤ snap_tol`（默认 8°）→ **精确吸正**，`info["snapped"]=True`；
- `≤ snap_near`（默认 25°）→ 投到该轴（软拉扯）；
- 再远 → 不干预。

> ⚠️ **别再尝试用"权重 × 垂距²"实现软拉扯**：实测 `tan(near)²≈0.217` 太小 ——
> 轴候选的分数比原始位置大 4.6 倍（6029 vs 1311），根本拉不动。用范围判断才可靠。
> 同理硬吸正也**不能"逐方向试 + 比分数"**：偏 5° 时"垂足"与"轴上点"分数几乎相同
> （差 <1e-9）会被容差挡掉 → 必须**先挑出最近的轴再无条件吸**。

**为什么默认"吸附水平/竖直"而不是"跟随角度表"**：节点图本来就不按角度表精确画 ——
实测表里 `angle` 与图上边方向整体差 90°（有符号偏差中位 −89.2°：61 条 −90°、32 条 +90°），
且不一致的 31 条里 `B2/B3/C1/N4` 一带需要 `+0°`。用户明确要求偏好水平/竖直，故以此为准。

`DRAG_ANGLE_OFFSET = 90.0` 只在「跟随角度表」模式下生效（改动时注意两处同源：
`_edge_pref_dirs()` 与诊断用的 `ang_dev` 计算）。

---

## 5. 拖动约束求解（`solve_drag_position`）

对每个相邻节点 `other`，要求该边同时满足：
1. **角度**：`点 → 直线` 距离 ≤ `TOL_LINE(0.5px)`（**不是**"与方向向量平行"的叉积判据！）
2. **长度**：`|点-other| ≥ step(cm) × K`，`K = unit_px_per_cm`（默认 0.884，可改）

实现为**候选点 + 硬筛选**：
- 候选 = 各边角度射线上的点（**必须精确加入 `want` 的垂足**，否则单边节点会被弹到几十像素外）+ 最小长度圆的径向投影与弧采样；
- 筛选后取离 `want` 最近的点；**无可行点 → 返回 `want`（放开不吸附）** 并置 `feasible=False`。

**同一条线段两方向去重**：用"共线判定（±180 等价）"判断是否属于同一引导线，
不能直接用 `frozenset((frm,to))` 相等就合并（历史上因此把正常情况判成矛盾）。

**单位长度 K 的物理现实**：节点图**不是等比例**的，`图上px ÷ step` 从 **0.17 到 94.9（差 500 倍）**，
所以**不存在**能让所有边都满足"长度 ≥ step×K"的 K。实测（用户布局）：
K=0.5 → 0 条违规；**K=0.63 → 1 条**（`C2→C1`）；K=0.884 → 3 条；理论最大可行 K=0.520。
→ 工具栏「违反约束」按钮负责把违规边列出来，**不要试图"修好"这个矛盾**。

---

## 6. 关键不变量（改代码时必须保住）

1. **往返零差异**：不做编辑时 `export_edge_table()` 与源文件**逐字段相同**（`roundtrip_report()`）。
   所以**不要**把 `Edge` 的文本字段规范化成数字。
2. **导出行数 == `NAV_EDGE_COUNT`**，导出文本含编译期 `NavEdgeTbl_size_check`。
3. **`enum MapNode` 顺序 = 节点索引**（`map.h`），导出按当前节点列表顺序重排；
   增删节点后**必须**人工同步 `Mission/mission_planner.c` 的 `wp`、门逻辑、宝物表。
4. **宏必须能求值**：124 条边的 `angle/step` 全部可解（含 `ANGLE_REV()` 与带括号的
   `LEN_N18B5 = (LEN_N22B7 - 20)`）。解析 `#define` 时注意：
   - **函数宏的 `(` 必须紧贴宏名**，否则 `#define X   (A - B)` 的括号会被当参数表吃掉 → 宏丢失；
   - **`config.h` 有跨行块注释**，必须整体去注释，逐行 strip 会留下 `*/`。
5. **`world_to_view` 在 0° 档是恒等**。
6. **拖动约束的两处角度必须同源**（`_allowed_dirs` 与诊断）。
7. **`cm` 一律用「图坐标（世界）距离 ÷ K」算，绝不能用屏幕像素**：`w2s()` / `_edge_endpoints()`
   返回的是**屏幕**坐标，而 `屏px = 世界px × scale` —— 拿屏幕距离 ÷ K 会让读数**随缩放变化**
   （踩过：画布上的「图 xx.xcm」放大就变大）。统一走 `App._world_len_cm(e)`；
   `_geometry_warning_data()` / `solve_drag_position()` 本来就是世界坐标，是对的。
   同理 `calc_step_geo()` 要用 `self._unit_k()`，**别硬编码 0.884**（K 是可改的）。
7. **障碍惩罚表 == 固件的 `nav_planner.c: NavObsPenalty[]`**（`MapModel.OBS`）。
   **这是"上位机显示的路线"和"车上跑的路线"是否同一条的命门**：漏改过
   `Bridge/Hill/LBHill/SM/View/View1/BACK/BSoutPole/QQB/BHM`（写成 0）与 `BLBL`（写成 70），
   于是规划器把桥/山/楼梯/景点/跷跷板/波动板全当**免费捷径**，显示的路线与实车不符。
   `_selftest.py` 第 8 节会解析固件源码自动逐项比对 —— 改了固件就同步这张表，别只改一边。
   📌 **`Hill` 现为 230**（2026-09-13 由 300 降）：各起终点对的翻转阈值**不同** ——
   `N8→C9`/`N8→P5` 要 `Hill ≤ 239` 才走楼梯，`N12→N20` 要到 `≤200` 才走；取 230 同时满足
   「N8→C9 走楼梯、N12→N20 走南环」，且 `_weight_calib` 15 条参考路线仍 15/15。
   代价：`N12→P8`（阈值 247）等 61/2450 对改走楼梯侧（需实车复核）。
   ⚠️ **这个值写在三处**：`nav_planner.c: NavObsPenalty[4]`、`map_model.OBS["Hill"]`、
   `validate/_weight_calib.py: OBS_PENALTY[4]`。调它之前先用
   `plan_route([a,b], "full")` 量出**目标那一对**的阈值（各对不一样，别拿一个数当通用）。
8. **「线索路线」必须逐条镜像固件分支，不要自己发明**。四段 wp 分别来自
   `update_route_at_P1()` / `update_route_at_door_for_stageAB()` + `plan_treasure_return()` /
   `route_return_home()` / `get_newroute()`，都写在 `map_model.py` 的同名纯函数里；
   规划入口是 `MapModel.plan_route(wp, mode, blocked)`，`blocked` 镜像 `nav_set_edge_blocked()`。
   固件在这些输入下会 `CarBrake_Stop()` 的组合**必须报错**，不许硬凑路线。
   门区 8 条边、通行语义常量、`door_pass[0..3]`→D2/D3/D4/D5 的对应也都在 `map_model.py` 顶部。
9. **`door()` 内部的路线也要显示**（`door_read_flow()` / `door_back_flow()`）：`door()` 有三处
   **不改 `NavEdgeTbl[]` 却直接改 `route[]` / `nodes.nowNode`** 的动作 —— `door_retreat()`
   的隐式 `nowNode` 改动、D3 黑的 `door1route={N3,N8}`、D5 黑+D2 蓝的 `route[0]=N3;route[1]=0xFF`。
   它们是"门区路线看不懂"的主要来源，漏掉就会得出"路线不对"的错误结论。
   渲染在 `map_editor._door_trace_lines()`；⚠️ 判断 `DOOR_D5_BACK`/`DOOR_D4_BACK` 时注意
   **else 分支是"非绿"（黑和蓝都走）**，不是只有黑。
10. **第一轮完整路线 = 逐段拼接，拼接点只能是固件的真实交接点**（`_round1_complete()`）：
   `mapInit` 的 `nowNode=P2→N2` → P1 的手写数组（前 4 跳与 `nav_build_route({N2,P1,N5})` 相同，
   所以 `P2 → N2 → 手写数组` 就是完整路）→ `door_read_hops()`（退回重读，只挑**真实边**）→
   `stageAB`（`wp[0]` = 过门落点）→ `plan_treasure_return`（`wp[0]` = 读宝物的平台）→
   `door_back_chain()`（回程穿 BACK 门时 `door()` 会再覆盖一次）。画布分色靠 `App.route_split`
   （回程起始下标）；**任何新的"设置 route"的地方都要把 `route_split` 一起复位**，否则会误分色。
   ⚠️ **门是按边顺序读的**（`door_read_names()` / `doors_known_only()` / `_doors_after_entry_read()`）：
   读灯边是 `N5→N12`(D2) / `N5→N8`(D3) / `N3→N8`(D4) / `N10→N3`(D5)，`door_pass[]` 初值 0 = **未读**，
   而**未读 ≠ 黑灯** —— 梯子（`plan_treasure_return` / `get_newroute`）把 0 当"非绿非黑"。
   所以喂给梯子的只能是"**车真的读到过**的门"：D2 蓝 ⇒ 直接落 N12、`N5→N8` 那条边根本没走 ⇒
   D3 永远是 0。拿对话框填的值直接进梯子会算出车根本走不到的路线（实测：D2 蓝 + 填 D3 绿 ⇒
   仿真算出走 D3，真车 D3 未读 ⇒ 回程掉到"经 D5"分支走 `N10→N3`，两边对不上）。
11. **新建边/按钮算角度必须走「边表约定」，不能用图上裸几何角**（`App._auto_edge_angle()`）。   表里 `angle` 是**单向图**编码：几何只能定出**直线**、定不出**方向感** —— 实测本图 109 条边里
   52 条是「几何 + 90°」、31 条是「几何 − 90°」（同一根直线、方向相反）。所以：
   ① 起点已有**共线**出边（≤ `ANGLE_ANCHOR_TOL` 8°）→ 沿用它的 `angle`；
   ② 否则「几何 + `DRAG_ANGLE_OFFSET`(90°)」；③ 再吸附到 `0/±90/180`（`ANGLE_SNAP_TOL` 5°）。
   用在 `create_edge_quick()`、`calc_angle_geo()`（单选）与 `_calc_angle_geo_batch()`（框选批量）
   三处（**别再各写一份**）。
   ⚠️ 注意 `_edge_pref_dirs()` 用的是反方向的 `angle + DRAG_ANGLE_OFFSET`（引导线是**双向直线**，
   ±180 同一条线，所以那边不算错）；**但写进边表的方向感必须靠①的锚定或③的吸附来定**。
   **框选批量（`Ctrl+拖空白` 或 `_calc_angle_geo_batch`）的确定性要求**：整批**先算后写**
   且 `ignore=整批` ⇒ 批内各边**互不做共线锚定参照**，只允许沿用**框外**共线边的 `angle`。
   若改一条算一条，先改的边会成为后改边的锚 ⇒ 结果依赖处理顺序（一条错的老角度污染整批）。
   框选判据 = **两端节点都在框内**（`App.selected_edges` 存 `(frm,to)` 键）；
   `App.sel_edge` 的 property 在单选一条边时**清空** `selected_edges`（点空白/点节点同样清），
   避免按钮按旧批量作用于用户看不见的一批边。
12. **平台交换只换"名字"，`func` 跟着平台类型走**（`MapModel.swap_platforms()`）：
   `from`/`to` 互换，**`step`/`angle`/`flag`/`speed` 一个都不动**（长度不变），
   每条相关边的 `func` 换成"新名字那个平台"的入口/出口动作 —— 入口/出口动作**从当前地图读**
   （`node_io_roles()`：优先取 `func != NONE` 的那条），**不要硬编码 P5=UpStage 之类的表**。
   ⚠️ 换完 `mission_planner.c` 的 `wp` / 门逻辑 / 宝物表 / `barrier.c` 的节点名判断**都要复核**
   （它们按名字走，编辑器保证不了业务自洽）；两边有直接边时**必须拒绝**（否则那条边算谁的说不清）。
13. **第二轮路线可以改"巡游顺序"，但固件 wp 不会跟着变**（`round2_waypoints(..., cruise=)`）：
   `cruise` 只替换巡游那 4 跳（P5~P8 各一次，顺序就是走法）；**进门处"多保留的那一个 N8"跟的是
   巡游首站**（首站 = P6 才留，等价固件的 `p6_first`），**不是宝物值** —— 宝物只定默认方向。
   自定义顺序与固件默认（`round2_firmware_cruise()`）不同时，报告里必须出
   **"固件 `get_newroute()` 的 wp 要人手同步"** 的告警；`_selftest` 第 11 节拿
   `mission_planner.c` 源码对拍默认顺序，动 `round2_*` 就要跑它。
   画布"画布显示"过滤（`ROUTE_VIEW_MODES` / `App.route_view`）**只影响绘制**，不改 `self.route`；
   `_route_split_ok()` 为假（路线未分色）时只看单段 ⇒ **一段都不画** + 状态栏说明，不许瞎画。

---

## 7. 安全规则（血的教训，务必保持）

1. **`_guismoke.py` 绝不能碰 `layouts/*.json`**：
   - 保存/载入测试走 `layouts/` **之外**的工作区沙箱目录（`save_layout(path=...)` 是专为测试留的入口）；
   - 测试前后对真实布局做 **SHA256 比对**，不一致直接 fail。
   > 背景：曾有一版让测试直接写/删真实 `default.json`，**误删了用户调好的布局**（无法恢复）。
2. **沙箱目录不能用 `tempfile.mkdtemp`**：本环境文件沙箱下它建的目录写入会
   `PermissionError: [Errno 13]`（工作区内也一样）。**用 `os.makedirs`**。
   （Windows 系统 TEMP 也在沙箱外，同样写不了。）
3. **保存布局永远先快照**：`_snapshot_layout()` 把旧版复制到**被测文件同目录**的
   `snapshots/`（保留 30 份）。快照放"同目录"而不是固定 `layouts/snapshots`，
   这样测试写沙箱时快照也落沙箱、不污染真实目录。
4. **写回固件前必须**：`validate()` 无 error + 自动备份到 `backups/` + 提示用户 `git diff` 复核。
5. **模态对话框陷阱**：任何"打开即可能弹窗"的路径都会让无人值守测试挂住
   （曾因无限重绘 + `Treeview` 选中回环导致挂死）。测试里只调不弹窗的入口。
   ⚠️ 同理：**测试里不要真触发 `_on_node_menu` / `_on_edge_menu` / `_on_bg_menu`**（它们 `tk_popup` 会阻塞）。
   要验证"Shift+右键走菜单"就把 `_on_node_menu` 换成桩函数，别真弹。
6. **`layouts/default.json` 会盖掉固件地图（重要）**：布局文件里**连边表一起存**，
   而 `App.__init__` 会自动载入它。所以存在两份地图，且**布局优先**：界面上显示的路线、校验、
   导出的 C 代码都可能基于布局而不是 `NavEdgeTbl[]`。本项目踩过一次：布局里多了 `C10`、
   少了 `C9↔P7` / `B7↔C6`（`_selftest.py` 第 7 节那个"演示改动"被在界面里做出来并存了盘）。
   - 护栏：`App._source_diff_items()` 把当前模型与 `M.MapModel.load_from_sources()` 对比，
     不一致时**状态栏 + 「校验」面板**都会告警。
   - **`_guismoke.py` 因此必须先强制 `load_from_sources()` 再断言**，否则测试结果会随用户存过的布局飘。
7. **「写回固件」只能替换表体，尾部必须沿用原文件**（`App._splice_edge_table(src, block)`，纯函数）。
   ⚠️ `export_edge_table(with_header=False)` 的输出**自带尾部**（`};` + 编译期检查 typedef +
   "已移至" 注释），而原文件在 `};` 之后本来就有那一段 —— 早期整块拼接 ⇒
   **`NavEdgeTbl_size_check` 变两份，且每写回一次多一份**（实测：写回前备份 1 份 → 写回后 2 份）。
   现在只取到表体收尾的 `};`。`_guismoke.py` 有纯函数级断言守着（不碰真实文件）。
8. **测试/脚本里不要硬编码具体节点或边**：地图真的会变（`C10` 从测试临时名变成了真节点、
   `C9↔P7` 被删）。断言一律从 `load_from_sources()` 推：数量对比用新解析的模型、
   "选一条边"用 `max(edges, key=step)`、演示改动挑一条 `has_reverse` 的现成边。
   另外**改名/删除"原装"节点会连带删掉它原有的边**（测试里别这么干，只动自己新建的节点）。
9. **加 UI 按钮必须确认它"真的被映射"**：`pack` 的空间是**按打包顺序**分配的 —— 把控件加进一个
   已经被 `expand=True` 的子控件占满的父容器（例如左栏 `top` 里两个 Treeview 之后），
   它的 `winfo_ismapped()` 会是 **False**，也就是**用户根本看不到**（踩过：平台交换按钮加在边表下面，
   用户反馈"左侧添加在哪呢，我怎么没看到"）。稳妥做法：挂到**顺序靠前的行**（如左栏「边显示」那行），
   或 `side="bottom"` 且比 expander 更早 pack。`_guismoke.py` 现在有一条断言检查入口
   `winfo_ismapped()`。
   顺带：**工具栏行宽要按 `minsize` 宽度（1200）判**，不是按当前窗口宽 —— 窗口能拉大，
   但缩到最小时溢出的行会把右侧控件挤到屏幕外（加「平台交换」到工具栏第 1 行就让该行变成 1254px）。

---

## 8. 测试怎么跑 / 期望结果

```bash
# 在仓库根执行
python 地图修改上位机/map_editor/_selftest.py     # 期望：全部通过，exit 0
python 地图修改上位机/map_editor/_guismoke.py     # 期望：185 项 [OK] / 0 FAIL

# 改 map_model.py 后额外跑（确认没碰坏既有工具链）
python 地图修改上位机/validate/_weight_calib.py   # 15/15
python 地图修改上位机/validate/_check_csr.py
python 地图修改上位机/validate/_check_map_debug.py
python 地图修改上位机/validate/_check_door_perm.py
```

**`_selftest.py` 覆盖**：解析（节点/边/悬空端点/重复 typedef）→ 往返零差异 → 宏求值 →
导出格式 → 编辑 → 规划 → 真实改动演练 → **成本表逐项比对固件 `nav_planner.c`** →
**门回程复现 `validate/_check_door_perm.py` 的 12 条 golden**（单一真值来源，直接 import）→
**第二轮 wp 巡游顺序与 `mission_planner.c` 的 `if (p6_first)…else…` 块源码对拍**（第 11 节）。

**`_guismoke.py` 覆盖**：画布尺寸/缩放、**工具栏三行且不溢出**、底图载入、
布局保存/载入（沙箱 + 真实 SHA256 不变）、底图反推标定、拖动约束（引导线角度 =
表里 angle + 偏移、矛盾时放开不吸附）、**点图形选边（命中区）**、**连线模式点两下建边**、
Delete 删边、校验面板、规划、6 类导出、节点增删/恢复、滚轮缩放、
**右键连线（含 Shift+右键=菜单、左键也能完成、取消起点）**、
**新建边角度走边表约定**、**「图 xx.xcm」与缩放无关**、
**框选批量**（`Ctrl+拖空白`：选中判据=两端都在框内 / 紫色高亮 / 整批一个撤销点 / 批外共线可锚定 /
批内互不锚定 / 单选一条边清空批量）、
**线索/每盏门灯/宝物 → 固件分支路线**（含 golden 比对与"固件会停车"分支）、
**`door()` 内部手写路线（`door1route` / `route[0]=N3`）与 DOOR 边告警**、
**第一轮完整路线拼接**（回程起点=第二个平台、每一跳都是真实边、BACK 门重规划段）
+ **画布确实画出两种颜色**、**画布显示过滤**（只看去程 ⇒ 只画蓝 / 只看回程 ⇒ 只画青绿 /
无分色时两色都不画）、
**第二轮路线**（默认巡游顺序与固件一致 / 自定义顺序只换巡游段、门节点跟巡游首站 /
与固件默认不同 ⇒ 报告出"需手工同步固件 wp"告警 / `route_split` 落在最后一个巡游平台）、
**「线索路线…」/「二轮路线…」对话框能构建 / 记住上次配置 / 非法配置回退 / 随布局持久化**、
**新入口（平台交换 / 二轮路线 / 画布显示）在界面上真的可见（`winfo_ismapped()`）且在左栏宽度内**。

---

## 9. 常见改动怎么做

| 想改什么 | 改哪里 | 注意 |
|---------|-------|------|
| 工具栏加/改控件 | `App._build_toolbar()` 的 `row1` / `row2` / `row3` | **三行**，最宽约 1163px，`minsize` 1200×720；`_guismoke` 有"≥3 行且不溢出"断言 |
| **边列表展示模式** | `App.edge_view` + `_fill_edges_merged()` + `_apply_edge_columns()` | 三种模式：合并双向(默认,每线段一行,两方向并列) / 逐条 / 只看双向。<br>**树 iid 有两种前缀**：`e:A->B`（单行）与 `b:A<->B`（合并行）——改 `_on_tree_edge_select` / `_tree_select` 时必须同时兼容，否则选中会失效 |
| **拖动吸附** | `snap_mode` / `snap_tol` / `snap_near` + `_edge_pref_dirs()` + `solve_drag_position()` | 见 §4.3：**按范围确定性吸附**，别用权重实现 |
| 改边的命中区宽度 | `EDGE_HIT_WIDTH`（默认 14px）、双向边间距 `EDGE_PAIR_OFFSET`（默认 6 ⇒ 两条线相隔 12px） | 命中线是 `fill=""` 的粗线，**必须**放进 `_canvas_items[tag]` 才有绑定 |
| **改选边/选方向的手感** | `App._edges_near()`（**自己算候选**，含双向偏移，按距离排序）+ `_on_edge_press()`（同处再点=切换）+ `_on_edge_double()` + `_on_tree_edge_select()`（合并行再点=切换方向） | ⚠️ **别退回"只靠 Tk 最上层 item"**：双向边两条线是同一线段、命中区会重叠 ⇒ 永远只选到一条（用户反馈过）。`_edge_near()` 已改为走 `_edges_near()` 取最近；同处的"再点一次"用 0.35s/3px 判双击以避开双击编辑 |
| **改画布上的 cm 读数** | `App._world_len_cm(e)`（`_draw_edges` 用） | 见 §6.7：**必须世界坐标**，否则随缩放变。`show_edge_lengths` 开关 + `label_mode` 决定显示 |
| 双击手势 | `_on_bg_double()`（按落点分派） | 节点=忽略 / 边=编辑 / Shift+空白=建节点 / 空白=只提示。<br>各分支**都要 `return "break"`**，否则会冒泡到画布层重复触发 |
| **鼠标手势（节点右键=连线）** | 节点绑定见 `_draw_nodes()` 里的 `tag_bind`；连线取点在 `_connect_pick()`；右键分派在 `_on_node_right()` | 右键节点=开始/完成连线，**Shift+右键=节点菜单**（`_on_node_menu`）。`_on_node_press` 与 `_connect_pick` 共用同一套取点逻辑；改完跑 `_guismoke` 的右键断言。**别把菜单绑回裸右键**（那就又变回"左键点不中"的老问题） |
| 改节点图形/配色 | `NODE_STYLE`、`_draw_nodes()` | 半径随 `scale` 变化，别写死 |
| **改路线配色/去程回程分色** | `ROUTE_COLOR` / `ROUTE_COLOR_BACK` / `_draw_route()` + `App.route_split`；画布过滤 `ROUTE_VIEW_MODES` / `App.route_view` / `_route_view_changed()` / `_route_split_ok()` | 分色只在"完整路线"生效；`route_split` 必须在所有设置 `self.route` 的地方一起复位，见 §6.10。**过滤只影响绘制，不改 `self.route`**；`_route_split_ok()` 为假（未分色）时只看单段 ⇒ 一段都不画 + 状态栏说明，不许瞎画 |
| 改默认视图旋转 | `ROT_DEFAULT` | 0°=恒等；底图会跟着转 |
| 改拖动约束 | `solve_drag_position()` / `_allowed_dirs()` / `DRAG_ANGLE_OFFSET` | 见 §4.3、§5；**角度判据两处要同源** |
| **改新建边/算角度的规则** | `App._auto_edge_angle()`（`create_edge_quick()` / `calc_angle_geo()` 单选 / `_calc_angle_geo_batch()` 框选批量共用）；`calc_step_geo()` / `_calc_step_geo_batch()`；常量 `DRAG_ANGLE_OFFSET` / `ANGLE_ANCHOR_TOL` / `ANGLE_SNAP_TOL`；辅助 `_norm180` / `_angdiff` / `_snap90` | 见 §6.11。**必须写"边表约定"**（水平=0/180、竖直=±90），不能直接用图上几何角；**批量必须整批先算后写、批内互不锚定**（确定性，见 §6.11）；改完跑 `_guismoke` 的角度断言 |
| 改出厂节点坐标 | `map_model.SEED_POSITIONS` / `MISSING_SEED` | 但**用户保存的布局优先级更高**，会覆盖它 |
| **改障碍惩罚/成本模型** | `MapModel.OBS` / `NAV_W_TURN`（`map_model.py`） | ⚠️ 必须与 `nav_planner.c` 的 `NavObsPenalty[]` 一致，见 §6.7；`_selftest` 第 8 节守着 |
| **改「线索路线」分支** | `map_model` 的 `p1_route` / `stageab_waypoints` / `stageab_enter_node` / `door_read_flow` / `door_back_flow` / `treasure_return_waypoints` / `door_return_home_waypoints` / `round2_waypoints`；UI 在 `map_editor._clue_route_sections`（**纯计算，无 Tk**）+ `plan_clue_route_dialog`（只搭界面） | 逐条镜像固件，见 §6.8/§6.9；改完跑 `_selftest` 第 9 节 + `_guismoke` 的线索检查。**别把计算塞回对话框里**，否则冒烟测试覆盖不到 |
| **改「线索路线」对话框的输入项/记忆** | `App.clue_route_cfg`（内存）+ `constraints.clue_route`（持久化，见 `_sync_state_to_model()` / `_apply_model_background()`）；控件取值列表在 `plan_clue_route_dialog()` 里的 `STAGES` / `P1_VALS` / `AB_VALS` / `TREASURE_VALS`（回程入口不设控件：由 4 格门灯经 `_back_door_edge()` / `_back_branch_from_edge()` 自动推；旧布局里存的 `back` 键按未知键忽略）| 配置**一律按显示字符串存**，读回时用 `_pick()` 做**成员校验**（非法就回退默认，别直接 set 进控件）。改文案会让人家存过的配置失效 → 自动回退，可接受但要知情 |
| **改「二轮路线…」（查看 + 自定义巡游顺序）** | `map_model.round2_waypoints(doors, treasure, cruise=None)` / `round2_firmware_cruise()`；UI 在 `map_editor._round2_route_sections()`（**纯计算，无 Tk**）+ `plan_round2_route_dialog()`（只搭界面）；配置 `App.round2_cfg` + `constraints.round2_route` | `cruise` 只换巡游那 4 跳；门的"多保留 N8"跟的是**巡游首站**（首站=P6 才留，= 固件的 `p6_first`），不是宝物值；⚠️ **只改软件显示/规划，固件 `get_newroute()` 的 wp 要人手同步**（顺序与固件默认不同时报告必须出告警）；跑 `_selftest` 第 11 节 + `_guismoke` 的二轮检查 |
| **改平台快速交换** | `MapModel.swap_platforms(a, b, swap_xy=False, dry_run=False)` + `MapModel.node_io_roles(name)`；界面 `App.platform_swap_dialog()` | 语义：**只改 `from`/`to`**（step/angle/flag/speed 不动），`func` 换成新名字平台的入口/出口动作；入口/出口动作**从当前地图读**（不硬编码）。`dry_run` 给对话框做预览。见 §6.12 |
| 改边表解析 | `parse_edge_table()` / `_EDGE_ROW_RE` | 保持"文本原样保留"；跑 `_selftest` 的往返断言 |
| 改宏解析 | `parse_config_macros()` / `_CExpr` | 见 §6.4 两个坑；求值器不要改回 `eval`+文本替换 |
| 加导出格式 | `MapModel.export_*()` | 保持确定性（不要输出时间戳到会被 diff 的块里） |

---

## 10. 已知限制（不要当 bug 修）

1. **图上距离 ≠ 实际长度**；`px/step` 差 500 倍，任何 K 都有一部分边违规。
2. **有 3 个节点在 `节点图.jpg` 上根本没画**：`C6 / C7 / C8`（见 `MISSING_SEED`），
   坐标只能估。精度上限 ≈ **±50px** —— 依据：把图上已画的节点当未知重解一遍，平均也偏 52px。
   （`MISSING_SEED` 里还留着 `G1 / C2 / B4` —— 当前 `enum MapNode` 已没有这三个节点，
   留着无害、便于以后重新加回来。）
3. **多边节点的角度约束常常无解**（一个节点连 ≥3 条不同方向的边），已按"放开不吸附"处理。
4. **6 条线段两方向需要的偏移相反**（`N3↔S1`/`C1↔N6`/`C1↔C2`/`N14↔S3`/`N15↔S4`/`N16↔S5`），
   在**任何单一约定**下都不可能同时对齐。
5. **`S1 = 0`** 而 `VIA_POINT=0` 是"不用途径点"哨兵 → `S1` 不能当途径点。
6. 实际地图改动（切 `C9↔P7`、加 `C10`、挪 `P7` 等）**尚未做** —— 等拓扑确定；
   工具只保证"导出文本正确"，**不保证业务自洽**。

---

## 11. 数据来源与可追溯性

- **出厂节点坐标**：`map_model.SEED_POSITIONS`（原图像素系），
  来源是当时那份节点图像素几何分析里的 `P{}` 像素表 + 换算（该脚本已随过程产物于 2026-09-26 清理）。
- **角度/长度真值**：只来自 `NavEdgeTbl[]` 与 `config.h`，**没有任何第二份数据源**。
- **布局文件**：用户拖拽的结果，存 `Node.x/y` + 底图标定 + 约束设置；**不影响固件**。
- 想要"程序算出来的路线"和固件一致 → 对照 `地图修改上位机/validate/_check_map_debug.py`。
