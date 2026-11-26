# 应用方式

把本目录复制到鲸鲸/Breezeblue 运行时根目录下的 `a-card`，然后以管理员 PowerShell 运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\a-card\setup.ps1 -RuntimeRoot "D:\whale-cover"
```

`setup.ps1` 会安装 torch-directml、替换 render/inference 两个文件并生成诊断日志。测试反馈只看 `data\logs\a-card-diagnostics.log` 和 `collect.ps1` 打出的 zip。

仓库内容不包含模型、聊天、账号、cookies 或运行时数据。
