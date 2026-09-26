@echo off
rem ============================================================
rem  Xunbao Map Editor - double-click to launch
rem  Uses pythonw.exe so no console window appears.
rem
rem  KEEP THIS FILE PURE ASCII. cmd.exe reads .bat in the OEM
rem  code page (936 on this machine), so any non-ASCII byte
rem  (e.g. a hardcoded "map editor" folder name) is decoded as
rem  garbage, the path stops resolving, and pythonw.exe dies
rem  silently with no window. That was the 2026-09-25 bug.
rem ============================================================

set "EDITOR_DIR="
if exist "%~dp0map_editor\map_editor.py" set "EDITOR_DIR=%~dp0map_editor"
if not defined EDITOR_DIR for /d %%D in ("%USERPROFILE%\Desktop\MC_32\robotcup\xunbao\*") do if exist "%%D\map_editor\map_editor.py" set "EDITOR_DIR=%%D\map_editor"

if not defined EDITOR_DIR (
  echo.
  echo [run_editor] map_editor\map_editor.py not found.
  echo   looked next to this script: %~dp0map_editor
  echo   looked under: %USERPROFILE%\Desktop\MC_32\robotcup\xunbao\*\map_editor
  echo.
  pause
  exit /b 1
)

start "" pythonw.exe "%EDITOR_DIR%\map_editor.py"
