# GoMaster / 围棋助手

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

基于 KataGo 的围棋 AI 助手，支持截图识别、自动落子和实时分析。

A Go AI assistant based on KataGo, supporting screenshot recognition, automatic move placement, and real-time analysis.

## 功能特点 / Features

- **多平台支持 / Multi-platform**: 兼容腾讯围棋、野狐围棋、弈城、OGS、新浪围棋、99围棋等主流对弈平台
  - Compatible with major Go platforms: Tencent Go, Fox Go, Yicheng, OGS, Sina Go, 99Go, etc.
- **截图识别 / Screenshot Recognition**: 自动识别棋盘截图中的棋局状态
  - Automatically recognize the game state from board screenshots
- **AI 分析 / AI Analysis**: 基于 KataGo 进行实时局面分析，返回推荐落子和胜率
  - Real-time position analysis based on KataGo, returning recommended moves and win rates
- **自动落子 / Auto-play**: 支持自动模拟鼠标落子操作
  - Support automatic mouse click simulation for move placement
- **可视化 / Visualization**: 实时显示胜率、推荐点等信息
  - Real-time display of win rates, recommended points, and other information
- **轮巡监控 / Polling Monitor**: 自动检测棋盘变化，智能判断是否轮到自己
  - Automatically detect board changes and intelligently determine when it's your turn

## 演示视频 / Demo Video

### 功能演示

[![GoMaster 功能演示](https://img.youtube.com/vi/dQw4w9WgXcQ/0.jpg)](https://github.com/qiaojunsheng/gomaster/blob/main/client/screenshots/3月4日.mp4)

点击上方图片观看演示视频，展示 GoMaster 的主要功能：
- 棋盘识别
- AI 分析
- 自动落子
- 多平台支持

Click the image above to watch the demo video, showcasing GoMaster's main features:
- Board recognition
- AI analysis
- Auto-play
- Multi-platform support

## 项目结构 / Project Structure

```
GoMaster/
├── README.md                   # 项目说明文档 / Project documentation
├── LICENSE                     # 许可证 / License
├── .gitignore                  # Git忽略配置 / Git ignore configuration
├── requirements.txt            # Python依赖 / Python dependencies
├── client/                     # 客户端应用 / Client application
│   ├── go_client_new.py       # 主程序 / Main program
│   ├── go_coordinates.py       # 坐标转换 / Coordinate conversion
│   ├── go_board.py            # 棋盘处理 / Board processing
│   ├── gbr_recognizer.py      # GBR识别 / GBR recognition
│   ├── gbr/                   # GBR库 / GBR library
│   │   ├── gr/               # 棋盘识别算法 / Board recognition algorithm
│   │   └── img/              # 识别模板 / Recognition templates
│   ├── client_config.json     # 配置文件（自动生成）/ Config file (auto-generated)
│   └── start_client.sh       # 启动脚本 / Startup script
└── server/                    # 服务端 / Server
    ├── katago_server.py       # 主程序（FastAPI）/ Main program (FastAPI)
    ├── katago_gtp_client.py   # GTP客户端 / GTP client
    ├── go_coordinates.py      # 坐标转换 / Coordinate conversion
    ├── katago/                # KataGo引擎 / KataGo engine
    │   ├── KataGo/           # KataGo源码 / KataGo source code
    │   └── weights/          # 神经网络模型 / Neural network models
    └── start_server.sh        # 启动脚本 / Startup script
```

## 环境要求 / Requirements

- Python 3.8+
- macOS / Linux / Windows
- KataGo 神经网络模型 / KataGo neural network model

## 安装部署 / Installation

### 1. 克隆项目 / Clone the repository

```bash
git clone https://github.com/qiaojunsheng/gomaster.git
cd GoMaster
```

### 2. 安装 Python 依赖 / Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. 下载 KataGo 模型 / Download KataGo model

KataGo 需要神经网络模型才能运行。从以下地址下载模型文件：

KataGo requires a neural network model to run. Download the model file from:

- KataGo 模型下载 / Model download: https://katagotraining.org/networks/

将下载的 `.bin.gz` 文件放到 `server/katago/weights/` 目录。

Place the downloaded `.bin.gz` file in the `server/katago/weights/` directory.

### 4. 启动服务端 / Start the server

```bash
cd server
python katago_server.py
```

或使用启动脚本 / Or use the startup script:

```bash
bash server/start_server.sh
```

服务端默认监听 `http://localhost:8001`

The server listens on `http://localhost:8001` by default.

### 5. 启动客户端 / Start the client

```bash
cd client
python go_client_new.py
```

或使用启动脚本 / Or use the startup script:

```bash
bash client/start_client.sh
```

## 使用说明 / Usage Guide

### 首次配置 / First-time Configuration

1. 点击界面右上角的 ☰ 图标打开设置
   - Click the ☰ icon in the top right corner to open settings
2. 设置"棋盘区域"：框选游戏中棋盘区域
   - Set "Board Region": Select the board area in the game
3. 设置"监控区域"：框选显示手数的区域（可选）
   - Set "Monitor Region": Select the area showing move numbers (optional)
4. 选择你的棋子颜色（黑/白）
   - Select your stone color (Black/White)
5. 点击保存
   - Click Save

### 支持的平台 / Supported Platforms

本应用兼容以下对弈平台，只需框选对应平台的棋盘区域即可使用：

This app is compatible with the following Go platforms. Just select the board area of the corresponding platform to use:

| 平台 / Platform | 说明 / Description |
|----------------|-------------------|
| 腾讯围棋 / Tencent Go | 腾讯官方围棋对弈平台 / Tencent official Go platform |
| 野狐围棋 / Fox Go | 野狐围棋对弈平台 / Fox Go platform |
| 弈城 / Yicheng | 弈城围棋 / Yicheng Go |
| OGS | Online Go Server |
| 新浪围棋 / Sina Go | 新浪围棋对弈平台 / Sina Go platform |
| 99围棋 / 99Go | 99围棋平台 / 99Go platform |

### 界面功能 / Interface Features

| 功能 / Feature | 说明 / Description |
|---------------|-------------------|
| 轮巡 / Polling | 开启后自动检测棋盘变化 / Auto-detect board changes when enabled |
| 黑/白 / Black/White | 选择当前下棋方 / Select current player |
| 时间 / Time | 滑动选择AI思考时间（0-23秒）/ Slide to select AI thinking time (0-23s) |
| 棋盘 / Board | 显示可视化棋盘和推荐点 / Display visual board and recommended points |
| 等待 / Wait | 模拟人类思考延迟 / Simulate human thinking delay |
| 下一步 / Next | 手动触发一次分析 / Manually trigger an analysis |

### 计算时间设置 / Thinking Time Settings

- **短时间 / Short (0-5秒)**: 快速分析，适合中盘战斗 / Quick analysis, suitable for mid-game fights
- **中等时间 / Medium (5-15秒)**: 平衡分析速度和精度 / Balance between speed and accuracy
- **长时间 / Long (15-23秒)**: 深度分析，适合官子阶段 / Deep analysis, suitable for endgame

### 自动落子 / Auto-play

开启"轮巡"后，AI 分析完成会自动执行落子。建议初学者先关闭，观察 AI 推荐后再手动落子。

After enabling "Polling", the AI will automatically place moves after analysis. Beginners are recommended to turn this off first, observe AI recommendations, and then place moves manually.

## 技术架构 / Technical Architecture

- **客户端 / Client**: Python + Tkinter (GUI) + OpenCV (图像处理 / Image processing)
- **服务端 / Server**: Python + FastAPI + KataGo
- **通信 / Communication**: HTTP REST API
- **识别算法 / Recognition Algorithm**: GBR (Greedy Blob Recognition)

## 常见问题 / FAQ

### Q: 服务端启动失败，提示找不到 KataGo？
### Q: Server fails to start, saying KataGo not found?

A: 确保已下载 KataGo 模型文件并放到正确位置。
   - Make sure you have downloaded the KataGo model file and placed it in the correct location.

### Q: 客户端连接不上服务端？
### Q: Client cannot connect to server?

A: 检查服务端是否已启动，确保端口 8001 未被占用。
   - Check if the server is running and ensure port 8001 is not occupied.

### Q: 棋盘识别不准确？
### Q: Board recognition is inaccurate?

A: 重新设置棋盘区域，确保框选完整且无遮挡。
   - Reconfigure the board region, ensuring the selection is complete and unobstructed.

### Q: AI 收官阶段判断不准确？
### Q: AI endgame judgment is inaccurate?

A: 收官阶段建议增加计算时间，或手动判断官子价值。
   - Increase thinking time during endgame, or manually judge the value of endgame moves.

## 许可证 / License

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 贡献指南 / Contributing

欢迎提交 Issue 和 Pull Request！

Issues and Pull Requests are welcome!

## 致谢 / Acknowledgments

- [KataGo](https://github.com/lightvector/KataGo) - 强大的开源围棋 AI 引擎 / Powerful open-source Go AI engine
- [GBR](https://github.com/kinfkong/igoke) - 围棋棋盘识别算法 / Go board recognition algorithm

## 免责声明 / Disclaimer

本工具仅供学习和研究使用。使用本工具进行在线对弈时，请遵守相关平台的使用条款。开发者不对因使用本工具而产生的任何后果负责。

This tool is for educational and research purposes only. When using this tool for online play, please comply with the terms of service of the relevant platforms. The developers are not responsible for any consequences arising from the use of this tool.
