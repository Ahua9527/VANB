# vanb_rx.py
import subprocess
from venv import logger
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

# def verify_environment() -> bool:
#     """验证运行环境"""
#     required_vars = {
#         'GST_PLUGIN_PATH': '/Library/NDI SDK for Apple/lib/macOS',
#         'DYLD_LIBRARY_PATH': '/Library/NDI SDK for Apple/lib/macOS',
#         'GI_TYPELIB_PATH': '/opt/homebrew/lib/girepository-1.0'
#     }
    
#     missing_vars = []
#     for var, path in required_vars.items():
#         current = os.environ.get(var, '')
#         if not current:
#             missing_vars.append(var)
#         elif path not in current:
#             os.environ[var] = f"{path}:{current}"
    
#     if missing_vars:
#         print("错误: 缺少必要的环境变量:")
#         for var in missing_vars:
#             print(f"  - {var}")
#         return False
    
#     return True

def get_homebrew_prefix() -> str:
    """动态获取Homebrew安装路径"""
    try:
        result = subprocess.run(['brew', '--prefix'], 
                               capture_output=True, 
                               text=True,
                               check=True)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return '/opt/homebrew'  # M系列芯片默认路径

def verify_environment() -> bool:
    """改进后的环境验证"""
    brew_prefix = get_homebrew_prefix()
    required_paths = {
        'GST_PLUGIN_PATH': [
            '/Library/NDI SDK for Apple/lib/macOS',
            f'{brew_prefix}/lib/gstreamer-1.0'
        ],
        'DYLD_LIBRARY_PATH': [
            '/Library/NDI SDK for Apple/lib/macOS',
            '/usr/local/lib'
        ],
        'GI_TYPELIB_PATH': [
            f'{brew_prefix}/lib/girepository-1.0',
            '/usr/local/lib/girepository-1.0'
        ]
    }
    
    # 验证路径存在性
    missing_dirs = []
    for var, paths in required_paths.items():
        existing_dirs = [p for p in paths if os.path.exists(p)]
        if not existing_dirs:
            missing_dirs.append(f"{var}: {', '.join(paths)}")
            continue
            
        current = os.environ.get(var, '').split(':')
        for d in existing_dirs:
            if d not in current:
                current.insert(0, d)
        os.environ[var] = ':'.join(current)
    
    if missing_dirs:
        logger.error("关键路径缺失:\n%s", "\n".join(missing_dirs))
        return False
    return True


def get_rtmp_url() -> str:
    """获取 RTMP URL 输入"""
    while True:
        try:
            rtmp_url = input("请输入 RTMP 播放源 URL: ").strip()
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
        from gi.repository import Gst, GLib
        Gst.init(None)
        
        # 获取 GStreamer 版本
        major, minor, micro, nano = Gst.version()
        logger.debug(f"GStreamer 版本: {major}.{minor}.{micro}.{nano}")
        
        # 创建Pipeline管理器
        pipeline_manager = PipelineManager()
        
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