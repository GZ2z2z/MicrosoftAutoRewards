# -*- coding: utf-8 -*-
"""
Edge 30分钟后台静默浏览打卡模块
功能：
1. 自动检测 https://rewards.bing.com/earn 页面上的【Edge 浏览连续打卡】进度 (例如 5/30 分钟)
2. 若已满 30 分钟则直接跳过，避免重复耗时
3. 若未满 30 分钟，自动进入后台静默浏览模式：
   - 访问官方打卡激活入口与必应资讯/MSN/优质内容页
   - 持续拟真自然滚动、停留阅读、文章翻阅与多标签页活动
   - 保持 document.visibilityState = 'visible' 与焦点活跃
   - 周期性 (每 3~4 分钟) 轮询核验微软服务器记录的最新打卡分钟数
   - 达到 30/30 分钟或达成目标后自动退出并报告成果
"""

import sys
import time
import random
import datetime
from typing import Optional, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from core.browser import simulate_scroll

# 官方激活与高权重内容池
EDGE_STREAK_ACTIVATION_URL = "https://www.bing.com/?rwgbopen=1&FORM=rwbsl1"
PROMO_URL = "https://rewards.bing.com/promo/edge-browsing-streak"
EARN_URL = "https://rewards.bing.com/earn"

NEWS_TOPICS = [
    "https://www.bing.com/news",
    "https://www.bing.com/search?q=James+Webb+Space+Telescope+discoveries&FORM=HDRSC1",
    "https://www.bing.com/search?q=%E7%A7%91%E6%8A%80%E5%89%8D%E6%B2%BF%E6%9C%80%E6%96%B0%E7%AA%81%E7%A0%B4&FORM=HDRSC1",
    "https://www.bing.com/search?q=%E5%85%A8%E7%90%83%E8%87%AA%E7%84%B6%E5%9C%B0%E7%90%86%E5%A5%87%E8%A7%82&FORM=HDRSC1",
    "https://www.bing.com/search?q=mars+rover+latest+rock+sample+analysis&FORM=HDRSC1",
    "https://www.bing.com/search?q=%E4%BA%BA%E7%B1%BB%E5%8F%B2%E4%B8%8A%E7%9A%84%E4%BC%9F%E5%A4%A7%E5%BB%BA%E7%AD%91&FORM=HDRSC1",
    "https://www.bing.com/search?q=renewable+energy+breakthroughs+solar&FORM=HDRSC1",
    "https://www.bing.com/search?q=%E5%9C%B0%E7%90%83%E6%B7%B1%E6%B5%B7%E6%8E%A2%E7%B4%A2%E6%96%B0%E7%89%A9%E7%A7%8D&FORM=HDRSC1",
    "https://www.bing.com/search?q=deep+space+exploration+missions&FORM=HDRSC1",
    "https://www.bing.com/search?q=%E5%8F%A4%E4%BB%A3%E6%96%87%E6%98%8E%E9%81%97%E8%BF%B9%E8%80%83%E5%8F%A4&FORM=HDRSC1"
]


def get_edge_browsing_progress(driver) -> Optional[Dict[str, Any]]:
    """
    解析当前 Edge 浏览 30 分钟打卡进度
    返回字典: {"current": 5, "target": 30, "is_done": False}
    """
    try:
        progress = driver.execute_script("""
            const allElements = Array.from(document.querySelectorAll('*'));
            for (const el of allElements) {
                const text = el.innerText || '';
                const m = text.match(/分钟[:：\\s]*(\\d+)\\s*\\/\\s*(\\d+)/i) || text.match(/(\\d+)\\s*\\/\\s*(\\d+)\\s*分钟/i);
                if (m && el.children.length <= 2) {
                    const cur = parseInt(m[1], 10);
                    const tgt = parseInt(m[2], 10);
                    return {
                        current: cur,
                        target: tgt,
                        is_done: cur >= tgt
                    };
                }
            }
            return null;
        """)
        return progress
    except Exception:
        return None


def run_edge_30min_browsing(driver, max_minutes: int = 35, target_minutes: int = 30) -> bool:
    """
    执行 Edge 30 分钟后台静默浏览打卡任务
    """
    print("\n" + "=" * 60)
    print("🌐 【Edge 浏览连续打卡】开始后台静默 30 分钟浏览打卡...")
    print("=" * 60)

    # 1. 查询当前打卡进度
    driver.get(EARN_URL)
    time.sleep(4)
    prog = get_edge_browsing_progress(driver)

    current_min = prog["current"] if prog else 0
    target_min = prog["target"] if prog else target_minutes

    if prog and prog.get("is_done"):
        print(f"🎉 今日 Edge 浏览打卡已达成 {current_min}/{target_min} 分钟 (已完成)，无需额外浏览！")
        return True

    needed_minutes = max(1, target_min - current_min)
    print(f"📊 当前打卡进度: {current_min}/{target_min} 分钟 | 需继续静默浏览: 约 {needed_minutes} 分钟")
    print("🚀 正在激活 Edge 浏览打卡信标，开启后台静默拟真浏览...")

    # 2. 激活官方入口 (rwgbopen=1)
    try:
        driver.get(EDGE_STREAK_ACTIVATION_URL)
        time.sleep(3.5)
    except Exception:
        pass

    start_time = time.time()
    last_check_time = start_time
    last_nav_time = start_time
    topic_index = 0

    # 随机打乱内容池
    topics = list(NEWS_TOPICS)
    random.shuffle(topics)

    while True:
        elapsed_sec = time.time() - start_time
        elapsed_min = elapsed_sec / 60.0

        # 超时保护
        if elapsed_min >= max_minutes:
            print(f"\n⏱️ 已达单次最大浏览保护时长 ({max_minutes} 分钟)，正在做最后状态核验...")
            break

        # 人机拟真滚动与微阅读 (每 20~35 秒一次交互)
        simulate_scroll(driver, steps=random.randint(2, 4))
        time.sleep(random.uniform(15, 25))

        # 保持视口激活
        try:
            driver.execute_script("""
                window.dispatchEvent(new Event('focus'));
                document.dispatchEvent(new Event('visibilitychange'));
            """)
        except Exception:
            pass

        # 页面切换与阅读跳转 (每 90~150 秒切换一次主题或点击内容)
        if time.time() - last_nav_time > random.uniform(90, 150):
            target_url = topics[topic_index % len(topics)]
            topic_index += 1
            last_nav_time = time.time()
            try:
                # 偶尔在 Bing 页面内直接点击结果链接，模拟深层阅读
                clicked_link = driver.execute_script("""
                    const links = Array.from(document.querySelectorAll("h2 a, .b_algo h2 a, a[href*='bing.com/news']"));
                    if (links.length > 0) {
                        const randomLink = links[Math.floor(Math.random() * Math.min(links.length, 5))];
                        return randomLink.href;
                    }
                    return null;
                """)
                if clicked_link and random.random() < 0.4:
                    driver.get(clicked_link)
                else:
                    driver.get(target_url)
                time.sleep(3)
            except Exception:
                try:
                    driver.get(target_url)
                except Exception:
                    pass

        # 周期性核验打卡进度 (每 3 分钟查询一次微软官方记录)
        if time.time() - last_check_time > 180:
            last_check_time = time.time()
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"  [{now_str}] ⏱️ 已后台静默浏览 {elapsed_min:.1f} 分钟，正在核验微软服务器进度...", flush=True)
            
            # 使用新建标签页快速核验，不打断主浏览视口
            try:
                driver.execute_script(f"window.open('{EARN_URL}', '_blank');")
                time.sleep(3.5)
                handles = driver.window_handles
                if len(handles) > 1:
                    driver.switch_to.window(handles[-1])
                    check_prog = get_edge_browsing_progress(driver)
                    driver.close()
                    driver.switch_to.window(handles[0])
                    
                    if check_prog:
                        c = check_prog["current"]
                        t = check_prog["target"]
                        print(f"  [{now_str}] 📈 微软服务器实时打卡进度: {c}/{t} 分钟", flush=True)
                        if check_prog.get("is_done") or c >= t:
                            print(f"\n🎉 恭喜！Edge 浏览打卡已达成 {c}/{t} 分钟 (全部完成)！")
                            return True
            except Exception as e:
                print(f"  ⚠️ 进度核验微异常 (继续浏览): {e}")

    # 最终结算核验
    driver.get(EARN_URL)
    time.sleep(4)
    final_prog = get_edge_browsing_progress(driver)
    if final_prog:
        print(f"✓ 最终 Edge 浏览打卡进度: {final_prog['current']}/{final_prog['target']} 分钟")
        return final_prog.get("is_done", False)
    return True
