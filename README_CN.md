# GoMaster / 围棋助手

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

基于 KataGo 的围棋 AI 助手，支持截图识别、自动落子和实时分析。

## 功能特点

- **多平台支持**: 兼容腾讯围棋、野狐围棋、弈城、OGS、新浪围棋、99围棋等主流对弈平台
- **截图识别**: 自动识别棋盘截图中的棋局状态
- **AI 分析**: 基于 KataGo 进行实时局面分析，返回推荐落子和胜率
- **自动落子**: 支持自动模拟鼠标落子操作
- **可视化**: 实时显示胜率、推荐点等信息
- **轮巡监控**: 自动检测棋盘变化，智能判断是否轮到自己

## 演示视频

### 功能演示

**视频下载链接：** [GoMaster 功能演示](https://github.com/qiaojunsheng/gomaster/raw/main/client/screenshots/3月4日.mp4)

**视频内容：**
- 棋盘识别
- AI 分析
- 自动落子
- 多平台支持

## 项目结构

```
GoMaster/
├── README.md                   # 项目说明文档（主文件）
├── README_CN.md                # 项目说明文档（中文）
├── README_EN.md                # 项目说明文档（英文）
├── LICENSE                     # 许可证
├── .gitignore                  # Git忽略配置
├── requirements.txt            # Python依赖
├── client/                     # 客户端应用
│   ├── go_client_new.py       # 主程序
│   ├── go_coordinates.py       # 坐标转换
│   ├── go_board.py            # 棋盘处理
│   ├── gbr_recognizer.py      # GBR识别
│   ├── gbr/                   # GBR库
│   │   ├── gr/               # 棋盘识别算法
│   │   └── img/              # 识别模板
│   ├── client_config.json     # 配置文件（自动生成）
│   └── start_client.sh       # 启动脚本
└── server/                    # 服务端
    ├── katago_server.py       # 主程序（FastAPI）
    ├── katago_gtp_client.py   # GTP客户端
    ├── go_coordinates.py      # 坐标转换
    ├── katago/                # KataGo引擎
    │   ├── KataGo/           # KataGo源码
    │   └── weights/          # 神经网络模型
    └── start_server.sh        # 启动脚本
```

## 环境要求

- Python 3.8+
- macOS / Linux / Windows
- KataGo 神经网络模型

## 安装部署

### 1. 克隆项目

```bash
git clone https://github.com/qiaojunsheng/gomaster.git
cd GoMaster
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 下载 KataGo 模型

KataGo 需要神经网络模型才能运行。从以下地址下载模型文件：

- KataGo 模型下载：https://katagotraining.org/networks/

将下载的 `.bin.gz` 文件放到 `server/katago/weights/` 目录。

### 4. 启动服务端

```bash
cd server
python katago_server.py
```

或使用启动脚本：

```bash
bash server/start_server.sh
```

服务端默认监听 `http://localhost:8001`

### 5. 启动客户端

```bash
cd client
python go_client_new.py
```

或使用启动脚本：

```bash
bash client/start_client.sh
```

## 使用说明

### 首次配置

1. 点击界面右上角的 ☰ 图标打开设置
2. 设置"棋盘区域"：框选游戏中棋盘区域
3. 设置"监控区域"：框选显示手数的区域（可选）
4. 选择你的棋子颜色（黑/白）
5. 点击保存

### 支持的平台

本应用兼容以下对弈平台，只需框选对应平台的棋盘区域即可使用：

| 平台 | 说明 |
|------|------|
| 腾讯围棋 | 腾讯官方围棋对弈平台 |
| 野狐围棋 | 野狐围棋对弈平台 |
| 弈城 | 弈城围棋 |
| OGS | Online Go Server |
| 新浪围棋 | 新浪围棋对弈平台 |
| 99围棋 | 99围棋平台 |

### 界面功能

| 功能 | 说明 |
|------|------|
| 轮巡 | 开启后自动检测棋盘变化 |
| 黑/白 | 选择当前下棋方 |
| 时间 | 滑动选择AI思考时间（0-23秒） |
| 棋盘 | 显示可视化棋盘和推荐点 |
| 等待 | 模拟人类思考延迟 |
| 下一步 | 手动触发一次分析 |

### 计算时间设置

- **短时间 (0-5秒)**: 快速分析，适合中盘战斗
- **中等时间 (5-15秒)**: 平衡分析速度和精度
- **长时间 (15-23秒)**: 深度分析，适合官子阶段

### 自动落子

开启"轮巡"后，AI 分析完成会自动执行落子。建议初学者先关闭，观察 AI 推荐后再手动落子。

## 技术架构

- **客户端**: Python + Tkinter (GUI) + OpenCV (图像处理)
- **服务端**: Python + FastAPI + KataGo
- **通信**: HTTP REST API
- **识别算法**: GBR (Greedy Blob Recognition)

## 常见问题

### Q: 服务端启动失败，提示找不到 KataGo？

A: 确保已下载 KataGo 模型文件并放到正确位置。

### Q: 客户端连接不上服务端？

A: 检查服务端是否已启动，确保端口 8001 未被占用。

### Q: 棋盘识别不准确？

A: 重新设置棋盘区域，确保框选完整且无遮挡。

### Q: AI 收官阶段判断不准确？

A: 收官阶段建议增加计算时间，或手动判断官子价值。

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 致谢

- [KataGo](https://github.com/lightvector/KataGo) - 强大的开源围棋 AI 引擎
- [GBR](https://github.com/kinfkong/igoke) - 围棋棋盘识别算法

## 免责声明

本工具仅供学习和研究使用。使用本工具进行在线对弈时，请遵守相关平台的使用条款。开发者不对因使用本工具而产生的任何后果负责。