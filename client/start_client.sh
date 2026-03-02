#!/bin/bash

# 围棋助手客户端启动脚本
# 功能：截图、配置、GBR识别、自动落子

cd "$(dirname "$0")"

echo "=================================================="
echo "围棋助手客户端"
echo "=================================================="
echo "功能：截图、配置、GBR识别、自动落子"
echo "服务端：http://localhost:8001"
echo "=================================================="
echo ""

# 检查Python环境
if ! command -v python &> /dev/null; then
    echo "错误：未找到Python，请先安装Python 3.8+"
    exit 1
fi

# 启动客户端
echo "正在启动客户端..."
python go_client_new.py
