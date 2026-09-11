# -*- coding: utf-8 -*-
"""
PC 端桌面必应搜索自动化执行器 (15次自然搜索)
"""

import time
import random
import urllib.parse
from core.browser import human_sleep, simulate_scroll
from data.keywords import SEARCH_KEYWORDS_ZH, SEARCH_KEYWORDS_EN

class BingSearcher:
    def __init__(self, driver):
        self.driver = driver

    def perform_searches(self, count: int = 15, min_delay: float = 7.0, max_delay: float = 12.0) -> int:
        """
        在 Edge 浏览器中执行自然必应搜索
        :param count: 目标搜索次数 (默认 15 次)
        :param min_delay: 单次搜索最小防风控间隔 (秒)
        :param max_delay: 单次搜索最大防风控间隔 (秒)
        :return: 成功搜索次数
        """
        print("\n" + "=" * 60)
        print(f"🔍 开始执行【PC 桌面端必应搜索】(计划搜索 {count} 次)...")
        print("=" * 60)

        # 构造词库池 (中文占 75%，英文占 25%)
        pool = SEARCH_KEYWORDS_ZH * 2 + SEARCH_KEYWORDS_EN
        random.shuffle(pool)
        selected_keywords = pool[:count]

        # 确保词库数量充足
        while len(selected_keywords) < count:
            selected_keywords.append(random.choice(SEARCH_KEYWORDS_ZH))

        completed = 0
        for idx, keyword in enumerate(selected_keywords, 1):
            encoded = urllib.parse.quote(keyword)
            search_url = f"https://www.bing.com/search?q={encoded}&FORM=QBLH"

            delay = random.uniform(min_delay, max_delay)
            print(f"[{idx}/{count}] 必应搜索: \"{keyword}\"")

            try:
                self.driver.get(search_url)
                time.sleep(1.8)

                # 模拟平滑滚动以触发搜索入账信标
                simulate_scroll(self.driver, steps=2)

                print(f"       ⏱️ 等待防风控间隔 {delay:.1f} 秒...")
                time.sleep(delay)
                completed += 1
            except Exception as e:
                print(f"       ⚠️ 搜索过程中发生非致命异常: {e}")
                time.sleep(3.0)

        print("-" * 60)
        print(f"✓ PC 桌面端必应搜索全部完成！成功执行: {completed}/{count} 次")
        print("=" * 60 + "\n")
        return completed
