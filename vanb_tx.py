# vanb_tx.py
import gi
import os
import logging
import time
import sys
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入核心模块
from core.pipeline_manager import PipelineManager, PipelineMode

def setup_logging() -> logging.Logger:
    """配置日志系统"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('vanb-tx.log')
        ]
    )
    return logging.getLogger(__name__)

def verify_environment() -> bool:
    """验证运行环境"""
    required_vars = {
        'GST_PLUGIN_PATH': '/Library/NDI SDK for Apple/lib/macOS',
        'DYLD_LIBRARY_PATH': '/Library/NDI SDK for Apple/lib/macOS',
        'GI_TYPELIB_PATH': '/opt/homebrew/lib/girepository-1.0'
    }
    
    missing_vars = []
    for var, path in required_vars.items():
        current = os.environ.get(var, '')
        if not current:
            missing_vars.append(var)
        elif path not in current:
            os.environ[var] = f"{path}:{current}"
    
    if missing_vars:
        print("错误: 缺少必要的环境变量:")
        for var in missing_vars:
            print(f"  - {var}")
        return False
    
    return True

def get_rtmp_url() -> str:
    """获取 RTMP 推流地址"""
    while True:
        try:
            rtmp_url = input("请输入 RTMP 推流地址: ").strip()
            if not rtmp_url:
                print("URL 不能为空，请重新输入")
                continue
            if not rtmp_url.startswith("rtmp://"):
                print("请输入有效的 RTMP URL (以 rtmp:// 开头)")
                continue
            return rtmp_url
        except Exception as e:
            print(f"输入错误: {e}")
            print("请重新输入")

def select_ndi_source(pipeline_manager: PipelineManager) -> Optional[str]:
    """让用户选择 NDI 源"""
    logger = logging.getLogger(__name__)
    
    # 扫描 NDI 源
    sources = pipeline_manager.ndi_manager.scan_sources()
    if not sources:
        logger.error("未找到任何 NDI 源")
        return None
        
    # 过滤出活跃的源
    active_sources = [s for s in sources if s.is_active]
    if not active_sources:
        logger.error("未找到活跃的 NDI 源")
        return None
        
    # 显示可用的 NDI 源
    print("\n可用的 NDI 源:")
    for i, source in enumerate(active_sources, 1):
        print(f"{i}. {source.name}")
        
    # 获取用户选择
    while True:
        try:
            choice = input("\n请选择 NDI 源 (输入序号): ").strip()
            index = int(choice) - 1
            if 0 <= index < len(active_sources):
                selected = active_sources[index].name
                logger.info(f"已选择 NDI 源: {selected}")
                return selected
            print("无效的选择，请重试")
        except ValueError:
            print("请输入有效的数字")
        except (KeyboardInterrupt, EOFError):
            return None

def main():
    """主程序入口"""
    try:
        # 设置日志
        logger = setup_logging()
        logger.info("VANB-Tx 初始化...")

        # 验证环境
        if not verify_environment():
            logger.error("环境验证失败")
            return

        # 初始化 GStreamer
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst, GLib
        Gst.init(None)
        
        # 获取 GStreamer 版本
        major, minor, micro, nano = Gst.version()
        logger.debug(f"GStreamer 版本: {major}.{minor}.{micro}.{nano}")
        
        # 创建Pipeline管理器
        pipeline_manager = PipelineManager()
        
        try:
            # 选择 NDI 源
            ndi_source = select_ndi_source(pipeline_manager)
            if not ndi_source:
                logger.error("未选择 NDI 源")
                return
            
            # 获取推流地址
            rtmp_url = get_rtmp_url()
            
            # 启动发送端Pipeline
            success = pipeline_manager.start_pipeline(
                mode=PipelineMode.TRANSMIT,
                rtmp_url=rtmp_url,
                ndi_source=ndi_source,
                # 可选：配置编码参数
                video_bitrate=2000,  # 2Mbps
                audio_bitrate=128000,  # 128kbps
                video_format='I420',
                audio_rate=44100,
                audio_channels=2
            )
            
            if not success:
                logger.error("Pipeline启动失败")
                return
            
            # 创建主循环
            main_loop = GLib.MainLoop()
            
            try:
                # 启动主循环
                main_loop.run()
            except KeyboardInterrupt:
                logger.info("收到用户中断信号")
            finally:
                main_loop.quit()
                
        except KeyboardInterrupt:
            logger.info("收到用户中断信号")
        except Exception as e:
            logger.error(f"运行出错: {e}")
                
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
    finally:
        # 确保停止Pipeline
        if 'pipeline_manager' in locals():
            pipeline_manager.stop_pipeline()
        logger.info("程序结束")

if __name__ == "__main__":
    main()