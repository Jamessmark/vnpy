"""
主入口
支持：单次立即运行 / 定时调度（每天 17:00）/ 指定日期调试

完整流程：
  Step 0a  分钟K → 日K      (minute_to_daily.py)
  Step 0b  日K  → 主连      (build_main_contract.py --no-minute)
  Step 1   加载全品种 K 线数据
  Step 2a  复盘昨日报告 → 保存 memory/
  Step 2b  发送给 CodeFlicker Agent 生成执行计划（含复盘背景）
  Step 3   保存报告

用法：
    uv run python ai/agent/futures_daily_analyst/run.py
    uv run python ai/agent/futures_daily_analyst/run.py --schedule
    uv run python ai/agent/futures_daily_analyst/run.py --date 2026-04-07
    uv run python ai/agent/futures_daily_analyst/run.py --skip-build    # 跳过K线构建
    uv run python ai/agent/futures_daily_analyst/run.py --skip-review   # 跳过复盘
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from config import (
    WATCH_SYMBOLS,
    BAR_LOOKBACK_DAYS,
    REPORTS_DIR,
    SCHEDULE_TIME,
)
from data_loader import load_all_symbols
from report_generator import generate_report, save_report
from review import run_review, load_latest_memory

# 子脚本绝对路径
_MINUTE_TO_DAILY = ROOT / "examples" / "data_recorder" / "minute_to_daily.py"
_BUILD_MAIN      = ROOT / "ai" / "data_process" / "build_main_contract.py"


def _run_script(label: str, script: Path, extra_args: list[str] | None = None) -> bool:
    """用当前 Python 解释器运行子脚本，实时打印输出，返回是否成功"""
    cmd = [sys.executable, str(script)] + (extra_args or [])
    print(f"  » python {script.name} {' '.join(extra_args or [])}", flush=True)
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"  ⚠️  {label} 返回错误码 {result.returncode}，继续后续步骤", flush=True)
        return False
    return True


def build_daily_bars() -> None:
    """
    Step 0a  分钟K → 日K（全合约）
    Step 0b  日K  → 主连日K（--no-minute 跳过分钟主连，速度快）
    """
    print("► Step 0  构建日K线数据")
    print("  [0a] 分钟K → 日K（minute_to_daily）", flush=True)
    _run_script("minute_to_daily", _MINUTE_TO_DAILY)

    print("  [0b] 日K → 主连（build_main_contract --no-minute）", flush=True)
    _run_script("build_main_contract", _BUILD_MAIN, ["--no-minute"])
    print()


def run_agent(
    report_date: datetime | None = None,
    skip_build: bool = False,
    skip_review: bool = False,
) -> None:
    if report_date is None:
        report_date = datetime.now()

    date_str = report_date.strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*60}")
    print(f"  期货每日执行计划 Agent 启动")
    print(f"  运行时间：{date_str}")
    print(f"{'='*60}\n")

    # ── Step 0：构建日K线 ──────────────────────────────────────────
    if not skip_build:
        build_daily_bars()
    else:
        print("► Step 0  跳过K线构建（--skip-build）\n")

    # ── Step 1：加载 K 线数据 ──────────────────────────────────────
    print("► Step 1  加载 K 线行情数据")
    market_data = load_all_symbols(
        watch_symbols=WATCH_SYMBOLS,
        days=BAR_LOOKBACK_DAYS,
        end_date=report_date,
    )
    loaded = sum(1 for d in market_data if d["bars"])
    print(f"  ✓ 成功加载 {loaded}/{len(WATCH_SYMBOLS)} 个品种\n")

    # ── Step 2a：复盘昨日报告 ──────────────────────────────────────
    review_memory = ""
    if not skip_review:
        print("► Step 2a 复盘昨日报告")
        try:
            review_memory = run_review(market_data=market_data, report_date=report_date)
        except Exception as e:
            print(f"  ⚠️  复盘出错（不影响今日报告）：{e}", flush=True)
        if not review_memory:
            review_memory = load_latest_memory(report_date)
            if review_memory:
                print(f"  [复盘] 加载历史复盘记忆作为背景参考", flush=True)
        print()
    else:
        print("► Step 2a 跳过复盘（--skip-review）\n")
        review_memory = load_latest_memory(report_date)

    # ── Step 2b：生成今日报告 ─────────────────────────────────────
    print("► Step 2b 发送给 CodeFlicker Agent 生成执行计划")
    report = generate_report(
        market_data=market_data,
        report_date=report_date,
        review_memory=review_memory,
    )

    # ── Step 3：保存报告 ───────────────────────────────────────────
    output_path = save_report(report, REPORTS_DIR, report_date)
    print(f"  ✓ 报告已保存：{output_path}\n")

    print("=" * 60)
    print(report)
    print("=" * 60)
    print(f"\n✅ 完成！报告路径：{output_path}")


def run_scheduled() -> None:
    try:
        import schedule
        import time
    except ImportError:
        print("❌ 缺少 schedule 包：uv add schedule")
        sys.exit(1)

    print(f"⏰ 定时模式，每天 {SCHEDULE_TIME} 自动运行，按 Ctrl+C 退出\n")
    schedule.every().day.at(SCHEDULE_TIME).do(run_agent)
    while True:
        schedule.run_pending()
        time.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="期货每日执行计划 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  uv run python ai/agent/futures_daily_analyst/run.py                   # 完整流程
  uv run python ai/agent/futures_daily_analyst/run.py --skip-build      # 跳过K线构建
  uv run python ai/agent/futures_daily_analyst/run.py --skip-review     # 跳过昨日复盘
  uv run python ai/agent/futures_daily_analyst/run.py --date 2026-04-07 # 指定日期
  uv run python ai/agent/futures_daily_analyst/run.py --schedule        # 每天定时运行
        """,
    )
    parser.add_argument("--schedule", "-s", action="store_true",
                        help=f"定时模式：每天 {SCHEDULE_TIME} 运行")
    parser.add_argument("--date", "-d", type=str, default=None,
                        help="指定日期 YYYY-MM-DD（调试用）")
    parser.add_argument("--skip-build", action="store_true",
                        help="跳过 minute_to_daily + build_main_contract 步骤")
    parser.add_argument("--skip-review", action="store_true",
                        help="跳过昨日报告复盘步骤")
    args = parser.parse_args()

    if args.schedule:
        run_scheduled()
    else:
        report_date = None
        if args.date:
            try:
                report_date = datetime.strptime(args.date, "%Y-%m-%d").replace(hour=23, minute=10)
            except ValueError:
                print(f"❌ 日期格式错误：{args.date}")
                sys.exit(1)
        run_agent(report_date, skip_build=args.skip_build, skip_review=args.skip_review)


if __name__ == "__main__":
    main()
