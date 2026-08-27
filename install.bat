@echo off
chcp 65001 >nul
title 小铃铛桌宠 - 一键安装
echo ============================================
echo   小铃铛桌宠 - 一键安装依赖
echo ============================================
echo.
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 没找到 Python。请先安装 Python 3.10 以上版本，
    echo        安装时勾选 "Add python.exe to PATH"。
    echo        下载地址：https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [1/2] 创建虚拟环境 .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败。
        pause
        exit /b 1
    )
) else (
    echo [1/2] 虚拟环境已存在，跳过。
)

echo [2/2] 安装依赖（用阿里云镜像加速）...
".venv\Scripts\python.exe" -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --timeout 120

echo.
echo ============================================
echo   安装完成！双击 run.bat 启动桌宠。
echo   首次使用：右键桌宠 -^> 设置 -^> 填 AI 的 API Key。
echo ============================================
echo.
pause
