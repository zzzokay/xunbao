# 地图修改上位机

寻宝小车地图编辑工具。双击 `run_editor.bat` 启动编辑器。

## 快速开始

1. 双击 **`run_editor.bat`** — 打开地图编辑器
2. 看 **`map_editor/README.md`** — 使用说明

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
- `Mission/config.h` — 宏定义（`LEN_*`、`ANGLE_*`、`DOOR_LEN_*`、`TURN_CALC_ENABLE`）
- `Navigation/map.c` — **转弯前补偿**两张表（`kTurnTbl[]` / `GetForwardDistanceBeforeGyroTurn`）
  + 公式参数 `TURN_L_PIVOT` / `TURN_GATE_CM` / `TURN_D_*`。入口：编辑器左栏
  「⟲ 转弯补偿…」（原理见 `项目讲解文档/project_reference.md` §14）
