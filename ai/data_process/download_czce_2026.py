"""
郑州商品交易所期货历史行情数据下载工具

下载指定年份所有品种的期货日行情数据，保存到本地。
数据来源：郑州商品交易所官网
URL格式：https://www.czce.com.cn/cn/DFSStaticFiles/Future/{year}/FutureDataAllHistory/{SYMBOL}FUTURES{year}.txt

使用方法：
    # 下载2026年所有品种
    uv run python ai/data_process/download_czce.py

    # 下载指定年份
    uv run python ai/data_process/download_czce.py --year 2025

    # 下载指定年份 + 品种
    uv run python ai/data_process/download_czce.py --year 2025 --symbols MA SA TA
"""

import argparse
import time
from pathlib import Path

import requests

# ─────────────────────────────────────────────────────────────
# 郑商所所有期货品种代码
# ─────────────────────────────────────────────────────────────

ALL_SYMBOLS = [
    "AP",   # 苹果
    "CF",   # 棉花
    "CJ",   # 红枣
    "CY",   # 棉纱
    "FG",   # 玻璃
    "JR",   # 粳稻
    "LR",   # 晚籼稻
    "MA",   # 甲醇
    "OI",   # 菜籽油
    "PF",   # 短纤
    "PK",   # 花生仁
    "PL",   # 花生油
    "PM",   # 普通小麦
    "PR",   # 花生原料（Peanut Raw）
    "PX",   # 对二甲苯
    "RI",   # 早籼稻
    "RM",   # 菜籽粕
    "RS",   # 菜籽
    "SA",   # 纯碱
    "SF",   # 硅铁
    "SH",   # 花生
    "SM",   # 锰硅
    "SR",   # 白糖
    "TA",   # PTA
    "UR",   # 尿素
    "WH",   # 强筋小麦
    "ZC",   # 动力煤

]

BASE_URL = "https://www.czce.com.cn/cn/DFSStaticFiles/Future/{year}/FutureDataAllHistory/{symbol}FUTURES{year}.txt"

# 输出目录
DATA_ROOT = Path(__file__).parent.parent / "data" / "czce"


def download_symbol(symbol: str, year: int, save_dir: Path, session: requests.Session) -> bool:
    """下载单个品种的数据文件"""
    url = BASE_URL.format(year=year, symbol=symbol)
    save_path = save_dir / f"{symbol}FUTURES{year}.txt"

    try:
        resp = session.get(url, timeout=15)
        if resp.status_code == 404:
            return False  # 该年份该品种无数据，静默跳过
        resp.raise_for_status()

        # 检查内容是否是有效的数据（不是错误页面）
        content = resp.content
        text_preview = content[:200].decode("gbk", errors="replace")
        if "404" in text_preview or "Not Found" in text_preview or len(content) < 100:
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
    print(f"下载 {year} 年郑商所期货数据")
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
        time.sleep(0.3)  # 礼貌性延迟，避免频繁请求

    print(f"\n{'─'*50}")
    print(f"✅ 成功下载：{success} 个品种")
    if failed:
        print(f"⚠️  未找到数据（该年份可能无此品种）：{', '.join(failed)}")

    # 统计文件总大小
    total_size = sum(f.stat().st_size for f in save_dir.glob("*.txt"))
    print(f"📁 总大小：{total_size / 1024:.1f} KB")


def main() -> None:
    parser = argparse.ArgumentParser(description="郑商所期货历史数据下载工具")
    parser.add_argument("--year", type=int, default=2026, help="下载年份（默认2026）")
    parser.add_argument(
        "--symbols", nargs="+",
        help="指定品种代码（如 MA SA TA），不指定则下载所有品种"
    )
    args = parser.parse_args()

    symbols = [s.upper() for s in args.symbols] if args.symbols else ALL_SYMBOLS
    download_year(args.year, symbols)


if __name__ == "__main__":
    main()
