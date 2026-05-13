#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "进入目录: $SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "创建虚拟环境 .venv ..."
  python3 -m venv .venv
else
  echo ".venv 已存在，跳过创建。"
fi

echo "激活虚拟环境..."
source ".venv/bin/activate"

echo "安装依赖..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "安装完成。"
echo "下一步：双击“Mac启动.command”，在网页里填写 API Key。"
read -r -p "按回车键退出..."
