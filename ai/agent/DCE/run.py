"""
DCE 决策系统主运行脚本

流程：
    1. [新增] 通过 DCE API 下载最新日K线数据，保存到数据库
    2. [新增] 更新主力映射表 + 合成 888 主连合约
    3. Alpha158 因子计算（从数据库读取 888 数据）
    4. 新闻获取
    5. LLM 决策报告生成

DCE 大商所主要品种：豆一、豆二、玉米、玉米淀粉、豆粕、豆油、棕榈油、鸡蛋、
                塑料、PVC、聚丙烯、焦炭、焦煤、铁矿石、乙二醇、苯乙烯、液化石油气

用法：
    # 运行全部核心品种（自动拉取今日最新数据）
    uv run python ai/agent/DCE/run.py

    # 指定品种
    uv run python ai/agent/DCE/run.py --varieties a m y
    uv run python ai/agent/DCE/run.py --varieties p m y --date 2026-05-26

    # 跳过数据更新（仅用已有数据生成报告）
    uv run python ai/agent/DCE/run.py --no-fetch

    # 指定目标日期（计算哪天因子，默认最新）
    uv run python ai/agent/DCE/run.py --date 2026-04-25

    # 指定输出文件名
    uv run python ai/agent/DCE/run.py --output my_report.md
"""
import os
import sys
from pathlib import Path
from datetime import date, datetime
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ── 数据采集层 ───────────────────────────────────────────────────────────────
from ai.agent.DCE.data_collector.collector import daily_update

# ── 通用层 ──────────────────────────────────────────────────────────────────
from ai.agent.common.factor_analysis import Alpha158Calculator
from ai.agent.common.news_sentiment import NewsSentimentAnalyzer
from ai.agent.common.llm_advisor import LLMAdvisor

# ── DCE 专有 ────────────────────────────────────────────────────────────────
from ai.agent.DCE.dce_constants import CORE_VARIETIES, VARIETY_NAMES

# 报告目录
_REPORT_DIR = Path(__file__).parent / "reports"


def _send_report_email(report_path: Path, target_date: date) -> None:
    """
    用 yagmail 将报告以 HTML 邮件发送到 163 邮箱。
    邮件正文 = Markdown 原文（纯文本），附件 = .md 报告文件。
    所需 .env 配置：
        MAIL_USER     发件人 163 邮箱账号
        MAIL_PASSWORD 163 SMTP 授权码（非登录密码）
        MAIL_TO       收件人邮箱（默认同发件人）
    """
    import yagmail

    user     = os.getenv("MAIL_USER", "").strip()
    password = os.getenv("MAIL_PASSWORD", "").strip()
    to       = os.getenv("MAIL_TO", user).strip()

    if not user or not password:
        print("  ⚠️ 邮件未发送：.env 中 MAIL_USER / MAIL_PASSWORD 未配置")
        return

    subject = f"📊 DCE 大商所日报 {target_date.isoformat()}"

    # 读取报告正文（Markdown 纯文本作为邮件正文）
    body = report_path.read_text(encoding="utf-8") if report_path.exists() else "（报告文件未找到）"

    try:
        yag = yagmail.SMTP(
            user     = user,
            password = password,
            host     = "smtp.163.com",
            port     = 994,
            smtp_ssl = True,
        )
        yag.send(
            to          = to,
            subject     = subject,
            contents    = body,
            attachments = str(report_path) if report_path.exists() else None,
        )
        print(f"  ✅ 报告已发送至 {to}")
    except Exception as e:
        print(f"  ❌ 邮件发送失败: {e}")


def main(
    varieties: list = None,
    target_date: date = None,
    output_file: str = None,
    fetch_data: bool = True,
) -> None:
    """
    主运行流程：API 拉取数据 → 主连更新 → Alpha158 因子计算 → 新闻获取 → LLM 决策报告。

    Args:
        varieties:    品种列表；None 则使用 CORE_VARIETIES 全部品种
        target_date:  目标日期；None 则使用数据库最新有数据的日期
        output_file:  汇总报告文件名（不含目录）
        fetch_data:   是否先通过 API 拉取最新数据（默认 True）
    """
    print("\n" + "=" * 60)
    print("🚀 DCE 决策系统 - 主流程")
    print("=" * 60)

    if varieties is None:
        varieties = CORE_VARIETIES

    # ── Step 1: 拉取最新日K线数据并更新主连 ────────────────────────────────
    if fetch_data:
        print("\n[步骤 1/4] 通过 DCE API 拉取最新日K线数据...")
        try:
            # 若用户指定了日期，把它传给 daily_update，避免拉取超出范围的数据
            fetch_target = target_date.strftime("%Y%m%d") if target_date else None
            update_stats = daily_update(target_date=fetch_target)
            status = update_stats.get("status", "unknown")
            if status == "up_to_date":
                print(f"  ✅ 数据已是最新（{update_stats.get('target_date')}），无需更新")
                # 使用 API 返回的最新交易日作为目标日期
                if target_date is None and update_stats.get("target_date"):
                    from datetime import datetime as dt
                    target_date = dt.strptime(update_stats["target_date"], "%Y%m%d").date()
            elif status == "success":
                new_cnt = update_stats.get("new_contracts", 0)
                updated = update_stats.get("updated_varieties", 0)
                td = update_stats.get("target_date", "")
                print(f"  ✅ 数据更新成功！日期={td}, 新增={new_cnt} 条合约数据, 更新={updated} 个品种主连")
                if target_date is None and td:
                    from datetime import datetime as dt
                    target_date = dt.strptime(td, "%Y%m%d").date()
                if update_stats.get("errors"):
                    print(f"  ⚠️ 部分错误: {len(update_stats['errors'])} 个")
                    for err in update_stats["errors"][:3]:
                        print(f"     - {err}")
            else:
                print(f"  ⚠️ 数据更新状态: {status}")
        except Exception as e:
            print(f"  ❌ 数据拉取失败: {e}，将使用数据库现有数据继续")
    else:
        print("\n[步骤 1/4] 跳过数据拉取（--no-fetch 模式）")

    if target_date is None:
        target_date = date.today()

    print(f"\n📊 处理品种: {len(varieties)} 个")
    print(f"   {', '.join(varieties)}")
    print(f"📅 目标日期: {target_date}")

    # ── Step 2: Alpha158 因子计算（直接从数据库读取 888 数据）───────────────
    print("\n[步骤 2/4] Alpha158 因子计算...")
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

    # ── Step 3: 新闻获取 ───────────────────────────────────────────────────────
    print("\n[步骤 3/4] 新闻获取...")
    analyzer          = NewsSentimentAnalyzer()
    sentiment_results = {}

    for variety in alpha_results:
        variety_name = VARIETY_NAMES.get(variety, variety)
        try:
            result = analyzer.analyze_variety(variety, variety_name, days=30)
            sentiment_results[variety] = result
            print(f"  ✅ {variety_name} 新闻={result.get('news_count', 0)} 条")
        except Exception as e:
            print(f"  ❌ {variety_name} 情绪分析失败: {e}")

    print(f"\n✅ 完成 {len(sentiment_results)}/{ok_count} 个品种的情绪分析")

    # ── Step 4: 决策生成 ─────────────────────────────────────────────────────
    print("\n[步骤 4/4] 决策报告生成...")
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
            close = report.get("close_price", 0)
            has_resp = bool(report.get("llm_response"))
            print(f"  ✅ {variety_name} 收盘={close:.2f}  LLM={'✓' if has_resp else '✗'}")
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

        # ── Step 5: 发送邮件 ────────────────────────────────────────────────
        print("\n[步骤 5/5] 发送邮件报告...")
        _send_report_email(report_path, target_date)

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
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="跳过 API 数据拉取，直接使用数据库现有数据",
        default=False,
    )
    args = parser.parse_args()
    main(
        varieties   = args.varieties,
        target_date = args.date,
        output_file = args.output,
        fetch_data  = not args.no_fetch,
    )
