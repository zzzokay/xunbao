# 地图修改上位机

寻宝小车地图编辑工具。双击 `run_editor.bat` 启动编辑器。

## 快速开始

1. 双击 **`run_editor.bat`** — 打开地图编辑器
2. 看 **`map_editor/README.md`** — 使用说明

## 目录结构

```
地图修改上位机/
├── run_editor.bat          ← 启动编辑器（可复制到桌面）
├── run_editor_console.bat  ← 带命令行窗口版（出错时看报错）
├── map_editor/             ← 编辑器主体
│   ├── README.md           ← 使用说明
│   ├── AI_CONTEXT.md       ← AI 参考文档
│   ├── map_editor.py       ← 主程序
│   ├── map_model.py        ← 核心模型
│   ├── layouts/            ← 保存的布局
│   └── backups/            ← 写回固件时的自动备份
├── validate/               ← 上真车前的校验脚本
└── analyze/                ← 诊断/分析脚本
```

## 相关文件

编辑器读取/修改的固件文件：
- `Navigation/map_message.c` — 边表 `NavEdgeTbl[]`
- `Mission/config.h` — 宏定义（`LEN_*`、`ANGLE_*`、`DOOR_LEN_*`）
- `Mission/map.h` — 节点枚举 `enum MapNode`
