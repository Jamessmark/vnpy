"""
DCE 模块单元测试

测试所有核心模块的功能正确性，不依赖网络（API 测试除外）。
"""
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
import traceback

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def test_dce_api():
    """测试 DCE API 客户端"""
    print("\n" + "=" * 60)
    print("测试模块 1: DCE API 客户端")
    print("=" * 60)
    try:
        from ai.agent.DCE.data_collector.dce_api import get_dce_client

        client = get_dce_client()

        print("\n[测试 1.1] 获取最新交易日...")
        trade_date = client.get_max_trade_date()
        print(f"✅ 最新交易日: {trade_date}")

        print("\n[测试 1.2] 获取品种列表...")
        varieties = client.get_varieties()
        print(f"✅ 品种数量: {len(varieties)}")
        if varieties:
            print(f"  示例品种: {varieties[0].get('varietyName')} ({varieties[0].get('varietyId')})")

        print("\n[测试 1.3] 获取历史日K线...")
        test_date = "20251014"
        quotes = client.get_day_quotes(test_date, variety_id="a")
        print(f"✅ 获取到 {len(quotes)} 条行情数据")
        if quotes:
            print(f"  示例: {quotes[0].get('contractId')} 收盘价 {quotes[0].get('closePrice')}")

        print("\n" + "-" * 60)
        print("✅ DCE API 客户端测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
        return False


def test_main_contract_manager():
    """测试通用主力合约管理"""
    print("\n" + "=" * 60)
    print("测试模块 2: 主力合约管理（common）")
    print("=" * 60)
    try:
        from ai.agent.common.main_contract_manager import (
            MappingStore,
            symbol_prefix,
            calculate_weighted_bar,
        )

        print("\n[测试 2.1] 品种前缀提取...")
        assert symbol_prefix("a2507") == "a"
        assert symbol_prefix("MA2505") == "MA"
        print("✅ 品种前缀提取正确")

        print("\n[测试 2.2] 主力映射表存储...")
        store = MappingStore()
        test_mapping = [{
            "trade_date":    date.today(),
            "dominant":      "a2507",
            "sub_dominant":  "a2509",
            "open_interest": 150000.0,
        }]
        rows = store.save_mapping("a", "DCE", test_mapping)
        print(f"✅ 保存 {rows} 条记录")
        dominant = store.get_dominant("a", "DCE", date.today())
        print(f"✅ 查询主力合约: {dominant}")
        store.close()

        print("\n[测试 2.3] 加权合成计算...")
        bar1 = {
            "symbol": "a2507", "datetime": datetime.now(),
            "open": 3500, "high": 3520, "low": 3490, "close": 3510,
            "volume": 100000, "turnover": 351000000, "open_interest": 150000,
        }
        bar2 = {
            "symbol": "a2509", "datetime": datetime.now(),
            "open": 3480, "high": 3500, "low": 3470, "close": 3490,
            "volume": 80000, "turnover": 279200000, "open_interest": 120000,
        }
        weighted = calculate_weighted_bar("a", None, bar1, bar2)
        print(f"✅ 加权合成成功")
        print(f"  加权收盘价: {weighted['close']:.2f}")
        print(f"  总成交量:   {weighted['volume']}")
        print(f"  总持仓量:   {weighted['open_interest']}")

        print("\n" + "-" * 60)
        print("✅ 主力合约管理测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
        return False


def test_bar_utils():
    """测试通用 bar 工具函数"""
    print("\n" + "=" * 60)
    print("测试模块 3: Bar 工具函数（common）")
    print("=" * 60)
    try:
        from ai.agent.common.bar_utils import parse_date, format_date, get_trade_dates

        print("\n[测试 3.1] 日期解析与格式化...")
        d = parse_date("20250415")
        assert d.year == 2025 and d.month == 4 and d.day == 15
        assert format_date(d) == "20250415"
        print("✅ 日期解析与格式化正确")

        print("\n[测试 3.2] 交易日枚举...")
        from datetime import date as dt_date
        dates = get_trade_dates(dt_date(2025, 4, 14), dt_date(2025, 4, 18))
        assert len(dates) == 5  # 周一到周五
        print(f"✅ 交易日枚举正确：{dates}")

        print("\n" + "-" * 60)
        print("✅ Bar 工具函数测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
        return False


def test_alpha158_calculator():
    """测试 Alpha158 因子计算（直接使用 common）"""
    print("\n" + "=" * 60)
    print("测试模块 4: Alpha158 因子计算（common）")
    print("=" * 60)
    try:
        from ai.agent.common.factor_analysis import Alpha158Calculator
        import polars as pl
        import numpy as np

        calculator = Alpha158Calculator()

        print("\n[测试 4.1] 创建模拟数据...")
        dates = [datetime.now() - timedelta(days=i) for i in range(100, 0, -1)]
        prices = 3500 + np.cumsum(np.random.randn(100) * 10)
        data = [{
            "datetime":      dt,
            "open":          prices[i] - 5,
            "high":          prices[i] + 10,
            "low":           prices[i] - 10,
            "close":         prices[i],
            "volume":        100000 + int(np.random.randint(-20000, 20000)),
            "turnover":      prices[i] * 100000,
            "open_interest": 150000 + int(np.random.randint(-10000, 10000)),
        } for i, dt in enumerate(dates)]
        df = pl.DataFrame(data)
        print(f"✅ 创建了 {len(df)} 天的模拟数据")

        print("\n[测试 4.2] 计算 Alpha158 特征...")
        features = calculator.calculate_alpha158(df)
        feature_count = len([k for k in features if not k.startswith("_")])
        print(f"✅ 计算了 {feature_count} 个特征")
        for key in list(features.keys())[:5]:
            if not key.startswith("_"):
                print(f"    {key}: {features[key]:.4f}")

        print("\n" + "-" * 60)
        print("✅ Alpha158 因子计算测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
        return False


def test_sentiment_analyzer():
    """测试新闻情绪分析（direct from common）"""
    print("\n" + "=" * 60)
    print("测试模块 5: 新闻情绪分析（common）")
    print("=" * 60)
    try:
        from ai.agent.common.news_sentiment import NewsSentimentAnalyzer

        analyzer = NewsSentimentAnalyzer()

        print("\n[测试 5.1] 情绪分析逻辑（模拟新闻）...")
        mock_news = [
            {
                "title": "豆粕期货强势上涨突破新高",
                "content": "受供应趋紧影响，豆粕期货持续走强",
                "publish_time": datetime.now(),
                "url": "http://example.com",
                "source": "测试",
            },
            {
                "title": "豆粕市场看多情绪浓厚",
                "content": "机构普遍看好后市表现",
                "publish_time": datetime.now(),
                "url": "http://example.com",
                "source": "测试",
            },
        ]
        result = analyzer.analyze_sentiment_with_llm(mock_news, "豆粕")
        print(f"✅ 情绪分析完成")
        print(f"  情绪标签: {result['sentiment_label']}")
        print(f"  情绪得分: {result['sentiment_score']:.2f}")
        print(f"  摘要:     {result['summary']}")

        print("\n" + "-" * 60)
        print("✅ 新闻情绪分析测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
        return False


def test_llm_advisor():
    """测试 LLM 决策顾问（direct from common）"""
    print("\n" + "=" * 60)
    print("测试模块 6: LLM 决策顾问（common）")
    print("=" * 60)
    try:
        from ai.agent.common.llm_advisor import LLMAdvisor
        from pathlib import Path

        report_dir = Path(__file__).parent.parent / "reports"
        advisor = LLMAdvisor(
            exchange_name = "大商所",
            session_name  = "DCE决策Agent",
            report_dir    = report_dir,
        )

        print("\n[测试 6.1] 生成单个品种决策报告...")
        alpha_features = {
            "_date":              date.today(),
            "_close":             3500.0,
            "_volume":            150000,
            "return_5d":          0.025,
            "return_20d":         0.08,
            "rsi_14":             65,
            "bollinger_position": 0.7,
            "volume_ratio_5":     1.3,
        }
        sentiment_result = {
            "sentiment_score": 0.4,
            "sentiment_label": "偏多",
            "summary":         "分析了10条新闻，整体情绪偏多",
            "key_points":      [{"title": "豆粕期货创新高", "tendency": "利多"}],
        }
        report = advisor.generate_decision_report("m", "豆粕", alpha_features, sentiment_result)
        print(f"✅ 决策报告生成成功")
        print(f"  综合得分: {report['decision']['综合得分']}")
        print(f"  市场观点: {report['decision']['market_view']}")
        print(f"  操作建议: {report['decision']['action']}")

        print("\n[测试 6.2] 生成批量报告...")
        md_content = advisor.generate_batch_report([report], "test_report.md")
        print(f"✅ 批量报告生成成功，长度: {len(md_content)} 字符")

        print("\n" + "-" * 60)
        print("✅ LLM 决策顾问测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
        return False


def test_dce_constants():
    """测试 DCE 常量文件"""
    print("\n" + "=" * 60)
    print("测试模块 7: DCE 常量")
    print("=" * 60)
    try:
        from ai.agent.DCE.dce_constants import VARIETIES, VARIETY_NAMES, CORE_VARIETIES

        print(f"✅ VARIETIES 品种数: {len(VARIETIES)}")
        print(f"✅ CORE_VARIETIES 品种数: {len(CORE_VARIETIES)}")
        print(f"✅ VARIETY_NAMES 映射数: {len(VARIETY_NAMES)}")
        assert "m" in VARIETY_NAMES
        assert VARIETY_NAMES["m"] == "豆粕"
        print(f"✅ 验证 m -> {VARIETY_NAMES['m']}")

        print("\n" + "-" * 60)
        print("✅ DCE 常量测试通过")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有模块测试"""
    print("\n" + "=" * 60)
    print("🧪 DCE 决策系统 - 模块单元测试")
    print("=" * 60)

    results = {
        "DCE API 客户端":   test_dce_api(),
        "主力合约管理":      test_main_contract_manager(),
        "Bar 工具函数":      test_bar_utils(),
        "Alpha158 计算":     test_alpha158_calculator(),
        "新闻情绪分析":      test_sentiment_analyzer(),
        "LLM 决策顾问":      test_llm_advisor(),
        "DCE 常量":          test_dce_constants(),
    }

    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    total  = len(results)
    passed = sum(1 for v in results.values() if v)
    for module, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {module}: {status}")
    print(f"\n总计 {total} 个模块 | 通过 {passed} | 失败 {total - passed}")
    print(f"通过率: {passed / total * 100:.1f}%")
    return results


if __name__ == "__main__":
    run_all_tests()
