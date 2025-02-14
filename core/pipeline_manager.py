# core/pipeline_manager.py
import logging
import time
from typing import Optional, Dict, Any
from enum import Enum, auto
from dataclasses import dataclass

from .interfaces import IPipeline, PipelineStats
from .pipeline_factory import PipelineFactory, PipelineLifecycleManager
from .ndi_manager import NDIManager

class PipelineMode(Enum):
    """Pipeline运行模式"""
    TRANSMIT = auto()  # NDI转RTMP
    RECEIVE = auto()   # RTMP转NDI

@dataclass
class PipelineContext:
    """Pipeline运行上下文"""
    mode: PipelineMode
    pipeline: Optional[IPipeline] = None
    lifecycle_manager: Optional[PipelineLifecycleManager] = None
    start_time: float = 0.0
    config: Dict[str, Any] = None

class PipelineManager:
    """改进版Pipeline管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.ndi_manager = NDIManager()
        self.pipeline_factory = PipelineFactory()
        self._context: Optional[PipelineContext] = None
        self._monitoring = False

    def _create_pipeline_config(self, mode: PipelineMode, **kwargs) -> Dict[str, Any]:
        """
        根据模式创建Pipeline配置
        
        Args:
            mode: Pipeline运行模式
            **kwargs: 配置参数
            
        Returns:
            Dict[str, Any]: Pipeline配置字典
        """
        config = {}
        
        if mode == PipelineMode.RECEIVE:
            # 接收模式：RTMP转NDI
            if 'rtmp_url' not in kwargs:
                raise ValueError("接收模式需要提供rtmp_url参数")
                
            # 生成唯一的NDI名称
            prefix = kwargs.get('prefix', 'VANB-Rx')
            ndi_name = self.ndi_manager.generate_unique_name(prefix)
            
            config = {
                'rtmp_url': kwargs['rtmp_url'],
                'ndi_name': ndi_name
            }
            
        elif mode == PipelineMode.TRANSMIT:
            # 发送模式：NDI转RTMP
            if 'rtmp_url' not in kwargs:
                raise ValueError("发送模式需要提供rtmp_url参数")
                
            # 如果没有指定NDI源，使用自动选择
            ndi_source = kwargs.get('ndi_source')
            if not ndi_source:
                sources = self.ndi_manager.scan_sources()
                active_sources = [s for s in sources if s.is_active]
                if not active_sources:
                    raise ValueError("未找到活跃的NDI源")
                ndi_source = active_sources[0].name
                
            config = {
                'ndi_source': ndi_source,
                'rtmp_url': kwargs['rtmp_url'],
                'video_bitrate': kwargs.get('video_bitrate', 2000),
                'audio_bitrate': kwargs.get('audio_bitrate', 128000),
                'video_format': kwargs.get('video_format', 'I420'),
                'audio_rate': kwargs.get('audio_rate', 44100),
                'audio_channels': kwargs.get('audio_channels', 2)
            }
            
        return config

    def start_pipeline(self, mode: PipelineMode, **kwargs) -> bool:
        """
        启动Pipeline
        
        Args:
            mode: Pipeline运行模式
            **kwargs: 配置参数
            
        Returns:
            bool: 是否成功启动
        """
        try:
            # 停止现有Pipeline
            if self._context and self._context.pipeline:
                self.stop_pipeline()
                
            # 创建Pipeline配置
            config = self._create_pipeline_config(mode, **kwargs)
            
            # 创建Pipeline实例
            pipeline_type = 'rx' if mode == PipelineMode.RECEIVE else 'tx'
            pipeline = self.pipeline_factory.create_pipeline(pipeline_type, config)
            
            if not pipeline:
                self.logger.error("Pipeline创建失败")
                return False
                
            # 创建生命周期管理器
            lifecycle_manager = PipelineLifecycleManager(pipeline)
            
            # 更新上下文
            self._context = PipelineContext(
                mode=mode,
                pipeline=pipeline,
                lifecycle_manager=lifecycle_manager,
                start_time=time.time(),
                config=config
            )
            
            # 启动Pipeline
            if not lifecycle_manager.start():
                self.logger.error("Pipeline启动失败")
                return False
                
            # 启动监控
            self._start_monitoring()
            return True
            
        except Exception as e:
            self.logger.error(f"启动Pipeline失败: {e}")
            return False

    def stop_pipeline(self):
        """停止Pipeline"""
        if self._context and self._context.lifecycle_manager:
            try:
                self._monitoring = False
                self._context.lifecycle_manager.stop()
                self._context = None
            except Exception as e:
                self.logger.error(f"停止Pipeline失败: {e}")

    def is_running(self) -> bool:
        """
        检查Pipeline是否正在运行
        
        Returns:
            bool: 是否正在运行
        """
        return (
            self._context is not None and 
            self._context.pipeline is not None and
            self._context.pipeline.verify_stream()
        )

    def get_stats(self) -> Optional[PipelineStats]:
        """
        获取Pipeline运行统计信息
        
        Returns:
            Optional[PipelineStats]: 统计信息
        """
        if not self._context or not self._context.pipeline:
            return None
            
        stats = self._context.pipeline.get_stats()
        stats.running_time = time.time() - self._context.start_time
        return stats

    def _start_monitoring(self):
        """启动Pipeline监控"""
        if self._monitoring:
            return
            
        self._monitoring = True
        
        def monitor():
            if not self._monitoring:
                return False
                
            try:
                if not self.is_running():
                    self.logger.warning("检测到Pipeline已停止运行")
                    if self._context and self._context.lifecycle_manager:
                        # 尝试处理错误
                        if self._context.lifecycle_manager.handle_error(Exception("Pipeline停止运行")):
                            # 需要重试
                            self.logger.info("尝试重启Pipeline...")
                            self._restart_pipeline()
                return True
                    
            except Exception as e:
                self.logger.error(f"监控过程出错: {e}")
                return False
                
        # 使用GLib添加定时器
        from gi.repository import GLib
        GLib.timeout_add_seconds(5, monitor)

    def _restart_pipeline(self):
        """重启Pipeline"""
        if not self._context:
            return
            
        try:
            mode = self._context.mode
            config = self._context.config
            self.stop_pipeline()
            time.sleep(2)  # 等待资源释放
            self.start_pipeline(mode, **config)
        except Exception as e:
            self.logger.error(f"重启Pipeline失败: {e}")

    def get_current_mode(self) -> Optional[PipelineMode]:
        """获取当前Pipeline模式"""
        return self._context.mode if self._context else None

    def get_pipeline_config(self) -> Optional[Dict[str, Any]]:
        """获取当前Pipeline配置"""
        return self._context.config if self._context else None