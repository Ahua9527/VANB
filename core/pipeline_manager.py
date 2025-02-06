# core/pipeline_manager.py
import logging
from typing import Optional, Dict, Any
from enum import Enum, auto
from dataclasses import dataclass

from .ndi_manager import NDIManager
from .base_pipeline import BasePipeline
from .rx_pipeline import RxPipeline, RxPipelineConfig
from .tx_pipeline import TxPipeline, TxPipelineConfig

class PipelineMode(Enum):
    """Pipeline运行模式"""
    TRANSMIT = auto()  # NDI转RTMP
    RECEIVE = auto()   # RTMP转NDI

@dataclass
class PipelineStats:
    """Pipeline统计信息"""
    mode: PipelineMode
    running_time: float = 0
    frame_drops: int = 0
    current_bitrate: float = 0
    error_count: int = 0

class PipelineManager:
    """Pipeline管理器，用于统一管理Pipeline的创建、运行和监控"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.ndi_manager = NDIManager()
        self._current_pipeline: Optional[BasePipeline] = None
        self._stats = PipelineStats(mode=PipelineMode.RECEIVE)

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
            if self._current_pipeline:
                self.stop_pipeline()

            # 根据模式创建Pipeline
            if mode == PipelineMode.TRANSMIT:
                return self._start_tx_pipeline(**kwargs)
            elif mode == PipelineMode.RECEIVE:
                return self._start_rx_pipeline(**kwargs)
            else:
                raise ValueError(f"不支持的Pipeline模式: {mode}")

        except Exception as e:
            self.logger.error(f"启动Pipeline失败: {e}")
            return False

    def _start_tx_pipeline(self, rtmp_url: str, **kwargs) -> bool:
        """启动发送端Pipeline"""
        try:
            # 扫描并选择NDI源
            sources = self.ndi_manager.scan_sources()
            if not sources:
                self.logger.error("未找到任何NDI源")
                return False

            # 如果没有指定源，使用第一个活跃的源
            ndi_source = kwargs.get('ndi_source')
            if not ndi_source:
                active_sources = [s for s in sources if s.is_active]
                if not active_sources:
                    self.logger.error("未找到活跃的NDI源")
                    return False
                ndi_source = active_sources[0].name

            # 创建配置
            config = TxPipelineConfig(
                ndi_source=ndi_source,
                rtmp_url=rtmp_url,
                video_bitrate=kwargs.get('video_bitrate', 2000),
                audio_bitrate=kwargs.get('audio_bitrate', 128000),
                video_format=kwargs.get('video_format', 'I420'),
                audio_rate=kwargs.get('audio_rate', 44100),
                audio_channels=kwargs.get('audio_channels', 2)
            )

            # 创建并启动Pipeline
            self._current_pipeline = TxPipeline(config)
            self._stats.mode = PipelineMode.TRANSMIT
            
            with self._current_pipeline.managed_run() as pipeline:
                self.logger.info(f"发送端Pipeline启动成功: {ndi_source} -> {rtmp_url}")
                pipeline.run()
                
            return True

        except Exception as e:
            self.logger.error(f"启动发送端Pipeline失败: {e}")
            return False

    def _start_rx_pipeline(self, rtmp_url: str, **kwargs) -> bool:
        """启动接收端Pipeline"""
        try:
            # 生成唯一的NDI名称
            prefix = kwargs.get('prefix', 'VANB-Rx')
            ndi_name = self.ndi_manager.generate_unique_name(prefix)

            # 创建配置
            config = RxPipelineConfig(
                rtmp_url=rtmp_url,
                ndi_name=ndi_name
            )

            # 创建并启动Pipeline
            self._current_pipeline = RxPipeline(config)
            self._stats.mode = PipelineMode.RECEIVE
            
            with self._current_pipeline.managed_run() as pipeline:
                self.logger.info(f"接收端Pipeline启动成功: {rtmp_url} -> {ndi_name}")
                pipeline.run()
                
            return True

        except Exception as e:
            self.logger.error(f"启动接收端Pipeline失败: {e}")
            return False

    def stop_pipeline(self) -> bool:
        """
        停止当前运行的Pipeline
        
        Returns:
            bool: 是否成功停止
        """
        try:
            if self._current_pipeline:
                self._current_pipeline.stop()
                self._current_pipeline = None
                self.logger.info("Pipeline已停止")
            return True
        except Exception as e:
            self.logger.error(f"停止Pipeline失败: {e}")
            return False

    def get_stats(self) -> PipelineStats:
        """
        获取Pipeline运行统计信息
        
        Returns:
            PipelineStats: 统计信息
        """
        return self._stats

    def is_running(self) -> bool:
        """
        检查Pipeline是否正在运行
        
        Returns:
            bool: 是否正在运行
        """
        return (
            self._current_pipeline is not None and 
            self._current_pipeline.verify_stream()
        )