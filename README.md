# Breezeblue 翻唱运行时安装器

安装器 1.0.17 包含插件 1.0.4。已有运行时可执行 install.cmd -OnlyStep plugin -ForceSteps plugin 覆盖插件、CLI、语音发送器、音源准备和整首渲染脚本，保留原设置与模型；随后在插件市场重新确认完整权限。升级会备份新旧插件安装文件。本版不附带测试曲，把有权使用的音频放入 data/songs 即可。

给**原版鲸鲸 4.1.2+** 安装翻唱功能：普通点歌用 seed-vc 渲染整首，在人声停顿附近切分为多条微信语音。

> 最新安装包：[下载最新安装包](https://github.com/RacOrange/breezeblue-sing-installer/releases/latest)

## 0. 最快安装（照着做）

| 步骤 | 做什么 | 大约耗时 |
| --- | --- | --- |
| 1 | 下载 `Breezeblue-Sing-Installer-*.zip`，右键**全部解压**到普通文件夹 | 1 分钟 |
| 2 | 右键 `install.cmd` → **以管理员身份运行**，等它下载完 | 20–60 分钟 |
| 3 | 重启电脑 | 2 分钟 |
| 4 | 设置声音：输出 `CABLE Input`，输入 `CABLE Output` | 2 分钟 |
| 5 | 启动微信和鲸鲸，启用插件，补做方案 B 参考音 | 按安装提示操作 |
| 6 | 把歌曲放入 `data/songs`，私聊发 `点歌 歌名` | 取决于歌曲长度和显卡 |

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

## 5.5 插件设置 JSON 怎么填

插件卡片的「设置」是一个 JSON 输入框。**只装在本机默认目录时，留 `{}` 也能用**；私聊点歌默认开启，需要变更时建议直接填下面这份（把 `你的用户名` 换成自己的 Windows 用户名）：

```json
{
  "coverCli": "C:\\Users\\你的用户名\\whale-cover\\tools\\cover.mjs",
  "python": "C:\\Users\\你的用户名\\whale-cover\\engine\\venv\\Scripts\\python.exe",
  "ffmpeg": "C:\\Users\\你的用户名\\whale-cover\\tools\\ffmpeg",
  "dataDir": "C:\\Users\\你的用户名\\whale-cover\\data",
  "voicePython": "C:\\Users\\你的用户名\\whale-cover\\voice\\venv\\Scripts\\python.exe",
  "voiceSender": "C:\\Users\\你的用户名\\whale-cover\\voice\\send_cover.py",
  "neteaseCookies": "C:\\Users\\你的用户名\\whale-cover\\cookies.txt",
  "engine": "seedvc",
  "maxSeconds": 30,
  "onlyGroup": false,
  "autoRender": true,
  "proactiveEnabled": false,
  "proactiveIdleMinutes": 120,
  "proactiveDailyMax": 2,
  "proactiveQuietStart": "22:30",
  "proactiveQuietEnd": "09:00",
  "proactiveCooldownMinutes": 360,
  "proactiveAllowDownload": false, "proactiveDownloadCandidates": []
}
```

- 路径必须用**双反斜杠** `\\` 或正斜杠 `/`；
- `onlyGroup: false` 表示私聊也接管点歌；
- 保存后发 `点歌帮助` 验证；
- 安装器写入的运行时在哪个盘，就把路径换成那个盘（例如 `D:\\whale-cover`）。


1. 私聊机器人，发送：
   ```
   点歌 加入的歌名
   ```
2. 应该立刻收到：`是《see you again》对吧，我先找原曲～`
3. 整首渲染耗时随歌曲长度、模型和显卡而变化。发送时请确认微信前台、绑定账号及语音输入，并查看是否出现新语音条。
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

## 8. 首次参考音设置

新安装默认进入方案 B，复用鲸鲸已经设置好的语音。鲸鲸和微信应处于运行状态，绑定账号、语音开关和 VB-CABLE 都要就绪。安装器说明测试语音会进文件传输助手，并等用户明确确认。无人值守安装会把参考音留作待配置。

就绪后可执行 `install.cmd -OnlyStep reference -UseInstalledVoice`。方案 B 失败时保留旧文件并提示原因，不回退到 Windows TTS。已经可用的鲸鲸参考音或自行导入的 WAV 会继续保留。想自行导入时，把参考音及对应清单放入 `ref/profiles`。用 Breeze API 的用户可显式选 C。

正在播放其他电脑声音时，先暂停其它音源再录参考音。当前参考音的合成与录音仍需在实际微信及音频设备上验收。

### 安装好以后，唱一首试试

1. 在运行时的 `data\songs` 放入一首你有权使用的音频，并把文件名改成歌名。
2. 确认鲸鲸内核、微信桥接和插件均已启用。在自己的微信私聊发「点歌 样例曲」，用「点歌单」看进度。
3. 整首制作完成后，原版鲸鲸 4.1.8.2 会按停顿发送分段语音。具备长歌 WAV 附件能力的宿主会问要整首文件还是分段语音，可以自然回复「发文件吧」或「分段发吧」。
4. 看到回执不确定时，先核对聊天里的语音条或文件，再按需要播放已有成品。若点歌或参考音配置卡住，先查账号、微信窗口和 VB-CABLE 的音频设备。

更多用法，包括网易云「我喜欢的音乐」、主动唱歌和白名单代发，见 [插件市场使用教程](https://github.com/Banan1cee/whale-girl-plugins/tree/main/plugins/breezeblue-sing)。

## 9. 可选：主动唱歌

启用前停用旧的 breeze-proactive。新版只投递给已绑定并且能唯一核验的主人私聊。插件设置里可调：

| 设置 | 作用 | 默认 |
| --- | --- | --- |
| `proactiveEnabled` | 是否主动唱歌 | false |
| `proactiveIdleMinutes` | 微信空闲多少分钟后触发 | 120 |
| `proactiveDailyMax` | 每天最多几首 | 2 |
| `proactiveQuietStart` / `proactiveQuietEnd` | 静默时段 | 22:30–09:00 |
| `proactiveCooldownMinutes` | 两次之间至少隔多久 | 360 |
| proactiveAllowDownload / proactiveDownloadCandidates | 可选下载开关和歌名数组 | false / 空列表 |

## 10. 常见问题

| 现象 | 处理 |
| --- | --- |
| 窗口一闪而过 | 用最新安装包；右键 `install.cmd` 管理员运行；还不行就看 `installer.log` 或截图错误 |
| 提示找不到鲸鲸 | 手动输入路径，如 `D:\WhaleGirl`（下面要有 `data\config.json`） |
| 下载慢/中断 | 开代理后重跑 `install.cmd`，会续传 |
| 点歌没反应 | 确认插件已启用、JS 插件总闸开启、内核重启过、旧插件已停用；私聊点歌需要设置里 `onlyGroup: false` |
| 语音没声音/环境音 | 检查第 4 节：输出 `CABLE Input`、输入 `CABLE Output` |
| 语音发送失败 | 微信必须在**最前面**；不要最小化或切到别的窗口 |
| 冒烟测试报“无法将 node 项识别为…” | 系统没装 Node 或不在 PATH；新版安装器会改用鲸鲸自带 `runtime\node.exe`，不影响使用，也可以装 Node.js LTS |
| CUDA 报错 | 更新 NVIDIA 驱动；6GB 显存成品建议 30 秒，不要超 |
| 参考音不像 | 按第 8 节重新设置参考音 |

## 11. 升级 / 卸载

### 从 1.0.1 等旧版升级到新版

直接覆盖安装时，旧安装状态会显示“已完成，跳过”，运行时脚本和插件可能不会更新。请用 `-ForceSteps` 指定要重新部署的步骤：

1. 下载新版安装包并解压。
2. 右键 `install.cmd` → 以管理员身份运行，或打开管理员 PowerShell 进入解压目录。
3. 执行：

   ```bat
   install.cmd -ForceSteps voice,seedvc,plugin
   ```

   等价的 PowerShell：

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1 -ForceSteps voice,seedvc,plugin
   ```

| 步骤 | 更新的内容 |
| --- | --- |
| `voice` | 语音发送依赖 + `send_cover.py`（首尾缓冲/淡入淡出） |
| `seedvc` | 渲染脚本 `render_cover.py`、seed-vc 辅助脚本 |
| `plugin` | 市场插件 `breezeblue-sing` |
| `reference` | 重新生成参考音（会覆盖 `ref`，需要时再加） |

- **不要**删除 `.installer-state.json`，否则会重新走全部步骤；
- 模型和 venv 已存在，不会重新下载；
- 升级后重启鲸鲸内核，让插件生效。

### 如果窗口显示“所有步骤均已完成，本次没有修改”

说明旧版本的安装状态还在，这不是新安装完成。按上面的 `-ForceSteps` 升级即可。

### 卸载

- 停用插件即可停止功能；
- 删除运行时目录（默认 `%USERPROFILE%\whale-cover` 或安装时选的盘）；
- 安装器在鲸鲸 `data\backup-sing-installer-*` 里保留了插件/配置备份；
- VB-CABLE 可在“应用和功能”里卸载。


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


## 整首翻唱候选

普通点歌保留整首成品，根据分离后的人声低谷在每条最多约 56 秒的范围内分段。按顺序发送，上一条状态不确定则停止。闲时主动唱歌仍使用短段，优先选本地未唱的歌，并读取旧主动插件歌名记录用于去重。已有 30 秒成品不会自动延长，需重新从原曲点歌。

整首分段、历史去重、暂停及重放防重通过合成测试。实际 Seed-VC 整曲输出、方案 B 录音、微信逐条送达均要在目标机器专项验收。代发唱歌也已进入离线候选，真实群聊和私聊收件仍待授权验证。


## 跨会话代发唱歌

在插件设置中显式打开 relaySingEnabled，并把目标会话的准确微信 ID 加入 relaySingWhitelist。名单可以混合群和私聊。宿主已有代发白名单时，两个名单都必须通过。身份按宿主绑定的账号 ID 核验。目标需要在当前账号的联系人缓存里能唯一定位。

绑定主人在私聊里可说「去「测试群」唱《歌名》」或「把《歌名》唱给爸爸听」。预览会显示目标与歌名，只有同一主人在同一私聊中输入提示的「唱歌确认 六位码」，并且未超过十分钟，才会下单和渲染。普通的「确认」仍属于宿主原有功能。每次分段投递前重新核对联系人和白名单，目标无法核验或语音条无法确认时停发。当前发送器以新控件标识、右侧位置和时长作为送达证据；目标微信版本和布局需要真实验证。

合并候选依赖 Api 4 宿主授予的子进程能力。Windows 上存在额外限制的宿主无法启动音频进程，遇到该限制应使用兼容的原版客户端。

### RTX 50 系列 CUDA 兼容性

安装器读取 NVIDIA 显卡算力。Blackwell 选用 PyTorch 与 TorchAudio 2.7.1 的官方 cu128 Windows 轮子，其他已支持显卡可沿用通过算子验证的环境。安装时会实际执行 GPU 张量计算。旧安装如果报 PyTorch 与显卡不兼容，运行 install.cmd -OnlyStep deps，然后跑完整安装以同步本地渲染与插件文件。第一次安装仍默认进入方案 B，已有可用参考音继续保留。
