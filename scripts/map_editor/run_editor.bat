@echo off
rem ============================================================
rem  Xunbao Map Editor  --  double-click this file to open
rem  寻宝地图编辑器：双击本文件即可打开（不会弹命令行窗口）
rem
rem  Uses pythonw.exe so no console window appears.
rem  If nothing happens after double-clicking, run
rem  "run_editor_console.bat" instead to see the error message.
rem ============================================================
cd /d "%~dp0"
start "" pythonw.exe "%~dp0map_editor.py"
