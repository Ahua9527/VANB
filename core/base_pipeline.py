import gi
import os
import logging
import time
from typing import Optional
from contextlib import contextmanager
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GLib

class PipelineError(Exception):
    """Pipeline 相关错误的基类"""
    pass

class ElementCreationError(PipelineError):
    """元素创建失败错误"""
    pass

class PipelineStateError(PipelineError):
    """Pipeline 状态错误"""
    pass

class BasePipelineConfig:
    """Pipeline 配置基类"""
    def get_pipeline_description(self) -> str:
        """获取 Pipeline 描述字符串"""
        raise NotImplementedError("子类必须实现此方法")

class BaseMessageHandler:
    """GStreamer 消息处理器基类"""
    def __init__(self, pipeline: 'BasePipeline'):
        self.pipeline = pipeline
        self.logger = logging.getLogger(__name__)

    def handle_message(self, _bus, message: Gst.Message) -> bool:
        """处理 GStreamer 总线消息"""
        handlers = {
            Gst.MessageType.EOS: self._handle_eos,
            Gst.MessageType.ERROR: self._handle_error,
            Gst.MessageType.WARNING: self._handle_warning,
            Gst.MessageType.STATE_CHANGED: self._handle_state_changed,
            Gst.MessageType.ELEMENT: self._handle_element,
            Gst.MessageType.QOS: self._handle_qos
        }
        
        handler = handlers.get(message.type)
        if handler:
            return handler(message)
        return True

    def _handle_eos(self, _message: Gst.Message) -> bool:
        """处理流结束消息"""
        self.logger.info("收到流结束信号")
        self.pipeline.stop()
        return False

    def _handle_error(self, message: Gst.Message) -> bool:
        """处理错误消息"""
        err, debug = message.parse_error()
        self.logger.error(f"错误: {err.message}")
        self.logger.debug(f"调试信息: {debug}")
        self.pipeline.stop()
        return False

    def _handle_warning(self, message: Gst.Message) -> bool:
        """处理警告消息"""
        warn, debug = message.parse_warning()
        self.logger.warning(f"警告: {warn.message}")
        self.logger.debug(f"调试信息: {debug}")
        return True

    def _handle_state_changed(self, message: Gst.Message) -> bool:
        """处理状态改变消息"""
        if message.src == self.pipeline.pipeline:
            old_state, new_state, pending = message.parse_state_changed()
            self.logger.debug(
                f"Pipeline状态改变: {old_state.value_nick} -> "
                f"{new_state.value_nick} [{pending.value_nick}]"
            )
        return True

    def _handle_element(self, message: Gst.Message) -> bool:
        """处理元素消息"""
        structure = message.get_structure()
        if structure:
            self.logger.debug(f"元素消息: {structure.get_name()}")
        return True

    def _handle_qos(self, message: Gst.Message) -> bool:
        """处理 QOS 消息"""
        live, running_time, stream_time, timestamp, duration = message.parse_qos()
        self.logger.debug(
            f"QOS: live={live}, running_time={running_time}, "
            f"stream_time={stream_time}, timestamp={timestamp}, duration={duration}"
        )
        return True

class BasePipeline:
    """GStreamer Pipeline 基类"""
    def __init__(self, config: BasePipelineConfig):
        self.config = config
        self.pipeline: Optional[Gst.Pipeline] = None
        self.loop: Optional[GLib.MainLoop] = None
        self.handler: Optional[BaseMessageHandler] = None
        self.logger = logging.getLogger(__name__)

    def create(self) -> bool:
        """创建并配置 Pipeline"""
        try:
            # 创建 pipeline
            self.pipeline = Gst.parse_launch(self.config.get_pipeline_description())
            if not self.pipeline:
                raise ElementCreationError("无法创建 Pipeline")
            
            # 设置消息处理
            self.handler = self._create_message_handler()
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect('message', self.handler.handle_message)
            
            # 创建主循环
            self.loop = GLib.MainLoop()
            return True
            
        except GLib.Error as e:
            self.logger.error(f"创建管道失败: {e.message}")
            return False
        except Exception as e:
            self.logger.error(f"创建管道时发生未知错误: {e}")
            return False

    def _create_message_handler(self) -> BaseMessageHandler:
        """创建消息处理器"""
        return BaseMessageHandler(self)

    def start(self) -> bool:
        """启动 Pipeline"""
        if not self.pipeline:
            raise PipelineError("Pipeline 未创建")
        
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            raise PipelineStateError("无法将管道设置为播放状态")
        return True

    def stop(self):
        """停止 Pipeline"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            
        if self.loop and self.loop.is_running():
            self.loop.quit()

    def run(self):
        """运行主循环"""
        if not self.loop:
            raise PipelineError("主循环未创建")
            
        try:
            self.loop.run()
        except KeyboardInterrupt:
            self.logger.info("收到用户中断信号")
        except Exception as e:
            self.logger.error(f"运行主循环时发生错误: {e}")
        finally:
            self.stop()

    @contextmanager
    def managed_run(self):
        """使用上下文管理器运行 Pipeline"""
        try:
            if not self.create():
                raise PipelineError("Pipeline 创建失败")
            if not self.start():
                raise PipelineError("Pipeline 启动失败")
            yield self
        finally:
            self.stop()
