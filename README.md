# Breezeblue 翻唱运行时安装器

给**原版鲸鲸 4.1.2+** 安装翻唱功能：点歌后自动找音源、切 30 秒副歌、用 seed-vc 换成指定音色，再发成微信语音。

> 最新安装包：<../../releases/latest>

## 0. 最快安装（照着做）

| 步骤 | 做什么 | 大约耗时 |
| --- | --- | --- |
| 1 | 下载 `Breezeblue-Sing-Installer-*.zip`，右键**全部解压**到普通文件夹 | 1 分钟 |
| 2 | 右键 `install.cmd` → **以管理员身份运行**，等它下载完 | 20–60 分钟 |
| 3 | 重启电脑 | 2 分钟 |
| 4 | 设置声音：输出 `CABLE Input`，输入 `CABLE Output` | 2 分钟 |
| 5 | 启动鲸鲸，启用插件，私聊发 `点歌 see you again` | 8–15 分钟出成品 |

后面是详细说明；第一次装建议完整看一遍第 1–6 节。

---

## 1. 安装前确认

- [ ] Windows 10/11 64 位
- [ ] NVIDIA 显卡（建议 6GB 显存以上）
- [ ] 微信电脑版 **4.2**（当前只保证这个版本）
- [ ] 鲸鲸 **4.1.2 或更高**，并且能正常启动
- [ ] 磁盘可用空间 **10GB 以上**（C 盘不够会自动换到空间最大的盘）
- [ ] 安装时需要管理员权限
- [ ] 装完需要重启一次（VB-CABLE 驱动）

> 不需要提前安装原版 breeze 翻唱插件；安装器会装新的 `breezeblue-sing`。

## 2. 下载与解压

1. 打开上面的 Releases 页面，下载最新的 `Breezeblue-Sing-Installer-*.zip`。
2. 右键 ZIP → **全部解压**，解压到普通文件夹，例如 `D:\Breezeblue`。
3. **不要**直接在压缩包里双击运行。

## 3. 安装

1. 进入解压后的文件夹，右键 `install.cmd` → **以管理员身份运行**。
   - 也可以双击 `Setup.cmd`，它会自动请求管理员权限。
   - 如果被安全软件拦截，选择允许；仍不行就右键 `install.cmd` 以管理员运行。
2. 黑窗口会开始下载，约 8–10GB。**不要关闭窗口**。
   - 断网/失败后重新运行 `install.cmd`，会继续下载。
   - 下载慢可以先开代理；安装器会使用系统代理。
3. 如果窗口提示输入鲸鲸目录，填你的鲸鲸安装文件夹，例如：
   ```
   D:\WhaleGirl
   ```
   （路径下应该有 `data\config.json`）
4. 全部完成后按提示重启电脑。
5. 重启后可以检查安装：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\verify.ps1
   ```
   看到“全部检查通过”即可。

**装完的目录**：默认 `%USERPROFILE%\whale-cover`；如果 C 盘空间不足，会自动装到空间最大的盘，例如 `D:\whale-cover`。

## 3.5 鲸鲸装在带中文/空格的路径怎么办

如果鲸鲸装在类似 `D:\我的软件\whaleGirl` 的路径，安装器会自动扫描各盘根目录和浅层子目录（最多两层），通常能直接找到。

如果没找到：

1. 安装窗口会提示“鲸鲸安装目录”，直接粘贴完整路径，例如：
   ```
   D:\我的软件\whaleGirl
   ```
   然后回车。
2. 也可以带参数运行：
   ```bat
   install.cmd -WhaleGirl "D:\我的软件\whaleGirl"
   ```
3. 确认该路径下确实有 `data\config.json`。

路径可以包含中文和空格；手动在 PowerShell 里运行时，用双引号把路径包起来即可。

## 4. 设置声音（必须，否则语音没声）

安装器用 VB-CABLE 把电脑播放的声音送进微信麦克风，需要设置一次：

1. 右键任务栏右下角小喇叭 → **声音设置**。
2. **输出**：选择 `CABLE Input`。
3. **输入**：选择 `CABLE Output`。
4. 打开微信 → 设置 → 通用设置/音视频，确认麦克风是“系统默认”。
5. 验证：用微信录一段语音，说话时电脑播放的音乐应该能被录进去。

> 如果不设置，插件发语音时微信会录到环境音或静音。

## 5. 启动鲸鲸并启用插件

1. 启动鲸鲸，确认内核和桥接都显示运行中。
2. 打开「插件市场 → 已安装」，找到 **Breezeblue 翻唱（本地发送器版）**。
3. 启用它，确认 `system.full` 权限。
4. **如果你以前装过旧的 `breeze-sing`（Breezeblue 翻唱 0.6.3）**：请把它停用，避免两个插件同时抢点歌。
5. 打开新插件的「设置」，确认路径是本机实际路径（如 `D:\whale-cover\...`）。
6. 如果鲸鲸内核在装插件前就已启动，**重启一次内核**。

## 6. 第一次点歌

1. 私聊机器人，发送：
   ```
   点歌 see you again
   ```
2. 应该立刻收到：`是《see you again》对吧，我先找原曲～`
3. 首次渲染约 8–15 分钟；完成后会发 30 秒语音，约 12 秒后再补一句“我唱了《see you again》，你觉得好听吗？”。
4. 发送语音时**微信要保持在最前面**；窗口被切走会失败并提示，不会发错人。

---

## 7. 可选：网易云会员曲目（cookie）

不配置也能用免费音源和本地歌曲；配置后可以下载会员曲目。

### 导出 cookie

1. 用 Chrome / Edge 打开 `https://music.163.com` 并登录。
2. 安装 cookie 导出扩展，例如：
   - Chrome/Edge 扩展商店搜索 **Get cookies.txt LOCALLY**
3. 在网易云页面点扩展图标 → **Export**，得到 `cookies.txt`（Netscape 格式）。
4. 把文件保存到运行时目录，例如：
   ```
   D:\whale-cover\cookies.txt
   ```
   （默认运行时在 `%USERPROFILE%\whale-cover\cookies.txt`）

### 让插件使用

1. 打开插件卡片「设置」。
2. 把 `neteaseCookies` 填成上面的完整路径，例如：
   ```
   D:\whale-cover\cookies.txt
   ```
3. 保存后重新点歌即可。

### 注意

- 插件只保存 cookie 文件**路径**，不保存内容、不上传。
- 部分版权曲（例如某些原版）即使有会员也没有 API 下载地址；这种只能把音频放进 `data\songs` 当本地歌曲。
- cookie 会过期，失效后重新导出覆盖即可。

## 8. 可选：参考音（决定“像不像”）

参考音决定翻唱像谁。安装器默认用 **Windows 本地 TTS** 自动生成 6 段参考音，装完即可用，但音色和鲸鲸语音不完全一样。

### 方案 A：默认（零配置）

安装器已自动完成，`ref\profiles\` 下有 `voice_*.wav`。直接点歌即可。

### 方案 B：复用鲸鲸已有语音（不需要 API Key，实验）

前提：鲸鲸在运行、微信已登录、语音发送已启用、CABLE 已设置。

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -OnlyStep reference -UseInstalledVoice
```

它会：

1. 让鲸鲸给文件传输助手发一条短语音，把会话切过去；
2. 再发一条约 30 秒 TTS；
3. 同时录 `CABLE Output`，生成参考音。

文件传输助手会收到测试语音，介意可手动删除。微信会话被切换时会失败，失败自动回退 Windows TTS。

### 方案 C：用自己的 Breeze API Key（音色最接近）

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -OnlyStep reference -BreezeKey "你的 Key"
```

### 方案 D：导入自己的参考音

1. 准备 6 个 wav（日常/开心/温柔/认真/难过/生气），每个 10–30 秒干净人声；
2. 命名 `voice_daily.wav`、`voice_happy.wav`、`voice_gentle.wav`、`voice_serious.wav`、`voice_sad.wav`、`voice_angry.wav`；
3. 放进 `ref\profiles\`，保留或重新生成 `profiles.json`；
4. 重新点歌。

## 9. 可选：主动唱歌

插件设置里可调：

| 设置 | 作用 | 默认 |
| --- | --- | --- |
| `proactiveEnabled` | 是否主动唱歌 | true |
| `proactiveIdleMinutes` | 微信空闲多少分钟后触发 | 120 |
| `proactiveDailyMax` | 每天最多几首 | 2 |
| `proactiveQuietStart` / `proactiveQuietEnd` | 静默时段 | 22:30–09:00 |
| `proactiveCooldownMinutes` | 两次之间至少隔多久 | 360 |
| `downloadCandidates` | 本地唱完后从网上找的候选歌 | 晴天/后来/小幸运 |

## 10. 常见问题

| 现象 | 处理 |
| --- | --- |
| 窗口一闪而过 | 用最新安装包；右键 `install.cmd` 管理员运行；还不行就看 `installer.log` 或截图错误 |
| 提示找不到鲸鲸 | 手动输入路径，如 `D:\WhaleGirl`（下面要有 `data\config.json`） |
| 下载慢/中断 | 开代理后重跑 `install.cmd`，会续传 |
| 点歌没反应 | 确认插件已启用、JS 插件总闸开启、内核重启过、旧插件已停用 |
| 语音没声音/环境音 | 检查第 4 节：输出 `CABLE Input`、输入 `CABLE Output` |
| 语音发送失败 | 微信必须在**最前面**；不要最小化或切到别的窗口 |
| CUDA 报错 | 更新 NVIDIA 驱动；6GB 显存成品建议 30 秒，不要超 |
| 参考音不像 | 用第 8 节方案 B/C/D 换参考音 |

## 11. 升级 / 卸载

- **升级**：下载新安装包，直接覆盖安装；已完成的运行时会跳过，不会重复下载。
- **停用**：插件市场里禁用插件即可。
- **卸载**：禁用插件 → 删除运行时目录（默认 `%USERPROFILE%\whale-cover`，或你安装时选的盘）→ 在“应用和功能”里卸载 VB-CABLE。
- 安装器在鲸鲸 `data\backup-sing-installer-*` 里保留了插件/配置备份，可回滚。

## 12. 安全与隐私

- 安装器不包含任何人的 API Key、cookie、人设、聊天记录；
- 参考音只在你要生成时读取本机鲸鲸配置，不打包、不上传；
- 插件通过 Windows UIA 操作微信发送语音，发送前会核验会话；
- 第三方项目，请自行评估风险。

## 13. 安装包校验

下载后可以核对 SHA-256（Release 说明里有对应值）：

```powershell
Get-FileHash .\Breezeblue-Sing-Installer-*.zip -Algorithm SHA256
```
