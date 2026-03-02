"""
围棋规则引擎
实现棋盘、落子、提子、打劫等核心规则
"""
import numpy as np
from typing import List, Tuple, Optional, Set
from copy import deepcopy
from enum import IntEnum


class Color(IntEnum):
    """棋子颜色"""
    EMPTY = 0
    BLACK = 1
    WHITE = 2

    def opponent(self):
        """返回对手颜色"""
        return Color.WHITE if self == Color.BLACK else Color.BLACK


class GoBoard:
    """围棋棋盘"""
    
    def __init__(self, size: int = 19):
        """
        初始化棋盘
        Args:
            size: 棋盘大小，默认19x19
        """
        self.size = size
        self.board = np.zeros((size, size), dtype=np.int8)
        self.ko_point = None  # 打劫点
        self.last_move = None  # 上一步落子
        self.move_history = []  # 落子历史
        self.captured_stones = {Color.BLACK: 0, Color.WHITE: 0}  # 提子数
        self.board_history = []  # 棋盘状态历史（用于悔棋）
        self.position_history_counts = {}
        self.position_history_stack = []
        self._add_position(Color.BLACK)
        
    def copy(self):
        """深拷贝棋盘"""
        new_board = GoBoard(self.size)
        new_board.board = self.board.copy()
        new_board.ko_point = self.ko_point
        new_board.last_move = self.last_move
        new_board.move_history = self.move_history.copy()
        new_board.captured_stones = self.captured_stones.copy()
        new_board.position_history_counts = self.position_history_counts.copy()
        new_board.position_history_stack = self.position_history_stack.copy()
        # 深拷贝board_history
        new_board.board_history = []
        for state in self.board_history:
            new_state = {
                'board': state['board'].copy(),
                'ko_point': state['ko_point'],
                'last_move': state['last_move'],
                'captured_stones': state['captured_stones'].copy(),
                'move_history': state['move_history'].copy()
            }
            new_board.board_history.append(new_state)
        return new_board

    def _position_key(self, board: np.ndarray, next_player: Color):
        return (board.tobytes(), int(next_player))

    def _add_position(self, next_player: Color):
        key = self._position_key(self.board, next_player)
        self.position_history_stack.append(key)
        self.position_history_counts[key] = self.position_history_counts.get(key, 0) + 1

    def _remove_last_position(self):
        if not self.position_history_stack:
            return
        key = self.position_history_stack.pop()
        count = self.position_history_counts.get(key, 0)
        if count <= 1:
            self.position_history_counts.pop(key, None)
        else:
            self.position_history_counts[key] = count - 1
    
    def is_valid_move(self, row: int, col: int, color: Color) -> bool:
        """
        检查落子是否合法
        Args:
            row: 行坐标
            col: 列坐标
            color: 棋子颜色
        Returns:
            是否合法
        """
        # 检查坐标是否在棋盘内
        if not (0 <= row < self.size and 0 <= col < self.size):
            return False
        
        # 检查位置是否为空
        if self.board[row, col] != Color.EMPTY:
            return False
        
        # 检查打劫
        if self.ko_point == (row, col):
            return False
        
        # 尝试落子
        test_board = self.copy()
        test_board.board[row, col] = color
        
        # 检查是否提子
        captured = test_board._capture_stones(row, col, color.opponent())
        
        group = test_board._get_group(row, col, color)
        liberties = test_board._get_group_liberties(group)
        if len(captured) == 1 and len(liberties) == 1 and captured[0] in liberties:
            test_board.ko_point = captured[0]
        else:
            test_board.ko_point = None
        
        if not liberties:
            return False

        next_player = color.opponent()
        next_key = self._position_key(test_board.board, next_player)
        if next_key in self.position_history_counts:
            return False
        
        return True
    
    def place_stone(self, row: int, col: int, color: Color) -> bool:
        """
        落子
        Args:
            row: 行坐标
            col: 列坐标
            color: 棋子颜色
        Returns:
            是否成功落子
        """
        if not self.is_valid_move(row, col, color):
            return False
        
        # 保存当前棋盘状态（用于悔棋）
        self.board_history.append({
            'board': self.board.copy(),
            'ko_point': self.ko_point,
            'last_move': self.last_move,
            'captured_stones': self.captured_stones.copy(),
            'move_history': self.move_history.copy()
        })
        
        self.board[row, col] = color
        self.last_move = (row, col)
        self.move_history.append((row, col, color))
        
        # 提子
        captured = self._capture_stones(row, col, color.opponent())
        self.captured_stones[color] += len(captured)
        
        group = self._get_group(row, col, color)
        liberties = self._get_group_liberties(group)
        if len(captured) == 1 and len(liberties) == 1 and captured[0] in liberties:
            self.ko_point = captured[0]
        else:
            self.ko_point = None

        self._add_position(color.opponent())
        
        return True
    
    def _capture_stones(self, row: int, col: int, opponent_color: Color) -> List[Tuple[int, int]]:
        """
        提子
        Args:
            row: 落子行
            col: 落子列
            opponent_color: 对手颜色
        Returns:
            被提掉的棋子坐标列表
        """
        captured = []
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        
        for dr, dc in directions:
            nr, nc = row + dr, col + dc
            if (0 <= nr < self.size and 0 <= nc < self.size and
                self.board[nr, nc] == opponent_color):
                # 检查这个连通块是否有气
                group = self._get_group(nr, nc, opponent_color)
                if not self._group_has_liberty(group):
                    for r, c in group:
                        self.board[r, c] = Color.EMPTY
                        captured.append((r, c))
        
        return captured
    
    def _get_group(self, row: int, col: int, color: Color) -> Set[Tuple[int, int]]:
        """
        获取连通块
        Args:
            row: 起始行
            col: 起始列
            color: 棋子颜色
        Returns:
            连通块坐标集合
        """
        group = set()
        stack = [(row, col)]
        visited = set()
        
        while stack:
            r, c = stack.pop()
            if (r, c) in visited:
                continue
            visited.add((r, c))
            
            if self.board[r, c] == color:
                group.add((r, c))
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if (0 <= nr < self.size and 0 <= nc < self.size and
                        (nr, nc) not in visited):
                        stack.append((nr, nc))
        
        return group
    
    def _has_liberty(self, row: int, col: int, color: Color) -> bool:
        """
        检查棋子是否有气
        Args:
            row: 行坐标
            col: 列坐标
            color: 棋子颜色
        Returns:
            是否有气
        """
        group = self._get_group(row, col, color)
        return self._group_has_liberty(group)
    
    def _group_has_liberty(self, group: Set[Tuple[int, int]]) -> bool:
        """
        检查连通块是否有气
        Args:
            group: 连通块坐标集合
        Returns:
            是否有气
        """
        for r, c in group:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if (0 <= nr < self.size and 0 <= nc < self.size and
                    self.board[nr, nc] == Color.EMPTY):
                    return True
        return False
    
    def _get_group_liberties(self, group: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        liberties = set()
        for r, c in group:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if (0 <= nr < self.size and 0 <= nc < self.size and
                    self.board[nr, nc] == Color.EMPTY):
                    liberties.add((nr, nc))
        return liberties
    
    def get_valid_moves(self, color: Color) -> List[Tuple[int, int]]:
        """
        获取所有合法落子点
        Args:
            color: 棋子颜色
        Returns:
            合法落子点列表
        """
        valid_moves = []
        for r in range(self.size):
            for c in range(self.size):
                if self.is_valid_move(r, c, color):
                    valid_moves.append((r, c))
        return valid_moves
    
    def pass_move(self, color: Color):
        """过手"""
        # 保存当前棋盘状态（用于悔棋）
        self.board_history.append({
            'board': self.board.copy(),
            'ko_point': self.ko_point,
            'last_move': self.last_move,
            'captured_stones': self.captured_stones.copy(),
            'move_history': self.move_history.copy()
        })
        self.move_history.append((None, None, color))
        self.ko_point = None
        self._add_position(color.opponent())
    
    def undo(self) -> bool:
        """
        悔棋（撤销上一步）
        Returns:
            是否成功悔棋
        """
        if not self.board_history:
            return False

        self._remove_last_position()
        
        # 恢复上一个棋盘状态
        prev_state = self.board_history.pop()
        self.board = prev_state['board']
        self.ko_point = prev_state['ko_point']
        self.last_move = prev_state['last_move']
        self.captured_stones = prev_state['captured_stones']
        self.move_history = prev_state['move_history']
        
        return True
    
    def get_move_count(self) -> int:
        """获取当前手数"""
        return len(self.move_history)
    
    def get_game_result(self) -> Optional[float]:
        """
        计算游戏结果（使用简单的领地计算）
        Returns:
            BLACK胜返回1.0，WHITE胜返回-1.0，未结束返回None
        """
        # 如果最后两步都是过手，游戏结束
        if len(self.move_history) >= 2:
            last_two = self.move_history[-2:]
            if (last_two[0][0] is None and last_two[1][0] is None):
                # 计算领地
                territory = self._calculate_territory()
                if territory > 0:
                    return 1.0  # BLACK胜
                elif territory < 0:
                    return -1.0  # WHITE胜
                else:
                    return 0.0  # 平局
        return None
    
    def _calculate_territory(self) -> float:
        """
        计算领地（简化版）
        Returns:
            领地差（正数表示BLACK领先）
        """
        # 使用简单的死子判断和领地计算
        black_score = self.captured_stones[Color.WHITE]
        white_score = self.captured_stones[Color.BLACK]
        
        # 计算空点归属（简化：使用距离最近的颜色）
        for r in range(self.size):
            for c in range(self.size):
                if self.board[r, c] == Color.EMPTY:
                    # 找到最近的棋子
                    min_dist_black = float('inf')
                    min_dist_white = float('inf')
                    
                    for rr in range(self.size):
                        for cc in range(self.size):
                            if self.board[rr, cc] == Color.BLACK:
                                dist = abs(rr - r) + abs(cc - c)
                                min_dist_black = min(min_dist_black, dist)
                            elif self.board[rr, cc] == Color.WHITE:
                                dist = abs(rr - r) + abs(cc - c)
                                min_dist_white = min(min_dist_white, dist)
                    
                    if min_dist_black < min_dist_white:
                        black_score += 1
                    elif min_dist_white < min_dist_black:
                        white_score += 1
        
        return black_score - white_score - 7.5  # 贴目
    
    def to_feature(self) -> np.ndarray:
        """
        将棋盘转换为特征向量（用于神经网络输入）
        Returns:
            特征数组 shape: (channels, size, size)
        """
        features = []
        size = self.size
        
        # 当前玩家视角（BLACK）
        # 1. 当前玩家的棋子
        black_board = (self.board == Color.BLACK).astype(np.float32)
        features.append(black_board)
        
        # 2. 对手的棋子
        white_board = (self.board == Color.WHITE).astype(np.float32)
        features.append(white_board)
        
        # 3. 空点
        empty_board = (self.board == Color.EMPTY).astype(np.float32)
        features.append(empty_board)
        
        # 4. 打劫点
        ko_board = np.zeros((size, size), dtype=np.float32)
        if self.ko_point:
            ko_board[self.ko_point[0], self.ko_point[1]] = 1.0
        features.append(ko_board)
        
        # 5. 上一步落子
        last_move_board = np.zeros((size, size), dtype=np.float32)
        if self.last_move:
            last_move_board[self.last_move[0], self.last_move[1]] = 1.0
        features.append(last_move_board)
        
        # 6. 轮到谁下（全1或全0）
        turn_board = np.ones((size, size), dtype=np.float32)  # 当前是BLACK
        features.append(turn_board)
        
        # 7-12. 历史信息（最近6步）
        history_length = min(6, len(self.move_history))
        for i in range(6):
            hist_board = np.zeros((size, size), dtype=np.float32)
            if i < history_length:
                move = self.move_history[-(i+1)]
                if move[0] is not None:
                    hist_board[move[0], move[1]] = 1.0
            features.append(hist_board)
        
        return np.stack(features, axis=0)
    
    def move_to_index(self, row: int, col: int) -> int:
        """将坐标转换为索引（用于神经网络输出）"""
        if row is None or col is None:  # 过手
            return self.size * self.size
        return row * self.size + col
    
    def index_to_move(self, index: int) -> Tuple[Optional[int], Optional[int]]:
        """将索引转换为坐标"""
        if index == self.size * self.size:
            return (None, None)  # 过手
        row = index // self.size
        col = index % self.size
        return (row, col)
    
    def __str__(self):
        """打印棋盘"""
        symbols = {Color.EMPTY: '.', Color.BLACK: 'X', Color.WHITE: 'O'}
        lines = []
        lines.append('  ' + ' '.join([chr(ord('A') + i) for i in range(min(19, self.size))]))
        for r in range(self.size):
            line = f'{r+1:2d} '
            for c in range(self.size):
                line += symbols[self.board[r, c]] + ' '
            lines.append(line)
        return '\n'.join(lines)
