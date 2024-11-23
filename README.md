# VANB (Video Audio Network Bridge)
# VANB (Video Assistant  NDI Bridge)
# VANB (哇!! NB)

VANB 是一个基于 GStreamer 的视频/音频流转换工具，支持 NDI 与 RTMP 协议间的双向转换。它允许将 NDI 源推流到 RTMP 服务器，或将 RTMP 流转换为 NDI 输出。

## 支持平台

目前主要支持以下平台：
- macOS (Apple Silicon)

## 环境要求

### 系统依赖
- [GStreamer 1.24+](https://gstreamer.freedesktop.org)
- [NewTek NDI SDK](https://www.ndi.tv/sdk/)

### 安装步骤

1. 安装 [NewTek NDI SDK](https://www.ndi.tv/sdk/)

2. 通过 Homebrew 安装 GStreamer
```bash
brew install --cask --zap gstreamer-development
```

3. 克隆项目仓库
```bash
git clone https://github.com/Ahua9527/VANB.git -b dev
cd VANB
```

4. 安装 Python 依赖
```bash
pip install -r requirements.txt
```

5. 配置环境变量 (参考 .env 文件)
```bash
# 配置 NDI SDK 路径
export NDI_SDK_PATH=/Library/NDI SDK for Apple
# 配置 GStreamer 插件路径
export GST_PLUGIN_PATH=/opt/homebrew/lib/gstreamer-1.0:${NDI_SDK_PATH}/lib/macOS
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:${NDI_SDK_PATH}/lib/macOS
export GI_TYPELIB_PATH=/opt/homebrew/lib/girepository-1.0:/usr/local/lib/girepository-1.0
```

## 使用方法

### NDI 转 RTMP (发送端)
```bash
python vanb_tx.py
```
程序会自动扫描可用的 NDI 源，并提示输入 RTMP 推流地址。

### RTMP 转 NDI (接收端)
```bash
python vanb_rx.py
```
输入 RTMP 拉流地址后，程序会自动创建一个新的 NDI 输出。


## 开发状态

### 已实现功能
- ✓  NDI 到 RTMP 的转换
- ✓  RTMP 到 NDI 的转换
- ✓  自动帧率和分辨率适配
- ✓  音视频同步
- ✓  NDI 源自动扫描
- ✓  NDI 输出自动命名
- ✓  VideoToolbox硬件编解码

### 待实现功能
- ⨯ 配置文件支持 (Profile/config.json)
  - 通过配置文件控制输入输出参数
  - 支持多种转码预设配置
  - 可配置缓冲区大小和延迟参数
  - 支持转码质量和性能平衡配置
- ⨯  多路流并发处理
- ⨯  更多的流媒体协议支持
- ⨯  更多编码格式支持

## 许可声明

⚠️ **重要提示：许可与合规性**

### GStreamer 许可
- GStreamer 核心库和插件采用 LGPL 2.1+ 许可
- 某些插件可能使用了GPL许可，使用这些插件时需要注意遵守相应的许可要求：
  - `gst-plugins-base`: LGPL
  - `gst-plugins-good`: LGPL
  - `gst-plugins-ugly`: LGPL + GPL
  - `gst-plugins-bad`: LGPL + GPL
  - `gst-libav`: GPL

**特别注意**: 本项目使用了以下GPL许可的插件：
- 来自 gst-plugins-bad:
  - `faad`: AAC音频解码器 (GPL)
  - `x265`: HEVC/H.265视频编码器 (GPL)
- 来自 gst-plugins-ugly:
  - `x264`: H.264视频编码器 (GPL)

**因此本项目需要遵守GPL许可证的要求。**

**注意**：
1. 如果您的应用程序使用了GPL插件，那么您的应用程序也需要遵守GPL许可
2. 建议仔细检查您使用的具体插件的许可证要求
3. 商业使用时请特别注意GPL插件的使用，建议咨询法律顾问

### NDI 许可
1. 本项目仅用于开发和测试目的
2. NDI® 是 NewTek, Inc. 的注册商标
3. 使用本项目需要遵守 NewTek NDI® SDK 许可协议
4. 在生产环境中使用前，请确保已获得所有必要的许可和授权

## 问题反馈

如遇到问题，请：
1. 检查是否正确配置了环境变量
2. 确认 GStreamer 插件是否正确安装
3. 查看日志文件中的详细错误信息
4. 通过 Issues 反馈问题，并附上日志和环境信息