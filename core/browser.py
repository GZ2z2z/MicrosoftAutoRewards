# -*- coding: utf-8 -*-
"""
核心浏览器驱动模块 (Microsoft Edge / Google Chrome 双引擎驱动封装与反检测配置)
"""

import os
import sys
import time
import random
from pathlib import Path
from typing import Optional

# 强制 Windows 控制台以 UTF-8 输出，防止 Emoji 和中文字符引发 UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 获取项目根目录与持久化用户会话目录
ROOT_DIR = Path(__file__).resolve().parent.parent

def get_default_profile_dir() -> Path:
    old_profile = ROOT_DIR / "edge_profile"
    if old_profile.exists() and any(old_profile.iterdir()):
        return old_profile
    return ROOT_DIR / "browser_profile"

DEFAULT_PROFILE_DIR = get_default_profile_dir()

def detect_available_browser() -> str:
    """
    智能检测系统中可用的 Chromium 内核浏览器:
    检测 Edge，如果不存在或已卸载则回退到 Chrome。
    """
    edge_paths = [
        os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\Application\msedge.exe"),
    ]
    for ep in edge_paths:
        if os.path.exists(ep):
            return "edge"

    chrome_paths = [
        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
    ]
    for cp in chrome_paths:
        if os.path.exists(cp):
            return "chrome"

    return "edge"

def release_profile_locks(profile_dir: Path):
    """
    启动前安全释放目标 Profile 目录的占用:
    1. 结束仅属于当前项目历史遗留的自动化 Chrome / Edge 孤儿进程 (不影响用户日常开启的正常浏览器)
    2. 清理残留的 lockfile / SingletonLock，彻底杜绝 DevToolsActivePort doesn't exist / crashed 错误
    """
    if sys.platform == "win32":
        try:
            import subprocess
            dir_str = str(profile_dir.resolve()).replace("\\", "\\\\")
            ps_script = (
                "$procs = Get-CimInstance Win32_Process | Where-Object { "
                "($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') -and "
                f"($_.CommandLine -like '*{dir_str}*' -or $_.CommandLine -like '*Microsoft_rewards*' -or $_.CommandLine -like '*MicrosoftRewards*') "
                "}; "
                "foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script], capture_output=True, timeout=5)
        except Exception:
            pass

    # 清理残留的 lockfile
    for lock_name in ["lockfile", "SingletonLock", "SingletonSocket", "SingletonCookie"]:
        lock_file = profile_dir / lock_name
        if lock_file.exists():
            try:
                lock_file.unlink(missing_ok=True)
            except Exception:
                pass

def get_browser_driver(headless: bool = False, profile_dir: str = None, browser: str = "auto"):
    """
    初始化并返回配置完善的 WebDriver 实例 (支持 Edge / Chrome 自动探测与智能降级)
    - 采用独立 Profile 目录，永久保留登录状态且不与日常浏览器冲突
    - 注入反检测配置，隐藏 webdriver 自动化标记
    - Chrome 模式下注入 Edge UA，确保微软 Rewards 平台完美兼容并享受打卡加成
    """
    target_profile = Path(profile_dir) if profile_dir else get_default_profile_dir()
    target_profile.mkdir(parents=True, exist_ok=True)

    # 启动前排查并解除可能存在的进程锁与 lockfile
    release_profile_locks(target_profile)

    def build_options(is_chrome: bool):
        opts = ChromeOptions() if is_chrome else EdgeOptions()
        opts.add_argument(f"--user-data-dir={target_profile.resolve()}")
        opts.add_argument("--window-size=1366,900")
        opts.add_argument("--start-maximized")
        opts.add_argument("--lang=zh-CN")

        # 核心防崩溃与环境兼容
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")

        # 反检测核心配置
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        # 性能与磁盘优化
        opts.add_argument("--log-level=3")
        opts.add_argument("--disable-infobars")
        opts.add_argument("--disable-notifications")
        opts.add_argument("--disable-popup-blocking")
        opts.add_argument("--disk-cache-size=10485760")
        opts.add_argument("--media-cache-size=10485760")
        opts.add_argument("--disable-component-update")
        opts.add_argument("--no-default-browser-check")
        opts.add_argument("--no-first-run")

        if is_chrome:
            # 注入 Edge UA 伪装，确保微软识别为 Edge 享受打卡及搜索奖励
            opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")
        else:
            opts.add_argument("--disable-features=msEdgeWallet,EdgeShopping,msEdgeEntityExtraction,msEdgeSidebarV2")

        if headless:
            opts.add_argument("--headless=new")
            opts.add_argument("--disable-gpu")

        return opts

    chosen_browser = browser.lower()
    if chosen_browser == "auto":
        chosen_browser = detect_available_browser()

    driver = None
    # 尝试启动指定/探测到的浏览器
    if chosen_browser == "chrome":
        try:
            print("🌐 [引擎选择] 正在启动 Google Chrome 浏览器 (已自动配置 Edge 伪装)...")
            options = build_options(is_chrome=True)
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            print(f"[错误] Chrome 驱动初始化失败: {e}")
            raise e
    else:
        try:
            print("🌐 [引擎选择] 正在启动 Microsoft Edge 浏览器...")
            options = build_options(is_chrome=False)
            driver = webdriver.Edge(options=options)
        except Exception as edge_err:
            print(f"[提示] 未能成功启动 Edge 浏览器: {edge_err}")
            print("🔄 正在尝试自动切换降级至 Google Chrome 浏览器...")
            try:
                options = build_options(is_chrome=True)
                driver = webdriver.Chrome(options=options)
                print("✓ 成功切换至 Google Chrome 驱动！")
            except Exception as chrome_err:
                print(f"[错误] Chrome 驱动回退启动也失败: {chrome_err}")
                print("[提示] 请确保系统已安装 Microsoft Edge 或 Google Chrome 浏览器。")
                raise edge_err

    # 执行 CDP 命令彻底抹除 navigator.webdriver 标识
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(document, 'hidden', {
                    get: () => false
                });
                Object.defineProperty(document, 'visibilityState', {
                    get: () => 'visible'
                });
                """
            }
        )
    except Exception:
        pass

    return driver

# 保持向后兼容性别名
get_edge_driver = get_browser_driver


def human_sleep(min_sec: float = 2.0, max_sec: float = 4.0):
    """人类行为特征的随机微暂停"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def simulate_scroll(driver, steps: int = 3):
    """平滑滚动页面，模拟人类阅读以触发所有懒加载与发分信标"""
    try:
        total_height = driver.execute_script("return Math.max(document.body.scrollHeight, 1200);")
        step_height = total_height // max(1, steps)
        current = 0
        for _ in range(steps):
            current += step_height + random.randint(-40, 60)
            driver.execute_script(f"window.scrollTo({{top: {current}, behavior: 'smooth'}});")
            time.sleep(random.uniform(0.6, 1.2))
        
        # 滚回上半部
        driver.execute_script("window.scrollTo({top: 200, behavior: 'smooth'});")
        time.sleep(0.5)
    except Exception:
        pass


def switch_to_new_tab(driver, original_window):
    """切换至新打开的标签页"""
    windows = driver.window_handles
    for w in windows:
        if w != original_window:
            driver.switch_to.window(w)
            return True
    return False


def close_tab_and_return(driver, original_window):
    """安全关闭当前任务标签页并切回主页面"""
    try:
        if driver.current_window_handle != original_window:
            driver.close()
    except Exception:
        pass
    try:
        driver.switch_to.window(original_window)
    except Exception:
        if len(driver.window_handles) > 0:
            driver.switch_to.window(driver.window_handles[0])
