"""
主连（888）历史数据重建工具 — 命令行入口

用法：

    # 重建 DCE 全部品种（force 覆盖重建）
    uv run python ai/agent/main_contract_builder/run.py --exchange DCE

    # 只重建指定品种
    uv run python ai/agent/main_contract_builder/run.py --exchange DCE --varieties a m y

    # 增量模式（已有 888 数据的日期跳过）
    uv run python ai/agent/main_contract_builder/run.py --exchange DCE --no-force

    # 探查数据库中有哪些品种
    uv run python ai/agent/main_contract_builder/run.py --exchange DCE --list

    # 重建其他交易所
    uv run python ai/agent/main_contract_builder/run.py --exchange CZCE
    uv run python ai/agent/main_contract_builder/run.py --exchange SHFE

    # 重建所有支持交易所的主连数据
    uv run python ai/agent/main_contract_builder/run.py --all

    # 所有交易所 + JSON 报告
    uv run python ai/agent/main_contract_builder/run.py -a -j --report all_exchanges.json
"""
import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vnpy.trader.database import get_database
from vnpy.trader.constant import Exchange, Interval

from ai.agent.main_contract_builder.builder import (
    rebuild_all,
    rebuild_variety,
    get_varieties_in_db,
    _to_exchange,
    _is_futures,
)


def _symbol_prefix(symbol: str) -> str:
    """从合约代码提取品种前缀"""
    import re
    return re.sub(r"\d", "", symbol)


def cmd_list(exchange: str) -> None:
    """探查数据库中指定交易所的期货品种列表（排除期权）"""
    exchange_enum = _to_exchange(exchange.upper())
    db = get_database()

    varieties = get_varieties_in_db(exchange_enum, db)
    overviews = db.get_bar_overview()

    print(f"\n{'='*50}")
    print(f"📦 {exchange.upper()} 数据库期货品种列表（共 {len(varieties)} 个）")
    print(f"{'='*50}")

    for v in varieties:
        # 统计该品种的合约数和日期范围
        v_overviews = [
            o for o in overviews
            if o.exchange == exchange_enum
            and o.interval == Interval.DAILY
            and _is_futures(o.symbol)
            and _symbol_prefix(o.symbol) == v
        ]
        if v_overviews:
            min_d = min((o.start.date() for o in v_overviews if o.start), default=None)
            max_d = max((o.end.date()   for o in v_overviews if o.end  ), default=None)
            print(f"  {v:<6}  合约数:{len(v_overviews):<4}  "
                  f"范围: {min_d} ~ {max_d}")
        else:
            print(f"  {v}")

    print()


def _run_all_exchanges(force: bool, json_output: bool, report_path: Path) -> None:
    """
    遍历所有支持的交易所，逐个执行 rebuild_all 并汇总。
    """
    all_exchanges = ["DCE", "CZCE", "SHFE", "INE", "GFEX", "CFFEX"]
    grand_summary = {
        "total_exchanges":  len(all_exchanges),
        "exchanges_ok":     0,
        "exchanges_fail":   0,
        "total_varieties":  0,
        "total_generated":  0,
        "total_errors":     0,
        "by_exchange":      {},
    }

    # 预探查：只保留数据库中有数据的交易所
    db = get_database()
    overviews  = db.get_bar_overview()
    exchanges_with_data = set(o.exchange.value for o in overviews)

    exchanges_to_run = [e for e in all_exchanges if e in exchanges_with_data]
    if not exchanges_to_run:
        print("⚠️  数据库中未发现任何支持交易所的合约数据")
        return

    print(f"\n{'#'*60}")
    print(f"🏭 全量重建所有交易所主连数据")
    print(f"   交易所: {exchanges_to_run}")
    print(f"   force: {force}")
    print(f"{'#'*60}")

    for exchange in exchanges_to_run:
        print(f"\n{'='*60}")
        print(f"🏛️  交易所: {exchange}")
        print(f"{'='*60}")
        try:
            result = rebuild_all(
                exchange  = exchange,
                varieties = None,   # None = 自动探测全部品种
                force     = force,
                verbose   = True,
            )
            grand_summary["by_exchange"][exchange] = result
            grand_summary["exchanges_ok"]       += 1
            grand_summary["total_varieties"]   += result.get("varieties_ok", 0)
            grand_summary["total_generated"]   += result.get("total_generated", 0)
            grand_summary["total_errors"]      += result.get("total_errors", 0)
        except Exception as e:
            print(f"   ❌ 交易所 {exchange} 整体失败: {e}")
            grand_summary["exchanges_fail"] += 1
            grand_summary["by_exchange"][exchange] = {"error": str(e)}

    # 汇总
    print(f"\n{'#'*60}")
    print(f"📊 全量重建汇总 — 全部 {len(exchanges_to_run)} 个交易所")
    print(f"{'#'*60}")
    print(f"  成功交易所: {grand_summary['exchanges_ok']} / {len(exchanges_to_run)}")
    print(f"  失败交易所: {grand_summary['exchanges_fail']}")
    print(f"  品种总数:   {grand_summary['total_varieties']}")
    print(f"  生成K线总数: {grand_summary['total_generated']}")
    print(f"  错误总数:   {grand_summary['total_errors']}")

    if json_output:
        print("\n" + json.dumps(grand_summary, indent=2, default=str))

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(grand_summary, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n📄 汇总已写入: {report_path.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="主连（888）历史数据重建工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--exchange", "-e",
        default="DCE",
        help="交易所代码（DCE/CZCE/SHFE/INE/GFEX/CFFEX，默认 DCE）",
    )
    parser.add_argument(
        "--varieties", "-v",
        nargs="+",
        default=None,
        help="指定品种代码列表（如 a m y），默认全部重建",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        default=True,
        help="强制覆盖已有 888 数据（默认开启）",
    )
    parser.add_argument(
        "--no-force",
        action="store_true",
        help="关闭 force，增量模式（跳过已有数据的日期）",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="仅探查数据库品种列表，不执行重建",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="输出 JSON 格式汇总结果",
    )
    parser.add_argument(
        "--variety",
        help="仅重建单个品种（简写，等效于 --varieties xxx）",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="将结果写入指定 JSON 文件",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="重建所有交易所的主连数据（DCE/CZCE/SHFE/INE/GFEX/CFFEX）",
    )

    args = parser.parse_args()

    exchange = args.exchange.upper()
    force    = not args.no_force   # --no-force 覆盖默认值

    # ── list 模式 ──────────────────────────────────────────────────────────
    if args.list:
        cmd_list(exchange)
        return

    # ── 全量重建所有交易所 ───────────────────────────────────────────────
    if args.all:
        _run_all_exchanges(force, args.json, args.report)
        return

    # ── 确定品种列表 ─────────────────────────────────────────────────────
    varieties = args.varieties
    if args.variety:
        varieties = [args.variety]

    # ── 单品种快速入口 ───────────────────────────────────────────────────
    if varieties and len(varieties) == 1:
        print(f"\n{'='*60}")
        print(f"🔨 重建 {exchange}.{varieties[0]} 主连历史数据  force={force}")
        print(f"{'='*60}")
        result = rebuild_variety(
            variety  = varieties[0],
            exchange = exchange,
            force    = force,
            verbose  = True,
        )
        summary = {
            "exchange":        exchange,
            "varieties_total": 1,
            "varieties_ok":    1 if result.get("generated", 0) > 0 else 0,
            "varieties_skip":  0,
            "total_generated": result.get("generated", 0),
            "total_errors":    result.get("errors", 0),
            "details":         {varieties[0]: result},
        }
    else:
        # ── 批量重建 ────────────────────────────────────────────────────
        summary = rebuild_all(
            exchange  = exchange,
            varieties = varieties,
            force     = force,
            verbose   = True,
        )

    # ── 输出 JSON ────────────────────────────────────────────────────────
    if args.json:
        print("\n" + json.dumps(summary, indent=2, default=str))

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n📄 结果已写入: {args.report.resolve()}")


if __name__ == "__main__":
    main()
