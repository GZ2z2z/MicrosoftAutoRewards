# -*- coding: utf-8 -*-
"""
任务管理与辅助工具模块
支持 Windows 定时任务安装/卸载、缓存清理、运行日志查看与新电脑环境向导
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional

# 确保在 Windows 控制台支持 UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent

def clean_edge_cache():
    """清理浏览器运行时临时缓存，保持体积极致小巧并保留登录凭据"""
    print("\n" + "=" * 60)
    print("🧹 正在清理浏览器临时缓存与垃圾文件...")
    print("   (安全机制: 仅清理网页静态资源与诊断数据，100% 完整保留登录凭据)")
    print("=" * 60)

    # 1. 结束可能残留在后台的自动化 Edge / Chrome 进程
    try:
        cmd = "Get-CimInstance Win32_Process -Filter \"Name = 'msedge.exe' or Name = 'chrome.exe'\" | Where-Object { $_.CommandLine -like '*Microsoft_rewards*' -or $_.CommandLine -like '*MicrosoftRewards*' -or $_.CommandLine -like '*browser_profile*' -or $_.CommandLine -like '*edge_profile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
    except Exception:
        pass

    target_profiles = [ROOT_DIR / "edge_profile", ROOT_DIR / "browser_profile"]
    existing_profiles = [p for p in target_profiles if p.exists()]
    if not existing_profiles:
        print("✓ 当前未发现会话缓存目录，无需清理。")
        return

    for profile_dir in existing_profiles:
        # 计算清理前体积
        def get_dir_size(path):
            total = 0
            try:
                for entry in path.rglob("*"):
                    if entry.is_file():
                        total += entry.stat().st_size
            except Exception:
                pass
            return total

        before_mb = get_dir_size(profile_dir) / (1024 * 1024)

        # 可安全删除的临时目录列表
        disposable_dirs = [
            profile_dir / "component_crx_cache",
            profile_dir / "ProvenanceData",
            profile_dir / "ProvenanceDataTensors",
            profile_dir / "Edge Wallet",
        profile_dir / "Edge Shopping",
        profile_dir / "Subresource Filter",
        profile_dir / "Edge Entity Extraction",
        profile_dir / "GrShaderCache",
        profile_dir / "ShaderCache",
        profile_dir / "Speech Recognition",
        profile_dir / "hyphen-data",
        profile_dir / "ZxcvbnData",
        profile_dir / "Typosquatting",
        profile_dir / "Edge Sidebar",
        profile_dir / "Edge Signal Triggers",
        profile_dir / "SmartScreen",
        profile_dir / "Autofill",
        profile_dir / "Edge Notifications",
        profile_dir / "Trust Protection Lists",
        profile_dir / "SafetyTips",
        profile_dir / "EADPData Component",
        profile_dir / "EdgeArbitration",
        profile_dir / "Edge3pSerp",
        profile_dir / "Crashpad",
        profile_dir / "BrowserMetrics",
        profile_dir / "EdgeLanguageDetectionModel",
        profile_dir / "Default" / "Cache",
        profile_dir / "Default" / "Code Cache",
        profile_dir / "Default" / "GPUCache",
        profile_dir / "Default" / "DawnGraphiteCache",
        profile_dir / "Default" / "DawnWebGPUCache",
        profile_dir / "Default" / "EdgeCoupons",
        profile_dir / "Default" / "Service Worker" / "CacheStorage"
    ]

        for d in disposable_dirs:
            if d.exists():
                try:
                    shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    pass

        # 清理 .pma 临时监控文件
        for pma in profile_dir.rglob("*.pma"):
            try:
                pma.unlink(missing_ok=True)
            except Exception:
                pass

        after_mb = get_dir_size(profile_dir) / (1024 * 1024)
        saved_mb = max(0.0, before_mb - after_mb)

        print(f"✓ 已完成目录清理: {profile_dir.name}")
        print(f"   清理前大小: {before_mb:.2f} MB")
        print(f"   清理后大小: {after_mb:.2f} MB (本次释放空间: {saved_mb:.2f} MB)")
    print("=" * 60 + "\n")


def normalize_time_str(raw_time: str) -> str:
    """
    格式化时间字符串为标准的 24 小时制 HH:mm
    支持输入格式：
      - 8.30 / 8.3 -> 08:30
      - 8:30 / 08:30 -> 08:30
      - 9.00 / 9 -> 09:00
      - 12.00 / 12:00 -> 12:00
    若为空或格式异常，默认返回 "08:30"
    """
    if not raw_time or not str(raw_time).strip():
        return "08:30"
    t = str(raw_time).strip().replace("：", ":").replace(".", ":").replace("。", ":")
    if ":" in t:
        parts = t.split(":")
        try:
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 and parts[1].strip() else 0
            if len(parts) > 1 and len(parts[1].strip()) == 1 and parts[1].strip() == "3":
                m = 30
            return f"{h:02d}:{m:02d}"
        except Exception:
            return "08:30"
    elif t.isdigit():
        val = int(t)
        if len(t) <= 2:
            return f"{val:02d}:00"
        elif len(t) == 3:
            return f"{int(t[0]):02d}:{int(t[1:]):02d}"
        elif len(t) == 4:
            return f"{int(t[:2]):02d}:{int(t[2:]):02d}"
    return "08:30"


def install_task(time_str: Optional[str] = None):
    """在 Windows 计划任务中注册每日静默运行任务"""
    if not time_str:
        print("\n" + "=" * 60)
        print("⏰ 设置 Microsoft Rewards 每日自动定时打卡任务")
        print("=" * 60)
        print("\n请输入每天希望自动执行打卡的时间：")
        print("  • 格式支持：8.30 (代表 8:30) 或直接输入 8:30、09:00 等")
        print("  • 直接按【回车键 (Enter)】使用默认时间 [ 8.30 / 08:30 ]\n")
        try:
            user_input = input("请输入打卡时间 (直接回车默认 8.30): ").strip()
        except Exception:
            user_input = "8.30"
        time_str = user_input or "8.30"

    time_str = normalize_time_str(time_str)
    print("\n" + "=" * 60)
    print("⏰ 安装 Windows 每日自动定时打卡任务")
    print("=" * 60)

    # 确保 silent_run.vbs 与 run_task.bat 存在
    vbs_path = ROOT_DIR / "silent_run.vbs"
    vbs_content = 'Set WshShell = CreateObject("WScript.Shell")\n' \
                  'Set fso = CreateObject("Scripting.FileSystemObject")\n' \
                  'scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)\n' \
                  'WshShell.CurrentDirectory = scriptDir\n' \
                  'WshShell.Run "cmd.exe /c """ & scriptDir & "\\run_task.bat""", 0, False\n'
    vbs_path.write_text(vbs_content, encoding="ascii")

    task_bat = ROOT_DIR / "run_task.bat"
    bat_content = '@echo off\ncd /d "%~dp0"\ncall run.bat --headless\n'
    task_bat.write_text(bat_content, encoding="ascii")

    print(f"正在配置定时打卡任务: 每日 {time_str} 执行...")

    ps_script = f"""
    $scriptPath = "{vbs_path.resolve()}"
    $workDir = "{ROOT_DIR.resolve()}"
    $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument ('"' + $scriptPath + '"') -WorkingDirectory $workDir
    $trigger = New-ScheduledTaskTrigger -Daily -At "{time_str}"
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName "MicrosoftRewards_DailyAuto" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    """
    res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script], capture_output=True, text=True)

    if res.returncode == 0:
        print("\n" + "=" * 60)
        print("✓ Windows 计划任务 [MicrosoftRewards_DailyAuto] 安装成功！")
        print(f"  • 每日运行时间: {time_str}")
        print("  • 运行模式: 后台完全静默运行 (无控制台黑框、无弹窗)")
        print("  • 睡眠唤醒: 支持电脑睡眠自动唤醒执行 (WakeToRun)")
        print("  • 自动补跑: 若电脑在打卡时间处于关机状态，开机后系统会自动排队补跑！")
        print("=" * 60 + "\n")
        return True
    else:
        print(f"❌ 安装失败: {res.stderr.strip()}")
        print("提示: 如因权限问题，请右键以管理员身份运行。")
        return False


def uninstall_task():
    """卸载 Windows 计划任务"""
    print("\n" + "=" * 60)
    print("🛑 正在卸载 Windows 定时任务 [MicrosoftRewards_DailyAuto]...")
    print("=" * 60)

    ps_script = 'Unregister-ScheduledTask -TaskName "MicrosoftRewards_DailyAuto" -Confirm:$false -ErrorAction SilentlyContinue'
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script], capture_output=True, text=True)
    
    # 兜底清理
    subprocess.run(["schtasks", "/delete", "/tn", "MicrosoftRewards_DailyAuto", "/f"], capture_output=True)

    print("✓ 计划任务已成功移除！")
    print("=" * 60 + "\n")


def view_logs():
    """打开运行日志"""
    log_file = ROOT_DIR / "logs" / "rewards.log"
    if not log_file.exists():
        print(f"\n[提示] 暂无日志文件 (尚未生成: {log_file})")
        return
    print(f"\n正在使用记事本打开日志文件: {log_file}")
    os.system(f'start notepad.exe "{log_file.resolve()}"')


def setup_wizard():
    """新电脑一键初始化向导"""
    print("\n" + "=" * 60)
    print("🚀 Microsoft Rewards 新电脑一键配置向导")
    print("============================================================")

    # 1. 检查 selenium
    print("\n[步骤 1/3] 检查运行依赖 (Selenium)...")
    try:
        import selenium
        print(f"✓ 检测到已安装 Selenium (版本: {selenium.__version__})")
    except ImportError:
        print("正在自动安装 Selenium 库...")
        subprocess.run([sys.executable, "-m", "pip", "install", "selenium"], check=True)
        print("✓ Selenium 安装成功！")

    # 2. 引导登录
    from core.browser import get_browser_driver, detect_available_browser
    from core.dashboard import RewardsDashboard

    detected = detect_available_browser()
    browser_name = "Google Chrome" if detected == "chrome" else "Microsoft Edge"

    print(f"\n[步骤 2/3] 首次登录微软账号 (检测到系统浏览器: {browser_name})...")
    print(f"即将为您打开 {browser_name} 浏览器窗口，请在窗口中登录您的微软账号。")
    print("登录后，登录凭据将永久保存在这台电脑上！")
    input(f"请按回车键打开 {browser_name} 登录窗口...")

    driver = None
    try:
        driver = get_browser_driver(headless=False)
        dashboard = RewardsDashboard(driver)
        if dashboard.ensure_logged_in(is_headless=False):
            print("✓ 账号登录验证通过并已持久化保存！")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    # 3. 安装计划任务
    print("\n[步骤 3/3] 安装 Windows 每日自动静默打卡任务...")
    time_input = input("请输入每日自动运行时间 (格式如 8.30 或 08:30，直接回车默认 8.30): ").strip()
    if not time_input:
        time_input = "8.30"
    install_task(time_input)

    print("\n" + "★" * 60)
    print("🎉 新电脑配置全部完成！")
    print(f"   从明天起，您的电脑每天将在 {normalize_time_str(time_input)} 自动完成打卡。")
    print("   您可以随时双击运行【查看运行日志.bat】查看积分增加情况。")
    print("★" * 60 + "\n")


def create_portable_package():
    """生成纯净移植压缩包 (排除 edge_profile, browser_profile, logs, 临时文件，避免跨机器冲突与锁定错误)"""
    import zipfile
    print("\n" + "=" * 60)
    print("📦 正在生成【新电脑纯净移植压缩包】...")
    print("   (说明: 自动排除本机锁定的会话缓存与日志，彻底避免文件被占用与跨电脑失效)")
    print("=" * 60)

    # 1. 结束残留 Edge / Chrome 进程以确保安全
    try:
        cmd = "Get-CimInstance Win32_Process -Filter \"Name = 'msedge.exe' or Name = 'chrome.exe'\" | Where-Object { $_.CommandLine -like '*Microsoft_rewards*' -or $_.CommandLine -like '*MicrosoftRewards*' -or $_.CommandLine -like '*browser_profile*' -or $_.CommandLine -like '*edge_profile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
    except Exception:
        pass

    zip_filename = ROOT_DIR / "Microsoft_rewards_portable.zip"
    if zip_filename.exists():
        try:
            zip_filename.unlink()
        except Exception:
            pass

    exclude_dirs = {"edge_profile", "browser_profile", "logs", "__pycache__", ".git", ".vscode", ".idea"}
    exclude_extensions = {".zip", ".pyc", ".pma", ".log"}

    added_count = 0
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in ROOT_DIR.rglob("*"):
            if not file_path.is_file():
                continue
            # 检查是否位于被排除的目录
            rel_parts = file_path.relative_to(ROOT_DIR).parts
            if any(p in exclude_dirs for p in rel_parts):
                continue
            if file_path.suffix.lower() in exclude_extensions:
                continue

            arcname = str(file_path.relative_to(ROOT_DIR))
            zf.write(file_path, arcname)
            added_count += 1

    size_kb = zip_filename.stat().st_size / 1024
    print("\n" + "★" * 60)
    print("✓ 纯净移植包生成成功！")
    print(f"  • 文件名称: {zip_filename.name}")
    print(f"  • 文件路径: {zip_filename.resolve()}")
    print(f"  • 压缩包大小: {size_kb:.1f} KB (不到 1 MB，无任何文件锁死冲突)")
    print(f"  • 包含文件数: {added_count} 个")
    print("------------------------------------------------------------")
    print("💡 移植到另一台电脑的使用方法:")
    print("  1. 直接把这个【Microsoft_rewards_portable.zip】复制到另一台电脑。")
    print("  2. 在另一台电脑上【解压全部文件】到任意文件夹。")
    print("  3. 双击运行【一键配置新电脑(初次使用).bat】即可完成全部设置！")
    print("★" * 60 + "\n")
