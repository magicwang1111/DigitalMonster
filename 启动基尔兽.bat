@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "DM_PY=D:\miniconda3\pythonw.exe"
if not exist "%DM_PY%" (
  echo 未找到 Python，请编辑本文件中的 DM_PY 路径。
  pause
  exit /b 1
)
start "" "%DM_PY%" -m digitalmon.desktop
