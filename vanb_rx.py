import gi
import os
import logging
import time
import sys
from typing import Optional, List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入核心模块
from core.rx_pipeline import RxPipeline, RxPipelineConfig
from core.scanner import scan_ndi_names

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

def get_sequence_number(ndi_names: List[str]) -> int:
    """获取新的序列号"""
    existing_numbers = set()
    for name in ndi_names:
        if "VANB-Rx-" in name:
            try:
                number = int(name.split("VANB-Rx-")[-1].split(")")[0])
                if number > 0:
                    existing_numbers.add(number)
            except (ValueError, IndexError):
                continue
    
    sequence_number = 1
    while sequence_number in existing_numbers:
        sequence_number += 1
    
    return sequence_number

def verify_ndi_name(ndi_name: str, ndi_names: List[str]) -> bool:
    """验证新生成的 NDI 名称是否有效且不重复"""
    if not ndi_name.startswith("VANB-Rx-"):
        return False
    
    try:
        number = int(ndi_name.split("-")[-1])
        if number <= 0:
            return False
    except ValueError:
        return False
    
    return not any(ndi_name == existing_name for existing_name in ndi_names)

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
        
        # 获取 RTMP URL
        rtmp_url = get_rtmp_url()
        
        while True:
            try:
                # 扫描当前网络中的 NDI 源
                ndi_names = scan_ndi_names()
                if ndi_names is None:
                    ndi_names = []
                    logger.warning("NDI 扫描失败，将使用默认序号")
                
                # 打印扫描到的 NDI 源
                if not ndi_names:
                    logger.debug("未扫描到任何 NDI 源")
                else:
                    for name in ndi_names:
                        logger.info(f"{name}")
                
                # 获取新的序列号
                sequence_number = get_sequence_number(ndi_names)
                new_ndi_name = f"VANB-Rx-{sequence_number}"
                
                # 验证新生成的 NDI 名称
                if not verify_ndi_name(new_ndi_name, ndi_names):
                    raise ValueError(f"无法使用 NDI 名称: {new_ndi_name} (已被占用)")
                
                logger.info(f"将使用新的 NDI 名称: {new_ndi_name}")
                
                # 创建并运行 Pipeline
                config = RxPipelineConfig(
                    rtmp_url=rtmp_url,
                    ndi_name=new_ndi_name
                )
                
                pipeline = RxPipeline(config)
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