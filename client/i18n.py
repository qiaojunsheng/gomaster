#!/usr/bin/env python3
"""
国际化模块 - 支持多语言切换
"""

import json
import os
from pathlib import Path

# 默认语言
DEFAULT_LANGUAGE = 'zh'

# 翻译字典
TRANSLATIONS = {
    'zh': {
        # 窗口标题
        'window_title': '围棋助手 - GoMaster',
        'config_title': '配置',
        
        # 按钮和标签
        'next_step': '下一步',
        'polling': '自动下棋',
        'black': '黑',
        'white': '白',
        'time': '思考时间',
        'board': '棋盘',
        'waiting': '等待',
        'config': '配置',
        'save_settings': '保存设置',
        'browse': '浏览',
        'switch': '切换',
        
        # 状态
        'connecting': '连接中...',
        'connected': '已连接',
        'disconnected': '未连接',
        'waiting_analysis': '等待分析...',
        'analyzing': '分析中...',
        'switch_success': '切换成功',
        'switch_failed': '切换失败',
        'request_failed': '请求失败',
        'connection_failed': '连接失败',
        
        # 配置项
        'platform_preset': '平台预设:',
        'board_region': '棋盘区域 (X, Y, 宽, 高):',
        'monitor_region': '监控区域 (X, Y, 宽, 高):',
        'gbr_params_file': 'GBR参数文件:',
        'katago_model': 'KataGo 模型:',
        'server_url': '服务端地址:',
        'language': '语言:',
        
        # 平台名称
        'platform_ogs': 'OGS',
        'platform_tencent': '腾讯',
        'platform_fox': '野狐',
        'platform_yicheng': '弈城',
        
        # 坐标标签
        'x': 'X',
        'y': 'Y',
        'width': '宽',
        'height': '高',
        
        # 提示信息
        'use_server_default': '使用服务端默认',
        'select_gbr_file': '选择GBR参数文件',
        'gbr_filter': 'GBR参数文件',
        'all_files': '所有文件',
        
        # 分析结果
        'recommend': '推荐',
        'winrate': '胜率',
        'score_lead': '目差',
        'komi': '贴目',
        'moves': '手',
        
        # 错误信息
        'error_server_not_connected': '错误：服务端未连接',
        'error_no_board_region': '错误：未配置棋盘区域',
        'error_recognition_failed': '错误：棋盘识别失败',
        'error_analysis_failed': '错误：分析失败',
        'error_gbr_not_initialized': '错误：GBR未初始化',
        'error_no_stones_detected': '错误：未检测到棋子',
        
        # Others
        'ko_detected': '检测到打劫',
        'my_turn': '轮到我方',
        'opponent_turn': '轮到对方',
        
        # Analysis results
        'analysis_result': '分析结果：',
        'best_move': '推荐',
        'ko_alt_move': '打劫! 改下',
        'ko_detected_short': '打劫',
        'stones_count': '黑{} 白{}',
        'recommended_moves': '推荐落子：',
        'ko_detected': '检测到打劫：',
        'no_recommendations': '无推荐',
        
        # Monitor
        'monitor_no_text': '[无文字]',
        'monitor_text_prefix': '',
        
        # Errors
        'screenshot_failed': '截图失败',
        'recognition_failed': '识别失败',
        'no_stones_detected': '未识别到棋子',
        
        # Thinking
        'thinking_ko_detected': '检测到打劫可能，等待时间',

        # Score display
        'black_lead': '黑领先{}目',
        'white_lead': '白领先{}目',
        'score_even': '局势均衡',

        # Help
        'help_title': '📖 GoMaster Pro 使用说明',
        'close': '关闭',
    },
    'en': {
        # Window titles
        'window_title': 'GoMaster - Go Assistant',
        'config_title': 'Settings',
        
        # Buttons and labels
        'next_step': 'Next',
        'polling': 'Auto',
        'black': 'B',
        'white': 'W',
        'time': 'Think Time',
        'board': 'Board',
        'waiting': 'Wait',
        'config': 'Config',
        'save_settings': 'Save',
        'browse': 'Browse',
        'switch': 'Switch',
        
        # Status
        'connecting': 'Connecting...',
        'connected': 'Connected',
        'disconnected': 'Disconnected',
        'waiting_analysis': 'Waiting...',
        'analyzing': 'Analyzing...',
        'switch_success': 'Success',
        'switch_failed': 'Failed',
        'request_failed': 'Request Failed',
        'connection_failed': 'Connection Failed',
        
        # Config items
        'platform_preset': 'Platform:',
        'board_region': 'Board Region (X, Y, W, H):',
        'monitor_region': 'Monitor Region (X, Y, W, H):',
        'gbr_params_file': 'GBR Params:',
        'katago_model': 'KataGo Model:',
        'server_url': 'Server URL:',
        'language': 'Language:',
        
        # Platform names
        'platform_ogs': 'OGS',
        'platform_tencent': 'Tencent',
        'platform_fox': 'Fox',
        'platform_yicheng': 'Yicheng',
        
        # Coordinate labels
        'x': 'X',
        'y': 'Y',
        'width': 'W',
        'height': 'H',
        
        # Messages
        'use_server_default': 'Use Server Default',
        'select_gbr_file': 'Select GBR Params File',
        'gbr_filter': 'GBR Files',
        'all_files': 'All Files',
        
        # Analysis results
        'recommend': 'Best',
        'winrate': 'Win%',
        'score_lead': 'Score',
        'komi': 'Komi',
        'moves': 'Moves',
        
        # Error messages
        'error_server_not_connected': 'Error: Server not connected',
        'error_no_board_region': 'Error: Board region not set',
        'error_recognition_failed': 'Error: Recognition failed',
        'error_analysis_failed': 'Error: Analysis failed',
        'error_gbr_not_initialized': 'Error: GBR not initialized',
        'error_no_stones_detected': 'Error: No stones detected',
        
        # Others
        'ko_detected': 'Ko detected',
        'my_turn': 'My Turn',
        'opponent_turn': 'Opponent Turn',
        
        # Analysis results
        'analysis_result': 'Analysis Result:',
        'best_move': 'Best',
        'ko_alt_move': 'Ko! Alt',
        'ko_detected_short': 'Ko',
        'stones_count': 'B:{} W:{}',
        'recommended_moves': 'Best:',
        'ko_detected': 'Ko detected:',
        'no_recommendations': 'No recommendations',
        
        # Monitor
        'monitor_no_text': '[No text]',
        'monitor_text_prefix': '[Monitor]',
        
        # Errors
        'screenshot_failed': 'Screenshot failed',
        'recognition_failed': 'Recognition failed',
        'no_stones_detected': 'No stones detected',
        
        # Thinking
        'thinking_ko_detected': 'Ko detected, waiting time',

        # Score display
        'black_lead': 'B lead {}',
        'white_lead': 'W lead {}',
        'score_even': 'Even',

        # Help
        'help_title': '📖 GoMaster Pro Help',
        'close': 'Close',
    }
}


class I18n:
    """国际化类"""
    
    _instance = None
    _language = DEFAULT_LANGUAGE
    _config_file = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._config_file = Path(__file__).parent / 'i18n_config.json'
            cls._load_language()
        return cls._instance
    
    @classmethod
    def _load_language(cls):
        """从配置文件加载语言设置"""
        try:
            if cls._config_file and cls._config_file.exists():
                with open(cls._config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    cls._language = config.get('language', DEFAULT_LANGUAGE)
        except Exception:
            cls._language = DEFAULT_LANGUAGE
    
    @classmethod
    def _save_language(cls):
        """保存语言设置到配置文件"""
        try:
            if cls._config_file:
                with open(cls._config_file, 'w', encoding='utf-8') as f:
                    json.dump({'language': cls._language}, f, ensure_ascii=False)
        except Exception:
            pass
    
    @classmethod
    def set_language(cls, lang: str):
        """设置语言"""
        if lang in TRANSLATIONS:
            cls._language = lang
            cls._save_language()
    
    @classmethod
    def get_language(cls) -> str:
        """获取当前语言"""
        return cls._language
    
    @classmethod
    def get_available_languages(cls) -> dict:
        """获取可用语言列表"""
        return {
            'zh': '中文',
            'en': 'English'
        }
    
    @classmethod
    def t(cls, key: str, *args) -> str:
        """
        获取翻译文本
        :param key: 翻译键
        :param args: 格式化参数
        :return: 翻译后的文本
        """
        # 获取当前语言的翻译
        translation = TRANSLATIONS.get(cls._language, TRANSLATIONS[DEFAULT_LANGUAGE])
        text = translation.get(key, key)
        
        # 如果当前语言没有翻译，回退到默认语言
        if text == key and cls._language != DEFAULT_LANGUAGE:
            default_translation = TRANSLATIONS[DEFAULT_LANGUAGE]
            text = default_translation.get(key, key)
        
        # 格式化参数
        if args:
            try:
                text = text.format(*args)
            except Exception:
                pass
        
        return text


# 便捷函数
def t(key: str, *args) -> str:
    """获取翻译文本的便捷函数"""
    # 确保实例已创建，从而加载语言配置
    I18n()
    return I18n.t(key, *args)


def set_language(lang: str):
    """设置语言的便捷函数"""
    # 确保实例已创建
    I18n()
    I18n.set_language(lang)


def get_language() -> str:
    """获取当前语言的便捷函数"""
    # 确保实例已创建
    I18n()
    return I18n.get_language()


def get_available_languages() -> dict:
    """获取可用语言列表的便捷函数"""
    return I18n.get_available_languages()
