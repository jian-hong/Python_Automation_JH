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
  
 