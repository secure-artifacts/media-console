@echo off
chcp 65001 >nul
title 媒体控制台 - 纯净打包与自动清理脚本

echo =======================================================
echo        开始配置纯净隔离环境并打包媒体控制台
echo =======================================================
echo.

:: 1. 创建隔离的虚拟环境
if not exist "venv" (
    echo [1/4] 正在创建干净的 Python 虚拟环境...
    python -m venv venv
) else (
    echo [1/4] 发现已存在的虚拟环境，准备清理后重新挂载...
    rmdir /s /q venv
    python -m venv venv
)

:: 2. 激活虚拟环境
call venv\Scripts\activate

:: 3. 安装所需的原生海外开源依赖包 (强制指定海外官方源 https://pypi.org/simple/)
echo.
echo [2/4] 正在连接官方海外节点，下载并安装所有依赖库...
python -m pip install --upgrade pip -i https://pypi.org/simple/

:: 安装核心UI、播放器、打包工具、yt-dlp 以及【新增的 Google Drive API 依赖】
pip install -i https://pypi.org/simple/ PySide6 python-vlc pyinstaller Pillow yt-dlp google-api-python-client google-auth-httplib2 google-auth-oauthlib

:: 4. 开始打包
echo.
echo [3/4] 开始执行 PyInstaller 核心打包程序...
pyinstaller --noconfirm ^
            --windowed ^
            --onefile ^
            --name "MediaConsole" ^
            --icon="iii.png" ^
            --add-data="iii.png;." ^
            --hidden-import yt_dlp ^
            --hidden-import googleapiclient ^
            "媒体播放器_最终版_串联播放_录音版.py"

echo.
echo [4/4] 正在清理所有临时文件和虚拟环境，请稍候...

:: 退出虚拟环境（解除文件占用锁定）
call venv\Scripts\deactivate.bat 2>nul

:: 将生成的 exe 文件从 dist 文件夹中提取到脚本所在目录
move /y "dist\MediaConsole.exe" "%~dp0MediaConsole.exe" >nul

:: 彻底删除打包产生的编译缓存和中间产物
rmdir /s /q build
rmdir /s /q dist
del /f /q MediaConsole.spec

:: 彻底销毁 Python 虚拟环境（文件较多，可能需要几秒钟）
rmdir /s /q venv

echo.
echo =======================================================
echo 打包与清理任务全部完成！
echo =======================================================
echo 现场已清理干净，你的独立软件 [MediaConsole.exe] 已生成在当前目录。
echo.
echo ⚠️ 提示：如果要使用网盘自动上传功能，请确保【credentials.json】
echo 和生成的 exe 软件存放在同一个文件夹内。
echo.
pause