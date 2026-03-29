"""
新闻摘要工具 - 基于 news-summary skill
从 BBC/Reuters/Al Jazeera RSS 抓取新闻，用 LLM 生成摘要

用法：
    uv run python ai_news/fetchers/news_summary.py              # 文字摘要
    uv run python ai_news/fetchers/news_summary.py --topic oil  # 只看原油相关新闻

依赖：uv add feedparser openai python-dotenv
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import feedparser
from dotenv import load_dotenv
from openai import OpenAI

# 加载根目录 .env 文件
load_dotenv(Path(__file__).parent.parent / ".env")

# ── 从 config.json 加载配置（可复用）──────────────────────────────
_cfg = json.loads((Path(__file__).parent.parent / "config" / "config.json").read_text(encoding="utf-8"))

# RSS 数据源：env 变量可覆盖 default URL
RSS_FEEDS: dict[str, tuple[str, str]] = {
    key: (val["name"], os.getenv(val["env"], val["default"]))
    for key, val in _cfg["rss_feeds"].items()
}

# 主题关键词
TOPIC_KEYWORDS: dict[str, list[str]] = _cfg["topic_keywords"]


def fetch_headlines(feed_keys: list[str], max_per_feed: int = 100) -> list[dict]:
    """从多个 RSS 源抓取标题和摘要"""
    items = []
    for key in feed_keys:
        name, url = RSS_FEEDS[key]
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                items.append({
                    "title":   entry.get("title", ""),
                    "summary": entry.get("summary", entry.get("description", ""))[:200],
                    "source":  name,
                    "link":    entry.get("link", ""),
                })
        except Exception as e:
            print(f"  [警告] 抓取失败 {url}: {e}", file=sys.stderr)
    return items


def filter_by_topic(items: list[dict], topic: str) -> list[dict]:
    """按主题关键词过滤新闻"""
    keywords = TOPIC_KEYWORDS.get(topic.lower(), [topic])
    result = []
    for item in items:
        text = (item["title"] + " " + item["summary"]).lower()
        if any(kw.lower() in text for kw in keywords):
            result.append(item)
    return result


def sample_by_source(items: list[dict], total: int = 40) -> list[dict]:
    """按来源均匀采样，避免某个源独占"""
    from collections import defaultdict
    buckets: dict = defaultdict(list)
    for item in items:
        buckets[item["source"]].append(item)
    per_source = max(3, total // max(len(buckets), 1))
    sampled = []
    for source_items in buckets.values():
        sampled.extend(source_items[:per_source])
    return sampled[:total]


def summarize_with_llm(items: list[dict], topic: str | None = None) -> str:
    """调用 LLM 生成新闻摘要"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return format_raw(sample_by_source(items))

    client = OpenAI(api_key=api_key)

    # 按来源均匀采样
    sampled = sample_by_source(items)

    # 构建新闻文本
    news_text = "\n".join(
        f"{i+1}. [{item['source']}] {item['title']}: {item['summary']}"
        for i, item in enumerate(sampled[:40])
    )

    topic_hint = f"重点关注与【{topic}】相关的内容。" if topic else ""
    prompt = f"""你是一位专业的财经新闻编辑。以下是今日最新新闻，请提炼出 5-8 条最重要的内容，生成简洁的中文摘要。{topic_hint}

新闻列表：
{news_text}

输出格式：
📰 新闻摘要 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]

🌍 [分类]
- [要点1]
- [要点2]
...

要求：每条摘要不超过50字，保留关键数据和事实。"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return resp.choices[0].message.content


def format_raw(items: list[dict]) -> str:
    """无 API Key 时的原始格式输出"""
    lines = [f"📰 新闻摘要 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]\n"]
    for item in items:
        lines.append(f"• [{item['source']}] {item['title']}")
    return "\n".join(lines)



def main():
    parser = argparse.ArgumentParser(description="新闻摘要工具")
    parser.add_argument("--topic", "-t", type=str, help="过滤主题: oil / gold / china / fed")
    parser.add_argument("--feeds", "-f", nargs="+",
                        choices=list(RSS_FEEDS.keys()),
                        default=list(RSS_FEEDS.keys()),
                        help="选择数据源（默认: 全部）")
    args = parser.parse_args()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在抓取新闻...", file=sys.stderr)

    # 1. 抓取新闻
    items = fetch_headlines(args.feeds, max_per_feed=100)
    print(f"  共抓取 {len(items)} 条新闻", file=sys.stderr)

    # 2. 主题过滤
    if args.topic:
        items = filter_by_topic(items, args.topic)
        print(f"  主题过滤后剩余 {len(items)} 条", file=sys.stderr)
        if not items:
            print(f"未找到与 [{args.topic}] 相关的新闻")
            return

    # 3. LLM 摘要
    print("  正在生成摘要...", file=sys.stderr)
    summary = summarize_with_llm(items, topic=args.topic)
    print(summary)



if __name__ == "__main__":
    main()
