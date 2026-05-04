"""
DCE 完整流程测试

端到端测试：数据采集 → 因子计算 → 情绪分析 → 决策生成
"""
import sys
from pathlib import Path
from datetime import date, datetime
import traceback
import time

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

_REPORT_DIR = Path(__file__).parent.parent / "reports"


def test_full_pipeline(test_variety: str = "a", test_variety_name: str = "豆一"):
    """
    完整流程端到端测试。

    Args:
        test_variety:      测试品种代码（如 "a"）
        test_variety_name: 测试品种中文名称（如 "豆一"）
    """
    print("\n" + "=" * 60)
    print("🔄 完整流程测试 - 端到端")
    print("=" * 60)

    start_time = time.time()
    results = {"steps": {}, "success": False, "error": None}

    try:
        # ── Step 1: 数据采集 ──────────────────────────────────────────
        print("\n[步骤 1/4] 数据采集...")
        print("-" * 60)
        from ai.agent.DCE.data_collector.collector import daily_update

        update_result = daily_update()
        results["steps"]["data_collection"] = {
            "success":          update_result.get("status") in ("success", "up_to_date"),
            "target_date":      update_result.get("target_date"),
            "new_contracts":    update_result.get("new_contracts", 0),
            "updated_varieties": update_result.get("updated_varieties", 0),
        }
        print(f"✅ 数据采集完成")
        print(f"  目标日期: {update_result.get('target_date')}")
        print(f"  新增合约: {update_result.get('new_contracts')} 个")

        # ── Step 2: Alpha158 因子计算 ─────────────────────────────────
        print("\n[步骤 2/4] Alpha158 因子计算...")
        print("-" * 60)
        from ai.agent.common.factor_analysis import Alpha158Calculator
        from vnpy.trader.constant import Exchange

        calculator   = Alpha158Calculator()
        alpha_features = calculator.calculate_for_variety(test_variety, Exchange.DCE)
        if not alpha_features:
            raise ValueError(f"品种 {test_variety} 因子计算失败")

        feature_count = len([k for k in alpha_features if not k.startswith("_")])
        results["steps"]["alpha158"] = {
            "success":       True,
            "variety":       test_variety,
            "feature_count": feature_count,
            "close_price":   alpha_features.get("_close"),
            "date":          str(alpha_features.get("_date")),
        }
        print(f"✅ 因子计算完成")
        print(f"  品种: {test_variety}  特征数: {feature_count}  收盘价: {alpha_features.get('_close', 0):.2f}")

        # ── Step 3: 新闻情绪分析 ──────────────────────────────────────
        print("\n[步骤 3/4] 新闻情绪分析...")
        print("-" * 60)
        from ai.agent.common.news_sentiment import NewsSentimentAnalyzer

        analyzer  = NewsSentimentAnalyzer()
        mock_news = [{
            "title":        f"{test_variety_name}期货走势分析",
            "content":      f"{test_variety_name}市场供需平衡",
            "publish_time": datetime.now(),
            "url":          "http://example.com",
            "source":       "测试",
        }]
        sentiment_result = analyzer.analyze_sentiment_with_llm(mock_news, test_variety_name)
        sentiment_result["variety"]      = test_variety
        sentiment_result["variety_name"] = test_variety_name

        results["steps"]["sentiment"] = {
            "success":         True,
            "variety":         test_variety,
            "sentiment_label": sentiment_result.get("sentiment_label"),
            "sentiment_score": sentiment_result.get("sentiment_score"),
            "news_count":      len(mock_news),
        }
        print(f"✅ 情绪分析完成")
        print(f"  情绪标签: {sentiment_result.get('sentiment_label')}")
        print(f"  情绪得分: {sentiment_result.get('sentiment_score', 0):.2f}")

        # ── Step 4: 决策生成 ──────────────────────────────────────────
        print("\n[步骤 4/4] 决策报告生成...")
        print("-" * 60)
        from ai.agent.common.llm_advisor import LLMAdvisor

        advisor = LLMAdvisor(
            exchange_name = "大商所",
            session_name  = "DCE决策Agent",
            report_dir    = _REPORT_DIR,
        )
        decision_report = advisor.generate_decision_report(
            test_variety, test_variety_name, alpha_features, sentiment_result
        )
        report_md = advisor.generate_batch_report(
            [decision_report],
            f"test_report_{test_variety}_{date.today().isoformat()}.md",
        )
        results["steps"]["decision"] = {
            "success":       True,
            "variety":       test_variety,
            "score":         decision_report["decision"]["综合得分"],
            "view":          decision_report["decision"]["market_view"],
            "action":        decision_report["decision"]["action"],
            "report_length": len(report_md),
        }
        print(f"✅ 决策生成完成")
        print(f"  综合得分: {decision_report['decision']['综合得分']}")
        print(f"  市场观点: {decision_report['decision']['market_view']}")
        print(f"  操作建议: {decision_report['decision']['action']}")

        results["success"] = True

    except Exception as e:
        results["error"] = str(e)
        print(f"\n❌ 流程测试失败: {e}")
        traceback.print_exc()

    duration = time.time() - start_time
    results["duration_seconds"] = round(duration, 2)

    print("\n" + "=" * 60)
    print("📊 完整流程测试结果")
    print("=" * 60)
    for step_name, step_result in results["steps"].items():
        status = "✅ 通过" if step_result.get("success") else "❌ 失败"
        print(f"  {step_name}: {status}")

    if results["success"]:
        print(f"\n✅ 完整流程测试通过！耗时 {duration:.2f}s")
    else:
        print(f"\n❌ 完整流程测试失败：{results.get('error', '未知')}")

    return results


if __name__ == "__main__":
    test_full_pipeline("a", "豆一")
