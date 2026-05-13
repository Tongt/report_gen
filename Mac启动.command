#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "未找到 .venv，请先双击“Mac第一次安装.command”完成安装。"
  read -r -p "按回车键退出..."
  exit 1
fi

source ".venv/bin/activate"

echo "正在启动五看五定智能体..."
streamlit run app.py &
STREAMLIT_PID=$!

sleep 3
open "http://localhost:8501"

wait $STREAMLIT_PID
