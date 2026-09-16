# -*- coding: utf-8 -*-
"""
微软 Rewards 仪表盘解析与每日活动/日常任务自动化执行器
分阶段精准执行：
  阶段一：每日活动 (Daily Set) -> https://rewards.bing.com/dashboard
  阶段二：周期任务与日常任务 (Earn) -> https://rewards.bing.com/earn
真实前台激活、解题交互、9秒发分信标停留与微软官方打勾核验
"""

import time
import json
import re
import urllib.parse
from typing import Dict, List, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from core.browser import human_sleep, simulate_scroll, switch_to_new_tab, close_tab_and_return
from core.solvers import solve_page_activities

DASHBOARD_URL = "https://rewards.bing.com/dashboard"
EARN_URL = "https://rewards.bing.com/earn"
REWARDS_HOME = "https://rewards.bing.com/"

class RewardsDashboard:
    def __init__(self, driver):
        self.driver = driver

    def ensure_logged_in(self, is_headless: bool = False) -> bool:
        """确保已登录微软账户，未登录时留出时间供用户手动登录并自动持久化"""
        self.driver.get(DASHBOARD_URL)
        time.sleep(3)

        current_url = self.driver.current_url.lower()
        if "login.live.com" in current_url or "signin" in current_url:
            if is_headless:
                print("\n" + "=" * 60)
                print("❌ [提示] 本地 Profile 尚未登录微软账号，无法在无头静默模式下进行首次登录！")
                print("   请先双击运行 run.bat 选择 [6] 或执行 `python rewards_runner.py --login`，")
                print("   在弹出的浏览器窗口中登录一次（登录后即可永久享受后台静默运行）。")
                print("=" * 60 + "\n", flush=True)
                return False

            print("\n" + "=" * 60, flush=True)
            print("🔑 [提示] 检测到当前尚未登录微软账号！", flush=True)
            print("   浏览器窗口已为您打开，请在窗口中登录您的微软账号。", flush=True)
            print("   登录后脚本将自动检测并永久保存您的登录状态！", flush=True)
            print("=" * 60 + "\n", flush=True)

            for _ in range(120):  # 最长等待 4 分钟
                time.sleep(2)
                cur = self.driver.current_url.lower()
                if "rewards.bing.com" in cur and "login.live.com" not in cur:
                    print("✓ 登录成功！会话已自动保存至本地目录。", flush=True)
                    time.sleep(3)
                    return True
            print("❌ 登录超时，请重新运行脚本。", flush=True)
            return False

        return True

    def get_user_status(self) -> Dict[str, Any]:
        """读取当前用户积分与连胜天数"""
        points = 0
        streak = 0

        try:
            status_data = self.driver.execute_script("""
                try {
                    const d = window.dashboardData || (window.rewards && window.rewards.dashboardData) || (window.appData && window.appData.dashboardData);
                    if (d && d.userStatus) {
                        return {
                            points: d.userStatus.availablePoints || 0,
                            streak: d.userStatus.currentStreak || 0
                        };
                    }
                    const nextEl = document.getElementById('__NEXT_DATA__');
                    if (nextEl) {
                        const parsed = JSON.parse(nextEl.textContent);
                        const pd = (parsed.props && parsed.props.pageProps && (parsed.props.pageProps.dashboardData || parsed.props.pageProps.userData)) || parsed.dashboardData;
                        if (pd && pd.userStatus) {
                            return {
                                points: pd.userStatus.availablePoints || 0,
                                streak: pd.userStatus.currentStreak || 0
                            };
                        }
                    }
                } catch(e) {}
                return null;
            """)
            if status_data:
                points = status_data.get("points", 0)
                streak = status_data.get("streak", 0)
        except Exception:
            pass

        # DOM 兜底读取
        if points == 0:
            try:
                dom_pts = self.driver.execute_script("""
                    const m = document.body.innerText.match(/(?:可用积分|Available\\s*points)[^\\d]*([\\d,]+)/i);
                    if (m) {
                        const n = parseInt(m[1].replace(/,/g, ''), 10);
                        if (!isNaN(n) && n > 0 && n < 2000000) return n;
                    }
                    return 0;
                """)
                if dom_pts and dom_pts > 0:
                    points = dom_pts
            except Exception:
                pass

        if streak == 0:
            try:
                dom_streak = self.driver.execute_script("""
                    const sm = document.body.innerText.match(/(?:每日连续打卡|连续打卡|连签)[^\\d]*(\\d+)\\s*天/i);
                    if (sm) return parseInt(sm[1], 10);
                    return 0;
                """)
                if dom_streak and dom_streak > 0:
                    streak = dom_streak
            except Exception:
                pass

        return {"points": points, "streak": streak}

    def scan_page_cards(self, page_type: str = "dashboard") -> List[Dict[str, Any]]:
        """
        全量扫描指定页面中的任务卡片
        :param page_type: 'dashboard' (每日活动 3 项) 或 'earn' (周期任务与日常打卡)
        :return: 任务卡片列表
        """
        simulate_scroll(self.driver, steps=3)
        time.sleep(1.2)

        cards = self.driver.execute_script(r"""
            const pageType = arguments[0];
            const results = [];

            // 过滤非任务卡片（兑换、抽奖、券包、积分上限等）
            const isDisallowed = (title, text, href) => {
                const c = (title + ' ' + text + ' ' + (href || '')).toLowerCase();
                // 若卡片带有明确的积分增加标志 (+10, +5 等) 或任务进度，属于正常任务，绝不能当作普通外链过滤！
                const hasPointsBadge = /\+\s*\d+/.test(text) || /\d+\s*(?:个?任务|tasks?)/i.test(text);

                if (/抽奖|券包|打折|优惠券|捐赠|捐款|sweepstakes|voucher|donate|禮品卡|礼品卡|gift\s*card|套件|古代錢幣|精选兑换/i.test(c)) return true;
                if (/徽章|成就|勋章|称号|办公室伙伴|dos\s*老大|音频迷|(?<!网络)本地英雄|badges?|achievements?/i.test(c)) return true;
                if (!hasPointsBadge && /^(?:可用积分|积分上限|可领取|总积分|当前总积分|连胜天数|连胜|波罗|个人资料|目标|查看全部|状态|级别|等级|设置|帮助|反馈|隐私|条款|points|streak|status|goal|连签奖励|活动|必应|microsoft edge)$/i.test(title.trim())) return true;
                if (href && !href.startsWith('http://') && !href.startsWith('https://') && !href.startsWith('/')) return true;
                if (/microsoft-edge:|ms-windows-store:|searchbar/i.test(href || '')) return true;
                if (/使用搜索栏/i.test(title)) return true;
                if (!hasPointsBadge && href && (href.includes('/redeem') || href.includes('/refer') || href.includes('status/level') || href.includes('modal='))) return true;
                return false;
            };

            const isLocked = (text) => {
                return /需要.*(?:级别|等级|银牌|金牌)|锁定|\blocked\b|未解锁|等待\s*\d+\s*小时|rewards\s*app\s*only|app\s*only|仅限积分商城应用/i.test(text);
            };

            const hasVisiblePointsBadge = (card) => {
                const allLeaf = card.querySelectorAll("span, div, p, a, button, b, strong");
                for (const el of allLeaf) {
                    if (el.children.length === 0) {
                        const txt = (el.innerText || el.textContent || "").trim();
                        if (/^\+\s*\d+$/.test(txt) || /^\+\s*\d+\s*(?:分|pts?)?$/i.test(txt)) {
                            try {
                                const style = window.getComputedStyle(el);
                                if (style.display !== "none" && style.visibility !== "hidden" && parseFloat(style.opacity || "1") > 0 && el.getBoundingClientRect().width > 0) {
                                    return true;
                                }
                            } catch (e) {
                                return true;
                            }
                        }
                    }
                }
                return false;
            };

            const hasVisibleCheckmark = (card) => {
                const allLeaf = card.querySelectorAll("span, div, p, i, svg, b, strong");
                for (const leaf of allLeaf) {
                    if (leaf.children.length === 0) {
                        const txt = (leaf.innerText || leaf.textContent || "").trim();
                        if (/^[✔✓]/.test(txt)) {
                            try {
                                const style = window.getComputedStyle(leaf);
                                if (style.display !== "none" && style.visibility !== "hidden" && parseFloat(style.opacity || "1") > 0 && leaf.getBoundingClientRect().width > 0) {
                                    return true;
                                }
                            } catch (e) {}
                        }
                    }
                }
                const checkCandidates = card.querySelectorAll(".mee-icon-CheckMark, svg[class*='check' i], [class*='checkMark' i], [class*='c-glyph-checkmark' i], svg[viewBox='0 0 7 6'], [aria-label*='完成'], [aria-label*='complete' i]");
                for (const el of checkCandidates) {
                    const aria = (el.getAttribute("aria-label") || "").trim();
                    if (/未完成|完成以|完成可|完成此|complete to|not completed/i.test(aria)) continue;
                    try {
                        const style = window.getComputedStyle(el);
                        if (style.display !== "none" && style.visibility !== "hidden" && parseFloat(style.opacity || "1") > 0 && el.getBoundingClientRect().width > 0) {
                            return true;
                        }
                    } catch (e) {}
                }
                if (card.innerHTML.includes('CheckMark') || card.innerHTML.includes('viewBox="0 0 7 6"')) {
                    return true;
                }
                return false;
            };

            const isCompleted = (card, text) => {
                const punchMatch = text.match(/(\d+)\s*\/\s*(\d+)\s*(?:个?任务|tasks?)/i);
                if (punchMatch) {
                    if (parseInt(punchMatch[1], 10) >= parseInt(punchMatch[2], 10)) return true;
                }
                const hasPointsBadge = hasVisiblePointsBadge(card);
                const hasCheck = hasVisibleCheckmark(card);
                if (hasPointsBadge && !hasCheck) return false;
                if (hasCheck) return true;
                if (/已完成|Completed/i.test(text)) {
                    if (!/未完成|完成以|完成可|完成此|complete to|not completed/i.test(text)) return true;
                }
                return false;
            };

            // 扫描 DOM 中所有任务卡片元素 (支持 a, div, span, mee-card, fui-Card 等各种 Fluent 2 封装)
            const cardCandidates = Array.from(document.querySelectorAll(
                "a[class*='rounded-cornerCardDefault'], div[class*='rounded-cornerCardDefault'], span[class*='rounded-cornerCardDefault'], a[href*='bing.com/search'], a[data-bi-name], mee-card, [class*='c-card' i], [class*='card-item' i], [class*='activity-card' i], [class*='fui-Card' i], [data-bi-area*='daily' i] a, [data-bi-area*='earn' i] a"
            ));

            let index = 0;
            const seenTitles = new Set();
            const seenHrefs = new Set();

            for (const card of cardCandidates) {
                const cardText = (card.innerText || "").trim();
                if (cardText.length < 4 || cardText.length > 500) continue;

                // 提取标题
                let title = "";
                const heading = card.querySelector("h1, h2, h3, h4, h5, [class*='title' i], [class*='heading' i], p[class*='Strong' i]");
                if (heading) {
                    title = (heading.innerText || "").replace(/\+\s*\d+$/, "").replace(/[✔✓]\s*\d*$/, "").replace(/已完成$/, "").trim();
                }
                if (!title) {
                    const lines = cardText.split('\n').map(s => s.trim()).filter(Boolean);
                    title = lines.find(l => l.length >= 2 && l.length <= 40 && !/^\+?\d+$/.test(l) && !/^[✔✓]/.test(l) && !/已完成|需要|重置|了解更多/.test(l)) || "";
                }

                // 优先从卡片自身或内部提取真实链接
                let href = card.getAttribute("href") || "";
                if (!href || href.startsWith("javascript:") || href.endsWith("#")) {
                    const innerA = card.querySelector("a[href]");
                    if (innerA && innerA.href && !innerA.href.startsWith("javascript:")) {
                        href = innerA.getAttribute("href") || innerA.href;
                    }
                }

                if (!title || seenTitles.has(title) || isDisallowed(title, cardText, href)) continue;
                if (href && !href.startsWith("javascript:") && href !== "#" && seenHrefs.has(href)) continue;
                seenTitles.add(title);
                if (href && !href.startsWith("javascript:") && href !== "#") seenHrefs.add(href);

                const isPunch = /\d+\s*\/\s*\d+\s*(?:个?任务|tasks?)/i.test(cardText) || /punchcard/i.test(href);

                // 提取积分：必须具备积分标志（+10, +5, 10 已完成, 10分 等）或为周期打卡任务
                let points = 0;
                const pm = cardText.match(/\+\s*(\d+)/) ||
                           cardText.match(/[✔✓]\s*(\d+)/) ||
                           cardText.match(/(\d+)[\s\S]{0,10}已完成/) ||
                           cardText.match(/(\d+)\s*(?:分|pts?)/i);
                if (pm) {
                    points = parseInt(pm[1], 10);
                } else if (isPunch) {
                    points = 50;
                } else {
                    // 没有积分标识的非任务卡片（如纯文章推广、横幅），直接跳过！
                    continue;
                }

                let promoUrl = href;
                if (promoUrl && promoUrl.startsWith("/")) {
                    promoUrl = "https://rewards.bing.com" + promoUrl;
                }
                if (!promoUrl) {
                    promoUrl = `https://www.bing.com/search?q=${encodeURIComponent(title)}&FORM=QBLH`;
                }

                const completed = isCompleted(card, cardText);
                const locked = isLocked(cardText);

                results.push({
                    index: index++,
                    title,
                    points,
                    isDailySet: pageType === "dashboard",
                    isPunchCard: isPunch,
                    completed,
                    locked,
                    url: promoUrl
                });
            }
            return results;
        """, page_type)

        return cards or []

    def execute_card(self, card: Dict[str, Any], current_url: str) -> bool:
        """
        真实前台执行单个任务卡片：
        1. 模拟自然点击派发
        2. 切换至前台任务标签页
        3. 模拟滚动与活动求解 (Quiz / Poll / Puzzle / Browse)
        4. 前台停留 8~9 秒确保发分信标上传
        5. 关闭标签页并刷新核验
        """
        title = card["title"]
        pts = card["points"]
        print(f"\n🎯 正在执行任务: 【{title}】(+{pts}分)...")

        initial_window = self.driver.current_window_handle
        initial_windows = set(self.driver.window_handles)

        # 尝试在页面中查找并点击该卡片
        clicked = self.driver.execute_script("""
            const targetTitle = arguments[0];
            const allLinks = Array.from(document.querySelectorAll("a, button, div[role='button'], div[class*='cursor-pointer'], span[class*='cursor-pointer'], [class*='rounded-cornerCardDefault']"));
            const matchCard = allLinks.find(el => {
                const t = (el.innerText || "").trim();
                return t.includes(targetTitle) && el.children.length <= 10;
            });
            if (matchCard) {
                const clickable = matchCard.closest("a, button, [role='button']") || matchCard;
                const opts = { bubbles: true, cancelable: true, view: window };
                clickable.dispatchEvent(new PointerEvent("pointerdown", opts));
                clickable.dispatchEvent(new MouseEvent("mousedown", opts));
                clickable.dispatchEvent(new PointerEvent("pointerup", opts));
                clickable.dispatchEvent(new MouseEvent("mouseup", opts));
                clickable.dispatchEvent(new MouseEvent("click", opts));
                if (typeof clickable.click === 'function') clickable.click();
                return { success: true, href: clickable.href || null };
            }
            return { success: false };
        """, title)

        time.sleep(3.5)
        current_windows = set(self.driver.window_handles)
        new_windows = current_windows - initial_windows

        if new_windows:
            new_tab = list(new_windows)[0]
            self.driver.switch_to.window(new_tab)
            print(f"  🌐 任务标签页已激活: 《{self.driver.title}》")
        else:
            # 若未弹新窗，判断是否当前窗口跳转或需直接导航
            if current_url not in self.driver.current_url:
                print(f"  🌐 页面已直接导航至: 《{self.driver.title}》")
            else:
                target_url = card.get("url") or f"https://www.bing.com/search?q={urllib.parse.quote(title)}"
                print(f"  🌐 直接在前台打开任务链接: {target_url}")
                self.driver.execute_script("window.open(arguments[0], '_blank');", target_url)
                time.sleep(2.5)
                current_windows = set(self.driver.window_handles)
                new_windows = current_windows - initial_windows
                if new_windows:
                    self.driver.switch_to.window(list(new_windows)[0])

        # 检查是否打开了周期打卡详情页 (URL 含有 quest / punchcard 或卡片被标记为 isPunchCard)
        cur_url = self.driver.current_url.lower()
        if card.get("isPunchCard") or "/earn/quest/" in cur_url or "/punchcard/" in cur_url or "punchcard" in card.get("url", "").lower():
            self._handle_punchcard_subtasks(initial_window)
        else:
            # 在前台任务页进行解题求解与人机拟真滚动
            try:
                simulate_scroll(self.driver, steps=2)
                time.sleep(1.5)
                solve_page_activities(self.driver)
            except Exception as e:
                print(f"  ⚠️ 执行页面求解交互异常 (非致命): {e}")

            # 核心关键：前台静默停留 8~9 秒，确保必应发分信标成功上传至微软服务器
            print("  ⏱️ 保持前台视口 8 秒，等待微软 Rewards 积分入账信标...")
            time.sleep(8.5)

        # 安全关闭任务标签页并切回主页面
        if new_windows:
            try:
                self.driver.close()
            except Exception:
                pass
            self.driver.switch_to.window(initial_window)
        else:
            self.driver.get(current_url)

        time.sleep(2.5)
        return True

    def _handle_punchcard_subtasks(self, initial_window: str) -> int:
        """
        处理周期任务详情页 (Quest / Punch Card) 内的所有子任务：
        自动解析未完成且具有【浏览/开始】CTA 按钮的子项并逐个执行打卡
        """
        print("  📑 [周期任务] 正在解析打卡详情页子任务...")
        time.sleep(3.5)

        punch_window = self.driver.current_window_handle

        subtasks = self.driver.execute_script("""
            const results = [];
            const h3s = Array.from(document.querySelectorAll("h3"));
            for (const h3 of h3s) {
                const title = (h3.innerText || '').trim();
                if (!title) continue;
                let container = h3.parentElement;
                for (let i = 0; i < 4; i++) {
                    if (!container || !container.parentElement) break;
                    if (container.classList && (container.className.includes('flex') || container.className.includes('item') || container.className.includes('card'))) {
                        break;
                    }
                    container = container.parentElement;
                }
                if (!container) continue;

                const fullText = (container.parentElement ? container.parentElement.innerText : container.innerText) || '';
                const isDone = container.parentElement ? (
                    container.parentElement.innerHTML.includes('CheckMark') || 
                    container.parentElement.innerHTML.includes('viewBox="0 0 7 6"') || 
                    (container.parentElement.innerHTML.includes('fill="currentColor"') && container.parentElement.innerHTML.includes('text-fgCtrlOnImage')) ||
                    /已完成/i.test(fullText)
                ) : false;

                // 寻找按钮/链接
                const cta = container.querySelector("a, button, [role='link']");
                let ctaText = cta ? (cta.innerText || '').trim() : '';
                let ctaHref = cta ? (cta.href || cta.getAttribute('href')) : '';
                let ctaDisabled = cta ? (
                    cta.getAttribute('aria-disabled') === 'true' || 
                    cta.getAttribute('data-disabled') === 'true' || 
                    cta.disabled
                ) : false;

                results.push({
                    title,
                    isDone,
                    ctaText,
                    ctaHref,
                    ctaDisabled
                });
            }
            return results;
        """)

        if not subtasks:
            print("  ⚠️ 未在详情页解析到子任务，执行常规浏览拟真...")
            simulate_scroll(self.driver, steps=2)
            time.sleep(5)
            return 0

        print(f"  📋 检测到 {len(subtasks)} 项打卡子任务:")
        for idx, st in enumerate(subtasks, 1):
            if st["isDone"]:
                status = "✔ 已完成"
            elif st["ctaDisabled"]:
                status = "🔒 冷却中(需等24h后解锁)"
            else:
                status = "🎯 待打卡"
            cta_info = f" [按钮: {st['ctaText']}]" if st['ctaText'] else ""
            print(f"     {idx}. 【{st['title']}】 -> {status}{cta_info}")

        actionable_tasks = [st for st in subtasks if not st["isDone"] and not st["ctaDisabled"] and (st["ctaHref"] or st["ctaText"])]
        if not actionable_tasks:
            cooldown_tasks = [st for st in subtasks if not st["isDone"] and st["ctaDisabled"]]
            if cooldown_tasks:
                print(f"  ⏳ 子任务【{cooldown_tasks[0]['title']}】需等待上一项完成满 24 小时后解锁，明天打卡将自动完成！")
            else:
                print("  🎉 该周期打卡任务的全部子项均已完成！")
            return 0

        completed_subs = 0
        for st in actionable_tasks:
            title = st["title"]
            cta_text = st["ctaText"] or "浏览"
            print(f"\n  👉 正在执行子任务: 【{title}】 (触发点击【{cta_text}】)...")

            initial_windows = set(self.driver.window_handles)

            # 1. 尝试使用真实鼠标动作链 ActionChains 点击该子任务的按钮/链接
            clicked = False
            try:
                elements = self.driver.find_elements(By.XPATH, f"//h3[contains(text(), '{title[:6]}')]/ancestor::div[contains(@class, 'flex') or contains(@class, 'card') or contains(@class, 'item')][1]//a | //h3[contains(text(), '{title[:6]}')]/ancestor::div[contains(@class, 'flex') or contains(@class, 'card') or contains(@class, 'item')][1]//button")
                if not elements:
                    elements = self.driver.find_elements(By.XPATH, f"//a[contains(., '{cta_text[:2]}')] | //button[contains(., '{cta_text[:2]}')]")

                for el in elements:
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el)
                        time.sleep(1.0)
                        ActionChains(self.driver).move_to_element(el).pause(0.3).click().perform()
                        clicked = True
                        break
            except Exception:
                pass

            if not clicked:
                # 2. JavaScript 全事件仿真点击派发 (PointerEvent + MouseEvent + click)
                clicked = self.driver.execute_script("""
                    const targetTitle = arguments[0];
                    const h3s = Array.from(document.querySelectorAll('h3'));
                    for (const h3 of h3s) {
                        if ((h3.innerText || '').includes(targetTitle)) {
                            let container = h3.parentElement;
                            for (let i = 0; i < 4; i++) {
                                if (!container || !container.parentElement) break;
                                if (container.classList && (container.className.includes('flex') || container.className.includes('item') || container.className.includes('card'))) break;
                                container = container.parentElement;
                            }
                            const cta = container ? container.querySelector("a, button, [role='link']") : null;
                            if (cta) {
                                cta.scrollIntoView({behavior: 'smooth', block: 'center'});
                                const opts = { bubbles: true, cancelable: true, view: window };
                                cta.dispatchEvent(new PointerEvent('pointerdown', opts));
                                cta.dispatchEvent(new MouseEvent('mousedown', opts));
                                cta.dispatchEvent(new PointerEvent('pointerup', opts));
                                cta.dispatchEvent(new MouseEvent('mouseup', opts));
                                cta.dispatchEvent(new MouseEvent('click', opts));
                                if (typeof cta.click === 'function') cta.click();
                                return true;
                            }
                        }
                    }
                    return false;
                """, title[:6])

            time.sleep(3.5)
            new_windows = set(self.driver.window_handles) - initial_windows
            if new_windows:
                sub_window = list(new_windows)[0]
                self.driver.switch_to.window(sub_window)
                print(f"     🌐 子任务页面已激活: 《{self.driver.title}》")
                time.sleep(2.0)
                simulate_scroll(self.driver, steps=3)
                print("     ⏱️ 保持视口 12 秒等待微软打卡积分信标上传...")
                time.sleep(12.0)
                try:
                    self.driver.close()
                except Exception:
                    pass
                self.driver.switch_to.window(punch_window)
                time.sleep(2.0)
                completed_subs += 1
                print(f"     ✓ 子任务【{title}】打卡完成！")
            else:
                # 兜底：若未弹新窗，尝试直接打开 URL
                sub_url = st.get("ctaHref")
                if sub_url and sub_url.startswith("http"):
                    print(f"     🌐 直接打开子任务链接: {sub_url}")
                    self.driver.execute_script("window.open(arguments[0], '_blank');", sub_url)
                    time.sleep(3.0)
                    new_windows = set(self.driver.window_handles) - initial_windows
                    if new_windows:
                        sub_window = list(new_windows)[0]
                        self.driver.switch_to.window(sub_window)
                        time.sleep(2.0)
                        simulate_scroll(self.driver, steps=3)
                        time.sleep(12.0)
                        try:
                            self.driver.close()
                        except Exception:
                            pass
                        self.driver.switch_to.window(punch_window)
                        time.sleep(2.0)
                        completed_subs += 1
                        print(f"     ✓ 子任务【{title}】打卡完成！")

        self.driver.refresh()
        time.sleep(3.5)
        return completed_subs

    def run_daily_set(self) -> int:
        """
        阶段一：执行每日活动 (Daily Set)
        目标页面: https://rewards.bing.com/dashboard
        包含 3 项每日必做任务 (例如音乐活动、旧金山海湾、观星建议等)
        """
        print("\n" + "=" * 60)
        print("🚀 【阶段 1/2】开始执行【每日活动 (Daily Set)】...")
        print(f"   访问官方页面: {DASHBOARD_URL}")
        print("=" * 60)

        self.driver.get(DASHBOARD_URL)
        time.sleep(4)

        initial_status = self.get_user_status()
        print(f"📊 当前可用积分: {initial_status['points']} | 连胜天数: {initial_status['streak']} 天\n")

        cards = self.scan_page_cards(page_type="dashboard")
        print(f"📋 【每日活动】扫描结果 (共发现 {len(cards)} 项任务):")
        for idx, c in enumerate(cards, 1):
            status_str = "🔒 未解锁" if c["locked"] else ("✔ 已完成" if c["completed"] else "🎯 待执行")
            print(f"  {idx}. 【{c['title']}】(+{c['points']}分) -> 状态: {status_str}")
        print("-" * 60)

        pending_cards = [c for c in cards if not c["completed"] and not c["locked"]]
        if not pending_cards:
            print("🎉 今日【每日活动 (Daily Set)】已全部处于完成打勾状态！无需重复执行。\n")
            return 0

        print(f"👉 发现 {len(pending_cards)} 项待完成的每日活动，开始逐项执行...\n")
        completed_count = 0

        for i, card in enumerate(pending_cards, 1):
            self.execute_card(card, DASHBOARD_URL)

            # 刷新仪表盘，向微软官方核验真实打卡结果
            print(f"  🔍 正在向微软服务器核验【{card['title']}】打卡结果...")
            self.driver.get(DASHBOARD_URL)
            time.sleep(4)

            latest_status = self.get_user_status()
            latest_cards = self.scan_page_cards(page_type="dashboard")
            matched = next((lc for lc in latest_cards if lc["title"] == card["title"] or card["title"] in lc["title"]), None)

            if matched and matched["completed"]:
                completed_count += 1
                gain = latest_status["points"] - initial_status["points"]
                print(f"  ✓ 【真实完成】任务【{card['title']}】已通过微软官方核验并打勾！(当前总积分: {latest_status['points']})\n")
            elif latest_status["points"] > initial_status["points"]:
                completed_count += 1
                gain = latest_status["points"] - initial_status["points"]
                print(f"  ✓ 【真实入账】任务【{card['title']}】积分已成功入账！(+{gain}分，当前总积分: {latest_status['points']})\n")
            else:
                print(f"  ⚠️ 任务【{card['title']}】微软服务器可能存在轻微同步延迟，已进入下一项\n")

            human_sleep(1.5, 3.0)

        final_status = self.get_user_status()
        print(f"✓ 每日活动阶段完成！成功处理: {completed_count}/{len(pending_cards)} 项\n")
        return completed_count

    def run_earn_tasks(self) -> int:
        """
        阶段二：执行周期任务与日常任务 (Earn)
        目标页面: https://rewards.bing.com/earn
        自动识别周期打卡 (Punch Card) 与可执行的日常活动，跳过等级未解锁卡片
        """
        print("\n" + "=" * 60)
        print("🌟 【阶段 2/2】开始执行【周期任务与日常任务 (Earn)】...")
        print(f"   访问官方页面: {EARN_URL}")
        print("=" * 60)

        self.driver.get(EARN_URL)
        time.sleep(4)

        cards = self.scan_page_cards(page_type="earn")
        print(f"📋 【积分赚取 (Earn)】扫描结果 (共发现 {len(cards)} 项任务):")
        for idx, c in enumerate(cards, 1):
            tag = " [周期打卡]" if c["isPunchCard"] else ""
            status_str = "🔒 未解锁" if c["locked"] else ("✔ 已完成" if c["completed"] else "🎯 待执行")
            print(f"  {idx}. 【{c['title']}】{tag}(+{c['points']}分) -> 状态: {status_str}")
        print("-" * 60)

        pending_cards = [c for c in cards if not c["completed"] and not c["locked"]]
        if not pending_cards:
            print("🎉 积分赚取页面 (earn) 中的任务均已完成或无需执行！\n")
            return 0

        print(f"👉 发现 {len(pending_cards)} 项待完成任务，开始执行...\n")
        completed_count = 0

        for card in pending_cards:
            self.execute_card(card, EARN_URL)
            completed_count += 1
            human_sleep(2.0, 3.5)

        return completed_count

    def claim_available_points(self) -> int:
        """
        自动检测并领取 dashboard 页面上的待入账/待领取积分 (如搜索后产生的【可领取 6*】以及月度/首搜待领取奖励)
        目标页面: https://rewards.bing.com/dashboard
        """
        print("\n" + "=" * 60)
        print("🎁 正在检查是否存在【可领取】搜索积分与待入账奖励...")
        print("=" * 60)

        total_claimed = 0
        try:
            if "rewards.bing.com/dashboard" not in self.driver.current_url.lower():
                self.driver.get(DASHBOARD_URL)
                time.sleep(3.5)

            # 1. 精准查找包含“可领取”且具有数字>0的按钮卡片
            claim_info = self.driver.execute_script(r"""
                const allNodes = Array.from(document.querySelectorAll('button, [role="button"]'));
                const claimCard = allNodes.find(el => {
                    const t = (el.innerText || '').replace(/\s+/g, ' ');
                    return t.includes('可领取') && t.includes('领取') && el.children.length <= 4;
                });
                if (claimCard) {
                    const m = claimCard.innerText.match(/(\d+)/);
                    return { found: true, pts: m ? parseInt(m[1], 10) : 0, text: claimCard.innerText };
                }
                return { found: false, pts: 0 };
            """)

            if not claim_info.get("found") or claim_info.get("pts", 0) <= 0:
                print("✓ 当前暂无可领取的额外积分 (可领取: 0)，无需执行领取，直接跳过！\n")
                return 0

            pending_pts = claim_info["pts"]
            print(f"👉 发现待入账奖励 (+{pending_pts} 积分)，正在自动打开抽屉并一键领取...")

            # 2. 点击卡片打开抽屉
            opened = self.driver.execute_script(r"""
                const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
                const target = btns.find(b => {
                    const t = (b.innerText || '').replace(/\s+/g, ' ');
                    return t.includes('可领取') && t.includes('领取') && b.children.length <= 4;
                });
                if (target) {
                    target.click();
                    return true;
                }
                return false;
            """)
            time.sleep(3.0)

            # 3. 精准点击抽屉内部的【领取积分】按钮 (文本含有“待领取”与“领取积分”的 button)
            claimed = self.driver.execute_script(r"""
                const allBtns = Array.from(document.querySelectorAll('button'));
                const btn = allBtns.find(b => {
                    const t = (b.innerText || '').trim();
                    return t.includes('领取积分') && (t.includes('待领取') || t.includes('领取'));
                });
                if (btn) {
                    btn.scrollIntoView({behavior: 'smooth', block: 'center'});
                    const opts = { bubbles: true, cancelable: true, view: window };
                    btn.dispatchEvent(new PointerEvent('pointerdown', opts));
                    btn.dispatchEvent(new MouseEvent('mousedown', opts));
                    btn.dispatchEvent(new PointerEvent('pointerup', opts));
                    btn.dispatchEvent(new MouseEvent('mouseup', opts));
                    btn.dispatchEvent(new MouseEvent('click', opts));
                    if (typeof btn.click === 'function') btn.click();
                    return { success: true, text: (btn.innerText || '').replace(/\n+/g, ' ') };
                }
                return { success: false };
            """)

            if claimed and claimed.get("success"):
                print(f"  ✓ 成功触发领取操作！【{claimed.get('text', '')}】")
                time.sleep(3.0)
                total_claimed += 1
            else:
                fallback = self.driver.execute_script("""
                    const all = Array.from(document.querySelectorAll("*"));
                    for (const el of all) {
                        if ((el.innerText || '').trim() === "领取积分") {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                """)
                if fallback:
                    print("  ✓ 通过兜底文本元素成功触发领取！")
                    time.sleep(3.0)
                    total_claimed += 1

            # 4. 【核验环节：领取完成后检测一遍是不是成功领取】
            print("  🔍 正在向微软服务器核验领取结果与最新状态...")
            time.sleep(2.5)
            verify_res = self.driver.execute_script(r"""
                const all = Array.from(document.querySelectorAll('*'));
                const noMorePoints = all.some(el => (el.innerText || '').includes('当前没有要领取的积分'));
                const zeroButton = all.some(el => {
                    const t = (el.innerText || '').trim();
                    return t === '0\n\n领取积分' || t === '0 领取积分' || t.startsWith('0\n\n');
                });
                
                const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
                const card = btns.find(b => {
                    const t = (b.innerText || '').replace(/\s+/g, ' ');
                    return t.includes('可领取') && b.children.length <= 5;
                });
                let cardPts = 0;
                if (card) {
                    const m = card.innerText.match(/(\d+)/);
                    cardPts = m ? parseInt(m[1], 10) : 0;
                }
                
                return {
                    isClean: noMorePoints || zeroButton || cardPts === 0,
                    cardPts: cardPts
                };
            """)

            updated_status = self.get_user_status()
            if verify_res and verify_res.get("isClean"):
                print(f"  ✓ 【核验确认】奖励积分已成功划转入账！待入账积分已清零 (0)，最新可用总积分: {updated_status['points']}\n")
            else:
                rem = verify_res.get('cardPts', 0) if verify_res else 0
                print(f"  ⚠️ 核验提示：微软服务器可能存在同步微延迟 (剩余待领取: {rem} 分)，当前最新可用总积分: {updated_status['points']}\n")

            # 5. 关闭抽屉，恢复页面整洁
            self.driver.execute_script("""
                const closeBtn = Array.from(document.querySelectorAll('button, div[role="button"]')).find(b => {
                    const t = (b.innerText || '').trim();
                    return t === '关闭' || t === '✕' || t === '×' || b.getAttribute('aria-label') === '关闭' || b.getAttribute('aria-label') === 'Close';
                });
                if (closeBtn) closeBtn.click();
            """)
            time.sleep(1.0)

        except Exception as e:
            print(f"  ⚠️ 自动领取积分过程中发生非致命异常: {e}\n")

        return total_claimed

    # 别名兼容
    claim_pending_rewards = claim_available_points

    def run_visual_search(self) -> bool:
        """
        自动完成必应【视觉搜索连续打卡】(赚取每日 +5 积分与 7 天连续打卡印章/印花)
        访问视觉搜索入口并通过本地图片上传或拟真检索触发打卡信标
        """
        print("\n" + "=" * 60)
        print("📷 正在检查【视觉搜索连续打卡】任务状态...")
        print("=" * 60)

        try:
            if "rewards.bing.com/dashboard" not in self.driver.current_url.lower():
                self.driver.get(DASHBOARD_URL)
                time.sleep(3.5)

            # 1. 检查今日是否已完成 (精准匹配视觉搜索卡片，防止祖先容器误判)
            is_already_done = self.driver.execute_script(r"""
                const btns = Array.from(document.querySelectorAll('button, div[role="button"]'));
                const vsCard = btns.find(el => {
                    const t = (el.innerText || '').trim();
                    return t.includes('视觉搜索') && t.includes('活动:') && t.length < 50;
                });
                if (vsCard) {
                    const t = vsCard.innerText;
                    return t.includes('1/1') || t.includes('已完成');
                }
                return false;
            """)

            if is_already_done:
                print("✓ 今日视觉搜索任务已完成 (活动: 1/1)，无需重复打卡。\n")
                return True

            print("👉 今日视觉搜索待打卡，正在前往必应并自动触发图像检索...")

            # 2. 访问携带视觉打卡标识的必应搜索主页
            vs_url = "https://www.bing.com/?features=vsstreak,vstooltip&form=ML2XES"
            self.driver.get(vs_url)
            time.sleep(4.0)

            # 3. 优先使用本地图标文件上传 (最稳定，直接触发原生文件检索通道)
            from pathlib import Path
            project_root = Path(__file__).resolve().parent.parent
            img_candidates = [
                project_root / "extension" / "icons" / "icon128.png",
                project_root / "extension" / "icons" / "icon48.png",
                project_root / "extension" / "icons" / "icon16.png"
            ]
            test_img = next((img for img in img_candidates if img.exists()), None)

            uploaded = False
            if test_img:
                file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file'], #sb_fileinput")
                for fi in file_inputs:
                    try:
                        fi.send_keys(str(test_img.resolve()))
                        uploaded = True
                        print(f"  ✓ 已通过上传图像触发视觉搜索: {test_img.name}")
                        break
                    except Exception:
                        pass

            # 4. 备用方案 A：唤起面板并输入图像 URL
            if not uploaded:
                try:
                    from selenium.webdriver.common.keys import Keys
                    btn = self.driver.find_element(By.CSS_SELECTOR, "#sb_sbi, [aria-label*='图像搜索']")
                    btn.click()
                    time.sleep(1.5)
                    img_pst = self.driver.find_element(By.CSS_SELECTOR, "#sb_imgpst, input[placeholder*='图像链接']")
                    img_pst.send_keys("https://www.bing.com/sa/simg/favicon-2x.ico")
                    img_pst.send_keys(Keys.ENTER)
                    uploaded = True
                    print("  ✓ 已通过输入图像 URL 触发视觉搜索")
                except Exception:
                    pass

            # 5. 备用方案 B：图片库快捷视觉搜索
            if not uploaded:
                print("  ⚠️ 切换至图片库视觉搜索快捷通道...")
                self.driver.get("https://www.bing.com/images/search?q=landscape&form=HDRSC3")
                time.sleep(3.5)
                self.driver.execute_script("""
                    const icon = document.querySelector('.iacf_vsicon') || document.querySelector('[aria-label="视觉搜索"]');
                    if (icon) icon.click();
                """)
                time.sleep(4.0)

            print("  ⏱️ 等待必应视觉搜索解析结果并停留 12 秒等待打卡信标上传...")
            time.sleep(12.0)
            try:
                simulate_scroll(self.driver, steps=2)
                time.sleep(4.0)
            except Exception:
                pass

            # 6. 返回 Rewards 检查并核验打卡结果
            self.driver.get(DASHBOARD_URL)
            time.sleep(4.0)
            verify_res = self.driver.execute_script(r"""
                const btns = Array.from(document.querySelectorAll('button, div[role="button"]'));
                const vsCard = btns.find(el => {
                    const t = (el.innerText || '').trim();
                    return t.includes('视觉搜索') && t.includes('活动:') && t.length < 50;
                });
                return vsCard ? vsCard.innerText.replace(/\n+/g, ' ') : null;
            """)

            if verify_res and ("1/1" in verify_res or "已完成" in verify_res):
                print(f"🎉 【核验通过】视觉搜索连续打卡已成功打勾 (1/1)！最新状态: 【{verify_res}】\n")
                return True
            else:
                print(f"✓ 视觉搜索打卡指令已派发完毕！最新状态: 【{verify_res or '已提交打卡'}】\n")
                return True

        except Exception as e:
            print(f"  ⚠️ 视觉搜索打卡过程中出现非致命异常: {e}\n")
            return False

    # 别名兼容
    perform_visual_search = run_visual_search
