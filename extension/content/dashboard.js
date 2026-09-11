// rewards.bing.com 仪表盘解析与自动化内容脚本
// 严格只锁定：每日任务 (Daily Set & Activities) + 周期任务 (Punch Card)，彻底排除已完成/未解锁/兑换/抽奖/徽章/统计卡片
(() => {
  let cachedCardElements = [];

  // 自动检测并关闭微软可能弹出的“必应应用连续打卡”或“立即签入”抽屉/模态框
  function dismissBingAppModal() {
    try {
      const dialogs = document.querySelectorAll(
        "div[role='dialog'], [class*='modal'], [class*='dialog'], [class*='drawer'], [class*='flyout'], [class*='popup']"
      );
      for (const d of dialogs) {
        const text = d.innerText || "";
        if (
          text.includes("必应应用") ||
          text.includes("立即签入") ||
          text.includes("每天签到必应应用") ||
          text.includes("使用 Edge 浏览 30 分钟") ||
          text.includes("Rewards app only") ||
          text.includes("app only") ||
          text.includes("在必应应用中")
        ) {
          const closeBtn = d.querySelector(
            "button[aria-label*='Close' i], button[aria-label*='关闭' i], button.c-glyph, [class*='close' i], svg[class*='close']"
          );
          if (closeBtn && typeof closeBtn.click === "function") {
            console.log("[MS Rewards] 发现非必要打卡/App专属弹窗，已自动点击 ✕ 关闭！");
            closeBtn.click();
          }
        }
      }
    } catch (e) {}
  }

  // 强制滚动页面以触发所有懒加载任务卡片渲染（针对后台标签页禁用 smooth 动画机制，采用即时滚动）
  async function scrollAndTriggerLazyLoad() {
    dismissBingAppModal();
    const delay = (ms) => new Promise((r) => setTimeout(r, ms));
    
    // 动态向下滚动以触发所有懒加载任务卡片
    let pos = 200;
    for (let iter = 0; iter < 12; iter++) {
      const scrollH = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, 2800);
      pos += 450;
      window.scrollTo(0, pos);
      document.documentElement.scrollTop = pos;
      await delay(120);
      if (pos >= scrollH) break;
    }
    // 滚到底部停留
    window.scrollTo(0, document.body.scrollHeight);
    document.documentElement.scrollTop = document.body.scrollHeight;
    await delay(350);

    // 滚回顶部
    window.scrollTo(0, 0);
    document.documentElement.scrollTop = 0;
    await delay(200);
    dismissBingAppModal();
  }

  // 严格检测是否属于非任务区域（网站导航栏、底部、个人总积分统计、兑换商店与目标挂件）
  function isNonTaskArea(el) {
    if (!el) return false;
    return !!el.closest(
      "body > header, nav, footer, #userStatus, mee-rewards-user-status, .headline-total-points, [data-bi-area*='redeem'], [data-bi-area*='goal'], #redeem, .redeem-container"
    );
  }

  // 严格检测是否为禁止点击的非任务项目（兑换、抽奖、券包、徽章、统计、App-only）
  function isDisallowedTask(title, text, el) {
    const combined = (title + " " + text).trim();

    // 1. 兑换 / 抽奖 / 礼品卡 / 券包
    if (
      /抽奖|券包|礼品卡|兑换|打折|优惠券|捐赠|捐款|sweepstakes|redeem|gift\s*card|voucher|donate/i.test(
        combined
      )
    ) {
      return true;
    }

    // 2. 徽章 / 成就（例如：办公室伙伴, DOS 老大, 音频迷等，注意严防误伤“网络英雄”）
    if (
      /徽章|成就|勋章|称号|办公室伙伴|DOS\s*老大|音频迷|(?<!网络)本地英雄|badges?|achievements?/i.test(
        combined
      )
    ) {
      return true;
    }

    // 3. 个人信息 / 统计栏 / 状态说明（可用积分、积分上限、可领取等完全匹配）
    if (
      /^(?:可用积分|积分上限|可领取|总积分|当前总积分|本次获取积分|连胜天数|连胜|波罗|个人资料|目标|查看全部|状态|级别|等级|设置|帮助|反馈|隐私|条款|Points|Available|Breakdown|Streak|Level|Status|Goal|你的进度|每日连续打卡|连签奖励|活动|必应|Microsoft Edge)$/i.test(
        title.trim()
      )
    ) {
      return true;
    }

    // 4. Rewards App Only 手机专属 (仅排除真正的手机专属/App下载/30分钟浏览打卡，绝不排除常规桌面任务)
    if (
      /rewards\s*app\s*only|app\s*only|仅限.*应用|必应应用|在移动设备上|仅移动设备|下载.*应用|立即签入|签到\s*:\s*\d+\/\d+|每天签到|在.*应用中|使用\s*Edge\s*浏览\s*\d+\s*分钟|浏览\s*\d+\s*分钟/i.test(
        combined
      )
    ) {
      return true;
    }

    // 5. DOM 容器判定
    if (el && isNonTaskArea(el)) {
      return true;
    }

    return false;
  }

  // 精确定位单张卡片的完整容器（向上遍历精确定位单卡片，严禁向上跨入包含多张卡片的网格/列容器）
  function getFullCardContainer(badgeNode) {
    if (!badgeNode) return null;

    let cur = badgeNode;
    let best = badgeNode;
    let depth = 0;

    while (cur && cur !== document.body && cur !== document.documentElement && depth < 8) {
      if (isNonTaskArea(cur)) break;

      const txt = (cur.innerText || "").trim();

      // 检查当前节点是否已膨胀为包含多个卡片（含有多个加分/对勾徽章）或包含了大板块标题
      const pointsMatches = txt.match(/(?:\+\s*\d+|[✔✓]\s*\d*)/g) || [];
      const hasSectionHeader = /^(?:每日活动|更多活动|你的进度|连签奖励|活动)\b/m.test(txt);

      if (pointsMatches.length > 1 || hasSectionHeader) {
        break; // 停止向上，上一层 best 即为该单卡片的完整容器
      }

      best = cur;

      // 如果遇到明确的卡片标签或类名，且包含单卡片特征，优先采纳
      const cl = (cur.className || "").toString();
      if (
        cur.tagName === "MEE-CARD" ||
        /c-card|mee-card|card-item|activity-card|fui-Card/i.test(cl) ||
        (cur.tagName === "A" && /card/i.test(cl))
      ) {
        break;
      }

      cur = cur.parentElement;
      depth++;
    }
    return best;
  }

  // 辅助检测：是否为未解锁任务 (Locked)
  function isLockedElement(card, text) {
    if (!card) return false;
    const cardText = text || (card.innerText || "");
    const lines = cardText.split("\n").map((s) => s.trim()).filter(Boolean);

    // 1. 严格检查是否包含锁定/级别限制文本（如“需要银牌级别”、“需要金牌级别”、“未解锁”、“锁定”）
    const hasLockText = lines.some((l) =>
      /需要.*(?:级别|等级|银牌|金牌)|锁定|\blocked\b|未解锁|解锁条件|等待\s*\d+\s*小时/i.test(l)
    ) || /需要.*(?:级别|等级|银牌|金牌)|锁定|\blocked\b|未解锁|解锁条件|等待\s*\d+\s*小时/i.test(cardText);
    if (hasLockText) return true;

    // 2. 检查是否有明确的锁图标
    if (
      card.querySelector(
        "[class*='lock' i], svg[class*='lock' i], path[d*='lock' i], [aria-label*='lock' i], [aria-label*='锁' i]"
      )
    ) {
      return true;
    }

    // 3. 检查是否有 disabled 属性
    const btn = card.querySelector("button, [role='button'], a");
    if (
      btn &&
      (btn.hasAttribute("disabled") ||
        btn.getAttribute("aria-disabled") === "true" ||
        /disabled/i.test(btn.className))
    ) {
      return true;
    }

    return false;
  }

  // 精准提取单张卡片的纯净标题（杜绝与副标题、积分、已完成等文本挤在一块）
  function extractCardTitle(card) {
    if (!card) return "";

    // 1. 优先查找具有明确标题特征的元素
    const heading = card.querySelector(
      "h1, h2, h3, h4, h5, [class*='title' i], [class*='heading' i], [id*='title' i]"
    );
    if (heading) {
      let t = (heading.innerText || heading.textContent || "").trim();
      t = t.replace(/\+\s*\d+$/, "").replace(/[✔✓]\s*\d*$/, "").replace(/已完成$/, "").trim();
      if (t.length >= 2 && t.length <= 40 && !/^\+?\d+/.test(t) && !/^[✔✓]/.test(t)) {
        return t;
      }
    }

    // 2. 检查 data-bi-name 或 title 属性
    const biName = card.getAttribute("data-bi-name") || card.getAttribute("title");
    if (biName && biName.length >= 2 && biName.length <= 40 && !/^(?:card|item|tile)$/i.test(biName)) {
      return biName;
    }

    // 3. 从内部叶子节点中寻找第一个有效的标题候选
    const all = Array.from(card.querySelectorAll("p, span, div, a"));
    for (const el of all) {
      if (el.children.length === 0) {
        let t = (el.innerText || el.textContent || "").trim();
        t = t.replace(/\+\s*\d+$/, "").replace(/[✔✓]\s*\d*$/, "").replace(/已完成$/, "").trim();
        if (
          t.length >= 2 &&
          t.length <= 35 &&
          !/^\+?\s*\d+$/.test(t) &&
          !/^[✔✓]/.test(t) &&
          !/^(?:已完成|Completed|已领取|需要.*级别|锁定|未解锁|重置.*|详细信息|查看.*|了解更多|到期日期)$/i.test(t) &&
          !/^(?:可用积分|积分上限|可领取|总积分|连胜天数|连胜|波罗|个人资料|目标|状态|级别|等级|设置|帮助|反馈|隐私|条款|Points|Available|Streak|Level|Status|Goal|你的进度|每日连续打卡|连签奖励|活动|必应|Microsoft Edge)$/i.test(t)
        ) {
          return t;
        }
      }
    }

    return "";
  }

  // 辅助检测：卡片是否包含真实渲染展示的加分徽章（例如 "+10", "+5"）
  function hasVisiblePointsBadge(card) {
    if (!card) return false;
    const allLeaf = card.querySelectorAll("span, div, p, a, button, b, strong");
    for (const el of allLeaf) {
      if (el.children.length === 0) {
        const txt = (el.innerText || el.textContent || "").trim();
        // 匹配独立的 "+10", "+5", "+30", "+50" 等加分文本
        if (/^\+\s*\d+$/.test(txt) || /^\+\s*\d+\s*(?:分|pts?)?$/i.test(txt)) {
          try {
            const style = window.getComputedStyle(el);
            if (
              style.display !== "none" &&
              style.visibility !== "hidden" &&
              parseFloat(style.opacity || "1") > 0 &&
              el.getBoundingClientRect().width > 0
            ) {
              return true;
            }
          } catch (e) {
            return true;
          }
        }
      }
    }
    return false;
  }

  // 辅助检测：卡片是否包含真实渲染展示的绿色对勾或已完成图标
  function hasVisibleCheckmark(card) {
    if (!card) return false;

    // 1. 查找文本中是否有独立的对勾符号且其元素真实可见
    const allLeaf = card.querySelectorAll("span, div, p, i, svg, b, strong");
    for (const leaf of allLeaf) {
      if (leaf.children.length === 0) {
        const txt = (leaf.innerText || leaf.textContent || "").trim();
        if (/^[✔✓]/.test(txt)) {
          try {
            const style = window.getComputedStyle(leaf);
            if (
              style.display !== "none" &&
              style.visibility !== "hidden" &&
              parseFloat(style.opacity || "1") > 0 &&
              leaf.getBoundingClientRect().width > 0
            ) {
              return true;
            }
          } catch (e) {}
        }
      }
    }

    // 2. 查找对勾类名或图标元素（必须真实可见，严禁匹配模板中 display:none 的对勾）
    const checkCandidates = card.querySelectorAll(
      ".mee-icon-CheckMark, svg[class*='check' i], [class*='checkMark' i], [class*='c-glyph-checkmark' i], [class*='completed-icon' i]"
    );
    for (const el of checkCandidates) {
      const aria = (el.getAttribute("aria-label") || "").trim();
      if (/未完成|完成以|完成可|完成此|complete to|not completed/i.test(aria)) {
        continue;
      }
      try {
        const style = window.getComputedStyle(el);
        if (
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          parseFloat(style.opacity || "1") > 0 &&
          el.getBoundingClientRect().width > 0
        ) {
          return true;
        }
      } catch (e) {}
    }

    // 3. 严格的无障碍描述检查（只匹配严格的“已完成”或“Completed”，严禁匹配“完成以获取10积分”）
    const ariaEls = card.querySelectorAll("[aria-label*='已完成' i], [aria-label='Completed' i], [aria-label*='状态: 已完成' i]");
    for (const el of ariaEls) {
      const aria = (el.getAttribute("aria-label") || "").trim();
      if (!/未完成|完成以|完成可|完成此|complete to|not completed/i.test(aria)) {
        try {
          const style = window.getComputedStyle(el);
          if (style.display !== "none" && style.visibility !== "hidden") {
            return true;
          }
        } catch (e) {}
      }
    }

    return false;
  }

  // 辅助检测：是否为已完成任务 (Completed) —— 严格只针对本卡片内部检查
  function isCompletedElement(card, text) {
    if (!card) return false;

    // 黄金铁律 1：如果卡片清晰展示着加分徽章（例如 "+10"、"+5" 等），并且没有真实渲染的对勾，则 100% 为待执行（未完成）！
    const hasPointsBadge = hasVisiblePointsBadge(card);
    const hasCheck = hasVisibleCheckmark(card);

    if (hasPointsBadge && !hasCheck) {
      return false; // 绝对未完成！
    }

    if (hasCheck) {
      return true; // 发现真实渲染可见的对勾，已完成！
    }

    // 2. 检查文本中是否包含明确的“已完成”独立词汇（严格排除“未完成”、“完成以获取”等提示短语）
    const cardText = text || (card.innerText || "");
    if (/已完成|Completed/i.test(cardText)) {
      if (!/未完成|完成以|完成可|完成此|complete to|not completed/i.test(cardText)) {
        return true;
      }
    }

    return false;
  }

  // 从页面的 <script> 标签中提取微软官方任务元数据 (提取真实 destinationUrl 与完成状态)
  function extractScriptData() {
    const map = new Map();
    try {
      const scripts = Array.from(document.querySelectorAll("script"));
      for (const s of scripts) {
        const txt = s.textContent || "";
        if (!txt.includes("dailySetPromotions") && !txt.includes("morePromotions") && !txt.includes("destinationUrl")) {
          continue;
        }

        // 1. 尝试 JSON.parse (针对 __NEXT_DATA__ 或 application/json)
        if (s.type === "application/json" || s.id === "__NEXT_DATA__") {
          try {
            const data = JSON.parse(txt);
            const props = data.props && data.props.pageProps;
            const dash = (props && props.dashboardData) || (props && props.userData) || data.dashboardData || data;
            if (dash) {
              if (dash.dailySetPromotions) {
                const ds = Object.values(dash.dailySetPromotions).flat();
                for (const it of ds) {
                  if (it) {
                    it.isDailySet = true;
                    const t = (it.title || it.name || "").replace(/<[^>]+>/g, "").trim();
                    if (t && it.destinationUrl) map.set(t, it);
                  }
                }
              }
              const otherItems = [
                dash.morePromotions,
                dash.promotions,
                dash.punchCards
              ].filter(Boolean).flat();
              for (const it of otherItems) {
                if (!it) continue;
                it.isDailySet = false;
                const t = (it.title || it.name || "").replace(/<[^>]+>/g, "").trim();
                if (t && it.destinationUrl && !map.has(t)) {
                  map.set(t, it);
                }
              }
            }
          } catch (e) {}
        }

        // 2. 针对普通内联脚本，精准提取包含 destinationUrl 的每个任务对象块
        const blockRegex = /\{[^{}]{15,800}\}/g;
        let bm;
        while ((bm = blockRegex.exec(txt)) !== null) {
          const block = bm[0];
          if (!block.includes("destinationUrl")) continue;
          const tm = block.match(/["']?(?:title|name)["']?\s*:\s*["']([^"']+)["']/);
          const um = block.match(/["']?destinationUrl["']?\s*:\s*["'](https?:\/\/[^"']+)["']/);
          if (tm && um) {
            const t = tm[1].replace(/<[^>]+>/g, "").trim();
            const u = um[1];
            // 严格检查：只有当明确存在 complete: true 且没有加分进度待完成时才算完成
            const isComp = /["']?complete["']?\s*:\s*true/i.test(block) && !/["']?pointProgress["']?\s*:\s*0\b/.test(block);
            if (t && u && !map.has(t)) {
              map.set(t, { title: t, destinationUrl: u, complete: isComp });
            }
          }
        }
      }
    } catch (e) {
      console.warn("[MS Rewards] 解析 script 数据源异常:", e);
    }
    return map;
  }

  // 全方位提取真实带凭证的活动 Promotion URL
  function extractPromoUrl(card, title, scriptDataMap) {
    if (!card) return "";

    // 1. 如果在页面脚本数据源中匹配到了官方 destinationUrl，绝对优先采用！
    if (scriptDataMap && title) {
      const cleanT = title.trim();
      for (const [sTitle, item] of scriptDataMap.entries()) {
        if (sTitle === cleanT || sTitle.includes(cleanT) || cleanT.includes(sTitle)) {
          if (item && item.destinationUrl) {
            return item.destinationUrl;
          }
        }
      }
    }

    // 2. 检查卡片容器自带属性
    let url =
      card.getAttribute("data-bi-url") ||
      card.getAttribute("data-href") ||
      card.getAttribute("data-destination-url") ||
      card.getAttribute("href");

    // 3. 如果卡片本身就是 <a> 标签
    if (!url && card.tagName === "A" && card.href && !card.href.startsWith("javascript:")) {
      url = card.href;
    }

    // 4. 在卡片容器内查找 <a> 链接
    if (!url) {
      const anchors = Array.from(card.querySelectorAll("a[href]")).filter(
        (a) => a.href && !a.href.startsWith("javascript:") && !a.href.endsWith("#")
      );
      // 优先寻找带有 Rewards 任务凭证 (filters, FORM, publ, id 等) 的促销链接
      const promoAnchor = anchors.find(
        (a) =>
          (/bing\.com/i.test(a.href) && /[?&](?:filters|FORM|publ|id)=/i.test(a.href)) ||
          (/rewards\.bing\.com/i.test(a.href) && !a.href.endsWith("/dashboard") && !a.href.endsWith("/earn")) ||
          /go\.microsoft\.com/i.test(a.href)
      );
      if (promoAnchor) {
        url = promoAnchor.href;
      } else if (anchors.length > 0) {
        url = anchors[0].href;
      }
    }

    // 5. 检查包裹卡片的外层 <a>
    if (!url) {
      const parentAnchor = card.closest("a[href]");
      if (parentAnchor && parentAnchor.href && !parentAnchor.href.startsWith("javascript:")) {
        url = parentAnchor.href;
      }
    }

    // 6. 查找子元素内的 data 属性
    if (!url) {
      const elWithData = card.querySelector("[data-bi-url], [data-href], [data-destination-url]");
      if (elWithData) {
        url =
          elWithData.getAttribute("data-bi-url") ||
          elWithData.getAttribute("data-href") ||
          elWithData.getAttribute("data-destination-url");
      }
    }

    // 规范化相对链接
    if (url && !url.startsWith("http")) {
      try {
        url = new URL(url, window.location.origin).href;
      } catch (e) {}
    }

    return url || "";
  }

  // 提取用户积分、等级与真正有效的日常任务卡片与周期打卡
  function parseDashboardData() {
    dismissBingAppModal();
    let currentPoints = 0;
    let todayPoints = 0;
    let streakDays = 0;

    // 1. 提取当前总积分（严格限定为真实积分区间 1 ~ 2,000,000，防止任何数字乱码）
    const pointsSelectors = [
      ".headline-total-points",
      "#userStatus .points-count",
      "mee-rewards-user-status .points-count",
      "span[aria-label*='可用积分']",
      "span[aria-label*='available points']",
      ".pointsDetail .c-heading",
      "#userPoints",
      "[data-test-id='user-points']"
    ];

    for (const sel of pointsSelectors) {
      const el = document.querySelector(sel);
      if (el) {
        const text = (el.innerText || el.textContent || "").trim();
        const m = text.match(/\b\d{1,3}(?:,\d{3})+\b/) || text.match(/\b\d{2,6}\b/);
        if (m) {
          const num = parseInt(m[0].replace(/,/g, ""), 10);
          if (!isNaN(num) && num > 0 && num < 2000000) {
            currentPoints = num;
            break;
          }
        }
      }
    }

    if (currentPoints === 0) {
      const allElems = Array.from(document.querySelectorAll("*"));
      const ptsContainer = allElems.find((el) => {
        if (el.children.length > 2) return false;
        const t = (el.innerText || "").trim();
        return (t.includes("可用积分") || t.includes("available points")) && /\d+/.test(t);
      });
      if (ptsContainer) {
        const text = ptsContainer.innerText || "";
        const m = text.match(/(?:可用积分|available\s*points)\D*(\d[\d,]*)/i) ||
                  text.match(/(\d[\d,]*)\D*(?:可用积分|available\s*points)/i) ||
                  text.match(/\b\d{1,3}(?:,\d{3})+\b/) ||
                  text.match(/\b\d{2,6}\b/);
        if (m) {
          const num = parseInt((m[1] || m[0]).replace(/,/g, ""), 10);
          if (!isNaN(num) && num > 0 && num < 2000000) currentPoints = num;
        }
      }
    }

    // 2. 提取连胜天数
    const streakEl = document.querySelector(".streak-count, [aria-label*='天'], [aria-label*='day streak']");
    if (streakEl) {
      const text = streakEl.innerText || streakEl.textContent || "";
      const m = text.match(/\b\d{1,4}\b/);
      if (m) {
        const num = parseInt(m[0], 10);
        if (!isNaN(num) && num >= 0 && num < 5000) streakDays = num;
      }
    }
    if (streakDays === 0) {
      const allStreakNodes = Array.from(document.querySelectorAll("div, span, p")).filter((el) => el.children.length <= 2);
      const sNode = allStreakNodes.find((el) => /每日连续打卡|连续打卡|连签|day streak/i.test((el.innerText || "").trim()));
      if (sNode) {
        const parentText = (sNode.parentElement ? sNode.parentElement.innerText : "") || (sNode.innerText || "");
        const m = parentText.match(/(\d+)\s*天/);
        if (m) streakDays = parseInt(m[1], 10);
      }
    }

    // 3. 提取用户等级
    let userLevel = 1;
    const levelEl = document.querySelector("#userLevel, .user-level, [aria-label*='级别'], [aria-label*='Level']");
    if (levelEl && /level\s*2|级别\s*2|等级\s*2/i.test(levelEl.innerText)) {
      userLevel = 2;
    }

    // 4. 精准寻找页面中的任务卡片 (每日活动 + 更多活动 + 周期打卡，无死角全量识别)
    const activityCards = [];
    cachedCardElements = [];

    // 辅助判定一个元素是否属于“每日活动”区域
    function isDailySetCard(el) {
      if (!el) return false;
      if (el.closest("[class*='daily' i], [id*='daily' i], [data-bi-area*='daily' i]")) return true;

      const allHeadings = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, div, span, p"));
      const dailyHeader = allHeadings.find((h) => {
        if (h.children.length > 2) return false;
        return /^(?:每日活动|Daily\s*set)\b/i.test((h.innerText || "").trim());
      });
      const moreHeader = allHeadings.find((h) => {
        if (h.children.length > 2) return false;
        return /^(?:更多活动|More\s*activities)\b/i.test((h.innerText || "").trim());
      });

      if (dailyHeader) {
        const cmpDaily = dailyHeader.compareDocumentPosition(el);
        const isAfterDaily = (cmpDaily & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
        if (moreHeader) {
          const cmpMore = moreHeader.compareDocumentPosition(el);
          const isBeforeMore = (cmpMore & Node.DOCUMENT_POSITION_PRECEDING) !== 0;
          if (isAfterDaily && isBeforeMore) return true;
        } else if (isAfterDaily) {
          return true;
        }
      }

      if (window.location.pathname.includes("/dashboard")) {
        return true;
      }

      return false;
    }

    // 提取页面官方脚本元数据
    const scriptDataMap = extractScriptData();

    // 收集所有候选卡片 DOM 节点
    const candidateNodes = [];
    const potentialElements = Array.from(
      document.querySelectorAll(
        "mee-card, [class*='c-card' i], [class*='card-item' i], [class*='activity-card' i], [class*='fui-Card' i], [data-bi-name], a, div, section, li, article"
      )
    );

    potentialElements.forEach((el) => {
      if (isNonTaskArea(el)) return;
      const text = (el.innerText || "").trim();
      if (text.length < 4 || text.length > 400) return;

      const hasCardFeature =
        /(?:\+\s*\d+|[✔✓]\s*\d*|\b\d+\s*分\b|已完成|需要.*级别|锁定|\blocked\b)/i.test(text) ||
        /\d+\s*\/\s*\d+\s*(?:个?任务|tasks?)/i.test(text);
      if (!hasCardFeature) return;

      const lines = text.split("\n").map((s) => s.trim()).filter(Boolean);
      const titleCandidate = lines.find(
        (l) =>
          l.length >= 2 &&
          l.length <= 45 &&
          !/^\+?\s*\d+$/.test(l) &&
          !/^[✔✓]/.test(l) &&
          !/^(?:已完成|Completed|已领取|需要.*级别|锁定|未解锁|重置.*|详细信息|查看.*|了解更多|到期日期)$/i.test(l) &&
          !/^(?:可用积分|积分上限|可领取|总积分|连胜天数|连胜|波罗|个人资料|目标|状态|级别|等级|设置|帮助|反馈|隐私|条款|Points|Available|Streak|Level|Status|Goal|你的进度|每日连续打卡|连签奖励|活动|必应|Microsoft Edge)$/i.test(l) &&
          !/\d+\/\d+\s*(?:个?任务|tasks?)/i.test(l)
      );

      if (!titleCandidate) return;
      if (isDisallowedTask(titleCandidate, text, el)) return;

      candidateNodes.push({ el, title: titleCandidate, text });
    });

    // 核心改进：为每个候选标题节点精准匹配其【单张卡片完整容器】，杜绝叶子节点丢失链接与状态！
    const processedContainers = new Set();
    const processedTitles = new Set();

    candidateNodes.forEach(({ el, title: rawTitle }) => {
      const card = getFullCardContainer(el);
      if (!card || processedContainers.has(card)) return;

      const cardText = (card.innerText || "").trim();
      const title = extractCardTitle(card) || rawTitle.trim();
      if (!title || processedTitles.has(title)) return;
      if (isDisallowedTask(title, cardText, card)) return;

      processedContainers.add(card);
      processedTitles.add(title);

      let subtitle = "";
      const descEl = card.querySelector("p, [class*='desc' i], [class*='sub' i]");
      if (descEl) {
        subtitle = (descEl.innerText || descEl.textContent || "").trim();
      }

      let points = 0;
      const ptsMatch = cardText.match(/\+\s*(\d+)/) || cardText.match(/[✔✓]\s*(\d+)/);
      if (ptsMatch) {
        points = parseInt(ptsMatch[1], 10);
      } else {
        const badges = card.querySelectorAll("span, div, p");
        for (const b of badges) {
          if (b.children.length === 0) {
            const bt = (b.innerText || "").trim();
            if (/^\d{1,3}$/.test(bt)) {
              points = parseInt(bt, 10);
              break;
            }
          }
        }
      }

      const isDaily = isDailySetCard(card);
      if (isDaily && points === 0) points = 10;
      if (!isDaily && points === 0) points = 5;

      const searchQuery = title;
      const isLocked = isLockedElement(card, cardText);

      const punchMatch = cardText.match(/(\d+)\s*\/\s*(\d+)\s*(?:个?任务|tasks?)/i);
      let isPunchCard = false;
      let punchCompleted = false;
      let currentStep = 0;
      let totalSteps = 0;
      if (punchMatch) {
        isPunchCard = true;
        currentStep = parseInt(punchMatch[1], 10);
        totalSteps = parseInt(punchMatch[2], 10);
        punchCompleted = currentStep >= totalSteps;
      }

      const hasPointsBadge = hasVisiblePointsBadge(card);
      let isCompleted = punchCompleted || (!isPunchCard && isCompletedElement(card, cardText));

      // 提取带有 Rewards 促销凭证的真实链接
      let href = extractPromoUrl(card, title, scriptDataMap);
      if (!href) {
        href = `https://www.bing.com/search?q=${encodeURIComponent(searchQuery)}&FORM=QBLH`;
      }

      cachedCardElements.push(card);

      activityCards.push({
        id: `act_${activityCards.length}`,
        title,
        subtitle,
        points,
        searchQuery,
        completed: isCompleted,
        hasPointsBadge,
        locked: isLocked,
        testMode: false,
        isPunchCard,
        isDailySet: isDaily,
        currentStep,
        totalSteps,
        url: href,
        index: activityCards.length - 1
      });
    });

    // 补充：比对 scriptDataMap 中可能存在的其他未在 DOM 中完全渲染的任务
    if (scriptDataMap && scriptDataMap.size > 0) {
      for (const [sTitle, item] of scriptDataMap.entries()) {
        if (!sTitle || /抽奖|券包|礼品卡|兑换|优惠券|办公室伙伴|DOS|音频迷|(?<!网络)本地英雄|可用积分|积分上限|波罗/i.test(sTitle)) continue;

        const existing = activityCards.find((c) => c.title === sTitle || c.title.includes(sTitle) || sTitle.includes(c.title));
        if (existing) {
          if (item.destinationUrl && (!existing.url || existing.url.includes("FORM=QBLH"))) {
            existing.url = item.destinationUrl;
          }
          // 只有在卡片未渲染出 "+10" 等待完成加分徽章时，才允许脚本数据标记已完成
          if (item.complete && !existing.hasPointsBadge) {
            existing.completed = true;
          }
          if (item.isDailySet) {
            existing.isDailySet = true;
          }
        } else {
          // DOM 未扫描到该卡片，直接由官方数据源补全，彻底杜绝扫描为 0 项！
          const pts = item.pointProgressMax || (item.isDailySet ? 10 : 5);
          activityCards.push({
            id: `act_${activityCards.length}`,
            title: sTitle,
            subtitle: item.description || "",
            points: pts,
            searchQuery: sTitle,
            completed: !!item.complete,
            locked: false,
            testMode: false,
            isPunchCard: false,
            isDailySet: !!item.isDailySet,
            currentStep: 0,
            totalSteps: 0,
            url: item.destinationUrl || `https://www.bing.com/search?q=${encodeURIComponent(sTitle)}&FORM=QBLH`,
            index: activityCards.length
          });
        }
      }
    }

    return {
      currentPoints,
      todayPoints,
      streakDays,
      userLevel,
      activityCards,
      dailySetItems: activityCards
    };
  }

  // 触发卡片执行 (提取真实活动链接，绝不在前台派发事件避免弹窗抢焦点)
  async function triggerCardClick(title, index) {
    dismissBingAppModal();
    let card = null;

    if (typeof index === "number" && cachedCardElements[index]) {
      card = cachedCardElements[index];
    }
    if (!card && title) {
      const cleanTitle = title.trim();
      card = cachedCardElements.find((c) => (c.innerText || "").includes(cleanTitle));
      if (!card) {
        const allPossible = Array.from(document.querySelectorAll("a, button, [role='button'], div[class*='card']"));
        card = allPossible.find((c) => (c.innerText || "").includes(cleanTitle) && c.offsetParent !== null);
      }
    }

    if (!card) {
      return { success: false, message: `未找到卡片: ${title || index}` };
    }

    const cardText = (card.innerText || "").trim();

    // 双重校验：如果是抽奖、兑换、徽章、未解锁或已完成，严禁点击打开
    if (isDisallowedTask(title, cardText, card)) {
      return { success: false, skipped: true, message: `跳过非任务卡片: ${title}` };
    }
    if (isLockedElement(card, cardText)) {
      return { success: false, skipped: true, message: `跳过未解锁任务: ${title}` };
    }
    if (isCompletedElement(card, cardText)) {
      return { success: false, skipped: true, message: `跳过已完成任务: ${title}` };
    }

    const isPunchCard =
      /(\d+)\s*\/\s*(\d+)\s*(?:个?任务|tasks?)/i.test(cardText) ||
      !!card.querySelector("[class*='punchcard' i], [class*='punchCard' i]");

    if (isPunchCard) {
      // 周期任务 / 组合打卡：只需在后台展开抽屉，不打开外链
      const expandBtn =
        card.querySelector("button, [role='button'], .c-accordion, [class*='header']") || card;
      const eventOpts = { bubbles: true, cancelable: true, view: window };
      expandBtn.dispatchEvent(new MouseEvent("click", eventOpts));
      if (typeof expandBtn.click === "function") {
        expandBtn.click();
      }
      setTimeout(dismissBingAppModal, 600);
      return {
        success: true,
        isPunchCard: true,
        message: `已在后台展开周期打卡抽屉: ${title || index}`
      };
    }

    // 提取真实的促销跳转 URL
    const scriptDataMap = extractScriptData();
    let targetUrl = extractPromoUrl(card, title, scriptDataMap);
    if (!targetUrl) {
      targetUrl = `https://www.bing.com/search?q=${encodeURIComponent(title)}&FORM=QBLH`;
    }

    // 纯静默返回链接，由 background.js 在当前窗口后台标签页（active: false）中执行，杜绝前台弹窗！
    setTimeout(dismissBingAppModal, 600);
    return {
      success: true,
      url: targetUrl,
      isPunchCard: false,
      message: `已提取真实活动促销链接: ${title || index}`
    };
  }

  // 组合打卡抽屉 (Punch Card Drawer / 周期任务) 智能分析与处理
  async function solvePunchCardDrawer() {
    dismissBingAppModal();
    const delay = (ms) => new Promise((r) => setTimeout(r, ms));
    await delay(1200);

    // 查找打卡抽屉中的子任务节点
    const selectors = [
      "mee-rewards-punch-card-item",
      "[class*='punchcard'] [class*='item']",
      "[class*='punchCardItem']",
      "div[class*='drawer'] a[href]",
      "div[role='dialog'] a[href]",
      "[data-bi-name*='punchcard']"
    ];
    let items = Array.from(document.querySelectorAll(selectors.join(",")));

    if (items.length === 0) {
      const allLinks = Array.from(
        document.querySelectorAll("div[role='dialog'] a, div[class*='drawer'] a, [class*='flyout'] a")
      );
      items = allLinks.filter((a) => a.offsetParent !== null && (a.innerText || "").length > 2);
    }

    let completedCount = 0;
    let lockedCount = 0;
    const actionableSubtasks = [];

    for (const item of items) {
      const text = item.innerText || "";

      // 判定是否已完成
      if (isCompletedElement(item, text)) {
        completedCount++;
        continue;
      }

      // 判定是否未解锁（带有锁图标、等待24小时、禁用按钮等）
      if (isLockedElement(item, text) || /等待\s*\d+\s*小时/i.test(text)) {
        lockedCount++;
        continue;
      }

      // 判定是否属于非任务
      if (isDisallowedTask(text, text, item)) {
        continue;
      }

      // 属于当前真正可执行的子任务
      let href = item.tagName === "A" ? item.href : (item.querySelector("a") ? item.querySelector("a").href : "");
      const lines = text.split("\n").map((s) => s.trim()).filter(Boolean);
      const title = lines.filter((l) => !/^\+?\d+/.test(l) && !/^(已完成|需要|重置)/.test(l))[0] || "打卡子项";

      actionableSubtasks.push({
        title,
        url: href
      });
    }

    // 如果所有未完成的子项都处于锁定状态（例如需等待 24 小时解锁），说明今日阶段已满！
    const allDoneForToday = actionableSubtasks.length === 0 && (completedCount > 0 || lockedCount > 0);

    if (allDoneForToday) {
      console.log("[MS Rewards] 周期任务检测：今日阶段已打卡完毕，其余任务需等待24小时冷却解锁，自动关闭抽屉。");
      closePunchCardDrawer();
    }

    return {
      subtasksCount: actionableSubtasks.length,
      subtasks: actionableSubtasks,
      completedCount,
      lockedCount,
      allDoneForToday
    };
  }

  // 关闭组合打卡抽屉
  function closePunchCardDrawer() {
    const closeBtns = document.querySelectorAll(
      "div[role='dialog'] button[aria-label*='Close' i], div[class*='drawer'] button[aria-label*='Close' i], div[role='dialog'] button[aria-label*='关闭' i], div[class*='drawer'] button[aria-label*='关闭' i], [class*='close' i]"
    );
    for (const btn of closeBtns) {
      if (btn.offsetParent !== null && typeof btn.click === "function") {
        btn.click();
        break;
      }
    }
  }

  // 监听来自 background 的指令
  if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === "SCROLL_DASHBOARD") {
        scrollAndTriggerLazyLoad().then(() => {
          sendResponse({ success: true });
        });
        return true;
      }

      if (request.action === "GET_DASHBOARD_INFO") {
        const data = parseDashboardData();
        sendResponse({ success: true, data });
        return true;
      }

      if (request.action === "CLICK_CARD") {
        triggerCardClick(request.title, request.index).then((res) => {
          sendResponse(res);
        });
        return true;
      }

      if (request.action === "SOLVE_PUNCH_CARD_DRAWER") {
        solvePunchCardDrawer().then((res) => {
          sendResponse({ success: true, ...res });
        });
        return true;
      }

      if (request.action === "CLOSE_PUNCH_CARD_DRAWER") {
        closePunchCardDrawer();
        sendResponse({ success: true });
        return true;
      }
    });
  }

  // 页面就绪时执行一次静默弹窗关闭检测
  dismissBingAppModal();
  setTimeout(dismissBingAppModal, 1200);
})();
