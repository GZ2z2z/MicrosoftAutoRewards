// Microsoft Rewards 自动化调度中心 (Manifest V3 Background Service Worker)
// 纯后台标签页静默运行：绝不单独弹窗、做完即关、严格跳过已完成与未解锁任务、智能处理周期打卡
importScripts("data/words.js");

// 默认配置
const DEFAULT_SETTINGS = {
  pcSearchCount: 15,
  minDelay: 7,
  maxDelay: 12,
  enableDailySet: true,
  enablePcSearch: true,
  enableAlarm: true,
  alarmTime: "08:30",
  cooldownMode: false,
  searchLang: "mixed",
  notifyOnComplete: true
};

// 运行时状态
let runtimeState = {
  running: false,
  stopped: false,
  currentStep: "idle", // 'idle' | 'daily_set' | 'pc_search' | 'done'
  dailySetDone: 0,
  dailySetTotal: 0,
  pcSearchDone: 0,
  pcSearchTotal: 15,
  currentPoints: 0,
  startPoints: 0,
  streakDays: 0,
  lastRunDate: ""
};

let userSettings = { ...DEFAULT_SETTINGS };
let activityLogs = [];
let currentTaskTabId = null;
let completedCycleCardsToday = new Set(); // 记录今日已满额的周期任务
let managedTabIds = new Set(); // 严格记录本扩展创建的后台标签页，绝不干扰用户自建的标签页

// 日志追加与广播
function addLog(message, type = "info") {
  const time = new Date().toLocaleTimeString();
  const logItem = { time, message, type };
  activityLogs.unshift(logItem);
  if (activityLogs.length > 150) {
    activityLogs.pop();
  }
  chrome.runtime.sendMessage({
    action: "STATE_UPDATED",
    state: runtimeState,
    log: logItem
  }).catch(() => {});
  console.log(`[MS Rewards][${type.toUpperCase()}] ${message}`);
}

// 广播状态更新给打开的 popup
function broadcastState() {
  chrome.runtime.sendMessage({
    action: "STATE_UPDATED",
    state: runtimeState
  }).catch(() => {});
}

// 延迟辅助
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const getRandomDelay = (minSec, maxSec) => {
  const min = Math.max(2, minSec) * 1000;
  const max = Math.max(minSec, maxSec) * 1000;
  return Math.floor(Math.random() * (max - min + 1) + min);
};

// 标签页安全关闭
async function safeCloseTab(tabId) {
  if (tabId) {
    try {
      await chrome.tabs.remove(tabId);
    } catch (e) {}
  }
  if (currentTaskTabId === tabId) {
    currentTaskTabId = null;
  }
}

async function waitForTabLoad(tabId, timeoutMs = 20000) {
  return new Promise((resolve) => {
    let timer = null;
    const listener = (updatedTabId, changeInfo) => {
      if (updatedTabId === tabId && changeInfo.status === "complete") {
        cleanup();
        resolve(true);
      }
    };
    const cleanup = () => {
      chrome.tabs.onUpdated.removeListener(listener);
      if (timer) clearTimeout(timer);
    };
    chrome.tabs.onUpdated.addListener(listener);
    timer = setTimeout(() => {
      cleanup();
      resolve(false);
    }, timeoutMs);
  });
}

// 发送桌面通知
function sendNotification(title, message) {
  if (!userSettings.notifyOnComplete) return;
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: `[Microsoft Rewards] ${title}`,
    message: message,
    priority: 1
  });
}

// 初始化设置与定时器
async function initExtension() {
  const stored = await chrome.storage.local.get(["settings", "lastRunDate", "completedCycleCards"]);
  if (stored.settings) {
    userSettings = { ...DEFAULT_SETTINGS, ...stored.settings };
    if (stored.settings.pcSearchCount === 30 || !stored.settings.pcSearchCount) {
      userSettings.pcSearchCount = 15;
    }
  } else {
    userSettings = { ...DEFAULT_SETTINGS };
  }
  if (stored.lastRunDate) {
    runtimeState.lastRunDate = stored.lastRunDate;
  }
  if (stored.completedCycleCards && Array.isArray(stored.completedCycleCards)) {
    completedCycleCardsToday = new Set(stored.completedCycleCards);
  }
  if (runtimeState.currentPoints >= 2000000) {
    runtimeState.currentPoints = 0;
    runtimeState.startPoints = 0;
  }
  setupDailyAlarm();
}

// 设置每日定时执行闹钟
async function setupDailyAlarm() {
  await chrome.alarms.clear("daily_rewards_alarm");
  if (!userSettings.enableAlarm || !userSettings.alarmTime) {
    addLog("每日定时执行已关闭", "info");
    return;
  }

  const [hours, minutes] = userSettings.alarmTime.split(":").map(Number);
  const now = new Date();
  const target = new Date();
  target.setHours(hours, minutes, 0, 0);

  if (target <= now) {
    target.setDate(target.getDate() + 1);
  }

  const delayInMinutes = Math.max(1, (target.getTime() - now.getTime()) / 60000);
  chrome.alarms.create("daily_rewards_alarm", {
    delayInMinutes,
    periodInMinutes: 24 * 60
  });

  addLog(`定时闹钟已设定: 下次将于 ${target.toLocaleDateString()} ${userSettings.alarmTime} 触发`, "info");
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "daily_rewards_alarm") {
    addLog("⏰ 触发每日定时自动化打卡任务...", "info");
    const today = new Date().toISOString().slice(0, 10);
    if (runtimeState.lastRunDate === today) {
      addLog("检测到今日任务此前已完成，跳过本次定时触发", "info");
      return;
    }
    startFullAutomation();
  }
});

chrome.runtime.onStartup.addListener(async () => {
  await initExtension();
  const today = new Date().toISOString().slice(0, 10);
  if (userSettings.enableAlarm && runtimeState.lastRunDate !== today) {
    const [hours, minutes] = userSettings.alarmTime.split(":").map(Number);
    const now = new Date();
    if (now.getHours() > hours || (now.getHours() === hours && now.getMinutes() >= minutes)) {
      addLog("检测到今日定时任务未执行，将在5秒后自动补跑...", "info");
      setTimeout(() => startFullAutomation(), 5000);
    }
  }
});

chrome.runtime.onInstalled.addListener(() => {
  initExtension();
});

// ====================== 核心任务辅助函数 ======================

// 标题与任务过滤辅助工具
function cleanOfficialTitle(str) {
    if (!str) return "";
    return str
      .replace(/<[^>]+>/g, "")
      .replace(/&nbsp;/g, " ")
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .trim();
  }

  function isDisallowedOfficialPromo(it) {
    const combined = ((it.title || "") + " " + (it.name || "") + " " + (it.description || "") + " " + (it.exclusivePromotionBucket || "")).toLowerCase();
    if (/抽奖|券包|礼品卡|兑换|打折|优惠券|捐赠|捐款|sweepstakes|redeem|gift\s*card|voucher|donate/i.test(combined)) return true;
    if (/徽章|成就|勋章|称号|办公室伙伴|dos\s*老大|音频迷|(?<!网络)本地英雄|badges?|achievements?/i.test(combined)) return true;
    if (/rewards\s*app\s*only|app\s*only|仅限.*应用|必应应用|在移动设备上|仅移动设备|下载.*应用|立即签入|每天签到|在.*应用中|使用\s*edge\s*浏览\s*\d+\s*分钟|浏览\s*\d+\s*分钟/i.test(combined)) return true;
    if (/需要.*(?:级别|等级|银牌|金牌)|锁定|\blocked\b|未解锁/i.test(combined)) return true;
    return false;
  }

  // 核心突破：通过 Manifest V3 MAIN 执行世界直接读取微软官方原生数据模型 (权威无偏差)
  async function getOfficialDashboardData(tabId) {
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        world: "MAIN",
        func: () => {
          try {
            // 1. 全局 window.dashboardData
            const d = window.dashboardData || (window.rewards && window.rewards.dashboardData) || (window.appData && window.appData.dashboardData);
            if (d) {
              return {
                userStatus: d.userStatus ? {
                  availablePoints: d.userStatus.availablePoints,
                  currentStreak: d.userStatus.currentStreak,
                  level: d.userStatus.levelInfo ? d.userStatus.levelInfo.activeLevel : d.userStatus.level
                } : null,
                dailySetPromotions: d.dailySetPromotions || null,
                morePromotions: d.morePromotions || null,
                punchCards: d.punchCards || null,
                promotions: d.promotions || null
              };
            }

            // 2. Next.js / React pageProps
            const nextEl = document.getElementById("__NEXT_DATA__");
            if (nextEl) {
              const parsed = JSON.parse(nextEl.textContent);
              const pp = parsed.props && parsed.props.pageProps;
              const pd = pp && (pp.dashboardData || pp.userData);
              if (pd) {
                return {
                  userStatus: pd.userStatus ? {
                    availablePoints: pd.userStatus.availablePoints,
                    currentStreak: pd.userStatus.currentStreak,
                    level: pd.userStatus.levelInfo ? pd.userStatus.levelInfo.activeLevel : pd.userStatus.level
                  } : null,
                  dailySetPromotions: pd.dailySetPromotions || null,
                  morePromotions: pd.morePromotions || null,
                  punchCards: pd.punchCards || null,
                  promotions: pd.promotions || null
                };
              }
            }

            // 3. 扫描 script 标签内的定义
            const scripts = document.querySelectorAll("script");
            for (const s of scripts) {
              const txt = s.textContent || "";
              if (txt.includes("dailySetPromotions") || txt.includes("dashboardData")) {
                try {
                  const fn = new Function(txt + "; return (typeof dashboardData !== 'undefined' ? dashboardData : null);");
                  const pd = fn();
                  if (pd) {
                    return {
                      userStatus: pd.userStatus ? {
                        availablePoints: pd.userStatus.availablePoints,
                        currentStreak: pd.userStatus.currentStreak,
                        level: pd.userStatus.levelInfo ? pd.userStatus.levelInfo.activeLevel : pd.userStatus.level
                      } : null,
                      dailySetPromotions: pd.dailySetPromotions || null,
                      morePromotions: pd.morePromotions || null,
                      punchCards: pd.punchCards || null,
                      promotions: pd.promotions || null
                    };
                  }
                } catch (e) {}
              }
            }
          } catch (e) {}
          return null;
        }
      });

      if (results && results[0] && results[0].result) {
        return results[0].result;
      }
    } catch (err) {
      console.warn("[MS Rewards] 读取官方原生 dashboardData 异常:", err);
    }
    return null;
  }

  // 查找或打开微软积分中心页面 (兼容 Edge 与 Chrome，优先直接复用已打开的前台/后台页面)
  async function getOrOpenRewardsTab(preferredUrl = "https://rewards.bing.com/dashboard") {
    const allTabs = await chrome.tabs.query({});
    const matchedTab = allTabs.find((t) =>
      t.url &&
      (/(?:rewards\.bing\.com|account\.microsoft\.com\/rewards|bing\.com\/rewards|rewards\.microsoft\.com)/i.test(t.url))
    );

    if (matchedTab) {
      addLog(`🔍 检测到已打开微软积分中心 (${matchedTab.url})，直接采用该页面同步...`, "info");
      // 检查是否为 Edge 睡眠/休眠标签页 (Sleeping Tab)，若是则主动唤醒重载
      if (matchedTab.discarded) {
        addLog(`💤 检测到该标签页处于休眠状态，正在唤醒重新加载...`, "info");
        await chrome.tabs.reload(matchedTab.id);
        await waitForTabLoad(matchedTab.id, 15000);
        await sleep(2000);
      }
      return { tab: matchedTab, isTempTab: false };
    }

    addLog(`🌐 打开微软积分中心 (${preferredUrl})...`, "info");
    const newTab = await chrome.tabs.create({ url: preferredUrl, active: false });
    managedTabIds.add(newTab.id);
    currentTaskTabId = newTab.id;
    await waitForTabLoad(newTab.id, 15000);
    await sleep(2500);
    return { tab: newTab, isTempTab: true };
  }

  // 从指定标签页提取任务卡片数据
  async function extractCardsFromTab(tab) {
    if (!tab) return { cards: [], official: null };

    // 1. 优先尝试读取官方原生数据
    const official = await getOfficialDashboardData(tab.id);
    if (official && official.userStatus) {
      if (typeof official.userStatus.availablePoints === "number" && official.userStatus.availablePoints > 0) {
        runtimeState.currentPoints = official.userStatus.availablePoints;
      }
      if (typeof official.userStatus.currentStreak === "number" && official.userStatus.currentStreak >= 0) {
        runtimeState.streakDays = official.userStatus.currentStreak;
      }
    }

    // 2. 注入最新 dashboard.js
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content/dashboard.js"]
    }).catch(() => null);

    // 3. 滚动以唤醒页面所有懒加载卡片
    await chrome.tabs.sendMessage(tab.id, { action: "SCROLL_DASHBOARD" }).catch(() => null);
    await sleep(1500);

    // 4. 获取 DOM 卡片并重试
    let res = await chrome.tabs.sendMessage(tab.id, { action: "GET_DASHBOARD_INFO" }).catch(() => null);
    let retries = 0;
    while ((!res || !res.success || !res.data || !res.data.activityCards || res.data.activityCards.length === 0) && retries < 2) {
      retries++;
      await sleep(1500);
      await chrome.tabs.sendMessage(tab.id, { action: "SCROLL_DASHBOARD" }).catch(() => null);
      res = await chrome.tabs.sendMessage(tab.id, { action: "GET_DASHBOARD_INFO" }).catch(() => null);
    }

    let cards = (res && res.data && res.data.activityCards) || [];
    if (res && res.data && res.data.currentPoints > 0) {
      runtimeState.currentPoints = res.data.currentPoints;
    }
    if (res && res.data && typeof res.data.streakDays === "number") {
      runtimeState.streakDays = res.data.streakDays;
    }

    // 5. 核心增强：无论 DOM 渲染为何种形态，从官方原生数据模型中无遗漏补齐每日活动与推广任务
    if (official) {
      if (official.dailySetPromotions) {
        const dsItems = Array.isArray(official.dailySetPromotions)
          ? official.dailySetPromotions
          : Object.values(official.dailySetPromotions).flat();
        for (const it of dsItems) {
          if (!it) continue;
          const t = cleanOfficialTitle(it.title || it.name);
          if (t && !isDisallowedOfficialPromo(it)) {
            const isComp = (it.complete === true) || (typeof it.pointProgressMax === "number" && it.pointProgressMax > 0 && typeof it.pointProgress === "number" && it.pointProgress >= it.pointProgressMax && it.pointProgress > 0);
            const existing = cards.find(c => c.title === t || c.title.includes(t) || t.includes(c.title));
            if (existing) {
              existing.isDailySet = true;
              if (isComp && !existing.hasPointsBadge) existing.completed = true;
              if (it.destinationUrl) existing.url = it.destinationUrl;
            } else {
              cards.push({
                id: `off_ds_${cards.length}`,
                title: t,
                points: it.pointProgressMax || 10,
                completed: isComp,
                locked: false,
                isPunchCard: false,
                isDailySet: true,
                url: it.destinationUrl || `https://www.bing.com/search?q=${encodeURIComponent(t)}&FORM=QBLH`
              });
            }
          }
        }
      }

      const otherPromos = [...(official.morePromotions || []), ...(official.promotions || [])];
      for (const it of otherPromos) {
        if (!it) continue;
        const t = cleanOfficialTitle(it.title || it.name);
        if (t && !isDisallowedOfficialPromo(it)) {
          const isComp = (it.complete === true) || (typeof it.pointProgressMax === "number" && it.pointProgressMax > 0 && typeof it.pointProgress === "number" && it.pointProgress >= it.pointProgressMax && it.pointProgress > 0);
          const existing = cards.find(c => c.title === t || c.title.includes(t) || t.includes(c.title));
          if (existing) {
            if (isComp && !existing.hasPointsBadge) existing.completed = true;
            if (it.destinationUrl) existing.url = it.destinationUrl;
          } else {
            cards.push({
              id: `off_more_${cards.length}`,
              title: t,
              points: it.pointProgressMax || 5,
              completed: isComp,
              locked: false,
              isPunchCard: false,
              isDailySet: false,
              url: it.destinationUrl || `https://www.bing.com/search?q=${encodeURIComponent(t)}&FORM=QBLH`
            });
          }
        }
      }
    }

    return { cards, official };
  }

  // 单卡片真实执行核心：前台短暂激活打开 -> 解题/滚动 -> 停留确保发分信标发送 -> 关闭并切回原页面 -> 刷新核验
  async function executeSingleCard(card, hostTab, currentIdx, totalCount) {
    const ptsText = card.points ? `(+${card.points}分)` : "";
    addLog(`[执行 ${currentIdx}/${totalCount}] 正在执行: 【${card.title}】${ptsText}...`, "info");

    let userActiveTabId = null;
    try {
      const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (activeTab) userActiveTabId = activeTab.id;
    } catch (e) {}

    // 1. 尝试从 hostTab 中捕获真实 Promotion URL (如果有)
    let targetUrl = "";
    if (hostTab) {
      try {
        const clickResults = await chrome.scripting.executeScript({
          target: { tabId: hostTab.id },
          world: "MAIN",
          func: (targetTitle) => {
            let promoUrl = "";
            const origOpen = window.open;
            window.open = function(url) {
              if (url && typeof url === "string") promoUrl = url;
              return null;
            };
            try {
              const all = Array.from(document.querySelectorAll("mee-card, [class*='card' i], [class*='Card' i], a, div, button"));
              const matchCard = all.find((el) => {
                const t = (el.innerText || "").trim();
                return t.includes(targetTitle) && el.children.length <= 8 && el.offsetParent !== null;
              });
              if (matchCard) {
                const clickable = matchCard.closest("a, [role='button'], button") || matchCard.querySelector("a, [role='button'], button") || matchCard;
                if (clickable.tagName === "A" && clickable.href && !clickable.href.startsWith("javascript:") && !clickable.href.endsWith("#")) {
                  promoUrl = clickable.href;
                }
                const opts = { bubbles: true, cancelable: true, view: window };
                clickable.dispatchEvent(new PointerEvent("pointerdown", opts));
                clickable.dispatchEvent(new MouseEvent("mousedown", opts));
                clickable.dispatchEvent(new PointerEvent("pointerup", opts));
                clickable.dispatchEvent(new MouseEvent("mouseup", opts));
                clickable.dispatchEvent(new MouseEvent("click", opts));
                if (typeof clickable.click === "function") clickable.click();
              }
            } catch (e) {}
            window.open = origOpen;
            return promoUrl;
          },
          args: [card.title]
        });
        if (clickResults && clickResults[0] && clickResults[0].result) {
          targetUrl = clickResults[0].result;
        }
      } catch (e) {}
    }

    if (!targetUrl || targetUrl.includes("FORM=QBLH")) {
      targetUrl = card.url && !card.url.includes("FORM=QBLH") ? card.url : targetUrl;
    }
    if (!targetUrl) {
      targetUrl = `https://www.bing.com/search?q=${encodeURIComponent(card.searchQuery || card.title)}`;
    }

    // 2. 核心关键：以 active: true 在前台短暂激活打开，让必应页面具有真实可见性，触发 Rewards 积分入账信标！做完即关并自动恢复用户原标签页！
    let openedTab = null;
    try {
      openedTab = await chrome.tabs.create({ url: targetUrl, active: true });
      managedTabIds.add(openedTab.id);
      currentTaskTabId = openedTab.id;

      await waitForTabLoad(openedTab.id, 15000);
      await sleep(1500);

      // 主动注入问答与解题脚本
      await chrome.scripting.executeScript({
        target: { tabId: openedTab.id, allFrames: true },
        files: ["content/quiz_solver.js"]
      }).catch(() => null);

      if (/拼图|Puzzle/i.test(card.title)) {
        addLog(`🧩 检测到拼图任务【${card.title}】，正在尝试自动点击【跳过拼图 ->】...`, "info");
        await chrome.tabs.sendMessage(openedTab.id, { action: "SOLVE_PUZZLE" }).catch(() => null);
        await sleep(1500);
        await chrome.tabs.sendMessage(openedTab.id, { action: "SOLVE_PAGE" }).catch(() => null);
      } else {
        await chrome.tabs.sendMessage(openedTab.id, { action: "SOLVE_PAGE" }).catch(() => null);
      }

      // 触发轻量滚动交互并等待微软 Rewards 浮层发分信标上传 (7~9秒)
      await chrome.tabs.sendMessage(openedTab.id, { action: "SIMULATE_SCROLL" }).catch(() => null);
      await sleep(getRandomDelay(7, 9));

    } catch (err) {
      addLog(`任务【${card.title}】执行提示: ${err.message}`, "info");
    } finally {
      if (openedTab) {
        await safeCloseTab(openedTab.id);
        managedTabIds.delete(openedTab.id);
      }
      // 立即恢复用户的原本活跃标签页！
      if (userActiveTabId) {
        await chrome.tabs.update(userActiveTabId, { active: true }).catch(() => {});
      }
    }

    // 3. 实时向微软服务器核验真实打卡结果
    addLog(`🔍 正在向微软官方服务器核验【${card.title}】打卡结果...`, "info");
    await sleep(1500);

    let isTaskVerifiedDone = false;
    let updatedPoints = runtimeState.currentPoints;

    if (hostTab) {
      try {
        await chrome.tabs.reload(hostTab.id);
        await waitForTabLoad(hostTab.id, 12000);
        await sleep(2000);

        const latestOfficial = await getOfficialDashboardData(hostTab.id);
        if (latestOfficial) {
          if (latestOfficial.userStatus && typeof latestOfficial.userStatus.availablePoints === "number") {
            updatedPoints = latestOfficial.userStatus.availablePoints;
          }
          const allLatestPromos = [
            ...(Array.isArray(latestOfficial.dailySetPromotions) ? latestOfficial.dailySetPromotions : Object.values(latestOfficial.dailySetPromotions || {}).flat()),
            ...(Array.isArray(latestOfficial.morePromotions) ? latestOfficial.morePromotions : []),
            ...(Array.isArray(latestOfficial.promotions) ? latestOfficial.promotions : [])
          ];
          const matchedLatest = allLatestPromos.find(
            (p) => cleanOfficialTitle(p.title || p.name) === card.title || (p.title && p.title.includes(card.title)) || (card.title && card.title.includes(cleanOfficialTitle(p.title || p.name)))
          );
          if (matchedLatest && (matchedLatest.complete === true || (matchedLatest.pointProgressMax > 0 && matchedLatest.pointProgress >= matchedLatest.pointProgressMax && matchedLatest.pointProgress > 0))) {
            isTaskVerifiedDone = true;
          }
        }

        // 补充 DOM 检查作为双保险
        const domCheck = await chrome.tabs.sendMessage(hostTab.id, { action: "GET_DASHBOARD_INFO" }).catch(() => null);
        if (domCheck && domCheck.success && domCheck.data) {
          if (domCheck.data.currentPoints > 0) updatedPoints = Math.max(updatedPoints, domCheck.data.currentPoints);
          const matchedDom = (domCheck.data.activityCards || []).find(
            (c) => c.title === card.title || c.title.includes(card.title) || card.title.includes(c.title)
          );
          if (matchedDom && matchedDom.completed) {
            isTaskVerifiedDone = true;
          }
        }
      } catch (e) {}
    }

    if (isTaskVerifiedDone) {
      runtimeState.dailySetDone++;
      if (updatedPoints > runtimeState.currentPoints) {
        const ptsGained = updatedPoints - runtimeState.currentPoints;
        runtimeState.todayPoints = (runtimeState.todayPoints || 0) + ptsGained;
        runtimeState.currentPoints = updatedPoints;
        addLog(`✓ 【真实完成】任务【${card.title}】已通过微软服务器核验并打勾！(+${ptsGained}分，当前总积分: ${updatedPoints})`, "success");
      } else {
        runtimeState.currentPoints = updatedPoints;
        addLog(`✓ 【真实完成】任务【${card.title}】已通过微软官方核验并打勾！`, "success");
      }
    } else if (updatedPoints > runtimeState.currentPoints) {
      runtimeState.dailySetDone++;
      const ptsGained = updatedPoints - runtimeState.currentPoints;
      runtimeState.todayPoints = (runtimeState.todayPoints || 0) + ptsGained;
      runtimeState.currentPoints = updatedPoints;
      addLog(`✓ 【真实入账】任务【${card.title}】积分已成功入账！(+${ptsGained}分，当前总积分: ${updatedPoints})`, "success");
    } else {
      addLog(`⚠️ 任务【${card.title}】微软官方服务器暂未打勾 (可能存在网络同步延迟)，已进入下一项`, "warning");
    }

    broadcastState();
    await sleep(getRandomDelay(2, 3));
  }

  // 1. 严格分阶段执行：阶段一 /dashboard 每日活动 -> 阶段二 /earn 周期及日常任务
  async function runDashboardTasks() {
    addLog(">>> 正在启动【每日活动与日常打卡】...", "info");
    runtimeState.currentStep = "daily_set";

    let hostRewardsTab = null;
    let isRewardsTemp = false;

    try {
      // ==================== 阶段 1：每日活动专属执行 (rewards.bing.com/dashboard) ====================
      addLog("==========================================", "info");
      addLog(">>> 【阶段 1/2】连接每日活动专属页面 (rewards.bing.com/dashboard)...", "info");
      const tabResult = await getOrOpenRewardsTab("https://rewards.bing.com/dashboard");
      hostRewardsTab = tabResult.tab;
      isRewardsTemp = tabResult.isTempTab;

      // 确保 hostRewardsTab 处于 dashboard 页面
      if (!hostRewardsTab.url || !hostRewardsTab.url.includes("/dashboard")) {
        addLog("正在将积分中心页面切换至 /dashboard...", "info");
        await chrome.tabs.update(hostRewardsTab.id, { url: "https://rewards.bing.com/dashboard" });
        await waitForTabLoad(hostRewardsTab.id, 15000);
        await sleep(2000);
      }

      // 提取 /dashboard 上的每日活动卡片
      const dashScan = await extractCardsFromTab(hostRewardsTab);
      let dailyCards = (dashScan.cards || []).filter((c) => c.isDailySet || (!c.isPunchCard && c.points === 10));
      // 如果未能自动过滤，但在 /dashboard 页面，全部有效活动均作为每日活动
      if (dailyCards.length === 0 && dashScan.cards && dashScan.cards.length > 0) {
        dailyCards = dashScan.cards.filter((c) => !isDisallowedOfficialPromo(c));
      }

      addLog(`📅 【每日活动 (共 ${dailyCards.length} 项)】来自 rewards.bing.com/dashboard:`, "info");
      dailyCards.forEach((c, idx) => {
        const statusStr = c.locked ? "🔒 未解锁" : (c.completed ? "✔ 已完成" : "🎯 待执行");
        const ptsStr = c.points ? ` (+${c.points}分)` : "";
        addLog(`  ${idx + 1}. 【${c.title}】${ptsStr} -> 状态: ${statusStr}`, c.completed ? "info" : (c.locked ? "warning" : "success"));
      });

      const pendingDailyCards = dailyCards.filter((c) => !c.completed && !c.locked && !isDisallowedOfficialPromo(c));

      runtimeState.dailySetTotal = pendingDailyCards.length;
      runtimeState.dailySetDone = 0;
      broadcastState();

      if (pendingDailyCards.length === 0) {
        addLog("🎉 今日【每日活动 (Daily Set)】已全部处于完成状态！", "success");
      } else {
        addLog(`📋 发现 ${pendingDailyCards.length} 项待完成的每日活动，开始逐项在前台激活执行...`, "info");
        for (let i = 0; i < pendingDailyCards.length; i++) {
          if (runtimeState.stopped) break;
          await executeSingleCard(pendingDailyCards[i], hostRewardsTab, i + 1, pendingDailyCards.length);
        }
      }

      if (runtimeState.stopped) return;

      // ==================== 阶段 2：周期任务与日常任务执行 (rewards.bing.com/earn) ====================
      addLog("==========================================", "info");
      addLog(">>> 【阶段 2/2】切换至【积分赚取页面 (rewards.bing.com/earn)】扫描周期任务与日常任务...", "info");
      await chrome.tabs.update(hostRewardsTab.id, { url: "https://rewards.bing.com/earn" });
      await waitForTabLoad(hostRewardsTab.id, 15000);
      await sleep(2500);

      const earnScan = await extractCardsFromTab(hostRewardsTab);
      const earnCards = (earnScan.cards || []).filter((c) => {
        if (isDisallowedOfficialPromo(c)) return false;
        // 排除阶段 1 中已经处理过的每日活动
        if (dailyCards.some((dc) => dc.title === c.title)) return false;
        return true;
      });

      if (earnCards.length > 0) {
        addLog(`🌟 【周期任务与日常任务 (共 ${earnCards.length} 项)】来自 rewards.bing.com/earn:`, "info");
        earnCards.forEach((c, idx) => {
          const typeTag = c.isPunchCard ? " [周期打卡]" : "";
          const statusStr = c.locked ? "🔒 未解锁" : (c.completed ? "✔ 已完成" : "🎯 待执行");
          const ptsStr = c.points ? ` (+${c.points}分)` : "";
          addLog(`  ${idx + 1}. 【${c.title}】${typeTag}${ptsStr} -> 状态: ${statusStr}`, c.completed ? "info" : (c.locked ? "warning" : "success"));
        });

        const pendingEarnCards = earnCards.filter((c) => !c.completed && !c.locked && !completedCycleCardsToday.has(c.title));
        if (pendingEarnCards.length === 0) {
          addLog("🎉 积分赚取页面 (earn) 中的任务均已完成或无需执行！", "success");
        } else {
          addLog(`📋 发现 ${pendingEarnCards.length} 项待完成的赚取任务，开始执行...`, "info");
          runtimeState.dailySetTotal += pendingEarnCards.length;
          broadcastState();

          for (let i = 0; i < pendingEarnCards.length; i++) {
            if (runtimeState.stopped) break;
            const card = pendingEarnCards[i];

            if (card.isPunchCard) {
              // 周期打卡
              addLog(`[周期打卡 ${i + 1}/${pendingEarnCards.length}] 分析周期活动: 【${card.title}】...`, "info");
              await chrome.tabs.sendMessage(hostRewardsTab.id, { action: "CLICK_CARD", title: card.title, index: card.index }).catch(() => null);
              await sleep(2000);
              const drawerInfo = await chrome.tabs.sendMessage(hostRewardsTab.id, { action: "SOLVE_PUNCH_CARD_DRAWER" }).catch(() => null);
              if (drawerInfo && drawerInfo.allDoneForToday) {
                addLog(`✓ 周期打卡【${card.title}】今日阶段已完成！`, "success");
                completedCycleCardsToday.add(card.title);
                chrome.storage.local.set({ completedCycleCards: Array.from(completedCycleCardsToday) });
                runtimeState.dailySetDone++;
                broadcastState();
                continue;
              }
              const subtasks = (drawerInfo && drawerInfo.subtasks) || [];
              for (let s = 0; s < subtasks.length; s++) {
                if (runtimeState.stopped) break;
                const sub = subtasks[s];
                addLog(`  -> [子任务 ${s + 1}/${subtasks.length}] 执行: ${sub.title}...`, "info");
                const subCard = { title: sub.title, url: sub.url, points: 5, searchQuery: sub.title };
                await executeSingleCard(subCard, hostRewardsTab, s + 1, subtasks.length);
              }
              await chrome.tabs.sendMessage(hostRewardsTab.id, { action: "CLOSE_PUNCH_CARD_DRAWER" }).catch(() => null);
              await sleep(1500);
            } else {
              await executeSingleCard(card, hostRewardsTab, i + 1, pendingEarnCards.length);
            }
          }
        }
      } else {
        addLog("ℹ️ 积分赚取页面 (earn) 暂无其他待完成活动", "info");
      }

      addLog("==========================================", "info");
      addLog(`📊 所有卡片任务执行完毕！当前总积分: ${runtimeState.currentPoints}，连胜: ${runtimeState.streakDays} 天`, "success");
      broadcastState();

    } catch (err) {
      addLog(`执行日常任务卡片异常: ${err.message}`, "error");
    } finally {
      if (isRewardsTemp && hostRewardsTab) {
        await safeCloseTab(hostRewardsTab.id);
        managedTabIds.delete(hostRewardsTab.id);
      }
      for (const tabId of managedTabIds) {
        await safeCloseTab(tabId);
      }
      managedTabIds.clear();
    }
  }

// 2. 在当前窗口后台标签页中执行 PC 桌面端搜索任务 (绝不单独弹窗，做完即关)
async function performSearches() {
  const targetCount = userSettings.pcSearchCount;
  const modeName = "PC 端桌面搜索";
  runtimeState.currentStep = "pc_search";
  runtimeState.pcSearchTotal = targetCount;
  runtimeState.pcSearchDone = 0;
  broadcastState();

  addLog(`>>> 开始执行 ${modeName}，计划搜索 ${targetCount} 次 (后台标签页静默运行)...`, "info");

  let searchTab = null;
  let userActiveTabId = null;
  try {
    const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (activeTab) userActiveTabId = activeTab.id;
  } catch (e) {}

  try {
    searchTab = await chrome.tabs.create({
      url: "https://www.bing.com/",
      active: false
    });
    managedTabIds.add(searchTab.id);
    currentTaskTabId = searchTab.id;
    await waitForTabLoad(searchTab.id, 12000);
    await sleep(2000);

    for (let i = 0; i < targetCount; i++) {
      if (runtimeState.stopped) {
        addLog(`搜索已被用户主动停止`, "warning");
        break;
      }

      // 防风控冷却模式
      if (userSettings.cooldownMode && i > 0 && i % 4 === 0) {
        addLog(`[防风控冷却模式] 已完成 4 次搜索，根据规则暂停 15 分钟等待冷却解冻...`, "warning");
        sendNotification("防风控冷却等待", "已完成一组搜索，正在安全暂停15分钟...");
        for (let wait = 0; wait < 15 * 60; wait += 10) {
          if (runtimeState.stopped) break;
          await sleep(10000);
        }
        if (runtimeState.stopped) break;
        addLog(`[防风控冷却模式] 冷却结束，继续下一轮搜索！`, "info");
      }

      const keyword = getRandomSearchKeyword(userSettings.searchLang);
      const searchUrl = `https://www.bing.com/search?q=${encodeURIComponent(keyword)}&FORM=QBLH`;

      addLog(`[${modeName} ${i + 1}/${targetCount}] 后台搜索: "${keyword}"`, "info");

      if (runtimeState.stopped) break;
      try {
        await chrome.tabs.update(searchTab.id, { url: searchUrl });
        await waitForTabLoad(searchTab.id, 12000);
      } catch (tabErr) {
        if (runtimeState.stopped) break;
        throw tabErr;
      }

      // 平滑滚动
      await chrome.tabs.sendMessage(searchTab.id, { action: "SIMULATE_SCROLL" }).catch(() => null);

      const delayTime = getRandomDelay(userSettings.minDelay, userSettings.maxDelay);
      await sleep(delayTime);

      runtimeState.pcSearchDone = i + 1;
      broadcastState();
    }

    if (!runtimeState.stopped) {
      addLog(`${modeName} 全部完成！`, "success");
    }
  } catch (err) {
    if (!runtimeState.stopped) {
      addLog(`${modeName} 过程中出现异常: ${err.message}`, "error");
    }
  } finally {
    // 关键：搜索完成后彻底关闭搜索后台标签页！绝不残留！
    if (searchTab) {
      await safeCloseTab(searchTab.id);
      managedTabIds.delete(searchTab.id);
    }
    if (userActiveTabId) {
      chrome.tabs.update(userActiveTabId, { active: true }).catch(() => {});
    }
  }
}

// 3. 最终结算 (在后台标签页读取最终积分，读取完立即关闭)
async function finalizeRewards() {
  addLog(">>> 正在同步最终积分...", "info");
  let tab = null;
  try {
    tab = await chrome.tabs.create({ url: "https://rewards.bing.com/dashboard", active: false });
    managedTabIds.add(tab.id);
    await waitForTabLoad(tab.id, 12000);
    await sleep(2500);

    const response = await chrome.tabs.sendMessage(tab.id, { action: "GET_DASHBOARD_INFO" }).catch(() => null);
    if (response && response.success && response.data) {
      const finalPoints = response.data.currentPoints || runtimeState.currentPoints;
      const gained = runtimeState.startPoints > 0 ? Math.max(0, finalPoints - runtimeState.startPoints) : 0;
      runtimeState.currentPoints = finalPoints;
      runtimeState.todayPoints = gained;
      broadcastState();

      const summaryMsg = `今日任务已全部完成！当前总积分: ${finalPoints}${gained > 0 ? ` (本次新增 +${gained} 积分)` : ""}`;
      addLog(summaryMsg, "success");
      sendNotification("打卡大功告成！🎉", summaryMsg);
    }
  } catch (err) {
    addLog(`同步结算信息提示: ${err.message}`, "info");
  } finally {
    if (tab) {
      await safeCloseTab(tab.id);
      managedTabIds.delete(tab.id);
    }
  }

  const today = new Date().toISOString().slice(0, 10);
  runtimeState.lastRunDate = today;
  await chrome.storage.local.set({ lastRunDate: today });
}

// 启动全套自动化 (后台标签页静默运行，绝不单独弹窗)
async function startFullAutomation() {
  if (runtimeState.running) {
    addLog("任务已经在运行中，请勿重复启动", "warning");
    return;
  }

  runtimeState.running = true;
  runtimeState.stopped = false;
  runtimeState.startPoints = 0;
  broadcastState();
  addLog("==========================================", "info");
  addLog("🚀 开始执行 Microsoft Rewards 每日任务 (后台标签页静默运行)...", "info");

  try {
    // 1. 仪表盘日常任务与周期打卡
    if (userSettings.enableDailySet) {
      await runDashboardTasks();
    }

    // 2. PC 端桌面搜索
    if (userSettings.enablePcSearch && !runtimeState.stopped) {
      await performSearches();
    }

    // 3. 汇总积分与通知
    if (!runtimeState.stopped) {
      await finalizeRewards();
    }
  } catch (e) {
    addLog(`执行过程异常中断: ${e.message}`, "error");
  } finally {
    runtimeState.running = false;
    runtimeState.currentStep = "idle";
    broadcastState();
    for (const tabId of managedTabIds) {
      await safeCloseTab(tabId);
    }
    managedTabIds.clear();
    if (currentTaskTabId) {
      await safeCloseTab(currentTaskTabId);
    }
    addLog("所有任务已全部结束，后台标签页已全部关闭！", "info");
    addLog("==========================================", "info");
  }
}

// 停止自动化
async function stopAutomation() {
  if (!runtimeState.running) return;
  addLog("🛑 收到用户终止指令，正在停止所有任务...", "warning");
  runtimeState.stopped = true;
  runtimeState.running = false;
  runtimeState.currentStep = "idle";
  broadcastState();

  for (const tabId of managedTabIds) {
    await safeCloseTab(tabId);
  }
  managedTabIds.clear();

  if (currentTaskTabId) {
    await safeCloseTab(currentTaskTabId);
  }
  addLog("已安全停止并关闭后台标签页", "info");
}

// 单独任务执行入口
async function startSpecificTask(taskType) {
  if (runtimeState.running) {
    addLog("检测到已有正在执行的任务，正在自动切换...", "warning");
    await stopAutomation();
    await sleep(600);
  }

  runtimeState.running = true;
  runtimeState.stopped = false;
  broadcastState();

  try {
    if (taskType === "daily_set") {
      await runDashboardTasks();
    } else if (taskType === "pc_search") {
      await performSearches();
    }
  } catch (err) {
    addLog(`单项任务异常: ${err.message}`, "error");
  } finally {
    runtimeState.running = false;
    runtimeState.currentStep = "idle";
    broadcastState();
    if (currentTaskTabId) await safeCloseTab(currentTaskTabId);
  }
}

// 消息通信监听 (来自 popup)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "GET_STATE") {
    sendResponse({
      state: runtimeState,
      settings: userSettings,
      logs: activityLogs
    });
    return true;
  }

  if (request.action === "START_ALL") {
    startFullAutomation();
    sendResponse({ success: true });
    return true;
  }

  if (request.action === "START_TASK") {
    startSpecificTask(request.taskType);
    sendResponse({ success: true });
    return true;
  }

  if (request.action === "STOP") {
    stopAutomation();
    sendResponse({ success: true });
    return true;
  }

  if (request.action === "SAVE_SETTINGS") {
    userSettings = { ...userSettings, ...request.settings };
    chrome.storage.local.set({ settings: userSettings });
    setupDailyAlarm();
    addLog("用户设置已更新并保存", "info");
    sendResponse({ success: true });
    return true;
  }

  if (request.action === "CLEAR_LOGS") {
    activityLogs = [];
    sendResponse({ success: true });
    return true;
  }

  if (request.action === "TASK_SOLVED") {
    const typeMap = {
      puzzle: "🧩 拼图（已自动跳过）",
      poll: "📊 每日投票",
      quiz: "📝 测验问答",
      thisOrThat: "⚖️ 二选一"
    };
    const desc = typeMap[request.type] || request.type;
    addLog(`✓ 页面检测到【${desc}】任务并已自动完成！`, "success");
    sendResponse({ success: true });
    return true;
  }
});
