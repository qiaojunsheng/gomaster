#!/usr/bin/env python3
"""
KataGo 分析服务端
仅负责接收棋盘状态，调用KataGo分析，返回推荐落子
"""

import json
import os
import sys
import time
import threading
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from katago_gtp_client import KataGoGTPClient

app = FastAPI(title="KataGo 分析服务", version="2.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 数据模型 ============

class StonePosition(BaseModel):
    """棋子位置"""
    x: int
    y: int


class BoardState(BaseModel):
    """棋盘状态"""
    black: List[StonePosition]
    white: List[StonePosition]
    board_size: int = 19


class AnalyzeRequest(BaseModel):
    """分析请求"""
    stones: Dict[str, List[Dict[str, int]]]  # {'black': [{'x':0,'y':0},...], 'white': [...]}
    current_color: str = "B"  # 'B' 或 'W'
    max_time: float = 10.0
    max_visits: Optional[int] = None
    avoid_positions: Optional[List[Dict[str, int]]] = None  # 打劫时需要排除的位置
    playout_doubling_advantage: Optional[float] = None  # 必须在 -3 到 3 范围内
    fast_mode: bool = False  # 快棋模式：只返回最佳落子，不进行胜率分析


class AnalyzeResponse(BaseModel):
    """分析响应"""
    success: bool
    recommended_move: Optional[str] = None
    recommended_moves: Optional[List[Dict]] = None  # 多个推荐落子（用于显示候选点）
    win_rate: Optional[float] = None
    visits: Optional[int] = None
    message: Optional[str] = None
    analysis_time: float = 0.0


# ============ 服务端状态 ============

class ServerState:
    def __init__(self):
        self.katago_client: Optional[KataGoGTPClient] = None
        self.is_ready = False
        self.lock = threading.Lock()
        # 缓存棋盘状态用于增量更新
        self.last_stones: Optional[Dict[str, List[Dict[str, int]]]] = None
        self.last_max_time: Optional[float] = None
        self.current_model: Optional[str] = None
        
    def get_available_models(self) -> List[Dict[str, str]]:
        """获取可用模型列表"""
        base_dir = Path(__file__).parent
        weights_dir = base_dir / 'katago' / 'weights'
        models = []
        if weights_dir.exists():
            for f in sorted(weights_dir.glob('*.bin.gz')):
                models.append({
                    'name': f.name,
                    'path': str(f),
                    'display': f.name.replace('kata1-', '').replace('.bin.gz', '')
                })
        return models
        
    def _get_b28_model(self, models: List[Dict[str, str]]) -> Dict[str, str]:
        """获取b28模型，如果没有则返回b18，再没有则返回第一个"""
        for m in models:
            if 'b28' in m['name']:
                return m
        # 如果没有找到b28，找b18
        for m in models:
            if 'b18' in m['name']:
                return m
        # 如果都没有，返回第一个
        if models:
            return models[0]
        raise Exception("没有找到可用的模型文件")
        
    def initialize(self, model_name: Optional[str] = None):
        """初始化KataGo客户端"""
        try:
            print("正在初始化 KataGo...")
            # 获取配置路径
            base_dir = Path(__file__).parent
            katago_path = base_dir / 'katago' / 'KataGo' / 'cpp' / 'build' / 'katago'
            config_path = base_dir / 'katago' / 'KataGo' / 'cpp' / 'configs' / 'gtp_example.cfg'
            
            # 获取可用模型
            available_models = self.get_available_models()
            if not available_models:
                raise Exception("没有找到可用的模型文件")
            
            # 选择模型
            if model_name:
                # 查找指定模型
                selected_model = None
                for m in available_models:
                    if m['name'] == model_name or model_name in m['name']:
                        selected_model = m
                        break
                if not selected_model:
                    print(f"警告: 未找到模型 {model_name}，使用b28模型")
                    selected_model = self._get_b28_model(available_models)
            else:
                # 默认使用b28模型
                selected_model = self._get_b28_model(available_models)
            
            self.current_model = selected_model['name']
            print(f"使用模型: {self.current_model}")
            
            self.katago_client = KataGoGTPClient(
                katago_path=str(katago_path),
                model_path=selected_model['path'],
                config_path=str(config_path),
                use_mps=True
            )
            self.is_ready = True
            print("KataGo 已就绪")
        except Exception as e:
            print(f"KataGo 初始化失败: {e}")
            self.is_ready = False
            
    def switch_model(self, model_name: str) -> bool:
        """切换模型"""
        try:
            with self.lock:
                # 关闭当前客户端
                if self.katago_client:
                    try:
                        self.katago_client.close()
                    except:
                        pass
                    self.katago_client = None
                
                self.is_ready = False
                self.last_stones = None
                
                # 使用新模型重新初始化
                self.initialize(model_name)
                return self.is_ready
        except Exception as e:
            print(f"切换模型失败: {e}")
            return False
            
    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """分析棋盘 - 不使用缓存，每次清空重新设置"""
        if not self.is_ready or not self.katago_client:
            return AnalyzeResponse(
                success=False,
                message="KataGo 未就绪"
            )

        start_time = time.time()
        print(f"[分析请求] max_time={request.max_time}, fast_mode={request.fast_mode}, color={request.current_color}")

        try:
            with self.lock:  # 线程锁保护KataGo访问
                current_stones = request.stones

                # 每次清空棋盘并重新设置所有棋子（不使用缓存）
                self.katago_client.send_command("clear_board")
                self._set_all_stones(current_stones)

                # 快棋模式：使用 genmove 快速获取最佳落子，不进行详细分析
                if request.fast_mode:
                    best_move_coord = self.katago_client.genmove(
                        request.current_color,
                        fast_mode=True,
                        max_time=request.max_time
                    )
                    if best_move_coord and best_move_coord[0] is not None:
                        # 将坐标转换为 GTP 格式
                        best_move = self.katago_client.coord_to_gtp(best_move_coord[0], best_move_coord[1])
                        # 只返回最佳落子，不包含胜率等信息
                        recommended_moves = [{
                            'move': best_move,
                            'winrate': 0,
                            'visits': 0,
                            'scoreMean': 0
                        }]
                        recommended_move = best_move
                    else:
                        recommended_move = None
                        recommended_moves = None
                else:
                    # 普通模式：使用 kata-analyze 获取详细分析（包含胜率、目差等）
                    # 处理打劫：如果提供了避免位置，使用get_recommended_moves获取多个推荐
                    recommended_move = None
                    recommended_moves = None
                    avoid_positions = request.avoid_positions

                    # 准备PDA参数
                    pda_value = request.playout_doubling_advantage if request.playout_doubling_advantage is not None else 1.5

                    if avoid_positions:
                        # 转换为 (row, col) 格式
                        avoid_pos_list = [(p['y'], p['x']) for p in avoid_positions]
                        moves = self.katago_client.get_recommended_moves(
                            max_moves=5,
                            avoid_positions=avoid_pos_list,
                            max_time=request.max_time,
                            current_color=request.current_color,
                            playout_doubling_advantage=pda_value
                        )
                        if moves:
                            recommended_moves = []
                            for m in moves:
                                gtp = self.katago_client.coord_to_gtp(m['row'], m['col'])
                                recommended_moves.append({
                                    'move': gtp,
                                    'winrate': m.get('winrate', 0),
                                    'visits': m.get('visits', 0),
                                    'scoreMean': m.get('scoreMean', 0)
                                })
                            recommended_move = recommended_moves[0]['move']
                    else:
                        # 普通分析 - 使用 get_recommended_moves 获取推荐列表（包含胜率）
                        moves = self.katago_client.get_recommended_moves(
                            max_moves=5,
                            max_time=request.max_time,
                            current_color=request.current_color,
                            playout_doubling_advantage=pda_value
                        )
                        if moves:
                            recommended_moves = []
                            for m in moves:
                                gtp = self.katago_client.coord_to_gtp(m['row'], m['col'])
                                recommended_moves.append({
                                    'move': gtp,
                                    'winrate': m.get('winrate', 0),
                                    'visits': m.get('visits', 0),
                                    'scoreMean': m.get('scoreMean', 0)
                                })
                            recommended_move = recommended_moves[0]['move']
                        else:
                            recommended_move = None

                # 不使用缓存
                self.last_stones = None

            analysis_time = time.time() - start_time

            return AnalyzeResponse(
                success=True,
                recommended_move=recommended_move,
                recommended_moves=recommended_moves,
                analysis_time=analysis_time
            )

        except Exception as e:
            # 出错时重置缓存，下次强制完整重置
            self.last_stones = None
            return AnalyzeResponse(
                success=False,
                message=f"分析失败: {str(e)}",
                analysis_time=time.time() - start_time
            )
    
    def _needs_full_reset(self, last_stones: Optional[Dict], current_stones: Dict) -> bool:
        """检查是否需要完整重置棋盘"""
        if last_stones is None:
            return True
        
        last_black = set((s['x'], s['y']) for s in last_stones.get('black', []))
        last_white = set((s['x'], s['y']) for s in last_stones.get('white', []))
        curr_black = set((s['x'], s['y']) for s in current_stones.get('black', []))
        curr_white = set((s['x'], s['y']) for s in current_stones.get('white', []))
        
        # 如果有棋子被移除，需要完整重置
        removed_black = last_black - curr_black
        removed_white = last_white - curr_white
        
        if removed_black or removed_white:
            return True
        
        # 如果棋子颜色发生变化，需要完整重置
        color_changed = (last_black & curr_white) or (last_white & curr_black)
        if color_changed:
            return True
        
        return False
    
    def _get_stone_changes(self, last_stones: Optional[Dict], current_stones: Dict) -> Dict:
        """获取棋子变化（新增和移除）"""
        if last_stones is None:
            return {
                'add_black': current_stones.get('black', []),
                'add_white': current_stones.get('white', [])
            }
        
        last_black = set((s['x'], s['y']) for s in last_stones.get('black', []))
        last_white = set((s['x'], s['y']) for s in last_stones.get('white', []))
        curr_black = set((s['x'], s['y']) for s in current_stones.get('black', []))
        curr_white = set((s['x'], s['y']) for s in current_stones.get('white', []))
        
        # 新增的棋子
        add_black_coords = curr_black - last_black
        add_white_coords = curr_white - last_white
        
        # 转换回列表格式
        add_black = [{'x': x, 'y': y} for x, y in add_black_coords]
        add_white = [{'x': x, 'y': y} for x, y in add_white_coords]
        
        return {
            'add_black': add_black,
            'add_white': add_white
        }
    
    def _set_all_stones(self, stones: Dict):
        """设置所有棋子"""
        for stone in stones.get('black', []):
            try:
                gtp_coord = self._array_to_gtp(stone['x'], stone['y'])
                self.katago_client.send_command(f"play B {gtp_coord}")
            except:
                pass
        
        for stone in stones.get('white', []):
            try:
                gtp_coord = self._array_to_gtp(stone['x'], stone['y'])
                self.katago_client.send_command(f"play W {gtp_coord}")
            except:
                pass
    
    def _apply_stone_changes(self, changes: Dict):
        """应用棋子变化（增量更新）"""
        for stone in changes.get('add_black', []):
            try:
                gtp_coord = self._array_to_gtp(stone['x'], stone['y'])
                self.katago_client.send_command(f"play B {gtp_coord}")
            except:
                pass
        
        for stone in changes.get('add_white', []):
            try:
                gtp_coord = self._array_to_gtp(stone['x'], stone['y'])
                self.katago_client.send_command(f"play W {gtp_coord}")
            except:
                pass
            
    def _array_to_gtp(self, x: int, y: int) -> str:
        """数组坐标转GTP坐标"""
        # 确保坐标在有效范围内 (0-18)
        if not (0 <= x <= 18 and 0 <= y <= 18):
            raise ValueError(f"坐标超出范围: x={x}, y={y}, 必须在 0-18 之间")
        
        col = chr(ord('A') + x)
        if col >= 'I':
            col = chr(ord(col) + 1)
        row = 19 - y
        return f"{col}{row}"
        
    def shutdown(self):
        """关闭服务"""
        if self.katago_client:
            try:
                self.katago_client.quit()
            except:
                pass
            

state = ServerState()


# ============ API 路由 ============

@app.on_event("startup")
def startup():
    """启动时初始化"""
    state.initialize()


@app.on_event("shutdown")
def shutdown():
    """关闭时清理"""
    state.shutdown()


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "KataGo 分析服务",
        "version": "2.0.0",
        "status": "ready" if state.is_ready else "not_ready"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy" if state.is_ready else "unhealthy",
        "katago_ready": state.is_ready,
        "model_loaded": state.katago_client is not None
    }

@app.get("/status")
async def get_status():
    """获取服务状态"""
    return {
        "status": "ok" if state.is_ready else "error",
        "katago_ready": state.is_ready
    }


@app.get("/models")
def get_models():
    """获取可用模型列表"""
    return {
        "current": state.current_model,
        "models": state.get_available_models()
    }


@app.get("/katago/config")
def get_katago_config():
    """获取KataGo关键配置参数"""
    try:
        config = state.katago_client.katago_config if state.katago_client else {}
        # 调试：打印实际读取的配置
        print(f"[DEBUG] KataGo config nnCacheSizePowerOfTwo: {config.get('nnCacheSizePowerOfTwo', 'NOT FOUND')}")
        # 返回关键参数，包括目数权重、胜率权重、探索参数
        return {
            "numSearchThreads": config.get("numSearchThreads", 6),
            "nnCacheSizePowerOfTwo": config.get("nnCacheSizePowerOfTwo", 19),
            "maxVisits": config.get("maxVisits", 5000),
            "maxTime": config.get("maxTime", 5.0),
            "cpuctExploration": config.get("cpuctExploration", 1.2),
            "rootPolicyOptimism": config.get("rootPolicyOptimism", 0.45),
            "winLossUtilityFactor": config.get("winLossUtilityFactor", 1.0),
            "staticScoreUtilityFactor": config.get("staticScoreUtilityFactor", 0.1),
            "dynamicScoreUtilityFactor": config.get("dynamicScoreUtilityFactor", 0.3),
            "resignThreshold": config.get("resignThreshold", -0.99)
        }
    except Exception as e:
        print(f"[API] 获取KataGo配置失败: {e}")
        return {
            "numSearchThreads": 6,
            "nnCacheSizePowerOfTwo": 19,
            "maxVisits": 5000,
            "maxTime": 5.0,
            "cpuctExploration": 1.2,
            "rootPolicyOptimism": 0.45,
            "winLossUtilityFactor": 1.0,
            "staticScoreUtilityFactor": 0.1,
            "dynamicScoreUtilityFactor": 0.3,
            "resignThreshold": -0.99
        }


@app.post("/switch_model")
def switch_model_endpoint(request: dict):
    """切换模型"""
    model_name = request.get("model_name")
    if not model_name:
        return {"success": False, "message": "未指定模型名称"}
    
    success = state.switch_model(model_name)
    return {
        "success": success,
        "current": state.current_model,
        "message": "切换成功" if success else "切换失败"
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_board(request: AnalyzeRequest):
    """分析棋盘并返回推荐落子"""
    return state.analyze(request)


@app.post("/stop")
def stop_server():
    """停止服务（用于远程关闭）"""
    state.shutdown()
    return {"status": "stopped"}


# ============ 主函数 ============

def main():
    """主函数"""
    print("=" * 50)
    print("KataGo 分析服务")
    print("=" * 50)
    print("功能：仅提供AI分析，不处理截图和识别")
    print("接口：http://localhost:8001")
    print("=" * 50)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )


if __name__ == "__main__":
    main()
