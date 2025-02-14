# core/pipeline_factory.py
import logging
from typing import Dict, Any, Optional
from .interfaces import (
    AbstractPipelineFactory, 
    IPipeline,
    AbstractPipelineLifecycle
)
from .rx_pipeline import RxPipeline, RxPipelineConfig
from .tx_pipeline import TxPipeline, TxPipelineConfig

class PipelineFactory(AbstractPipelineFactory):
    """具体的Pipeline工厂实现"""
    
    def __init__(self):
        super().__init__()
        # 注册支持的Pipeline类型
        self.register_pipeline('rx', self._create_rx_pipeline)
        self.register_pipeline('tx', self._create_tx_pipeline)
        
    def _create_rx_pipeline(self, config: Dict[str, Any]) -> Optional[IPipeline]:
        """创建接收端Pipeline"""
        try:
            # 验证必要参数
            required_params = {'rtmp_url', 'ndi_name'}
            if not all(param in config for param in required_params):
                missing = required_params - set(config.keys())
                self.logger.error(f"缺少必要参数: {missing}")
                return None
                
            # 创建配置对象
            pipeline_config = RxPipelineConfig(
                rtmp_url=config['rtmp_url'],
                ndi_name=config['ndi_name']
            )
            
            # 创建Pipeline实例
            return RxPipeline(pipeline_config)
            
        except Exception as e:
            self.logger.error(f"创建接收端Pipeline失败: {e}")
            return None
            
    def _create_tx_pipeline(self, config: Dict[str, Any]) -> Optional[IPipeline]:
        """创建发送端Pipeline"""
        try:
            # 验证必要参数
            required_params = {'rtmp_url', 'ndi_source'}
            if not all(param in config for param in required_params):
                missing = required_params - set(config.keys())
                self.logger.error(f"缺少必要参数: {missing}")
                return None
                
            # 创建配置对象
            pipeline_config = TxPipelineConfig(
                ndi_source=config['ndi_source'],
                rtmp_url=config['rtmp_url'],
                video_bitrate=config.get('video_bitrate', 2000),
                audio_bitrate=config.get('audio_bitrate', 128000),
                video_format=config.get('video_format', 'I420'),
                audio_rate=config.get('audio_rate', 44100),
                audio_channels=config.get('audio_channels', 2)
            )
            
            # 创建Pipeline实例
            return TxPipeline(pipeline_config)
            
        except Exception as e:
            self.logger.error(f"创建发送端Pipeline失败: {e}")
            return None

class PipelineLifecycleManager(AbstractPipelineLifecycle):
    """Pipeline生命周期管理器"""
    
    def __init__(self, pipeline: IPipeline):
        super().__init__(pipeline)
        self._retry_count = 0
        self._max_retries = 3
        
    def start(self) -> bool:
        """
        启动Pipeline，包含完整的生命周期管理
        
        Returns:
            bool: 是否成功启动
        """
        try:
            # 执行启动前检查
            if not self.pre_start():
                return False
                
            # 创建并启动Pipeline
            if not self.pipeline.create():
                self.logger.error("Pipeline创建失败")
                return False
                
            if not self.pipeline.start():
                self.logger.error("Pipeline启动失败")
                return False
                
            # 执行启动后处理
            self.post_start()
            return True
            
        except Exception as e:
            self.logger.error(f"Pipeline启动过程出错: {e}")
            return False
            
    def stop(self):
        """停止Pipeline，执行完整的停止流程"""
        try:
            self.pre_stop()
            self.pipeline.stop()
            self.post_stop()
        except Exception as e:
            self.logger.error(f"Pipeline停止过程出错: {e}")
            
    def handle_error(self, error: Exception) -> bool:
        """
        处理Pipeline运行时错误
        
        Args:
            error: 发生的错误
            
        Returns:
            bool: 是否需要重试
        """
        self._retry_count += 1
        
        if self._retry_count > self._max_retries:
            self.logger.error(f"达到最大重试次数({self._max_retries})，停止重试")
            return False
            
        self.logger.warning(f"Pipeline错误，尝试重启 (第{self._retry_count}次重试): {error}")
        return True
        
    def reset_retry_count(self):
        """重置重试计数"""
        self._retry_count = 0