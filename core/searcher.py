# -*- coding: utf-8 -*-
"""
PC 端桌面必应搜索自动化执行器
特性：
1. 优先核验当前必应搜索已获得积分与每日上限 (如 60/60)
2. 若已达满分则直接跳过，绝不盲目重复搜索
3. 若未达满分，根据实际差额精确计算所需搜索次数并补足至满额
4. 倒数第二阶段执行，确保其他任务附带搜索被充分计入
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
        通过 https://rewards.bing.com/earn 页面的“积分明细”抽屉精准读取
        """
        try:
            if "rewards.bing.com/earn" not in self.driver.current_url.lower():
                self.driver.get("https://rewards.bing.com/earn")
                time.sleep(3.5)

            # 查找并点击“积分明细”打开抽屉
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
            time.sleep(2.5)

            pts = self.driver.execute_script(r"""
                const all = Array.from(document.querySelectorAll('*'));
                for (const el of all) {
                    const t = (el.innerText || '').trim();
                    if (t.includes('连续打卡') || t.includes('印章') || t.includes('1,000 奖励')) continue;
                    if (t.includes('必应搜索') && /\d+\s*\/\s*\d+/.test(t) && t.length < 80) {
                        const m = t.match(/(\d+)\s*\/\s*(\d+)/);
                        if (m) {
                            const cur = parseInt(m[1], 10);
                            const max = parseInt(m[2], 10);
                            if (max >= 10) {
                                return { current: cur, max: max };
                            }
                        }
                    }
                }
                return null;
            """)

            # 关闭抽屉，恢复页面状态
            self.driver.execute_script("""
                const closeBtn = Array.from(document.querySelectorAll('button, div[role="button"]')).find(b => {
                    const t = (b.innerText || '').trim();
                    return t === '关闭' || t === '✕' || t === '×' || b.getAttribute('aria-label') === '关闭' || b.getAttribute('aria-label') === 'Close';
                });
                if (closeBtn) closeBtn.click();
            """)

            if pts:
                return pts
        except Exception:
            pass
        return {"current": 0, "max": 60}

    def perform_searches(self, count: int = 22, min_delay: float = 7.0, max_delay: float = 12.0, ensure_max: bool = True) -> int:
        """
        在 Edge 浏览器中执行自然必应搜索并确保达到每日上限 (如 60/60 分)
        【先检测，已完成则跳过；未完成则按实际缺额补齐】
        :param count: 最大单次搜索允许上限 (默认 22 次)
        :param min_delay: 单次搜索最小防风控间隔 (秒)
        :param max_delay: 单次搜索最大防风控间隔 (秒)
        :param ensure_max: 是否在搜索后自动核验并精准补足直到满额 60 分 (默认 True)
        :return: 成功搜索次数
        """
        print("\n" + "=" * 60)
        print("🔍 正在核验【PC 桌面端必应搜索】今日打卡进度...")
        print("=" * 60)

        # 1. 优先核验当前必应搜索已获得积分与上限
        pts = self.get_search_points()
        cur = pts.get("current", 0)
        target = pts.get("max", 60)
        print(f"📊 微软官方实时记录: 必应搜索 {cur}/{target} 积分")

        # 2. 若已达满分，直接跳过！
        if cur >= target and target > 0:
            print(f"🎉 今日必应搜索已达成 {cur}/{target} 满额积分！无需重复搜索，直接跳过。\n")
            return 0

        # 3. 按实际缺额计算计划搜索次数 (每次搜索得 3 分)
        needed_pts = target - cur
        needed_searches = max(1, (needed_pts + 2) // 3)
        plan_count = min(count, needed_searches)
        print(f"👉 距离 {target} 满分还差 {needed_pts} 积分，按实际缺额计划精准执行 {plan_count} 次搜索...\n")

        # 构造词库池 (中文占 75%，英文占 25%)
        pool = SEARCH_KEYWORDS_ZH * 2 + SEARCH_KEYWORDS_EN
        random.shuffle(pool)

        completed = 0
        for idx in range(plan_count):
            keyword = pool[idx % len(pool)]
            encoded = urllib.parse.quote(keyword)
            search_url = f"https://www.bing.com/search?q={encoded}&FORM=QBLH"

            delay = random.uniform(min_delay, max_delay)
            print(f"[{idx+1}/{plan_count}] 必应搜索: \"{keyword}\"")

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

        # 4. 动态核验与差额自动补足
        if ensure_max:
            time.sleep(2.0)
            pts = self.get_search_points()
            cur = pts.get("current", 0)
            target = pts.get("max", 60)
            print(f"  📊 搜索后微软服务器最新记录: 必应搜索 {cur}/{target} 积分")

            safety_limit = 5
            extra_idx = 0
            while cur < target and extra_idx < safety_limit:
                extra_idx += 1
                needed_searches = max(1, (target - cur + 2) // 3)
                print(f"  👉 距离满分仍差 {target - cur} 分，补充执行第 {extra_idx} 轮差额搜索 ({needed_searches} 次)...")

                for _ in range(needed_searches):
                    kw = pool[(plan_count + extra_idx * 10) % len(pool)]
                    s_url = f"https://www.bing.com/search?q={urllib.parse.quote(kw)}&FORM=QBLH"
                    print(f"  [补齐] 必应搜索: \"{kw}\"")
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
        print(f"✓ PC 桌面端必应搜索阶段完成！累计执行: {completed} 次，最终进度: {cur}/{target} 积分")
        print("=" * 60 + "\n")
        return completed
