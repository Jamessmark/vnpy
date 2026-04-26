"""
郑州商品交易所期权历史行情数据下载工具

下载指定年份所有品种的期权日行情数据，保存到本地。
数据来源：郑州商品交易所官网
URL格式：https://www.czce.com.cn/cn/DFSStaticFiles/Option/{year}/OptionDataAllHistory/{SYMBOL}OPTIONS{year}.txt

使用方法：
    uv run python ai/data_process/download_czce_options.py

    # 下载指定年份
    uv run python ai/data_process/download_czce_options.py --year 2026
"""

import argparse
import time
from pathlib import Path

import requests

# ─────────────────────────────────────────────────────────────
# 郑商所所有期权品种代码
# ─────────────────────────────────────────────────────────────

ALL_OPTIONS = [
    "AP",   # 苹果期权
    "CF",   # 棉花期权
    "CJ",   # 红枣期权
    "FG",   # 玻璃期权
    "MA",   # 甲醇期权
    "OI",   # 菜籽油期权
    "PF",   # 短纤期权
    "PK",   # 花生仁期权
    "PL",   # 花生油期权
    "PR",   # 花生原料期权
    "PX",   # 对二甲苯期权
    "RM",   # 菜籽粕期权
    "SA",   # 纯碱期权
    "SF",   # 硅铁期权
    "SH",   # 花生期权
    "SM",   # 锰硅期权
    "SR",   # 白糖期权
    "TA",   # PTA期权
    "UR",   # 尿素期权
    "ZC",   # 动力煤期权
]

BASE_URL = "https://www.czce.com.cn/cn/DFSStaticFiles/Option/{year}/OptionDataAllHistory/{symbol}OPTIONS{year}.txt"

# 输出目录
DATA_ROOT = Path(__file__).parent.parent / "data" / "czce_options"


def download_symbol(symbol: str, year: int, save_dir: Path, session: requests.Session) -> bool:
    """下载单个品种的数据文件"""
    url = BASE_URL.format(year=year, symbol=symbol)
    save_path = save_dir / f"{symbol}OPTIONS{year}.txt"

    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 404:
            return False  # 该年份该品种无数据，静默跳过
        resp.raise_for_status()

        # 检查内容是否是有效的数据
        content = resp.content
        if len(content) < 100:
            return False

        save_path.write_bytes(content)
        size_kb = len(content) / 1024
        print(f"  ✅ {symbol}: {size_kb:.1f} KB → {save_path.name}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"  ❌ {symbol}: 请求失败 - {e}")
        return False


def download_year(year: int, symbols: list[str]) -> None:
    """下载指定年份所有品种"""
    save_dir = DATA_ROOT / str(year)
    save_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"下载 {year} 年郑商所期权数据")
    print(f"保存路径：{save_dir}")
    print(f"品种数量：{len(symbols)}")
    print(f"{'='*50}")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.czce.com.cn/",
    })

    success = 0
    failed = []

    for symbol in symbols:
        ok = download_symbol(symbol, year, save_dir, session)
        if ok:
            success += 1
        else:
            failed.append(symbol)
        time.sleep(0.3)  # 礼貌性延迟

    print(f"\n{'─'*50}")
    print(f"✅ 成功下载：{success} 个品种")
    if failed:
        print(f"⚠️  未找到数据：{', '.join(failed)}")

    # 统计文件总大小
    total_size = sum(f.stat().st_size for f in save_dir.glob("*.txt"))
    print(f"📁 总大小：{total_size / 1024:.1f} KB")


def main() -> None:
    parser = argparse.ArgumentParser(description="郑商所期权历史数据下载工具")
    parser.add_argument("--year", type=int, default=2026, help="下载年份（默认2026）")
    parser.add_argument(
        "--symbols", nargs="+",
        help="指定品种代码（如 SR CF），不指定则下载所有品种"
    )
    args = parser.parse_args()

    symbols = [s.upper() for s in args.symbols] if args.symbols else ALL_OPTIONS
    download_year(args.year, symbols)


if __name__ == "__main__":
    main()
