# -*- coding: utf-8 -*-
"""
智能解题器与交互求解器 (处理问答测验、每日投票、拼图跳过与二选一)
"""

import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from core.browser import human_sleep, simulate_scroll

def solve_page_activities(driver) -> bool:
    """
    全方位检测并解决当前页面中的 Rewards 任务：
    1. 拼图任务 (自动点击【跳过拼图】)
    2. 每日投票 (Poll)
    3. 问答测验 (Quiz / Trivia)
    4. 二选一 (This or That)
    5. 常规浏览任务 (平滑滚动并等待信标入账)
    """
    time.sleep(2.5)

    # 1. 尝试跳过拼图
    if solve_puzzle(driver):
        print("  🧩 [解题器] 检测到拼图任务，已自动点击【跳过拼图】完成！")
        return True

    # 2. 尝试每日投票
    if solve_poll(driver):
        print("  📊 [解题器] 检测到每日投票，已自动完成投票！")
        return True

    # 3. 尝试问答测验
    if solve_quiz(driver):
        print("  📝 [解题器] 检测到问答测验，已自动答题完成！")
        return True

    # 4. 尝试二选一
    if solve_this_or_that(driver):
        print("  ⚖️ [解题器] 检测到二选一任务，已完成交互！")
        return True

    # 5. 常规浏览任务
    print("  🌐 [解题器] 常规浏览类任务，正在模拟人类深度浏览...")
    simulate_scroll(driver, steps=3)
    human_sleep(5.0, 8.0)
    return True


def solve_puzzle(driver) -> bool:
    """解决滑动拼图：直接点击【跳过拼图 ->】并等待重定向至必应聚焦结果页入账"""
    try:
        current_url = driver.current_url.lower()
        # 页面是否具有拼图特征
        has_puzzle = "imagepuzzle" in current_url or driver.execute_script(
            "return !!(document.getElementById('skipPuzzle') || document.querySelector('.skipPuzzle, #tiles, #board'));"
        )
        if not has_puzzle:
            return False

        print("  🧩 [拼图求解] 检测到滑动拼图页面，正在执行自动跳过...")

        # 直接使用 JavaScript 点击跳过拼图 (避免 Selenium 物理点击被透明遮罩或动画拦截)
        skipped = driver.execute_script("""
            const skip = document.getElementById("skipPuzzle") || 
                         document.querySelector(".skipPuzzle, [class*='skip-puzzle' i], a[href*='spotlightPageUrl']");
            if (skip) {
                skip.click();
                return true;
            }
            // 兜底：查找所有文字含“跳过”的元素
            const all = Array.from(document.querySelectorAll("a, button, div, span"));
            const btn = all.find(e => /跳过拼图|Skip puzzle/i.test(e.innerText || '') && e.children.length <= 1);
            if (btn) {
                (btn.closest("a, button, div.skipPuzzle") || btn).click();
                return true;
            }
            return false;
        """)

        if skipped:
            print("  ✓ 已成功触发【跳过拼图】！等待跳转至必应聚焦结果页...")
            # 拼图跳转通常在 1~3 秒内重定向至 spotlight 结果页
            for _ in range(12):
                time.sleep(1.0)
                cur = driver.current_url.lower()
                if "imagepuzzle" not in cur and ("spotlight" in cur or "search" in cur):
                    print(f"  🌐 已成功跳转至聚焦搜索页: {driver.current_url[:65]}...")
                    break

            # 在跳转后的必应搜索页进行平滑滚动与信标停留入账
            time.sleep(2.0)
            simulate_scroll(driver, steps=2)
            human_sleep(4.0, 6.0)
            return True

    except Exception as e:
        print(f"  ⚠️ 拼图自动跳过处理异常: {e}")
    return False


def solve_poll(driver) -> bool:
    """解决每日投票：随机选择一个选项并提交"""
    try:
        poll_cards = driver.find_elements(
            By.CSS_SELECTOR,
            "div[id^='btoption'], #btoption0, #btoption1, .btOptionCard, .bt_Option"
        )
        visible_options = [c for c in poll_cards if c.is_displayed()]
        if visible_options:
            choice = random.choice(visible_options[:2])
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", choice)
            time.sleep(0.8)
            driver.execute_script("arguments[0].click();", choice)
            human_sleep(2.5, 4.0)
            return True
    except Exception:
        pass
    return False


def solve_quiz(driver) -> bool:
    """解决问答测验：自动点击开始，循环答题直到完成"""
    try:
        # 检查是否有“开始答题”按钮
        start_btns = driver.find_elements(
            By.CSS_SELECTOR,
            "#rqStartQuiz, input[id*='StartQuiz'], input[value*='quiz'], input[value*='开始'], button[id*='StartQuiz']"
        )
        for b in start_btns:
            if b.is_displayed():
                driver.execute_script("arguments[0].click();", b)
                human_sleep(1.5, 2.5)
                break

        # 检查是否存在答题选项
        attempts = 0
        max_attempts = 15
        answered = False

        while attempts < max_attempts:
            attempts += 1
            options = driver.find_elements(
                By.CSS_SELECTOR,
                "input[name='rqAnswerOption'], .rqOption:not(.wrongOption):not(.rqDisabled), .rq_button, .btOptionCard, [data-option]"
            )
            visible_options = [o for o in options if o.is_displayed()]

            if not visible_options:
                # 尝试点击“下一题”按钮
                next_btns = driver.find_elements(
                    By.CSS_SELECTOR,
                    "#rqAnswerOptionNext, input[value*='Next'], input[value*='下一题'], button[id*='Next']"
                )
                next_visible = [nb for nb in next_btns if nb.is_displayed()]
                if next_visible:
                    driver.execute_script("arguments[0].click();", next_visible[0])
                    human_sleep(1.5, 2.5)
                    continue

                # 检查是否已显示完成提示
                header_text = driver.execute_script(
                    "return (document.querySelector('.rqHeader, #rqHeader, .c-heading, #quizCompleteContainer') || {}).innerText || '';"
                )
                if any(kw in header_text for kw in ["完成", "恭喜", "congratulations", "earned"]):
                    return True
                break

            choice = random.choice(visible_options)
            driver.execute_script("arguments[0].click();", choice)
            answered = True
            human_sleep(1.2, 2.2)

        return answered
    except Exception:
        pass
    return False


def solve_this_or_that(driver) -> bool:
    """解决二选一活动"""
    try:
        cards = driver.find_elements(By.CSS_SELECTOR, ".btOptionCard, div[id^='btoption'], div[data-serpquery]")
        visible_cards = [c for c in cards if c.is_displayed()]
        if len(visible_cards) >= 2:
            choice = random.choice(visible_cards[:2])
            driver.execute_script("arguments[0].click();", choice)
            human_sleep(2.5, 3.5)
            return True
    except Exception:
        pass
    return False
