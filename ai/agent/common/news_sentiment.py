"""
新闻获取与兼容分析模块（腾讯新闻）

说明：
- 仅使用腾讯新闻 CLI 作为新闻来源。
- 保留 `NewsSentimentAnalyzer` 兼容接口，避免旧代码导入失败。
- 不做多空推断：统一返回中性分数，仅提供真实新闻内容。
"""

import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class NewsFetcher:
    """腾讯新闻抓取器（仅腾讯源）"""

    def __init__(self, timeout: int = 15):
        self._timeout = timeout
        self._cli_path = self._find_cli()

    def _find_cli(self) -> Optional[str]:
        path = shutil.which("tencent-news-cli")
        if path:
            return path

        candidates = [
            "~/.tencent-news-cli/bin/tencent-news-cli",
            "/usr/local/bin/tencent-news-cli",
            "/opt/homebrew/bin/tencent-news-cli",
        ]
        for p in candidates:
            full = os.path.expanduser(p)
            if os.path.isfile(full) and os.access(full, os.X_OK):
                return full
        return None

    def fetch_news(self, keyword: str, days: int = 7, max_results: int = 20) -> List[Dict]:
        """搜索新闻并返回结构化结果"""
        if not self._cli_path:
            print("⚠️ 腾讯新闻 CLI 未安装")
            return []

        try:
            result = subprocess.run(
                [self._cli_path, "search", keyword, "--limit", str(max_results)],
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            items = self._parse_output(result.stdout + result.stderr)
            if days > 0:
                items = self._filter_by_days(items, days)
            return items
        except subprocess.TimeoutExpired:
            print("⚠️ 腾讯新闻查询超时")
            return []
        except Exception as e:
            print(f"⚠️ 腾讯新闻查询失败: {e}")
            return []

    def _parse_output(self, output: str) -> List[Dict]:
        items: List[Dict] = []
        cur: Dict = {}

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            m = re.match(r"^\d+\.\s+标题[：:]\s*(.+)$", line)
            if m:
                if cur.get("title"):
                    items.append(cur)
                cur = {
                    "title": m.group(1).strip(),
                    "content": "",
                    "publish_time": None,
                    "url": "",
                    "source": "腾讯新闻",
                }
                continue

            m = re.match(r"^摘要[：:]\s*(.+)$", line)
            if m and cur:
                cur["content"] = m.group(1).strip()
                continue

            m = re.match(r"^来源[：:]\s*(.+)$", line)
            if m and cur:
                cur["source"] = m.group(1).strip()
                continue

            m = re.match(r"^发布时间[：:]\s*(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})", line)
            if m and cur:
                cur["publish_time"] = re.sub(r"[T\s]+", " ", m.group(1).strip())
                continue

            m = re.match(r"^链接[：:]\s*(https?://\S+)$", line)
            if m and cur:
                cur["url"] = m.group(1).strip()
                continue

        if cur.get("title"):
            items.append(cur)

        return items

    def _filter_by_days(self, items: List[Dict], days: int) -> List[Dict]:
        cutoff = datetime.now() - timedelta(days=days)
        out: List[Dict] = []
        for it in items:
            pt = it.get("publish_time")
            if not pt:
                out.append(it)
                continue
            try:
                dt = datetime.strptime(pt[:19], "%Y-%m-%d %H:%M:%S")
                if dt >= cutoff:
                    out.append(it)
            except Exception:
                out.append(it)
        return out


class NewsSentimentAnalyzer:
    """
    兼容旧接口：run.py 仍导入该类。

    注意：按你的要求，不做多空判断，仅返回真实新闻；
    情绪字段返回中性占位，供下游兼容使用。
    """

    def __init__(self):
        self._fetcher = NewsFetcher()

    def analyze_variety(self, variety: str, variety_name: str, days: int = 7) -> Dict:
        news = self._fetcher.fetch_news(variety_name, days=days, max_results=20)

        return {
            "variety": variety,
            "variety_name": variety_name,
            "news": news,
            "news_count": len(news),
            "sentiment_score": 0.0,
            "sentiment_label": "中性",
            "summary": f"腾讯新闻共获取 {len(news)} 条",
            "key_points": [
                {
                    "title": n.get("title", ""),
                    "source": n.get("source", ""),
                    "tendency": "中性",
                }
                for n in news[:5]
            ],
        }


if __name__ == "__main__":
    analyzer = NewsSentimentAnalyzer()
    result = analyzer.analyze_variety("p", "棕榈油", days=7)
    print(f"✅ 新闻数量: {result['news_count']}")
    print(f"✅ 摘要: {result['summary']}")
    for n in result["news"][:5]:
        print(f"- [{n.get('source','')}] {n.get('title','')}")
