#!/bin/bash

# 围棋助手系统启动脚本
# 分别启动服务端和客户端

cd "$(dirname "$0")"

echo "=================================================="
echo "围棋助手系统"
echo "=================================================="
echo ""
echo "目录结构："
echo "  server/ - 服务端（KataGo分析）"
echo "  client/ - 客户端（截图、识别、自动落子）"
echo ""
echo "使用说明："
echo "  1. 先启动服务端: ./server/start_server.sh"
echo "  2. 再启动客户端: ./client/start_client.sh"
echo ""
echo "或者分别打开两个终端运行："
echo "  终端1: cd server && ./start_server.sh"
echo "  终端2: cd client && ./start_client.sh"
echo "=================================================="
echo ""

# 检查参数
if [ "$1" == "server" ]; then
    echo "启动服务端..."
    cd server && ./start_server.sh
elif [ "$1" == "client" ]; then
    echo "启动客户端..."
    cd client && ./start_client.sh
else
    echo "请指定要启动的组件："
    echo "  ./start_system.sh server  - 启动服务端"
    echo "  ./start_system.sh client  - 启动客户端"
    echo ""
    echo "或者直接进入对应目录启动："
    echo "  cd server && ./start_server.sh"
    echo "  cd client && ./start_client.sh"
fi
