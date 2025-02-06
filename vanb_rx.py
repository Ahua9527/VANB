# vanb_rx.py
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
            logging.FileHandler('vanb-rx.log')
        ]
    )
    return logging.getLogger(__name__)

def verify_environment() -> bool:
    """验证运行环境"""
    required_vars = {
        'GST_PLUGIN_PATH': '/Library/NDI SDK for Apple/lib/macOS',
        'DYLD_LIBRARY_PATH': '/Library/NDI SDK for Apple/lib/macOS',
        'GI_TYPELIB_PATH': '/usr/local/lib/girepository-1.0'
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
    """获取 RTMP URL 输入"""
    while True:
        try:
            rtmp_url = input("请输入 RTMP 源 URL: ").strip()
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

def main():
    """主程序入口"""
    try:
        # 设置日志
        logger = setup_logging()
        logger.info("VANB-Rx 初始化...")

        # 验证环境
        if not verify_environment():
            logger.error("环境验证失败")
            return

        # 初始化 GStreamer
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        Gst.init(None)
        
        # 获取 GStreamer 版本
        major, minor, micro, nano = Gst.version()
        logger.debug(f"GStreamer 版本: {major}.{minor}.{micro}.{nano}")
        
        # 创建Pipeline管理器
        pipeline_manager = PipelineManager()
        
        while True:
            try:
                # 获取 RTMP URL
                rtmp_url = get_rtmp_url()
                
                # 启动接收端Pipeline
                success = pipeline_manager.start_pipeline(
                    mode=PipelineMode.RECEIVE,
                    rtmp_url=rtmp_url,
                    prefix='VANB-Rx'  # 可选：指定NDI名称前缀
                )
                
                if not success:
                    logger.error("Pipeline启动失败")
                    retry = input("是否重试? (y/n): ").lower().strip()
                    if retry != 'y':
                        break
                    continue
                
                # 等待Pipeline运行完成或出错
                while pipeline_manager.is_running():
                    try:
                        # 每5秒获取一次统计信息
                        stats = pipeline_manager.get_stats()
                        logger.debug(
                            f"Pipeline运行状态:\n"
                            f"- 运行时间: {stats.running_time:.1f}秒\n"
                            f"- 丢帧数: {stats.frame_drops}\n"
                            f"- 当前码率: {stats.current_bitrate:.1f}kbps"
                        )
                        time.sleep(5)
                    except KeyboardInterrupt:
                        logger.info("收到用户中断信号")
                        break
                
                # 检查是否需要重试
                retry = input("\n是否重试? (y/n): ").lower().strip()
                if retry != 'y':
                    break
                
                logger.info("准备重新启动...")
                pipeline_manager.stop_pipeline()
                time.sleep(2)
                
            except KeyboardInterrupt:
                logger.info("收到用户中断信号")
                break
            except Exception as e:
                logger.error(f"运行出错: {e}")
                retry = input("是否重试? (y/n): ").lower().strip()
                if retry != 'y':
                    break
                pipeline_manager.stop_pipeline()
                time.sleep(2)
                
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
    finally:
        # 确保停止Pipeline
        if 'pipeline_manager' in locals():
            pipeline_manager.stop_pipeline()
        logger.info("程序结束")

if __name__ == "__main__":
    main()