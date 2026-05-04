"""
DCE 决策系统主运行脚本

数据完全来自数据库（无需从 API 下载），流程：
    Alpha158 因子计算 → 新闻情绪分析 → LLM 决策报告生成

DCE 大商所主要品种：豆一、豆二、玉米、玉米淀粉、豆粕、豆油、棕榈油、鸡蛋、
                塑料、PVC、聚丙烯、焦炭、焦煤、铁矿石、乙二醇、苯乙烯、液化石油气

前置条件：
    1. 历史原始 K 线已通过 import_dce.py 导入数据库
    2. 888 主连数据已通过 main_contract_builder 生成

用法：
    # 运行全部核心品种
    uv run python ai/agent/DCE/run.py

    # 指定品种
    uv run python ai/agent/DCE/run.py --varieties a m y

    # 棕榈油
    uv run python ai/agent/DCE/run.py --varieties p

    # 指定目标日期（计算哪天因子，默认最新）
    uv run python ai/agent/DCE/run.py --date 2026-04-25

    # 指定输出文件名
    uv run python ai/agent/DCE/run.py --output my_report.md
"""
import sys
from pathlib import Path
from datetime import date, datetime
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ── 通用层 ──────────────────────────────────────────────────────────────────
from ai.agent.common.factor_analysis import Alpha158Calculator
from ai.agent.common.news_sentiment import NewsSentimentAnalyzer
from ai.agent.common.llm_advisor import LLMAdvisor

# ── DCE 专有 ────────────────────────────────────────────────────────────────
from ai.agent.DCE.dce_constants import CORE_VARIETIES, VARIETY_NAMES

# 报告目录
_REPORT_DIR = Path(__file__).parent / "reports"


def main(
    varieties: list = None,
    target_date: date = None,
    output_file: str = None,
) -> None:
    """
    主运行流程：Alpha158 因子计算 → 新闻情绪分析 → LLM 决策报告。

    Args:
        varieties:    品种列表；None 则使用 CORE_VARIETIES 全部品种
        target_date:  目标日期；None 则使用数据库最新有数据的日期
        output_file:  汇总报告文件名（不含目录）
    """
    print("\n" + "=" * 60)
    print("🚀 DCE 决策系统 - 主流程")
    print("=" * 60)

    if varieties is None:
        varieties = CORE_VARIETIES

    if target_date is None:
        target_date = date.today()

    print(f"📊 处理品种: {len(varieties)} 个")
    print(f"   {', '.join(varieties)}")
    print(f"📅 目标日期: {target_date}")

    # ── Step 1: Alpha158 因子计算（直接从数据库读取 888 数据）───────────
    print("\n[步骤 1/3] Alpha158 因子计算...")
    calculator    = Alpha158Calculator()
    alpha_results = {}

    for variety in varieties:
        try:
            features = calculator.calculate_for_variety(
                variety, target_date=target_date
            )
            if features:
                alpha_results[variety] = features
                name = VARIETY_NAMES.get(variety, variety)
                close = features.get("_close", 0)
                print(f"  ✅ {name}({variety}) 收盘={close:.2f}")
        except Exception as e:
            name = VARIETY_NAMES.get(variety, variety)
            print(f"  ❌ {name}({variety}) 因子计算失败: {e}")

    ok_count = len(alpha_results)
    print(f"\n✅ 完成 {ok_count}/{len(varieties)} 个品种的因子计算")

    if not alpha_results:
        print("❌ 所有品种因子计算均失败，退出")
        return

    # ── Step 2: 新闻情绪分析 ──────────────────────────────────────────────
    print("\n[步骤 2/3] 新闻情绪分析...")
    analyzer          = NewsSentimentAnalyzer()
    sentiment_results = {}

    for variety in alpha_results:
        variety_name = VARIETY_NAMES.get(variety, variety)
        try:
            result = analyzer.analyze_variety(variety, variety_name, days=7)
            sentiment_results[variety] = result
            print(f"  ✅ {variety_name} 情绪={result.get('sentiment_label', 'N/A')}"
                  f"  得分={result.get('sentiment_score', 0):.2f}")
        except Exception as e:
            print(f"  ❌ {variety_name} 情绪分析失败: {e}")

    print(f"\n✅ 完成 {len(sentiment_results)}/{ok_count} 个品种的情绪分析")

    # ── Step 3: 决策生成 ──────────────────────────────────────────────────
    print("\n[步骤 3/3] 决策报告生成...")
    advisor = LLMAdvisor(
        exchange_name = "大商所",
        session_name  = "DCE决策Agent",
        report_dir    = _REPORT_DIR,
    )
    reports = []

    for variety in alpha_results:
        if variety not in sentiment_results:
            continue
        variety_name = VARIETY_NAMES.get(variety, variety)
        try:
            report = advisor.generate_decision_report(
                variety,
                variety_name,
                alpha_results[variety],
                sentiment_results[variety],
            )
            reports.append(report)
            score = report["decision"].get("综合得分", "N/A")
            action = report["decision"].get("action", "N/A")
            print(f"  ✅ {variety_name} 决策  综合={score}  建议={action}")
        except Exception as e:
            print(f"  ❌ {variety_name} 决策报告失败: {e}")

    print(f"\n✅ 完成 {len(reports)} 个品种的决策报告")

    # 生成汇总报告
    if reports:
        if output_file is None:
            output_file = f"decision_report_{target_date.isoformat()}.md"
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = _REPORT_DIR / output_file
        advisor.generate_batch_report(reports, output_file)
        print(f"\n✅ 汇总报告已生成: {report_path}")

    print("\n" + "=" * 60)
    print("✅ DCE 决策系统运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DCE 大商所决策系统")
    parser.add_argument(
        "--varieties",
        nargs="+",
        help="指定品种列表（如: a m y）",
        default=None,
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="目标日期（如: 2026-04-25），默认今天",
        default=None,
    )
    parser.add_argument(
        "--output",
        help="输出报告文件名（如: report.md）",
        default=None,
    )
    args = parser.parse_args()
    main(
        varieties   = args.varieties,
        target_date = args.date,
        output_file = args.output,
    )
