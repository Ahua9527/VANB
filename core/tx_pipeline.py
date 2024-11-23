from dataclasses import dataclass
from core.base_pipeline import *

@dataclass
class TxPipelineConfig(BasePipelineConfig):
    """发送端 Pipeline 配置类"""
    ndi_source: str                    # NDI 源名称
    rtmp_url: str                      # RTMP 推流地址
    video_bitrate: int = 2000          # 视频码率 (Kbps)
    audio_bitrate: int = 128000        # 音频码率 (bps)
    video_format: str = "I420"         # 视频格式
    audio_rate: int = 44100            # 音频采样率
    audio_channels: int = 2            # 音频通道数
    
    def get_pipeline_description(self) -> str:
        """获取 Pipeline 描述字符串"""
        return (
            # NDI 源配置
            # f'ndisrc ndi-name="{self.ndi_source}" ! timestamp-mode=3 ! ndisrcdemux name=demux '
            f'ndisrc '
            f'ndi-name="{self.ndi_source}" '
            f'timestamp-mode=timecode '     # 使用接收时间作为时间戳
            f'max-queue-length=20 '             # 增加队列长度
            f'bandwidth=100 ! '                 # 使用最高带宽
            f'ndisrcdemux name=demux '

            # === 视频处理路径 ===
            f'demux.video ! '
            f'queue max-size-bytes=0 max-size-buffers=0 max-size-time=500000000 ! '
            f'videoconvert ! '
            f'videoconvert ! video/x-raw,format={self.video_format} ! '
            f'vtenc_h264_hw '
            f'bitrate={self.video_bitrate} '
            f'allow-frame-reordering=false '
            f'realtime=true ! '
            f'queue max-size-bytes=0 max-size-buffers=0 leaky=downstream ! '
            f'mux. '
            
            # === 音频处理路径 ===
            f'demux.audio ! '
            f'queue max-size-bytes=0 max-size-buffers=0 max-size-time=500000000 ! '
            f'audioconvert ! audioresample ! '
            f'audio/x-raw,'
            f'rate={self.audio_rate},'
            f'channels={self.audio_channels} ! '
            f'faac bitrate={self.audio_bitrate} ! '
            f'queue max-size-bytes=0 max-size-buffers=0 leaky=downstream ! '
            f'mux. '
            
            # === 输出配置 ===
            f'flvmux name=mux latency=500 streamable=true ! '
            f'rtmpsink location={self.rtmp_url} '
        )

class TxMessageHandler(BaseMessageHandler):
    """发送端 Pipeline 消息处理器"""
    def __init__(self, pipeline: 'TxPipeline'):
        super().__init__(pipeline)
        self.drop_count = 0            # 丢帧计数
        self.last_log_time = 0         # 上次日志时间
        self.start_time = time.time()  # 启动时间
        self.running = True            # 运行状态标志

    def _handle_warning(self, message: Gst.Message) -> bool:
        """处理警告消息"""
        warn, debug = message.parse_warning()
        
        # 处理丢帧警告
        if "Dropping" in warn.message:
            self._handle_frame_drop(warn.message)
            return True
            
        # 记录其他警告
        self.logger.warning(f"警告: {warn.message}")
        self.logger.debug(f"调试信息: {debug}")
        return True

    def _handle_frame_drop(self, message: str):
        """处理丢帧情况"""
        self.drop_count += 1
        current_time = time.time()
        
        # 每30秒输出一次统计
        if current_time - self.last_log_time >= 30:
            runtime = current_time - self.start_time
            drop_rate = self.drop_count / runtime if runtime > 0 else 0
            self.logger.info(
                f"运行统计:\n"
                f"- 运行时长: {runtime:.1f}秒\n"
                f"- 累计丢帧: {self.drop_count}\n"
                f"- 平均丢帧率: {drop_rate:.2f}帧/秒"
            )
            self.last_log_time = current_time

    def _handle_state_changed(self, message: Gst.Message) -> bool:
        """处理状态改变消息"""
        if message.src == self.pipeline.pipeline:
            old_state, new_state, pending = message.parse_state_changed()
            self.logger.debug(
                f"Pipeline状态改变: {old_state.value_nick} -> "
                f"{new_state.value_nick} [{pending.value_nick}]"
            )
            
            if new_state == Gst.State.PLAYING:
                self.logger.info(f"NDI 源 {self.pipeline.config.ndi_source} 开始推流")
                self.start_time = time.time()
                self.drop_count = 0
                self._start_performance_monitoring()
            elif new_state == Gst.State.NULL:
                self.logger.info(f"NDI 源 {self.pipeline.config.ndi_source} 已停止推流")
                self.running = False
        return True

    def _start_performance_monitoring(self):
        """启动性能监控"""
        def monitor_performance():
            if not self.running:
                return False
                
            try:
                pipeline = self.pipeline.pipeline
                if not pipeline:
                    return False

                # 查询延迟
                lat = pipeline.query_latency()
                if lat[0]:
                    _, min_lat, max_lat = lat
                    self.logger.debug(
                        f"Pipeline 延迟: {min_lat/1000000.0:.1f}ms - "
                        f"{max_lat/1000000.0:.1f}ms"
                    )
                
                # 查询处理位置
                pos = pipeline.query_position(Gst.Format.TIME)
                if pos[0]:
                    _, position = pos
                    self.logger.debug(
                        f"处理进度: {position/Gst.SECOND:.2f}秒"
                    )

                return True
                
            except Exception as e:
                self.logger.debug(f"性能监控错误: {e}")
                return False

        # 每5秒监控一次性能
        GLib.timeout_add_seconds(5, monitor_performance)

class TxPipeline(BasePipeline):
    """NDI 转 RTMP Pipeline"""
    def __init__(self, config: TxPipelineConfig):
        super().__init__(config)
        self.logger = logging.getLogger(__name__)

    def _create_message_handler(self) -> TxMessageHandler:
        """创建消息处理器"""
        return TxMessageHandler(self)
        
    def create(self) -> bool:
        """创建并配置 Pipeline"""
        self.logger.info(f"创建推流管道: {self.config.ndi_source} -> RTMP")
        return super().create()

    def start(self) -> bool:
        """启动 Pipeline"""
        self.logger.info("正在启动推流...")
        return super().start()

    def stop(self):
        """停止 Pipeline"""
        self.logger.info("正在停止推流...")
        super().stop()

    def verify_stream(self) -> bool:
        """验证流状态"""
        if not self.pipeline:
            return False
            
        # 检查管道状态
        _, state, _ = self.pipeline.get_state(0)
        if state != Gst.State.PLAYING:
            return False
            
        return True