#!/usr/bin/env python3
"""
围棋助手客户端
功能：截图、GBR识别、与服务端通信获取AI分析
"""

import tkinter as tk
from tkinter import messagebox
import threading
import time
import json
import os
import sys
import re
import math
import random
import platform
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from pathlib import Path
import requests

# 设置日志文件
LOG_FILE = "/Users/qiao/Desktop/qiao/program/GoMaster/client/debug.log"

def log_debug(message):
    """写入调试日志"""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
            f.flush()
    except Exception as e:
        print(f"日志写入失败: {e}")

def log_clear():
    """清空日志文件"""
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("")
    except:
        pass

# 清空旧日志
log_clear()
log_debug("=== GoMaster 客户端启动 ===")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageGrab, ImageTk, ImageDraw
import numpy as np
import cv2

from gbr_recognizer import GBRRecognizer
from go_coordinates import array_to_gtp, gtp_to_array
from go_board import GoBoard, Color, find_ko_threats, find_ko_resolution_moves
from i18n import t, set_language, get_language, get_available_languages

# 尝试导入 RapidOCR (v3.6.0+ 使用 rapidocr 包)
try:
    from rapidocr import RapidOCR
    RAPIDOCR_AVAILABLE = True
except ImportError:
    # 回退到旧版本导入
    try:
        from rapidocr_onnxruntime import RapidOCR
        RAPIDOCR_AVAILABLE = True
    except ImportError:
        RAPIDOCR_AVAILABLE = False
        print("[警告] RapidOCR未安装，无法使用文字识别功能。请运行: pip install rapidocr")


def normalize_board_background(img: np.ndarray, target_color: Tuple[int, int, int] = (220, 179, 92)) -> np.ndarray:
    """将棋盘底色统一为土黄色"""
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    
    lower_wood = np.array([15, 50, 100])
    upper_wood = np.array([35, 200, 255])
    mask_wood = cv2.inRange(hsv, lower_wood, upper_wood)
    
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, 255, 50])
    mask_black = cv2.inRange(hsv, lower_black, upper_black)
    
    lower_white = np.array([0, 0, 200])
    upper_white = np.array([180, 30, 255])
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    
    mask_exclude = cv2.bitwise_or(mask_black, mask_white)
    mask_final = cv2.bitwise_and(mask_wood, cv2.bitwise_not(mask_exclude))
    
    kernel = np.ones((3, 3), np.uint8)
    mask_final = cv2.morphologyEx(mask_final, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask_final = cv2.morphologyEx(mask_final, cv2.MORPH_OPEN, kernel, iterations=1)
    
    target_bgr = np.array([target_color[2], target_color[1], target_color[0]], dtype=np.uint8)
    target_img = np.full_like(img_bgr, target_bgr)
    result_bgr = np.where(mask_final[..., None] > 0, target_img, img_bgr)
    
    result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
    return result_rgb


class GoClient:
    """围棋助手客户端 - 商业版"""
    
    DEPTH_PRESETS = [
        {'time': 0.7, 'label': '0.7'},
        {'time': 1.9, 'label': '1.9'},
        {'time': 3.7, 'label': '3.7'},
        {'time': 5.7, 'label': '5.7'},
        {'time': 7.7, 'label': '7.7'},
        {'time': 11.0, 'label': '11'}
    ]
    
    # 商业版配色方案
    COLORS = {
        'primary': '#2196F3',      # 主色调 - 蓝色
        'primary_dark': '#1976D2',  # 深蓝色
        'primary_light': '#BBDEFB', # 浅蓝色
        'accent': '#FF4081',        # 强调色 - 粉红
        'success': '#4CAF50',       # 成功绿
        'warning': '#FFC107',       # 警告黄
        'error': '#F44336',         # 错误红
        'background': '#FAFAFA',    # 背景色
        'card': '#FFFFFF',          # 卡片色
        'text_primary': '#212121',  # 主文本
        'text_secondary': '#757575', # 次要文本
        'divider': '#E0E0E0',       # 分割线
        'border': '#E8E8E8',        # 边框色 - 更浅的灰色
    }
    
    # 字体配置 - 使用系统默认清晰字体
    # 使用系统默认字体，Tkinter 会自动选择最佳可用字体
    FONTS = {
        'title': ('Helvetica Neue', 14, 'bold'),
        'heading': ('Helvetica Neue', 13, 'bold'),
        'body': ('Helvetica Neue', 12),
        'body_bold': ('Helvetica Neue', 12, 'bold'),
        'small': ('Helvetica Neue', 11),
        'large': ('Helvetica Neue', 16, 'bold'),
    }
    
    def __init__(self):
        # 打印彩色 Logo
        self._print_logo()
        
        self.root = tk.Tk()
        
        self.root.title("GoMaster")
        self.root.geometry("300x293")
        self.root.resizable(False, False)
        self.root.configure(bg=self.COLORS['background'])
        
        # macOS 特定的窗口属性设置
        self._setup_macos_window()
        
        # 修复窗口焦点切换后点击不灵敏的问题
        self.root.bind('<FocusIn>', self._on_focus_in)
        # 只在窗口背景上绑定点击事件，不拦截控件点击
        self.root.bind('<Button-1>', self._on_click)
        
        self._set_window_position()
        
        self.config = {
            'server_url': 'http://localhost:8001',
            'max_time': 5.0,  # 增加思考时间以提高胜率
            'max_visits': 5000,  # 增加访问次数以提高胜率
            'board_region': None,
            'monitor_region': None,
            'gbr_params_file': None,
            'platform': 'tencent',  # 默认平台
            'model_name': None  # 默认使用服务端默认模型
        }
        self.available_models = []  # 可用模型列表
        self.current_model = None  # 当前使用的模型
        
        self.board_region = None
        self.monitor_region = None
        
        self.gbr_recognizer = None
        self.target_window = None
        self.window_bounds = None
        
        self.auto_polling_enabled = tk.BooleanVar(value=False)
        self.selected_color = tk.StringVar(value="B")
        self.show_visualization = tk.BooleanVar(value=False)
        self.human_like_thinking = tk.BooleanVar(value=False)  # 模拟人类思考开关

        self.is_processing = False
        self.monitor_timer_id = None
        self.monitor_interval = 1.0
        self.last_recommended_move = None
        self.last_last_recommended_move = None  # 上上次推荐位置（用于检测连续相同推荐）
        self.last_recommended_moves = None
        self.last_recommended_move_count = 0
        self.excluded_recommended_moves = []  # 多个推荐落子
        self.last_board_info = None  # 保存 board_edges 和 board_spacing（仅用于当前次点击）
        self.last_stones = None  # 上一次识别的棋盘
        self._rapidocr = None
        # 轮巡控制
        self.last_analysis_time = 0  # 上次分析完成时间
        self.just_clicked = False  # 刚完成自动落子，需要等待
        # 打劫检测
        self.move_history = []  # 保存历史落子用于检测打劫
        self.ko_detected = False  # 是否检测到打劫
        self.ko_excluded_last_turn = False  # 上一轮是否排除了打劫位置
        self.last_ko_move = None  # 上一次打劫位置
        self.last_ko_candidate_moves = None  # 保存打劫时的劫材列表用于可视化
        # 规则引擎（用于准确检测打劫和查找劫材）
        self.board_engine = GoBoard(size=19)  # 添加规则引擎

        self.config_file = Path(__file__).parent / 'client_config.json'

        self._load_config()
        self._init_gbr()
        self._init_ocr()
        self._create_widgets()
        self._check_server()
        self._start_connection_monitor()  # 启动连接状态自动更新
        
    def _on_focus_in(self, event):
        """窗口获得焦点时强制刷新"""
        self.root.lift()
        self.root.focus_force()
        self.root.update()

    def _print_logo(self):
        """打印彩色 GoMaster Logo"""
        # ANSI 颜色代码
        RESET = '\033[0m'
        BOLD = '\033[1m'
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        MAGENTA = '\033[95m'
        BLUE = '\033[94m'
        WHITE = '\033[97m'
        RED = '\033[91m'
        
        logo = f"""
{CYAN}╔══════════════════════════════════════════════════════════════════╗{RESET}
{CYAN}║{RESET}                                                                  {CYAN}║{RESET}
{CYAN}║{RESET}   {BOLD}{GREEN}╔══════╗{RESET} {BOLD}{YELLOW}╔══════╗{RESET} {BOLD}{MAGENTA}╔══════╗{RESET} {BOLD}{BLUE}╔══════╗{RESET} {BOLD}{GREEN}╔══════╗{RESET} {BOLD}{YELLOW}╔══════╗{RESET} {BOLD}{RED}╔══════╗{RESET}   {CYAN}║{RESET}
{CYAN}║{RESET}   {BOLD}{GREEN}║  G   ║{RESET} {BOLD}{YELLOW}║  O   ║{RESET} {BOLD}{MAGENTA}║  M   ║{RESET} {BOLD}{BLUE}║  A   ║{RESET} {BOLD}{GREEN}║  S   ║{RESET} {BOLD}{YELLOW}║  T   ║{RESET} {BOLD}{RED}║  E   ║{RESET}   {CYAN}║{RESET}
{CYAN}║{RESET}   {BOLD}{GREEN}║      ║{RESET} {BOLD}{YELLOW}║      ║{RESET} {BOLD}{MAGENTA}║      ║{RESET} {BOLD}{BLUE}║      ║{RESET} {BOLD}{GREEN}║      ║{RESET} {BOLD}{YELLOW}║      ║{RESET} {BOLD}{RED}║      ║{RESET}   {CYAN}║{RESET}
{CYAN}║{RESET}   {BOLD}{GREEN}╚══════╝{RESET} {BOLD}{YELLOW}╚══════╝{RESET} {BOLD}{MAGENTA}╚══════╝{RESET} {BOLD}{BLUE}╚══════╝{RESET} {BOLD}{GREEN}╚══════╝{RESET} {BOLD}{YELLOW}╚══════╝{RESET} {BOLD}{RED}╚══════╝{RESET}   {CYAN}║{RESET}
{CYAN}║{RESET}                                                                  {CYAN}║{RESET}
{CYAN}║{RESET}             {BOLD}{WHITE}围棋 AI 助手{RESET}  •  {GREEN}Powered by KataGo{RESET}  •  v1.0         {CYAN}║{RESET}
{CYAN}╚══════════════════════════════════════════════════════════════════╝{RESET}
"""
        print(logo)
    
    def _disable_main_window(self):
        """禁用主窗口所有控件（macOS 模态对话框替代方案）"""
        for widget in self.root.winfo_children():
            try:
                widget.configure(state='disabled')
            except:
                pass
    
    def _enable_main_window(self):
        """启用主窗口所有控件"""
        for widget in self.root.winfo_children():
            try:
                widget.configure(state='normal')
            except:
                pass
    
    def _on_config_close(self, dialog):
        """配置窗口关闭时的处理"""
        self._enable_main_window()
        dialog.destroy()
    
    def _setup_macos_window(self):
        """设置窗口属性 - 根据平台优化"""
        self.is_windows = platform.system() == 'Windows'
        self.is_macos = platform.system() == 'Darwin'
        
        try:
            # 使用 wm_attributes 替代 attributes
            self.root.wm_attributes('-topmost', True)
        except Exception as e:
            print(f"[窗口] 窗口设置失败: {e}")
        # 回退到标准设置
        try:
            self.root.attributes('-topmost', True)
        except:
            pass
    
    def _on_click(self, event):
        """窗口点击时激活窗口"""
        self._activate_window()
    
    def _activate_window(self):
        """激活窗口 - 简单方案"""
        try:
            self.root.lift()
            self.root.focus_force()
        except:
            pass
        
    def _set_window_position(self):
        """设置窗口位置到右上角"""
        try:
            self.root.update_idletasks()
            width = 300
            height = 293
            screen_width = self.root.winfo_screenwidth()
            x = screen_width - width - 20
            y = 20
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        except:
            pass
            
    def _load_config(self):
        """加载配置"""
        try:
            if self.config_file.exists():
                with open(self.config_file) as f:
                    saved = json.load(f)
                    self.config.update(saved)
                    if saved.get('board_region'):
                        self.board_region = tuple(saved['board_region'])
                    if saved.get('monitor_region'):
                        self.monitor_region = tuple(saved['monitor_region'])
        except:
            pass

    def _save_config(self):
        """保存配置"""
        try:
            data = self.config.copy()
            data['board_region'] = list(self.board_region) if self.board_region else None
            data['monitor_region'] = list(self.monitor_region) if self.monitor_region else None
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except:
            pass
    
    def _update_ui_language(self):
        """更新界面语言 - 切换语言后调用"""
        # 窗口标题保持GoMaster不变

        # 更新下一步按钮
        self.next_button.config(text=t('next_step'))

        # 更新Canvas复选框文本
        if hasattr(self, 'auto_polling_canvas'):
            self.auto_polling_canvas.itemconfig('text_label', text=t('polling'))
        if hasattr(self, 'board_canvas'):
            self.board_canvas.itemconfig('text_label', text=t('board'))

        # 更新颜色显示
        self._update_stone_toggle_display()

        # 更新时间标签
        for widget in self.root.winfo_children():
            self._update_widget_language(widget)
    
    def _update_widget_language(self, widget):
        """递归更新所有控件的语言"""
        try:
            # 更新标签文本
            if isinstance(widget, tk.Label):
                current_text = widget.cget('text')
                # 根据当前文本内容判断应该使用哪个翻译键
                if '思考时间' in current_text or 'Think Time' in current_text:
                    widget.config(text=t('time'))
                elif '分析结果' in current_text or 'Analysis Result' in current_text:
                    widget.config(text=t('analysis_result'))
            
            # 更新按钮文本
            elif isinstance(widget, tk.Button):
                current_text = widget.cget('text')
                if '配置' in current_text or 'Config' in current_text:
                    widget.config(text=t('config'))
            
            # 更新复选框文本
            elif isinstance(widget, tk.Checkbutton):
                current_text = widget.cget('text')
                if '棋盘' in current_text or 'Board' in current_text:
                    widget.config(text=t('board'))
        except:
            pass
        
        # 递归处理子控件
        try:
            for child in widget.winfo_children():
                self._update_widget_language(child)
        except:
            pass
            
    def _init_gbr(self):
        """初始化GBR识别器"""
        try:
            self.gbr_recognizer = GBRRecognizer(board_size=19)
        except Exception as e:
            print(f"GBR初始化失败: {e}")

    def _init_ocr(self):
        """初始化OCR识别器"""
        if RAPIDOCR_AVAILABLE:
            try:
                self._rapidocr = RapidOCR()
                print("[OCR] RapidOCR 初始化成功")
            except Exception as e:
                print(f"[OCR] RapidOCR 初始化失败: {e}")
                self._rapidocr = None

    def _recognize_monitor_text(self) -> Optional[str]:
        """识别监控区域文字"""
        if not self.monitor_region or not self._rapidocr:
            log_debug("[监控识别] 未配置监控区域或OCR未初始化")
            return None

        try:
            x, y, w, h = self.monitor_region
            if w <= 0 or h <= 0:
                log_debug(f"[监控识别] 监控区域尺寸无效: {self.monitor_region}")
                return None

            # 截取监控区域
            log_debug(f"[监控识别] 截取区域: x={x}, y={y}, w={w}, h={h}")
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            
            # 保存截图用于调试
            debug_path = "/Users/qiao/Desktop/qiao/program/GoMaster/client/screenshots/monitor_debug.png"
            img.save(debug_path)
            log_debug(f"[监控识别] 截图已保存到: {debug_path}")
            
            img_array = np.array(img)

            # 使用 RapidOCR 识别 (适配 v3.6.0+ 和旧版本)
            result = self._rapidocr(img_array)
            log_debug(f"[监控识别] OCR原始结果: {result}")

            # 提取所有识别到的文字
            texts = []
            if result:
                # RapidOCR v3.6.0+ 返回 RapidOCROutput 对象
                if hasattr(result, 'txts') and result.txts:
                    texts = [t for t in result.txts if t]
                # 检查 word_results 字段 (有些版本使用这个字段)
                elif hasattr(result, 'word_results') and result.word_results:
                    for item in result.word_results:
                        if isinstance(item, (list, tuple)) and len(item) >= 1:
                            text = item[0]  # word_results 格式: (text, score, box)
                            if text and text.strip():
                                texts.append(text)
                # 旧版本返回元组 (result_list, elapse)
                elif isinstance(result, (list, tuple)) and len(result) >= 1:
                    result_list = result[0]
                    if result_list:
                        for item in result_list:
                            if len(item) >= 2:
                                text = item[1]
                                if text:
                                    texts.append(text)

            log_debug(f"[监控识别] 提取到的文字: {texts}")

            if texts:
                recognized_text = ' '.join(texts)
                # 去除空格和换行
                recognized_text = recognized_text.replace(' ', '').replace('\n', '').strip()
                log_debug(f"[监控识别] 最终识别结果: '{recognized_text}'")
                return recognized_text if recognized_text else None

            log_debug("[监控识别] 未识别到任何文字")
            return None
        except Exception as e:
            log_debug(f"[监控识别] 识别失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _is_my_turn(self, recognized_text: Optional[str]) -> bool:
        """检查是否轮到自己下棋"""
        if not recognized_text:
            return True  # 未识别到文字，默认允许

        selected_color = self.selected_color.get()  # "B" 或 "W"
        platform = self.config.get('platform', 'unknown')
        
        log_debug(f"[轮次判断] 平台: {platform}, 选择颜色: {selected_color}, 识别文字: '{recognized_text}'")
        
        # OGS 平台：只通过"您"字判断
        # OGS 界面会在轮到用户下棋时显示"您"
        if platform == 'ogs':
            if '您' in recognized_text:
                log_debug("[轮次判断] OGS平台: 识别到'您', 轮到我方")
                return True
            else:
                log_debug("[轮次判断] OGS平台: 未识别到'您', 轮到对方")
                return False
        
        # 弈城/野狐平台：直接识别数字（手数）进行奇偶性判断
        # 这些平台的监控区域只显示纯数字手数
        if platform in ['yicheng', 'fox']:
            numbers = re.findall(r'\d+', recognized_text)
            log_debug(f"[轮次判断] 弈城/野狐平台: 提取到的数字: {numbers}")
            if numbers:
                try:
                    number = int(numbers[0])
                    is_odd = (number % 2 == 1) and number != 0  # 0 作为偶数处理
                    log_debug(f"[轮次判断] 手数: {number}, 奇数: {is_odd}")

                    # 奇数+白棋 或 偶数（包括0）+黑棋 = 轮到自己
                    if is_odd and selected_color == "W":
                        log_debug("[轮次判断] 奇数+白棋 = 轮到我方")
                        return True
                    elif not is_odd and selected_color == "B":
                        log_debug("[轮次判断] 偶数+黑棋 = 轮到我方")
                        return True
                    else:
                        log_debug("[轮次判断] 不匹配 = 轮到对方")
                        return False
                except ValueError as e:
                    log_debug(f"[轮次判断] 数字转换失败: {e}")
                    pass
            else:
                log_debug("[轮次判断] 未识别到数字，默认允许")
        
        # 其他平台：通过手数奇偶性判断（需要包含"Move"或"手"字样）
        if 'Move' in recognized_text or '手' in recognized_text:
            numbers = re.findall(r'\d+', recognized_text)
            if numbers:
                try:
                    number = int(numbers[0])
                    is_odd = (number % 2 == 1) and number != 0  # 0 作为偶数处理

                    # 奇数+白棋 或 偶数（包括0）+黑棋 = 轮到自己
                    if is_odd and selected_color == "W":
                        return True
                    elif not is_odd and selected_color == "B":
                        return True
                    else:
                        return False
                except ValueError:
                    pass

        # 默认允许（未识别到明确信息时）
        log_debug("[轮次判断] 默认允许")
        return True

    def _recognize_monitor_text_cached(self) -> Optional[str]:
        """识别监控区域文字 - 每次都用新截图，绝不使用缓存"""
        return self._recognize_monitor_text()

    def _calculate_board_complexity(self, stones: Dict) -> float:
        """
        计算棋面复杂度，返回0-1之间的值
        复杂度基于：棋子数量、棋子分布密度、接触战数量
        """
        black_stones = stones.get('black', [])
        white_stones = stones.get('white', [])
        total_stones = len(black_stones) + len(white_stones)
        
        if total_stones == 0:
            return 0.0
        
        # 1. 基于棋子数量的复杂度（越多越复杂，非线性增长）
        # 使用对数函数，前50手增长快，之后增长慢
        stone_complexity = min(1.0, math.log(total_stones + 1) / math.log(100))
        
        # 2. 计算棋子分布密度（标准差越小，密度越高越复杂）
        all_stones = black_stones + white_stones
        if len(all_stones) >= 4:
            rows = [s[0] for s in all_stones]
            cols = [s[1] for s in all_stones]
            row_std = np.std(rows) if len(rows) > 1 else 0
            col_std = np.std(cols) if len(cols) > 1 else 0
            # 标准差越小（集中在某个区域），复杂度越高
            avg_std = (row_std + col_std) / 2
            density_complexity = max(0, 1.0 - avg_std / 9.0)  # 9是棋盘半宽
        else:
            density_complexity = 0.0
        
        # 3. 计算接触战数量（相邻的黑白棋子对）
        contact_count = 0
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        for br, bc in black_stones:
            for wr, wc in white_stones:
                # 检查是否相邻（包括对角）
                if abs(br - wr) <= 1 and abs(bc - wc) <= 1 and (br != wr or bc != wc):
                    contact_count += 1
        # 接触战越多越复杂，但超过20对后增长放缓
        contact_complexity = min(1.0, contact_count / 20.0)
        
        # 综合复杂度：棋子数量占40%，密度占30%，接触战占30%
        total_complexity = (stone_complexity * 0.4 + 
                           density_complexity * 0.3 + 
                           contact_complexity * 0.3)
        
        return min(1.0, max(0.0, total_complexity))

    def _create_widgets(self):
        """创建界面 - 商业版设计"""
        # 主容器
        main_frame = tk.Frame(self.root, bg=self.COLORS['background'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
        
        # ===== 顶部品牌区域 =====
        brand_frame = tk.Frame(main_frame, bg=self.COLORS['background'])
        brand_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Logo和标题
        logo_frame = tk.Frame(brand_frame, bg=self.COLORS['background'])
        logo_frame.pack(side=tk.LEFT)

        # 绘制上黑下白的围棋图标（带状态指示器）
        self.logo_canvas = tk.Canvas(
            logo_frame,
            width=32,
            height=32,
            bg=self.COLORS['background'],
            highlightthickness=0
        )
        self.logo_canvas.pack(side=tk.LEFT)
        # 上半部分黑色
        self.logo_canvas.create_arc(2, 2, 26, 26, start=0, extent=180, fill='black', outline='black')
        # 下半部分白色
        self.logo_canvas.create_arc(2, 2, 26, 26, start=180, extent=180, fill='white', outline='#333333')
        # 状态指示器小圆点（右下角）
        self.status_circle = self.logo_canvas.create_oval(20, 20, 28, 28, fill='#FFC107', outline='white', width=2)
        
        title_label = tk.Label(
            logo_frame,
            text="GoMaster",
            bg=self.COLORS['background'],
            fg=self.COLORS['text_primary'],
            font=self.FONTS['title']
        )
        title_label.pack(side=tk.LEFT, padx=(5, 0))
        

        
        # 右侧状态和控制按钮 - 统一使用Canvas绘制，更整齐
        right_frame = tk.Frame(brand_frame, bg=self.COLORS['background'])
        right_frame.pack(side=tk.RIGHT)

        # 帮助按钮 - 纯图标无背景
        help_canvas = tk.Canvas(
            right_frame,
            width=20,
            height=20,
            bg=self.COLORS['background'],
            highlightthickness=0,
            cursor="hand2"
        )
        help_canvas.pack(side=tk.LEFT, padx=(0, 12))
        # 问号文字（无圆圈背景）
        help_canvas.create_text(10, 10, text="?", fill=self.COLORS['primary'], font=self.FONTS['heading'])
        help_canvas.bind("<Button-1>", lambda e: self._show_help())

        # 配置按钮 - 齿轮图标
        config_canvas = tk.Canvas(
            right_frame,
            width=22,
            height=22,
            bg=self.COLORS['background'],
            highlightthickness=0,
            cursor="hand2"
        )
        config_canvas.pack(side=tk.LEFT, padx=(0, 10))
        # 绘制齿轮图标
        cx, cy = 11, 11  # 中心点
        outer_r, inner_r = 8, 5  # 外圈和内圈半径
        num_teeth = 8  # 齿数
        # 绘制齿轮齿
        for i in range(num_teeth):
            angle = i * 45  # 360/8 = 45度
            rad = math.radians(angle)
            rad2 = math.radians(angle + 22.5)
            x1 = cx + inner_r * math.cos(rad)
            y1 = cy + inner_r * math.sin(rad)
            x2 = cx + outer_r * math.cos(rad2)
            y2 = cy + outer_r * math.sin(rad2)
            x3 = cx + inner_r * math.cos(math.radians(angle + 45))
            y3 = cy + inner_r * math.sin(math.radians(angle + 45))
            config_canvas.create_polygon(x1, y1, x2, y2, x3, y3, fill=self.COLORS['primary'], outline='')
        # 绘制中心圆
        config_canvas.create_oval(cx-3, cy-3, cx+3, cy+3, fill=self.COLORS['background'], outline=self.COLORS['primary'], width=1)
        config_canvas.bind("<Button-1>", lambda e: self._open_config())
        
        # ===== 主要操作区域（简洁样式，无边框） =====
        action_frame = tk.Frame(main_frame, bg=self.COLORS['background'], padx=15, pady=8)
        action_frame.pack(fill=tk.X, pady=(0, 5))

        # 主操作按钮 - 使用Canvas绘制，文字亮绿色，字号更大
        self.next_button = self._create_custom_button(
            action_frame,
            text=t('next_step'),
            command=self._on_next_step,
            font=self.FONTS['heading'],
            bg=self.COLORS['primary'],
            fg='#90EE90',  # 亮绿色
            active_bg=self.COLORS['primary_dark'],
            height=48
        )
        self.next_button.pack(fill=tk.X)
        
        # ===== 设置区域（卡片样式） =====
        settings_card = tk.Frame(main_frame, bg=self.COLORS['card'], padx=15, pady=6)
        settings_card.pack(fill=tk.X, pady=(0, 5))
        settings_card.configure(highlightbackground=self.COLORS['divider'], highlightthickness=1)
        
        # 第一行：自动下棋、棋盘和颜色选择（使用Canvas绘制更精美）
        row1_frame = tk.Frame(settings_card, bg=self.COLORS['card'])
        row1_frame.pack(fill=tk.X, pady=(0, 5))

        # 自动下棋开关 - 使用Canvas绘制
        self._create_canvas_checkbox(row1_frame, 'polling', self.auto_polling_enabled, self._on_polling_changed)

        # 棋盘开关 - 使用Canvas绘制（更大间距）
        self._create_canvas_checkbox(row1_frame, 'board', self.show_visualization, self._on_viz_changed, padx=(16, 0))

        # 颜色选择 - 使用Canvas绘制（更大间距）
        self._create_canvas_color_toggle(row1_frame, padx=(16, 0))

        # 第二行：时间设置和监控显示
        row2_frame = tk.Frame(settings_card, bg=self.COLORS['card'])
        row2_frame.pack(fill=tk.X)

        # 时钟图标 + AI思考时间标签
        time_label_frame = tk.Frame(row2_frame, bg=self.COLORS['card'])
        time_label_frame.pack(side=tk.LEFT, padx=(0, 5))

        tk.Label(time_label_frame, text="⏲", bg=self.COLORS['card'],
                fg=self.COLORS['text_secondary'], font=('Helvetica Neue', 28)).pack(side=tk.LEFT)

        tk.Label(time_label_frame, text=t('time'), bg=self.COLORS['card'],
                fg=self.COLORS['text_secondary'], font=self.FONTS['body_bold']).pack(side=tk.LEFT)

        # 自定义时间滑动条（带Canvas绘制的时间值显示）
        self._create_time_slider(row2_frame)

        # ===== 结果显示区域（卡片样式） =====
        result_card = tk.Frame(main_frame, bg=self.COLORS['card'], padx=10, pady=4)
        result_card.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        result_card.configure(highlightbackground=self.COLORS['border'], highlightthickness=1)

        # 结果标题行（包含分析结果标签和轮到显示）
        result_header_frame = tk.Frame(result_card, bg=self.COLORS['card'])
        result_header_frame.pack(fill=tk.X, pady=(0, 3))

        # 结果标题
        result_header = tk.Label(
            result_header_frame,
            text=t('recommended_moves'),
            bg=self.COLORS['card'],
            fg=self.COLORS['text_secondary'],
            font=self.FONTS['small']
        )
        result_header.pack(side=tk.LEFT)

        # 轮到显示
        self.turn_label = tk.Label(
            result_header_frame,
            text="",
            bg=self.COLORS['card'],
            fg=self.COLORS['primary'],
            font=self.FONTS['small']
        )
        self.turn_label.pack(side=tk.LEFT, padx=(5, 0))

        # 监控区域识别文字显示（挨着轮到次序后面）
        self.monitor_text_label = tk.Label(
            result_header_frame,
            text="",
            bg=self.COLORS['card'],
            fg=self.COLORS['text_secondary'],
            font=self.FONTS['small']
        )
        self.monitor_text_label.pack(side=tk.LEFT, padx=(10, 0))

        # 使用 Canvas 替代 Text 实现更美观的显示效果
        self.result_canvas = tk.Canvas(
            result_card,
            bg=self.COLORS['card'],
            highlightbackground='#CCCCCC',
            highlightthickness=2,
            height=60
        )
        self.result_canvas.pack(fill=tk.BOTH, expand=True)
        # 存储当前显示的内容
        self.result_canvas_items = []
        
        # 只在轮巡启用时启动监控
        if self.auto_polling_enabled.get():
            self._start_monitor()
        
    def _update_depth_buttons(self):
        """更新深度按钮状态"""
        current_time = self.config.get('max_time', 1.9)
        for i, btn in enumerate(self.depth_buttons):
            preset = self.DEPTH_PRESETS[i]
            if abs(preset['time'] - current_time) < 0.1:
                btn.config(bg="white", fg="#4CAF50")
            else:
                btn.config(bg="white", fg="#333333")
                
    def _on_polling_changed(self):
        """轮巡开关变化"""
        if self.auto_polling_enabled.get():
            self._start_monitor()
        else:
            self._stop_monitor()

    def _on_viz_changed(self):
        """可视化开关变化"""
        if self.show_visualization.get():
            if self.last_stones:
                # 使用保存的劫材信息（如果有）
                ko_move = self.last_ko_move if self.ko_detected and self.last_ko_move else None
                candidate_moves = self.last_ko_candidate_moves if self.ko_detected else None
                self._show_board_visualization(self.last_stones, ko_move=ko_move, candidate_moves=candidate_moves)
        else:
            # 关闭棋盘窗口
            if hasattr(self, 'board_window') and self.board_window.winfo_exists():
                self.board_window.destroy()

    def _clear_result_canvas(self):
        """清空结果显示区域"""
        self.result_canvas.delete('all')
        self.result_canvas_items = []

    def _update_result_canvas_simple(self):
        """简化显示结果"""
        self._clear_result_canvas()
        canvas_width = self.result_canvas.winfo_width()
        canvas_height = self.result_canvas.winfo_height()
        if canvas_width < 10:
            canvas_width = 400
        if canvas_height < 10:
            canvas_height = 60
        self.result_canvas.create_text(
            canvas_width // 2, canvas_height // 2,
            text=t('waiting_analysis'),
            font=self.FONTS['body'],
            fill=self.COLORS['text_secondary'],
            anchor='c'
        )

    def _start_monitor(self):
        """启动监控"""
        self._stop_monitor()
        self._monitor_loop()
        
    def _stop_monitor(self):
        """停止监控"""
        if self.monitor_timer_id:
            self.root.after_cancel(self.monitor_timer_id)
            self.monitor_timer_id = None
            
    def _monitor_loop(self):
        """监控循环 - 每秒检查"""
        if self.auto_polling_enabled.get():
            # 如果刚完成自动落子，重置标记并立即分析（无等待）
            if self.just_clicked:
                self.just_clicked = False
            # 只有当前没有在处理时才进行分析
            if not self.is_processing:
                self._check_and_analyze()
            else:
                print("[监控] 跳过分析：上一个请求仍在处理中")

        # 每秒更新监控区域显示（无论是否分析）
        self._update_monitor_display()

        # 只在轮巡启用时继续循环
        if self.auto_polling_enabled.get():
            # 轮巡间隔1秒
            self.monitor_timer_id = self.root.after(1000, self._monitor_loop)
    
    def _update_monitor_display(self):
        """更新监控区域显示"""
        try:
            monitor_text = self._recognize_monitor_text_cached()
            if monitor_text:
                # 确保标签已显示
                self.root.after(0, lambda: self._show_monitor_text(f"{t('monitor_text_prefix')} {monitor_text}"))
            else:
                self.root.after(0, self._hide_monitor_text)
        except Exception as e:
            print(f"[监控] 更新显示失败: {e}")
    
    def _show_monitor_text(self, text):
        """显示监控文本"""
        self.monitor_text_label.config(text=text)
    
    def _hide_monitor_text(self):
        """隐藏监控文本"""
        self.monitor_text_label.config(text="")
        
    def _check_and_analyze(self):
        """检查并分析"""
        if not self.board_region:
            return
        threading.Thread(target=self._analyze, daemon=True).start()
        
    def _create_custom_button(self, parent, text, command, font, bg, fg, active_bg, height=40):
        """创建自定义 Canvas 按钮，简洁无边框"""
        # 创建容器 Frame（无highlight边框）
        btn_frame = tk.Frame(parent, bg=parent.cget('bg'), cursor="hand2",
                             highlightthickness=0, bd=0)

        # 创建 Canvas（无highlight边框）
        canvas = tk.Canvas(btn_frame, bg=bg, highlightthickness=0, height=height, bd=0)
        canvas.pack(fill=tk.X, expand=True)

        # 按钮状态
        btn_state = {'normal': bg, 'active': active_bg, 'disabled': '#BDBDBD'}
        is_disabled = [False]
        button_text = [text]  # 使用列表存储可变文本

        def draw_button(state='normal'):
            canvas.delete('all')
            width = canvas.winfo_width()
            if width < 10:
                width = 200

            # 绘制圆角矩形背景
            radius = 6
            color = btn_state.get(state, bg)
            canvas.create_rectangle(
                radius, 0, width - radius, height,
                fill=color, outline=color
            )
            canvas.create_rectangle(
                0, radius, width, height - radius,
                fill=color, outline=color
            )
            canvas.create_oval(
                0, 0, radius * 2, radius * 2,
                fill=color, outline=color
            )
            canvas.create_oval(
                width - radius * 2, 0, width, radius * 2,
                fill=color, outline=color
            )
            canvas.create_oval(
                0, height - radius * 2, radius * 2, height,
                fill=color, outline=color
            )
            canvas.create_oval(
                width - radius * 2, height - radius * 2, width, height,
                fill=color, outline=color
            )

            # 绘制文字
            text_color = fg if state != 'disabled' else '#757575'
            canvas.create_text(
                width // 2, height // 2,
                text=button_text[0],
                font=font,
                fill=text_color
            )

        # 初始绘制
        btn_frame.after(10, lambda: draw_button('normal'))

        # 绑定事件
        def on_enter(e):
            if not is_disabled[0]:
                draw_button('active')

        def on_leave(e):
            if not is_disabled[0]:
                draw_button('normal')

        def on_click(e):
            if not is_disabled[0]:
                draw_button('active')
                if command:
                    command()

        def on_release(e):
            if not is_disabled[0]:
                draw_button('normal')

        canvas.bind('<Enter>', on_enter)
        canvas.bind('<Leave>', on_leave)
        canvas.bind('<Button-1>', on_click)
        canvas.bind('<ButtonRelease-1>', on_release)
        btn_frame.bind('<Enter>', on_enter)
        btn_frame.bind('<Leave>', on_leave)
        btn_frame.bind('<Button-1>', on_click)
        btn_frame.bind('<ButtonRelease-1>', on_release)

        # 配置方法
        def config(text=None, state=None, fg=None):
            if text is not None:
                button_text[0] = text
                draw_button('normal' if not is_disabled[0] else 'disabled')
            if state is not None:
                is_disabled[0] = (state == tk.DISABLED)
                draw_button('disabled' if is_disabled[0] else 'normal')

        btn_frame.config = config

        # 窗口大小改变时重绘
        def on_resize(e):
            draw_button('normal' if not is_disabled[0] else 'disabled')

        canvas.bind('<Configure>', on_resize)

        return btn_frame

    def _on_next_step(self):
        """下一步按钮"""
        if self.is_processing:
            return
        # 手动点击时也要检查是否轮到自己
        threading.Thread(target=self._analyze, daemon=True).start()

    def _capture_board(self) -> Optional[np.ndarray]:
        """截取棋盘"""
        try:
            if self.board_region:
                x, y, w, h = self.board_region
                img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
                return np.array(img)
            else:
                img = ImageGrab.grab()
                return np.array(img)
        except Exception as e:
            print(f"截图失败: {e}")
            return None
            
    def _recognize_board(self, img: np.ndarray) -> Optional[Dict]:
        """识别棋盘"""
        if not self.gbr_recognizer:
            return None
        try:
            normalized = normalize_board_background(img)
            result = self.gbr_recognizer.recognize_from_array(
                normalized,
                params_file=self.config.get('gbr_params_file')
            )
            return result
        except Exception as e:
            print(f"识别失败: {e}")
            return None
            
    def _analyze(self, force: bool = False):
        """分析棋盘 - 每次都用新截图

        Args:
            force: 是否强制分析（忽略是否轮到自己的检查）
        """
        self.is_processing = True
        
        # 在主线程更新按钮状态（不清空结果显示，保留上次推荐）
        def update_ui_start():
            self.next_button.config(text=t('analyzing'), state=tk.DISABLED, fg='#E0E0E0')
        self.root.after(0, update_ui_start)

        try:
            # 步骤1: 识别监控区域文字
            monitor_text = self._recognize_monitor_text_cached()
            
            # 步骤2: 轮巡模式下检查是否轮到自己
            if self.auto_polling_enabled.get() and not force:
                is_my_turn = self._is_my_turn(monitor_text)
                
                if not is_my_turn:
                    # 只在状态变化时更新UI（不清空推荐结果）
                    def update_ui_wait():
                        if monitor_text:
                            self._show_monitor_text(f"[✗] {monitor_text}")
                        else:
                            self._hide_monitor_text()
                        # 更新轮到显示
                        self.turn_label.config(text=t('opponent_turn'), fg=self.COLORS['text_secondary'])
                        # 保留上次的推荐结果显示，不清空
                    self.root.after(0, update_ui_wait)
                    return
                
                # 注意：动态等待时间已移至识别棋盘后，根据棋面复杂度计算

            # 步骤3: 确认轮到自己后（延迟后），再进行截图
            img = self._capture_board()
            if img is None:
                self.root.after(0, lambda: self._update_result(t('screenshot_failed')))
                return

            # 步骤4: 识别棋盘 - 每次都用新截取的图像，绝不使用缓存
            stones = self._recognize_board(img)

            if stones is None:
                self.root.after(0, lambda: self._update_result(t('recognition_failed')))
                return

            black_stones = stones.get('black', [])
            white_stones = stones.get('white', [])

            # 检查上次推荐的位置是否无法落子（已有棋子），如果是则判定为打劫
            ko_detected_this_turn = False
            print(f"[打劫调试] last_recommended_move={self.last_recommended_move}, last_stones={self.last_stones is not None}")

            # 新增：如果连续两次推荐相同位置，判定为打劫（即使位置还没被占用）
            if self.last_recommended_move and self.last_last_recommended_move:
                if self.last_recommended_move == self.last_last_recommended_move:
                    if self.last_recommended_move not in self.excluded_recommended_moves:
                        self.excluded_recommended_moves.append(self.last_recommended_move)
                        print(f"[打劫] 连续两次推荐相同位置 {self.last_recommended_move}，判定为打劫位置")
                        ko_detected_this_turn = True

            if self.last_recommended_move:
                # 将 GTP 坐标转换为棋盘坐标
                rec_row, rec_col = self.board_engine.gtp_to_coord(self.last_recommended_move)
                # 检查该位置是否有棋子
                rec_pos = (rec_row, rec_col)
                is_occupied = rec_pos in black_stones or rec_pos in white_stones
                # 棋盘状态是否变化
                stones_changed = self.last_stones and stones != self.last_stones
                print(f"[打劫调试] stones_changed={stones_changed}, last_black={len(self.last_stones.get('black', []) if self.last_stones else [])}, curr_black={len(black_stones)}")
                # 如果位置已被占用（无法落子），判定为打劫
                if is_occupied:
                    if self.last_recommended_move not in self.excluded_recommended_moves:
                        self.excluded_recommended_moves.append(self.last_recommended_move)
                        print(f"[打劫] 推荐位置 {self.last_recommended_move} 无法落子，判定为打劫位置")
                        ko_detected_this_turn = True
                # 如果棋盘变化了，清空排除列表（打劫已解决或对方已落子）
                if stones_changed:
                    if self.excluded_recommended_moves:
                        print(f"[打劫] 棋盘变化，清空排除列表: {self.excluded_recommended_moves}")
                        self.excluded_recommended_moves = []
            
            # 调试：每帧都打印打劫检测状态
            if ko_detected_this_turn or self.excluded_recommended_moves:
                print(f"[打劫调试] excluded_recommended_moves={self.excluded_recommended_moves}, ko_detected={ko_detected_this_turn}")
            
            self.last_stones = stones
            self.last_board_info = {
                'board_edges': stones.get('board_edges'),
                'board_spacing': stones.get('board_spacing')
            }

            # 调试输出：显示识别到的棋子
            print(f"[GBR] 识别到黑子: {len(black_stones)} 个, 白子: {len(white_stones)} 个")
            if black_stones:
                print(f"[GBR] 黑子位置: {black_stones}")
            if white_stones:
                print(f"[GBR] 白子位置: {white_stones}")

            if not black_stones and not white_stones:
                self.root.after(0, lambda: self._update_result(t('no_stones_detected')))
                return

            # 获取用户选择的颜色和当前实际轮到的一方
            user_color = self.selected_color.get()  # 用户选择执子颜色
            if user_color == "B":
                current_color = "B" if len(black_stones) <= len(white_stones) else "W"
            elif user_color == "W":
                current_color = "W" if len(white_stones) <= len(black_stones) else "B"
            else:
                current_color = user_color

            # 准备排除位置列表
            # 如果上次推荐无法落子（棋盘未变化），则排除该位置
            avoid_pos = None
            if self.excluded_recommended_moves:
                avoid_pos = []
                for ex_move in self.excluded_recommended_moves:
                    row, col = self.board_engine.gtp_to_coord(ex_move)
                    avoid_pos.append({'x': col, 'y': row})
                print(f"[打劫] 排除位置: {self.excluded_recommended_moves} -> avoid_pos={avoid_pos}")

            # 调用分析，传入需要排除的位置
            response = self._request_analysis(black_stones, white_stones, current_color, avoid_positions=avoid_pos)

            if response and response.get('success'):
                move = response.get('recommended_move')
                recommended_moves = response.get('recommended_moves', [])
                # 记录上上次推荐位置（用于检测连续相同推荐）
                if self.last_recommended_move:
                    self.last_last_recommended_move = self.last_recommended_move
                self.last_recommended_move = move
                self.last_recommended_moves = recommended_moves

                # 判断是否处于打劫状态：有排除的位置且KataGo返回了推荐
                is_ko = len(self.excluded_recommended_moves) > 0 and len(recommended_moves) > 0
                potential_ko_move = self.excluded_recommended_moves[0] if self.excluded_recommended_moves else None

                # 如果是打劫状态，KataGo返回的推荐就是劫材
                ko_alternative_moves = []
                if is_ko:
                    # KataGo已经排除了打劫位置，返回的推荐就是劫材
                    for i, m in enumerate(recommended_moves[:3]):  # 获取前3个替代位置
                        ko_alternative_moves.append({
                            'rank': i + 1,
                            'move': m['move'],
                            'winrate': m['winrate']  # 使用原始胜率
                        })
                    print(f"[打劫] 已排除 {potential_ko_move}，KataGo返回 {len(ko_alternative_moves)} 个劫材")

                # 获取目数差（scoreMean）- 当前下棋方视角
                score_mean = recommended_moves[0].get('scoreMean', 0) if recommended_moves else 0
                # 转换为黑方视角：如果当前是白棋下，目数差取反
                if current_color == 'W':
                    score_mean = -score_mean

                # 准备显示前三个推荐选项
                # KataGo 返回的 winrate 是当前下棋方(current_color)的胜率
                top_moves = []
                if recommended_moves:
                    for i, m in enumerate(recommended_moves[:3]):
                        top_moves.append({
                            'rank': i + 1,
                            'move': m['move'],
                            'winrate': m['winrate']  # 使用原始胜率（current_color的胜率）
                        })
                
                if is_ko:
                    self.ko_detected = True
                    # 使用规则引擎查找劫材和消劫点
                    engine_ko_threats = []
                    ko_resolution_moves = []
                    try:
                        # 1. 先查找能够消劫的位置（提掉对方相邻棋子）
                        board = self._sync_board_engine(black_stones, white_stones)
                        color = Color.BLACK if current_color == 'B' else Color.WHITE
                        
                        # 将打劫位置从GTP转换为坐标
                        ko_gtp = potential_ko_move
                        ko_coord = self.board_engine.gtp_to_coord(ko_gtp)  # (row, col)
                        
                        # 查找消劫点
                        ko_resolution_moves = find_ko_resolution_moves(board, color, ko_coord)
                        if ko_resolution_moves:
                            print(f"[打劫] 找到 {len(ko_resolution_moves)} 个消劫选点（可提子消劫）")
                            # 只取前3个最佳消劫点
                            ko_resolution_moves = ko_resolution_moves[:3]
                        
                        # 2. 再查找普通劫材
                        engine_ko_threats = self._get_ko_threats_with_engine(
                            black_stones, white_stones, current_color, min_value=0.05, ko_position=ko_coord
                        )
                        if engine_ko_threats:
                            print(f"[打劫] 规则引擎找到 {len(engine_ko_threats)} 个劫材")
                            # 只取前5个最有价值的劫材
                            engine_ko_threats = engine_ko_threats[:5]
                    except Exception as e:
                        print(f"[打劫] 规则引擎查找劫材失败: {e}")

                    # 打劫时简化显示：只显示劫材位置
                    ko_threats_list = []
                    
                    # 合并KataGo推荐的劫材和规则引擎找到的劫材
                    for am in ko_alternative_moves[:3]:
                        if am['move'] not in ko_threats_list:
                            ko_threats_list.append(am['move'])
                    
                    if engine_ko_threats:
                        for row, col, value in engine_ko_threats[:3]:
                            gtp = self.board_engine.coord_to_gtp(row, col)
                            if gtp not in ko_threats_list:
                                ko_threats_list.append(gtp)
                    
                    if ko_threats_list:
                        msg = f"💡 推荐劫材: {', '.join(ko_threats_list[:3])}"
                    else:
                        msg = "💡 暂无推荐劫材"
                    
                    # 更新轮到显示
                    self.root.after(0, lambda: self.turn_label.config(text=t('my_turn'), fg=self.COLORS['success']))
                    self.root.after(0, lambda: self._update_result(msg))
                    
                    # 打劫时自动选择最佳劫材或消劫点
                    if self.auto_polling_enabled.get():
                        best_move = None
                        move_source = None
                        
                        # 1. 优先选择消劫点（能够提子消劫的位置）
                        if ko_resolution_moves:
                            best_resolution = ko_resolution_moves[0]
                            best_move = self.board_engine.coord_to_gtp(best_resolution[0], best_resolution[1])
                            move_source = f"消劫点(价值:{best_resolution[2]:.2f})"
                            print(f"[打劫] 优先选择消劫点: {best_move} (价值:{best_resolution[2]:.2f})")
                        
                        # 2. 如果没有消劫点，选择KataGo推荐的劫材
                        if not best_move and ko_alternative_moves:
                            best_move = ko_alternative_moves[0]['move']
                            move_source = "KataGo推荐"
                            print(f"[打劫] 自动选择KataGo推荐劫材: {best_move}")
                        
                        # 3. 如果规则引擎找到高价值劫材，优先使用
                        if not best_move and engine_ko_threats:
                            best_threat = engine_ko_threats[0]
                            # 如果规则引擎找到的劫材价值很高（>0.5），优先使用
                            if best_threat[2] > 0.5:
                                best_move = self.board_engine.coord_to_gtp(best_threat[0], best_threat[1])
                                move_source = f"规则引擎(价值:{best_threat[2]:.2f})"
                                print(f"[打劫] 优先选择规则引擎找到的高价值劫材: {best_move} (价值:{best_threat[2]:.2f})")
                        
                        if best_move:
                            print(f"[打劫] 最终选择: {best_move} (来源: {move_source})")
                            self._auto_click(best_move)
                            self.just_clicked = True
                            return
                        else:
                            print("[打劫] 未找到合适的劫材，等待手动处理")
                            return
                else:
                    self.ko_detected = False
                    # 显示前三个推荐选项（一行显示）
                    if top_moves:
                        # 调试输出：查看实际返回的推荐
                        print(f"[Debug] KataGo返回 {len(top_moves)} 个推荐:")
                        for i, tm in enumerate(top_moves):
                            print(f"  {i+1}. {tm['move']} ({tm['winrate']:.1f}%)")
                        
                        # 使用彩色小圆点标记推荐位置（🟥🟩🟨）
                        # current_color 是当前下棋方，winrate 是该方的胜率
                        circles = ['🟥', '🟩', '🟨']
                        moves_str = " ".join([f"{circles[i]}{tm['move']}({current_color}:{tm['winrate']:.1f}%)" for i, tm in enumerate(top_moves)])

                        # 添加目数差信息（scoreMean 是黑方视角）
                        if score_mean > 0:
                            score_info = f"⚫领先{score_mean:.1f}目"
                        elif score_mean < 0:
                            score_info = f"⚪领先{abs(score_mean):.1f}目"
                        else:
                            score_info = "⚖️局势均衡"
                        
                        msg = f"{t('recommended_moves')} {moves_str} ⎸ {score_info}"
                    else:
                        msg = t('no_recommendations')
                        score_info = None
                    
                    # 更新轮到显示
                    self.root.after(0, lambda: self.turn_label.config(text=t('my_turn'), fg=self.COLORS['success']))
                    self.root.after(0, lambda: self._update_result(msg, score_info if top_moves else None))

                # 显示可视化棋盘（增量更新）
                if self.show_visualization.get():
                    # 构建candidate_moves：只显示劫材位置（不显示打劫位置）
                    if is_ko:
                        candidate_moves = []
                        # 添加KataGo推荐的劫材
                        for am in ko_alternative_moves[:3]:
                            if not any(cm['move'] == am['move'] for cm in candidate_moves):
                                candidate_moves.append(am)
                        # 添加规则引擎找到的劫材（转换为move格式）
                        if engine_ko_threats:
                            for row, col, value in engine_ko_threats[:3]:
                                gtp = self.board_engine.coord_to_gtp(row, col)
                                if not any(cm['move'] == gtp for cm in candidate_moves):
                                    candidate_moves.append({'move': gtp, 'winrate': value * 100})
                        # 保存劫材信息用于后续可视化开关切换
                        self.last_ko_candidate_moves = candidate_moves.copy()
                        ko_move = None  # 不显示打劫位置
                    else:
                        candidate_moves = None
                        self.last_ko_candidate_moves = None
                        ko_move = None
                    # 使用默认参数捕获当前值，避免lambda延迟绑定问题
                    self.root.after(0, lambda s=stones, km=ko_move, cm=candidate_moves: self._show_board_visualization(s, ko_move=km, candidate_moves=cm))

                # 更新历史落子记录（使用最佳选择）
                best_move = top_moves[0]['move'] if top_moves else move
                if best_move and best_move != 'PASS':
                    self.move_history.append(best_move)
                    if len(self.move_history) > 20:
                        self.move_history.pop(0)

                # 轮巡模式下自动落子（选择最佳位置）
                if self.auto_polling_enabled.get() and top_moves and not is_ko:
                    self._auto_click(top_moves[0]['move'])
                    self.just_clicked = True  # 标记刚完成落子，下次轮巡需要等待
            else:
                if get_language() == 'en':
                    error = response.get('message', 'Analysis failed') if response else 'Server not responding'
                else:
                    error = response.get('message', '分析失败') if response else '服务端无响应'
                self.root.after(0, lambda: self._update_result(error))

        except Exception as e:
            if get_language() == 'en':
                error_msg = f"Error: {e}"
            else:
                error_msg = f"错误: {e}"
            self.root.after(0, lambda msg=error_msg: self._update_result(msg))
        finally:
            self.is_processing = False
            self.last_analysis_time = time.time()  # 记录分析完成时间
            self.root.after(0, lambda: self.next_button.config(text=t('next_step'), state=tk.NORMAL, fg='white'))
            
    def _request_analysis(self, black_stones, white_stones, current_color, avoid_positions=None) -> Optional[Dict]:
        """请求服务端分析
        
        Args:
            black_stones: 黑棋位置列表
            white_stones: 白棋位置列表
            current_color: 当前执子颜色
            avoid_positions: 需要排除的位置（打劫时使用）
        """
        try:
            # GBR 返回的是 (row, col)，需要转换为 (x, y) 即 (col, row)
            data = {
                'stones': {
                    'black': [{'x': s[1], 'y': s[0]} for s in black_stones],
                    'white': [{'x': s[1], 'y': s[0]} for s in white_stones]
                },
                'current_color': current_color,
                'max_time': self.config.get('max_time', 5.0),
                'max_visits': self.config.get('max_visits', 5000),
                # 白棋使用更高的PDA来对抗黑棋先手优势
                'playout_doubling_advantage': 2.5,  # 双方使用相同的极端杀棋PDA
                'fast_mode': False  # 快棋模式已移除，始终使用普通模式
            }

            if avoid_positions:
                data['avoid_positions'] = avoid_positions
            
            resp = requests.post(
                f"{self.config['server_url']}/analyze",
                json=data,
                timeout=30
            )
            return resp.json()
        except Exception as e:
            print(f"请求失败: {e}")
            return None

    def _sync_board_engine(self, black_stones: list, white_stones: list) -> GoBoard:
        """
        将识别的棋子同步到 board_engine
        参考 Sabaki 的棋盘构建方式

        Args:
            black_stones: 黑棋位置列表 [(row, col), ...]
            white_stones: 白棋位置列表 [(row, col), ...]

        Returns:
            构建好的 GoBoard 实例
        """
        # 创建新棋盘（Sabaki 风格：从空棋盘开始，按顺序落子）
        board = GoBoard(size=19)

        # 合并所有棋子并按某种顺序落子（这里简化处理，直接设置）
        # 注意：这种方式会丢失打劫状态，因为没按顺序落子
        for row, col in black_stones:
            if board.get(row, col) == Color.EMPTY:
                board.set(row, col, Color.BLACK)

        for row, col in white_stones:
            if board.get(row, col) == Color.EMPTY:
                board.set(row, col, Color.WHITE)

        self.board_engine = board
        return board

    def _build_board_from_history(self, moves: List[Tuple[int, int, Color]]) -> GoBoard:
        """
        从历史落子记录构建棋盘（更准确的打劫检测）
        参考 Sabaki 的 getBoard 方法

        Args:
            moves: 落子历史 [(row, col, color), ...]

        Returns:
            构建好的 GoBoard 实例
        """
        board = GoBoard(size=19)

        for row, col, color in moves:
            if board.has(row, col) and board.get(row, col) == Color.EMPTY:
                # 使用 make_move 来正确更新打劫状态
                board = board.make_move(row, col, color)

        self.board_engine = board
        return board

    def _detect_ko_with_engine(self, black_stones: list, white_stones: list, current_color: str) -> Dict[str, Any]:
        """
        使用规则引擎准确检测打劫状态（Sabaki 风格）

        基于棋盘状态判断，而非历史记录

        Args:
            black_stones: 黑棋位置列表
            white_stones: 白棋位置列表
            current_color: 当前要下的一方 ('B' 或 'W')

        Returns:
            打劫状态字典
        """
        # 同步棋盘状态
        board = self._sync_board_engine(black_stones, white_stones)

        color = Color.BLACK if current_color == 'B' else Color.WHITE

        # 首先尝试从 _ko_info 获取打劫信息（如果有落子历史）
        ko_info = board.get_ko_info()
        if ko_info['is_ko'] and ko_info['sign'] == color:
            # 查找劫材
            ko_threats = find_ko_threats(board, color, min_value=0.2)
            return {
                'is_ko': True,
                'ko_point': ko_info['vertex'],
                'ko_threats': ko_threats,
                'forbidden_sign': color
            }

        # 如果没有历史记录，通过棋盘状态推断打劫
        detected_ko = board.detect_ko_from_position(color)
        if detected_ko['is_ko']:
            # 查找劫材
            ko_threats = find_ko_threats(board, color, min_value=0.2)
            return {
                'is_ko': True,
                'ko_point': detected_ko['ko_point'],
                'ko_threats': ko_threats,
                'forbidden_sign': color
            }

        return {'is_ko': False}

    def _get_ko_threats_with_engine(self, black_stones: list, white_stones: list, current_color: str, min_value: float = 0.2, ko_position: Tuple[int, int] = None) -> List[Tuple[int, int, float]]:
        """
        使用规则引擎查找劫材（Sabaki 风格）

        Args:
            black_stones: 黑棋位置列表
            white_stones: 白棋位置列表
            current_color: 当前要下的一方 ('B' 或 'W')
            min_value: 最小劫材价值
            ko_position: 特定的打劫位置，用于优先查找相关的劫材

        Returns:
            劫材列表，每个元素为 (row, col, value)
        """
        # 同步棋盘状态
        board = self._sync_board_engine(black_stones, white_stones)

        # 查找劫材
        color = Color.BLACK if current_color == 'B' else Color.WHITE
        return find_ko_threats(board, color, min_value=min_value, ko_position=ko_position)

    def _auto_click(self, gtp_coord: str):
        """自动落子"""
        if not gtp_coord or gtp_coord == 'PASS':
            return
        
        # 验证 GTP 坐标格式
        if len(gtp_coord) < 2:
            return
        
        try:
            col_char = gtp_coord[0].upper()
            row_num = int(gtp_coord[1:])
        except ValueError:
            return
        
        try:
            import pyautogui

            # 优先使用 GBR 识别的 board_edges 和 board_spacing 计算精确坐标
            if self.last_board_info and self.last_board_info.get('board_edges') and self.last_board_info.get('board_spacing'):
                board_edges = self.last_board_info['board_edges']
                board_spacing = self.last_board_info['board_spacing']

                # GTP 转数组坐标 (row, col)
                col = ord(col_char) - ord('A')
                if col >= 8:
                    col -= 1
                row = 19 - row_num  # GTP行号1-19转数组行号0-18

                # 转换为 GBR 格式 (a, b)
                # a: 列 1-19 (从左到右)
                # b: 行 1-19 (从下到上)
                a = col + 1  # 列：0-18 -> 1-19
                b = 19 - row  # 行：从上到下0-18 -> 从下往上1-19

                # 计算图像坐标（相对于截图）
                img_x = board_edges[0][0] + (a - 1) * board_spacing[0]
                img_y = board_edges[0][1] + (b - 1) * board_spacing[1]

                # 翻转Y坐标（修复镜像问题）
                if self.board_region:
                    img_height = self.board_region[3]
                    img_y = img_height - img_y

                # 转换为屏幕坐标
                if self.board_region:
                    bx, by, bw, bh = self.board_region
                    click_x = bx + img_x
                    click_y = by + img_y
                else:
                    click_x = img_x
                    click_y = img_y

            else:
                # 降级使用简单计算
                try:
                    col_char = gtp_coord[0].upper()
                    row_num = int(gtp_coord[1:])
                    col = ord(col_char) - ord('A')
                    if col >= 8:
                        col -= 1
                    row = 19 - row_num
                except (ValueError, IndexError):
                    return
                
                if not self.board_region:
                    return

                x, y, w, h = self.board_region
                cell_w = w / 18
                cell_h = h / 18

                click_x = x + col * cell_w
                click_y = y + row * cell_h

            pyautogui.doubleClick(click_x, click_y)
            
            # 落子成功后清空排除列表
            self.excluded_recommended_moves = []
            print(f"[自动落子] 成功落子 {gtp_coord}，清空排除列表")
            
        except Exception as e:
            print(f"自动落子失败: {e}")
            
    def _update_result(self, text: str, score_info: str = None, append: bool = False):
        """更新结果显示 - 使用 Canvas 实现游戏级美观效果，支持自动换行

        Args:
            text: 主要显示文本
            score_info: 目数差信息（可选）
            append: 是否追加到现有内容（默认False，清空后显示）
        """
        # 清空 Canvas
        self.result_canvas.delete('all')
        self.result_canvas_items = []

        # 获取 Canvas 尺寸
        self.result_canvas.update_idletasks()
        canvas_width = self.result_canvas.winfo_width()
        canvas_height = self.result_canvas.winfo_height()

        if canvas_width < 10:
            canvas_width = 400
        if canvas_height < 10:
            canvas_height = 60

        padding = 10
        line_height = 22

        # 解析文本内容
        has_rec = '推荐落子' in text or t('recommended_moves') in text
        has_sep = '⎸' in text

        if has_rec and has_sep:
            # 分离推荐部分和目数差
            parts = text.split('⎸')
            if len(parts) == 2:
                rec_part = parts[0].strip()
                score_part = parts[1].strip()

                # 解析推荐位置
                import re
                moves = re.findall(r'([🟥🟩🟨])([A-Z]\d+)\(([BW]):([\d.]+)%\)', rec_part)
                colors_map = {'🟥': '#F44336', '🟩': '#4CAF50', '🟨': '#FFC107'}

                # 2x2 表格布局参数
                cols = 2  # 2列
                rows = 2  # 2行
                cell_width = (canvas_width - padding * 2) // cols  # 每个格子宽度
                cell_height = (canvas_height - 10) // rows  # 每个格子高度

                # 绘制2x2表格中的推荐
                for i, (circle, pos, color, winrate) in enumerate(moves[:3]):  # 最多3个推荐
                    # 计算当前推荐在第几行第几列
                    row = i // cols
                    col = i % cols

                    # 计算格子中心位置
                    cell_x = padding + col * cell_width + cell_width // 2
                    cell_y = 5 + row * cell_height + cell_height // 2

                    # 绘制彩色圆角方块（居中）
                    box_size = 14
                    color_fill = colors_map.get(circle, '#999999')
                    r = 4
                    # 计算起始x位置（让整个推荐项居中）
                    item_width = box_size + 6 + 30 + 70  # 方块+间距+位置+胜率
                    start_x = cell_x - item_width // 2

                    x1, y1_box, x2, y2_box = start_x, cell_y - box_size//2, start_x + box_size, cell_y + box_size//2
                    self.result_canvas.create_polygon(
                        x1+r, y1_box, x2-r, y1_box, x2, y1_box+r, x2, y2_box-r, x2-r, y2_box, x1+r, y2_box, x1, y2_box-r, x1, y1_box+r,
                        fill=color_fill, outline='', smooth=True
                    )
                    # 在方块中绘制数字
                    self.result_canvas.create_text(
                        start_x + box_size//2, cell_y, text=str(i+1),
                        font=('Helvetica Neue', 8, 'bold'),
                        fill='white',
                        anchor='c'
                    )

                    # 位置文字
                    self.result_canvas.create_text(
                        start_x + box_size + 6, cell_y, text=pos,
                        font=self.FONTS['body_bold'],
                        fill=self.COLORS['text_primary'],
                        anchor='w'
                    )

                    # 胜率
                    self.result_canvas.create_text(
                        start_x + box_size + 6 + 30, cell_y, text=f'({color}:{winrate}%)',
                        font=self.FONTS['small'],
                        fill=self.COLORS['text_secondary'],
                        anchor='w'
                    )

                # 在第4个格子（右下）显示目数差
                last_cell_x = padding + 1 * cell_width + cell_width // 2
                last_cell_y = 5 + 1 * cell_height + cell_height // 2
                self._draw_score_part_centered(last_cell_x, last_cell_y, score_part)
            else:
                self._draw_simple_text(padding, canvas_height // 2, text)
        else:
            self._draw_simple_text(padding, canvas_height // 2, text)

    def _draw_score_part(self, x, y, score_part):
        """绘制目数差部分 - 缩小图标，明确显示黑白"""
        # 解析目数差并确定显示文字
        if '⚫' in score_part:
            icon = '⚫'
            score_value = score_part.replace('⚫', '').replace('领先', '').replace('目', '').strip()
            display_text = t('black_lead').format(score_value)
            icon_color = '#333333'
        elif '⚪' in score_part:
            icon = '⚪'
            score_value = score_part.replace('⚪', '').replace('领先', '').replace('目', '').strip()
            display_text = t('white_lead').format(score_value)
            icon_color = '#666666'
        else:
            icon = '⚖️'
            display_text = t('score_even')
            icon_color = '#FF9800'
        
        # 绘制小图标背景圆（缩小）
        circle_size = 8
        self.result_canvas.create_oval(
            x, y - circle_size, x + circle_size * 2, y + circle_size,
            fill='#F5F5F5', outline='#E0E0E0'
        )
        
        # 小图标
        self.result_canvas.create_text(
            x + circle_size, y, text=icon,
            font=('Helvetica Neue', 10),
            fill=icon_color,
            anchor='c'
        )
        
        # 目数差文字（蓝色醒目，显示"黑领先X目"或"白领先X目"）
        self.result_canvas.create_text(
            x + circle_size * 2 + 6, y, text=display_text,
            font=('Helvetica Neue', 12, 'bold'),
            fill='#2196F3',
            anchor='w'
        )
    
    def _draw_simple_text(self, x, y, text):
        """绘制简单文本"""
        self.result_canvas.create_text(
            x, y, text=text,
            font=self.FONTS['body'],
            fill=self.COLORS['text_primary'],
            anchor='w'
        )

    def _draw_score_part_centered(self, center_x, center_y, score_part):
        """绘制目数差部分 - 居中显示"""
        # 解析目数差并确定显示文字
        if '⚫' in score_part:
            icon = '⚫'
            score_value = score_part.replace('⚫', '').replace('领先', '').replace('目', '').strip()
            display_text = t('black_lead').format(score_value)
            icon_color = '#333333'
        elif '⚪' in score_part:
            icon = '⚪'
            score_value = score_part.replace('⚪', '').replace('领先', '').replace('目', '').strip()
            display_text = t('white_lead').format(score_value)
            icon_color = '#666666'
        else:
            icon = '⚖️'
            display_text = t('score_even')
            icon_color = '#FF9800'
        
        # 计算整体宽度以居中
        circle_size = 8
        # 估算文字宽度（每个字符约10像素）
        text_width = len(display_text) * 10
        total_width = circle_size * 2 + 6 + text_width
        
        # 计算起始x位置（居中）
        x = center_x - total_width // 2
        y = center_y
        
        # 绘制小图标背景圆
        self.result_canvas.create_oval(
            x, y - circle_size, x + circle_size * 2, y + circle_size,
            fill='#F5F5F5', outline='#E0E0E0'
        )
        
        # 小图标
        self.result_canvas.create_text(
            x + circle_size, y, text=icon,
            font=('Helvetica Neue', 10),
            fill=icon_color,
            anchor='c'
        )
        
        # 目数差文字
        self.result_canvas.create_text(
            x + circle_size * 2 + 6, y, text=display_text,
            font=('Helvetica Neue', 12, 'bold'),
            fill='#2196F3',
            anchor='w'
        )

    def _create_canvas_checkbox(self, parent, text_key, variable, command, padx=(0, 0)):
        """创建可爱的花朵形状或棋盘图标复选框（超紧凑布局）"""
        checkbox_frame = tk.Frame(parent, bg=self.COLORS['card'])
        checkbox_frame.pack(side=tk.LEFT, padx=padx)

        # 计算Canvas宽度（图标和文字保持适当间距）
        text_content = t(text_key)
        text_length = len(text_content)
        # 中文每个字约12px，英文每个字母约8px
        char_width = 12 if any('\u4e00' <= c <= '\u9fff' for c in text_content) else 8
        # 图标区域(28px) + 间距(4px) + 文字宽度
        canvas_width = 32 + text_length * char_width
        canvas_height = 28
        canvas = tk.Canvas(
            checkbox_frame,
            width=canvas_width,
            height=canvas_height,
            bg=self.COLORS['card'],
            highlightthickness=0,
            cursor="hand2"
        )
        canvas.pack()

        # 保存引用
        if text_key == 'polling':
            self.auto_polling_canvas = canvas
            self.auto_polling_var = variable
            self.auto_polling_cmd = command
            # 绘制花朵（自动下棋）- 图标靠左
            self._draw_flower_checkbox(canvas, variable.get(), icon_x=14)
            # 文字与图标保持适当间距（和黑白选择器一致），颜色稍浅不突出
            canvas.create_text(32, 14, text=text_content, font=self.FONTS['body_bold'],
                              fill=self.COLORS['text_secondary'], tags='text_label', anchor='w')
        else:
            self.board_canvas = canvas
            self.board_var = variable
            self.board_cmd = command
            # 绘制棋盘图标（棋盘）- 图标靠左
            self._draw_board_checkbox(canvas, variable.get(), icon_x=14)
            # 文字与图标保持适当间距（和黑白选择器一致），颜色稍浅不突出
            canvas.create_text(32, 14, text=text_content, font=self.FONTS['body_bold'],
                              fill=self.COLORS['text_secondary'], tags='text_label', anchor='w')

        # 绑定点击事件
        canvas.bind("<Button-1>", lambda e, c=canvas, v=variable, cmd=command, key=text_key: self._on_canvas_checkbox_click(e, c, v, cmd, key))

    def _draw_flower_checkbox(self, canvas, is_checked, icon_x=14):
        """绘制花朵形状复选框"""
        center_x, center_y = icon_x, 14
        petal_length = 6

        # 绘制花朵花瓣（5个花瓣）
        petal_color = '#FF69B4' if is_checked else '#FFB6C1'
        outline_color = '#FF1493' if is_checked else '#FFB6C1'

        # 上花瓣
        canvas.create_oval(center_x-4, center_y-petal_length-3, center_x+4, center_y-petal_length+5,
                          fill=petal_color, outline=outline_color, width=1, tags=('petal', 'petal_top'))
        # 右上花瓣
        canvas.create_oval(center_x+3, center_y-petal_length+1, center_x+11, center_y-petal_length+9,
                          fill=petal_color, outline=outline_color, width=1, tags=('petal', 'petal_tr'))
        # 右下花瓣
        canvas.create_oval(center_x+3, center_y+petal_length-7, center_x+11, center_y+petal_length+1,
                          fill=petal_color, outline=outline_color, width=1, tags=('petal', 'petal_br'))
        # 左下花瓣
        canvas.create_oval(center_x-11, center_y+petal_length-7, center_x-3, center_y+petal_length+1,
                          fill=petal_color, outline=outline_color, width=1, tags=('petal', 'petal_bl'))
        # 左上花瓣
        canvas.create_oval(center_x-11, center_y-petal_length+1, center_x-3, center_y-petal_length+9,
                          fill=petal_color, outline=outline_color, width=1, tags=('petal', 'petal_tl'))

        # 绘制花朵中心（花蕊）
        center_color = '#FFA500' if is_checked else '#FFD700'
        canvas.create_oval(center_x-5, center_y-5, center_x+5, center_y+5,
                          fill=center_color, outline='#FF8C00', width=1, tags='flower_center')

        # 绘制花蕊小点
        canvas.create_oval(center_x-2, center_y-2, center_x+2, center_y+2,
                          fill='#FF6347', outline='', tags='flower_dot')

        # 绘制勾选标记
        canvas.create_text(center_x, center_y, text='✓',
                          font=('Helvetica Neue', 10, 'bold'),
                          fill='white', tags='check_mark',
                          state='normal' if is_checked else 'hidden')

    def _draw_board_checkbox(self, canvas, is_checked, icon_x=14):
        """绘制简化的小棋盘图标复选框"""
        # 棋盘位置和大小（再缩小一点，居中于icon_x）
        board_size = 16
        board_x = icon_x - board_size / 2
        board_y = 6
        grid_count = 4  # 4x4网格（更简单）

        # 棋盘背景色（传统棋盘土黄色，稍亮）
        bg_color = '#E8C9A0'  # 稍亮的传统棋盘土黄色
        border_color = '#C4A77D'  # 深一点的土黄色边框

        # 绘制棋盘背景
        canvas.create_rectangle(
            board_x, board_y, board_x + board_size, board_y + board_size,
            fill=bg_color, outline=border_color, width=1, tags='board_bg'
        )

        # 绘制简单的网格线（3x3格子）- 稍深的灰色线条，更细
        line_color = '#A0A0A0'
        cell_size = board_size / (grid_count - 1)

        # 横线（只画中间两条）
        for i in range(1, grid_count - 1):
            y = board_y + i * cell_size
            canvas.create_line(
                board_x, y, board_x + board_size, y,
                fill=line_color, width=0.5, tags='board_grid'
            )

        # 竖线（只画中间两条）
        for i in range(1, grid_count - 1):
            x = board_x + i * cell_size
            canvas.create_line(
                x, board_y, x, board_y + board_size,
                fill=line_color, width=0.5, tags='board_grid'
            )

        # 绘制选中对勾（在棋盘中央）
        center_x = board_x + board_size / 2
        center_y = board_y + board_size / 2
        canvas.create_text(center_x, center_y, text='✓',
                          font=('Helvetica Neue', 12, 'bold'),
                          fill='#2196F3',
                          tags='check_mark',
                          state='normal' if is_checked else 'hidden')

    def _on_canvas_checkbox_click(self, event, canvas, variable, command, key):
        """处理Canvas复选框点击"""
        # 切换变量值
        variable.set(not variable.get())

        # 更新显示
        is_checked = variable.get()

        # 根据类型更新不同的复选框
        if key == 'polling':
            # 花朵复选框
            petal_color = '#FF69B4' if is_checked else '#FFB6C1'
            outline_color = '#FF1493' if is_checked else '#FFB6C1'
            center_color = '#FFA500' if is_checked else '#FFD700'

            # 更新所有花瓣
            for tag in ['petal_top', 'petal_tr', 'petal_br', 'petal_bl', 'petal_tl']:
                canvas.itemconfig(tag, fill=petal_color, outline=outline_color)

            # 更新花蕊
            canvas.itemconfig('flower_center', fill=center_color)
        else:
            # 棋盘复选框（椴木色）
            bg_color = '#F0E6D2' if is_checked else '#E0D4C0'
            border_color = '#C4B8A0' if is_checked else '#B4A890'
            canvas.itemconfig('board_bg', fill=bg_color, outline=border_color)

        # 显示/隐藏勾选标记
        canvas.itemconfig('check_mark', state='normal' if is_checked else 'hidden')

        # 执行回调
        if command:
            command()

    def _create_canvas_color_toggle(self, parent, padx=(0, 0)):
        """创建精美的立体黑白子选择器（超紧凑布局，显示完整）"""
        toggle_frame = tk.Frame(parent, bg=self.COLORS['card'])
        toggle_frame.pack(side=tk.LEFT, padx=padx)

        # 计算Canvas宽度 - 确保文字显示完整
        text_content = t('black')  # 使用"黑"或"白"计算
        text_length = len(text_content)
        char_width = 12 if any('\u4e00' <= c <= '\u9fff' for c in text_content) else 8
        # 两个棋子(24px each) + 间距(4px) + 文字
        canvas_width = 52 + text_length * char_width + 4
        canvas_height = 28
        self.color_toggle_canvas = tk.Canvas(
            toggle_frame,
            width=canvas_width,
            height=canvas_height,
            bg=self.COLORS['card'],
            highlightthickness=0,
            cursor="hand2"
        )
        self.color_toggle_canvas.pack()

        # 绘制立体黑子（左侧）
        self._draw_3d_stone(self.color_toggle_canvas, 12, 14, 'black', 'black_stone')

        # 绘制立体白子（右侧）
        self._draw_3d_stone(self.color_toggle_canvas, 32, 14, 'white', 'white_stone')

        # 绘制选中指示器（绿色对勾，黑白棋子上都清晰可见）
        self.selection_indicator = self.color_toggle_canvas.create_text(
            0, 0, text='✓', font=('Helvetica Neue', 10, 'bold'),
            fill='#4CAF50', tags='indicator', anchor='center'
        )

        # 绘制颜色文字标签（紧挨棋子右侧），颜色稍浅不突出
        self.color_text = self.color_toggle_canvas.create_text(
            52, 14, text=t('black'), fill=self.COLORS['text_secondary'],
            font=self.FONTS['body_bold'], tags='color_text', anchor='w'
        )

        # 初始状态
        self._update_stone_toggle_display()

        # 绑定点击事件
        self.color_toggle_canvas.bind("<Button-1>", self._on_stone_toggle_click)

    def _draw_3d_stone(self, canvas, cx, cy, color, tag_prefix):
        """绘制3D立体围棋子（更紧凑版）

        Args:
            canvas: Canvas对象
            cx, cy: 棋子中心坐标
            color: 'black' 或 'white'
            tag_prefix: 标签前缀
        """
        r = 8  # 棋子半径（再缩小一点）

        # 绘制阴影（偏移1像素）
        canvas.create_oval(
            cx - r + 1, cy - r + 1, cx + r + 1, cy + r + 1,
            fill='#A0A0A0', outline='', tags=f'{tag_prefix}_shadow'
        )

        # 绘制棋子主体
        stone_color = '#1a1a1a' if color == 'black' else '#f5f5f5'
        canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill=stone_color, outline='#333333' if color == 'black' else '#cccccc',
            width=1, tags=f'{tag_prefix}_body'
        )

        # 绘制高光（左上角）- 营造立体感
        highlight_color = '#444444' if color == 'black' else '#ffffff'
        canvas.create_oval(
            cx - r + 2, cy - r + 2, cx - r + 6, cy - r + 6,
            fill=highlight_color, outline='', tags=f'{tag_prefix}_highlight'
        )

        # 绘制主光源反射（椭圆高光）
        reflection_color = '#666666' if color == 'black' else '#ffffff'
        canvas.create_oval(
            cx - 3, cy - 4, cx + 1, cy - 1,
            fill=reflection_color, outline='', tags=f'{tag_prefix}_reflection'
        )

    def _update_stone_toggle_display(self):
        """更新立体黑白子选择器显示"""
        if self.selected_color.get() == "B":
            # 黑子选中 - 绿色对勾显示在黑子正中心
            self.color_toggle_canvas.coords('indicator', 12, 14)
            self.color_toggle_canvas.itemconfig('color_text', text=t('black'))
        else:
            # 白子选中 - 绿色对勾显示在白子正中心
            self.color_toggle_canvas.coords('indicator', 32, 14)
            self.color_toggle_canvas.itemconfig('color_text', text=t('white'))

    def _on_stone_toggle_click(self, event):
        """处理立体黑白子选择器点击"""
        x = event.x
        # 点击左侧黑子区域（半径8，中心12）
        if x < 22:
            self.selected_color.set("B")
        # 点击右侧白子区域（半径8，中心32）
        elif x < 44:
            self.selected_color.set("W")
        # 点击文字区域也切换
        else:
            if self.selected_color.get() == "B":
                self.selected_color.set("W")
            else:
                self.selected_color.set("B")
        self._update_stone_toggle_display()

    def _create_time_slider(self, parent):
        """创建自定义时间滑动条 - 带刻度标记和时间值显示"""
        slider_frame = tk.Frame(parent, bg=self.COLORS['card'])
        slider_frame.pack(side=tk.LEFT, padx=5)

        # 创建Canvas绘制滑动条（增加高度以容纳时间值显示）
        slider_width = 140
        slider_height = 48
        self.time_slider_canvas = tk.Canvas(
            slider_frame,
            width=slider_width,
            height=slider_height,
            bg=self.COLORS['card'],
            highlightthickness=0,
            cursor="hand2"
        )
        self.time_slider_canvas.pack()

        # 滑动条参数
        self.time_slider_min = 0.5
        self.time_slider_max = 20.0
        self.time_slider_value = self.config.get('max_time', 1.9)

        # 轨道位置（向下移动以腾出空间给时间值显示）
        track_y = 28
        track_start = 15
        track_end = slider_width - 15

        # 绘制刻度标记和标签
        tick_positions = [1, 5, 10, 15, 20]  # 刻度位置
        for tick_val in tick_positions:
            ratio = (tick_val - self.time_slider_min) / (self.time_slider_max - self.time_slider_min)
            tick_x = track_start + ratio * (track_end - track_start)

            # 绘制刻度线（紧挨着轨道下方）
            self.time_slider_canvas.create_line(
                tick_x, track_y + 5, tick_x, track_y + 8,
                fill='#999999', width=1
            )

            # 绘制刻度标签（紧挨着刻度线下方）
            self.time_slider_canvas.create_text(
                tick_x, track_y + 16,
                text=str(tick_val),
                font=('Helvetica Neue', 7),
                fill='#888888'
            )

        # 绘制背景轨道（圆角）
        self.time_slider_canvas.create_line(track_start, track_y, track_end, track_y,
                                            fill='#E0E0E0', width=8, capstyle='round')

        # 绘制已填充部分（蓝色）
        self.time_slider_fill = self.time_slider_canvas.create_line(
            track_start, track_y, track_start, track_y,
            fill=self.COLORS['primary'], width=8, capstyle='round'
        )

        # 绘制滑块（圆形）
        self.time_slider_handle = self.time_slider_canvas.create_oval(
            0, 0, 18, 18,
            fill='white',
            outline=self.COLORS['primary'],
            width=2
        )

        # 添加阴影效果
        self.time_slider_shadow = self.time_slider_canvas.create_oval(
            2, 2, 20, 20,
            fill='#D0D0D0',
            outline=''
        )
        self.time_slider_canvas.tag_lower(self.time_slider_shadow)

        # 绘制时间值显示（在轨道正上方，简洁无背景）
        # 时间值文本 - 蓝色，无背景圈
        self.time_value_text = self.time_slider_canvas.create_text(
            0, 0,
            text="",
            font=('Helvetica Neue', 11, 'bold'),
            fill=self.COLORS['primary'],
            state='hidden'
        )

        # 更新滑块位置
        self._update_time_slider_position()

        # 绑定事件
        self.time_slider_canvas.bind("<Button-1>", self._on_time_slider_click)
        self.time_slider_canvas.bind("<B1-Motion>", self._on_time_slider_drag)
        
    def _update_time_slider_position(self):
        """更新时间滑动条位置和时间值显示"""
        slider_width = 140
        track_start = 15
        track_end = slider_width - 15
        track_length = track_end - track_start
        track_y = 28

        # 计算位置
        ratio = (self.time_slider_value - self.time_slider_min) / (self.time_slider_max - self.time_slider_min)
        handle_x = track_start + ratio * track_length

        # 更新填充线
        self.time_slider_canvas.coords(self.time_slider_fill, track_start, track_y, handle_x, track_y)

        # 更新滑块位置
        self.time_slider_canvas.coords(self.time_slider_handle, handle_x-9, track_y-9, handle_x+9, track_y+9)
        self.time_slider_canvas.coords(self.time_slider_shadow, handle_x-7, track_y-7, handle_x+11, track_y+11)

        # 更新时间值显示（在轨道正上方，简洁无背景）
        value_y = 12  # 轨道上方位置
        value_text = f"{self.time_slider_value:.1f}s"

        # 更新文本位置（无背景圈）
        self.time_slider_canvas.coords(self.time_value_text, handle_x, value_y)
        self.time_slider_canvas.itemconfig(self.time_value_text, text=value_text, state='normal')
        
    def _on_time_slider_click(self, event):
        """处理滑动条点击"""
        self._update_time_slider_from_mouse(event.x)
        
    def _on_time_slider_drag(self, event):
        """处理滑动条拖动"""
        self._update_time_slider_from_mouse(event.x)
        
    def _update_time_slider_from_mouse(self, mouse_x):
        """根据鼠标位置更新滑动条值"""
        slider_width = 140
        track_start = 15
        track_end = slider_width - 15
        track_length = track_end - track_start

        # 计算比例
        ratio = max(0, min(1, (mouse_x - track_start) / track_length))

        # 计算值（0.5-20.0，保留1位小数）
        raw_value = self.time_slider_min + ratio * (self.time_slider_max - self.time_slider_min)
        self.time_slider_value = round(raw_value * 2) / 2  # 四舍五入到0.5的倍数
        self.time_slider_value = max(self.time_slider_min, min(self.time_slider_max, self.time_slider_value))

        # 更新显示
        self._update_time_slider_position()

        # 更新配置
        self.config['max_time'] = self.time_slider_value
        self._save_config()

    def _show_board_visualization(self, stones: Dict, ko_move: Optional[str] = None, candidate_moves: Optional[List[Dict]] = None):
        """显示棋盘可视化 - 使用增量更新优化
        
        Args:
            stones: 棋盘棋子信息
            ko_move: 打劫位置（GTP坐标），如果有的话
            candidate_moves: 推荐候选落子列表，用于显示多个选项
        """
        try:
            # 创建或更新棋盘窗口
            if not hasattr(self, 'board_window') or not self.board_window.winfo_exists():
                self.board_window = tk.Toplevel(self.root)
                self.board_window.title(t('board'))
                self.board_window.geometry("500x520")
                self.board_window.configure(bg='#DCB35C')
                self.board_window.attributes('-topmost', True)
                self.board_window.update_idletasks()
                screen_width = self.board_window.winfo_screenwidth()
                screen_height = self.board_window.winfo_screenheight()
                x = screen_width - 520
                y = screen_height - 560
                self.board_window.geometry(f"500x520+{x}+{y}")

                self.board_canvas = tk.Canvas(self.board_window, width=480, height=480, bg='#DCB35C', highlightthickness=0)
                self.board_canvas.pack(pady=(10, 0))

                # 初始化棋盘背景（只绘制一次）
                self._draw_board_background()

                # 初始化棋子存储
                self.canvas_stones = {}

                # 创建底部配置信息标签（放在Canvas下方）
                self.config_label = tk.Label(
                    self.board_window,
                    text="",
                    bg='#DCB35C',
                    fg='#228B22',
                    font=('Arial', 11)
                )
                self.config_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 10))

            self.board_window.lift()
            self.board_window.attributes('-topmost', True)

            # 棋盘参数
            board_size = 19
            canvas_size = 480
            margin = 25
            cell_size = (canvas_size - 2 * margin) / (board_size - 1)
            stone_radius = cell_size * 0.4

            # 获取当前棋子集合
            current_stones = {}
            for stone in stones.get('black', []):
                row, col = stone[0], stone[1]
                current_stones[(row, col)] = 'black'
            for stone in stones.get('white', []):
                row, col = stone[0], stone[1]
                current_stones[(row, col)] = 'white'

            # 获取上次的棋子集合
            last_stones = getattr(self, 'canvas_stones', {})

            # 删除消失的棋子
            for pos, color in list(last_stones.items()):
                if pos not in current_stones:
                    # 删除该位置的棋子（通过标签）
                    self.board_canvas.delete(f"stone_{pos[0]}_{pos[1]}")

            # 添加或更新棋子
            for pos, color in current_stones.items():
                row, col = pos
                x = margin + col * cell_size
                y = margin + row * cell_size

                if pos in last_stones and last_stones[pos] == color:
                    # 棋子未变化，跳过
                    continue

                # 删除该位置的旧棋子（如果有）
                self.board_canvas.delete(f"stone_{row}_{col}")

                # 绘制新棋子
                if color == 'black':
                    self.board_canvas.create_oval(
                        x-stone_radius, y-stone_radius, x+stone_radius, y+stone_radius,
                        fill='black', outline='black', tags=f"stone_{row}_{col}"
                    )
                else:
                    self.board_canvas.create_oval(
                        x-stone_radius, y-stone_radius, x+stone_radius, y+stone_radius,
                        fill='white', outline='#888888', width=1, tags=f"stone_{row}_{col}"
                    )

            # 更新存储
            self.canvas_stones = current_stones

            # 删除旧的推荐标记
            self.board_canvas.delete("recommend")
            self.board_canvas.delete("ko_marker")
            self.board_canvas.delete("candidate")

            # 标记打劫位置和候选劫材（与推荐位置一样的规范显示）
            if ko_move and ko_move != 'PASS':
                # 颜色顺序：红(第1)、绿(第2)、黄(第3)
                ko_colors = ['red', 'green', 'yellow']
                
                # 显示候选劫材（用推荐位置一样的样式）
                if candidate_moves and len(candidate_moves) > 1:
                    for i, m in enumerate(candidate_moves[1:4]):  # 跳过第一个（打劫位置），显示后面的候选
                        try:
                            move = m['move'] if isinstance(m, dict) else m
                            winrate = m.get('winrate', 0) if isinstance(m, dict) else 0
                            if move == 'PASS' or len(move) < 2:
                                continue
                            col_char = move[0].upper()
                            row_num = int(move[1:])
                            col = ord(col_char) - ord('A')
                            if col >= 8:
                                col -= 1
                            row = 19 - row_num
                            x = margin + col * cell_size
                            y = margin + row * cell_size
                            color = ko_colors[i] if i < len(ko_colors) else 'gray'
                            # 彩色三角形标记劫材位置
                            self.board_canvas.create_polygon(
                                x, y - stone_radius * 0.9,  # 顶点
                                x - stone_radius * 0.75, y + stone_radius * 0.5,  # 左下
                                x + stone_radius * 0.75, y + stone_radius * 0.5,  # 右下
                                fill=color, outline='black', width=2, tags="candidate"
                            )
                            # 在三角形内显示序号
                            text_color = 'white' if color in ['red', 'green'] else 'black'
                            self.board_canvas.create_text(x, y + stone_radius*0.1, text=str(i+1), fill=text_color, 
                                                         font=('Arial', 12, 'bold'), tags="candidate")
                            # 在三角形上方显示胜率
                            self.board_canvas.create_text(x, y - stone_radius*1.2, 
                                                         text=f"{winrate:.1f}%", 
                                                         fill=color, 
                                                         font=('Arial', 9, 'bold'), 
                                                         tags="candidate")
                        except (ValueError, IndexError, NameError):
                            pass
                
                # 标记打劫位置（红色三角形+禁止符号）
                if ko_move and len(ko_move) >= 2:
                    try:
                        col_char = ko_move[0].upper()
                        row_num = int(ko_move[1:])
                        col = ord(col_char) - ord('A')
                        if col >= 8:
                            col -= 1
                        row = 19 - row_num
                        x = margin + col * cell_size
                        y = margin + row * cell_size
                        # 红色三角形标记打劫位置
                        self.board_canvas.create_polygon(
                            x, y - stone_radius * 0.8,
                            x - stone_radius * 0.7, y + stone_radius * 0.5,
                            x + stone_radius * 0.7, y + stone_radius * 0.5,
                            fill='red', outline='darkred', width=2, tags="ko_marker"
                        )
                        # 在三角形内显示禁止符号
                        self.board_canvas.create_text(x, y, text='🚫', fill='white', 
                                                     font=('Arial', 10, 'bold'), tags="ko_marker")
                    except (ValueError, IndexError, NameError):
                        pass
            # 显示劫材位置（打劫时ko_move为None，但candidate_moves有值）
            elif candidate_moves and len(candidate_moves) > 0:
                # 颜色顺序：红(第1)、绿(第2)、黄(第3)
                ko_colors = ['red', 'green', 'yellow']
                
                for i, m in enumerate(candidate_moves[:3]):  # 显示前3个劫材
                    try:
                        move = m['move'] if isinstance(m, dict) else m
                        winrate = m.get('winrate', 0) if isinstance(m, dict) else 0
                        if move == 'PASS' or len(move) < 2:
                            continue
                        col_char = move[0].upper()
                        row_num = int(move[1:])
                        col = ord(col_char) - ord('A')
                        if col >= 8:
                            col -= 1
                        row = 19 - row_num
                        x = margin + col * cell_size
                        y = margin + row * cell_size
                        color = ko_colors[i] if i < len(ko_colors) else 'gray'
                        # 彩色圆圈标记劫材位置
                        self.board_canvas.create_oval(
                            x-stone_radius*0.85, y-stone_radius*0.85,
                            x+stone_radius*0.85, y+stone_radius*0.85,
                            fill=color, outline='black', width=2, tags="candidate"
                        )
                        # 在圆圈内显示序号
                        text_color = 'white' if color in ['red', 'green'] else 'black'
                        self.board_canvas.create_text(x, y, text=str(i+1), fill=text_color, 
                                                     font=('Arial', 12, 'bold'), tags="candidate")
                    except (ValueError, IndexError, NameError):
                        pass
            # 标记推荐落子（非打劫时）
            else:
                # 获取推荐列表（从服务端返回的完整列表）
                recommended_moves = getattr(self, 'last_recommended_moves', [])
                if recommended_moves:
                    # 颜色顺序：红(第1)、绿(第2)、黄(第3)
                    colors = ['red', 'green', 'yellow']
                    for i, move_data in enumerate(recommended_moves[:3]):
                        try:
                            move = move_data['move']
                            winrate = move_data.get('winrate', 0)
                            if move == 'PASS' or len(move) < 2:
                                continue
                            col_char = move[0].upper()
                            row_num = int(move[1:])
                            col = ord(col_char) - ord('A')
                            if col >= 8:
                                col -= 1
                            row = 19 - row_num
                            x = margin + col * cell_size
                            y = margin + row * cell_size
                            color = colors[i] if i < len(colors) else 'gray'
                            # 更大的圆圈标记
                            self.board_canvas.create_oval(
                                x-stone_radius*0.85, y-stone_radius*0.85,
                                x+stone_radius*0.85, y+stone_radius*0.85,
                                fill=color, outline='black', width=2, tags="recommend"
                            )
                            # 在圆圈内显示序号
                            text_color = 'white' if color in ['red', 'green'] else 'black'
                            self.board_canvas.create_text(x, y, text=str(i+1), fill=text_color, 
                                                         font=('Arial', 12, 'bold'), tags="recommend")
                            # 在圆圈上方显示胜率
                            self.board_canvas.create_text(x, y - stone_radius*1.1, 
                                                         text=f"{winrate:.1f}%", 
                                                         fill=color, 
                                                         font=('Arial', 9, 'bold'), 
                                                         tags="recommend")
                        except (ValueError, IndexError):
                            pass
                # 如果没有推荐列表，显示单个推荐
                elif self.last_recommended_move and self.last_recommended_move != 'PASS' and len(self.last_recommended_move) >= 2:
                    try:
                        col_char = self.last_recommended_move[0].upper()
                        row_num = int(self.last_recommended_move[1:])
                        col = ord(col_char) - ord('A')
                        if col >= 8:
                            col -= 1
                        row = 19 - row_num
                        x = margin + col * cell_size
                        y = margin + row * cell_size
                        self.board_canvas.create_text(x, y, text='★', fill='red', font=('Arial', 16, 'bold'), tags="recommend")
                    except (ValueError, IndexError):
                        pass

            # 更新标题
            black_count = len(stones.get('black', []))
            white_count = len(stones.get('white', []))
            stones_str = t('stones_count').format(black_count, white_count)
            self.board_window.title(f"{t('board')} - {stones_str}")

            # 在底部显示服务器配置和KataGo参数（绿色小字）
            self._draw_config_info()

        except Exception as e:
            print(f"可视化失败: {e}")

    def _draw_config_info(self):
        """在棋盘底部绘制服务器配置和KataGo参数（包含目数权重、胜率权重、探索参数、实际visits）"""
        try:
            # 获取配置信息（从客户端配置）
            visits = self.config.get('max_visits', 5000)
            thinking_time = self.config.get('max_time', 5.0)

            # 获取服务器KataGo配置（缓存）
            katago_config = getattr(self, 'katago_config', None)
            if not katago_config:
                # 异步获取配置（首次）
                threading.Thread(target=self._fetch_katago_config, daemon=True).start()
                katago_config = {}

            # 获取实际分析的visits数量
            actual_visits = 0
            recommended_moves = getattr(self, 'last_recommended_moves', [])
            if recommended_moves and len(recommended_moves) > 0:
                # 使用第一个推荐位置的visits作为实际访问次数
                actual_visits = recommended_moves[0].get('visits', 0)

            # 构建显示文本
            # 第一行：基本参数
            config_items = [
                ("V", visits),
                ("T", f"{thinking_time}s")
            ]

            # 添加实际visits数量（如果有）
            if actual_visits > 0:
                config_items.append(("实际V", actual_visits))

            # 添加关键KataGo参数（目数权重、胜率权重、探索参数）
            if katago_config:
                # 胜率权重和目数权重
                wl = katago_config.get('winLossUtilityFactor', '-')
                dsu = katago_config.get('dynamicScoreUtilityFactor', '-')
                config_items.append(("胜率", wl))
                config_items.append(("目数", dsu))

                # 探索参数
                cpuct = katago_config.get('cpuctExploration', '-')
                config_items.append(("探索", cpuct))

                # 线程数
                threads = katago_config.get('numSearchThreads', '-')
                config_items.append(("线程", threads))

            # 构建文本
            parts = []
            for name, value in config_items:
                parts.append(f"{name}:{value}")
            config_text = " | ".join(parts)

            # 更新底部标签的文本
            if hasattr(self, 'config_label') and self.config_label.winfo_exists():
                self.config_label.config(text=config_text)
        except Exception as e:
            print(f"绘制配置信息失败: {e}")

    def _fetch_katago_config(self):
        """从服务器获取KataGo配置"""
        try:
            resp = requests.get(f"{self.config['server_url']}/katago/config", timeout=3)
            if resp.status_code == 200:
                self._katago_config_cache = resp.json()
                print(f"[Config] 获取KataGo配置成功")
            else:
                self._katago_config_cache = {}
        except Exception as e:
            print(f"[Config] 获取KataGo配置失败: {e}")
            self._katago_config_cache = {}

    def _draw_board_background(self):
        """绘制棋盘背景（只执行一次）"""
        board_size = 19
        canvas_size = 480
        margin = 25
        cell_size = (canvas_size - 2 * margin) / (board_size - 1)

        # 绘制网格和坐标
        grid_color = '#555555'
        for i in range(board_size):
            x = margin + i * cell_size
            y = margin + i * cell_size
            self.board_canvas.create_line(margin, y, canvas_size - margin, y, fill=grid_color, width=0.5, tags="bg")
            self.board_canvas.create_line(x, margin, x, canvas_size - margin, fill=grid_color, width=0.5, tags="bg")

            col_char = chr(ord('A') + i)
            if i >= 8:
                col_char = chr(ord('A') + i + 1)
            self.board_canvas.create_text(x, margin - 10, text=col_char, font=('Arial', 8), fill=grid_color, tags="bg")
            self.board_canvas.create_text(x, canvas_size - margin + 10, text=col_char, font=('Arial', 8), fill=grid_color, tags="bg")

            row_num = str(19 - i)
            self.board_canvas.create_text(margin - 10, y, text=row_num, font=('Arial', 8), fill=grid_color, tags="bg")
            self.board_canvas.create_text(canvas_size - margin + 10, y, text=row_num, font=('Arial', 8), fill=grid_color, tags="bg")

        # 绘制星位
        star_points = [(3, 3), (3, 9), (3, 15), (9, 3), (9, 9), (9, 15), (15, 3), (15, 9), (15, 15)]
        for col, row in star_points:
            x = margin + col * cell_size
            y = margin + row * cell_size
            r = 3
            self.board_canvas.create_oval(x-r, y-r, x+r, y+r, fill=grid_color, outline=grid_color, tags="bg")
        
    def _check_server(self):
        """检查服务端连接并获取模型列表和配置"""
        def check():
            try:
                # 检查健康状态
                resp = requests.get(f"{self.config['server_url']}/health", timeout=5)
                if resp.status_code == 200 and resp.json().get('katago_ready'):
                    # 更新Logo右下角状态指示器为亮绿色
                    self.root.after(0, lambda: self.logo_canvas.itemconfig(self.status_circle, fill='#00E676'))
                    # 获取模型列表
                    self._fetch_models()
                    # 获取KataGo配置
                    self._fetch_katago_config()
                else:
                    # 更新Logo右下角状态指示器为红色
                    self.root.after(0, lambda: self.logo_canvas.itemconfig(self.status_circle, fill='#F44336'))
            except:
                # 更新Logo右下角状态指示器为红色
                self.root.after(0, lambda: self.logo_canvas.itemconfig(self.status_circle, fill='#F44336'))
        threading.Thread(target=check, daemon=True).start()
        
    def _fetch_models(self):
        """从服务端获取可用模型列表"""
        try:
            resp = requests.get(f"{self.config['server_url']}/models", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.available_models = data.get('models', [])
                self.current_model = data.get('current')
                print(f"[模型] 可用模型: {[m['display'] for m in self.available_models]}")
                print(f"[模型] 当前模型: {self.current_model}")
        except Exception as e:
            print(f"[模型] 获取模型列表失败：{e}")

    def _fetch_katago_config(self):
        """从服务端获取KataGo配置参数"""
        try:
            resp = requests.get(f"{self.config['server_url']}/katago/config", timeout=5)
            if resp.status_code == 200:
                self.katago_config = resp.json()
                print(f"[配置] KataGo参数: {self.katago_config}")
        except Exception as e:
            print(f"[配置] 获取KataGo配置失败：{e}")
            self.katago_config = {}

    def _start_connection_monitor(self):
        """启动连接状态自动更新（每5秒检查一次）"""
        self._check_server()
        # 每5秒自动更新连接状态
        self.root.after(5000, self._start_connection_monitor)
    
    def _create_canvas_save_button(self, parent, command):
        """创建 Canvas 保存按钮"""
        btn_frame = tk.Frame(parent, bg=self.COLORS['background'], cursor="hand2")
        
        canvas = tk.Canvas(
            btn_frame,
            width=100,
            height=32,
            bg=self.COLORS['background'],
            highlightthickness=0
        )
        canvas.pack()
        
        button_text = t('save_settings')
        font = self.FONTS['body_bold']
        is_disabled = [False]
        
        def draw_button(state='normal'):
            canvas.delete('all')
            width, height = 100, 32
            radius = 6
            
            if state == 'disabled':
                color = '#CCCCCC'
            elif state == 'active':
                color = self.COLORS['primary_dark']
            else:
                color = self.COLORS['primary']
            
            # 绘制圆角矩形
            canvas.create_arc(
                0, 0, radius * 2, radius * 2,
                start=90, extent=90,
                fill=color, outline=color
            )
            canvas.create_arc(
                width - radius * 2, 0, width, radius * 2,
                start=0, extent=90,
                fill=color, outline=color
            )
            canvas.create_arc(
                0, height - radius * 2, radius * 2, height,
                start=180, extent=90,
                fill=color, outline=color
            )
            canvas.create_arc(
                width - radius * 2, height - radius * 2, width, height,
                start=270, extent=90,
                fill=color, outline=color
            )
            canvas.create_rectangle(
                radius, 0, width - radius, height,
                fill=color, outline=color
            )
            canvas.create_rectangle(
                0, radius, width, height - radius,
                fill=color, outline=color
            )
            
            # 绘制文字
            text_color = '#90EE90' if state != 'disabled' else '#757575'  # 亮绿色
            canvas.create_text(
                width // 2, height // 2,
                text=button_text,
                font=font,
                fill=text_color
            )
        
        # 初始绘制
        btn_frame.after(10, lambda: draw_button('normal'))
        
        # 绑定事件
        def on_enter(e):
            if not is_disabled[0]:
                draw_button('active')
        
        def on_leave(e):
            if not is_disabled[0]:
                draw_button('normal')
        
        def on_click(e):
            if not is_disabled[0]:
                draw_button('active')
                if command:
                    command()
        
        def on_release(e):
            if not is_disabled[0]:
                draw_button('normal')
        
        canvas.bind('<Enter>', on_enter)
        canvas.bind('<Leave>', on_leave)
        canvas.bind('<Button-1>', on_click)
        canvas.bind('<ButtonRelease-1>', on_release)
        btn_frame.bind('<Enter>', on_enter)
        btn_frame.bind('<Leave>', on_leave)
        btn_frame.bind('<Button-1>', on_click)
        btn_frame.bind('<ButtonRelease-1>', on_release)
        
        return btn_frame
    
    def _create_canvas_small_button(self, parent, button_text, command):
        """创建小型 Canvas 按钮（用于 Browse、Switch 等）"""
        btn_frame = tk.Frame(parent, bg=self.COLORS['card'], cursor="hand2")
        
        # 根据文字长度动态计算宽度（每个字符约 8 像素 + 边距）
        text_width = len(button_text) * 10 + 20
        width = max(70, text_width)
        height = 28
        
        canvas = tk.Canvas(
            btn_frame,
            width=width,
            height=height,
            bg=self.COLORS['card'],
            highlightthickness=0
        )
        canvas.pack()
        
        font = self.FONTS['small']
        is_disabled = [False]
        
        def draw_button(state='normal'):
            canvas.delete('all')
            radius = 5
            
            if state == 'disabled':
                bg_color = '#CCCCCC'
                text_color = '#757575'
            elif state == 'active':
                bg_color = self.COLORS['primary_dark']
                text_color = '#90EE90'  # 亮绿色
            else:
                bg_color = self.COLORS['primary']
                text_color = '#90EE90'  # 亮绿色
            
            # 绘制圆角矩形
            canvas.create_arc(
                0, 0, radius * 2, radius * 2,
                start=90, extent=90,
                fill=bg_color, outline=bg_color
            )
            canvas.create_arc(
                width - radius * 2, 0, width, radius * 2,
                start=0, extent=90,
                fill=bg_color, outline=bg_color
            )
            canvas.create_arc(
                0, height - radius * 2, radius * 2, height,
                start=180, extent=90,
                fill=bg_color, outline=bg_color
            )
            canvas.create_arc(
                width - radius * 2, height - radius * 2, width, height,
                start=270, extent=90,
                fill=bg_color, outline=bg_color
            )
            canvas.create_rectangle(
                radius, 0, width - radius, height,
                fill=bg_color, outline=bg_color
            )
            canvas.create_rectangle(
                0, radius, width, height - radius,
                fill=bg_color, outline=bg_color
            )
            
            # 绘制文字
            canvas.create_text(
                width // 2, height // 2,
                text=button_text,
                font=font,
                fill=text_color
            )
        
        # 初始绘制
        btn_frame.after(10, lambda: draw_button('normal'))
        
        # 绑定事件
        def on_enter(e):
            if not is_disabled[0]:
                draw_button('active')
        
        def on_leave(e):
            if not is_disabled[0]:
                draw_button('normal')
        
        def on_click(e):
            if not is_disabled[0]:
                draw_button('active')
                if command:
                    command()
        
        def on_release(e):
            if not is_disabled[0]:
                draw_button('normal')
        
        canvas.bind('<Enter>', on_enter)
        canvas.bind('<Leave>', on_leave)
        canvas.bind('<Button-1>', on_click)
        canvas.bind('<ButtonRelease-1>', on_release)
        btn_frame.bind('<Enter>', on_enter)
        btn_frame.bind('<Leave>', on_leave)
        btn_frame.bind('<Button-1>', on_click)
        btn_frame.bind('<ButtonRelease-1>', on_release)
        
        return btn_frame
        
    def _open_config(self):
        """打开配置窗口 - 弹出式模态对话框设计"""
        dialog = tk.Toplevel(self.root)
        dialog.title(t('config_title'))
        dialog.geometry("440x550")
        dialog.configure(bg=self.COLORS['background'])
        
        # 设置为模态对话框（macOS 上避免与 topmost 一起使用 grab_set）
        dialog.transient(self.root)  # 设置父窗口
        
        # macOS 上 grab_set 与 topmost 一起使用会导致崩溃
        # 只在 Windows 上使用 grab_set
        if getattr(self, 'is_windows', False):
            dialog.attributes('-topmost', True)
            dialog.grab_set()  # Windows 上可以安全使用模态
        else:
            # macOS 使用替代方案：禁用主窗口控件
            dialog.attributes('-topmost', True)
            self._disable_main_window()
            # 对话框关闭时恢复主窗口
            dialog.protocol("WM_DELETE_WINDOW", lambda: self._on_config_close(dialog))
        
        dialog.update_idletasks()
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        # 右下角位置：屏幕宽度 - 窗口宽度 - 边距，屏幕高度 - 窗口高度 - 边距
        x = screen_width - 440 - 20
        y = screen_height - 550 - 20
        dialog.geometry(f"440x550+{x}+{y}")
        
        # 主容器
        main_container = tk.Frame(dialog, bg=self.COLORS['background'], padx=20, pady=15)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # 标题行（包含齿轮图标、标题和保存按钮）
        title_row = tk.Frame(main_container, bg=self.COLORS['background'])
        title_row.pack(fill=tk.X, pady=(0, 10))
        
        # 齿轮图标 Canvas
        gear_canvas = tk.Canvas(
            title_row,
            width=24,
            height=24,
            bg=self.COLORS['background'],
            highlightthickness=0
        )
        gear_canvas.pack(side=tk.LEFT, padx=(0, 5))
        # 绘制齿轮图标
        cx, cy = 12, 12
        outer_r, inner_r = 9, 5
        num_teeth = 8
        for i in range(num_teeth):
            angle = i * 45
            rad = math.radians(angle)
            rad2 = math.radians(angle + 22.5)
            x1 = cx + inner_r * math.cos(rad)
            y1 = cy + inner_r * math.sin(rad)
            x2 = cx + outer_r * math.cos(rad2)
            y2 = cy + outer_r * math.sin(rad2)
            x3 = cx + inner_r * math.cos(math.radians(angle + 45))
            y3 = cy + inner_r * math.sin(math.radians(angle + 45))
            gear_canvas.create_polygon(x1, y1, x2, y2, x3, y3, fill=self.COLORS['primary'], outline='')
        gear_canvas.create_oval(cx-3, cy-3, cx+3, cy+3, fill=self.COLORS['background'], outline=self.COLORS['primary'], width=1)
        
        # 标题
        title_label = tk.Label(
            title_row,
            text=t('config_title'),
            bg=self.COLORS['background'],
            fg=self.COLORS['primary'],
            font=self.FONTS['large']
        )
        title_label.pack(side=tk.LEFT)

        # 保存按钮容器（先占位，等 save_config 定义后再创建按钮）
        save_btn_container = tk.Frame(title_row, bg=self.COLORS['background'])
        save_btn_container.pack(side=tk.RIGHT)

        # 创建 Canvas 和滚动条
        canvas = tk.Canvas(main_container, bg=self.COLORS['background'], highlightthickness=0)
        scrollbar = tk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=self.COLORS['background'])
        
        frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=frame, anchor="nw", width=380)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        platform_presets = {
            'ogs': {
                'board': (195, 183, 760, 760),
                'monitor': (1200, 380, 160, 30),
                'gbr': 'screenshots/ogs.gpar'
            },
            'tencent': {
                'board': (50, 90, 880, 880),
                'monitor': (1314, 91, 174, 44),
                'gbr': 'screenshots/tx.gpar'
            },
            'fox': {
                'board': (164, 110, 760, 760),
                'monitor': (409, 79, 100, 23),
                'gbr': 'screenshots/yh.gpar'
            },
            'yicheng': {
                'board': (270, 114, 703, 703),
                'monitor': (888, 79, 100, 23),
                'gbr': 'screenshots/yc.gpar'
            }
        }
        
        # 先定义区域变量
        region_vars = []
        monitor_vars = []
        
        # ===== 平台选择卡片 =====
        platform_card = tk.Frame(frame, bg=self.COLORS['card'], padx=15, pady=12)
        platform_card.pack(fill=tk.X, pady=(0, 10))
        platform_card.configure(highlightbackground=self.COLORS['divider'], highlightthickness=1)

        # 标题行
        platform_title_row = tk.Frame(platform_card, bg=self.COLORS['card'])
        platform_title_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(platform_title_row, text="🎮 " + t('platform_preset'), bg=self.COLORS['card'],
                fg=self.COLORS['text_primary'], font=self.FONTS['body_bold']).pack(side=tk.LEFT)

        # 平台选择区域
        platform_frame = tk.Frame(platform_card, bg=self.COLORS['card'])
        platform_frame.pack(fill=tk.X)
        
        platform_var = tk.StringVar(value=self.config.get('platform', 'tencent'))
        
        platform_names = {
            'ogs': t('platform_ogs'),
            'tencent': t('platform_tencent'),
            'fox': t('platform_fox'),
            'yicheng': t('platform_yicheng')
        }
        
        def on_platform_select():
            platform = platform_var.get()
            if platform and platform in platform_presets:
                preset = platform_presets[platform]
                for i, val in enumerate(preset['board']):
                    if i < len(region_vars):
                        region_vars[i].set(str(val))
                for i, val in enumerate(preset['monitor']):
                    if i < len(monitor_vars):
                        monitor_vars[i].set(str(val))
                gbr_entry_var.set(str(Path(__file__).parent / preset['gbr']))
        
        for platform in ['ogs', 'tencent', 'fox', 'yicheng']:
            tk.Radiobutton(
                platform_frame,
                text=platform_names[platform],
                variable=platform_var,
                value=platform,
                bg=self.COLORS['card'],
                fg=self.COLORS['text_primary'],
                selectcolor=self.COLORS['primary'],
                font=self.FONTS['small'],
                command=on_platform_select
            ).pack(side=tk.LEFT, padx=(0, 10))
        
        # ===== 棋盘区域卡片 =====
        board_card = tk.Frame(frame, bg=self.COLORS['card'], padx=15, pady=12)
        board_card.pack(fill=tk.X, pady=(0, 10))
        board_card.configure(highlightbackground=self.COLORS['divider'], highlightthickness=1)

        # 标题行
        board_title_row = tk.Frame(board_card, bg=self.COLORS['card'])
        board_title_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(board_title_row, text="📍 " + t('board_region'), bg=self.COLORS['card'],
                fg=self.COLORS['text_primary'], font=self.FONTS['body_bold']).pack(side=tk.LEFT)

        # 输入区域 - 使用两行网格布局，确保所有字段可见
        region_frame = tk.Frame(board_card, bg=self.COLORS['card'])
        region_frame.pack(fill=tk.X)

        defaults = self.board_region or (0, 0, 0, 0)
        labels = [t('x'), t('y'), t('width'), t('height')]
        
        # 第一行：X, Y
        row1_frame = tk.Frame(region_frame, bg=self.COLORS['card'])
        row1_frame.pack(fill=tk.X, pady=(0, 8))
        
        for i in range(2):
            # 标签
            tk.Label(row1_frame, text=labels[i], bg=self.COLORS['card'],
                    fg=self.COLORS['text_secondary'], font=self.FONTS['small']).pack(side=tk.LEFT, padx=(0, 3))
            var = tk.StringVar(value=str(defaults[i]))
            region_vars.append(var)
            # 输入框
            tk.Entry(row1_frame, textvariable=var, width=10, bg=self.COLORS['background'],
                    fg=self.COLORS['text_primary'], relief=tk.FLAT, highlightbackground=self.COLORS['divider'],
                    highlightthickness=1, justify='center').pack(side=tk.LEFT, padx=(0, 15))
        
        # 第二行：宽, 高
        row2_frame = tk.Frame(region_frame, bg=self.COLORS['card'])
        row2_frame.pack(fill=tk.X)
        
        for i in range(2, 4):
            # 标签
            tk.Label(row2_frame, text=labels[i], bg=self.COLORS['card'],
                    fg=self.COLORS['text_secondary'], font=self.FONTS['small']).pack(side=tk.LEFT, padx=(0, 3))
            var = tk.StringVar(value=str(defaults[i]))
            region_vars.append(var)
            # 输入框
            tk.Entry(row2_frame, textvariable=var, width=10, bg=self.COLORS['background'],
                    fg=self.COLORS['text_primary'], relief=tk.FLAT, highlightbackground=self.COLORS['divider'],
                    highlightthickness=1, justify='center').pack(side=tk.LEFT, padx=(0, 15))
        
        # ===== 监控区域卡片 =====
        monitor_card = tk.Frame(frame, bg=self.COLORS['card'], padx=15, pady=12)
        monitor_card.pack(fill=tk.X, pady=(0, 10))
        monitor_card.configure(highlightbackground=self.COLORS['divider'], highlightthickness=1)

        # 标题行
        monitor_title_row = tk.Frame(monitor_card, bg=self.COLORS['card'])
        monitor_title_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(monitor_title_row, text="👁️ " + t('monitor_region'), bg=self.COLORS['card'],
                fg=self.COLORS['text_primary'], font=self.FONTS['body_bold']).pack(side=tk.LEFT)

        # 输入区域 - 使用两行网格布局，确保所有字段可见
        monitor_frame = tk.Frame(monitor_card, bg=self.COLORS['card'])
        monitor_frame.pack(fill=tk.X)

        defaults = self.monitor_region or (0, 0, 0, 0)
        labels = [t('x'), t('y'), t('width'), t('height')]
        
        # 第一行：X, Y
        row1_frame = tk.Frame(monitor_frame, bg=self.COLORS['card'])
        row1_frame.pack(fill=tk.X, pady=(0, 8))
        
        for i in range(2):
            # 标签
            tk.Label(row1_frame, text=labels[i], bg=self.COLORS['card'],
                    fg=self.COLORS['text_secondary'], font=self.FONTS['small']).pack(side=tk.LEFT, padx=(0, 3))
            var = tk.StringVar(value=str(defaults[i]))
            monitor_vars.append(var)
            # 输入框
            tk.Entry(row1_frame, textvariable=var, width=10, bg=self.COLORS['background'],
                    fg=self.COLORS['text_primary'], relief=tk.FLAT, highlightbackground=self.COLORS['divider'],
                    highlightthickness=1, justify='center').pack(side=tk.LEFT, padx=(0, 15))
        
        # 第二行：宽, 高
        row2_frame = tk.Frame(monitor_frame, bg=self.COLORS['card'])
        row2_frame.pack(fill=tk.X)
        
        for i in range(2, 4):
            # 标签
            tk.Label(row2_frame, text=labels[i], bg=self.COLORS['card'],
                    fg=self.COLORS['text_secondary'], font=self.FONTS['small']).pack(side=tk.LEFT, padx=(0, 3))
            var = tk.StringVar(value=str(defaults[i]))
            monitor_vars.append(var)
            # 输入框
            tk.Entry(row2_frame, textvariable=var, width=10, bg=self.COLORS['background'],
                    fg=self.COLORS['text_primary'], relief=tk.FLAT, highlightbackground=self.COLORS['divider'],
                    highlightthickness=1, justify='center').pack(side=tk.LEFT, padx=(0, 15))
        
        # ===== GBR 参数文件卡片 =====
        gbr_card = tk.Frame(frame, bg=self.COLORS['card'], padx=15, pady=12)
        gbr_card.pack(fill=tk.X, pady=(0, 10))
        gbr_card.configure(highlightbackground=self.COLORS['divider'], highlightthickness=1)

        # 标题行（包含标题和浏览按钮）
        gbr_title_row = tk.Frame(gbr_card, bg=self.COLORS['card'])
        gbr_title_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(gbr_title_row, text="📁 " + t('gbr_params_file'), bg=self.COLORS['card'],
                fg=self.COLORS['text_primary'], font=self.FONTS['body_bold']).pack(side=tk.LEFT)

        # 浏览按钮容器（先占位，等 browse_gbr 定义后再创建）
        browse_btn_container = tk.Frame(gbr_title_row, bg=self.COLORS['card'])
        browse_btn_container.pack(side=tk.LEFT, padx=(10, 0))

        gbr_frame = tk.Frame(gbr_card, bg=self.COLORS['card'])
        gbr_frame.pack(fill=tk.X)

        gbr_entry_var = tk.StringVar(value=self.config.get('gbr_params_file', ''))
        gbr_entry_widget = tk.Entry(gbr_frame, textvariable=gbr_entry_var, font=self.FONTS['body'],
                                   bg=self.COLORS['background'], fg=self.COLORS['text_primary'],
                                   relief=tk.FLAT, highlightbackground=self.COLORS['divider'],
                                   highlightthickness=1)
        gbr_entry_widget.pack(fill=tk.X)
        
        # ===== 模型选择卡片 =====
        model_card = tk.Frame(frame, bg=self.COLORS['card'], padx=15, pady=12)
        model_card.pack(fill=tk.X, pady=(0, 10))
        model_card.configure(highlightbackground=self.COLORS['divider'], highlightthickness=1)

        # 标题行（包含标题和切换按钮）
        model_title_row = tk.Frame(model_card, bg=self.COLORS['card'])
        model_title_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(model_title_row, text="🧠 " + t('katago_model'), bg=self.COLORS['card'],
                fg=self.COLORS['text_primary'], font=self.FONTS['body_bold']).pack(side=tk.LEFT)

        # 切换按钮容器（先占位，等 switch_model 定义后再创建）
        switch_btn_container = tk.Frame(model_title_row, bg=self.COLORS['card'])
        switch_btn_container.pack(side=tk.LEFT, padx=(10, 0))

        model_frame = tk.Frame(model_card, bg=self.COLORS['card'])
        model_frame.pack(fill=tk.X)
        
        model_var = tk.StringVar(value=self.config.get('model_name', self.current_model or ''))
        model_combo = tk.OptionMenu(model_frame, model_var, '')
        model_combo.config(bg=self.COLORS['background'], fg=self.COLORS['text_primary'],
                          font=self.FONTS['body'], relief=tk.FLAT, highlightbackground=self.COLORS['divider'],
                          highlightthickness=1, padx=8, pady=2)
        model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        # 状态标签（先创建，供 switch_model 使用）
        model_status_label = tk.Label(model_frame, text="", bg=self.COLORS['card'], fg="#333333", font=self.FONTS['small'])
        model_status_label.pack(side=tk.LEFT)
        
        # 更新模型列表
        def update_model_list():
            menu = model_combo['menu']
            menu.delete(0, 'end')
            if self.available_models:
                for m in self.available_models:
                    display = m.get('display', m['name'])
                    menu.add_command(label=display, command=lambda v=m['name']: model_var.set(v))
                # 设置当前选中
                if not model_var.get() and self.current_model:
                    model_var.set(self.current_model)
            else:
                menu.add_command(label=t('use_server_default'), command=lambda: model_var.set(''))
        
        update_model_list()
        
        def switch_model():
            """切换模型"""
            selected = model_var.get()
            if not selected:
                return
            try:
                resp = requests.post(
                    f"{self.config['server_url']}/switch_model",
                    json={"model_name": selected},
                    timeout=30
                )
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get('success'):
                        self.current_model = result.get('current')
                        self.config['model_name'] = self.current_model
                        print(f"[模型] 已切换到: {self.current_model}")
                        # 显示成功提示
                        model_status_label.config(text=t('switch_success'), fg="#4CAF50")
                    else:
                        model_status_label.config(text=t('switch_failed'), fg="red")
                else:
                    model_status_label.config(text=t('request_failed'), fg="red")
            except Exception as e:
                print(f"[模型] 切换失败: {e}")
                model_status_label.config(text=t('connection_failed'), fg="red")
        
        # 在占位容器中创建自定义 Canvas 切换按钮
        switch_btn = self._create_canvas_small_button(switch_btn_container, t('switch'), switch_model)
        switch_btn.pack()
        
        # ===== 服务端地址卡片 =====
        server_card = tk.Frame(frame, bg=self.COLORS['card'], padx=15, pady=12)
        server_card.pack(fill=tk.X, pady=(0, 10))
        server_card.configure(highlightbackground=self.COLORS['divider'], highlightthickness=1)

        # 标题行
        server_title_row = tk.Frame(server_card, bg=self.COLORS['card'])
        server_title_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(server_title_row, text="🔗 " + t('server_url'), bg=self.COLORS['card'],
                fg=self.COLORS['text_primary'], font=self.FONTS['body_bold']).pack(side=tk.LEFT)

        server_entry = tk.Entry(server_card, font=self.FONTS['body'], bg=self.COLORS['background'],
                               fg=self.COLORS['text_primary'], relief=tk.FLAT,
                               highlightbackground=self.COLORS['divider'], highlightthickness=1)
        server_entry.pack(fill=tk.X)
        server_entry.insert(0, self.config['server_url'])

        # ===== 语言选择卡片 =====
        lang_card = tk.Frame(frame, bg=self.COLORS['card'], padx=15, pady=12)
        lang_card.pack(fill=tk.X, pady=(0, 10))
        lang_card.configure(highlightbackground=self.COLORS['divider'], highlightthickness=1)

        # 标题行
        lang_title_row = tk.Frame(lang_card, bg=self.COLORS['card'])
        lang_title_row.pack(fill=tk.X, pady=(0, 10))

        tk.Label(lang_title_row, text="🌐 " + t('language'), bg=self.COLORS['card'],
                fg=self.COLORS['text_primary'], font=self.FONTS['body_bold']).pack(side=tk.LEFT)

        language_frame = tk.Frame(lang_card, bg=self.COLORS['card'])
        language_frame.pack(fill=tk.X)

        language_var = tk.StringVar(value=get_language())
        available_langs = get_available_languages()

        for lang_code, lang_name in available_langs.items():
            tk.Radiobutton(
                language_frame,
                text=lang_name,
                variable=language_var,
                value=lang_code,
                bg=self.COLORS['card'],
                fg=self.COLORS['text_primary'],
                selectcolor=self.COLORS['primary'],
                font=self.FONTS['body']
            ).pack(side=tk.LEFT, padx=(0, 15))
        
        def browse_gbr():
            from tkinter import filedialog
            initial_dir = str(Path(__file__).parent / 'screenshots')
            filepath = filedialog.askopenfilename(
                title=t('select_gbr_file'),
                initialdir=initial_dir,
                filetypes=[(t('gbr_filter'), "*.gpar"), (t('all_files'), "*.*")]
            )
            if filepath:
                gbr_entry_var.set(filepath)
        
        # 在占位容器中创建自定义 Canvas 浏览按钮
        browse_btn = self._create_canvas_small_button(browse_btn_container, t('browse'), browse_gbr)
        browse_btn.pack()
        
        # 默认选中腾讯平台并填充参数
        platform_var.set(self.config.get('platform', 'tencent'))
        on_platform_select()
        
        def save_config():
            self.config['server_url'] = server_entry.get()
            self.config['gbr_params_file'] = gbr_entry_var.get() or None
            # 轮巡时自动启用自动落子
            self.config['auto_click'] = self.auto_polling_enabled.get()
            self.config['platform'] = platform_var.get()
            self.config['model_name'] = model_var.get() or None
            
            # 保存语言设置
            new_language = language_var.get()
            language_changed = False
            if new_language != get_language():
                set_language(new_language)
                language_changed = True
            
            try:
                self.board_region = tuple(int(v.get()) for v in region_vars)
                self.monitor_region = tuple(int(v.get()) for v in monitor_vars)
            except:
                pass
                
            self._save_config()
            self._check_server()
            
            # 如果语言改变了，更新主界面文本
            if language_changed:
                self._update_ui_language()
            
            # 关闭对话框（使用统一的关闭处理）
            self._on_config_close(dialog)
        
        # 创建保存按钮（在 save_config 定义后创建，避免闭包问题）
        save_btn = self._create_canvas_save_button(save_btn_container, save_config)
        save_btn.pack()
        
        # Canvas和滚动条布局
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def _show_help(self):
        """显示帮助窗口"""
        help_window = tk.Toplevel(self.root)
        help_window.title("使用说明 | User Guide")
        help_window.geometry("500x600")
        help_window.configure(bg=self.COLORS['background'])
        help_window.attributes('-topmost', True)
        
        # 居中显示
        help_window.update_idletasks()
        screen_width = help_window.winfo_screenwidth()
        screen_height = help_window.winfo_screenheight()
        x = (screen_width - 500) // 2
        y = (screen_height - 600) // 2
        help_window.geometry(f"500x600+{x}+{y}")
        
        # 主容器
        main_frame = tk.Frame(help_window, bg=self.COLORS['background'], padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = tk.Label(
            main_frame,
            text=t('help_title'),
            bg=self.COLORS['background'],
            fg=self.COLORS['primary'],
            font=self.FONTS['title']
        )
        title_label.pack(pady=(0, 20))
        
        # 创建Canvas和滚动条
        canvas = tk.Canvas(main_frame, bg=self.COLORS['background'], highlightthickness=0)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.COLORS['background'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=440)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 帮助内容
        help_sections = self._get_help_content()
        
        for section in help_sections:
            # 卡片容器
            card = tk.Frame(
                scrollable_frame,
                bg=self.COLORS['card'],
                padx=15,
                pady=15
            )
            card.pack(fill=tk.X, pady=(0, 15))
            card.configure(highlightbackground=self.COLORS['divider'], highlightthickness=1)
            
            # 标题
            section_title = tk.Label(
                card,
                text=section["title"],
                bg=self.COLORS['card'],
                fg=self.COLORS['text_primary'],
                font=self.FONTS['heading'],
                justify=tk.LEFT
            )
            section_title.pack(anchor=tk.W, pady=(0, 10))
            
            # 内容
            section_content = tk.Label(
                card,
                text=section["content"],
                bg=self.COLORS['card'],
                fg=self.COLORS['text_secondary'],
                font=self.FONTS['body'],
                justify=tk.LEFT,
                wraplength=400
            )
            section_content.pack(anchor=tk.W)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 关闭按钮
        close_btn = tk.Button(
            main_frame,
            text=t('close'),
            command=help_window.destroy,
            font=self.FONTS['body_bold'],
            bg=self.COLORS['primary'],
            fg="white",
            relief=tk.FLAT,
            padx=30,
            pady=8,
            cursor="hand2"
        )
        close_btn.pack(pady=(10, 0))

    def _get_help_content(self):
        """获取帮助内容（支持多语言）"""
        lang = I18n.get_language()

        if lang == 'en':
            return [
                {
                    "title": "🚀 Quick Start",
                    "content": """1. Start server: run server/start_server.sh
2. Start client: run client/start_client.sh
3. First use: Click ⚙ Config button to set board region
4. Select platform: Tencent/Fox/OGS/Yicheng
5. Select color: Click radio button ◉ to switch B/W
6. Click "Next" to start analysis"""
                },
                {
                    "title": "📡 Connection Status",
                    "content": """The dot at bottom-right of Logo shows server status:
  🟢 Green - Server connected, ready to use
  🔴 Red - Connection failed, check server
  🟡 Yellow - Checking connection

If red, check:
• Is server running? (./start_server.sh)
• Network connection
• Port 8001 available"""
                },
                {
                    "title": "🎯 Main Features",
                    "content": """• Next: Manual analysis of current board
• Auto Play: Polling mode, auto monitor and play
• Board: Show visual analysis (red/green/yellow marks)
• Think Time: AI calculation time (0.5-5s adjustable)
• B/W Switch: Click radio button to switch your color"""
                },
                {
                    "title": "📊 Analysis Results",
                    "content": """• Recommended moves: Top 3 positions with winrate
  Format: Position(Current:Win%)
  Ex: Q16(B:99.8%) means Black 99.8% winrate

• Score lead: From Black's perspective
  [B lead 10.5] or [W lead 8.2]

• Visual Board:
  🔴 Red circle - 1st recommendation
  🟢 Green circle - 2nd recommendation
  🟡 Yellow circle - 3rd recommendation"""
                },
                {
                    "title": "⚙️ Configuration",
                    "content": """• Platform Preset: Auto-load platform-specific params
• Board Region: Screen position of game board (required)
• Monitor Region: Area showing "Black/White to play" (optional)
• GBR Params: Advanced users can adjust recognition
• Language: Chinese/English switch
• Think Time: Longer = more accurate"""
                },
                {
                    "title": "🎮 Tips",
                    "content": """• Must configure board region first
• Polling mode auto-detects whose turn
• Ko fights auto-exclude ko positions
• Supports reconnect without restart
• Click board to see multiple recommendations
• Winrate is from current player's view
• Click radio button ◉ to quickly switch B/W"""
                },
                {
                    "title": "⚠️ Ko Handling",
                    "content": """When ko is detected:
• Shows "⚠️ Ko detected"
• Marks ko position (forbidden)
• Provides 1-3 alternative ko threats
• Auto-selects best threat (polling mode)
• Can recapture after one move"""
                },
                {
                    "title": "🔧 Troubleshooting",
                    "content": """• Connection failed: Check server (port 8001)
• Recognition failed: Reconfigure board region
• Inaccurate moves: Adjust GBR params
• Red status: Check network and server
• Focus issue: Click title bar to activate"""
                },
                {
                    "title": "📞 Support",
                    "content": """Server log: server/katago_server.log
Client log: client/go_client.log

Common issues:
1. Ensure KataGo model is downloaded
2. Check port 8001 availability
3. Verify Python dependencies
4. Check logs for details"""
                }
            ]
        else:  # Chinese (default)
            return [
                {
                    "title": "🚀 快速开始",
                    "content": """1. 启动服务端：运行 server/start_server.sh
2. 启动客户端：运行 client/start_client.sh
3. 首次使用：点击 ⚙ 配置按钮设置棋盘区域
4. 选择平台：腾讯/野狐/OGS/弈城
5. 选择执子颜色：点击 ◉ 单选按钮切换黑/白
6. 点击"下一步"开始分析"""
                },
                {
                    "title": "📡 连接状态指示",
                    "content": """Logo右下角的圆点显示服务器连接状态：
  🟢 绿色 - 服务器连接正常，可以正常使用
  🔴 红色 - 服务器连接失败，请检查服务端
  🟡 黄色 - 正在检查连接状态

如显示红色，请检查：
• 服务端是否已启动（./start_server.sh）
• 网络连接是否正常
• 端口8001是否被占用"""
                },
                {
                    "title": "🎯 主要功能",
                    "content": """• 下一步：手动分析当前棋盘局面
• 自动下棋：轮巡模式，自动监控并落子
• 棋盘：显示可视化分析棋盘（红/绿/黄标记推荐点）
• 思考时间：AI计算时间（0.5-5秒可调）
• 黑/白切换：点击单选按钮切换您执棋的颜色"""
                },
                {
                    "title": "📊 分析结果解读",
                    "content": """• 推荐落子：显示前3个推荐位置及胜率
  格式：位置(当前方:胜率%)
  例：Q16(B:99.8%) 表示黑棋胜率99.8%

• 目数差：黑方视角的领先目数
  [黑领先10.5目] 或 [白领先8.2目]

• 可视化棋盘：
  🔴 红色圆圈 - 第一推荐点
  🟢 绿色圆圈 - 第二推荐点
  🟡 黄色圆圈 - 第三推荐点"""
                },
                {
                    "title": "⚙️ 配置说明",
                    "content": """• 平台预设：自动加载平台特定的棋盘参数
• 棋盘区域：游戏棋盘的屏幕位置（必须配置）
• 监控区域：显示"黑棋下"/"白棋下"的区域（可选）
• GBR参数：高级用户可调整识别参数
• 语言：中文/English 界面切换
• 思考时间：AI分析时长（越长越准确）"""
                },
                {
                    "title": "🎮 使用技巧",
                    "content": """• 首次使用务必先配置棋盘区域
• 轮巡模式下会自动识别轮到谁下
• 打劫时会自动排除劫材位置
• 支持断线重连，无需重启客户端
• 点击棋盘可查看多个推荐点
• 胜率是当前下棋方的胜率
• 点击单选按钮 ◉ 可快速切换黑白"""
                },
                {
                    "title": "⚠️ 打劫处理",
                    "content": """当检测到打劫时：
• 显示"⚠️ 检测到打劫"
• 标记打劫位置（禁止落子）
• 提供1-3个替代劫材位置
• 自动选择最佳劫材（轮巡模式）
• 隔一轮后可正常回提"""
                },
                {
                    "title": "🔧 故障排除",
                    "content": """• 连接失败：检查服务端是否运行（端口8001）
• 识别失败：重新配置棋盘区域，确保棋盘完整可见
• 落子不准：调整GBR参数或重新框选棋盘
• 状态红色：Logo右下角红点，检查网络和服务端
• 焦点问题：点击窗口标题栏激活窗口后再操作控件"""
                },
                {
                    "title": "📞 技术支持",
                    "content": """服务端日志：server/katago_server.log
客户端日志：client/go_client.log

常见问题：
1. 确保KataGo模型文件已下载
2. 检查端口8001是否被占用
3. 确认Python依赖已安装
4. 查看日志文件定位问题"""
                }
            ]

    def run(self):
        """运行"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
        
    def _on_close(self):
        """关闭窗口"""
        self._stop_monitor()
        self._save_config()
        self.root.destroy()


if __name__ == "__main__":
    app = GoClient()
    app.run()
