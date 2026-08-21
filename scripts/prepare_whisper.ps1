# 显式准备 faster-whisper 模型到 Docker 命名卷。
# 用法：在仓库根目录运行 .\scripts\prepare_whisper.ps1 [-Model tiny]

param(
    [string]$Model = "tiny",
    [string]$Device = "cpu",
    [string]$ComputeType = "int8",
    [string]$CacheDir = "/models/whisper"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "未找到 Docker CLI，请先启动 Docker Desktop。"
}

if (-not (Test-Path "docker-compose.yml")) {
    throw "请在仓库根目录运行此脚本。"
}

$pythonScript = @'
import os
from pathlib import Path
from faster_whisper import WhisperModel

model_name = os.environ["PREPARE_WHISPER_MODEL"]
device = os.environ["PREPARE_WHISPER_DEVICE"]
compute_type = os.environ["PREPARE_WHISPER_COMPUTE_TYPE"]
cache_dir = os.environ["PREPARE_WHISPER_CACHE_DIR"]
print(f"准备 Whisper 模型: {model_name} ({device}/{compute_type})")
WhisperModel(model_name, device=device, compute_type=compute_type, download_root=cache_dir)
print(f"模型已准备到: {cache_dir}")
for snapshot in sorted(Path(cache_dir).glob(f"models--Systran--faster-whisper-{model_name}/snapshots/*")):
    if snapshot.is_dir():
        print(f"本地模型路径: {snapshot}")
'@

Write-Host "=== EduCreate Whisper 模型准备 ===" -ForegroundColor Cyan
Write-Host "模型：$Model，设备：$Device，计算类型：$ComputeType" -ForegroundColor Gray

docker compose run --rm --no-deps `
    -e "PREPARE_WHISPER_MODEL=$Model" `
    -e "PREPARE_WHISPER_DEVICE=$Device" `
    -e "PREPARE_WHISPER_COMPUTE_TYPE=$ComputeType" `
    -e "PREPARE_WHISPER_CACHE_DIR=$CacheDir" `
    backend python -c $pythonScript

if ($LASTEXITCODE -ne 0) {
    throw "Whisper 模型准备失败，请检查模型仓库网络、磁盘空间和设备配置。"
}

Write-Host "OK 模型准备完成。下一步请在 .env 中显式开启 VIDEO_TRANSCRIPTION_ENABLED。" -ForegroundColor Green
