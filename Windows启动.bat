@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

if not exist ".venv" (
  echo 未找到 .venv，请先双击“Windows第一次安装.bat”完成安装。
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"

echo 正在启动五看五定智能体...
start "" "http://localhost:8501"
streamlit run app.py
