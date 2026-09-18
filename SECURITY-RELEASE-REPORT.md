# 安全发布阶段报告

日期：2026-09-18

## 项目信息

- 软件：MediaConsole 视频播放器
- 开发者：姜明（经用户确认）
- 仓库：https://github.com/secure-artifacts/media-console
- 发布：https://github.com/secure-artifacts/media-console/releases/tag/v1.0.0
- 状态：构建发布已完成；审核表单已填写，等待人机验证和提交；尚未获得管理员审核结论。

## 验证记录

- GitHub 账号 jmdx-code 为 secure-artifacts 有效成员；复用 GitHub CLI 认证，浏览器使用 Edge 连接。未安装额外 GitHub/Playwright MCP，未新建 Token。
- 源码 Python 语法编译、构建依赖解析通过。
- 构建运行 35350432071 成功，源码提交 `6e5a044db0c0248a128f093f1d6efb99e8c69b22`。
- Windows x64 文件 `MediaConsole.exe`，90,749,919 字节，上传者 `github-actions[bot]`。
- SHA-256：`ff59689ed83019bda793df0041c5d8774433f0322a5b227c6a419c9395288167`。
- GitHub Attestation 存在；下载最终文件后，使用 `gh attestation verify` 限定仓库、源码提交和 `refs/tags/v1.0.0`，命令退出码为 0。
- CodeQL 最新检查成功；检查时 Code Scanning、Secret Scanning、Dependabot 各 0 个开放告警。扫描结果仅代表检查时状态。
- 密钥扫描、推送保护、依赖告警及自动安全更新已启用。
- 凭据 JSON、录音、播放列表、个人配置、虚拟环境和本地旧 EXE 已被忽略，未进入 Git 提交。

## 已处理问题与限制

- PyPI 公告核对发现原构建依赖 Pillow 12.1.0 有已知漏洞，已升级至 12.3.0（检查时该版本无有效漏洞公告），重新解析依赖并重建。
- 首次运行取消时已创建草稿 Release；修复运行通过 GitHub Actions 更新并正式发布最终产物，未人工上传或替换资产。
- 本次验证覆盖源码语法、云端打包、公开扫描和构建来源；尚未执行完整 GUI 播放、录音及 Google Drive 上传验收。
- 运行需要单独安装 64 位 VLC。GitHub 来源证明不等同于 Windows Authenticode 签名。

## 剩余步骤

1. 在 https://tpscsm-web.pages.dev/submit/review 完成人机验证并提交已填写表单。
2. 提交成功后，将以下消息发给 Teams 管理员（本任务未代发）：

   你好，我已提交 MediaConsole 视频播放器的安全审核申请，请帮忙审核。
   项目链接：https://github.com/secure-artifacts/media-console
   开发者：姜明。谢谢！

3. 等待管理员审核，获得实际结果后再更新最终报告；不能将构建成功视作审核通过。
