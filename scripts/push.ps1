# EduCreate-Smart-Class-Agent 一键推送脚本
# 用法：在仓库根目录 PowerShell 中运行 .\scripts\push.ps1

param(
    [string]$Message = "feat: update skeleton",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

Write-Host "=== EduCreate 推送脚本 ===" -ForegroundColor Cyan

# 1. 检查 git 仓库
if (-not (Test-Path ".git")) {
    Write-Host "X 当前目录不是 git 仓库" -ForegroundColor Red
    exit 1
}

# 2. 检查工作区状态
$status = git status --porcelain
if ($status) {
    Write-Host ">> 检测到变更，正在 add + commit..." -ForegroundColor Yellow
    git add .
    git commit -m $Message
} else {
    Write-Host "i  没有变更需要提交" -ForegroundColor Gray
}

# 3. 检查远程
$remote = git remote get-url origin 2>$null
if (-not $remote) {
    Write-Host "X 未配置 origin 远程仓库" -ForegroundColor Red
    Write-Host "  请先运行: git remote add origin https://github.com/ssspjy/EduCreate-Smart-Class-Agent.git" -ForegroundColor Gray
    exit 1
}

# 4. 推送
Write-Host ">> 推送到 $remote ($Branch)..." -ForegroundColor Yellow
git push -u origin $Branch

if ($LASTEXITCODE -eq 0) {
    Write-Host "OK 推送成功！" -ForegroundColor Green
} else {
    Write-Host "X 推送失败，请检查认证或网络" -ForegroundColor Red
    exit 1
}