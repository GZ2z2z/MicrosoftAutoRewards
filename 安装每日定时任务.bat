@echo off
chcp 65001 >nul
title 设置 Microsoft Rewards 每日定时打卡任务
cd /d "%~dp0"

echo ============================================================
echo   ⏰ 设置 Microsoft Rewards 每日自动定时打卡任务
echo ============================================================
echo.
echo 请输入每天希望自动执行打卡的时间：
echo   • 格式支持：8.30 (代表 8:30) 或直接输入 8:30、09:00、12.00 等
echo   • 直接按【回车键 (Enter)】使用默认时间 [ 8.30 / 08:30 ]
echo.
set "TASK_TIME="
set /p "TASK_TIME=请输入打卡时间 (直接回车默认 8.30): "

if "%TASK_TIME%"=="" set "TASK_TIME=8.30"

echo.
echo 正在配置 Windows 计划任务 (设定时间: %TASK_TIME%)...
call run.bat --install-task --time "%TASK_TIME%"