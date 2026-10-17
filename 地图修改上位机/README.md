# 地图修改上位机

寻宝小车地图编辑工具。双击 `run_editor.bat` 启动编辑器。

## 快速开始

1. 双击 **`run_editor.bat`** — 打开地图编辑器
2. 看 **`map_editor/README.md`** — 使用说明
3. 两套布局想对账 / 把一套的参数搬到另一套：编辑器左栏「**⇋ JSON 对比…**」
   （对比 + 按选择迁移，迁移前自动存快照；见 `map_editor/README.md` §4.5.1）

## 目录结构

```
地图修改上位机/
├── run_editor.bat          ← 启动编辑器（可复制到桌面）
├── map_editor/             ← 编辑器主体
│   ├── README.md           ← 使用说明
│   ├── AI_CONTEXT.md       ← AI 参考文档
│   ├── map_editor.py       ← 主程序
│   ├── map_model.py        ← 核心模型
│   ├── run_editor.bat / run_editor_console.bat  ← 启动器（带 / 不带控制台窗口两种）
│   ├── layouts/            ← 保存的布局
│   └── backups/            ← 写回固件时的自动备份
├── validate/               ← 上真车前的校验脚本（改边/改门逻辑后必跑）
├── tools/                  ← 可复用诊断脚本（按需跑；清单与用途见 tools/README.md）
└── reports/                ← AI 过程产物（分析报告/方案/日志；可随时清空，平时不用看）
```

> 本目录原先在仓库根 `scripts/` 下，后整体迁移到这里（见 git 提交"新增地图修改器"）。
> `项目讲解文档/README.md` §9 里 2026-09-26 之前的日志条目仍写旧路径，实际路径以上表为准。

## 相关文件

编辑器读取/修改的固件文件：
- `Navigation/map_message.c` — 边表 `NavEdgeTbl[]`
- `Navigation/map.h` — 节点枚举 `enum MapNode`
- `Mission/config.h` — 宏定义（`LEN_*`、`ANGLE_*`、`DOOR_LEN_*`、`TURN_CALC_ENABLE`、
  **`ROUND2_CRUISE_CW_*` / `ROUND2_CRUISE_CCW_*`** = 第二轮巡游顺序，宝物≠6 / =6 各一组）
- `Mission/barrier.c` — **门区状态机 `door()` 的触发链**（lastNode→nowNode ⇒ DoorState；
  编辑器从画布空白处**右键 →「🚧 门区状态表…」**查看/修改触发边并写回，写回自动备份）
- `Mission/mission_planner.c` — **door_zone[8][2] 门区禁用边**（与触发链同步管理；
  上位机门区回程/BACK 门识别都从这两个文件解析，固件改了自动跟上）
- `Navigation/map.c` — **转弯前补偿**两张表（`kTurnTbl[]` / `GetForwardDistanceBeforeGyroTurn`）
  + 公式参数 `TURN_L_PIVOT` / `TURN_GATE_CM` / `TURN_D_*`。入口：编辑器左栏
  「转弯补偿 / 显示:」那一行的「⟲ 转弯补偿…」（原理见 `项目讲解文档/project_reference.md` §14）
  ⚠️ 这两张表 + 公式参数**随「保存布局 / 另存为」存进布局 JSON**；点「重新载入源码」会重置回上面的源码值。

> 📌 **2026-10-07：编辑器左栏不再有节点表和边表**（原节点表 → 转弯补偿表，边表 → 整块删除）。
> 选节点/选边都在**画布上点**或用**右键菜单**；`⇄ 平台交换…` / `⟲ 转弯补偿…` 挪到了
> 左栏「转弯补偿 / 显示:」那一行。详见 `map_editor/README.md` §5。
