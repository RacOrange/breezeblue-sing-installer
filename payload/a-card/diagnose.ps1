param(
  [string]$RuntimeRoot = 'D:\whale-cover'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $RuntimeRoot).Path
$python = Join-Path $root 'engine\venv\Scripts\python.exe'
$logDir = Join-Path $root 'data\logs'
$log = Join-Path $logDir 'a-card-diagnostics.log'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Add-Line([string]$text) {
  $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $text"
  $line | Tee-Object -FilePath $log -Append
}

Add-Line '===== A-card diagnostics ====='
Add-Line "os=$([Environment]::OSVersion.VersionString) arch=$env:PROCESSOR_ARCHITECTURE"
Add-Line "runtime=$root"
try {
  Get-CimInstance Win32_VideoController | ForEach-Object {
    Add-Line "gpu=$($_.Name) driver=$($_.DriverVersion) vram=$([math]::Round(($_.AdapterRAM)/1MB,0))MB"
  }
} catch { Add-Line "gpu_query_error=$($_.Exception.Message)" }
Add-Line "python=$(& $python --version 2>&1)"
Add-Line "torch_pip=$(& $python -m pip show torch 2>$null | Select-String '^Version:' | ForEach-Object { $_.Line })"
Add-Line "directml_pip=$(& $python -m pip show torch-directml 2>$null | Select-String '^Version:' | ForEach-Object { $_.Line })"
Add-Line '----- probe -----'
try {
  & $python (Join-Path $PSScriptRoot 'probe.py') 2>&1 | ForEach-Object { Add-Line $_ }
} catch {
  Add-Line "probe_exception=$($_.Exception.Message)"
}
Add-Line '===== end ====='
Write-Host "诊断日志：$log"
