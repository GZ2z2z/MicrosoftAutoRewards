// Popup 界面交互逻辑
document.addEventListener("DOMContentLoaded", () => {
  // DOM 元素引用
  const statusPill = document.getElementById("statusPill");
  const currentPointsEl = document.getElementById("currentPoints");
  const todayPointsEl = document.getElementById("todayPoints");
  const streakDaysEl = document.getElementById("streakDays");
  const latestLogEl = document.getElementById("latestLog");

  const dailySetText = document.getElementById("dailySetText");
  const dailySetProgress = document.getElementById("dailySetProgress");
  const pcSearchText = document.getElementById("pcSearchText");
  const pcSearchProgress = document.getElementById("pcSearchProgress");

  const btnStartAll = document.getElementById("btnStartAll");
  const btnStop = document.getElementById("btnStop");
  const btnOnlyDaily = document.getElementById("btnOnlyDaily");
  const btnOnlyPc = document.getElementById("btnOnlyPc");

  // 设置表单元素
  const settingEnableAlarm = document.getElementById("settingEnableAlarm");
  const settingAlarmTime = document.getElementById("settingAlarmTime");
  const settingPcCount = document.getElementById("settingPcCount");
  const settingMinDelay = document.getElementById("settingMinDelay");
  const settingMaxDelay = document.getElementById("settingMaxDelay");
  const settingSearchLang = document.getElementById("settingSearchLang");
  const settingCooldownMode = document.getElementById("settingCooldownMode");
  const settingEnableDaily = document.getElementById("settingEnableDaily");
  const settingEnablePcSearch = document.getElementById("settingEnablePcSearch");
  const settingNotify = document.getElementById("settingNotify");
  const btnSaveSettings = document.getElementById("btnSaveSettings");

  // 日志元素
  const logsConsole = document.getElementById("logsConsole");
  const btnClearLogs = document.getElementById("btnClearLogs");

  // Tab 切换逻辑
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((b) => b.classList.remove("active"));
      tabContents.forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      const targetContent = document.getElementById(btn.dataset.tab);
      if (targetContent) targetContent.classList.add("active");
    });
  });

  // 更新界面状态
  function updateUI(state, settings) {
    if (!state) return;

    // 运行状态标识
    if (state.running) {
      statusPill.textContent = "运行中...";
      statusPill.className = "status-pill running";
      if (btnStartAll) btnStartAll.style.display = "none";
      if (btnStop) btnStop.style.display = "flex";
    } else {
      statusPill.textContent = "就绪";
      statusPill.className = "status-pill";
      if (btnStartAll) btnStartAll.style.display = "flex";
      if (btnStop) btnStop.style.display = "none";
    }

    // 积分与连胜 (严格限制在真实积分范围 1 ~ 2,000,000，防止异常大数破屏)
    if (currentPointsEl) {
      if (state.currentPoints > 0 && state.currentPoints < 2000000) {
        currentPointsEl.textContent = state.currentPoints.toLocaleString();
      } else {
        currentPointsEl.textContent = "-";
      }
    }
    if (todayPointsEl) {
      todayPointsEl.textContent = (state.todayPoints > 0 && state.todayPoints < 50000) ? `+${state.todayPoints}` : "+0";
    }
    if (streakDaysEl) {
      streakDaysEl.textContent = `${state.streakDays || 0} 天`;
    }

    // 每日任务卡片进度
    if (dailySetText && dailySetProgress) {
      const dailyTotal = typeof state.dailySetTotal === "number" ? state.dailySetTotal : 0;
      const dailyDone = typeof state.dailySetDone === "number" ? state.dailySetDone : 0;
      dailySetText.textContent = `${dailyDone} / ${dailyTotal}`;
      dailySetProgress.style.width = `${dailyTotal > 0 ? Math.min(100, Math.round((dailyDone / dailyTotal) * 100)) : 0}%`;
    }

    // PC 搜索进度
    if (pcSearchText && pcSearchProgress) {
      const pcTotal = state.pcSearchTotal || (settings ? settings.pcSearchCount : 15);
      const pcDone = state.pcSearchDone || 0;
      pcSearchText.textContent = `${pcDone} / ${pcTotal}`;
      pcSearchProgress.style.width = `${Math.min(100, Math.round((pcDone / Math.max(1, pcTotal)) * 100))}%`;
    }
  }

  // 渲染日志
  function renderLogs(logs) {
    if (!logsConsole) return;
    if (!logs || logs.length === 0) {
      logsConsole.innerHTML = '<div class="log-entry info">[系统] 暂无日志记录</div>';
      return;
    }

    logsConsole.innerHTML = logs
      .map((item) => `<div class="log-entry ${item.type}">[${item.time}] ${item.message}</div>`)
      .join("");

    if (logs.length > 0 && latestLogEl) {
      latestLogEl.textContent = `[${logs[0].time}] ${logs[0].message}`;
    }
  }

  // 填充设置表单
  function fillSettings(settings) {
    if (!settings) return;
    if (settingEnableAlarm) settingEnableAlarm.checked = !!settings.enableAlarm;
    if (settingAlarmTime) settingAlarmTime.value = settings.alarmTime || "08:30";
    if (settingPcCount) settingPcCount.value = settings.pcSearchCount || 15;
    if (settingMinDelay) settingMinDelay.value = settings.minDelay || 7;
    if (settingMaxDelay) settingMaxDelay.value = settings.maxDelay || 12;
    if (settingSearchLang) settingSearchLang.value = settings.searchLang || "mixed";
    if (settingCooldownMode) settingCooldownMode.checked = !!settings.cooldownMode;
    if (settingEnableDaily) settingEnableDaily.checked = settings.enableDailySet !== false;
    if (settingEnablePcSearch) settingEnablePcSearch.checked = settings.enablePcSearch !== false;
    if (settingNotify) settingNotify.checked = settings.notifyOnComplete !== false;
  }

  // 初始获取后台状态
  chrome.runtime.sendMessage({ action: "GET_STATE" }, (response) => {
    if (response) {
      updateUI(response.state, response.settings);
      fillSettings(response.settings);
      renderLogs(response.logs);
    }
  });

  // 监听后台的实时广播
  chrome.runtime.onMessage.addListener((request) => {
    if (request.action === "STATE_UPDATED") {
      updateUI(request.state);
      if (request.log) {
        if (latestLogEl) latestLogEl.textContent = `[${request.log.time}] ${request.log.message}`;
        if (logsConsole) {
          const newEntry = document.createElement("div");
          newEntry.className = `log-entry ${request.log.type}`;
          newEntry.textContent = `[${request.log.time}] ${request.log.message}`;
          logsConsole.insertBefore(newEntry, logsConsole.firstChild);
        }
      }
    }
  });

  function setUIRunning(label) {
    if (statusPill) {
      statusPill.textContent = "运行中: " + label;
      statusPill.className = "status-pill running";
    }
    if (btnStartAll) btnStartAll.style.display = "none";
    if (btnStop) btnStop.style.display = "flex";
    if (latestLogEl) latestLogEl.textContent = `[${new Date().toLocaleTimeString()}] 正在启动: ${label}...`;
  }

  // 按钮交互事件
  if (btnStartAll) {
    btnStartAll.addEventListener("click", () => {
      setUIRunning("全部任务");
      chrome.runtime.sendMessage({ action: "START_ALL" });
    });
  }

  if (btnStop) {
    btnStop.addEventListener("click", () => {
      chrome.runtime.sendMessage({ action: "STOP" }, () => {
        if (statusPill) {
          statusPill.textContent = "已停止";
          statusPill.className = "status-pill";
        }
        if (btnStartAll) btnStartAll.style.display = "flex";
        if (btnStop) btnStop.style.display = "none";
        if (latestLogEl) latestLogEl.textContent = `[${new Date().toLocaleTimeString()}] 任务已手动终止`;
      });
    });
  }

  if (btnOnlyDaily) {
    btnOnlyDaily.addEventListener("click", () => {
      setUIRunning("任务卡片与打卡");
      chrome.runtime.sendMessage({ action: "START_TASK", taskType: "daily_set" });
    });
  }

  if (btnOnlyPc) {
    btnOnlyPc.addEventListener("click", () => {
      setUIRunning("PC搜索");
      chrome.runtime.sendMessage({ action: "START_TASK", taskType: "pc_search" });
    });
  }

  if (btnSaveSettings) {
    btnSaveSettings.addEventListener("click", () => {
      const updatedSettings = {
        enableAlarm: settingEnableAlarm ? settingEnableAlarm.checked : true,
        alarmTime: settingAlarmTime ? settingAlarmTime.value : "08:30",
        pcSearchCount: settingPcCount ? parseInt(settingPcCount.value, 10) || 15 : 15,
        minDelay: settingMinDelay ? Math.max(3, parseInt(settingMinDelay.value, 10) || 7) : 7,
        maxDelay: settingMaxDelay ? Math.max(5, parseInt(settingMaxDelay.value, 10) || 12) : 12,
        searchLang: settingSearchLang ? settingSearchLang.value : "mixed",
        cooldownMode: settingCooldownMode ? settingCooldownMode.checked : false,
        enableDailySet: settingEnableDaily ? settingEnableDaily.checked : true,
        enablePcSearch: settingEnablePcSearch ? settingEnablePcSearch.checked : true,
        notifyOnComplete: settingNotify ? settingNotify.checked : true
      };

      chrome.runtime.sendMessage({ action: "SAVE_SETTINGS", settings: updatedSettings }, (res) => {
        if (res && res.success) {
          btnSaveSettings.textContent = "✓ 保存成功！";
          setTimeout(() => {
            btnSaveSettings.textContent = "保存设置";
          }, 1500);
        }
      });
    });
  }

  if (btnClearLogs) {
    btnClearLogs.addEventListener("click", () => {
      chrome.runtime.sendMessage({ action: "CLEAR_LOGS" }, () => {
        if (logsConsole) logsConsole.innerHTML = '<div class="log-entry info">[系统] 日志已清空</div>';
        if (latestLogEl) latestLogEl.textContent = "日志已清空";
      });
    });
  }
});
