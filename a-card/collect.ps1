param(
  [string]$RuntimeRoot = 'D:\whale-cover'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $RuntimeRoot).Path
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$out = Join-Path $root "a-card-report-$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$python = Join-Path $root 'engine\venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'probe.py') 2>&1 | Set-Content -LiteralPath (Join-Path $out 'probe.txt') -Encoding UTF8
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM |
  Format-List | Out-String | Set-Content -LiteralPath (Join-Path $out 'gpu.txt') -Encoding UTF8

$logs = Join-Path $root 'data\logs'
foreach ($name in @('a-card-diagnostics.log', 'seedvc.log', 'demucs.log', 'cuda.log', 'prep.log')) {
  $file = Join-Path $logs $name
  if (Test-Path -LiteralPath $file) { Copy-Item -LiteralPath $file -Destination $out -Force }
}
& $python -m pip freeze 2>$null | Select-String -Pattern 'torch|directml|audio|librosa' |
  Set-Content -LiteralPath (Join-Path $out 'python-packages.txt') -Encoding UTF8

$zip = Join-Path $root ("a-card-report-$stamp.zip")
Compress-Archive -Path (Join-Path $out '*') -DestinationPath $zip -Force
Remove-Item -LiteralPath $out -Recurse -Force
Write-Host "报告已生成：$zip"
