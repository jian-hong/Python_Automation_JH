"""
工具模块 - 日志、异常处理等通用功能
"""

import logging
import sys
from functools import wraps
from typing import Any, Callable, Optional, TypeVar
#from scope_setup import AppConfig, DEFAULT_CONFIG
#from configurations import AppConfig, DEFAULT_CONFIG


# 类型变量
F = TypeVar("F", bound=Callable[..., Any])




def handle_errors(
    error_msg: str = "操作失败",
    raise_exception: bool = False,
    default_return: Any = None
) -> Callable[[F], F]:
    """
    错误处理装饰器
    
    Args:
        error_msg: 错误提示消息
        raise_exception: 是否抛出异常
        default_return: 出错时的默认返回值
        
    Returns:
        装饰器函数
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = logging.getLogger("rigol_scope")
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"{error_msg}: {e}")
                if raise_exception:
                    raise
                return default_return
        return wrapper  # type: ignore
    return decorator


class BinaryDataParser:
    """二进制数据解析工具"""
    
    @staticmethod
    def parse_visa_binary(data: bytes) -> bytes:
        """
        解析 VISA 二进制数据头
        
        VISA 二进制格式: #<digit_count><data_length><data>
        例如: #800000100<100字节数据>
        
        Args:
            data: 原始字节数据
            
        Returns:
            解析后的纯数据部分
            
        Raises:
            ValueError: 数据格式不正确
        """
        if not data:
            raise ValueError("Empty data")
        
        # 检查是否为标准格式（以 # 开头）
        if data[0] == 35:  # '#' 字符
            # 获取长度字段的位数
            header_len_digit = int(chr(data[1]))
            # 获取数据长度
            data_len = int(data[2:2 + header_len_digit])
            # 提取数据部分
            return data[2 + header_len_digit:2 + header_len_digit + data_len]
        
        # 如果不是标准格式，直接返回原始数据
        return data
    
    @staticmethod
    def parse_ieee_block(data: bytes) -> bytes:
        """
        解析 IEEE 488.2 块数据格式
        
        Args:
            data: 原始字节数据
            
        Returns:
            解析后的数据
        """
        if not data:
            return data
        
        # 查找第一个非空白字符
        idx = 0
        while idx < len(data) and data[idx] in (32, 9, 10, 13):  # 空格、制表符、换行
            idx += 1
        
        if idx >= len(data):
            return data
        
        # 检查是否为块数据格式
        if data[idx] == 35:  # '#'
            return BinaryDataParser.parse_visa_binary(data[idx:])
        
        return data[idx:]


class ProgressIndicator:
    """进度指示器"""
    
    def __init__(self, total: int, description: str = "Progress"):
        self.total = total
        self.current = 0
        self.description = description
    
    def update(self, increment: int = 1) -> None:
        """更新进度"""
        self.current += increment
        self._display()
    
    def _display(self) -> None:
        """显示进度"""
        if self.total > 0:
            percentage = (self.current / self.total) * 100
            print(f"\r{self.description}: {self.current}/{self.total} ({percentage:.1f}%)", end="", flush=True)
            if self.current >= self.total:
                print()  # 完成后换行
    
    def finish(self, message: str = "完成") -> None:
        """完成进度显示"""
        print(f"\r{self.description}: {message}")


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小显示
    
    Args:
        size_bytes: 字节数
        
    Returns:
        格式化后的字符串
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def safe_import(module_name: str, package_name: Optional[str] = None) -> Any:
    """
    安全导入模块
    
    Args:
        module_name: 模块名
        package_name: 包名（用于pip安装提示）
        
    Returns:
        导入的模块
        
    Raises:
        ImportError: 导入失败
    """
    try:
        return __import__(module_name)
    except ImportError as e:
        pkg = package_name or module_name
        raise ImportError(
            f"无法导入 {module_name}。请安装: pip install {pkg}"
        ) from e


# =====================================================
# Test Timing Utilities - for measuring parameter test durations
# =====================================================

import time
from contextlib import contextmanager

class TestTimer:
    """Manages test timing for individual test parameters."""
    
    def __init__(self):
        """Initialize the test timer."""
        self._start_time = None
    
    def initial_time(self) -> None:
        """Record the initial/start time of a test parameter.
        
        Call this at the beginning of each parameter test to mark the start.
        """
        self._start_time = time.time() * 1000  # Convert to milliseconds
    
    def final_time(self) -> float:
        """Record the final/end time and return the duration in milliseconds.
        
        Returns:
            float: Duration in milliseconds since initial_time() was called.
                   Returns 0 if initial_time() was not called.
        
        Example:
            timer = TestTimer()
            timer.initial_time()
            # ... perform test measurement ...
            duration_ms = timer.final_time()
            logger.log_test(parameter_name, value, duration_ms=duration_ms)
        """
        if self._start_time is None:
            return 0
        
        end_time = time.time() * 1000  # Convert to milliseconds
        duration_ms = end_time - self._start_time
        self._start_time = None  # Reset for next measurement
        return duration_ms


# Global timer instance for convenience
_global_timer = TestTimer()


def initial_time() -> None:
    """Record the initial/start time of a test parameter.
    
    This is a convenience function that uses a global timer instance.
    Call this at the beginning of each parameter test measurement.
    
    Usage:
        initial_time()
        # ... perform measurement ...
        duration_ms = final_time()
    """
    _global_timer.initial_time()


def final_time() -> float:
    """Record the final/end time and return the duration in milliseconds.
    
    Returns:
        float: Duration in milliseconds since the last initial_time() call.
               Returns 0 if initial_time() was not called.
    
    Usage:
        initial_time()
        # ... perform measurement ...
        duration_ms = final_time()
        logger.log_test(parameter_name, value, duration_ms=duration_ms)
    """
    return _global_timer.final_time()


@contextmanager
def measure_time(parameter_name: str = ""):
    """Context manager for measuring test execution time.
    
    Args:
        parameter_name: Optional name of the parameter being tested.
        
    Yields:
        dict: Dictionary with 'start_time' and 'duration_ms' after context exits.
        
    Example:
        with measure_time("IN_T_O_HL") as timer_info:
            # ... perform test measurement ...
            pass
        duration_ms = timer_info['duration_ms']
        logger.log_test("IN_T_O_HL", value, duration_ms=duration_ms)
    """
    timer_info = {
        'parameter': parameter_name,
        'start_time': time.time() * 1000,
        'end_time': None,
        'duration_ms': 0
    }
    
    try:
        yield timer_info
    finally:
        timer_info['end_time'] = time.time() * 1000
        timer_info['duration_ms'] = timer_info['end_time'] - timer_info['start_time']
