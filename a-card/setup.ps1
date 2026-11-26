param(
  [string]$RuntimeRoot = 'D:\whale-cover'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $RuntimeRoot).Path
$python = Join-Path $root 'engine\venv\Scripts\python.exe'
$render = Join-Path $root 'render\render_cover.py'
$infer = Join-Path $root 'seed-vc\inference_local.py'
$patchDir = Join-Path $PSScriptRoot 'patches'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $root ("a-card-backup-$stamp")

if (-not (Test-Path -LiteralPath $python)) { throw "找不到 Python：$python" }
if (-not (Test-Path -LiteralPath $render)) { throw "找不到 render_cover.py：$render" }
if (-not (Test-Path -LiteralPath $infer)) { throw "找不到 inference_local.py：$infer" }

$gpus = @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion)
$gpuText = ($gpus | ForEach-Object { "$($_.Name) / $($_.DriverVersion)" }) -join '; '
Write-Host "检测到显卡：$gpuText"
if ($gpuText -notmatch 'AMD|Radeon|Advanced Micro Devices|Intel') {
  Write-Warning '没有检测到 AMD/Intel 显卡；如果这是 NVIDIA 机器，请不要运行本脚本。'
}

New-Item -ItemType Directory -Force -Path $backup | Out-Null
Copy-Item -LiteralPath $render -Destination (Join-Path $backup 'render_cover.py')
Copy-Item -LiteralPath $infer -Destination (Join-Path $backup 'inference_local.py')
& $python -m pip freeze 2>$null | Set-Content -LiteralPath (Join-Path $backup 'pip-freeze.txt') -Encoding UTF8

Write-Host '安装 torch-directml（预发布包，A 卡环境会替换 CUDA torch）...'
& $python -m pip install --pre 'torch-directml==0.2.5.dev240914' --index-url https://pypi.org/simple
if ($LASTEXITCODE -ne 0) { throw 'torch-directml 安装失败' }

# DirectML 使用 CPU torch 轮子；torchaudio 必须与 torch 2.4.1 兼容。
& $python -m pip install 'torchaudio==2.4.1' --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { Write-Warning 'torchaudio CPU 轮子安装失败；若运行时报 torchaudio 错误，请据此日志修复。' }

Copy-Item -LiteralPath (Join-Path $patchDir 'render_cover.py') -Destination $render -Force
Copy-Item -LiteralPath (Join-Path $patchDir 'inference_local.py') -Destination $infer -Force
Write-Host '已应用 A 卡兼容补丁。'

$diag = Join-Path $root 'data\logs'
New-Item -ItemType Directory -Force -Path $diag | Out-Null
& (Join-Path $PSScriptRoot 'diagnose.ps1') -RuntimeRoot $root

Write-Host ''
Write-Host '安装完成。备份目录：'
Write-Host "  $backup"
Write-Host '把 data\logs\a-card-diagnostics.log 和错误日志回传即可。'
