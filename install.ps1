param(
  [switch]$DryRun,
  [switch]$Yes,
  [string]$Root = (Join-Path $env:USERPROFILE 'whale-cover'),
  [string]$WhaleGirl = '',
  [string]$OnlyStep = '',
  [string]$BreezeKey = '',
  [switch]$UseInstalledVoice,
  [string[]]$ForceSteps = @()
)

$ErrorActionPreference = 'Continue'

# 默认安装盘：优先沿用已有运行时；否则选可用空间最大的盘，避免装到快满的 C 盘。
if (-not $PSBoundParameters.ContainsKey('Root')) {
  $envRoot = $env:WHALE_COVER_HOME
  $userRoot = Join-Path $env:USERPROFILE 'whale-cover'
  $existing = @()
  if ($envRoot) { $existing += $envRoot }
  $existing += $userRoot
  foreach ($drive in (Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue)) {
    $existing += (Join-Path ($drive.Name + ':\') 'whale-cover')
  }
  $found = $existing | Where-Object { $_ -and (Test-Path (Join-Path $_ 'data\config.json')) } | Select-Object -First 1
  if ($found) {
    $Root = $found
  } else {
    $best = $null
    $bestFree = 0
    foreach ($drive in (Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue)) {
      if (-not $drive.Free -or $drive.Free -lt 12GB) { continue }
      if ($drive.Free -gt $bestFree) { $bestFree = $drive.Free; $best = $drive.Name }
    }
    if ($best) { $Root = ($best + ':\whale-cover') }
  }
}
$script:StateFile = Join-Path $Root '.installer-state.json'
$script:LogFile = Join-Path $Root 'installer.log'

function Write-Info([string]$Text) {
  $line = '[' + (Get-Date -Format 'HH:mm:ss') + '] ' + $Text
  Write-Host $line
  try { Add-Content -Path $script:LogFile -Value $line -Encoding UTF8 } catch { }
}
function Write-Step([string]$Text) { Write-Host ''; Write-Host ('== ' + $Text + ' ==') -ForegroundColor Cyan }
function Fail([string]$Text) {
  Write-Host ('ERROR: ' + $Text) -ForegroundColor Red
  try { Add-Content -Path $script:LogFile -Value (('[' + (Get-Date -Format 'HH:mm:ss') + '] ERROR ' + $Text)) -Encoding UTF8 } catch { }
  if (-not $DryRun -and -not $Yes) {
    Write-Host ''
    Read-Host '按回车键退出（截图或复制上面的错误发给开发者）' | Out-Null
  }
  exit 1
}

function Read-State {
  if (Test-Path $script:StateFile) {
    try { return Get-Content $script:StateFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch { }
  }
  return [pscustomobject]@{ version = 1; steps = [pscustomobject]@{}; startedAt = (Get-Date).ToString('o') }
}
function Save-State($State) {
  New-Item -ItemType Directory -Force -Path $Root | Out-Null
  $State | ConvertTo-Json -Depth 6 | Set-Content -Path $script:StateFile -Encoding UTF8
}
function Test-Done($State, [string]$Id) {
  return $State.steps.PSObject.Properties.Name -contains $Id -and $State.steps.$Id.done -eq $true
}
function Mark-Done($State, [string]$Id, [string]$Detail = '') {
  $entry = [pscustomobject]@{ done = $true; at = (Get-Date).ToString('o'); detail = $Detail }
  if ($State.steps.PSObject.Properties.Name -contains $Id) { $State.steps.$Id = $entry }
  else { $State.steps | Add-Member -NotePropertyName $Id -NotePropertyValue $entry }
  Save-State $State
}

function Test-CudaExecution([string]$Python) {
  if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { return $false }
  $script = Join-Path $PSScriptRoot 'payload\render\cuda_smoke.py'
  & $Python $script 2>$null | Out-Null
  return $LASTEXITCODE -eq 0
}

function Get-TorchBuild {
  $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $smi) {
    $fallback = Join-Path $env:WINDIR 'System32\nvidia-smi.exe'
    if (Test-Path -LiteralPath $fallback -PathType Leaf) { $smi = Get-Item -LiteralPath $fallback }
  }
  if ($smi) {
    $command = if ($smi.Source) { $smi.Source } else { $smi.FullName }
    $caps = @(& $command --query-gpu=compute_cap --format=csv,noheader,nounits 2>$null)
    if ($LASTEXITCODE -eq 0 -and @($caps | Where-Object { $_ -match '^\s*(?:1[2-9]|[2-9]\d)\.\d+\s*$' }).Count) {
      return @{ Version = '2.7.1'; Cuda = 'cu128' }
    }
    if ($LASTEXITCODE -eq 0 -and @($caps | Where-Object { $_ -match '^\s*\d+\.\d+\s*$' }).Count) {
      return @{ Version = '2.4.1'; Cuda = 'cu121' }
    }
  }
  throw '无法读取 NVIDIA GPU 算力。请更新 NVIDIA 驱动，并确认 nvidia-smi 可用后重试。'
}

function Test-ReferenceReady {
  $manifest = Join-Path $Root 'ref\profiles.json'
  if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { return $false }
  try {
    $profiles = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($profiles.mode -eq 'windows-tts') { return $false }
    $defaultName = [string]$profiles.default
    if (-not $defaultName) { $defaultName = 'daily' }
    $entry = $profiles.profiles.PSObject.Properties[$defaultName]
    if (-not $entry -or $entry.Value.file -notmatch '^profiles[/\\][^/\\:]+[.]wav$') { return $false }
    $wav = Get-Item -LiteralPath (Join-Path (Join-Path $Root 'ref') $entry.Value.file) -ErrorAction Stop
    if ($wav.PSIsContainer -or $wav.Length -le 44) { return $false }
    $stream = [IO.File]::OpenRead($wav.FullName)
    try {
      $header = [byte[]]::new(12)
      if ($stream.Read($header, 0, $header.Length) -ne $header.Length) { return $false }
      $ascii = [Text.Encoding]::ASCII
      return ($ascii.GetString($header, 0, 4) -in @('RIFF', 'RF64', 'RIFX') -and
        $ascii.GetString($header, 8, 4) -eq 'WAVE')
    } finally { $stream.Dispose() }
  } catch {
    return $false
  }
}

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($id)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Find-WhaleGirl {
  $candidates = @()
  if ($WhaleGirl) {
    $config = Join-Path $WhaleGirl 'data\config.json'
    if (-not (Test-Path -LiteralPath $config -PathType Leaf)) {
      throw '显式指定的鲸鲸目录缺少 data/config.json，请核对 -WhaleGirl 路径。'
    }
    return (Resolve-Path -LiteralPath $WhaleGirl -ErrorAction Stop).ProviderPath
  }
  if ($env:WHALE_GIRL_HOME) { $candidates += $env:WHALE_GIRL_HOME }
  $candidates += @(
    (Join-Path $env:LOCALAPPDATA 'Programs\WhaleGirl'),
    (Join-Path $env:ProgramFiles 'WhaleGirl'),
    (Join-Path ${env:ProgramW6432} 'WhaleGirl'),
    (Join-Path $env:USERPROFILE 'WhaleGirl'),
    'E:\Program Files\WhaleGirl',
    'D:\Program Files\WhaleGirl',
    'E:\WhaleGirl',
    'D:\WhaleGirl'
  )
  foreach ($drive in (Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue)) {
    try {
      $name = [string]$drive.Name
      if (-not $name) { continue }
      $root = $name + ':\'
      if (-not (Test-Path -LiteralPath $root -ErrorAction SilentlyContinue)) { continue }
      $candidates += ($root + 'WhaleGirl')
      $candidates += ($root + 'whale-girl')
    } catch { continue }
  }
  $proc = Get-Process WhaleLauncher -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($proc -and $proc.Path) { $candidates += (Split-Path $proc.Path -Parent) }
  $candidates = $candidates | Where-Object { $_ -and $_.Trim() } | Select-Object -Unique
  foreach ($candidate in $candidates) {
    try {
      $config = Join-Path ([string]$candidate) 'data\config.json'
      if (Test-Path -LiteralPath $config -ErrorAction SilentlyContinue) { return [string]$candidate }
    } catch { continue }
  }
  # 注册表兜底
  try {
    $keys = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall' -ErrorAction SilentlyContinue
    foreach ($key in $keys) {
      $name = (Get-ItemProperty $key.PSPath -ErrorAction SilentlyContinue).DisplayName
      if ($name -match 'WhaleGirl|鲸鲸') {
        $loc = (Get-ItemProperty $key.PSPath).InstallLocation
        if ($loc -and (Test-Path (Join-Path $loc 'data\config.json'))) { return $loc }
      }
    }
  } catch { }
  # 兜底：各盘浅层扫描自定义目录（支持中文/空格路径，例如 D:\我的软件\whaleGirl）
  foreach ($drive in (Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue)) {
    try {
      $name = [string]$drive.Name
      if (-not $name) { continue }
      $root = $name + ':\'
      if (-not (Test-Path -LiteralPath $root -ErrorAction SilentlyContinue)) { continue }
      $dirs = Get-ChildItem -LiteralPath $root -Directory -Depth 2 -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^(?i)whale-?girl$' -or $_.Name -eq '鲸鲸' }
      foreach ($dir in $dirs) {
        try {
          $config = Join-Path $dir.FullName 'data\config.json'
          if (Test-Path -LiteralPath $config -ErrorAction SilentlyContinue) { return $dir.FullName }
        } catch { continue }
      }
    } catch { continue }
  }
  return ''
}
function Get-NvidiaInfo {
  $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
  if (-not $smi) { return $null }
  try {
    $out = & $smi.Source --query-gpu=name,memory.total --format=csv,noheader 2>$null
    return ($out | Select-Object -First 1)
  } catch { return $null }
}
function Get-WeChatVersion {
  $proc = Get-Process Weixin,WeChat -ErrorAction SilentlyContinue | Where-Object { $_.Path } | Select-Object -First 1
  if ($proc) {
    try { return (Get-Item $proc.Path).VersionInfo.FileVersion } catch { }
  }
  $procs = Get-CimInstance Win32_Process -Filter "name='Weixin.exe' OR name='WeChat.exe'" -ErrorAction SilentlyContinue
  if ($procs) {
    foreach ($item in $procs) {
      if ($item.ExecutablePath -and (Test-Path $item.ExecutablePath)) {
        try { return (Get-Item $item.ExecutablePath).VersionInfo.FileVersion } catch { }
      }
    }
  }
  $paths = @(
    (Join-Path $env:ProgramFiles 'Tencent\WeChat\Weixin.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Tencent\WeChat\Weixin.exe'),
    (Join-Path $env:ProgramFiles 'Tencent\Weixin\Weixin.exe'),
    (Join-Path ${env:ProgramFiles(x86)} 'Tencent\Weixin\Weixin.exe')
  ) | Where-Object { $_ -and (Test-Path $_) }
  foreach ($p in $paths) {
    try { return (Get-Item $p).VersionInfo.FileVersion } catch { }
  }
  return ''
}
function Get-FreeSpaceGB {
  try {
    $letter = $Root.Substring(0, 1)
    $drive = Get-PSDrive -Name $letter -ErrorAction Stop
    return [math]::Round($drive.Free / 1GB, 1)
  } catch { return -1 }
}

function Download-File([string]$Url, [string]$Dest) {
  New-Item -ItemType Directory -Force -Path (Split-Path $Dest -Parent) | Out-Null
  $part = $Dest + '.part'
  $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
  if ($curl) {
    $curlArgs = @('-L', '--fail', '--retry', '5', '--retry-delay', '3', '-C', '-', '-o', $part, $Url)
    if ($env:HTTPS_PROXY) { $curlArgs = @('--proxy', $env:HTTPS_PROXY) + $curlArgs }
    & $curl.Source @curlArgs
    if ($LASTEXITCODE -ne 0) { throw ('下载失败: ' + $Url) }
  } else {
    Invoke-WebRequest -Uri $Url -OutFile $part -UseBasicParsing
  }
  Move-Item -Path $part -Destination $Dest -Force
  Write-Info ('下载完成：' + (Split-Path $Dest -Leaf) + ' (' + [math]::Round((Get-Item $Dest).Length / 1MB, 1) + 'MB)')
}
function Ensure-Uv([string]$Root) {
  $uv = Join-Path $Root 'tools\uv\uv.exe'
  if (Test-Path $uv) { return $uv }
  $zip = Join-Path $Root 'tools\uv.zip'
  Download-File 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' $zip
  Expand-Archive -Path $zip -DestinationPath (Join-Path $Root 'tools\uv') -Force
  if (-not (Test-Path $uv)) { throw 'uv.exe 解压后不存在' }
  return $uv
}
function Ensure-Ffmpeg([string]$Root) {
  $dir = Join-Path $Root 'tools\ffmpeg'
  if (Test-Path (Join-Path $dir 'ffmpeg.exe')) { return $dir }
  $zip = Join-Path $Root 'tools\ffmpeg.zip'
  Download-File 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' $zip
  $tmp = Join-Path $Root 'tools\ffmpeg-tmp'
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
  Expand-Archive -Path $zip -DestinationPath $tmp -Force
  $exe = Get-ChildItem $tmp -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1
  if (-not $exe) { throw '压缩包内没有 ffmpeg.exe' }
  $bin = $exe.Directory.FullName
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Copy-Item (Join-Path $bin '*') $dir -Recurse -Force
  Remove-Item $tmp -Recurse -Force
  return $dir
}

# ---- 步骤定义：P1 只有检测逻辑，P2 逐步补下载实现 ----
$steps = @(
  @{ Id = 'env'; Name = '环境检测'; Action = {
      if (-not $IsWindows -and $PSVersionTable.PSEdition -ne 'Desktop') { Fail '只支持 Windows' }
      $admin = Test-Admin
      $gpu = Get-NvidiaInfo
      $wechat = Get-WeChatVersion
      $wg = Find-WhaleGirl
      $free = Get-FreeSpaceGB
      $gpuText = if ($gpu) { $gpu } else { '未检测到' }
      $wechatText = if ($wechat) { $wechat } else { '未检测到' }
      $wgText = if ($wg) { $wg } else { '未检测到' }
      Write-Info ('管理员=' + $admin + '；GPU=' + $gpuText + '；微信=' + $wechatText + '；鲸鲸=' + $wgText + '；磁盘=' + $free + 'GB')
      if (-not $gpu) {
        Write-Host 'WARNING: 未检测到 NVIDIA GPU / nvidia-smi；如果确认有 NVIDIA 显卡，可继续安装，后续用 verify.ps1 检查 CUDA' -ForegroundColor Yellow
      }
      if (-not $wg) {
        if ($DryRun) {
          Write-Host 'WARNING: 未找到鲸鲸安装目录（可用 -WhaleGirl 指定）' -ForegroundColor Yellow
        } else {
          Write-Host '没有自动找到鲸鲸安装目录。' -ForegroundColor Yellow
          Write-Host '请打开鲸鲸安装文件夹，复制地址栏路径（例如 D:\WhaleGirl），粘贴到下面：'
          $answer = Read-Host '鲸鲸安装目录（直接回车退出）'
          if ($answer) {
            $script:WhaleGirl = $answer.Trim().Trim('"')
            $wg = Find-WhaleGirl
          }
          if (-not $wg) { Fail '未找到鲸鲸安装目录；请确认路径下有 data\config.json' }
        }
      }
      if ($wechat -and $wechat -notmatch '^4\.2\.') { Write-Host 'WARNING: 微信版本不是 4.2，UIA 可能不兼容' -ForegroundColor Yellow }
      if ($free -ge 0 -and $free -lt 10) { Write-Host 'WARNING: 可用空间小于 10GB' -ForegroundColor Yellow }
    } },
  @{ Id = 'uv'; Name = 'uv / Python 3.11'; Action = {
      $uv = Ensure-Uv $Root
      Write-Info ('uv 就绪：' + $uv)
      $venv = Join-Path $Root 'engine\venv'
      if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) {
        & $uv venv $venv --python 3.11
        if ($LASTEXITCODE -ne 0) { throw 'uv venv 失败' }
      }
      $py = Join-Path $venv 'Scripts\python.exe'
      & $py --version
      Write-Info ('Python 就绪：' + $py)
    } },
  @{ Id = 'deps'; Name = 'Python 依赖'; Action = {
      $py = Join-Path $Root 'engine\venv\Scripts\python.exe'
      if (-not (Test-Path $py)) { throw '缺少 Python，请先完成 uv 步骤' }
      $probe = & $py -c "import torch,torchaudio,demucs,librosa,soundfile,transformers,requests,Crypto,huggingface_hub;print('ok')" 2>$null
      if ($probe -eq 'ok' -and (Test-CudaExecution $py)) {
        Write-Info '依赖已满足，CUDA 算子执行通过'
        return
      }
      $uv = Join-Path $Root 'tools\uv\uv.exe'
      if (-not (Test-CudaExecution $py)) {
        $build = Get-TorchBuild
        $pin = "$($build.Version)+$($build.Cuda)"
        Write-Info ("安装 PyTorch $pin（数 GB，可能较久）")
        & $uv pip install --python $py "torch==$pin" "torchaudio==$pin" --index-url "https://download.pytorch.org/whl/$($build.Cuda)"
        if ($LASTEXITCODE -ne 0) { throw 'torch 和 torchaudio 安装失败' }
        $cudaProbe = Join-Path $PSScriptRoot 'payload\render\cuda_smoke.py'
        & $py $cudaProbe
        if ($LASTEXITCODE -ne 0) { throw 'PyTorch 已安装，但 CUDA 算子执行失败。请检查 NVIDIA 驱动与显卡兼容性。' }
      }
      if ($probe -eq 'ok') { return }
      Write-Info '安装其余依赖'
      & $uv pip install --python $py 'demucs==4.1.0' 'librosa==0.10.2' 'soundfile==0.12.1' 'numpy==1.26.4' 'transformers==4.46.3' 'huggingface_hub==0.36.2' 'requests' 'pycryptodome' 'safetensors' 'scipy==1.13.1' 'tqdm' 'einops' 'psutil' 'onnxruntime' 'descript-audio-codec' 'descript-audiotools' 'julius' 'torch-stoi' 'munch==4.0.0' 'hydra-core==1.3.2' 'pyyaml' 'python-dotenv' 'pydub' 'accelerate'
      if ($LASTEXITCODE -ne 0) { throw 'Python 依赖安装失败' }
      Write-Info '依赖安装完成'
    } },
  @{ Id = 'ffmpeg'; Name = 'ffmpeg'; Action = {
      $dir = Ensure-Ffmpeg $Root
      Write-Info ('ffmpeg 就绪：' + $dir)
    } },
  @{ Id = 'seedvc'; Name = 'seed-vc 源码'; Action = {
      $seed = Join-Path $Root 'seed-vc'
      $tar = Join-Path $Root 'tools\seed-vc.tar.gz'
      if (-not (Test-Path (Join-Path $seed 'inference_local.py'))) {
        Download-File 'https://codeload.github.com/Plachtaa/seed-vc/tar.gz/refs/heads/main' $tar
        $tmp = Join-Path $Root 'tools\seedvc-tmp'
        if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
        New-Item -ItemType Directory -Force -Path $tmp | Out-Null
        & tar.exe -xzf $tar -C $tmp
        if ($LASTEXITCODE -ne 0) { throw 'seed-vc 解压失败' }
        $src = Get-ChildItem $tmp -Directory | Select-Object -First 1
        if (Test-Path $seed) { Remove-Item $seed -Recurse -Force }
        Move-Item $src.FullName $seed
        Remove-Item $tmp -Recurse -Force
        Remove-Item $tar -Force -ErrorAction SilentlyContinue
      }
      $payload = Join-Path $PSScriptRoot 'payload'
      Copy-Item (Join-Path $payload 'seedvc\inference_local.py') (Join-Path $seed 'inference_local.py') -Force
      Copy-Item (Join-Path $payload 'seedvc\local_sing.yml') (Join-Path $seed 'configs\local_sing.yml') -Force
      foreach ($pair in @(@('tools','tools'), @('whale-plugin','whale-plugin'), @('render','render'), @('voice','voice'))) {
        $from = Join-Path $payload $pair[0]
        $to = Join-Path $Root $pair[1]
        New-Item -ItemType Directory -Force -Path $to | Out-Null
        Copy-Item (Join-Path $from '*') $to -Recurse -Force
      }
      Write-Info ('seed-vc 就绪：' + $seed)
    } },
  @{ Id = 'models'; Name = '模型权重'; Action = {
      $py = Join-Path $Root 'engine\venv\Scripts\python.exe'
      $script = Join-Path $PSScriptRoot 'payload\seedvc\download_models.py'
      if (-not $env:HF_ENDPOINT) { $env:HF_ENDPOINT = 'https://hf-mirror.com' }
      & $py $script --root $Root
      if ($LASTEXITCODE -ne 0) { throw '模型下载失败' }
    } },
  @{ Id = 'voice'; Name = '语音发送依赖'; Action = {
      $venv = Join-Path $Root 'voice\venv'
      $uv = Join-Path $Root 'tools\uv\uv.exe'
      $py = Join-Path $venv 'Scripts\python.exe'
      if (-not (Test-Path $py)) { & $uv venv $venv --python 3.11 }
      $probe = & $py -c "import uiautomation,sounddevice,soundfile;print('ok')" 2>$null
      if ($probe -ne 'ok') {
        & $uv pip install --python $py 'uiautomation==2.0.29' 'sounddevice==0.5.6' 'soundfile==0.14.0' 'numpy' 'soundcard'
        if ($LASTEXITCODE -ne 0) { throw '语音依赖安装失败' }
      }
      Write-Info ('语音依赖就绪：' + $py)
    } },
  @{ Id = 'vbcable'; Name = 'VB-CABLE'; Action = {
      $devices = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -match 'CABLE' }
      if ($devices) { Write-Info '已检测到 CABLE 设备，跳过'; return }
      if (-not (Test-Admin)) { throw '安装 VB-CABLE 需要管理员权限（请以管理员运行）' }
      $zip = Join-Path $Root 'tools\vbcable.zip'
      Download-File 'https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip' $zip
      $dir = Join-Path $Root 'tools\vbcable'
      if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
      Expand-Archive -Path $zip -DestinationPath $dir -Force
      $setup = Get-ChildItem $dir -Recurse -Filter 'VBCABLE_Setup_x64.exe' | Select-Object -First 1
      if (-not $setup) { throw 'VB-CABLE 安装器不存在' }
      $proc = Start-Process -FilePath $setup.FullName -ArgumentList '-i','-h' -Wait -PassThru
      if ($proc.ExitCode -ne 0) { throw ('VB-CABLE 安装退出码 ' + $proc.ExitCode) }
      Write-Info 'VB-CABLE 已安装；需要重启后把播放设备设为 CABLE Input、微信麦克风设为 CABLE Output'
    } },
  @{ Id = 'plugin'; Name = '安装插件'; Action = {
      $ErrorActionPreference = 'Stop'
      $wg = Find-WhaleGirl
      if (-not $wg) { throw '未找到鲸鲸安装目录' }
      $plugins = Join-Path $wg 'data\plugins'
      New-Item -ItemType Directory -Force -Path $plugins | Out-Null
      $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
      $backup = Join-Path $wg ('data\backup-sing-installer-' + $stamp)
      $pkg = Join-Path $PSScriptRoot 'payload\plugin'
      $manifestPath = Join-Path $pkg 'plugin.json'
      $sourcePath = Join-Path $pkg 'plugin.js'
      $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
      if ($manifest.Id -ne 'breezeblue-sing' -or $manifest.Api -ne 4) { throw '插件清单无效' }
      $utf8 = [System.Text.UTF8Encoding]::new($false)
      $flow = [ordered]@{
        id = $manifest.Id; api = $manifest.Api; kind = $manifest.Kind
        hooks = @($manifest.Hooks); permissions = @($manifest.Permissions)
        executionTimeoutMs = $manifest.ExecutionTimeoutMs; intervalSeconds = $manifest.IntervalSeconds
        javascript = [System.IO.File]::ReadAllText($sourcePath, $utf8)
      }
      $flowBytes = $utf8.GetBytes(($flow | ConvertTo-Json -Depth 6 -Compress))
      $sha = [System.Security.Cryptography.SHA256]::Create()
      try { $hash = [BitConverter]::ToString($sha.ComputeHash($flowBytes)).Replace('-', '').ToLowerInvariant() }
      finally { $sha.Dispose() }
      $grantPath = Join-Path $plugins 'breezeblue-sing.flow-grant.json'
      $settings = [ordered]@{
        coverCli = (Join-Path $Root 'tools\cover.mjs')
        python = (Join-Path $Root 'engine\venv\Scripts\python.exe')
        ffmpeg = (Join-Path $Root 'tools\ffmpeg')
        dataDir = (Join-Path $Root 'data')
        engine = 'seedvc'; maxSeconds = 30; onlyGroup = $false; autoRender = $true
        neteaseCookies = (Join-Path $Root 'cookies.txt')
        voicePython = (Join-Path $Root 'voice\venv\Scripts\python.exe')
        voiceSender = (Join-Path $Root 'voice\send_cover.py')
      }
      if (Test-Path -LiteralPath $grantPath -PathType Leaf) {
        $prior = Get-Content -LiteralPath $grantPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($prior.settings) {
          foreach ($entry in $prior.settings.PSObject.Properties) { $settings[$entry.Name] = $entry.Value }
        }
      }
      $grant = [ordered]@{ enabled = $false; fullAccess = $false; hash = $hash; settings = $settings }
      $enabledPath = Join-Path $plugins 'breezeblue-sing.enabled'
      $writer = @(
        @{ Target = (Join-Path $plugins 'breezeblue-sing.flow.json'); Backup = 'breezeblue-sing.flow.json'; Bytes = $flowBytes },
        @{ Target = $grantPath; Backup = 'breezeblue-sing.flow-grant.json'; Bytes = $utf8.GetBytes(($grant | ConvertTo-Json -Depth 16 -Compress)) },
        @{ Target = (Join-Path $plugins 'breezeblue-sing.zip'); Backup = 'breezeblue-sing.zip' },
        @{ Target = (Join-Path $Root 'voice\send_cover.py'); Backup = 'runtime-send_cover.py'; Source = (Join-Path $PSScriptRoot 'payload\voice\send_cover.py') },
        @{ Target = (Join-Path $Root 'tools\cover.mjs'); Backup = 'runtime-cover.mjs'; Source = (Join-Path $PSScriptRoot 'payload\tools\cover.mjs') },
        @{ Target = (Join-Path $Root 'whale-plugin\breeze-prep.mjs'); Backup = 'runtime-breeze-prep.mjs'; Source = (Join-Path $PSScriptRoot 'payload\whale-plugin\breeze-prep.mjs') },
        @{ Target = (Join-Path $Root 'render\render_cover.py'); Backup = 'runtime-render_cover.py'; Source = (Join-Path $PSScriptRoot 'payload\render\render_cover.py') },
        @{ Target = (Join-Path $Root 'render\cuda_smoke.py'); Backup = 'runtime-cuda_smoke.py'; Source = (Join-Path $PSScriptRoot 'payload\render\cuda_smoke.py') }
      )
      New-Item -ItemType Directory -Path $backup -Force | Out-Null
      foreach ($name in @('breeze-sing', 'breezeblue-sing')) {
        foreach ($suffix in @('.flow.json', '.flow-grant.json', '.enabled', '.zip')) {
          $file = Join-Path $plugins ($name + $suffix)
          if (Test-Path -LiteralPath $file -PathType Leaf) { Copy-Item -LiteralPath $file -Destination $backup }
        }
      }
      foreach ($item in $writer | Where-Object { $_.Source }) {
        if (-not (Test-Path -LiteralPath $item.Source -PathType Leaf)) { throw '缺少运行时更新文件' }
        if (Test-Path -LiteralPath $item.Target -PathType Leaf) {
          Copy-Item -LiteralPath $item.Target -Destination (Join-Path $backup $item.Backup)
        }
      }
      $markerBackup = Join-Path $backup 'breezeblue-sing.enabled'
      $updated = [System.Collections.Generic.List[object]]::new()
      $temps = [System.Collections.Generic.List[string]]::new()
      try {
        foreach ($item in $writer) {
          New-Item -ItemType Directory -Path (Split-Path -Parent $item.Target) -Force | Out-Null
          $temp = $item.Target + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
          $temps.Add($temp)
          if ($item.Source) { Copy-Item -LiteralPath $item.Source -Destination $temp }
          elseif ($item.Bytes) { [System.IO.File]::WriteAllBytes($temp, $item.Bytes) }
          else {
            $zip = $temp + '.zip'
            $temps.Add($zip)
            Compress-Archive -LiteralPath @($manifestPath, $sourcePath) -DestinationPath $zip
            Move-Item -LiteralPath $zip -Destination $temp
          }
          $item.Temp = $temp
        }
        if (Test-Path -LiteralPath $enabledPath -PathType Leaf) { Remove-Item -LiteralPath $enabledPath }
        foreach ($item in $writer) {
          if (Test-Path -LiteralPath $item.Target -PathType Leaf) {
            [System.IO.File]::Replace($item.Temp, $item.Target, [System.Management.Automation.Language.NullString]::Value)
          } else {
            [System.IO.File]::Move($item.Temp, $item.Target)
          }
          $updated.Add($item)
        }
      } catch {
        foreach ($item in $updated) {
          $original = Join-Path $backup $item.Backup
          if (Test-Path -LiteralPath $original -PathType Leaf) { Copy-Item -LiteralPath $original -Destination $item.Target -Force }
          elseif (Test-Path -LiteralPath $item.Target -PathType Leaf) { Remove-Item -LiteralPath $item.Target }
        }
        if (Test-Path -LiteralPath $markerBackup -PathType Leaf) { Copy-Item -LiteralPath $markerBackup -Destination $enabledPath -Force }
        throw
      } finally {
        foreach ($temp in $temps) {
          if (Test-Path -LiteralPath $temp -PathType Leaf) { Remove-Item -LiteralPath $temp -ErrorAction SilentlyContinue }
        }
      }
      Write-Info ('插件已覆盖，设置已保留；请在插件市场重新授权启用新版。备份：' + $backup)
    } },
  @{ Id = 'reference'; Name = '方案 B：复用鲸鲸语音'; Action = {
      $script:ReferenceDeferred = $false
      if (-not $UseInstalledVoice -and -not $BreezeKey -and
        -not ($ForceSteps -contains 'reference') -and (Test-ReferenceReady)) {
        Write-Info '已有可用参考音，继续保留'
        return
      }
      $wg = Find-WhaleGirl
      if (-not $wg) { throw '未找到鲸鲸安装目录' }

      if ($BreezeKey) {
        $py = Join-Path $Root 'engine\venv\Scripts\python.exe'
        $script = Join-Path $PSScriptRoot 'payload\seedvc\tts_ref.py'
        $ffmpeg = Join-Path $Root 'tools\ffmpeg\ffmpeg.exe'
        $priorKey = $env:BREEZE_API_KEY
        try {
          $env:BREEZE_API_KEY = $BreezeKey
          & $py $script --runtime-root $Root --whale-girl $wg --ffmpeg $ffmpeg
        } finally {
          $env:BREEZE_API_KEY = $priorKey
        }
        if ($LASTEXITCODE -ne 0 -or -not (Test-ReferenceReady)) { throw 'Breeze 参考音生成失败' }
        return
      }

      Write-Host '方案 B 会复用鲸鲸当前语音，需先打开鲸鲸与微信，确认语音已开启且 VB-CABLE 就绪。'
      Write-Host '开始后会向自己的文件传输助手发送测试语音，录音只保存在本机。'
      $runCapture = $UseInstalledVoice
      if (-not $runCapture -and -not $Yes) {
        $runCapture = (Read-Host '已准备好，现在开始方案 B？输入 Y 确认，回车留待稍后') -match '^[yY]$'
      }
      if (-not $runCapture) {
        $script:ReferenceDeferred = $true
        Write-Info '参考音待配置。就绪后运行 install.cmd -OnlyStep reference -UseInstalledVoice。'
        return
      }

      $voicePy = Join-Path $Root 'voice\venv\Scripts\python.exe'
      $capture = Join-Path $PSScriptRoot 'payload\seedvc\capture_ref.py'
      if (-not (Test-Path -LiteralPath $voicePy -PathType Leaf) -or
        -not (Test-Path -LiteralPath $capture -PathType Leaf)) { throw '请先安装语音依赖，再重试方案 B' }
      & $voicePy $capture --runtime-root $Root --whale-girl $wg
      if ($LASTEXITCODE -ne 0 -or -not (Test-ReferenceReady)) {
        throw '方案 B 未完成。检查鲸鲸账号、微信前台和 VB-CABLE，再重试参考音步骤'
      }
      Write-Info '已使用鲸鲸当前语音生成参考音'
    } },
  @{ Id = 'songs'; Name = '默认测试歌曲'; Action = {
      New-Item -ItemType Directory -Force -Path (Join-Path $Root 'data\songs') | Out-Null
      Write-Info '可将自己有权使用的音频放入 data\songs'
    } },
  @{ Id = 'settings'; Name = '设置向导'; Action = {
      $cfgFile = Join-Path $Root 'config.json'
      if (-not (Test-Path $cfgFile)) {
        [System.IO.File]::WriteAllText($cfgFile, '{"proxy":""}', (New-Object System.Text.UTF8Encoding($false)))
      }
      New-Item -ItemType Directory -Force -Path (Join-Path $Root 'data\songs') | Out-Null
      Write-Host ''
      Write-Host '还需要你在鲸鲸里确认：' -ForegroundColor Cyan
      Write-Host '  1. 插件市场 → 已安装 → Breezeblue 翻唱 → 设置：确认路径与主动唱歌参数'
      Write-Host '  2. 网易云 cookies（可选）：把 cookies.txt 放到 ' + (Join-Path $Root 'cookies.txt')
      Write-Host '  3. VB-CABLE：播放设备选 CABLE Input，微信麦克风选 CABLE Output'
      Write-Host '  4. 重启鲸鲸内核，让它加载插件'
      Write-Host '  5. 私聊点一首歌做冒烟测试'
    } },
  @{ Id = 'smoke'; Name = '冒烟测试'; Action = {
      $cli = Join-Path $Root 'tools\cover.mjs'
      $py = Join-Path $Root 'engine\venv\Scripts\python.exe'
      $sender = Join-Path $Root 'voice\send_cover.py'
      if (-not (Test-Path $cli)) { throw 'cover.mjs 缺失' }
      if (-not (Test-Path $py)) { throw 'engine venv 缺失' }
      if (-not (Test-Path $sender)) { throw 'send_cover.py 缺失' }
      $env:WHALE_COVER_DATA_DIR = (Join-Path $Root 'data')
      $node = (Get-Command node -ErrorAction SilentlyContinue | Select-Object -First 1).Source
      if (-not $node) {
        $wgNode = Find-WhaleGirl
        if ($wgNode) {
          $bundled = Join-Path $wgNode 'runtime\node.exe'
          if (Test-Path -LiteralPath $bundled) { $node = $bundled }
        }
      }
      if (-not $node) {
        Write-Host 'WARNING: 系统 PATH 里没有 node，也没找到鲸鲸 runtime\node.exe；跳过 cover.mjs 自检。' -ForegroundColor Yellow
        Write-Host '        鲸鲸内核会使用自带 Node 运行插件，不影响使用；如需自检可安装 Node.js LTS。' -ForegroundColor Yellow
      } else {
        & $node $cli list --json | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'cover.mjs 自检失败' }
      }
      $cuda = & $py -c "import torch;print(torch.cuda.is_available())" 2>$null
      Write-Info ('冒烟通过；CUDA=' + $cuda)
    } }
)

Write-Host 'Breezeblue 翻唱运行时安装器 1.0.17' -ForegroundColor Green
Write-Host ('安装目录：' + $Root)
if ($DryRun) { Write-Host '模式：DryRun（只检测，不下载、不写入）' -ForegroundColor Yellow }

$state = Read-State
if (-not (Test-Path $Root)) {
  if ($DryRun) { Write-Info '目录不存在（DryRun 不创建）' }
  else { New-Item -ItemType Directory -Force -Path $Root | Out-Null }
}

foreach ($step in $steps) {
  if ($OnlyStep -and $step.Id -ne $OnlyStep) { continue }
  Write-Step $step.Name
  if ($DryRun) {
    if ($step.Id -eq 'env') {
      try { & $step.Action } catch { Write-Host ('DryRun 检测失败：' + $_.Exception.Message) -ForegroundColor Yellow }
    } else {
      Write-Info 'DryRun 跳过'
    }
    continue
  }
  $redoReference = $step.Id -eq 'reference' -and ($UseInstalledVoice -or $BreezeKey -or -not (Test-ReferenceReady))
  $repairCuda = $step.Id -eq 'deps' -and (Test-Done $state 'deps') -and -not (Test-CudaExecution (Join-Path $Root 'engine\venv\Scripts\python.exe'))
  if ((Test-Done $state $step.Id) -and -not $redoReference -and -not $repairCuda -and -not ($ForceSteps -contains $step.Id)) { Write-Info '已完成，跳过'; continue }
  try {
    & $step.Action
    if ($step.Id -eq 'reference' -and $script:ReferenceDeferred) { continue }
    Mark-Done $state $step.Id 'ok'
    $didRun = $true
  } catch {
    Fail ($step.Name + ' 失败：' + $_.Exception.Message)
  }
}

$state = Read-State
$pending = @($steps | Where-Object { -not (Test-Done $state $_.Id) })
if ($DryRun) {
  Write-Host ''
  Write-Host '检查结束（DryRun：没有下载、没有修改任何文件）。' -ForegroundColor Yellow
} elseif ($OnlyStep) {
  if ($OnlyStep -eq 'reference' -and $script:ReferenceDeferred) {
    Write-Host '方案 B 等待用户运行，参考音步骤未标记为完成。'
  } elseif (-not $didRun) { Write-Host '步骤已完成，覆盖升级请加 -ForceSteps。' }
} elseif ($pending.Count -eq 0 -and -not $didRun) {
  Write-Host ''
  Write-Host '所有步骤均已完成，本次没有修改。' -ForegroundColor Green
  Write-Host '如果你是从旧版升级，请用 -ForceSteps 重新部署新脚本/插件：' -ForegroundColor Yellow
  Write-Host '  install.cmd -OnlyStep plugin -ForceSteps plugin' -ForegroundColor Yellow
} else {
  Write-Host ''
  Write-Host '安装完成！下一步：' -ForegroundColor Green
  Write-Host ' 1) 重启电脑'
  Write-Host ' 2) 声音设置：输出选 CABLE Input，输入选 CABLE Output'
  Write-Host ' 3) 启动鲸鲸，在插件市场启用 Breezeblue 翻唱'
  Write-Host ' 4) 完成方案 B 后，私聊发：点歌 加入的歌名'
}
