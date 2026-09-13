@echo off
rem ============================================================
rem  Xunbao Map Editor (console version, for troubleshooting)
rem  寻宝地图编辑器（带命令行窗口版）：双击本文件，
rem  窗口里会打印启动信息；出错时能直接看到报错。
rem ============================================================
cd /d "%~dp0"
python.exe "%~dp0map_editor.py" %*
echo.
echo ============================================
echo  Editor closed.  If there was an error above,
echo  please copy it and send it back.
echo  编辑器已退出。若上面有报错，请复制发我。
echo ============================================
pause
