@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"
echo 当前目录: %cd%

if not exist ".venv" (
  echo 创建虚拟环境 .venv ...
  py -3 -m venv .venv
) else (
  echo .venv 已存在，跳过创建。
)

echo 激活虚拟环境...
call ".venv\Scripts\activate.bat"

echo 安装依赖...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo 安装完成。
echo 下一步：双击“Windows启动.bat”，在网页里填写 API Key
pause
