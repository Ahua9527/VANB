# core/interfaces.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

@dataclass
class PipelineStats:
    """Pipeline统计信息"""
    running_time: float = 0.0
    frame_drops: int = 0
    current_bitrate: float = 0.0
    error_count: int = 0
    state: str = "STOPPED"

class IPipeline(ABC):
    """Pipeline接口定义"""
    
    @abstractmethod
    def create(self) -> bool:
        """创建Pipeline"""
        pass
        
    @abstractmethod
    def start(self) -> bool:
        """启动Pipeline"""
        pass
        
    @abstractmethod
    def stop(self) -> None:
        """停止Pipeline"""
        pass
        
    @abstractmethod
    def verify_stream(self) -> bool:
        """验证流状态"""
        pass
        
    @abstractmethod
    def get_stats(self) -> PipelineStats:
        """获取Pipeline统计信息"""
        pass
        
    @abstractmethod
    def run(self) -> None:
        """运行Pipeline主循环"""
        pass

class IPipelineConfig(ABC):
    """Pipeline配置接口"""
    
    @abstractmethod
    def validate(self) -> bool:
        """验证配置是否有效"""
        pass
        
    @abstractmethod
    def get_pipeline_description(self) -> str:
        """获取Pipeline描述字符串"""
        pass

class IPipelineFactory(ABC):
    """Pipeline工厂接口"""
    
    @abstractmethod
    def create_pipeline(self, config: Dict[str, Any]) -> Optional[IPipeline]:
        """
        创建Pipeline实例
        
        Args:
            config: Pipeline配置参数
            
        Returns:
            Optional[IPipeline]: 创建的Pipeline实例，失败则返回None
        """
        pass

class IPipelineLifecycle(ABC):
    """Pipeline生命周期管理接口"""
    
    @abstractmethod
    def pre_start(self) -> bool:
        """Pipeline启动前的准备工作"""
        pass
        
    @abstractmethod
    def post_start(self) -> None:
        """Pipeline启动后的处理"""
        pass
        
    @abstractmethod
    def pre_stop(self) -> None:
        """Pipeline停止前的处理"""
        pass
        
    @abstractmethod
    def post_stop(self) -> None:
        """Pipeline停止后的清理工作"""
        pass
        
    @abstractmethod
    def handle_error(self, error: Exception) -> bool:
        """
        处理Pipeline运行时错误
        
        Returns:
            bool: 是否需要重试
        """
        pass

class AbstractPipelineFactory:
    """Pipeline工厂抽象基类"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._pipeline_types: Dict[str, type] = {}
        
    def register_pipeline(self, name: str, pipeline_class: type) -> None:
        """注册Pipeline类型"""
        self._pipeline_types[name] = pipeline_class
        self.logger.debug(f"注册Pipeline类型: {name}")
        
    def create_pipeline(self, pipeline_type: str, config: Dict[str, Any]) -> Optional[IPipeline]:
        """
        创建Pipeline实例
        
        Args:
            pipeline_type: Pipeline类型名称
            config: 配置参数
            
        Returns:
            Optional[IPipeline]: 创建的Pipeline实例
        """
        pipeline_class = self._pipeline_types.get(pipeline_type)
        if not pipeline_class:
            self.logger.error(f"未知的Pipeline类型: {pipeline_type}")
            return None
            
        try:
            pipeline = pipeline_class(config)
            self.logger.info(f"创建Pipeline实例: {pipeline_type}")
            return pipeline
        except Exception as e:
            self.logger.error(f"创建Pipeline失败: {e}")
            return None

class AbstractPipelineLifecycle:
    """Pipeline生命周期管理抽象基类"""
    
    def __init__(self, pipeline: IPipeline):
        self.pipeline = pipeline
        self.logger = logging.getLogger(__name__)
        
    def pre_start(self) -> bool:
        """Pipeline启动前的准备工作"""
        try:
            self.logger.info("执行Pipeline启动前检查...")
            return True
        except Exception as e:
            self.logger.error(f"启动前检查失败: {e}")
            return False
            
    def post_start(self) -> None:
        """Pipeline启动后的处理"""
        self.logger.info("Pipeline启动完成")
        
    def pre_stop(self) -> None:
        """Pipeline停止前的处理"""
        self.logger.info("准备停止Pipeline...")
        
    def post_stop(self) -> None:
        """Pipeline停止后的清理工作"""
        self.logger.info("Pipeline已停止，执行清理...")
        
    def handle_error(self, error: Exception) -> bool:
        """处理Pipeline运行时错误"""
        self.logger.error(f"Pipeline运行错误: {error}")
        return False  # 默认不重试