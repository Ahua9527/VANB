import gi
import os
import logging
import time
from typing import Optional, List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GLib

class NDIScanner:
    """NDI 源扫描器"""
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        self._init_gstreamer()

    def _setup_logging(self):
        """配置日志"""
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        if not self.logger.handlers:
            self.logger.setLevel(getattr(logging, log_level))

    def _init_gstreamer(self):
        """初始化 GStreamer"""
        if not Gst.is_initialized():
            Gst.init(None)

    def _create_test_pipeline(self) -> Optional[Gst.Pipeline]:
        """创建测试 Pipeline 以验证 NDI 插件"""
        try:
            pipeline_desc = "ndisrcdemux name=nditest"
            pipeline = Gst.parse_launch(pipeline_desc)
            return pipeline
        except GLib.Error as e:
            self.logger.error(f"无法创建 NDI 测试 pipeline: {e}")
            return None

    def _verify_ndi_plugin(self) -> bool:
        """验证 NDI 插件是否可用"""
        registry = Gst.Registry.get()
        ndi_plugin = registry.find_plugin('ndi')
        
        if not ndi_plugin:
            self.logger.error("未找到 NDI 插件")
            return False
            
        self.logger.debug(f"已找到 NDI 插件: {ndi_plugin.get_filename()}")
        
        # 验证必要的 NDI 元素
        required_elements = ['ndisrc', 'ndisink']
        missing_elements = []
        
        for element in required_elements:
            if not registry.find_feature(element, Gst.ElementFactory):
                missing_elements.append(element)
        
        if missing_elements:
            self.logger.error(f"缺少必要的 NDI 元素: {', '.join(missing_elements)}")
            return False
            
        return True

    def scan_sources(self, timeout_seconds: int = 3) -> Optional[List[str]]:
        """扫描 NDI 源"""
        try:
            # 验证 NDI 插件
            if not self._verify_ndi_plugin():
                return None
                
            # 创建设备监视器
            monitor = Gst.DeviceMonitor()
            
            # 设置 NDI 专用的 caps
            caps = Gst.Caps.from_string("application/x-ndi")
            monitor.add_filter("Video/Source", caps)
            
            # 启动监视器
            if not monitor.start():
                self.logger.error("设备监视器启动失败")
                return None
                
            try:
                # 等待并收集设备
                start_time = time.time()
                devices = []
                
                while time.time() - start_time < timeout_seconds:
                    current_devices = monitor.get_devices()
                    if current_devices:
                        for device in current_devices:
                            name = device.get_display_name()
                            if name not in devices:
                                self.logger.debug(f"发现 NDI 源: {name}")
                                devices.append(name)
                    time.sleep(0.5)
                
                if not devices:
                    self.logger.info(f"在 {timeout_seconds} 秒内未找到 NDI 源")
                else:
                    self.logger.info(f"{timeout_seconds} 秒内找到 {len(devices)} 个 NDI 源")
                    
                return devices
                
            finally:
                monitor.stop()
                
        except Exception as e:
            self.logger.error(f"扫描 NDI 源时发生错误: {e}")
            return None

def scan_ndi_names(timeout_seconds: int = 3) -> Optional[List[str]]:
    """扫描当前网络中的 NDI 源"""
    scanner = NDIScanner()
    return scanner.scan_sources(timeout_seconds)

def main():
    """主函数，用于测试"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("开始扫描 NDI 源...")
    
    try:
        sources = scan_ndi_names()
        if sources is None:
            logger.error("扫描失败")
            return
            
        if not sources:
            logger.debug("未找到任何 NDI 源")
        else:
            # logger.info("找到以下 NDI 源:")
            for source in sources:
                logger.info(f"{source}")
                
    except KeyboardInterrupt:
        logger.info("扫描被用户中断")
    except Exception as e:
        logger.error(f"扫描过程出错: {e}")
    finally:
        logger.info("扫描结束")

if __name__ == "__main__":
    main()