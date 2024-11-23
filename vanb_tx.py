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
from core.tx_pipeline import TxPipeline, TxPipelineConfig
from core.scanner import scan_ndi_names

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

def select_ndi_source() -> Optional[str]:
    """让用户选择 NDI 源"""
    logger = logging.getLogger(__name__)
    
    # 扫描 NDI 源
    sources = scan_ndi_names()
    if not sources:
        logger.error("未找到任何 NDI 源")
        return None
        
    # 显示可用的 NDI 源
    print("\n可用的 NDI 源:")
    for i, source in enumerate(sources, 1):
        print(f"{i}. {source}")
        
    # 获取用户选择
    while True:
        try:
            choice = input("\n请选择 NDI 源 (输入序号): ").strip()
            index = int(choice) - 1
            if 0 <= index < len(sources):
                selected = sources[index]
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
        from gi.repository import Gst
        Gst.init(None)
        
        # 获取 GStreamer 版本
        major, minor, micro, nano = Gst.version()
        logger.debug(f"GStreamer 版本: {major}.{minor}.{micro}.{nano}")
        
        while True:
            try:
                # 获取用户选择的 NDI 源
                ndi_source = select_ndi_source()
                if not ndi_source:
                    logger.error("未选择 NDI 源")
                    break
                
                # 获取推流地址
                rtmp_url = get_rtmp_url()
                
                # 创建并运行 Pipeline
                config = TxPipelineConfig(
                    ndi_source=ndi_source,
                    rtmp_url=rtmp_url
                )
                
                pipeline = TxPipeline(config)
                with pipeline.managed_run() as p:
                    p.run()
                
                # 检查是否需要重试
                retry = input("\n是否重试? (y/n): ").lower().strip()
                if retry != 'y':
                    break
                
                logger.info("准备重新启动...")
                time.sleep(2)
                
            except KeyboardInterrupt:
                logger.info("收到用户中断信号")
                break
            except Exception as e:
                logger.error(f"运行出错: {e}")
                retry = input("是否重试? (y/n): ").lower().strip()
                if retry != 'y':
                    break
                time.sleep(2)
                
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
    finally:
        logger.info("程序结束")

if __name__ == "__main__":
    main()