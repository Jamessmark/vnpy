"""
全交易所决策系统主运行脚本

流程：Alpha158 因子计算 → 新闻获取 → LLM 决策报告生成

支持交易所：CFFEX / CZCE / DCE / GFEX / INE / SHFE

用法：
    # 运行所有交易所全部品种
    uv run python ai/agent/common/run.py

    # 指定交易所
    uv run python ai/agent/common/run.py --exchanges DCE CZCE

    # 指定品种（需同时指定交易所）
    uv run python ai/agent/common/run.py --exchanges DCE --varieties p m y

    # 指定目标日期
    uv run python ai/agent/common/run.py --date 2026-05-24

    # 指定输出文件名
    uv run python ai/agent/common/run.py --output my_report.md
"""
import sys
import argparse
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ai.agent.common.factor_analysis import Alpha158Calculator
from ai.agent.common.news_sentiment import NewsSentimentAnalyzer
from ai.agent.common.llm_advisor import LLMAdvisor
from ai.agent.common.all_constants import EXCHANGE_VARIETIES, EXCHANGE_CN_NAMES, VARIETY_NAMES

_REPORT_DIR = Path(__file__).parent.parent / "reports"


def main(
    exchanges: list = None,
    varieties: list = None,
    target_date: date = None,
    output_file: str = None,
) -> None:
    print("\n" + "=" * 60)
    print("🚀 全交易所决策系统")
    print("=" * 60)

    if target_date is None:
        target_date = date.today()

    # 构建 (exchange, variety) 任务列表
    tasks = []
    if exchanges is None:
        exchanges = list(EXCHANGE_VARIETIES.keys())
    for exchange in exchanges:
        if exchange not in EXCHANGE_VARIETIES:
            print(f"  ⚠️ 未知交易所: {exchange}，跳过")
            continue
        ex_varieties, _ = EXCHANGE_VARIETIES[exchange]
        if varieties:
            ex_varieties = [v for v in varieties if v in ex_varieties]
        tasks.extend((exchange, v) for v in ex_varieties)

    print(f"📊 处理品种: {len(tasks)} 个  目标日期: {target_date}")

    # ── Step 1: Alpha158 因子计算 ─────────────────────────────────────────────
    print("\n[步骤 1/3] Alpha158 因子计算...")
    calculator    = Alpha158Calculator()
    alpha_results = {}  # (exchange, variety) → features

    for exchange, variety in tasks:
        name = VARIETY_NAMES.get(variety, variety)
        try:
            features = calculator.calculate_for_variety(
                variety, exchange=exchange, target_date=target_date
            )
            if features:
                alpha_results[(exchange, variety)] = features
                close = features.get("_close", 0)
                print(f"  ✅ [{exchange}] {name}({variety}) 收盘={close:.2f}")
        except Exception as e:
            print(f"  ❌ [{exchange}] {name}({variety}) 因子计算失败: {e}")

    print(f"\n✅ 完成 {len(alpha_results)}/{len(tasks)} 个品种因子计算")
    if not alpha_results:
        print("❌ 所有品种因子计算均失败，退出")
        return

    # ── Step 2: 新闻获取 ──────────────────────────────────────────────────────
    print("\n[步骤 2/3] 新闻获取...")
    analyzer          = NewsSentimentAnalyzer()
    sentiment_results = {}

    for (exchange, variety), _ in alpha_results.items():
        name = VARIETY_NAMES.get(variety, variety)
        try:
            result = analyzer.analyze_variety(variety, name, days=30)
            sentiment_results[(exchange, variety)] = result
            print(f"  ✅ [{exchange}] {name} 新闻={result.get('news_count', 0)} 条")
        except Exception as e:
            print(f"  ❌ [{exchange}] {name} 新闻获取失败: {e}")

    print(f"\n✅ 完成 {len(sentiment_results)}/{len(alpha_results)} 个品种新闻获取")

    # ── Step 3: LLM 决策报告 ──────────────────────────────────────────────────
    print("\n[步骤 3/3] 决策报告生成...")

    # 按交易所分组，每个交易所共用一个 LLMAdvisor Session
    reports_by_exchange: dict = {}
    advisors: dict = {}

    for (exchange, variety) in alpha_results:
        if (exchange, variety) not in sentiment_results:
            continue

        if exchange not in advisors:
            cn_name = EXCHANGE_CN_NAMES.get(exchange, exchange)
            advisors[exchange] = LLMAdvisor(
                exchange_name = cn_name,
                session_name  = f"{exchange}决策Agent",
                report_dir    = _REPORT_DIR / exchange,
            )
            reports_by_exchange[exchange] = []

        name    = VARIETY_NAMES.get(variety, variety)
        advisor = advisors[exchange]
        try:
            report = advisor.generate_decision_report(
                variety,
                name,
                alpha_results[(exchange, variety)],
                sentiment_results[(exchange, variety)],
            )
            reports_by_exchange[exchange].append(report)
            close    = report.get("close_price", 0)
            has_resp = bool(report.get("llm_response"))
            print(f"  ✅ [{exchange}] {name} 收盘={close:.2f}  LLM={'✓' if has_resp else '✗'}")
        except Exception as e:
            print(f"  ❌ [{exchange}] {name} 决策失败: {e}")

    # 生成报告（每个交易所独立文件）
    total = 0
    _fname = output_file or f"decision_report_{target_date.isoformat()}.md"
    for exchange, rpts in reports_by_exchange.items():
        if rpts:
            advisors[exchange].generate_batch_report(rpts, _fname)
            total += len(rpts)

    print(f"\n✅ 共生成 {total} 个品种的决策报告")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="全交易所决策系统")
    parser.add_argument(
        "--exchanges", nargs="+",
        help="指定交易所（如: DCE CZCE SHFE），默认全部",
        default=None,
    )
    parser.add_argument(
        "--varieties", nargs="+",
        help="指定品种代码（如: p m y），需配合 --exchanges 使用",
        default=None,
    )
    parser.add_argument(
        "--date", type=date.fromisoformat,
        help="目标日期（如: 2026-05-24），默认今天",
        default=None,
    )
    parser.add_argument(
        "--output",
        help="输出报告文件名（如: report.md）",
        default=None,
    )
    args = parser.parse_args()
    main(
        exchanges   = args.exchanges,
        varieties   = args.varieties,
        target_date = args.date,
        output_file = args.output,
    )
