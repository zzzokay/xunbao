@echo off
rem ============================================================
rem  Xunbao Map Editor (console version, for troubleshooting)
rem  Run this one when run_editor.bat does nothing - errors
rem  pythonw.exe swallows are printed here.
rem
rem  KEEP THIS FILE PURE ASCII. cmd.exe reads .bat in the OEM
rem  code page (936 on this machine), so any non-ASCII byte
rem  (e.g. a hardcoded "map editor" folder name) is decoded as
rem  garbage and the batch parser breaks mid-line. That was the
rem  2026-09-25 bug.
rem ============================================================

set "EDITOR_DIR="
if exist "%~dp0map_editor\map_editor.py" set "EDITOR_DIR=%~dp0map_editor"
if not defined EDITOR_DIR if exist "%~dp0..\map_editor\map_editor.py" set "EDITOR_DIR=%~dp0..\map_editor"
if not defined EDITOR_DIR for /d %%D in ("%USERPROFILE%\Desktop\MC_32\robotcup\xunbao\*") do if exist "%%D\map_editor\map_editor.py" set "EDITOR_DIR=%%D\map_editor"

if not defined EDITOR_DIR (
  echo.
  echo [run_editor] map_editor\map_editor.py not found.
  echo   looked next to this script, one level up, and under
  echo   %USERPROFILE%\Desktop\MC_32\robotcup\xunbao\*\map_editor
  echo.
  pause
  exit /b 1
)

python.exe "%EDITOR_DIR%\map_editor.py" %*
echo.
echo ============================================
echo  Editor closed (exit code %ERRORLEVEL%).
echo ============================================
pause
