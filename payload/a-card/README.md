# A 卡 DirectML 兼容层（实验版）

面向 **Windows + AMD Radeon（DirectX 12）** 的 Seed-VC 兼容补丁。

适用目标：

- Radeon RX 6000 / 7000 系列（RDNA2 / RDNA3）优先；
- Windows 10 21H2+ / Windows 11 64 位；
- AMD Adrenalin 24.9.1 或更新驱动；
- Python 3.11；
- 至少 16GB 显存/内存建议，8GB 显卡可能因模型较大而退避。

这不是纯 CPU 方案：检测到 `torch-directml` 时，Seed-VC 换声会走 DirectML（`privateuseone`）。  
`demucs` 人声分离暂时仍使用 CPU；DirectML 目前没有稳定的 demucs 后端。

## 安装

在 Breezeblue/鲸鲸运行时根目录执行（默认 `D:\whale-cover`）：

```powershell
powershell -ExecutionPolicy Bypass -File .\a-card\setup.ps1 -RuntimeRoot "D:\whale-cover"
```

脚本会：

1. 检查 AMD/Intel GPU；
2. 备份 `pip freeze` 和两个要替换的 Python 文件；
3. 安装预发布 `torch-directml`（A 卡环境会替换 CUDA torch）；
4. 把 `render_cover.py` 和 `inference_local.py` 替换为 A 卡兼容版；
5. 运行诊断并生成日志。

如果安装后要回滚，恢复脚本打印的 `.a-card-backup-*` 目录即可。

## 诊断

```powershell
powershell -ExecutionPolicy Bypass -File .\a-card\diagnose.ps1 -RuntimeRoot "D:\whale-cover"
```

日志：

```text
<RuntimeRoot>\data\logs\a-card-diagnostics.log
```

请把日志和你遇到的错误码一起回传。日志只包含系统/显卡/驱动/Python/torch/DirectML 版本、设备名和算子错误，不包含聊天内容。

## 已知限制

- 不保证所有 Seed-VC 算子都被 DirectML 支持；不支持时会抛出明确的 DML 后端错误；
- demucs 分离走 CPU，整首会明显慢于 NVIDIA CUDA；
- 8GB 显卡处理整首歌可能显存不足，先测试 20 秒片段；
- 目前没有 AMD 实机验证，这是给 A 卡网友的测试版，欢迎回报日志。

## 已验证的代码路径

- CUDA 环境继续走原路径；
- 无 CUDA 但 `torch-directml` 可用 → `dml`；
- 两者都没有 → 明确报 `A_GPU_BACKEND_UNAVAILABLE`，不再静默降级 CPU。

## 实测反馈（RX 7800 XT）

- Windows 11 + RX 7800 XT / gfx1101，Python 3.11；
- `torch==2.4.1+cpu`、`torch-directml==0.2.5.dev240914`；
- 单步约 0.4 秒，10 秒片段约 50 秒；
- 关键死锁：`DiT.forward` 的 `sequence_mask` 会触发设备到主机同步，已在 `seed-vc/modules/diffusion_transformer.py` 改为显式 mask；
- flow matching 已禁用 `torch.inference_mode()`、改为非原地拼接；
- mel/stft、RMVPE、Kaldi fbank、F0 量化、BigVGAN 在 DML 下走 CPU；
- 输出落盘做了 -1 dBFS 峰值保护；
- 连续跑两首建议间隔几秒，避免显存未回收 OOM。