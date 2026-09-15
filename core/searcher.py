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

    def get_search_points(self) -> dict:
        """
        读取当前必应搜索已获得积分与每日上限 (如 60/60)
        """
        try:
            self.driver.get("https://rewards.bing.com/earn")
            time.sleep(3.5)
            # 查找并点击“积分明细”
            self.driver.execute_script("""
                const els = Array.from(document.querySelectorAll('a, button, div[role="button"], span, p'));
                for (const el of els) {
                    const t = (el.innerText || '').trim();
                    if (t === '积分明细' || t.startsWith('积分明细')) {
                        el.click();
                        break;
                    }
                }
            """)
            time.sleep(3.0)

            pts = self.driver.execute_script(r"""
                const all = Array.from(document.querySelectorAll('*'));
                for (const el of all) {
                    const t = (el.innerText || '').trim();
                    if (t.includes('必应搜索') && t.includes('/60')) {
                        const m = t.match(/必应搜索[^\d]*(\d+)\s*\/\s*60/i) || t.match(/(\d+)\s*\/\s*60/i);
                        if (m) {
                            return { current: parseInt(m[1], 10), max: 60 };
                        }
                    }
                }
                return null;
            """)
            if pts:
                return pts
        except Exception:
            pass
        return {"current": 0, "max": 60}

    def perform_searches(self, count: int = 22, min_delay: float = 7.0, max_delay: float = 12.0, ensure_max: bool = True) -> int:
        """
        在 Edge 浏览器中执行自然必应搜索并确保达到每日上限 (如 60/60 分)
        :param count: 基础搜索计划次数 (默认 22 次)
        :param min_delay: 单次搜索最小防风控间隔 (秒)
        :param max_delay: 单次搜索最大防风控间隔 (秒)
        :param ensure_max: 是否自动核验并补足搜索直到满额 60 分 (默认 True)
        :return: 成功搜索次数
        """
        print("\n" + "=" * 60)
        print(f"🔍 开始执行【PC 桌面端必应搜索】(基础计划搜索 {count} 次，确保 60/60 满额)...")
        print("=" * 60)

        # 构造词库池 (中文占 75%，英文占 25%)
        pool = SEARCH_KEYWORDS_ZH * 2 + SEARCH_KEYWORDS_EN
        random.shuffle(pool)

        completed = 0
        for idx in range(count):
            keyword = pool[idx % len(pool)]
            encoded = urllib.parse.quote(keyword)
            search_url = f"https://www.bing.com/search?q={encoded}&FORM=QBLH"

            delay = random.uniform(min_delay, max_delay)
            print(f"[{idx+1}/{count}] 必应搜索: \"{keyword}\"")

            try:
                self.driver.get(search_url)
                time.sleep(1.8)
                simulate_scroll(self.driver, steps=2)
                print(f"       ⏱️ 等待防风控间隔 {delay:.1f} 秒...")
                time.sleep(delay)
                completed += 1
            except Exception as e:
                print(f"       ⚠️ 搜索过程中发生非致命异常: {e}")
                time.sleep(3.0)

        # 动态核验与差额自动补足
        if ensure_max:
            print("\n  🔍 正在核验必应搜索是否达成 60/60 满额积分...")
            pts = self.get_search_points()
            cur = pts.get("current", 0)
            target = pts.get("max", 60)
            print(f"  📊 微软服务器当前记录: 必应搜索 {cur}/{target} 积分")

            safety_limit = 10
            extra_idx = 0
            while cur < target and extra_idx < safety_limit:
                needed_searches = max(1, (target - cur + 2) // 3)
                print(f"  👉 距离 {target} 满分还差 {target - cur} 积分，正在自动补足 {needed_searches} 次搜索...")

                for _ in range(needed_searches):
                    extra_idx += 1
                    kw = pool[(count + extra_idx) % len(pool)]
                    s_url = f"https://www.bing.com/search?q={urllib.parse.quote(kw)}&FORM=QBLH"
                    print(f"  [补齐 {extra_idx}] 必应搜索: \"{kw}\"")
                    try:
                        self.driver.get(s_url)
                        time.sleep(1.8)
                        simulate_scroll(self.driver, steps=2)
                        time.sleep(random.uniform(min_delay, max_delay))
                        completed += 1
                    except Exception:
                        time.sleep(3.0)

                # 再次核验
                pts = self.get_search_points()
                cur = pts.get("current", target)
                print(f"  📊 补齐后最新记录: 必应搜索 {cur}/{target} 积分")

        print("-" * 60)
        print(f"✓ PC 桌面端必应搜索全部完成！成功执行: {completed} 次")
        print("=" * 60 + "\n")
        return completed
