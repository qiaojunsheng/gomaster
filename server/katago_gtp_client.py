"""
KataGo GTP 客户端
用于与 KataGo 引擎进行 GTP 协议通信
"""
import subprocess
import threading
import queue
import os
import time
from typing import Optional, Tuple
from go_coordinates import array_to_gtp, gtp_to_array


class KataGoGTPClient:
    """KataGo GTP 协议客户端"""
    
    def __init__(self, 
                 katago_path: str,
                 model_path: str,
                 config_path: str,
                 timeout: float = 30.0,
                 genmove_timeout: float = 120.0,
                 use_mps: bool = True,
                 fast_config: bool = False):
        """
        初始化 KataGo GTP 客户端
        
        Args:
            katago_path: KataGo 可执行文件路径
            model_path: KataGo 模型文件路径（可以指定特定模型）
            config_path: KataGo 配置文件路径
            timeout: 普通命令超时时间（秒）
            genmove_timeout: genmove 命令超时时间（秒）
            use_mps: 是否使用Apple MPS（Metal后端），默认True
                     注意：需要KataGo编译时启用Metal后端才能使用MPS
            fast_config: 是否使用快速配置文件（gtp_fast.cfg），默认False
        """
        self.katago_path = katago_path
        self.model_path = model_path
        self.timeout = timeout
        self.genmove_timeout = genmove_timeout
        self.use_mps = use_mps  # 始终设置use_mps属性
        
        # 如果指定使用快速配置，尝试使用gtp_fast.cfg
        if fast_config:
            import os
            fast_config_path = config_path.replace('gtp_example.cfg', 'gtp_fast.cfg')
            if os.path.exists(fast_config_path):
                self.config_path = fast_config_path
                print(f"[KataGo] 使用快速配置文件: {fast_config_path}")
            else:
                self.config_path = config_path
                print(f"[KataGo] 快速配置文件不存在，使用默认配置: {config_path}")
        else:
            self.config_path = config_path
        
        self.komi = 7.5  # 默认贴目（可以根据需要调整）
        
        self.process = None
        self.response_queue = queue.Queue()
        self.response_thread = None
        self.is_connected = False
        self.backend_detected = None  # 用于存储检测到的后端类型（Metal/Eigen）
        self.katago_config = {}  # 存储KataGo配置参数
        
        # 解析配置文件
        self._parse_config_file()
        
        # 启动 KataGo 进程
        self._start_katago()
    
    def _parse_config_file(self):
        """解析KataGo配置文件，提取关键参数"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('#') or not line:
                            continue
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            # 尝试转换为数字
                            try:
                                if '.' in value:
                                    value = float(value)
                                else:
                                    value = int(value)
                            except ValueError:
                                pass
                            self.katago_config[key] = value
                print(f"[KataGo] 已解析配置文件: {len(self.katago_config)} 个参数")
                # 调试：打印关键配置值
                cache_val = self.katago_config.get('nnCacheSizePowerOfTwo', 'NOT FOUND')
                print(f"[KataGo] nnCacheSizePowerOfTwo = {cache_val}")
        except Exception as e:
            print(f"[KataGo] 解析配置文件失败: {e}")
            self.katago_config = {}
    
    def _start_katago(self):
        """启动 KataGo 进程"""
        try:
            # 构建命令
            cmd = [
                self.katago_path,
                'gtp',
                '-model', self.model_path,
                '-config', self.config_path
            ]
            
            # 如果使用MPS，确保KataGo使用Metal后端
            # 注意：KataGo需要在编译时启用Metal后端才能使用MPS
            env = os.environ.copy()
            if self.use_mps:
                # KataGo会自动检测并使用Metal后端（如果已编译）
                # 不需要设置环境变量，KataGo会自动检测
                print(f"[KataGo] 尝试使用Apple MPS（Metal后端）进行推理")
                print(f"[KataGo] 注意：需要KataGo编译时启用Metal后端才能使用MPS")
                print(f"[KataGo] 如果未启用Metal，将回退到CPU（Eigen后端）")
            
            # 启动进程
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 将 stderr 重定向到 stdout，统一处理
                text=True,
                bufsize=1,
                env=env  # 使用修改后的环境变量
            )
            
            # 启动响应读取线程
            self.response_thread = threading.Thread(
                target=self._read_responses,
                daemon=True
            )
            self.response_thread.start()
            
            # 等待 KataGo 初始化（给时间让后端检测完成）
            time.sleep(2)  # 快棋模式：减少等待时间
            
            # 如果还没有检测到后端，再等待一下
            if self.backend_detected is None:
                time.sleep(1)
                if self.backend_detected is None:
                    print(f"[KataGo] ⚠️  未能从启动输出中检测到后端类型")
                    print(f"[KataGo] 提示: 请检查KataGo是否编译时启用了Metal后端")
            
            # 初始化 KataGo（发送必要的配置命令）
            try:
                # 测试连接
                response = self.send_command('name', timeout=10.0)
                if response:
                    self.is_connected = True
                    print(f"[KataGo] 连接成功: {response}")
                    # 如果已检测到后端，再次确认
                    if self.backend_detected:
                        if self.backend_detected == "Metal":
                            print(f"[KataGo] ✅ 当前使用后端: {self.backend_detected} (MPS加速已启用)")
                        elif self.backend_detected == "Eigen":
                            print(f"[KataGo] ⚠️  当前使用后端: {self.backend_detected} (CPU模式，未使用MPS)")
                            if self.use_mps:
                                print(f"[KataGo] 提示: 如果希望使用MPS加速，请确保KataGo编译时启用了Metal后端")
                        else:
                            print(f"[KataGo] 当前使用后端: {self.backend_detected}")
                else:
                    print("[KataGo] 警告: 无法获取引擎名称")
                
                # 设置棋盘大小（确保是 19x19）
                self.send_command('boardsize 19', timeout=5.0)
                print("[KataGo] 已设置棋盘大小: 19x19")
                
                # 设置贴目（中国规则：黑贴7.5目）
                self.send_command(f'komi {self.komi}', timeout=5.0)
                print(f"[KataGo] 已设置贴目: {self.komi}（中国规则）")
                
                # 清空棋盘
                self.send_command('clear_board', timeout=5.0)
                print("[KataGo] 已清空棋盘")
                
            except Exception as e:
                print(f"[KataGo] 初始化命令失败: {e}")
                # 即使初始化命令失败，也继续（可能是 KataGo 已经配置好了）
                self.is_connected = True
                
        except Exception as e:
            print(f"[KataGo] 启动失败: {e}")
            raise
    
    def _read_responses(self):
        """读取 KataGo 响应（后台线程）"""
        try:
            while self.process and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    line = line.strip()
                    if line:
                        # 检测后端类型（仅在启动时检测一次）
                        if self.backend_detected is None:
                            line_lower = line.lower()
                            if 'metal' in line_lower or 'mps' in line_lower:
                                self.backend_detected = 'Metal'
                                print(f"[KataGo] ✅ 检测到Metal后端（MPS加速已启用）")
                                print(f"[KataGo] 输出: {line}")
                                print(f"[KataGo] 所有后续推理将使用MPS（Metal）芯片加速")
                                print(f"[KataGo] 所有后续推理将使用MPS（Metal）芯片加速")
                            elif 'eigen' in line_lower or 'cpu' in line_lower:
                                self.backend_detected = 'Eigen'
                                if self.use_mps:
                                    print(f"[KataGo] ⚠️  警告: 检测到Eigen后端（CPU模式）")
                                    print(f"[KataGo] 输出: {line}")
                                    print(f"[KataGo] 提示: 如果希望使用MPS加速，请确保KataGo编译时启用了Metal后端")
                                    print(f"[KataGo] 编译命令: cmake .. -DBUILD_METAL=ON")
                                else:
                                    print(f"[KataGo] 使用Eigen后端（CPU模式）")
                        
                        # 过滤掉一些明显的调试信息，但保留所有可能包含响应的行
                        # KataGo 可能会输出一些信息性消息，我们需要识别真正的 GTP 响应
                        self.response_queue.put(line)
        except Exception as e:
            print(f"[KataGo] 读取响应错误: {e}")
            import traceback
            traceback.print_exc()
    
    def send_command(self, command: str, command_id: Optional[int] = None, timeout: Optional[float] = None) -> Optional[str]:
        """
        发送 GTP 命令并获取响应
        
        Args:
            command: GTP 命令（不含 ID）
            command_id: 可选的命令 ID（如果为None，自动生成）
            timeout: 可选的超时时间（秒），如果为 None 则使用默认超时
            
        Returns:
            响应内容（去除 ID 前缀）
        """
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("KataGo 进程未运行")
        
        # 确定超时时间
        if timeout is None:
            # genmove 命令使用更长的超时时间
            if command.strip().startswith('genmove'):
                timeout = self.genmove_timeout
            else:
                timeout = self.timeout
        
        # 如果没有提供命令ID，自动生成一个
        if command_id is None:
            import random
            command_id = random.randint(1, 999999)
        
        # 构建完整命令
        full_command = f"{command_id} {command}\n"
        
        # 清空响应队列中的旧响应
        # 对于clear_board等简单命令，完全清空队列以避免混淆
        # 对于其他命令，也清空队列，因为每个命令都有唯一的ID
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break
        
        # 发送命令
        try:
            self.process.stdin.write(full_command)
            self.process.stdin.flush()
            # 只在调试模式下打印
            # print(f"[KataGo] 发送命令: {command.strip()}")
        except Exception as e:
            raise RuntimeError(f"发送命令失败: {e}")
        
        # 等待响应（使用命令ID匹配）
        start_time = time.time()
        response_lines = []
        got_response = False
        is_multiline = command.strip() == 'showboard'  # showboard 是多行响应
        cmd_id_str = str(command_id)
        
        while time.time() - start_time < timeout:
            try:
                line = self.response_queue.get(timeout=0.2)  # 快棋模式：减少轮询间隔

                if not line:
                    continue
                
                line = line.strip()
                if not line:
                    continue
                
                print(f"[KataGo] 收到响应: {line[:100]}")  # 只打印前100个字符
                
                # 检查是否是针对当前命令的响应（通过命令ID匹配）
                if line.startswith('=') or line.startswith('?'):
                    # 提取响应中的命令ID
                    parts = line[1:].strip().split(None, 1)
                    if parts and parts[0] == cmd_id_str:
                        # 这是我们要找的响应
                        got_response = True
                        if line.startswith('='):
                            # 成功响应
                            if len(parts) > 1:
                                response_lines.append(parts[1])
                            else:
                                response_lines.append("")
                            
                            # 如果是 showboard，继续读取多行直到下一个 '='
                            if is_multiline:
                                continue
                            else:
                                break
                        else:
                            # 错误响应
                            error_msg = parts[1] if len(parts) > 1 else "未知错误"
                            print(f"[KataGo] 错误响应: {line}")
                            raise RuntimeError(f"KataGo 错误: {error_msg}")
                    else:
                        # 这是其他命令的响应，忽略
                        print(f"[KataGo] 忽略其他命令的响应: {line[:50]}")
                        continue
                elif line.startswith('#'):
                    # 注释行，继续读取（KataGo 可能输出调试信息）
                    continue
                else:
                    # 其他响应
                    if is_multiline and got_response:
                        # showboard 的多行内容
                        response_lines.append(line)
                        # 继续读取直到遇到下一个 '=' 或超时
                        continue
                    elif got_response:
                        # 已经收到响应，这可能是下一行的开始
                        break
                    else:
                        # 还没有收到响应，继续等待
                        continue
                    
            except queue.Empty:
                # 检查进程是否还在运行
                if self.process.poll() is not None:
                    raise RuntimeError("KataGo 进程意外退出")
                # 如果是多行响应且已经收到开始，可以结束
                if is_multiline and got_response and response_lines:
                    break
                continue
        
        if not got_response:
            # 检查进程状态
            if self.process.poll() is not None:
                raise RuntimeError(f"KataGo 进程退出，命令超时: {command}")
            else:
                raise RuntimeError(f"命令超时 ({timeout}秒): {command}")
        
        return ' '.join(response_lines) if response_lines else ""
    
    def coord_to_gtp(self, row: int, col: int) -> str:
        """
        坐标转换为 GTP 格式（如 A1, T19）
        
        Args:
            row: 行坐标 (0-18)，0 是顶部，18 是底部
            col: 列坐标 (0-18)，0 是左边，18 是右边
            
        Returns:
            GTP 格式坐标（如 "A1", "T19"）
        Note:
            使用统一的坐标转换模块 go_coordinates
        """
        return array_to_gtp(row, col, board_size=19)
    
    def gtp_to_coord(self, gtp_str: str) -> Tuple[Optional[int], Optional[int]]:
        """
        GTP 格式转换为坐标
        
        Args:
            gtp_str: GTP 格式坐标（如 "A1", "D16", "pass"）
            
        Returns:
            (row, col) 坐标，pass 返回 (None, None)
        Note:
            使用统一的坐标转换模块 go_coordinates
        """
        row, col = gtp_to_array(gtp_str, board_size=19)
        return (row, col)
    
    def clear_board(self):
        """清空棋盘"""
        self.send_command('clear_board')
    
    def set_komi(self, komi: float):
        """
        设置贴目
        
        Args:
            komi: 贴目值（例如 7.5, 10.5, 0 等）
                 标准贴目: 7.5（黑棋贴7.5目）
                 让先: 0（黑棋不贴目）
                 增加贴目: 10.5, 15.5 等（白棋优势更大）
        """
        if not (-150 <= komi <= 150):
            raise ValueError(f"贴目值必须在 -150 到 150 之间，当前值: {komi}")
        self.komi = komi
        self.send_command(f'komi {komi}')
        print(f"[KataGo] 已设置贴目: {komi}")
    
    def set_handicap(self, num_stones: int):
        """
        设置让子
        
        Args:
            num_stones: 让子数量（2, 3, 4, 5, 6, 7, 8, 9）
                        让子越多，KataGo越容易输
                        标准让子: 2-4子
                        高让子: 5-9子
        """
        if not (2 <= num_stones <= 9):
            raise ValueError(f"让子数量必须在 2 到 9 之间，当前值: {num_stones}")
        self.send_command(f'place_free_handicap {num_stones}')
        print(f"[KataGo] 已设置让子: {num_stones}子")
    
    def set_advantage_for_katago(self, katago_color: str = "B", advantage_level: str = "medium"):
        """
        设置KataGo的优势，让KataGo更容易赢棋
        
        Args:
            katago_color: KataGo执棋颜色 ("B" 或 "W")
            advantage_level: 优势级别
                - "small": 小优势（轻微调整）
                - "medium": 中等优势（推荐）
                - "large": 大优势（明显优势）
                - "extreme": 极大优势（几乎必胜）
        """
        if advantage_level == "small":
            if katago_color == "B":
                # KataGo执黑：减少贴目
                self.set_komi(6.5)
            else:
                # KataGo执白：增加贴目
                self.set_komi(8.5)
        elif advantage_level == "medium":
            if katago_color == "B":
                # KataGo执黑：让先（不贴目）
                self.set_komi(0)
            else:
                # KataGo执白：大幅增加贴目
                self.set_komi(10.5)
        elif advantage_level == "large":
            if katago_color == "B":
                # KataGo执黑：负贴目（黑棋优势）
                self.set_komi(-3.5)
            else:
                # KataGo执白：大幅增加贴目
                self.set_komi(15.5)
        elif advantage_level == "extreme":
            if katago_color == "B":
                # KataGo执黑：大幅负贴目
                self.set_komi(-10.5)
            else:
                # KataGo执白：极大贴目（白棋需要更高的贴目才能取胜）
                self.set_komi(25.5)
        else:
            raise ValueError(f"无效的优势级别: {advantage_level}，可选: small, medium, large, extreme")
        
        print(f"[KataGo] 已设置优势: KataGo执{katago_color}，优势级别={advantage_level}，贴目={self.komi}")
    
    def set_opponent_handicap(self, num_stones: int):
        """
        给对手设置让子（让KataGo处于优势）
        
        Args:
            num_stones: 让子数量（2, 3, 4, 5, 6, 7, 8, 9）
                        让子越多，对手越劣势，KataGo越容易赢
        """
        if not (2 <= num_stones <= 9):
            raise ValueError(f"让子数量必须在 2 到 9 之间，当前值: {num_stones}")
        # 注意：place_free_handicap 是给黑棋让子
        # 如果KataGo执白，给黑棋让子就是给对手让子
        self.send_command(f'place_free_handicap {num_stones}')
        print(f"[KataGo] 已给对手设置让子: {num_stones}子（KataGo优势）")
    
    def play(self, row: int, col: int, color: str) -> bool:
        """
        落子
        
        Args:
            row: 行坐标 (0-18)
            col: 列坐标 (0-18)
            color: 颜色 ("B" 或 "W")
            
        Returns:
            是否成功
        """
        if row is None or col is None:
            # 过手
            try:
                response = self.send_command(f'play {color} pass')
                return response == "" or "illegal" not in response.lower()
            except RuntimeError as e:
                print(f"[KataGo] play pass 失败: {e}")
                raise
        
        gtp_coord = self.coord_to_gtp(row, col)
        
        try:
            # 优化：使用更短的超时时间，因为play命令应该很快
            # 从2.0秒优化到0.5秒，可以显著减少play命令的等待时间
            response = self.send_command(f'play {color} {gtp_coord}', timeout=0.5)
            
            if response and "illegal" in response.lower():
                return False
            return True
        except RuntimeError as e:
            raise
    
    def play_many(self, moves: list, color: str) -> bool:
        """
        批量落子（优化：减少通信次数）
        
        Args:
            moves: 落子列表，每个元素为 (row, col) 元组
            color: 颜色 ("B" 或 "W")
            
        Returns:
            是否成功
        Note:
            虽然GTP协议不支持真正的批量命令，但我们可以优化超时时间
            以减少总耗时。实际实现仍然是逐个发送，但使用更短的超时时间。
        """
        if not moves:
            return True
        
        # 优化：使用更短的超时时间，因为play命令应该很快
        # 虽然仍然是逐个发送，但可以减少等待时间
        # 从1.0秒优化到0.5秒，可以显著减少批量play的总耗时
        for row, col in moves:
            try:
                if row is None or col is None:
                    self.send_command(f'play {color} pass', timeout=0.5)
                else:
                    gtp_coord = self.coord_to_gtp(row, col)
                    response = self.send_command(f'play {color} {gtp_coord}', timeout=0.5)
                    if response and "illegal" in response.lower():
                        print(f"[KataGo] 警告: 非法落子 {gtp_coord}")
            except RuntimeError as e:
                print(f"[KataGo] play {gtp_coord if row is not None and col is not None else 'pass'} 失败: {e}")
                # 继续执行其他落子，不中断
        
        return True
    
    def genmove(self, color: str, fast_mode: bool = False, maximize_score: bool = True,
                max_visits: Optional[int] = None, max_time: Optional[float] = None,
                playout_doubling_advantage: Optional[float] = None,
                win_komi: Optional[float] = None) -> Tuple[Optional[int], Optional[int]]:
        if maximize_score:
            actual_max_time = max_time if max_time else 0.8
            actual_pda = playout_doubling_advantage if playout_doubling_advantage is not None else 2.5

            # 不设置win_komi，让KataGo自然追求最大目数，不设截止目标
            # 使用标准贴目7.5，不欺骗KataGo

            # 设置maxTime和maxVisits（参考wq.py）
            self.send_command(f'kata-set-param maxTime {actual_max_time}', timeout=1.0)
            if max_visits is not None:
                self.send_command(f'kata-set-param maxVisits {max_visits}', timeout=1.0)
            self.send_command(f'kata-set-param playoutDoublingAdvantage {actual_pda}', timeout=1.0)
            self.send_command(f'kata-set-param playoutDoublingAdvantagePla {"BLACK" if color == "B" else "WHITE"}', timeout=1.0)

            # 使用更合理的超时时间：max_time + 5秒缓冲，确保KataGo有足够时间完成计算
            timeout_value = actual_max_time + 5.0
            response = self.send_command(f'genmove {color}', timeout=timeout_value)
            if not response:
                return (None, None)
            return self.gtp_to_coord(response.strip().upper())
        elif fast_mode:
            fast_max_time = max_time if max_time else 0.4
            self.send_command(f'kata-set-param maxTime {fast_max_time}', timeout=1.0)
            response = self.send_command(f'genmove {color}', timeout=min(self.genmove_timeout, 5.0))
        else:
            actual_max_time = max_time if max_time else 1.0
            self.send_command(f'kata-set-param maxTime {actual_max_time}', timeout=1.0)
            response = self.send_command(f'genmove {color}', timeout=min(self.genmove_timeout, actual_max_time + 5.0))
        
        if not response:
            return (None, None)
        
        response = response.strip().upper()
        return self.gtp_to_coord(response)
    
    def showboard(self) -> str:
        """显示棋盘（用于调试）"""
        return self.send_command('showboard')
    
    def get_board_state(self) -> Optional[list]:
        """
        从 KataGo 获取当前棋盘状态
        
        Returns:
            19x19 的棋盘状态列表，0=空, 1=黑, 2=白，如果失败返回 None
        """
        try:
            # 使用 showboard 命令获取棋盘状态
            board_str = self.showboard()
            
            if not board_str:
                return None
            
            # 解析棋盘字符串（KataGo 的 showboard 输出格式）
            # 格式类似：
            #    A B C D E F G H J K L M N O P Q R S T
            # 19 . . . . . . . . . . . . . . . . . . .
            # 18 . . . . . . . . . . . . . . . . . . .
            # ...
            
            board = [[0 for _ in range(19)] for _ in range(19)]
            
            lines = board_str.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 跳过表头和其他非数据行
                if line.startswith('A B C') or line.startswith('MoveNum:') or line.startswith('HASH:'):
                    continue
                
                # 跳过非数字开头的行
                if not line[0].isdigit():
                    continue
                
                # 解析行号
                parts = line.split()
                if len(parts) < 2:
                    continue
                
                try:
                    row_num = int(parts[0])
                    if 1 <= row_num <= 19:
                        row_idx = 19 - row_num  # 转换为数组索引（0-18），GTP的19行对应数组的0行
                        
                        # 解析棋子：KataGo 的 showboard 格式是 "19 . . X . . ." 这样的
                        # 每个字符代表一个交叉点，包括空格
                        # 我们需要跳过行号，然后解析每个字符
                        stone_line = ' '.join(parts[1:])  # 重新组合，保留空格
                        col_idx = 0
                        for char in stone_line:
                            if col_idx >= 19:
                                break
                            if char == 'X' or char == 'x':
                                board[row_idx][col_idx] = 1  # 黑
                                col_idx += 1
                            elif char == 'O' or char == 'o':
                                board[row_idx][col_idx] = 2  # 白
                                col_idx += 1
                            elif char == '.' or char == ' ':
                                # 空点或空格，跳过
                                if char == '.':
                                    col_idx += 1
                                # 如果是空格，不增加 col_idx（空格只是分隔符）
                            # 其他字符忽略
                except (ValueError, IndexError) as e:
                    print(f"[KataGo] 解析棋盘行失败: {line}, 错误: {e}")
                    continue
            
            return board
        except Exception as e:
            print(f"[KataGo] 获取棋盘状态失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def estimate_score(self) -> Optional[dict]:
        """
        评估当前形势 - 已禁用，直接返回None以节省计算资源
        
        Returns:
            None（禁用形势判断）
        """
        # 禁用形势判断，避免额外的kata-analyze调用
        return None
    
    def get_recommended_moves(self, max_moves: int = 5, fast_mode: bool = False,
                              avoid_position: Optional[Tuple[int, int]] = None,
                              avoid_positions: Optional[list] = None,
                              max_time: Optional[float] = None,
                              max_visits: Optional[int] = None,
                              current_color: Optional[str] = None,
                              playout_doubling_advantage: Optional[float] = None) -> Optional[list]:
        """
        获取AI推荐的落子点（使用kata-analyze命令）

        Args:
            max_moves: 最多返回的推荐落子点数量
            fast_mode: 是否使用快速模式（降低分析时间以加快速度）
            avoid_position: 要排除的单个位置 (row, col)，用于打劫时排除打劫位置（已弃用，使用avoid_positions）
            avoid_positions: 要排除的位置列表 [(row, col), ...]，用于打劫时排除多个打劫位置
            max_time: 最大思考时间（秒），如果提供则设置全局maxTime参数
            max_visits: 最大访问次数，如果提供则设置全局maxVisits参数
            playout_doubling_advantage: PDA值，用于调整KataGo的激进程度

        Returns:
            推荐落子点列表，每个元素为：
            {
                'row': int,
                'col': int,
                'winrate': float,  # 胜率（0-100）
                'visits': int,     # 访问次数
                'prior': float,     # 先验概率（0-100）
                'scoreLead': float, # 分数领先
                'utility': float     # 综合效用值
            }
        """
        try:
            if current_color is None:
                current_color = self._get_current_color()
            if current_color is None:
                current_color = "B"
            
            # 如果提供了max_time或max_visits，设置全局参数
            if max_time is not None:
                try:
                    self.send_command(f'kata-set-param maxTime {max_time}', timeout=1.0)
                    print(f"[KataGo] 设置maxTime={max_time:.1f}秒（用于kata-analyze）")
                except Exception as e:
                    print(f"[KataGo] ⚠️ 设置maxTime失败: {e}")
            
            if max_visits is not None:
                try:
                    self.send_command(f'kata-set-param maxVisits {max_visits}', timeout=1.0)
                    print(f"[KataGo] 设置maxVisits={max_visits}（用于kata-analyze）")
                except Exception as e:
                    print(f"[KataGo] ⚠️ 设置maxVisits失败: {e}")
            
            # 设置PDA让KataGo更积极地追求胜率
            try:
                # 如果传入了 playout_doubling_advantage 参数，使用传入的值，否则默认2.5
                pda_value = playout_doubling_advantage if playout_doubling_advantage is not None else 2.5
                self.send_command(f'kata-set-param playoutDoublingAdvantage {pda_value}', timeout=1.0)
                self.send_command(f'kata-set-param playoutDoublingAdvantagePla {"BLACK" if current_color == "B" else "WHITE"}', timeout=1.0)
                print(f"[KataGo] 设置PDA={pda_value}（积极追求胜率）")
            except Exception as e:
                print(f"[KataGo] ⚠️ 设置PDA失败: {e}")
            
            # 轮巡间隔时间0.2秒（20 centiseconds）
            # interval 单位是百分之一秒（centiseconds），20 = 0.2秒
            analyze_command = f'kata-analyze {current_color} interval 20 maxmoves {max_moves} rootInfo true'
            
            # 处理排除位置（支持单个或多个位置）
            positions_to_avoid = []
            if avoid_positions is not None:
                # 使用新的avoid_positions参数（优先）
                positions_to_avoid = avoid_positions
            elif avoid_position is not None:
                # 兼容旧的avoid_position参数
                positions_to_avoid = [avoid_position]
            
            # 如果指定了要排除的位置（用于打劫），添加到命令中
            if positions_to_avoid:
                # 转换为GTP格式并去重
                avoid_gtp_list = []
                for pos in positions_to_avoid:
                    if isinstance(pos, tuple) and len(pos) == 2:
                        avoid_row, avoid_col = pos
                        avoid_gtp = self.coord_to_gtp(avoid_row, avoid_col)
                        if avoid_gtp not in avoid_gtp_list:
                            avoid_gtp_list.append(avoid_gtp)
                
                if avoid_gtp_list:
                    # avoid PLAYER VERTEX,VERTEX,... UNTILDEPTH
                    # UNTILDEPTH 设置为一个较大的值（如100）以确保在整个搜索深度中都排除该位置
                    avoid_str = ','.join(avoid_gtp_list)
                    analyze_command += f' avoid {current_color} {avoid_str} 100'
                    print(f"[KataGo] 排除位置: {avoid_str} (共{len(avoid_gtp_list)}个位置)")
            
            import random
            command_id = random.randint(1, 999999)
            cmd_id_str = str(command_id)
            
            # 清空响应队列
            while not self.response_queue.empty():
                try:
                    self.response_queue.get_nowait()
                except queue.Empty:
                    break
            
            # 发送命令
            full_command = f"{command_id} {analyze_command}\n"
            try:
                self.process.stdin.write(full_command)
                self.process.stdin.flush()
            except Exception as e:
                raise RuntimeError(f"发送命令失败: {e}")
            
            # 读取流式响应
            start_time = time.time()
            # 超时时间：如果提供了max_time，使用max_time+5秒；否则根据fast_mode决定
            if max_time is not None:
                timeout = max_time + 5.0  # 比maxTime稍长，确保能读取完整响应
                min_analysis_time = max_time  # 最小分析时间
            else:
                timeout = 5.0 if fast_mode else 10.0
                min_analysis_time = 2.0 if fast_mode else 6.0
            all_lines = []
            got_response_header = False
            
            while time.time() - start_time < timeout:
                try:
                    line = self.response_queue.get(timeout=0.2)  # 快棋模式：减少轮询间隔
                    if not line:
                        continue
                    
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 检查响应头
                    if line.startswith('=') or line.startswith('?'):
                        parts = line[1:].strip().split(None, 1)
                        if parts and parts[0] == cmd_id_str:
                            # 如果已经收到过响应头，且再次收到命令ID，说明是结束标记
                            if got_response_header:
                                # 结束标记（只有 =cmd_id 没有内容，或内容为空）
                                if len(parts) == 1 or not parts[1].strip():
                                    break
                            got_response_header = True
                            if line.startswith('?'):
                                error_msg = parts[1] if len(parts) > 1 else "未知错误"
                                raise RuntimeError(f"KataGo 分析错误: {error_msg}")
                            # 如果 =cmd_id 后面跟着 info，提取info部分
                            if len(parts) > 1 and parts[1].strip().startswith('info'):
                                all_lines.append(parts[1].strip())
                            continue
                    
                    # 收集所有 info 行
                    if got_response_header:
                        if line.startswith('info'):
                            all_lines.append(line)
                
                except queue.Empty:
                    # 如果已经过了最小分析时间，且收到过响应头，结束读取
                    elapsed = time.time() - start_time
                    if got_response_header and all_lines and elapsed >= min_analysis_time:
                        break
                    continue
            
            if not got_response_header:
                return None
            
            # 解析推荐落子点 - 使用字典去重，保留每个位置的最后一条记录
            print(f"[KataGo] 收到 {len(all_lines)} 行分析数据")
            # 打印前几行数据用于调试
            for i, line in enumerate(all_lines[:3]):
                print(f"[KataGo] 行{i+1}: {line[:100]}...")
            
            moves_dict = {}
            for line in all_lines:
                if 'info' not in line or 'move' not in line:
                    continue
                
                parts = line.split()
                try:
                    # 提取move坐标
                    move_idx = parts.index('move')
                    if move_idx + 1 >= len(parts):
                        continue
                    
                    move_str = parts[move_idx + 1]
                    coord = self.gtp_to_coord(move_str)
                    if coord is None:
                        continue
                    
                    row, col = coord
                    pos_key = (row, col)  # 使用坐标作为键去重
                    
                    # 提取胜率（winrate）
                    winrate = 0.0
                    try:
                        if 'winrate' in parts:
                            winrate_idx = parts.index('winrate')
                            if winrate_idx + 1 < len(parts):
                                raw_winrate = float(parts[winrate_idx + 1])
                                # lz-analyze 返回的是 0-10000 范围的整数（表示百分比*100）
                                # kata-analyze 返回的是 0-1 范围的浮点数
                                # 统一转换为 0-100 的百分比
                                if raw_winrate > 100:
                                    # lz-analyze 格式: 7493 -> 74.93%
                                    winrate = raw_winrate / 100
                                else:
                                    # kata-analyze 格式: 0.7493 -> 74.93%
                                    winrate = raw_winrate * 100
                    except (ValueError, IndexError):
                        pass
                    
                    # 提取访问次数（visits）
                    visits = 0
                    try:
                        if 'visits' in parts:
                            visits_idx = parts.index('visits')
                            if visits_idx + 1 < len(parts):
                                visits = int(parts[visits_idx + 1])
                    except (ValueError, IndexError):
                        pass
                    
                    # 提取目数差（scoreMean）
                    score_mean = 0.0
                    try:
                        if 'scoreMean' in parts:
                            score_idx = parts.index('scoreMean')
                            if score_idx + 1 < len(parts):
                                score_mean = float(parts[score_idx + 1])
                    except (ValueError, IndexError):
                        pass
                    
                    # 保存到字典（会覆盖同一位置的旧数据，保留最新的）
                    moves_dict[pos_key] = {
                        'row': row,
                        'col': col,
                        'winrate': winrate,
                        'visits': visits,
                        'scoreMean': score_mean,
                        'prior': 0.0,
                        'scoreLead': 0.0,
                        'utility': 0.0
                    }
                
                except (ValueError, IndexError) as e:
                    continue
            
            print(f"[KataGo] 解析出 {len(moves_dict)} 个不同位置")
            for pos, data in list(moves_dict.items())[:3]:
                print(f"[KataGo] 位置 {pos}: {data}")
            
            # 按访问次数排序（访问次数越多，说明KataGo认为该位置越重要）
            recommended_moves = sorted(
                moves_dict.values(),
                key=lambda x: x['visits'],
                reverse=True
            )
            
            # 返回前max_moves个推荐点
            return recommended_moves[:max_moves]
        
        except Exception as e:
            print(f"[KataGo] 获取推荐落子点失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_current_color(self) -> Optional[str]:
        """获取当前应该下棋的颜色"""
        try:
            # 尝试从棋盘状态推断
            board_state = self.get_board_state()
            if board_state:
                black_count = sum(1 for row in board_state for cell in row if cell == 1)
                white_count = sum(1 for row in board_state for cell in row if cell == 2)
                # 如果黑子数量 <= 白子数量，轮到黑方
                return "B" if black_count <= white_count else "W"
        except:
            pass
        return None
    
    def quit(self):
        """关闭连接"""
        try:
            if self.process:
                self.send_command('quit')
                self.process.terminate()
                self.process.wait(timeout=5)
        except:
            pass
        finally:
            self.is_connected = False
    
    def __del__(self):
        """析构函数"""
        self.quit()
