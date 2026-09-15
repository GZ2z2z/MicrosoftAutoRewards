# -*- coding: utf-8 -*-
"""
Microsoft Rewards 自动化打卡助手 (主运行入口)
支持每日活动打卡、15次桌面搜索、测验/投票/拼图求解、定时任务管理与缓存清理
"""

import sys
import os
import argparse
import time
from pathlib import Path

# 强制 Windows 控制台以 UTF-8 输出，防止 Emoji 和中文字符引发 UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from core.browser import get_edge_driver, get_browser_driver, detect_available_browser
from core.dashboard import RewardsDashboard
from core.searcher import BingSearcher
from core.edge_browse import run_edge_30min_browsing, get_edge_browsing_progress
from core.task_manager import clean_edge_cache, install_task, uninstall_task, view_logs, setup_wizard, create_portable_package

class AutoLogger:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        filepath.parent.mkdir(parents=True, exist_ok=True)
        self.log = open(filepath, "a", encoding="utf-8", errors="replace")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

def main():
    parser = argparse.ArgumentParser(description="Microsoft Rewards 自动化脚本")
    parser.add_argument("--headless", action="store_true", help="启用无头静默模式 (后台静默执行)")
    parser.add_argument("--daily", action="store_true", help="仅执行每日活动 (Daily Set 卡片与打卡)")
    parser.add_argument("--search", action="store_true", help="仅执行 PC 桌面端必应搜索")
    parser.add_argument("--browse30", action="store_true", help="后台静默执行 Edge 30 分钟浏览打卡")
    parser.add_argument("--no-browse30", action="store_true", help="跳过 Edge 30 分钟浏览打卡")
    parser.add_argument("--count", type=int, default=22, help="PC 桌面端搜索次数 (默认为 22 次，自动核验补足至 60/60 满分)")
    parser.add_argument("--browser", choices=["auto", "chrome", "edge"], default="auto", help="选择浏览器引擎 (auto/chrome/edge，默认为 auto)")
    parser.add_argument("--visual", action="store_true", help="仅执行必应视觉搜索连续打卡")
    parser.add_argument("--claim", action="store_true", help="仅检查并领取待入账积分")
    parser.add_argument("--login", action="store_true", help="仅打开浏览器供首次登录微软账号并保存会话")
    parser.add_argument("--clean", action="store_true", help="清理临时缓存垃圾")
    parser.add_argument("--install-task", action="store_true", help="安装 Windows 每日自动静默打卡任务")
    parser.add_argument("--uninstall-task", action="store_true", help="卸载 Windows 每日定时打卡任务")
    parser.add_argument("--view-log", action="store_true", help="查看运行日志")
    parser.add_argument("--setup", action="store_true", help="新电脑一键配置向导")
    parser.add_argument("--pack", action="store_true", help="生成纯净移植压缩包 (排除缓存冲突文件)")
    args = parser.parse_args()

    # 处理独立管理指令
    if args.clean:
        clean_edge_cache()
        return
    if args.install_task:
        install_task()
        return
    if args.uninstall_task:
        uninstall_task()
        return
    if args.view_log:
        view_logs()
        return
    if args.setup:
        setup_wizard()
        return
    if args.pack:
        create_portable_package()
        return

    print("=" * 60)
    print("🚀 Microsoft Rewards 自动化打卡助手 (Edge / Chrome 双引擎自适应)")
    print("   特性: 真实前台视口、原生发分信标、无死角核验、防风控人机拟真")
    print("=" * 60)

    # 如果没有命令行参数，展示清晰的交互选择菜单
    if len(sys.argv) == 1:
        print("\n请选择要执行的操作:")
        print("  [1] 一键完成全套任务 (每日活动 + 视觉搜索 + 60分必应搜索 + 自动领奖) [快速推荐]")
        print("  [2] 仅执行每日活动卡片 (Daily Set 3项 + 更多活动)")
        print("  [3] 仅执行 PC 桌面端必应搜索 (确保达到 60/60 满额积分)")
        print("  [4] 后台静默执行 Edge 30分钟浏览打卡 (赚取打卡积分与印章)")
        print("  [5] 后台静默全自动托管打卡 (全套任务 + 视觉搜索 + 60分搜索 + Edge 30分钟浏览 + 领奖) [全托管推荐]")
        print("  [6] 仅执行必应视觉搜索连续打卡")
        print("  [7] 首次登录微软账号 (打开浏览器窗口供登录并永久保存状态)")
        print("  " + "-" * 56)
        print("  [8] 安装/配置 Windows 每日定时打卡任务 (静默自动运行)")
        print("  [9] 卸载 Windows 每日定时打卡任务")
        print("  [C] 清理临时缓存垃圾 (深度瘦身，保留登录凭据)")
        print("  [L] 查看运行日志 (积分结算记录)")
        print("  [0] 新电脑一键配置向导 (检测依赖 + 登录 + 自动定时)")
        print("  [P] 生成新电脑纯净移植压缩包 (一键打包，排除冲突缓存)")
        print("-" * 60)
        try:
            choice = input("请输入选项编号 (直接回车默认运行 [1]): ").strip()
        except Exception:
            choice = "1"
        if not choice:
            choice = "1"

        if choice == "2":
            args.daily = True
        elif choice == "3":
            args.search = True
        elif choice == "4":
            args.browse30 = True
            args.headless = True
        elif choice == "5":
            args.headless = True
        elif choice == "6":
            args.visual = True
        elif choice == "7":
            args.login = True
        elif choice == "8":
            install_task()
            return
        elif choice == "9":
            uninstall_task()
            return
        elif choice.upper() == "C":
            clean_edge_cache()
            return
        elif choice.upper() == "L":
            view_logs()
            return
        elif choice == "0":
            setup_wizard()
            return
        elif choice.upper() == "P":
            create_portable_package()
            return

    if args.browse30:
        args.headless = True

    # 无头模式自动记录日志
    if args.headless:
        log_file = Path(__file__).resolve().parent / "logs" / "rewards.log"
        logger = AutoLogger(log_file)
        sys.stdout = logger
        sys.stderr = logger
        print("\n" + "=" * 60)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始执行 Microsoft Rewards 后台静默任务")
        print("=" * 60)

    # 首次引导登录模式强制禁用无头
    is_headless = args.headless and not args.login

    driver = None
    try:
        driver = get_browser_driver(headless=is_headless, browser=args.browser)
        dashboard = RewardsDashboard(driver)

        # 确保已登录微软账户
        if not dashboard.ensure_logged_in(is_headless=is_headless):
            return

        if args.login:
            print("\n✓ 账号状态已确认并已保存至本地 Profile 目录！您可以随时运行完整打卡。")
            return

        # 获取初始积分与连胜
        start_status = dashboard.get_user_status()
        print(f"💰 任务开始前可用总积分: {start_status['points']} | 连胜: {start_status['streak']} 天\n")

        if args.claim:
            # 仅独立领取待入账积分
            dashboard.claim_pending_rewards()
        elif args.visual:
            # 仅执行视觉搜索打卡
            dashboard.run_visual_search()
        elif args.browse30:
            # 仅独立执行 Edge 30 分钟后台静默浏览打卡
            run_edge_30min_browsing(driver)
        else:
            do_all = not args.daily and not args.search
            do_daily = args.daily or do_all
            do_search = args.search or do_all

            # 阶段 1：每日活动与日常任务卡片 (Daily Set + Earn)
            if do_daily:
                dashboard.run_daily_set()
                dashboard.run_earn_tasks()
                dashboard.run_visual_search()

            # 阶段 2：PC 桌面端必应搜索 (确保达成 60/60 满额积分)
            if do_search:
                searcher = BingSearcher(driver)
                searcher.perform_searches(count=args.count, min_delay=7.0, max_delay=11.0, ensure_max=True)

            # 阶段 3：后台静默全自动模式或指定模式下，执行 Edge 30 分钟静默浏览打卡
            is_chrome_driver = hasattr(driver, "capabilities") and driver.capabilities.get("browserName") == "chrome"
            should_browse30 = (is_headless or args.browse30) and not args.no_browse30 and do_all
            if should_browse30:
                if is_chrome_driver:
                    print("\nℹ️ 当前运行引擎为 Chrome（系统未安装 Edge 原生客户端），Edge 30 分钟打卡依赖原生 Edge 系统遥测服务，已自动安全跳过，避免无效挂机。")
                else:
                    run_edge_30min_browsing(driver)

            # 阶段 4：【最终核心收尾】在所有其他任务全部完成后，最后统一检查并一键领取所有待入账奖励积分
            dashboard.claim_available_points()

        # 3. 最终积分结算与成果汇报
        driver.get("https://rewards.bing.com/")
        time.sleep(3.5)
        end_status = dashboard.get_user_status()
        gained = max(0, end_status['points'] - start_status['points'])

        print("\n" + "★" * 60)
        print("🎉 今日 Microsoft Rewards 任务全部圆满完成！")
        print(f"   起始可用积分: {start_status['points']}")
        print(f"   最终可用积分: {end_status['points']} (本次新增: +{gained} 积分)")
        print(f"   当前连胜天数: {end_status['streak']} 天")
        print("★" * 60 + "\n")

    except KeyboardInterrupt:
        print("\n🛑 收到用户中断指令，正在安全退出...")
    except Exception as e:
        print(f"\n❌ 执行过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
            print("🔒 浏览器会话已安全释放。")

if __name__ == "__main__":
    main()
