// Bing / MSN / Microsoft 搜索与任务页面中的 Rewards 测验、拼图与投票智能解决器
(() => {
  // 严禁在 Rewards 仪表盘页面运行解题器，避免误触仪表盘自身的任务卡片！
  const curHost = window.location.hostname || "";
  const curPath = window.location.pathname || "";
  if (curHost.includes("rewards.bing.com") || curPath.startsWith("/rewards") || curPath.includes("/earn")) {
    return;
  }

  // 延迟辅助函数
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const randomDelay = (min, max) => delay(Math.floor(Math.random() * (max - min + 1) + min));

  // 智能真实点击模拟（兼容 Pointer/Mouse/Click 多层事件派发）
  function smartClick(el) {
    if (!el) return;
    try {
      const opts = { bubbles: true, cancelable: true, view: window };
      el.dispatchEvent(new PointerEvent("pointerdown", opts));
      el.dispatchEvent(new MouseEvent("mousedown", opts));
      el.dispatchEvent(new PointerEvent("pointerup", opts));
      el.dispatchEvent(new MouseEvent("mouseup", opts));
      el.dispatchEvent(new MouseEvent("click", opts));
      if (typeof el.click === "function") {
        el.click();
      }
    } catch (e) {
      if (typeof el.click === "function") el.click();
    }
  }

  // 1. 处理拼图任务 (Sliding Puzzle) —— 自动点击右上角【跳过拼图 ->】
  async function solvePuzzle() {
    // 检查并点击可能存在的 "Click to begin" 遮罩
    const beginBtn = Array.from(document.querySelectorAll("button, [role='button'], div, span, p, a")).find((el) => {
      if (el.children.length > 2) return false;
      const t = (el.innerText || "").trim();
      return /click to begin|开始|点击开始/i.test(t) && (el.offsetParent !== null || el.getBoundingClientRect().width > 0);
    });
    if (beginBtn) {
      console.log("[MS Rewards Solver] 🧩 检测到拼图开始引导，触发点击:", beginBtn);
      smartClick(beginBtn);
      await delay(600);
    }

    const findSkipBtn = () => {
      // 1. 精确属性选择器
      const direct = document.querySelector(
        "#skipPuzzle, .skip-puzzle, [id*='skipPuzzle' i], [class*='skipPuzzle' i], [aria-label*='跳过拼图' i], [aria-label*='Skip puzzle' i], [title*='跳过拼图' i], [title*='Skip puzzle' i], a[href*='skip' i]"
      );
      if (direct && (direct.offsetParent !== null || direct.getBoundingClientRect().width > 0)) return direct;

      // 2. 文本匹配：查找包含“跳过拼图”或“Skip puzzle”或“跳过”的叶子/近叶子元素
      const all = Array.from(
        document.querySelectorAll("a, button, [role='button'], div, span, p")
      );
      for (const el of all) {
        if (el.children.length > 2) continue;
        const txt = (el.innerText || el.textContent || "").trim();
        if (/跳过拼图|Skip\s*puzzle/i.test(txt) || /^(?:跳过拼图|跳过|Skip\s*puzzle|Skip)\s*[→\->>]*$/i.test(txt)) {
          const btn = el.closest("a, button, [role='button']") || el;
          if (btn.offsetParent !== null || btn.getBoundingClientRect().width > 0) {
            return btn;
          }
        }
      }
      return null;
    };

    let skipBtn = findSkipBtn();
    // 拼图页面如刚打开，等待元素渲染 (最多轮询6秒)
    if (!skipBtn) {
      for (let i = 0; i < 12; i++) {
        await delay(500);
        skipBtn = findSkipBtn();
        if (skipBtn) break;
      }
    }

    if (skipBtn) {
      console.log("[MS Rewards Solver] 🧩 成功定位拼图【跳过拼图】按钮，准备执行点击:", skipBtn);
      await randomDelay(800, 1500);

      smartClick(skipBtn);
      console.log("[MS Rewards Solver] 🧩 【跳过拼图】按钮已触发点击！");

      // 检查并自动点击可能存在的二次确认弹窗（如“确定”、“确认”、“跳过”）
      await delay(1200);
      const confirmBtns = Array.from(
        document.querySelectorAll("button, [role='button'], a, input[type='button']")
      ).filter((b) => {
        const t = (b.innerText || b.value || "").trim();
        return /^(?:确定|确认|跳过|Yes|OK|Confirm)$/i.test(t) && b.offsetParent !== null;
      });
      if (confirmBtns.length > 0) {
        smartClick(confirmBtns[0]);
      }

      await randomDelay(2000, 3000);
      return true;
    }

    return false;
  }

  // 2. 处理每日投票 (Poll)
  async function solvePoll() {
    const pollOptions = document.querySelectorAll(
      "div[id^='btoption'], #btoption0, #btoption1, .btOptionCard, .bt_Option"
    );

    if (pollOptions && pollOptions.length > 0) {
      console.log("[MS Rewards] 检测到每日投票，准备答题...");
      await randomDelay(1200, 2000);
      const choice = pollOptions[Math.floor(Math.random() * Math.min(2, pollOptions.length))];
      if (choice) {
        choice.click();
        console.log("[MS Rewards] 投票已点击完成");
        await randomDelay(2000, 3000);
        return true;
      }
    }
    return false;
  }

  // 3. 处理常规问答/闪电测验/超级测验 (Quiz / Trivia)
  async function solveQuiz() {
    // 检查是否有“开始答题”或“Start playing”按钮
    const startBtn = document.querySelector(
      "#rqStartQuiz, input[id*='StartQuiz' i], input[value*='quiz' i], input[value*='Start' i], input[value*='开始' i], button[id*='StartQuiz' i]"
    );
    // 预检是否有题目选项
    const initialOptions = Array.from(
      document.querySelectorAll(
        "input[name='rqAnswerOption'], .rqOption:not(.wrongOption):not(.rqDisabled), .rq_button, .btOptionCard, [data-option]"
      )
    ).filter((el) => el.offsetParent !== null);

    if (!startBtn && initialOptions.length === 0) {
      return false;
    }

    if (startBtn && startBtn.offsetParent !== null) {
      console.log("[MS Rewards] 检测到问答开始按钮，点击开始...");
      startBtn.click();
      await randomDelay(1500, 2500);
    }

    // 检查是否有题目和选项
    let attempts = 0;
    const maxAttempts = 15;
    let didAnswer = false;

    while (attempts < maxAttempts) {
      attempts++;

      // 获取当前题目的未点击或可选答案
      const options = Array.from(
        document.querySelectorAll(
          "input[name='rqAnswerOption'], .rqOption:not(.wrongOption):not(.rqDisabled), .rq_button, .btOptionCard, [data-option]"
        )
      ).filter((el) => el.offsetParent !== null);

      if (options.length === 0) {
        // 尝试查找“下一题”按钮
        const nextBtn = document.querySelector(
          "#rqAnswerOptionNext, input[value*='Next' i], input[value*='下一题' i]"
        );
        if (nextBtn && nextBtn.offsetParent !== null) {
          console.log("[MS Rewards] 点击下一题按钮...");
          nextBtn.click();
          await randomDelay(1500, 2500);
          continue;
        }

        // 检查问答是否已结束
        const completedIndicator = document.querySelector(
          ".rqHeader, #rqHeader, .c-heading, .b_focusTextExtra, #quizCompleteContainer"
        );
        if (completedIndicator && /完成|恭喜|congratulations|you earned/i.test(completedIndicator.innerText)) {
          console.log("[MS Rewards] 测验已全部完成！");
          return true;
        }
        break;
      }

      const optionToClick = options[Math.floor(Math.random() * options.length)];
      console.log("[MS Rewards] 正在尝试选择答案...");
      optionToClick.click();
      didAnswer = true;
      await randomDelay(1200, 2200);
      await delay(1000);
    }

    return didAnswer;
  }

  // 4. 处理“二选一”问答 (This or That)
  async function solveThisOrThat() {
    const cards = document.querySelectorAll(
      ".btOptionCard, div[id^='btoption'], div[data-serpquery]"
    );
    if (cards && cards.length >= 2) {
      console.log("[MS Rewards] 检测到二选一活动...");
      await randomDelay(1500, 2500);
      const choice = cards[Math.floor(Math.random() * 2)];
      if (choice) {
        choice.click();
        await randomDelay(2000, 3000);
        return true;
      }
    }
    return false;
  }

  // 综合执行
  async function autoSolvePage() {
    await delay(1200);

    // 1. 优先尝试解决拼图任务 (跳过拼图)
    const puzzleDone = await solvePuzzle();
    if (puzzleDone) {
      chrome.runtime.sendMessage({ action: "TASK_SOLVED", type: "puzzle" }).catch(() => {});
      return true;
    }

    // 2. 尝试每日投票 (Poll)
    const pollDone = await solvePoll();
    if (pollDone) {
      chrome.runtime.sendMessage({ action: "TASK_SOLVED", type: "poll" }).catch(() => {});
      return true;
    }

    // 3. 尝试常规测验 (Quiz)
    const quizDone = await solveQuiz();
    if (quizDone) {
      chrome.runtime.sendMessage({ action: "TASK_SOLVED", type: "quiz" }).catch(() => {});
      return true;
    }

    // 4. 尝试二选一 (This or That)
    const thisOrThatDone = await solveThisOrThat();
    if (thisOrThatDone) {
      chrome.runtime.sendMessage({ action: "TASK_SOLVED", type: "thisOrThat" }).catch(() => {});
      return true;
    }

    return false;
  }

  // 监听来自 background 的主动解题指令
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "SOLVE_PAGE" || request.action === "SOLVE_PUZZLE") {
      autoSolvePage().then((result) => sendResponse({ success: true, result }));
      return true;
    }
  });

  // 在符合条件的页面加载完成后自动执行一次
  const host = window.location.hostname || "";
  if (host.includes("bing.com") || host.includes("msn.com") || host.includes("microsoft.com")) {
    autoSolvePage().catch((err) => console.log("[MS Rewards Solver]", err));
  }
})();
