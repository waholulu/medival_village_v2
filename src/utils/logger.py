import datetime
from enum import Enum
from typing import Any

class LogCategory(Enum):
    SYSTEM = "SYSTEM"
    GAMEPLAY = "GAMEPLAY"
    AI = "AI"
    RENDER = "RENDER"
    INPUT = "INPUT"
    ERROR = "ERROR"

class Logger:
    _instance = None
    _time_manager = None
    _enabled = True  # 控制日志是否输出
    _enabled_categories = None  # None表示所有类别都启用，否则是启用的类别集合

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    @classmethod
    def set_time_manager(cls, time_manager: Any):
        """Injects the TimeManager instance to access current tick."""
        cls._time_manager = time_manager

    @classmethod
    def set_enabled(cls, enabled: bool):
        """启用或禁用日志输出"""
        cls._enabled = enabled

    @classmethod
    def set_enabled_categories(cls, categories: set = None):
        """
        设置启用的日志类别
        Args:
            categories: 启用的类别集合，None表示所有类别都启用
        """
        cls._enabled_categories = categories

    @staticmethod
    def log(category: LogCategory, message: str, tick: int = -1):
        """
        Logs a message with format: [Time][Tick][Category] Message
        If tick is -1 (default), tries to fetch it from TimeManager.
        """
        # 检查是否启用日志
        if not Logger._enabled:
            return
        
        # 检查类别是否启用
        if Logger._enabled_categories is not None and category not in Logger._enabled_categories:
            return
        
        current_tick = tick
        if current_tick == -1:
            if Logger._time_manager:
                current_tick = Logger._time_manager.total_ticks
            else:
                current_tick = 0

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}][Tick:{current_tick}][{category.value}] {message}"
        print(formatted_msg)

    @staticmethod
    def info(message: str, tick: int = -1):
        Logger.log(LogCategory.SYSTEM, message, tick)

    @staticmethod
    def gameplay(message: str, tick: int = -1):
        Logger.log(LogCategory.GAMEPLAY, message, tick)

    @staticmethod
    def error(message: str, tick: int = -1):
        Logger.log(LogCategory.ERROR, message, tick)
        
    @staticmethod
    def debug(message: str, tick: int = -1):
        # Could be filtered out in production
        Logger.log(LogCategory.SYSTEM, f"DEBUG: {message}", tick)
