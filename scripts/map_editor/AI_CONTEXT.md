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
| `_guismoke.py` | 界面冒烟测试（68 项），**全程沙箱，绝不碰真实布局** | 见 §7 隔离规则 |
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

---

## 8. 测试怎么跑 / 期望结果

```bash
# 在仓库根执行
python scripts/map_editor/_selftest.py     # 期望：全部通过，exit 0
python scripts/map_editor/_guismoke.py     # 期望：68 项 [OK] / 0 FAIL

# 改 map_model.py 后额外跑（确认没碰坏既有工具链）
python scripts/validate/_weight_calib.py   # 15/15
python scripts/validate/_check_csr.py
python scripts/validate/_check_map_debug.py
python scripts/validate/_check_door_perm.py
```

**`_guismoke.py` 覆盖**：画布尺寸/缩放、**工具栏两行且不溢出**、底图载入、
布局保存/载入（沙箱 + 真实 SHA256 不变）、底图反推标定、拖动约束（引导线角度 =
表里 angle + 偏移、矛盾时放开不吸附）、**点图形选边（命中区）**、**连线模式点两下建边**、
Delete 删边、校验面板、路线规划、6 类导出、节点增删/恢复、滚轮缩放。

---

## 9. 常见改动怎么做

| 想改什么 | 改哪里 | 注意 |
|---------|-------|------|
| 工具栏加/改控件 | `App._build_toolbar()` 的 `row1` / `row2` / `row3` | **三行**，最宽约 1163px，`minsize` 1200×720；`_guismoke` 有"≥3 行且不溢出"断言 |
| **边列表展示模式** | `App.edge_view` + `_fill_edges_merged()` + `_apply_edge_columns()` | 三种模式：合并双向(默认,每线段一行,两方向并列) / 逐条 / 只看双向。<br>**树 iid 有两种前缀**：`e:A->B`（单行）与 `b:A<->B`（合并行）——改 `_on_tree_edge_select` / `_tree_select` 时必须同时兼容，否则选中会失效 |
| **拖动吸附** | `snap_mode` / `snap_tol` / `snap_near` + `_edge_pref_dirs()` + `solve_drag_position()` | 见 §4.3：**按范围确定性吸附**，别用权重实现 |
| 改边的命中区宽度 | `EDGE_HIT_WIDTH`（默认 14px） | 命中线是 `fill=""` 的粗线，**必须**放进 `_canvas_items[tag]` 才有绑定 |
| 双击手势 | `_on_bg_double()`（按落点分派） | 节点=忽略 / 边=编辑 / Shift+空白=建节点 / 空白=只提示。<br>各分支**都要 `return "break"`**，否则会冒泡到画布层重复触发 |
| 改节点图形/配色 | `NODE_STYLE`、`_draw_nodes()` | 半径随 `scale` 变化，别写死 |
| 改默认视图旋转 | `ROT_DEFAULT` | 0°=恒等；底图会跟着转 |
| 改拖动约束 | `solve_drag_position()` / `_allowed_dirs()` / `DRAG_ANGLE_OFFSET` | 见 §4.3、§5；**角度判据两处要同源** |
| 改出厂节点坐标 | `map_model.SEED_POSITIONS` / `MISSING_SEED` | 但**用户保存的布局优先级更高**，会覆盖它 |
| 改边表解析 | `parse_edge_table()` / `_EDGE_ROW_RE` | 保持"文本原样保留"；跑 `_selftest` 的往返断言 |
| 改宏解析 | `parse_config_macros()` / `_CExpr` | 见 §6.4 两个坑；求值器不要改回 `eval`+文本替换 |
| 加导出格式 | `MapModel.export_*()` | 保持确定性（不要输出时间戳到会被 diff 的块里） |

---

## 10. 已知限制（不要当 bug 修）

1. **图上距离 ≠ 实际长度**；`px/step` 差 500 倍，任何 K 都有一部分边违规。
2. **6 个节点在 `节点图.jpg` 上根本没画**：`C2 / B4 / C6 / C7 / C8 / G1`（见 `MISSING_SEED`），
   坐标只能估。精度上限 ≈ **±50px** —— 依据：把图上已画的节点当未知重解一遍，平均也偏 52px。
3. **多边节点的角度约束常常无解**（一个节点连 ≥3 条不同方向的边），已按"放开不吸附"处理。
4. **6 条线段两方向需要的偏移相反**（`N3↔S1`/`C1↔N6`/`C1↔C2`/`N14↔S3`/`N15↔S4`/`N16↔S5`），
   在**任何单一约定**下都不可能同时对齐。
5. **`S1 = 0`** 而 `VIA_POINT=0` 是"不用途径点"哨兵 → `S1` 不能当途径点。
6. 实际地图改动（切 `C9↔P7`、加 `C10`、挪 `P7` 等）**尚未做** —— 等拓扑确定；
   工具只保证"导出文本正确"，**不保证业务自洽**。

---

## 11. 数据来源与可追溯性

- **出厂节点坐标**：`map_model.SEED_POSITIONS`（原图像素系），
  来源是仓库既有的 `scripts/analyze/analyze_turn_comp_map_geom.py` 里的 `P{}` 像素表 + 换算。
- **角度/长度真值**：只来自 `NavEdgeTbl[]` 与 `config.h`，**没有任何第二份数据源**。
- **布局文件**：用户拖拽的结果，存 `Node.x/y` + 底图标定 + 约束设置；**不影响固件**。
- 想要"程序算出来的路线"和固件一致 → 对照 `scripts/validate/_check_map_debug.py`。
