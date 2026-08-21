"""Video parser guardrail tests."""

from pathlib import Path
from types import SimpleNamespace

from app.services.parsers import video


def _settings(**overrides):
    values = {
        "video_max_duration_seconds": 1800,
        "video_transcription_enabled": True,
        "video_whisper_model_path": "",
        "video_allow_model_download": False,
        "video_whisper_model": "tiny",
        "video_whisper_device": "cpu",
        "video_whisper_compute_type": "int8",
        "video_whisper_language": "zh",
        "video_whisper_model_cache_dir": "/models/whisper",
        "video_transcription_timeout_seconds": 300,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_missing_local_model_does_not_extract_or_download(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(video, "_probe_duration", lambda *_args, **_kwargs: (2.0, None))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("音频提取不应在模型未就绪时执行")

    monkeypatch.setattr(video, "_extract_audio", fail_if_called)
    result = video.parse_video(tmp_path / "lesson.mp4", _settings())

    assert result.segments == []
    assert result.warnings == ["视频转写已启用，但未配置本地 Whisper 模型路径"]


def test_video_duration_limit_prevents_transcription(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(video, "_probe_duration", lambda *_args, **_kwargs: (1801.0, None))

    result = video.parse_video(
        tmp_path / "long.mp4",
        _settings(video_max_duration_seconds=1800, video_whisper_model_path="/models/whisper/tiny"),
    )

    assert result.segments == []
    assert "超过上限 1800 秒" in result.warnings[0]


def test_cached_model_path_resolves_prepared_snapshot(tmp_path: Path) -> None:
    model_dir = tmp_path / "models--Systran--faster-whisper-tiny"
    (model_dir / "refs").mkdir(parents=True)
    (model_dir / "snapshots" / "abc123").mkdir(parents=True)
    (model_dir / "refs" / "main").write_text("abc123\n", encoding="utf-8")

    assert video._cached_model_path("tiny", str(tmp_path)) == str(model_dir / "snapshots" / "abc123")
