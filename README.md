# Breezeblue 翻唱运行时安装器

为**原版鲸鲸 4.1.2+** 安装翻唱运行时，并自动装好配套插件 `breezeblue-sing`。不修改鲸鲸主程序。

- 下载最新安装器：<https://github.com/RacOrange/breezeblue-sing-installer/releases/latest>
- 安装器会部署：Python/torch/seed-vc/模型/ffmpeg、语音发送器、VB-CABLE、6 个情绪参考音、默认测试歌曲、插件本体。

## 一、电脑要求

- Windows 10/11 64 位
- NVIDIA 显卡（建议 6GB 显存以上）
- 微信电脑版 **4.2**
- 鲸鲸 **4.1.2 或更高**
- 磁盘可用空间 **10GB 以上**（C 盘不够会自动装到空间最大的盘）
- 安装时需要管理员权限；装 VB-CABLE 后需要**重启一次**

## 二、下载与解压

1. 打开上面的 Releases 页面，下载 `Breezeblue-Sing-Installer-1.0.0.zip`。
2. 右键 ZIP → **全部解压**，解压到一个普通文件夹（例如 `D:\Breezeblue`）。
3. **不要**直接在压缩包里双击运行。

## 三、运行安装

1. 进入解压后的文件夹，右键 `install.cmd` → **以管理员身份运行**。
   （也可以双击 `Setup.cmd`，它自己会请求管理员权限；如果弹窗被杀毒软件拦截，改用“以管理员身份运行 install.cmd”。）
2. 会出现一个黑色窗口开始下载，约 **8–10GB**，视网速需要 20–60 分钟。
   - 不要关闭窗口；
   - 断网后重新运行会继续下载；
   - 下载慢时可以先开代理（见常见问题）。
3. 全部完成后，如果提示需要重启，**重启电脑**。
4. 重启后可运行一次检查：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\verify.ps1
   ```
   看到“全部检查通过”即可。

## 四、设置声音设备（必须）

安装器会用 VB-CABLE 把音频送进微信麦克风，需要设置一次：

1. 右键任务栏右下角小喇叭 → **声音设置**。
2. **输出**设备选择 `CABLE Input`。
3. **输入**设备选择 `CABLE Output`。
4. 打开微信 → 设置 → 通用设置/音视频，确认麦克风是系统默认（CABLE Output）。
5. 用微信录一段语音测试：运行时微信应能录到“电脑播放的声音”，而不是真实麦克风。

> 如果不设置，插件发送语音时微信会录到环境音或没有声音。

## 五、启动鲸鲸并确认插件

1. 启动鲸鲸（启动器），确认内核和桥接都显示运行中。
2. 打开「插件市场 → 已安装」，找到 **Breezeblue 翻唱（本地发送器版）**。
3. 如果未启用，点启用并确认 `system.full` 权限。
4. 打开插件卡片「设置」，确认路径是本机实际路径（例如 `D:\whale-cover\...`）；主动唱歌默认开启，可按需修改静默时段/每日上限。
5. 如果鲸鲸内核在装插件前就已启动，重启一次内核让它加载插件。

## 六、首次测试

1. 私聊机器人发：
   ```
   点歌 see you again
   ```
2. 它应立刻回：`是《see you again》对吧，我先找原曲～`
3. 首次渲染约 8–15 分钟；渲染完成后会发 30 秒语音，约 12 秒后补一句“我唱了《see you again》，你觉得好听吗？”。
4. 语音发送时**微信需要在前台**；窗口被切走会失败并提示，不会发到错误的人。

## 七、可选设置

### 网易云会员曲目

1. 浏览器登录 `music.163.com`，用 cookie 导出扩展导出 Netscape 格式的 `cookies.txt`。
2. 保存到 `%USERPROFILE%\whale-cover\cookies.txt`（或安装器实际安装目录，如 `D:\whale-cover\cookies.txt`）。
3. 插件设置的 `neteaseCookies` 指向该文件。
4. 没有 cookie 也能用免费音源和本地歌曲。

### 参考音（音色）

安装器默认用 Windows 本地 TTS 生成 6 个情绪参考音，装完即可用，但音色和鲸鲸语音不完全一致。

想要更接近鲸鲸音色：准备一个 Breeze API Key，然后重新运行安装器的参考音步骤：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -OnlyStep reference -BreezeKey "你的 Key"
```

也可以直接把自己的 `voice_daily.wav` 等 6 个文件替换到 `ref\profiles\` 下（保留 `profiles.json`）。

### 主动唱歌

插件设置里可调：

- `proactiveEnabled`：开关
- `proactiveIdleMinutes`：微信空闲多少分钟触发，默认 120
- `proactiveDailyMax`：每天最多几首，默认 2
- `proactiveQuietStart/End`：静默时段，默认 22:30–09:00
- `proactiveCooldownMinutes`：两次间隔，默认 360

## 八、常见问题

**下载很慢/失败**
- 打开代理后重试（安装器使用系统代理环境变量）；已下载部分会续传。

**verify.ps1 报 ffmpeg/模型缺失**
- 重新运行 `install.cmd`（管理员），它会补齐缺失步骤。

**插件没反应/点歌不接管**
- 确认鲸鲸「功能设置」里 JavaScript 插件总闸已开启；
- 确认插件已启用、设置路径正确；
- 重启鲸鲸内核。

**发送语音失败**
- 微信必须在**前台**；
- 检查声音设备是否按第四节设置；
- 看 `D:\whale-cover\data\work\<单号>\` 和 `data\bridge.log`。

**NVIDIA/CUDA 报错**
- 更新 NVIDIA 驱动；6GB 显存建议成品 30 秒，不要超过。

**杀毒软件拦截**
- 安装器和 VB-CABLE 会被部分安全软件拦截；确认来源后允许。

## 九、卸载/回滚

- 停用插件即可停止功能；
- 删除运行时目录（默认 `%USERPROFILE%\whale-cover` 或安装时选的盘）；
- 安装器在鲸鲸 `data\backup-sing-installer-*` 里保留了插件/配置备份；
- VB-CABLE 可在“应用和功能”里卸载。

## 十、安全说明

- 安装器不包含任何人的 API Key、cookie、人设或聊天数据；
- 插件通过本机 UIA 操作微信发送语音，需要微信前台；发送前会核验会话；
- 本安装器与插件均为第三方项目，使用前请自行评估风险。
