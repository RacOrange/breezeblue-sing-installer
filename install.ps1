param(
  [switch]$DryRun,
  [switch]$Yes,
  [string]$Root = (Join-Path $env:USERPROFILE 'whale-cover'),
  [string]$WhaleGirl = '',
  [string]$OnlyStep = '',
  [string]$BreezeKey = '',
  [switch]$UseInstalledVoice
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
  return [pscustomobject]@{ version = 1; steps = @{}; startedAt = (Get-Date).ToString('o') }
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

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($id)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Find-WhaleGirl {
  $candidates = @()
  if ($WhaleGirl) { $candidates += $WhaleGirl }
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
      if ($probe -eq 'ok') {
        $cuda = & $py -c "import torch;print(torch.cuda.is_available())" 2>$null
        Write-Info ('依赖已满足，跳过；CUDA=' + $cuda)
        return
      }
      $uv = Join-Path $Root 'tools\uv\uv.exe'
      Write-Info '安装 torch cu121（约 2.4GB，可能较久）'
      & $uv pip install --python $py 'torch==2.4.1+cu121' 'torchaudio==2.4.1+cu121' --index-url https://download.pytorch.org/whl/cu121
      if ($LASTEXITCODE -ne 0) { throw 'torch 安装失败' }
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
      $wg = Find-WhaleGirl
      if (-not $wg) { throw '未找到鲸鲸安装目录' }
      $plugins = Join-Path $wg 'data\plugins'
      New-Item -ItemType Directory -Force -Path $plugins | Out-Null
      $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
      $backup = Join-Path $wg ('data\backup-sing-installer-' + $stamp)
      New-Item -ItemType Directory -Force -Path $backup | Out-Null
      foreach ($name in @('config.json')) {
        $file = Join-Path (Join-Path $wg 'data') $name
        if (Test-Path $file) { Copy-Item $file (Join-Path $backup $name) -Force }
      }
      Get-ChildItem $plugins -Filter 'breezeblue-sing*' -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $backup $_.Name) -Force
      }
      $src = Join-Path $PSScriptRoot 'payload\plugin\plugin.js'
      if (-not (Test-Path $src)) { throw '缺少插件源码 payload\plugin\plugin.js' }
      $flow = [ordered]@{
        id = 'breezeblue-sing'; api = 4; kind = 'message'
        hooks = @('chat.pre_reply', 'timer.tick')
        permissions = @('system.full')
        executionTimeoutMs = 20000; intervalSeconds = 10
        javascript = (Get-Content $src -Raw -Encoding UTF8)
      }
      $flowPath = Join-Path $plugins 'breezeblue-sing.flow.json'
      $flowBytes = [System.Text.Encoding]::UTF8.GetBytes(($flow | ConvertTo-Json -Depth 6 -Compress))
      [System.IO.File]::WriteAllBytes($flowPath, $flowBytes)
      $hash = (Get-FileHash $flowPath -Algorithm SHA256).Hash.ToLower()
      $settings = [ordered]@{
        coverCli = (Join-Path $Root 'tools\cover.mjs')
        python = (Join-Path $Root 'engine\venv\Scripts\python.exe')
        ffmpeg = (Join-Path $Root 'tools\ffmpeg')
        dataDir = (Join-Path $Root 'data')
        engine = 'seedvc'
        maxSeconds = 30
        onlyGroup = $false
        autoRender = $true
        neteaseCookies = (Join-Path $Root 'cookies.txt')
        voicePython = (Join-Path $Root 'voice\venv\Scripts\python.exe')
        voiceSender = (Join-Path $Root 'voice\send_cover.py')
        proactiveEnabled = $true
        proactiveIdleMinutes = 120
        proactiveDailyMax = 2
        proactiveQuietStart = '22:30'
        proactiveQuietEnd = '09:00'
        proactiveCooldownMinutes = 360
        allowDownload = $true
        downloadCandidates = @('晴天', '后来', '小幸运')
      }
      $grant = [ordered]@{ enabled = $true; fullAccess = $true; hash = $hash; settings = $settings }
      [System.IO.File]::WriteAllText((Join-Path $plugins 'breezeblue-sing.flow-grant.json'),
        ($grant | ConvertTo-Json -Depth 8), (New-Object System.Text.UTF8Encoding($false)))
      [System.IO.File]::WriteAllText((Join-Path $plugins 'breezeblue-sing.enabled'), '',
        (New-Object System.Text.UTF8Encoding($false)))
      # 开启 JS 插件总闸（只改数据目录 config.json，不改程序）
      $cfgFile = Join-Path $wg 'data\config.json'
      if (Test-Path $cfgFile) {
        $cfg = Get-Content $cfgFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $cfg.features) { $cfg | Add-Member -NotePropertyName features -NotePropertyValue ([pscustomobject]@{}) }
        $cfg.features | Add-Member -NotePropertyName javascriptPlugins -NotePropertyValue $true -Force
        [System.IO.File]::WriteAllText($cfgFile, ($cfg | ConvertTo-Json -Depth 20),
          (New-Object System.Text.UTF8Encoding($false)))
      }
      Write-Info ('插件已安装：' + $plugins + '；备份：' + $backup + '；重启鲸鲸内核后生效')
    } },
  @{ Id = 'reference'; Name = '生成参考音'; Action = {
      $wg = Find-WhaleGirl
      if (-not $wg) { throw '未找到鲸鲸安装目录' }
      $py = Join-Path $Root 'engine\venv\Scripts\python.exe'
      $script = Join-Path $PSScriptRoot 'payload\seedvc\tts_ref.py'
      $ffmpeg = Join-Path $Root 'tools\ffmpeg\ffmpeg.exe'
      $done = $false
      if ($UseInstalledVoice) {
        $voicePy = Join-Path $Root 'voice\venv\Scripts\python.exe'
        $capture = Join-Path $PSScriptRoot 'payload\seedvc\capture_ref.py'
        if ((Test-Path $voicePy) -and (Test-Path $capture)) {
          Write-Info '尝试复用鲸鲸现有语音生成参考音（需要鲸鲸/微信在运行，文件传输助手会收到测试语音）'
          & $voicePy $capture --runtime-root $Root --whale-girl $wg
          if ($LASTEXITCODE -eq 0) { $done = $true; Write-Info '已用鲸鲸现有语音生成参考音' }
          else { Write-Host '复用鲸鲸语音失败，回退 Windows 本地 TTS' -ForegroundColor Yellow }
        }
      }
      if (-not $done) {
        $extra = @()
        if ($BreezeKey) { $extra = @('--breeze-key', $BreezeKey) }
        & $py $script --runtime-root $Root --whale-girl $wg --ffmpeg $ffmpeg @extra
        if ($LASTEXITCODE -ne 0) { throw '参考音生成失败' }
      }
    } },
  @{ Id = 'songs'; Name = '默认测试歌曲'; Action = {
      $src = Join-Path $PSScriptRoot 'payload\songs'
      if (Test-Path $src) {
        $dst = Join-Path $Root 'data\songs'
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Copy-Item (Join-Path $src '*') $dst -Force
        Write-Info ('已放入默认测试歌曲：' + ((Get-ChildItem $dst -File | Select-Object -First 3 -ExpandProperty Name) -join '、'))
      }
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
      & node $cli list --json | Out-Null
      if ($LASTEXITCODE -ne 0) { throw 'cover.mjs 自检失败' }
      $cuda = & $py -c "import torch;print(torch.cuda.is_available())" 2>$null
      Write-Info ('冒烟通过；CUDA=' + $cuda)
    } }
)

Write-Host 'Breezeblue 翻唱运行时安装器 1.0.4' -ForegroundColor Green
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
  if ((Test-Done $state $step.Id) -and -not ($step.Id -eq 'reference' -and $UseInstalledVoice)) { Write-Info '已完成，跳过'; continue }
  try {
    & $step.Action
    if ($step.Id -eq 'env') { }
    Mark-Done $state $step.Id 'ok'
  } catch {
    Fail ($step.Name + ' 失败：' + $_.Exception.Message)
  }
}

Write-Host ''
Write-Host 'P1 检查结束。下一步由 P2 实现真实下载与安装。' -ForegroundColor Green
