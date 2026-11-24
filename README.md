# Breezeblue 翻唱运行时安装器

独立安装器：为**原版鲸鲸**安装翻唱所需运行时，并把 `breezeblue-sing` 插件接到本地发送器，**不修改鲸鲸主程序**。

## 目标环境

- Windows 10/11 x64
- NVIDIA GPU（建议 ≥6GB 显存）
- 微信 PC 4.2（UIA 自动化）
- 鲸鲸 4.1.2+（原版，未打补丁）
- 磁盘 ≥10GB 可用空间

## 安装器会做什么

| 步骤 | 内容 | 可跳过条件 |
| --- | --- | --- |
| env | 检查系统、管理员、NVIDIA、微信 4.2、鲸鲸路径、磁盘 | — |
| uv | 下载 uv（Python 版本/虚拟环境管理器） | 已有 `uv.exe` |
| python | `uv python install 3.11` + 运行时 venv | venv 已可用 |
| deps | torch 2.4.1+cu121、torchaudio、demucs、librosa、transformers、soundfile、requests、pycryptodome、huggingface_hub 等 | `import torch` 通过 |
| ffmpeg | 下载 BtbN 静态包到 `tools\ffmpeg` | `ffmpeg.exe` 存在 |
| seedvc | 下载 seed-vc 源码 + 本项目补丁文件（inference_local/render_cover 等） | `seed-vc\inference_local.py` 存在 |
| models | 下载 DiT/whisper-small/bigvgan/campplus/rmvpe 模型 | 关键文件存在 |
| voice | 语音发送 venv（uiautomation/sounddevice/soundfile） | 导入通过 |
| vbcable | 下载并静默安装 VB-CABLE | 检测到 CABLE 设备 |
| plugin | 把 `breezeblue-sing` 写入鲸鲸插件数据目录（备份原文件），开启 JS 插件开关 | 已安装同版本 |
| reference | 用鲸鲸当前 Breeze TTS 配置生成 6 情绪参考音 + profiles.json | profiles 已存在 |
| settings | 写入运行时 config.json、插件设置，打印剩余手工步骤 | — |

## 部分依赖已存在时

- `%USERPROFILE%\whale-cover\.installer-state.json` 记录每一步的完成状态和版本；
- 每一步先做**存在性/可用性检测**，已满足就跳过；
- 已有 `data\`（songs/orders/cookies）不会被覆盖；
- 已有 venv 但依赖不全会只补装缺失包；
- VB-CABLE 用设备枚举检测，已安装则不重装；
- 所有下载支持断点续传（`.part` 文件 + Range）。

## 安装后的设置向导

1. 检测微信 4.2 与鲸鲸路径；
2. 检测 NVIDIA 驱动/CUDA 可用性；
3. 确认 VB-CABLE：播放设备选 `CABLE Input`，微信麦克风选 `CABLE Output`；
4. 生成/确认 6 个情绪参考音（从鲸鲸 Breeze TTS 的 `data\voice-send.json` 读取地址/模型/音色，**不复制 Key**，只在本机调用）；
5. 可选填入网易云 `cookies.txt` 路径（VIP 曲目；不下发 cookie 内容）；
6. 单主人/双主人确认（插件内称呼主人/主人1/主人2）；
7. 安装插件并启用 `system.full` 权限；
8. 冒烟测试：点歌 5 秒测试 → 验证“语音 + 追问”。

## 不包含 / 边界

- 不打包鲸鲸主程序、不修改 `src/`、`bridge/`、不替换 EXE；
- 不打包任何人的 API Key、cookie、人设、参考音；
- 微信版本只保证 4.2；升级微信可能破坏 UIA；
- 语音发送期间微信必须前台，发送器会核验会话，失败不重发到错误会话。

## 当前状态（P3 完成 / P4 验证）

- `install.ps1`：环境检测、uv/Python、依赖、ffmpeg、seed-vc、模型、语音 venv、VB-CABLE、插件安装、参考音、设置向导、冒烟测试全步骤；幂等、断点、`-DryRun`。
- `payload/plugin/plugin.js` 0.9.0：直连本地 `send_cover.py`，**不需要鲸鲸宿主补丁**。
- `verify.ps1`：运行时/模型/依赖/CABLE/插件/CLI 共 18 项检查；在当前机器 18/18 通过（复用已有运行时）。
- 待办：干净 Windows 机器实际下载安装（约 8–10GB）、打包 Setup、真实点歌语音冒烟。

```bat
:: 一键安装（自动请求管理员权限，装 VB-CABLE 需要）
Setup.cmd

:: 或只检测，不下载
powershell -ExecutionPolicy Bypass -File .\install.ps1 -DryRun

:: 装完验收
powershell -ExecutionPolicy Bypass -File .\verify.ps1
```
