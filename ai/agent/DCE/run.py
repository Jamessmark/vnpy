"""
DCE 决策系统主运行脚本
DCE 大商所共 17 个品种：豆一、豆二、玉米、玉米淀粉、豆粕、豆油、棕榈油、鸡蛋、塑料、PVC、聚丙烯、焦炭、焦煤、铁矿石、乙二醇、苯乙烯、液化石油气

# 运行全部流程（默认处理全部 17 个品种）
uv run python ai/agent/DCE/run.py

# 指定品种
uv run python ai/agent/DCE/run.py --varieties a m y

# 跳过数据更新（使用已有数据）
uv run python ai/agent/DCE/run.py --skip-update

# 指定输出文件名
uv run python ai/agent/DCE/run.py --output my_report.md
"""
import sys
from pathlib import Path
from datetime import date
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ai.agent.DCE.data_collector.collector import daily_update, VARIETIES
from ai.agent.DCE.factor_analysis.alpha158_calculator import Alpha158Calculator
from ai.agent.DCE.news_sentiment.sentiment_analyzer import NewsSentimentAnalyzer, VARIETY_NAMES
from ai.agent.DCE.decision_engine.llm_advisor import LLMAdvisor


# DCE 全部品种列表
DCE_ALL_VARIETIES = [
    "a",   # 豆一
    "b",   # 豆二
    "c",   # 玉米
    "cs",  # 玉米淀粉
    "m",   # 豆粕
    "y",   # 豆油
    "p",   # 棕榈油
    "jd",  # 鸡蛋
    "l",   # 塑料
    "v",   # PVC
    "pp",  # 聚丙烯
    "j",   # 焦炭
    "jm",  # 焦煤
    "i",   # 铁矿石
    "eg",  # 乙二醇
    "eb",  # 苯乙烯
    "pg",  # 液化石油气
]


def main(
    varieties: list = None,
    skip_update: bool = False,
    output_file: str = None
):
    """
    主运行流程
    
    Args:
        varieties: 品种列表（None则使用全部品种）
        skip_update: 是否跳过数据更新
        output_file: 输出报告文件名
    """
    print("\n" + "="*60)
    print("🚀 DCE 决策系统 - 主流程")
    print("="*60)
    
    if varieties is None:
        varieties = DCE_ALL_VARIETIES  # 默认处理全部品种
    
    print(f"📊 处理品种: {len(varieties)} 个")
    print(f"   {', '.join(varieties)}")
    
    # Step 1: 数据采集
    if not skip_update:
        print("\n[步骤 1/4] 数据采集与更新...")
        try:
            update_result = daily_update(backfill_days=100)
            print(f"✅ 数据更新完成")
        except Exception as e:
            print(f"❌ 数据更新失败: {e}")
            return
    else:
        print("\n[步骤 1/4] 跳过数据更新")
    
    # Step 2: Alpha158 因子计算
    print("\n[步骤 2/4] Alpha158 因子计算...")
    calculator = Alpha158Calculator()
    alpha_results = {}
    
    for variety in varieties:
        try:
            features = calculator.calculate_for_variety(variety)
            if features:
                alpha_results[variety] = features
                print(f"  ✅ {variety} 因子计算完成")
        except Exception as e:
            print(f"  ❌ {variety} 因子计算失败: {e}")
    
    print(f"✅ 完成 {len(alpha_results)}/{len(varieties)} 个品种的因子计算")
    
    # Step 3: 新闻情绪分析
    print("\n[步骤 3/4] 新闻情绪分析...")
    analyzer = NewsSentimentAnalyzer()
    sentiment_results = {}
    
    for variety in alpha_results.keys():
        variety_name = VARIETY_NAMES.get(variety, variety)
        try:
            result = analyzer.analyze_variety(variety, variety_name, days=7)
            sentiment_results[variety] = result
            print(f"  ✅ {variety_name} 情绪分析完成")
        except Exception as e:
            print(f"  ❌ {variety_name} 情绪分析失败: {e}")
    
    print(f"✅ 完成 {len(sentiment_results)}/{len(alpha_results)} 个品种的情绪分析")
    
    # Step 4: 决策生成
    print("\n[步骤 4/4] 决策报告生成...")
    advisor = LLMAdvisor()
    reports = []
    
    for variety in alpha_results.keys():
        if variety not in sentiment_results:
            continue
        
        variety_name = VARIETY_NAMES.get(variety, variety)
        
        try:
            report = advisor.generate_decision_report(
                variety,
                variety_name,
                alpha_results[variety],
                sentiment_results[variety]
            )
            reports.append(report)
            print(f"  ✅ {variety_name} 决策报告完成")
        except Exception as e:
            print(f"  ❌ {variety_name} 决策报告失败: {e}")
    
    print(f"✅ 完成 {len(reports)} 个品种的决策报告")
    
    # 生成汇总报告
    if reports:
        if output_file is None:
            output_file = f"decision_report_{date.today().isoformat()}.md"
        
        advisor.generate_batch_report(reports, output_file)
        print(f"\n✅ 汇总报告已生成: {advisor.report_dir / output_file}")
    
    print("\n" + "="*60)
    print("✅ DCE 决策系统运行完成！")
    print("="*60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DCE 决策系统")
    parser.add_argument(
        "--varieties",
        nargs="+",
        help="指定品种列表（如: a m y）",
        default=None
    )
    parser.add_argument(
        "--skip-update",
        action="store_true",
        help="跳过数据更新"
    )
    parser.add_argument(
        "--output",
        help="输出报告文件名",
        default=None
    )
    
    args = parser.parse_args()
    
    main(
        varieties=args.varieties,
        skip_update=args.skip_update,
        output_file=args.output
    )
