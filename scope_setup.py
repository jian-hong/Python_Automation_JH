# scope_setup.py
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
from typing import Callable, List, Optional, Union, Generator
from configurations import *
from instruments import find_instruments 
import time
import os
import logging
import sys
import pyvisa

def measure_delay(scope, item, ch1, ch2):
    scope.write(f":MEASure:ITEM {item},CHAN{ch1},CHAN{ch2}")
    time.sleep(1)
    result = scope.query(
        f":MEASure:STATistic:ITEM? AVERages,{item},CHAN{ch1},CHAN{ch2}"
    )
    return float(result)
    
def measure_single(scope, item, ch):
    scope.write(f":MEASure:ITEM {item},CHAN{ch}")
    time.sleep(1)
    result = scope.query(
    f":MEASure:STATistic:ITEM? AVERages,{item},CHAN{ch}"
    )
    return float(result)
    
def scope_setup(scope, time_scale, trig_level):
    scope.write(":AUToscale")
    time.sleep(2)
    scope.write(f"TIMebase:MAIN:SCAle {time_scale}")
    scope.write(":TRIGger:EDGE:SLOPe POSitive")
    scope.write(f":TRIGger:EDGE:LEVel {trig_level}")
    time.sleep(1)
    scope.write(":SYSTem:KEY:PRESs MOFF")

def set_threshold(scope, ch):
    scope.write(f":MEASure:THR:SOURce CHAN{ch}")
    scope.write(":MEASure:SETup:MAX 80")
    scope.write(":MEASure:SETup:MIN 20")
    scope.write(":MEASure:SETup:MID 50")
 

@contextmanager
def connect_scope(
    config: Optional[ScopeConfig] = None,
    auto_disconnect: bool = True
) -> Generator[Optional[ScopeDevice], None, None]:
    """
    示波器连接上下文管理器
    
    使用示例:
        with connect_scope() as scope:
            if scope:
                print(scope.query("*IDN?"))
    
    Args:
        config: 连接配置
        auto_disconnect: 是否自动断开连接
        
    Yields:
        连接的设备对象，连接失败返回None
    """
    connector = ScopeConnector(config)
    device = None
    
    try:
        device = connector.connect()
        yield device
    except ScopeConnectionError as e:
        logging.getLogger("rigol_scope").error(f"连接失败: {e}")
        yield None
    finally:
        if auto_disconnect:
            connector.disconnect()

def screenshot():
    """主程序 - 功能演示"""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    
    print("=" * 60)
    print("普源示波器屏幕截图工具")
    print("=" * 60)
    
    # 使用自动连接
    auto = AutoCapture()
    
    # 示例1: 一键截图
    print("\n1. 快速截图...")
    result = auto.quick_capture()
    if result:
        print(f"   已保存: {result}")


def recover_scope_session(scope, clear: bool = False, run: bool = False) -> None:
    """Clear VISA error state; optionally RUN so the next JPEG is not Cnt=0."""
    try:
        scope.write("*CLS")
    except Exception:
        pass
    if clear:
        try:
            scope.write(":MEASure:CLEar")
        except Exception:
            pass
    if run:
        try:
            scope.write(":RUN")
        except Exception:
            pass


def park_scope_idle(scope, clear: bool = False) -> None:
    """STOP after a test. Do not call this from capture_scope_png."""
    try:
        scope.write(":STOP")
    except Exception:
        pass
    if clear:
        try:
            scope.write(":MEASure:CLEar")
        except Exception:
            pass


def capture_scope_png(scope, filepath, timeout_ms: int = 10000, jpeg_quality: int = 90) -> str:
    """MSO :DISP:DATA? to a file. Leaves the scope RUNning for the next shot.

    jpeg_quality is accepted for callers; Rigol MSO5000 :DISP:DATA? does not take it.
    """
    from pathlib import Path as _P

    from utils import BinaryDataParser

    path = _P(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    old_timeout = getattr(scope, "timeout", None)
    try:
        scope.timeout = int(timeout_ms)
        try:
            scope.write(":SYSTem:KEY:PRESs MOFF")
        except Exception:
            pass
        scope.write(":DISP:DATA?")
        raw = scope.read_raw()
        data = BinaryDataParser.parse_visa_binary(raw)
        path.write_bytes(data)
    finally:
        if old_timeout is not None:
            try:
                scope.timeout = old_timeout
            except Exception:
                pass
    recover_scope_session(scope, run=True)
    return str(path)

  
 