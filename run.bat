@echo off
title Microsoft Rewards Runner
cd /d "%~dp0"

set "PYTHONDONTWRITEBYTECODE=1"
set "PY_EXE="

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
) else if exist "C:\Python312\python.exe" (
    set "PY_EXE=C:\Python312\python.exe"
) else if exist "C:\Python311\python.exe" (
    set "PY_EXE=C:\Python311\python.exe"
) else (
    py -3 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "PY_EXE=py -3"
    ) else (
        python -c "import sys" >nul 2>&1
        if not errorlevel 1 (
            set "PY_EXE=python"
        )
    )
)

if not defined PY_EXE (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " ^
      "Write-Host '====================================================================' -ForegroundColor Yellow; " ^
      "Write-Host '[!] 未在系统中检测到 Python 运行环境！' -ForegroundColor Red; " ^
      "Write-Host '    正在为您自动下载并安装 Python 环境...' -ForegroundColor White; " ^
      "Write-Host '====================================================================' -ForegroundColor Yellow; " ^
      "Write-Host '[*] 正在尝试通过 Windows 原生 winget 自动安装 Python 3.12...' -ForegroundColor Cyan; " ^
      "winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements; " ^
      "if ($LASTEXITCODE -eq 0) { " ^
      "    Write-Host '[OK] Python 安装成功！请重新运行本程序。' -ForegroundColor Green; " ^
      "} else { " ^
      "    Write-Host '[*] winget 安装未完成，正在为您打开官方下载页面...' -ForegroundColor Yellow; " ^
      "    Start-Process 'https://www.python.org/downloads/' ; " ^
      "    Write-Host '--------------------------------------------------------------------' -ForegroundColor Gray; " ^
      "    Write-Host '安装提示：在安装窗口底部务必勾选：' -ForegroundColor Yellow; " ^
      "    Write-Host '   [√] Add python.exe to PATH' -ForegroundColor Green; " ^
      "    Write-Host '安装完毕后，再次运行本批处理即可！' -ForegroundColor White; " ^
      "    Write-Host '--------------------------------------------------------------------' -ForegroundColor Gray; " ^
      "}"
    echo.
    pause
    exit /b 1
)

"%PY_EXE%" rewards_runner.py %*

echo %* | findstr /i "\-\-headless" >nul && exit /b 0
echo.
pause