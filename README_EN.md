# GoMaster

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Go AI assistant based on KataGo, supporting screenshot recognition, automatic move placement, and real-time analysis.

## Features

- **Multi-platform**: Compatible with major Go platforms: Tencent Go, Fox Go, Yicheng, OGS, Sina Go, 99Go, etc.
- **Screenshot Recognition**: Automatically recognize the game state from board screenshots
- **AI Analysis**: Real-time position analysis based on KataGo, returning recommended moves and win rates
- **Auto-play**: Support automatic mouse click simulation for move placement
- **Visualization**: Real-time display of win rates, recommended points, and other information
- **Polling Monitor**: Automatically detect board changes and intelligently determine when it's your turn

## Demo Video

### Feature Demo

**Video Download Link:** [GoMaster Demo Video](https://github.com/qiaojunsheng/gomaster/raw/main/client/screenshots/3月4日.mp4)

**Video Content:**
- Board recognition
- AI analysis
- Auto-play
- Multi-platform support

## Project Structure

```
GoMaster/
├── README.md                   # Project documentation (Chinese)
├── README_EN.md                # Project documentation (English)
├── LICENSE                     # License
├── .gitignore                  # Git ignore configuration
├── requirements.txt            # Python dependencies
├── client/                     # Client application
│   ├── go_client_new.py       # Main program
│   ├── go_coordinates.py       # Coordinate conversion
│   ├── go_board.py            # Board processing
│   ├── gbr_recognizer.py      # GBR recognition
│   ├── gbr/                   # GBR library
│   │   ├── gr/               # Board recognition algorithm
│   │   └── img/              # Recognition templates
│   ├── client_config.json     # Config file (auto-generated)
│   └── start_client.sh       # Startup script
└── server/                    # Server
    ├── katago_server.py       # Main program (FastAPI)
    ├── katago_gtp_client.py   # GTP client
    ├── go_coordinates.py      # Coordinate conversion
    ├── katago/                # KataGo engine
    │   ├── KataGo/           # KataGo source code
    │   └── weights/          # Neural network models
    └── start_server.sh        # Startup script
```

## Requirements

- Python 3.8+
- macOS / Linux / Windows
- KataGo neural network model

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/qiaojunsheng/gomaster.git
cd GoMaster
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Download KataGo model

KataGo requires a neural network model to run. Download the model file from:

- Model download: https://katagotraining.org/networks/

Place the downloaded `.bin.gz` file in the `server/katago/weights/` directory.

### 4. Start the server

```bash
cd server
python katago_server.py
```

Or use the startup script:

```bash
bash server/start_server.sh
```

The server listens on `http://localhost:8001` by default.

### 5. Start the client

```bash
cd client
python go_client_new.py
```

Or use the startup script:

```bash
bash client/start_client.sh
```

## Usage Guide

### First-time Configuration

1. Click the ☰ icon in the top right corner to open settings
2. Set "Board Region": Select the board area in the game
3. Set "Monitor Region": Select the area showing move numbers (optional)
4. Select your stone color (Black/White)
5. Click Save

### Supported Platforms

This app is compatible with the following Go platforms. Just select the board area of the corresponding platform to use:

| Platform | Description |
|----------|-------------|
| Tencent Go | Tencent official Go platform |
| Fox Go | Fox Go platform |
| Yicheng | Yicheng Go |
| OGS | Online Go Server |
| Sina Go | Sina Go platform |
| 99Go | 99Go platform |

### Interface Features

| Feature | Description |
|---------|-------------|
| Polling | Auto-detect board changes when enabled |
| Black/White | Select current player |
| Time | Slide to select AI thinking time (0-23s) |
| Board | Display visual board and recommended points |
| Wait | Simulate human thinking delay |
| Next | Manually trigger an analysis |

### Thinking Time Settings

- **Short (0-5s)**: Quick analysis, suitable for mid-game fights
- **Medium (5-15s)**: Balance between speed and accuracy
- **Long (15-23s)**: Deep analysis, suitable for endgame

### Auto-play

After enabling "Polling", the AI will automatically place moves after analysis. Beginners are recommended to turn this off first, observe AI recommendations, and then place moves manually.

## Technical Architecture

- **Client**: Python + Tkinter (GUI) + OpenCV (Image processing)
- **Server**: Python + FastAPI + KataGo
- **Communication**: HTTP REST API
- **Recognition Algorithm**: GBR (Greedy Blob Recognition)

## FAQ

### Q: Server fails to start, saying KataGo not found?

A: Make sure you have downloaded the KataGo model file and placed it in the correct location.

### Q: Client cannot connect to server?

A: Check if the server is running and ensure port 8001 is not occupied.

### Q: Board recognition is inaccurate?

A: Reconfigure the board region, ensuring the selection is complete and unobstructed.

### Q: AI endgame judgment is inaccurate?

A: Increase thinking time during endgame, or manually judge the value of endgame moves.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Issues and Pull Requests are welcome!

## Acknowledgments

- [KataGo](https://github.com/lightvector/KataGo) - Powerful open-source Go AI engine
- [GBR](https://github.com/kinfkong/igoke) - Go board recognition algorithm

## Disclaimer

This tool is for educational and research purposes only. When using this tool for online play, please comply with the terms of service of the relevant platforms. The developers are not responsible for any consequences arising from the use of this tool.