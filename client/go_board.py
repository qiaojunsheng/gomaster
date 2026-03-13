"""
围棋规则引擎 - 参考 Sabaki 实现
实现棋盘、落子、提子、打劫等核心规则
"""
import numpy as np
from typing import List, Tuple, Optional, Set, Dict, Any
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
    """
    围棋棋盘 - 参考 Sabaki 的 @sabaki/go-board 实现
    
    核心特点：
    1. 使用 _ko_info 存储打劫信息 {sign: 玩家, vertex: 打劫点坐标}
    2. 在 make_move 中自动检测和设置打劫
    3. 提供 analyze_move 方法预先检查某步是否是打劫
    4. 基于棋盘状态判断，而非历史记录
    """

    def __init__(self, size: int = 19):
        """
        初始化棋盘
        Args:
            size: 棋盘大小，默认19x19
        """
        self.size = size
        self.board = np.zeros((size, size), dtype=np.int8)
        self._captures = {Color.BLACK: 0, Color.WHITE: 0}
        # 打劫信息：参考 Sabaki 的 _koInfo 结构
        self._ko_info = {
            'sign': Color.EMPTY,  # 哪方不能下打劫点
            'vertex': None        # 打劫点坐标 (row, col)
        }
        self.move_history = []  # 落子历史 [(row, col, color), ...]

    def get(self, row: int, col: int) -> Color:
        """获取指定位置的棋子颜色"""
        if 0 <= row < self.size and 0 <= col < self.size:
            return Color(self.board[row, col])
        return Color.EMPTY

    def set(self, row: int, col: int, color: Color):
        """设置指定位置的棋子颜色"""
        if 0 <= row < self.size and 0 <= col < self.size:
            self.board[row, col] = color
        return self

    def has(self, row: int, col: int) -> bool:
        """检查坐标是否在棋盘范围内"""
        return 0 <= row < self.size and 0 <= col < self.size

    def clear(self):
        """清空棋盘"""
        self.board.fill(Color.EMPTY)
        self._captures = {Color.BLACK: 0, Color.WHITE: 0}
        self._ko_info = {'sign': Color.EMPTY, 'vertex': None}
        self.move_history = []
        return self

    def clone(self):
        """克隆棋盘"""
        new_board = GoBoard(self.size)
        new_board.board = self.board.copy()
        new_board._captures = self._captures.copy()
        new_board._ko_info = deepcopy(self._ko_info)
        new_board.move_history = self.move_history.copy()
        return new_board

    def get_neighbors(self, row: int, col: int) -> List[Tuple[int, int]]:
        """获取相邻的四个位置"""
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        neighbors = []
        for dr, dc in directions:
            nr, nc = row + dr, col + dc
            if self.has(nr, nc):
                neighbors.append((nr, nc))
        return neighbors

    def get_chain(self, row: int, col: int) -> Set[Tuple[int, int]]:
        """
        获取连通块（同色的连通棋子）
        参考 Sabaki 的 getChain 方法
        """
        color = self.get(row, col)
        if color == Color.EMPTY:
            return set()

        chain = set()
        stack = [(row, col)]

        while stack:
            r, c = stack.pop()
            if (r, c) in chain:
                continue
            chain.add((r, c))

            for nr, nc in self.get_neighbors(r, c):
                if self.get(nr, nc) == color and (nr, nc) not in chain:
                    stack.append((nr, nc))

        return chain

    def get_liberties(self, row: int, col: int) -> Set[Tuple[int, int]]:
        """
        获取指定位置连通块的气
        参考 Sabaki 的 getLiberties 方法
        """
        color = self.get(row, col)
        if color == Color.EMPTY:
            return set()

        chain = self.get_chain(row, col)
        liberties = set()

        for r, c in chain:
            for nr, nc in self.get_neighbors(r, c):
                if self.get(nr, nc) == Color.EMPTY:
                    liberties.add((nr, nc))

        return liberties

    def has_liberties(self, row: int, col: int, visited: Set = None) -> bool:
        """
        检查指定位置的连通块是否有气
        参考 Sabaki 的 hasLiberties 方法
        """
        if visited is None:
            visited = set()

        color = self.get(row, col)
        if color == Color.EMPTY:
            return False

        if (row, col) in visited:
            return False

        # 检查邻居是否有空点
        for nr, nc in self.get_neighbors(row, col):
            if self.get(nr, nc) == Color.EMPTY:
                return True

        visited.add((row, col))

        # 递归检查同色邻居
        for nr, nc in self.get_neighbors(row, col):
            if self.get(nr, nc) == color:
                if self.has_liberties(nr, nc, visited):
                    return True

        return False

    def _has_no_liberties(self, chain: Set[Tuple[int, int]]) -> bool:
        """
        检查一个连通块是否没有气（用于提子检测）

        Args:
            chain: 连通块坐标集合

        Returns:
            True 如果没有气，False 否则
        """
        if not chain:
            return False

        liberties = set()
        for r, c in chain:
            for nr, nc in self.get_neighbors(r, c):
                if self.get(nr, nc) == Color.EMPTY:
                    liberties.add((nr, nc))

        return len(liberties) == 0

    def make_move(self, row: int, col: int, color: Color,
                  prevent_suicide: bool = False,
                  prevent_overwrite: bool = False,
                  prevent_ko: bool = False) -> 'GoBoard':
        """
        落子并返回新棋盘状态
        参考 Sabaki 的 makeMove 方法

        Args:
            row: 落子行
            col: 落子列
            color: 棋子颜色
            prevent_suicide: 是否禁止自杀
            prevent_overwrite: 是否禁止覆盖已有棋子
            prevent_ko: 是否禁止打劫

        Returns:
            新的 GoBoard 实例（Immutable 风格）
        """
        if color == Color.EMPTY or not self.has(row, col):
            return self.clone()

        # 检查是否覆盖已有棋子
        if prevent_overwrite and self.get(row, col) != Color.EMPTY:
            raise ValueError('Overwrite prevented')

        # 检查打劫
        if prevent_ko and self._ko_info['sign'] == color:
            ko_row, ko_col = self._ko_info['vertex']
            if ko_row == row and ko_col == col:
                raise ValueError('Ko prevented')

        # 克隆棋盘
        new_board = self.clone()
        new_board.set(row, col, color)

        # 提子
        neighbors = new_board.get_neighbors(row, col)
        dead_stones = []
        opponent = color.opponent()

        # 检查邻居中是否有被提的棋子
        for nr, nc in neighbors:
            if new_board.get(nr, nc) == opponent and not new_board.has_liberties(nr, nc):
                chain = new_board.get_chain(nr, nc)
                for r, c in chain:
                    new_board.set(r, c, Color.EMPTY)
                    dead_stones.append((r, c))
                new_board._captures[color] += len(chain)

        # 检测未来打劫 - 参考 Sabaki 的实现
        liberties = new_board.get_liberties(row, col)
        # 将集合转换为列表以便多次使用
        liberties_list = list(liberties)
        has_ko = (len(dead_stones) == 1 and           # 只提了一个子
                  len(liberties_list) == 1 and         # 落子后只有1气
                  liberties_list[0] == dead_stones[0] and  # 那1气正好是被提的子的位置
                  all(new_board.get(nr, nc) != color for nr, nc in neighbors))  # 四周没有自己的棋子

        new_board._ko_info = {
            'sign': opponent if has_ko else Color.EMPTY,
            'vertex': dead_stones[0] if has_ko else None
        }

        # 检测自杀
        if len(dead_stones) == 0 and len(liberties) == 0:
            if prevent_suicide:
                raise ValueError('Suicide prevented')

            # 自杀：提掉自己的棋子
            chain = new_board.get_chain(row, col)
            for r, c in chain:
                new_board.set(r, c, Color.EMPTY)
            new_board._captures[opponent] += len(chain)

        # 记录历史
        new_board.move_history.append((row, col, color))

        return new_board

    def analyze_move(self, row: int, col: int, color: Color) -> Dict[str, Any]:
        """
        分析某步棋的各种属性（不下子）
        参考 Sabaki 的 analyzeMove 方法

        Args:
            row: 落子行
            col: 落子列
            color: 棋子颜色

        Returns:
            {
                'pass': bool,        # 是否过手
                'overwrite': bool,   # 是否覆盖已有棋子
                'capturing': bool,   # 是否提子
                'suicide': bool,     # 是否自杀
                'ko': bool           # 是否打劫
            }
        """
        result = {
            'pass': color == Color.EMPTY or not self.has(row, col),
            'overwrite': self.get(row, col) != Color.EMPTY,
            'capturing': False,
            'suicide': False,
            'ko': False
        }

        if result['pass'] or result['overwrite']:
            return result

        # 检查是否是打劫
        if self._ko_info['sign'] == color:
            ko_row, ko_col = self._ko_info['vertex']
            if ko_row == row and ko_col == col:
                result['ko'] = True

        # 模拟落子
        original_sign = self.get(row, col)
        self.set(row, col, color)

        # 检查是否提子
        opponent = color.opponent()
        result['capturing'] = any(
            self.get(nr, nc) == opponent and not self.has_liberties(nr, nc)
            for nr, nc in self.get_neighbors(row, col)
        )

        # 检查是否自杀
        if not result['capturing'] and not self.has_liberties(row, col):
            result['suicide'] = True

        # 恢复
        self.set(row, col, original_sign)

        return result

    def is_valid_move(self, row: int, col: int, color: Color) -> bool:
        """
        检查某步是否合法
        参考 Sabaki 的合法棋判断
        """
        if not self.has(row, col):
            return False
        if self.get(row, col) != Color.EMPTY:
            return False

        analysis = self.analyze_move(row, col, color)
        return not analysis['ko'] and not analysis['overwrite']

    def get_ko_info(self) -> Dict[str, Any]:
        """
        获取打劫信息
        返回 Sabaki 风格的 koInfo
        """
        return {
            'sign': self._ko_info['sign'],
            'vertex': self._ko_info['vertex'],
            'is_ko': self._ko_info['vertex'] is not None
        }

    def detect_ko_from_position(self, current_color: Color) -> Dict[str, Any]:
        """
        通过棋盘状态推断打劫点（不依赖落子历史）

        打劫的棋盘特征：
        1. 有一个空点
        2. 该空点周围有且仅有一个对方的棋子（被提掉的子）
        3. 该空点周围有其他对方的棋子形成包围
        4. 该空点是一个"假眼"位置

        Args:
            current_color: 当前要下的一方

        Returns:
            打劫状态字典
        """
        opponent = current_color.opponent()

        for row in range(self.size):
            for col in range(self.size):
                if self.get(row, col) != Color.EMPTY:
                    continue

                # 检查该空点是否可能是打劫点
                neighbors = self.get_neighbors(row, col)
                opponent_neighbors = [n for n in neighbors if self.get(*n) == opponent]
                empty_neighbors = [n for n in neighbors if self.get(*n) == Color.EMPTY]

                # 打劫点特征：周围有且仅有1个对方棋子（刚被提掉）
                # 且至少有2个其他对方棋子包围
                if len(opponent_neighbors) >= 2:
                    # 检查是否形成"假眼"打劫形状
                    # 模拟当前方下在这里，看是否能提子
                    test_board = self.clone()
                    test_board.set(row, col, current_color)

                    # 检查周围是否有对方的棋子被提掉
                    captured = []
                    for nr, nc in neighbors:
                        if test_board.get(nr, nc) == opponent:
                            chain = test_board.get_chain(nr, nc)
                            if test_board._has_no_liberties(chain):
                                captured.extend(chain)

                    # 如果下在这里能提掉且仅提掉1个子，可能是打劫
                    if len(captured) == 1:
                        # 进一步验证：检查被提子的位置是否形成循环
                        captured_pos = captured[0]
                        # 模拟提子后的棋盘
                        after_capture = test_board.clone()
                        for cr, cc in captured:
                            after_capture.set(cr, cc, Color.EMPTY)

                        # 检查是否是典型的打劫形状（双方各有一个子可以被提）
                        return {
                            'is_ko': True,
                            'ko_point': (row, col),
                            'sign': current_color,  # 当前方不能立即回提
                            'captured_stone': captured_pos
                        }

        return {'is_ko': False}

    def get_captures(self, color: Color) -> int:
        """获取某方的提子数"""
        return self._captures.get(color, 0)

    def coord_to_gtp(self, row: int, col: int) -> str:
        """
        将坐标转换为GTP格式（如 "Q16"）
        参考 Sabaki 的 stringifyVertex
        """
        if row is None or col is None:
            return "pass"

        # GTP坐标：列用字母A-T（不含I），行用数字1-19
        col_char = chr(ord('A') + col)
        if col_char >= 'I':
            col_char = chr(ord(col_char) + 1)

        row_num = self.size - row

        return f"{col_char}{row_num}"

    def gtp_to_coord(self, gtp: str) -> Optional[Tuple[int, int]]:
        """
        将GTP坐标转换为内部坐标
        参考 Sabaki 的 parseVertex
        """
        if not gtp or gtp.lower() == 'pass':
            return None

        gtp = gtp.strip().upper()
        if len(gtp) < 2:
            return None

        col_char = gtp[0]
        try:
            row_num = int(gtp[1:])
        except ValueError:
            return None

        # 转换列
        if col_char >= 'I':
            col = ord(col_char) - ord('A') - 1
        else:
            col = ord(col_char) - ord('A')

        # 转换行
        row = self.size - row_num

        if 0 <= row < self.size and 0 <= col < self.size:
            return (row, col)

        return None

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


# =========================================================================
# 增强打劫检测和劫材查找功能（基于 Sabaki 风格）
# =========================================================================

def find_ko_threats(board: GoBoard, color: Color, min_value: float = 0.1) -> List[Tuple[int, int, float]]:
    """
    查找可能的劫材位置
    基于 Sabaki 风格的棋盘分析

    劫材的定义：
    1. 能够威胁对方大块棋子的位置
    2. 能够破坏对方眼形的位置
    3. 能够切断对方棋子的位置
    4. 能够吃掉对方棋子的位置

    Args:
        board: 棋盘实例
        color: 当前要下的一方
        min_value: 最小劫材价值（0-1之间）

    Returns:
        劫材列表，每个元素为 (row, col, value)，按价值排序
    """
    threats = []
    opponent = color.opponent()

    for r in range(board.size):
        for c in range(board.size):
            if board.get(r, c) != Color.EMPTY:
                continue

            # 检查这个位置是否是合法的劫材
            analysis = board.analyze_move(r, c, color)
            if analysis['ko'] or analysis['overwrite']:
                continue

            # 模拟落子
            test_board = board.make_move(r, c, color)

            value = 0.0

            # 1. 能够提子（直接吃掉对方棋子）- 高价值劫材
            if analysis['capturing']:
                # 计算提子数量
                captured_diff = test_board.get_captures(color) - board.get_captures(color)
                if captured_diff > 0:
                    value += min(captured_diff * 0.2, 0.8)  # 最多0.8

            # 2. 能够威胁对方大块棋子（减少对方棋子的气）
            threatened_stones = _count_threatened_stones(board, r, c, color)
            if threatened_stones > 5:
                value += min(threatened_stones * 0.05, 0.6)  # 最多0.6

            # 3. 能够破坏对方眼形
            if _is_eye_breaking_move(board, r, c, color):
                value += 0.4

            # 4. 能够切断对方棋子
            if _is_cutting_move(board, r, c, color):
                value += 0.3

            # 5. 如果是急所（双方都想下的点）
            if _is_vital_point(board, r, c):
                value += 0.2

            if value >= min_value:
                threats.append((r, c, value))

    # 按价值排序
    threats.sort(key=lambda x: x[2], reverse=True)
    return threats


def _count_threatened_stones(board: GoBoard, row: int, col: int, color: Color) -> int:
    """计算这手棋能威胁到对方多少棋子（使其只剩1-2气）"""
    opponent = color.opponent()
    threatened = 0

    # 检查四周的对方棋子
    for nr, nc in board.get_neighbors(row, col):
        if board.get(nr, nc) == opponent:
            liberties = board.get_liberties(nr, nc)
            # 如果落子后对方棋子只剩1-2气，视为被威胁
            if 1 <= len(liberties) <= 2:
                chain = board.get_chain(nr, nc)
                threatened += len(chain)

    return threatened


def _is_eye_breaking_move(board: GoBoard, row: int, col: int, color: Color) -> bool:
    """判断是否是破眼的好手"""
    opponent = color.opponent()

    # 检查四周是否有对方的眼形
    eye_count = 0
    for nr, nc in board.get_neighbors(row, col):
        if _is_potential_eye(board, nr, nc, opponent):
            eye_count += 1

    # 如果破坏2个以上的眼位点，视为破眼好手
    return eye_count >= 2


def _is_potential_eye(board: GoBoard, row: int, col: int, color: Color) -> bool:
    """判断某点是否是某方的潜在眼位"""
    if board.get(row, col) != Color.EMPTY:
        return False

    # 检查四周是否 mostly 是该颜色的棋子或边界
    color_count = 0
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    for dr, dc in directions:
        nr, nc = row + dr, col + dc
        if board.has(nr, nc):
            if board.get(nr, nc) == color:
                color_count += 1
        else:
            # 边界也算
            color_count += 1

    # 如果3-4个方向都是该颜色，视为潜在眼位
    return color_count >= 3


def _is_cutting_move(board: GoBoard, row: int, col: int, color: Color) -> bool:
    """判断是否是切断对方棋子的手筋"""
    opponent = color.opponent()

    # 检查四周是否有对方的连接棋子
    opponent_groups = []

    for nr, nc in board.get_neighbors(row, col):
        if board.get(nr, nc) == opponent:
            group = board.get_chain(nr, nc)
            if group not in opponent_groups:
                opponent_groups.append(group)

    # 如果能连接2个以上的对方棋子群，视为切断
    return len(opponent_groups) >= 2


def _is_vital_point(board: GoBoard, row: int, col: int) -> bool:
    """判断是否是急所（双方都想下的重要点）"""
    has_black = False
    has_white = False

    for nr, nc in board.get_neighbors(row, col):
        color = board.get(nr, nc)
        if color == Color.BLACK:
            has_black = True
        elif color == Color.WHITE:
            has_white = True

    return has_black and has_white
