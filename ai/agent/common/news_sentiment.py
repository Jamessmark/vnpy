"""
新闻获取与情绪分析模块（东方财富资讯搜索 API）

说明：
- 使用东方财富 finskillshub 资讯搜索 API（需要 EASTMONEY_APIKEY）。
- API Key 从项目根目录 .env 文件读取（EASTMONEY_APIKEY=mkt_xxx）。
- 不做多空推断：统一返回中性分数，仅提供真实新闻内容供下游分析。
- 保留 `NewsSentimentAnalyzer` 兼容接口，避免旧代码导入失败。
"""

import json
import os
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# 工具：读取 .env
# ---------------------------------------------------------------------------

def _load_env() -> Dict[str, str]:
    """从项目根目录 .env 加载环境变量（不覆盖已有的系统环境变量）"""
    env: Dict[str, str] = {}
    root = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = root / ".env"
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        env[k.strip()] = v.strip()
            break
        root = root.parent
    return env


_ENV = _load_env()


def _get_api_keys() -> list:
    """返回所有可用的 API Key 列表（优先读 EASTMONEY_APIKEY1/2，兼容旧 EASTMONEY_APIKEY）"""
    keys = []
    for k in ("EASTMONEY_APIKEY1", "EASTMONEY_APIKEY2", "EASTMONEY_APIKEY"):
        v = os.environ.get(k) or _ENV.get(k)
        if v and v not in keys:
            keys.append(v)
    return keys


# ---------------------------------------------------------------------------
# 工具：时间过滤
# ---------------------------------------------------------------------------

def _filter_by_days(items: List[Dict], days: int) -> List[Dict]:
    """按发布时间过滤，days=0 表示不过滤"""
    if days <= 0:
        return items
    cutoff = datetime.now() - timedelta(days=days)
    out: List[Dict] = []
    for it in items:
        pt = it.get("publish_time")
        if not pt:
            out.append(it)
            continue
        try:
            dt = datetime.strptime(str(pt)[:19], "%Y-%m-%d %H:%M:%S")
            if dt >= cutoff:
                out.append(it)
        except Exception:
            out.append(it)
    return out


# ---------------------------------------------------------------------------
# 东方财富资讯搜索抓取器
# ---------------------------------------------------------------------------

class NewsFetcher:
    """
    东方财富 finskillshub 资讯搜索抓取器。

    接口：POST https://mkapi2.dfcfs.com/finskillshub/api/claw/news-search
    响应路径：data.data.llmSearchResponse.data[]
    字段：title / content / date / insName（来源机构）/ informationType
    """

    _API_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/news-search"

    def __init__(self, timeout: int = 15):
        self._timeout  = timeout
        self._api_keys = _get_api_keys()
        self._key_idx  = 0  # 轮询指针

    def _next_key(self) -> Optional[str]:
        """轮流返回下一个 API Key"""
        if not self._api_keys:
            return None
        key = self._api_keys[self._key_idx % len(self._api_keys)]
        self._key_idx += 1
        return key

    def fetch_news(self, keyword: str, days: int = 30, max_results: int = 20, request_interval: float = 0.0) -> List[Dict]:
        """搜索新闻/研报并返回结构化结果列表（轮询 API Key）"""
        api_key = self._next_key()
        if not api_key:
            print("⚠️ 未配置 EASTMONEY_APIKEY，无法获取东方财富新闻")
            return []

        if request_interval > 0:
            time.sleep(request_interval)

        payload = json.dumps({"query": keyword}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self._API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "apikey": api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"⚠️ 东方财富 API 请求失败: {e}")
            return []

        try:
            data = json.loads(raw)
            d1 = data.get("data") or {}
            d2 = d1.get("data") or {}
            d3 = d2.get("llmSearchResponse") or {}
            items_raw = d3.get("data") or []
        except Exception as e:
            print(f"⚠️ 东方财富 API 响应解析失败: {e}")
            return []

        items: List[Dict] = []
        for it in items_raw[:max_results]:
            date_str = it.get("date", "")
            # 统一为 "YYYY-MM-DD HH:MM:SS" 格式
            publish_time = date_str[:19].replace("T", " ") if date_str else None

            items.append({
                "title": it.get("title", "").strip(),
                "content": it.get("content", "").strip()[:300],
                "publish_time": publish_time,
                "url": it.get("url", ""),
                "source": it.get("insName", "东方财富"),
                "info_type": it.get("informationType", ""),
            })

        if days > 0:
            items = _filter_by_days(items, days)

        return items


# ---------------------------------------------------------------------------
# NewsSentimentAnalyzer（兼容旧接口）
# ---------------------------------------------------------------------------

class NewsSentimentAnalyzer:
    """
    兼容旧接口：run.py 仍导入该类。

    不做多空判断，仅返回真实新闻内容；情绪字段返回中性占位，供下游使用。
    """

    def __init__(self):
        self._fetcher = NewsFetcher()

    def analyze_variety(self, variety: str, variety_name: str, days: int = 30) -> Dict:
        keyword = f"{variety_name}期货"
        news = self._fetcher.fetch_news(keyword, days=days, max_results=20)

        return {
            "variety": variety,
            "variety_name": variety_name,
            "news": news,
            "news_count": len(news),
            "sentiment_score": 0.0,
            "sentiment_label": "中性",
            "summary": f"共获取 {len(news)} 条资讯（东方财富）",
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
    result = analyzer.analyze_variety("p", "棕榈油", days=30)
    print(f"✅ 新闻数量: {result['news_count']}")
    print(f"✅ 摘要: {result['summary']}")
    for n in result["news"][:10]:
        print(f"- [{n.get('publish_time', '')[:10]}][{n.get('source', '')}] {n.get('title', '')}")
