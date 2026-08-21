# 视频解析与转写说明

## 能力范围

MP4 上传会先通过 FFprobe 校验文件和时长。视频转写开启后，FFmpeg 将音频转换为单声道 16 kHz WAV，再交给 `faster-whisper`；每个转写片段写入 `chunks`，包含时间范围、`media_ref` 和 `modality=transcript`。

默认关闭 Whisper 转写，只做视频探测并返回“未启用”提示。这是有意的部署边界：模型文件较大，不能在用户第一次上传时隐式下载或阻塞接口。Docker 镜像安装了 FFmpeg 和 `faster-whisper`，模型文件通过 `whisper_models` 命名卷持久化。

## 配置

| 环境变量 | 默认值 | 作用 |
|---|---:|---|
| `VIDEO_TRANSCRIPTION_ENABLED` | `false` | 是否执行 Whisper 转写 |
| `VIDEO_WHISPER_MODEL` | `tiny` | 允许下载时使用的模型名称 |
| `VIDEO_WHISPER_MODEL_PATH` | 空 | 本地模型目录；配置后不需要下载 |
| `VIDEO_WHISPER_MODEL_CACHE_DIR` | `./data/whisper-models` | 模型下载缓存目录；Compose 映射到 `/models/whisper` |
| `VIDEO_ALLOW_MODEL_DOWNLOAD` | `false` | 是否允许从模型仓库下载模型 |
| `VIDEO_WHISPER_DEVICE` | `cpu` | `cpu` 或已配置 CUDA 的 `cuda` |
| `VIDEO_WHISPER_COMPUTE_TYPE` | `int8` | CPU 推荐 `int8`，GPU 可改为 `float16` |
| `VIDEO_WHISPER_LANGUAGE` | `zh` | Whisper 语言提示 |
| `VIDEO_MAX_DURATION_SECONDS` | `1800` | 单个视频最大时长 |
| `VIDEO_TRANSCRIPTION_TIMEOUT_SECONDS` | `300` | FFmpeg 和转写处理的时间边界 |

## Docker 使用方式

只验证视频是否可读，不下载模型：

```env
VIDEO_TRANSCRIPTION_ENABLED=false
```

启用模型下载前，确认比赛环境允许访问模型仓库，然后在 `.env` 中设置：

```env
VIDEO_TRANSCRIPTION_ENABLED=true
VIDEO_ALLOW_MODEL_DOWNLOAD=true
VIDEO_WHISPER_MODEL=tiny
```

启动后第一次转写会下载模型，文件写入 `whisper_models` 卷。更稳定的比赛部署方式是提前准备模型目录，再设置：

```env
VIDEO_TRANSCRIPTION_ENABLED=true
VIDEO_ALLOW_MODEL_DOWNLOAD=false
# 可选：填写 prepare_whisper.ps1 输出的 snapshot 路径
VIDEO_WHISPER_MODEL_PATH=/models/whisper/models--Systran--faster-whisper-tiny/snapshots/<revision>
```

推荐在比赛部署前使用仓库脚本显式准备模型；脚本只执行模型下载，不会修改上传接口的默认开关：

```powershell
.\scripts\prepare_whisper.ps1 -Model tiny
```

模型准备成功后，再在 `.env` 中启用转写并重新创建后端容器：

```env
VIDEO_TRANSCRIPTION_ENABLED=true
VIDEO_ALLOW_MODEL_DOWNLOAD=false
VIDEO_WHISPER_MODEL_PATH=/models/whisper/tiny
```

模型准备脚本会输出实际的 snapshot 路径；也可以不填写 `VIDEO_WHISPER_MODEL_PATH`，后端会在缓存卷中自动解析已准备的 `faster-whisper` snapshot。模型准备失败时不要打开上传侧的隐式下载，先检查网络、磁盘空间和 CPU/GPU 配置。

## 冒烟检查

```powershell
curl.exe -F "file=@D:\资料\lesson.mp4" http://localhost:8000/api/v1/materials/upload
curl.exe http://localhost:8000/api/v1/materials/<file_id>/chunks
```

转写成功的 chunk 示例：

```json
{
  "content": "[12.4s–16.8s] 光的折射定律",
  "media_ref": "<stored-video>.mp4#t=12.4-16.8",
  "modality": "transcript"
}
```

如果 FFmpeg 不可用、视频没有音轨、超过时长上限、模型路径不存在或转写失败，上传仍会保留原视频，并把原因写入 `error_message`；不会伪造字幕 chunk。
