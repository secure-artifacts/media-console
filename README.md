# MediaConsole 视频播放器

基于 Python、PySide6 和 libVLC 的 Windows 桌面媒体播放器，支持播放列表、区段串联播放、录音和可选的 Google Drive 上传。

## 使用方法

1. 安装 [VideoLAN 官方 64 位 VLC](https://www.videolan.org/vlc/)。播放器依赖其 libVLC，本项目发布包不包含 VLC。
2. 从本仓库 Releases 下载 `MediaConsole.exe`，放入可写目录后运行。
3. Google Drive 上传为可选功能：使用自己的桌面 OAuth 客户端配置 `credentials.json`，授权后生成 `token.json`。这些文件只保存在本机，不要分享或提交。
4. 录音、播放列表及 `MediaConsoleConfig.ini` 属于个人数据，不随软件发布。

当前发布目标为 Windows x64。来源证明用于验证构建来源，不等同于 Windows Authenticode 签名或平台审核通过。

## 从源码运行和构建

安装 Python 3.14 x64 和 VLC x64，在项目目录打开 PowerShell：

```powershell
python -m venv .venv-build
.\.venv-build\Scripts\python -m pip install -r requirements-build.txt
.\.venv-build\Scripts\python '媒体播放器_最终版_串联播放_录音版.py'
```

打包命令与 CI 一致：

```powershell
.\.venv-build\Scripts\python -m PyInstaller --noconfirm --clean --windowed --onefile --name MediaConsole --icon iii.png --add-data 'iii.png;.' --hidden-import yt_dlp --hidden-import googleapiclient '媒体播放器_最终版_串联播放_录音版.py'
```

输出为 `dist/MediaConsole.exe`。构建只显式打包图标，不打包本机 OAuth 凭据或录音数据。

## 如何发布新版本

GitHub Actions 在推送 `v` 开头的 tag 后自动构建、生成 Attestation，并由 GitHub Actions 上传 Release。

### 1. 提交代码

先查看变更，确认没有凭据和个人数据，再提交需要发布的文件：

```powershell
git status
git add README.md requirements.txt requirements-build.txt .github .gitignore '媒体播放器_最终版_串联播放_录音版.py' iii.png
git diff --cached --stat
git commit -m '说明本次修改'
git push origin main
```

### 2. 创建并推送新版本

以下以 `v1.0.1` 为例，每个已成功发布的版本使用新的版本号：

```powershell
git tag -a v1.0.1 -m 'Release version 1.0.1'
git push origin v1.0.1
```

到仓库 Actions 页面查看构建进度，成功后到 Releases 下载。
重大不兼容改动增加主版本；新增功能增加次版本；修复增加修订版本。

### 3. 验证来源

安装 GitHub CLI 后，对下载的文件执行：

```powershell
gh attestation verify .\MediaConsole.exe --repo secure-artifacts/media-console
```

### 构建失败处理

先查看 Actions 日志，修复代码或 `.github/workflows/release.yml` 并提交推送。
仅对尚未成功发布的失败 tag，按安全发布平台要求删除并重建：

```powershell
git tag -d v1.0.1
git push origin :refs/tags/v1.0.1
git tag -a v1.0.1 -m 'Release version 1.0.1'
git push origin v1.0.1
```

不要手动上传或替换 Release 产物，否则来源校验可能失败。
