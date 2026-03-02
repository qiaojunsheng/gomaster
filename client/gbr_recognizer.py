"""
GBR棋盘识别器封装
封装GBR的棋盘识别功能，提供简单的接口
"""

import os
import sys
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gbr'))
from gr.board import GrBoard
from gr.grdef import GR_A, GR_B, GR_R, GR_BW, STONE_BLACK, STONE_WHITE
from go_coordinates import gbr_to_array


class GBRRecognizer:
    """GBR棋盘识别器"""
    
    def __init__(self, board_size: int = 19):
        """
        初始化识别器
        
        Args:
            board_size: 棋盘大小
        """
        self.board_size = board_size
        self.board = GrBoard()
    
    def recognize_board_image(self, image_path: str, params_file: Optional[str] = None) -> Dict:
        """
        识别棋盘图像
        
        Args:
            image_path: 图像文件路径
            params_file: 参数文件路径（可选）
            
        Returns:
            识别结果字典，包含 'black'、'white'、'board_edges'、'board_spacing' 等信息
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图像文件不存在: {image_path}")
        
        try:
            # 先加载参数文件（如果提供）
            if params_file and os.path.exists(params_file):
                self.board.load_params(params_file)
            
            # 禁用 WATERSHED 以避免 "Cannot find peak for stone" 警告
            # WATERSHED 是可选优化步骤，禁用后霍夫圆检测仍然可以正常工作
            self.board._params['WATERSHED_B'] = 0
            self.board._params['WATERSHED_W'] = 0
            
            # 加载图像并处理
            # 注意：不使用 f_with_params=True，因为参数已经手动加载了
            self.board.load_image(image_path, f_with_params=False, f_process=True)
            
            # 获取识别结果
            result = {
                'black': [],
                'white': [],
                'board_edges': None,
                'board_spacing': None
            }
            
            # 转换黑子
            black_stones = self.board.black_stones
            for stone in black_stones:
                a = stone[GR_A]
                b = stone[GR_B]
                row, col = gbr_to_array(a, b, self.board_size)
                result['black'].append((row, col))
            
            # 转换白子
            white_stones = self.board.white_stones
            for stone in white_stones:
                a = stone[GR_A]
                b = stone[GR_B]
                row, col = gbr_to_array(a, b, self.board_size)
                result['white'].append((row, col))
            
            # 获取棋盘边缘和间距信息（用于自动点击）
            from gbr.gr.grdef import GR_EDGES, GR_SPACING
            if self.board._res is not None:
                result['board_edges'] = self.board._res.get(GR_EDGES)
                result['board_spacing'] = self.board._res.get(GR_SPACING)
            
            return result
        except Exception as e:
            pass
            # 返回空结果而不是抛出异常
            return {
                'black': [],
                'white': [],
                'board_edges': None,
                'board_spacing': None
            }
    
    def recognize_from_array(self, img_array: np.ndarray, params_file: Optional[str] = None) -> Dict[str, List[Tuple[int, int]]]:
        """
        从numpy数组识别棋盘
        
        Args:
            img_array: RGB格式的图像数组
            params_file: 参数文件路径（可选）
            
        Returns:
            识别结果字典
        """
        import tempfile
        temp_path = os.path.join(tempfile.gettempdir(), f"gbr_temp_{os.getpid()}.png")
        cv2.imwrite(temp_path, cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR))
        
        try:
            result = self.recognize_board_image(temp_path, params_file=params_file)
            return result
        finally:
            try:
                os.remove(temp_path)
            except:
                pass
