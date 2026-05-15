# configurations.py


from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from enum import Enum
from instruments import Instruments, find_instruments 
from utils import BinaryDataParser, format_file_size, ProgressIndicator, handle_errors

import logging
import pyvisa

VCC_LIST = [5]
EXCEL_FILE = "RS622_results.xlsx"
current_limit = 0.10

# Timing settings
HtoL = 230  # ns


class ConnectionType(Enum):
    """连接类型"""
    USB = "usb"
    LAN = "lan"
    GPIB = "gpib"
    AUTO = "auto"
   
class ImageFormat(Enum):
    """支持的图片格式"""
    PNG = "png"
    BMP = "bmp"
    JPG = "jpg"
    JPEG = "jpeg"
    TIFF = "tiff"


class ScreenCapture:
    """
    屏幕截图工具
    
    提供示波器屏幕截图的各种功能
    """
    
    def __init__(
        self,
        device: Optional[ScopeDevice] = None,
        config: Optional[CaptureConfig] = None
    ):
        """
        初始化截图工具
        
        Args:
            device: 已连接的示波器设备，如果为None需要后续设置
            config: 截图配置
        """
        self.device = device
        self.config = config or DEFAULT_CONFIG.capture
        self.logger = logging.getLogger("rigol_scope")
        self._parser = BinaryDataParser()
        
        # 确保截图目录存在
        self._ensure_directory()
    
    def _ensure_directory(self) -> None:
        """确保截图目录存在"""
        self.config.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"截图目录: {self.config.screenshot_dir}")
    
    @property
    def is_ready(self) -> bool:
        """是否准备好截图"""
        return self.device is not None
    
    def set_device(self, device: ScopeDevice) -> None:
        """设置/更换设备"""
        self.device = device
    
    def _generate_filename(
        self,
        prefix: str = "screenshot",
        suffix: Optional[str] = None,
        ext: str = "png"
    ) -> str:
        """生成文件名"""
        timestamp = datetime.now().strftime(self.config.timestamp_format)
        if suffix:
            return f"{prefix}_{timestamp}_{suffix}.{ext}"
        return f"{prefix}_{timestamp}.{ext}"
    
    def _save_image(
        self,
        data: bytes,
        filename: str
    ) -> Path:
        """
        保存图片数据
        
        Args:
            data: 图片二进制数据
            filename: 文件名
            
        Returns:
            保存的文件路径
        """
        filepath = self.config.screenshot_dir / filename
        
        # 解析二进制数据
        image_data = self._parser.parse_visa_binary(data)
        
        # 保存文件
        with open(filepath, "wb") as f:
            f.write(image_data)
        
        return filepath
    
    def capture(
        self,
        format: Union[ImageFormat, str] = ImageFormat.PNG,
        filename: Optional[str] = None,
        prefix: str = "screenshot"
    ) -> Optional[Path]:
        """
        捕获屏幕截图
        
        Args:
            format: 图片格式
            filename: 自定义文件名（可选）
            prefix: 文件名前缀
            
        Returns:
            保存的文件路径，失败返回None
        """
        if not self.is_ready:
            self.logger.error("设备未就绪，无法截图")
            return None
        
        # 标准化格式
        if isinstance(format, str):
            try:
                format = ImageFormat(format.lower())
            except ValueError:
                format = ImageFormat.PNG
        
        try:
            self.logger.info(f"正在捕获屏幕 ({format.value}格式)...")

            Instruments().scope.write(":SYSTem:KEY:PRESs MOFF")
            
            # 设置显示数据输出
            original_timeout = self.device.resource.timeout
            self.device.resource.timeout = self.config.capture_timeout
            
            try:
                self.device.write(":DISP:DATA?")
                screen_data = self.device.read_raw()
            finally:
                self.device.resource.timeout = original_timeout
            
            if not screen_data:
                raise CaptureError("未获取到屏幕数据")
            
            # 生成文件名
            if filename is None:
                filename = self._generate_filename(prefix=prefix, ext=format.value)
            
            # 保存图片
            filepath = self._save_image(screen_data, filename)
            file_size = filepath.stat().st_size
            
            self.logger.info(
                f"[OK] Screenshot saved: {filepath.name} ({format_file_size(file_size)})"
            )
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"❌ 截图失败: {e}")
            return None
    
    def quick_save(self) -> Optional[Path]:
        """
        快速保存截图
        
        使用默认PNG格式，文件名带时间戳
        
        Returns:
            保存的文件路径
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"RIGOL_{timestamp}.png"
        return self.capture(format=ImageFormat.PNG, filename=filename)
    
    def batch_capture(
        self,
        count: int = 5,
        interval: float = 2.0,
        format: ImageFormat = ImageFormat.PNG,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Path]:
        """
        批量捕获截图
        
        Args:
            count: 捕获次数
            interval: 间隔时间（秒）
            format: 图片格式
            progress_callback: 进度回调函数，参数为(当前, 总计)
            
        Returns:
            保存的文件路径列表
        """
        if not self.is_ready:
            self.logger.error("设备未就绪，无法截图")
            return []
        
        saved_files: List[Path] = []
        self.logger.info(f"开始批量捕获: {count} 张图片，间隔 {interval} 秒")
        
        progress = ProgressIndicator(count, "批量捕获")
        
        for i in range(count):
            # 生成文件名
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"batch_{i+1:03d}_{timestamp}.{format.value}"
            
            # 捕获
            filepath = self.capture(format=format, filename=filename)
            if filepath:
                saved_files.append(filepath)
            
            # 更新进度
            progress.update()
            if progress_callback:
                progress_callback(i + 1, count)
            
            # 等待间隔
            if i < count - 1:
                time.sleep(interval)
        
        progress.finish(f"完成，共保存 {len(saved_files)} 张图片")
        return saved_files
    
    def capture_with_settings(
        self,
        format: ImageFormat = ImageFormat.PNG,
        invert: bool = False,
        brightness: Optional[int] = None
    ) -> Optional[Path]:
        """
        捕获带显示设置的截图
        
        Args:
            format: 图片格式
            invert: 是否反色
            brightness: 亮度 (0-100)
            
        Returns:
            保存的文件路径
        """
        if not self.is_ready:
            return None
        
        try:
            # 设置反色
            self.device.write(":DISP:INV ON" if invert else ":DISP:INV OFF")
            
            # 设置亮度
            if brightness is not None and 0 <= brightness <= 100:
                self.device.write(f":DISP:BRIG {brightness}")
            
            # 捕获
            return self.capture(format=format)
            
        except Exception as e:
            self.logger.warning(f"设置显示参数失败: {e}，将直接捕获")
            return self.capture(format=format)




class AutoCapture:
    """
    自动截图工具

    ✅ 使用已有 auto-detect 代码
    ✅ 自动识别示波器
    ✅ 自动连接 / 截图 / 断开
    """

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.logger = logging.getLogger("rigol_scope")

    def _connect_scope_auto(self):
        """
        使用已有 auto-detect 逻辑查找并连接示波器
        """
        instruments = find_instruments()

        if "MSO" not in instruments:
            self.logger.error("未检测到示波器 (MSO)")
            return None, None

        scope_res = instruments["MSO"]
        self.logger.info(f"Auto-detected scope: {scope_res}")

        connector = ScopeConnector(self.config.scope)

        try:
            device = connector.connect(resource=scope_res)
            return connector, device
        except Exception as e:
            self.logger.error(f"连接示波器失败: {e}")
            return None, None

    def quick_capture(self) -> Optional[Path]:
        """
        一键截图（自动检测示波器）
        """
        connector, device = self._connect_scope_auto()
        if not device:
            return None

        try:
            capture = ScreenCapture(device, self.config.capture)
            return capture.quick_save()
        finally:
            connector.disconnect()

    def batch_capture(
        self,
        count: int = 5,
        interval: float = 2.0
    ) -> List[Path]:
        """
        一键批量截图（自动检测示波器）
        """
        connector, device = self._connect_scope_auto()
        if not device:
            return []

        try:
            capture = ScreenCapture(device, self.config.capture)
            return capture.batch_capture(count, interval)
        finally:
            connector.disconnect()

@dataclass
class ScopeConfig:
    """示波器连接配置"""
    
    # 超时设置（毫秒）
    timeout: int = 10000
    
    # 读取终止符
    read_termination: str = "\n"
    
    # 写入终止符
    write_termination: str = "\n"
    
    # VISA 库路径（可选）
    visa_library: str = ""
    
    # 自动识别的厂商ID
    vendor_ids: List[str] = field(default_factory=lambda: ["0x1AB1", "0x1AB1"])
    
    # 自动识别的设备关键字
    device_keywords: List[str] = field(default_factory=lambda: ["RIGOL", "DS", "MSO"])
    
    # 连接类型
    connection_type: ConnectionType = ConnectionType.AUTO

@dataclass
class CaptureConfig:
    """截图配置"""
    
    # 默认保存目录
    screenshot_dir: Path = field(default_factory=lambda: Path("oscilloscope_screenshots"))
    
    # 默认图片格式
    default_format: ImageFormat = ImageFormat.PNG
    
    # 文件名时间戳格式
    timestamp_format: str = "%Y%m%d_%H%M%S"
    
    # 批量捕获默认参数
    default_count: int = 5
    default_interval: float = 2.0
    
    # 截图超时（毫秒）
    capture_timeout: int = 5000


@dataclass
class AppConfig:
    """应用配置"""
    
    # 示波器配置
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    
    # 截图配置
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    
    # 调试模式
    debug: bool = False
    
    # 日志级别
    log_level: str = "INFO"


# 预定义配置实例
DEFAULT_CONFIG = AppConfig()



class ScopeDevice:
    """示波器设备封装"""
    
    def __init__(self, resource: MessageBasedResource, idn: str):
        self.resource = resource
        self.idn = idn
        self._info = self._parse_idn(idn)
    
    def _parse_idn(self, idn: str) -> dict:
        """解析设备标识信息"""
        # 格式: 厂商,型号,序列号,固件版本
        parts = idn.split(",")
        return {
            "manufacturer": parts[0] if len(parts) > 0 else "Unknown",
            "model": parts[1] if len(parts) > 1 else "Unknown",
            "serial": parts[2] if len(parts) > 2 else "Unknown",
            "firmware": parts[3] if len(parts) > 3 else "Unknown",
        }
    
    @property
    def manufacturer(self) -> str:
        return self._info["manufacturer"]
    
    @property
    def model(self) -> str:
        return self._info["model"]
    
    @property
    def serial(self) -> str:
        return self._info["serial"]
    
    @property
    def firmware(self) -> str:
        return self._info["firmware"]
    
    def query(self, command: str) -> str:
        """发送查询命令"""
        return self.resource.query(command).strip()
    
    def write(self, command: str) -> None:
        """发送写入命令"""
        self.resource.write(command)
    
    def read_raw(self) -> bytes:
        """读取原始数据"""
        return self.resource.read_raw()
    
    def __repr__(self) -> str:
        return f"<ScopeDevice {self.manufacturer} {self.model} ({self.serial})>"

class ScopeConnector:
    """
    示波器连接器

    职责：
    ✅ 只负责连接 / 断开示波器
    ❌ 不负责扫描或识别设备
    """

    def __init__(self, config: Optional[ScopeConfig] = None):
        self.config = config or ScopeConfig()
        self.logger = logging.getLogger("rigol_scope")
        self._rm: Optional[pyvisa.ResourceManager] = None
        self._device: Optional[ScopeDevice] = None

    @property
    def is_connected(self) -> bool:
        return self._device is not None

    @property
    def device(self) -> Optional[ScopeDevice]:
        return self._device

    def _init_resource_manager(self) -> pyvisa.ResourceManager:
        """
        初始化 VISA ResourceManager
        """
        if self._rm is not None:
            return self._rm

        try:
            # Default VISA backend
            self._rm = pyvisa.ResourceManager()
            self.logger.info("VISA ResourceManager 初始化成功")
            return self._rm
        except Exception as e:
            self.logger.error(f"VISA 初始化失败: {e}")
            raise ScopeConnectionError("无法初始化 VISA 后端")

    def connect(self, resource: str) -> ScopeDevice:
        """
        连接指定的示波器资源

        Args:
            resource: VISA 资源字符串（来自 find_instruments）

        Returns:
            ScopeDevice
        """
        if not resource:
            raise ScopeConnectionError("未提供示波器资源字符串")

        rm = self._init_resource_manager()

        self.logger.info(f"正在连接示波器: {resource}")

        raw = rm.open_resource(resource)
        raw.timeout = self.config.timeout

        if self.config.read_termination:
            raw.read_termination = self.config.read_termination
        if self.config.write_termination:
            raw.write_termination = self.config.write_termination

        idn = raw.query("*IDN?").strip()
        if not idn:
            raise ScopeConnectionError("示波器无响应")

        self.logger.info(f"连接成功: {idn}")

        self._device = ScopeDevice(raw, idn)
        return self._device

    def disconnect(self) -> None:
        """
        断开示波器连接
        """
        if self._device:
            try:
                self._device.resource.close()
                self.logger.info("已断开示波器连接")
            except Exception as e:
                self.logger.warning(f"断开示波器失败: {e}")
            finally:
                self._device = None

    def __enter__(self) -> "ScopeConnector":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def __repr__(self) -> str:
        status = "已连接" if self.is_connected else "未连接"
        return f"<ScopeConnector {status}>"


class ScopeConnectionError(Exception):
    """示波器连接异常"""
    pass


def setup_logging(config: Optional[AppConfig] = None) -> logging.Logger:
    """
    配置日志系统
    
    Args:
        config: 应用配置，如果为None则使用默认配置
        
    Returns:
        配置好的日志记录器
    """
    if config is None:
        #from scope_setup import DEFAULT_CONFIG
        from configurations import DEFAULT_CONFIG
        config = DEFAULT_CONFIG
    
    # 创建日志记录器
    logger = logging.getLogger("rigol_scope")
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    
    # 避免重复添加处理器
    if not logger.handlers:
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if config.debug else logging.INFO)
        
        # 格式化
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger