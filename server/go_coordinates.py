#!/usr/bin/env python3
"""
围棋坐标转换工具模块

统一处理 GBR 坐标 (A, B) 和 GTP 坐标之间的转换

坐标系统说明：
1. GBR 坐标 (A, B):
   - A: 水平位置，1-based (1-19)，1 在左边，19 在右边
   - B: 垂直位置，1-based (1-19)，1 在底部，19 在顶部

2. 数组坐标 (row, col):
   - row: 行号，0-based (0-18)，0 在顶部，18 在底部
   - col: 列号，0-based (0-18)，0 在左边，18 在右边

3. GTP 坐标 (如 "A1", "T19"):
   - 列：字母 A-T（跳过 I），A 在左边，T 在右边
   - 行：数字 1-19，1 在底部，19 在顶部
   - 例如：A1 是左下角，T19 是右上角
"""

from typing import Optional, Tuple


def gbr_to_array(a: int, b: int, board_size: int = 19) -> Tuple[int, int]:
    """
    将 GBR 坐标 (A, B) 转换为数组坐标 (row, col)
    
    Args:
        a: GBR 水平位置 (1-based, 1-19)
        b: GBR 垂直位置 (1-based, 1-19, 1 在底部)
        board_size: 棋盘大小，默认 19
        
    Returns:
        (row, col) 数组坐标 (0-based)
        
    Examples:
        >>> gbr_to_array(1, 1, 19)  # 左下角
        (18, 0)
        >>> gbr_to_array(19, 19, 19)  # 右上角
        (0, 18)
        >>> gbr_to_array(4, 10, 19)  # D10
        (9, 3)
    """
    # A 从 1-based 转为 0-based
    col = a - 1
    # B 从 1-based 转为 0-based，然后翻转（B 从下往上，row 从上往下）
    row = board_size - b
    return (row, col)


def array_to_gbr(row: int, col: int, board_size: int = 19) -> Tuple[int, int]:
    """
    将数组坐标 (row, col) 转换为 GBR 坐标 (A, B)
    
    Args:
        row: 行坐标 (0-based, 0-18)
        col: 列坐标 (0-based, 0-18)
        board_size: 棋盘大小，默认 19
        
    Returns:
        (A, B) GBR 坐标 (1-based)
        
    Examples:
        >>> array_to_gbr(18, 0, 19)  # 左下角
        (1, 1)
        >>> array_to_gbr(0, 18, 19)  # 右上角
        (19, 19)
        >>> array_to_gbr(9, 3, 19)  # D10
        (4, 10)
    """
    # col 从 0-based 转为 1-based
    a = col + 1
    # row 翻转并转为 1-based（row 从上往下，B 从下往上）
    b = board_size - row
    return (a, b)


def array_to_gtp(row: int, col: int, board_size: int = 19) -> str:
    """
    将数组坐标 (row, col) 转换为 GTP 坐标
    
    Args:
        row: 行坐标 (0-based, 0-18)，0 在顶部
        col: 列坐标 (0-based, 0-18)，0 在左边
        board_size: 棋盘大小，默认 19
        
    Returns:
        GTP 格式坐标字符串（如 "A1", "T19"）
        
    Examples:
        >>> array_to_gtp(18, 0, 19)  # 左下角
        'A1'
        >>> array_to_gtp(0, 18, 19)  # 右上角
        'T19'
        >>> array_to_gtp(9, 3, 19)  # D10
        'D10'
    """
    if row is None or col is None:
        return "pass"
    
    # 列：A-T，跳过 I
    # A=0, B=1, ..., H=7, J=8 (跳过I), K=9, ..., T=18
    if col >= 8:
        col_char = chr(ord('A') + col + 1)  # 跳过 I
    else:
        col_char = chr(ord('A') + col)
    
    # GTP 的行号：1 是底部，19 是顶部
    # 数组的 row：0 是顶部，18 是底部
    row_gtp = board_size - row
    return f"{col_char}{row_gtp}"


def gtp_to_array(gtp_str: str, board_size: int = 19) -> Tuple[Optional[int], Optional[int]]:
    """
    将 GTP 坐标转换为数组坐标 (row, col)
    
    Args:
        gtp_str: GTP 格式坐标（如 "A1", "D16", "pass"）
        board_size: 棋盘大小，默认 19
        
    Returns:
        (row, col) 数组坐标，pass 返回 (None, None)
        
    Examples:
        >>> gtp_to_array("A1", 19)  # 左下角
        (18, 0)
        >>> gtp_to_array("T19", 19)  # 右上角
        (0, 18)
        >>> gtp_to_array("D10", 19)
        (9, 3)
        >>> gtp_to_array("pass", 19)
        (None, None)
    """
    gtp_str = gtp_str.upper().strip()
    if gtp_str == "PASS" or gtp_str == "":
        return (None, None)
    
    if len(gtp_str) < 2:
        return (None, None)
    
    col_char = gtp_str[0]
    row_str = gtp_str[1:]
    
    # 列：A-T，跳过 I
    # A=0, B=1, ..., H=7, J=8 (跳过I), K=9, ..., T=18
    if col_char < 'I':
        col = ord(col_char) - ord('A')
    else:
        col = ord(col_char) - ord('A') - 1
    
    try:
        row_gtp = int(row_str)  # GTP 行号（1-19）
        # 转换为数组行号：GTP 的 1 是底部，数组的 0 是顶部
        row = board_size - row_gtp
    except ValueError:
        return (None, None)
    
    if not (0 <= row < board_size and 0 <= col < board_size):
        return (None, None)
    
    return (row, col)


def gbr_to_gtp(a: int, b: int, board_size: int = 19) -> str:
    """
    将 GBR 坐标 (A, B) 直接转换为 GTP 坐标
    
    Args:
        a: GBR 水平位置 (1-based)
        b: GBR 垂直位置 (1-based, 1 在底部)
        board_size: 棋盘大小，默认 19
        
    Returns:
        GTP 格式坐标字符串
        
    Examples:
        >>> gbr_to_gtp(1, 1, 19)  # 左下角
        'A1'
        >>> gbr_to_gtp(19, 19, 19)  # 右上角
        'T19'
        >>> gbr_to_gtp(4, 10, 19)  # D10
        'D10'
    """
    row, col = gbr_to_array(a, b, board_size)
    return array_to_gtp(row, col, board_size)


def gtp_to_gbr(gtp_str: str, board_size: int = 19) -> Tuple[Optional[int], Optional[int]]:
    """
    将 GTP 坐标直接转换为 GBR 坐标 (A, B)
    
    Args:
        gtp_str: GTP 格式坐标
        board_size: 棋盘大小，默认 19
        
    Returns:
        (A, B) GBR 坐标，pass 返回 (None, None)
        
    Examples:
        >>> gtp_to_gbr("A1", 19)  # 左下角
        (1, 1)
        >>> gtp_to_gbr("T19", 19)  # 右上角
        (19, 19)
        >>> gtp_to_gbr("D10", 19)
        (4, 10)
    """
    row, col = gtp_to_array(gtp_str, board_size)
    if row is None or col is None:
        return (None, None)
    return array_to_gbr(row, col, board_size)


def format_position(row: int, col: int, board_size: int = 19) -> str:
    """
    格式化位置为人类可读格式
    
    Args:
        row: 行坐标 (0-based)
        col: 列坐标 (0-based)
        board_size: 棋盘大小，默认 19
        
    Returns:
        格式化字符串，如 "D10 (第10行, 第4列)"
    """
    gtp = array_to_gtp(row, col, board_size)
    return f"{gtp} (第{row+1}行, 第{col+1}列)"


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("坐标转换测试")
    print("=" * 60)
    
    # 测试 GBR 到数组
    print("\n【GBR → 数组】")
    test_cases = [
        ((1, 1), "左下角"),
        ((19, 19), "右上角"),
        ((4, 10), "D10"),
        ((16, 4), "Q4"),
    ]
    for (a, b), desc in test_cases:
        row, col = gbr_to_array(a, b)
        print(f"GBR({a}, {b}) {desc:8} → 数组({row:2}, {col:2})")
    
    # 测试数组到 GTP
    print("\n【数组 → GTP】")
    test_cases = [
        ((18, 0), "左下角"),
        ((0, 18), "右上角"),
        ((9, 3), "D10"),
        ((15, 15), "Q4"),
    ]
    for (row, col), desc in test_cases:
        gtp = array_to_gtp(row, col)
        print(f"数组({row:2}, {col:2}) {desc:8} → GTP {gtp}")
    
    # 测试 GTP 到数组
    print("\n【GTP → 数组】")
    test_cases = [
        ("A1", "左下角"),
        ("T19", "右上角"),
        ("D10", "D10"),
        ("Q4", "Q4"),
    ]
    for gtp, desc in test_cases:
        row, col = gtp_to_array(gtp)
        print(f"GTP {gtp:4} {desc:8} → 数组({row:2}, {col:2})")
    
    # 测试 GBR 到 GTP
    print("\n【GBR → GTP】")
    test_cases = [
        ((1, 1), "左下角"),
        ((19, 19), "右上角"),
        ((4, 10), "D10"),
        ((16, 4), "Q4"),
    ]
    for (a, b), desc in test_cases:
        gtp = gbr_to_gtp(a, b)
        print(f"GBR({a:2}, {b:2}) {desc:8} → GTP {gtp}")
    
    print("\n" + "=" * 60)

