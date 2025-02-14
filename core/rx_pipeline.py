# core/rx_pipeline.py
from dataclasses import dataclass
from core.base_pipeline import *
from core.interfaces import PipelineStats

@dataclass
class RxPipelineConfig(BasePipelineConfig):
    """接收端 Pipeline 配置类"""
    rtmp_url: str
    ndi_name: str
    
    def get_pipeline_description(self) -> str:
        """返回基于 rtmp2src/flvdemux/atdec 的低延迟优化流水线描述字符串"""
        return (
            # 通过 rtmp2src 从 RTMP 服务器接收数据
            f"rtmp2src location={self.rtmp_url} async-connect=true idle-timeout=0 ! "
            # 对 FLV 数据进行解封装
            f"flvdemux name=demux "
            # 视频链路
            f"demux.video ! "
            f"queue max-size-buffers=1 leaky=downstream name=videoqueue ! "
            f"h264parse ! vtdec_hw name=videodec ! "
            f"videoconvert ! video/x-raw,format=UYVY ! "
            f"queue max-size-buffers=1 leaky=downstream name=videoqueue2 ! "
            # 音视频合并器（确保音视频时间戳对齐）
            f"ndisinkcombiner name=combiner "
            # 音频链路
            f"demux.audio ! "
            f"queue max-size-buffers=1 leaky=downstream name=audioqueue ! "
            f"aacparse ! "
            # 使用 atdec 进行 AAC 解码，输出原始音频（支持 S16LE 或 F32LE 格式）
            f"atdec name=audiodec ! "
            f"audioconvert ! audioresample ! "
            f"audio/x-raw,format=F32LE,channels=2,rate=48000 ! "
            f"queue max-size-buffers=1 leaky=downstream name=audioqueue2 ! "
            # 将音频、视频从合并器分别输出到 ndisink
            f"combiner. "
            f"combiner. ! ndisink name=ndisink sync=false ndi-name={self.ndi_name}"
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

    def verify_stream(self) -> bool:
        """验证流状态"""
        if not self.pipeline:
            return False
            
        # 检查管道状态
        _, state, _ = self.pipeline.get_state(0)
        if state != Gst.State.PLAYING:
            return False
            
        # 获取音视频垫（pad）
        videopad = self.pipeline.get_by_name('videodec').get_static_pad('src')
        audiopad = self.pipeline.get_by_name('audiodec').get_static_pad('src')
        
        # 检查是否正在接收数据
        if videopad and audiopad:
            video_ok = videopad.is_linked() and videopad.is_active()
            audio_ok = audiopad.is_linked() and audiopad.is_active()
            return video_ok and audio_ok
            
        return False

    def get_stats(self) -> PipelineStats:
        """获取Pipeline统计信息"""
        stats = PipelineStats()
        
        if not self.pipeline:
            return stats
            
        try:
            # 获取Pipeline状态
            _, state, _ = self.pipeline.get_state(0)
            stats.state = state.value_nick.upper()
            
            # 获取音视频队列状态
            for queue_name in ['videoqueue', 'audioqueue']:
                queue = self.pipeline.get_by_name(queue_name)
                if queue:
                    # 获取队列大小和使用情况
                    cur_level = queue.get_property('current-level-bytes')
                    max_size = queue.get_property('max-size-bytes')
                    if max_size > 0:
                        # 计算使用百分比
                        usage = (cur_level / max_size) * 100
                        if queue_name == 'videoqueue':
                            stats.video_queue_usage = usage
                        else:
                            stats.audio_queue_usage = usage
                            
        except Exception as e:
            self.logger.error(f"获取Pipeline统计信息失败: {e}")
            
        return stats