from dataclasses import dataclass
from core.base_pipeline import *

@dataclass
class RxPipelineConfig(BasePipelineConfig):
    """接收端 Pipeline 配置类"""
    rtmp_url: str
    ndi_name: str
    
    def get_pipeline_description(self) -> str:
        """获取 Pipeline 描述字符串"""
        return (
            f"rtmpsrc location={self.rtmp_url} ! "
            f"flvdemux name=demux "
            f"demux.video ! "
            f"queue name=videoqueue ! "
            f"h264parse ! vtdec_hw name=videodec ! "
            f"videoconvert ! video/x-raw,format=UYVY ! "
            f"queue name=videoqueue2 ! "
            f"ndisinkcombiner name=combiner "
            f"demux.audio ! "
            f"queue name=audioqueue ! "
            f"aacparse ! avdec_aac name=audiodec ! "
            f"audioconvert ! "
            f"audio/x-raw,format=F32LE,channels=2 ! "
            f"queue name=audioqueue2 ! "
            f"combiner. "
            f"combiner. ! ndisink name=ndisink ndi-name={self.ndi_name}"
        )

class RxMessageHandler(BaseMessageHandler):
    """接收端消息处理器"""
    def _handle_state_changed(self, message: Gst.Message) -> bool:
        """处理状态改变消息"""
        if message.src == self.pipeline.pipeline:
            old_state, new_state, pending = message.parse_state_changed()
            self.logger.debug(
                f"Pipeline状态改变: {old_state.value_nick} -> "
                f"{new_state.value_nick} [{pending.value_nick}]"
            )
            if new_state == Gst.State.PLAYING:
                self.logger.info(f"NDI 输出 {self.pipeline.config.ndi_name} 开始正常播放")
            elif new_state == Gst.State.NULL:
                self.logger.info(f"NDI 输出 {self.pipeline.config.ndi_name} 已停止")
        return True

class RxPipeline(BasePipeline):
    """RTMP 转 NDI Pipeline"""
    def __init__(self, config: RxPipelineConfig):
        super().__init__(config)
        
    def _create_message_handler(self) -> RxMessageHandler:
        """创建消息处理器"""
        return RxMessageHandler(self)
        
    def create(self) -> bool:
        """创建并配置 Pipeline"""
        self.logger.info(f"创建 RTMP 转 NDI 管道: {self.config.ndi_name}")
        return super().create()
