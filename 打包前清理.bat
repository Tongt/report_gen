@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo 将执行打包前清理：
echo 1) 删除 API Key 文件：.env、config\user_settings.json
echo 2) 删除本地虚拟环境：.venv
echo 3) 删除历史报告：outputs\*.md
echo 4) 清空知识库资料：knowledge_base\raw_uploads\*
echo 5) 清空向量库数据：knowledge_base\chroma_db\*
echo 6) 删除缓存目录：__pycache__、.pytest_cache、.mypy_cache
echo.
set /p CONFIRM=确认继续？(y/N):

if /I not "%CONFIRM%"=="Y" (
  echo 已取消。
  pause
  exit /b 0
)

if exist ".env" del /f /q ".env"
if exist "config\user_settings.json" del /f /q "config\user_settings.json"
if exist ".venv" rmdir /s /q ".venv"
if exist "outputs\*.md" del /f /q "outputs\*.md"
if exist "knowledge_base\raw_uploads\*" del /f /q "knowledge_base\raw_uploads\*"
if exist "knowledge_base\chroma_db" rmdir /s /q "knowledge_base\chroma_db"
mkdir "knowledge_base\chroma_db" >nul 2>nul
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist ".pytest_cache" rmdir /s /q ".pytest_cache"
if exist ".mypy_cache" rmdir /s /q ".mypy_cache"

for /d /r %%D in (__pycache__) do @if exist "%%D" rmdir /s /q "%%D"

echo.
echo 清理完成，可以安全打包。
pause
