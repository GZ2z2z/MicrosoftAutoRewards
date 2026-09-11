# -*- coding: utf-8 -*-
"""
核心浏览器驱动模块 (Microsoft Edge Selenium 驱动封装与反检测配置)
"""

import os
import sys
import time
import random
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 获取项目根目录与持久化用户会话目录
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_DIR = ROOT_DIR / "edge_profile"

def get_edge_driver(headless: bool = False, profile_dir: str = None) -> webdriver.Edge:
    """
    初始化并返回配置完善的 Edge WebDriver 实例
    - 采用独立 Profile 目录，永久保留登录状态且不与日常 Edge 冲突
    - 注入反检测配置，隐藏 webdriver 自动化标记
    """
    options = EdgeOptions()

    # 1. 持久化独立用户数据目录
    target_profile = Path(profile_dir) if profile_dir else DEFAULT_PROFILE_DIR
    target_profile.mkdir(parents=True, exist_ok=True)
    options.add_argument(f"--user-data-dir={target_profile.resolve()}")

    # 2. 真实桌面视口与 UA
    options.add_argument("--window-size=1366,900")
    options.add_argument("--start-maximized")
    options.add_argument("--lang=zh-CN")

    # 3. 反检测关键配置 (参考 GitHub 知名项目最佳实践)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 4. 降低资源开销、严格限制磁盘缓存与防止多余垃圾缓存堆积
    options.add_argument("--log-level=3")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disk-cache-size=10485760")    # 限制磁盘缓存为 10MB，防止体积暴增
    options.add_argument("--media-cache-size=10485760")   # 限制媒体缓存为 10MB
    options.add_argument("--disable-component-update")    # 禁止 Edge 下载组件包缓存 (如 component_crx)
    options.add_argument("--disable-features=msEdgeWallet,EdgeShopping,msEdgeEntityExtraction,msEdgeSidebarV2")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--no-first-run")

    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")

    # 启动驱动
    try:
        driver = webdriver.Edge(options=options)
    except Exception as e:
        print(f"[错误] Edge 驱动初始化失败: {e}")
        print("[提示] 请确保您的 Windows 已安装 Microsoft Edge 浏览器。")
        raise e

    # 5. 执行 CDP 命令彻底抹除 navigator.webdriver 标识
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
