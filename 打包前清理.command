#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "将执行打包前清理："
echo "1) 删除 API Key 文件：.env、config/user_settings.json"
echo "2) 删除本地虚拟环境：.venv"
echo "3) 删除历史报告：outputs/*.md"
echo "4) 清空知识库资料：knowledge_base/raw_uploads/*"
echo "5) 清空向量库数据：knowledge_base/chroma_db/*"
echo "6) 删除缓存目录：__pycache__、.pytest_cache、.mypy_cache"
echo ""
read -r -p "确认继续？(y/N): " CONFIRM

if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo "已取消。"
  exit 0
fi

rm -f .env
rm -f config/user_settings.json
rm -rf .venv
rm -f outputs/*.md
rm -rf knowledge_base/raw_uploads/*
rm -rf knowledge_base/chroma_db/*
rm -rf __pycache__
rm -rf .pytest_cache
rm -rf .mypy_cache

# 清理常见子目录缓存
find . -type d -name "__pycache__" -prune -exec rm -rf {} +

echo ""
echo "清理完成，可以安全打包。"
read -r -p "按回车键退出..."
