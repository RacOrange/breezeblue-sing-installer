param(
  [string]$Root = '',
  [string]$WhaleGirl = ''
)

if (-not $Root) {
  $candidates = @((Join-Path $env:USERPROFILE 'whale-cover'))
  foreach ($drive in (Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue)) {
    $candidates += (Join-Path ($drive.Name + ':\') 'whale-cover')
  }
  $Root = $candidates | Where-Object { $_ -and (Test-Path (Join-Path $_ 'data')) } | Select-Object -First 1
  if (-not $Root) { $Root = Join-Path $env:USERPROFILE 'whale-cover' }
}

$ErrorActionPreference = 'Continue'
$fail = 0

function Check([string]$Name, [bool]$Ok, [string]$Detail = '') {
  if ($Ok) { Write-Host ('PASS  ' + $Name) -ForegroundColor Green }
  else { Write-Host ('FAIL  ' + $Name + '  ' + $Detail) -ForegroundColor Red; $script:fail++ }
}
function Find-WG {
  $c = @()
  if ($WhaleGirl) { $c += $WhaleGirl }
  $c += @(
    (Join-Path $env:LOCALAPPDATA 'Programs\WhaleGirl'),
    (Join-Path $env:ProgramFiles 'WhaleGirl'),
    (Join-Path ${env:ProgramW6432} 'WhaleGirl'),
    'E:\Program Files\WhaleGirl',
    'D:\Program Files\WhaleGirl'
  )
  foreach ($x in $c) { if ($x -and (Test-Path (Join-Path $x 'data\config.json'))) { return $x } }
  $p = Get-Process WhaleLauncher -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($p -and $p.Path) { $d = Split-Path $p.Path -Parent; if (Test-Path (Join-Path $d 'data\config.json')) { return $d } }
  return ''
}

Write-Host ('运行时：' + $Root)
Write-Host ('鲸鲸：' + (Find-WG))
Write-Host ''

Check 'cover.mjs' (Test-Path (Join-Path $Root 'tools\cover.mjs'))
Check 'breeze-prep.mjs' (Test-Path (Join-Path $Root 'whale-plugin\breeze-prep.mjs'))
Check 'render_cover.py' (Test-Path (Join-Path $Root 'render\render_cover.py'))
Check 'send_cover.py' (Test-Path (Join-Path $Root 'voice\send_cover.py'))
Check 'seed-vc inference_local.py' (Test-Path (Join-Path $Root 'seed-vc\inference_local.py'))
Check 'ffmpeg' (Test-Path (Join-Path $Root 'tools\ffmpeg\ffmpeg.exe'))
Check 'bigvgan 模型' (Test-Path (Join-Path $Root 'seed-vc\models\bigvgan-44k\bigvgan_generator.pt'))
Check 'whisper 模型' (Test-Path (Join-Path $Root 'seed-vc\models\whisper-small\model.safetensors'))
Check '参考音 profiles.json' (Test-Path (Join-Path $Root 'ref\profiles.json'))

$py = Join-Path $Root 'engine\venv\Scripts\python.exe'
Check 'engine python' (Test-Path $py)
if (Test-Path $py) {
  $cuda = & $py -c "import torch;print(torch.cuda.is_available())" 2>$null
  Check 'CUDA 可用' ($cuda -eq 'True') ('torch.cuda=' + $cuda)
}
$vpy = Join-Path $Root 'voice\venv\Scripts\python.exe'
Check 'voice python' (Test-Path $vpy)
if (Test-Path $vpy) {
  $ok = & $vpy -c "import uiautomation,sounddevice,soundfile;print('ok')" 2>$null
  Check '语音依赖导入' ($ok -eq 'ok')
}
$cable = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -match 'CABLE' }
Check 'VB-CABLE 设备' ([bool]$cable)

$wg = Find-WG
if ($wg) {
  $plugins = Join-Path $wg 'data\plugins'
  Check '插件 flow' (Test-Path (Join-Path $plugins 'breezeblue-sing.flow.json'))
  Check '插件授权' (Test-Path (Join-Path $plugins 'breezeblue-sing.flow-grant.json'))
  try {
    $cfg = Get-Content (Join-Path $wg 'data\config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    Check 'JS 插件总闸' ($cfg.features.javascriptPlugins -eq $true)
  } catch { Check 'JS 插件总闸' $false 'config 解析失败' }
}

$cli = Join-Path $Root 'tools\cover.mjs'
if (Test-Path $cli) {
  $env:WHALE_COVER_DATA_DIR = (Join-Path $Root 'data')
  $list = & node $cli list --json 2>$null
  Check 'cover CLI 自检' ($LASTEXITCODE -eq 0) ($list | Select-Object -First 1)
}

Write-Host ''
if ($fail -eq 0) { Write-Host '全部检查通过。' -ForegroundColor Green; exit 0 }
Write-Host ('有 ' + $fail + ' 项未通过。') -ForegroundColor Yellow
exit 1
