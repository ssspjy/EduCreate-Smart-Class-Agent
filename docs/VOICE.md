# 语音输入与转写说明

## 输入链路

澄清页的语音按钮按以下顺序工作：

1. 优先调用浏览器 Web Speech API，将最终识别文本直接追加到输入框。
2. 浏览器没有实时识别能力时，回退到 `MediaRecorder` 录音。
3. 录音以 WebM（浏览器实际支持的编码）上传到材料接口。
4. 后端通过 FFprobe/FFmpeg 提取音频，再按 Whisper 配置生成带时间戳的 transcript chunk。
5. 转写结果追加到澄清输入框，同时原始录音保留在材料列表中。

## 配置边界

语音转写复用视频的 Whisper 配置，默认仍为关闭：

```env
VIDEO_TRANSCRIPTION_ENABLED=false
VIDEO_ALLOW_MODEL_DOWNLOAD=false
```

关闭时，Web Speech API 在浏览器支持的情况下仍可直接输入文字；MediaRecorder 回退会保留录音，但页面会提示“未生成语音转写”，不会伪造文本。要启用回退转写，请先按 [`VIDEO.md`](./VIDEO.md) 准备模型，再显式设置 `VIDEO_TRANSCRIPTION_ENABLED=true`。

后端接受的录音扩展名包括 `webm`、`wav`、`m4a`、`mp3` 和 `ogg`。Compose 中录音进入 Celery 队列，澄清页会等待材料到达终态后再读取 transcript；超时只提示稍后检查材料，不会伪造文本。本地开发仍默认同步处理。

## 浏览器排障

- Web Speech API 不可用：确认页面处于安全上下文，并使用支持麦克风的浏览器；否则自动显示录音回退。
- 麦克风权限被拒绝：在浏览器站点权限中允许麦克风后重试。
- 回退录音没有 transcript：检查 Whisper 是否启用、模型路径是否可读，以及后端日志中的 FFmpeg/模型 warning。
