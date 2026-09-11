// Bing 搜索页防风控拟人化操作脚本
(() => {
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  // 模拟真实用户浏览与滚动
  async function simulateHumanInteraction() {
    // 稍微等待页面首屏渲染
    await delay(1200 + Math.random() * 800);

    // 平滑向下滚动一段距离
    const scrollDistance = 300 + Math.floor(Math.random() * 450);
    window.scrollBy({
      top: scrollDistance,
      behavior: "smooth"
    });

    await delay(1500 + Math.random() * 1000);

    // 随机上下微调
    if (Math.random() > 0.5) {
      window.scrollBy({
        top: -150 + Math.floor(Math.random() * 50),
        behavior: "smooth"
      });
    }

    // 检查右上角积分角标（如果存在）
    const pointsBadge = document.querySelector("#id_rc, #b_id_rc, .id_rc");
    let currentPoints = null;
    if (pointsBadge) {
      const text = pointsBadge.innerText || pointsBadge.textContent || "";
      const num = parseInt(text.replace(/[^0-9]/g, ""), 10);
      if (!isNaN(num)) currentPoints = num;
    }

    // 向后台通知页面已交互完成
    chrome.runtime.sendMessage({
      action: "SEARCH_INTERACTION_DONE",
      points: currentPoints
    });
  }

  // 监听来自 background 的交互触发指令
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "SIMULATE_SCROLL") {
      simulateHumanInteraction().then(() => {
        sendResponse({ success: true });
      });
      return true;
    }
  });

  // 如果是在搜索结果页面，自动执行一次轻量滚动
  if (window.location.pathname.startsWith("/search")) {
    simulateHumanInteraction().catch((e) => console.log("[MS Search Sim]", e));
  }
})();
