#!/bin/bash

# KataGo 分析服务端启动脚本
# 功能：仅提供AI分析，不处理截图和识别

cd "$(dirname "$0")"

echo "=================================================="
echo "KataGo 分析服务"
echo "=================================================="
echo "功能：仅提供AI分析，不处理截图和识别"
echo "接口：http://localhost:8001"
echo "=================================================="
echo ""

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "错误：未找到Python，请先安装Python 3.8+"
    exit 1
fi

# 启动服务端
echo "正在启动服务端..."
python katago_server.py
