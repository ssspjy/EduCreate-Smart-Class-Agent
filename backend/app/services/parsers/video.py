"""Bounded video probing, audio extraction and optional Whisper transcription."""

from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import tempfile
import time
from threading import Lock


@dataclass
class TranscriptSegment:
    """A transcript fragment with source timestamps in seconds."""

    start: float
    end: float
    text: str


@dataclass
class VideoParseResult:
    """Video parser output independent of the normalized material chunk type."""

    duration_seconds: float | None = None
    segments: list[TranscriptSegment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_MODEL_CACHE: dict[tuple[str, str, str, str], object] = {}
_MODEL_LOCK = Lock()


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def _probe_duration(path: Path, timeout: int) -> tuple[float | None, str | None]:
    try:
        result = _run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            timeout,
        )
    except FileNotFoundError:
        return None, "视频解析运行时不可用，请安装 FFmpeg 或使用 Docker 版本"
    except subprocess.TimeoutExpired:
        return None, "视频元数据探测超时"
    if result.returncode != 0:
        return None, "视频文件无法读取，请确认文件未损坏"
    try:
        return float(result.stdout.strip()), None
    except ValueError:
        return None, "视频缺少有效时长信息"


def _extract_audio(path: Path, output_path: Path, timeout: int) -> str | None:
    try:
        result = _run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-i",
                str(path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            timeout,
        )
    except FileNotFoundError:
        return "视频解析运行时不可用，请安装 FFmpeg 或使用 Docker 版本"
    except subprocess.TimeoutExpired:
        return "视频音频提取超时"
    if result.returncode != 0:
        return "视频不包含可提取的音频轨道"
    return None


def _cached_model_path(model_name: str, download_root: str) -> str | None:
    """Resolve a previously prepared Hugging Face snapshot without network access."""
    if not model_name or not download_root:
        return None
    model_dir = Path(download_root) / f"models--Systran--faster-whisper-{model_name}"
    revision_file = model_dir / "refs" / "main"
    if not revision_file.is_file():
        return None
    revision = revision_file.read_text(encoding="utf-8").strip()
    snapshot = model_dir / "snapshots" / revision
    return str(snapshot) if snapshot.is_dir() else None


def _get_model(
    model_path: str,
    device: str,
    compute_type: str,
    download_root: str,
) -> object:
    from faster_whisper import WhisperModel

    key = (model_path, device, compute_type, download_root)
    with _MODEL_LOCK:
        model = _MODEL_CACHE.get(key)
        if model is None:
            model = WhisperModel(
                model_path,
                device=device,
                compute_type=compute_type,
                download_root=download_root,
            )
            _MODEL_CACHE[key] = model
        return model


def _transcribe_audio(
    audio_path: Path,
    model_path: str,
    device: str,
    compute_type: str,
    language: str,
    timeout_seconds: int,
    download_root: str,
) -> list[TranscriptSegment]:
    model = _get_model(model_path, device, compute_type, download_root)
    segments, _info = model.transcribe(
        str(audio_path),
        language=language or None,
        vad_filter=True,
        beam_size=5,
    )
    started_at = time.monotonic()
    output: list[TranscriptSegment] = []
    for segment in segments:
        if time.monotonic() - started_at > timeout_seconds:
            raise TimeoutError("video transcription timeout")
        if segment.text and segment.text.strip():
            output.append(
                TranscriptSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=segment.text.strip(),
                )
            )
    return output


def _parse_transcribable_media(path: Path, settings: object, media_label: str) -> VideoParseResult:
    """Probe a video/audio file and optionally transcribe its extracted audio."""
    result = VideoParseResult()
    duration, warning = _probe_duration(path, timeout=10)
    result.duration_seconds = duration
    if warning:
        result.warnings.append(warning)
        return result
    if duration is not None and duration > settings.video_max_duration_seconds:
        result.warnings.append(
            f"{media_label}时长超过上限 {settings.video_max_duration_seconds} 秒，未执行转写"
        )
        return result
    if not settings.video_transcription_enabled:
        result.warnings.append(f"{media_label}已验证，但 Whisper 转写未启用")
        return result
    local_model_path = settings.video_whisper_model_path or _cached_model_path(
        settings.video_whisper_model,
        settings.video_whisper_model_cache_dir,
    )
    if not local_model_path and not settings.video_allow_model_download:
        result.warnings.append("视频转写已启用，但未配置本地 Whisper 模型路径")
        return result

    model_path = local_model_path or settings.video_whisper_model
    try:
        with tempfile.TemporaryDirectory(prefix="educreate-video-") as temp_dir:
            audio_path = Path(temp_dir) / "audio.wav"
            warning = _extract_audio(path, audio_path, settings.video_transcription_timeout_seconds)
            if warning:
                result.warnings.append(warning)
                return result
            result.segments = _transcribe_audio(
                audio_path,
                model_path=model_path,
                device=settings.video_whisper_device,
                compute_type=settings.video_whisper_compute_type,
                language=settings.video_whisper_language,
                timeout_seconds=settings.video_transcription_timeout_seconds,
                download_root=settings.video_whisper_model_cache_dir,
            )
    except ModuleNotFoundError:
        result.warnings.append("Whisper 运行时未安装，请安装 faster-whisper")
    except (subprocess.TimeoutExpired, TimeoutError):
        result.warnings.append("视频转写超时")
    except Exception as exc:
        result.warnings.append(f"视频转写失败（{type(exc).__name__}）")
    if not result.segments and not result.warnings:
        result.warnings.append(f"{media_label}未识别到语音内容")
    return result


def parse_video(path: Path, settings: object) -> VideoParseResult:
    """Probe a video and optionally transcribe its extracted audio."""
    return _parse_transcribable_media(path, settings, "视频")


def parse_audio(path: Path, settings: object) -> VideoParseResult:
    """Probe an audio recording and optionally transcribe it with Whisper."""
    return _parse_transcribable_media(path, settings, "音频")
