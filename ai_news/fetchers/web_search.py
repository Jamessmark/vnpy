#!/usr/bin/env python3
"""
网页搜索工具 - 基于 DuckDuckGo
支持网页、新闻、图片、视频搜索，可本地直接调用

用法：
    uv run python ai_news/fetchers/web_search.py "crude oil OPEC" --type news --time-range d
    uv run python ai_news/fetchers/web_search.py "螺纹钢 期货" --type news --region cn-zh
    uv run python ai_news/fetchers/web_search.py "Fed interest rate" --type news --format json

依赖：uv add ddgs
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ddgs import DDGS
    _USE_DDGS = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        _USE_DDGS = False
    except ImportError as e:
        print(f"Error: Missing required dependency: {e}", file=sys.stderr)
        print("Install with: uv add ddgs", file=sys.stderr)
        sys.exit(1)


class WebSearch:
    """使用 DuckDuckGo 进行网页搜索。"""

    def __init__(
        self,
        region: str = "wt-wt",
        safe_search: str = "moderate",
        timeout: int = 20,
    ):
        self.region = region
        self.safe_search = safe_search
        self.timeout = timeout

    def _ddgs(self):
        return DDGS()

    def search_text(
        self,
        query: str,
        max_results: int = 10,
        time_range: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """网页搜索。time_range: d/w/m/y"""
        try:
            return list(self._ddgs().text(
                query,
                region=self.region,
                safesearch=self.safe_search,
                timelimit=time_range,
                max_results=max_results,
            ))
        except Exception as e:
            print(f"搜索失败: {e}", file=sys.stderr)
            return []

    def search_news(
        self,
        query: str,
        max_results: int = 10,
        time_range: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """新闻搜索。返回字段：title, url, body, date, source"""
        try:
            return list(self._ddgs().news(
                query,
                region=self.region,
                safesearch=self.safe_search,
                timelimit=time_range,
                max_results=max_results,
            ))
        except Exception as e:
            print(f"新闻搜索失败: {e}", file=sys.stderr)
            return []

    def search_images(
        self,
        query: str,
        max_results: int = 10,
        size: Optional[str] = None,
        color: Optional[str] = None,
        type_image: Optional[str] = None,
        layout: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """图片搜索。"""
        try:
            return list(self._ddgs().images(
                query,
                region=self.region,
                safesearch=self.safe_search,
                size=size,
                color=color,
                type_image=type_image,
                layout=layout,
                max_results=max_results,
            ))
        except Exception as e:
            print(f"图片搜索失败: {e}", file=sys.stderr)
            return []

    def search_videos(
        self,
        query: str,
        max_results: int = 10,
        duration: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """视频搜索。"""
        try:
            return list(self._ddgs().videos(
                query,
                region=self.region,
                safesearch=self.safe_search,
                duration=duration,
                resolution=resolution,
                max_results=max_results,
            ))
        except Exception as e:
            print(f"视频搜索失败: {e}", file=sys.stderr)
            return []


# ── 格式化输出 ────────────────────────────────────────────────────

def _fmt(results: List[Dict], format_type: str, fields: dict) -> str:
    if not results:
        return "未找到结果。"
    if format_type == "json":
        return json.dumps(results, indent=2, ensure_ascii=False)
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "无标题")
        url   = r.get(fields.get("url", "href"), r.get("href", r.get("url", "")))
        body  = r.get(fields.get("body", "body"), "")
        meta  = " | ".join(str(r.get(k, "")) for k in fields.get("meta", []) if r.get(k))
        if format_type == "markdown":
            lines.append(f"## {i}. {title}")
            if meta:  lines.append(f"*{meta}*")
            lines.append(f"**URL:** {url}")
            if body:  lines.append(body)
            lines.append("")
        else:
            lines.append(f"{i}. {title}")
            if meta:  lines.append(f"   {meta}")
            lines.append(f"   {url}")
            if body:  lines.append(f"   {body[:120]}")
            lines.append("")
    return "\n".join(lines)

def format_web(results, fmt):
    return _fmt(results, fmt, {"url": "href", "body": "body", "meta": []})

def format_news(results, fmt):
    return _fmt(results, fmt, {"url": "url", "body": "body", "meta": ["source", "date"]})

def format_images(results, fmt):
    return _fmt(results, fmt, {"url": "image", "body": "", "meta": ["source"]})

def format_videos(results, fmt):
    return _fmt(results, fmt, {"url": "content", "body": "description", "meta": ["publisher", "duration"]})


def main():
    parser = argparse.ArgumentParser(
        description="DuckDuckGo 网页搜索工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  uv run python ai_news/fetchers/web_search.py "crude oil OPEC" --type news --time-range d
  uv run python ai_news/fetchers/web_search.py "螺纹钢 期货" --type news --region cn-zh
  uv run python ai_news/fetchers/web_search.py "Fed Powell" --type news --format json -n 20

时间范围 (--time-range):  d=今天  w=本周  m=本月  y=今年
        """
    )

    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("-t", "--type", choices=["web", "news", "images", "videos"], default="web")
    parser.add_argument("-n", "--max-results", type=int, default=10)
    parser.add_argument("--time-range", choices=["d", "w", "m", "y"])
    parser.add_argument("-r", "--region", default="wt-wt",
                        help="地区代码: wt-wt(全球) us-en cn-zh uk-en (默认: wt-wt)")
    parser.add_argument("--safe-search", choices=["on", "moderate", "off"], default="moderate")
    parser.add_argument("-f", "--format", choices=["text", "markdown", "json"], default="text")
    parser.add_argument("-o", "--output", help="输出到文件（不指定则打印到控制台）")

    # 图片专用
    parser.add_argument("--image-size", choices=["Small", "Medium", "Large", "Wallpaper"])
    parser.add_argument("--image-color")
    parser.add_argument("--image-type", choices=["photo", "clipart", "gif", "transparent", "line"])
    parser.add_argument("--image-layout", choices=["Square", "Tall", "Wide"])

    # 视频专用
    parser.add_argument("--video-duration", choices=["short", "medium", "long"])
    parser.add_argument("--video-resolution", choices=["high", "standard"])

    args = parser.parse_args()

    searcher = WebSearch(region=args.region, safe_search=args.safe_search)

    time_label = {"d": "今天", "w": "本周", "m": "本月", "y": "今年"}.get(args.time_range or "", "不限")
    print(f"🔍 搜索: {args.query}  类型: {args.type}  时间: {time_label}  数量: {args.max_results}", file=sys.stderr)

    results, formatter = [], format_web
    if args.type == "web":
        results = searcher.search_text(args.query, args.max_results, args.time_range)
        formatter = format_web
    elif args.type == "news":
        results = searcher.search_news(args.query, args.max_results, args.time_range)
        formatter = format_news
    elif args.type == "images":
        results = searcher.search_images(args.query, args.max_results,
                                         args.image_size, args.image_color,
                                         args.image_type, args.image_layout)
        formatter = format_images
    elif args.type == "videos":
        results = searcher.search_videos(args.query, args.max_results,
                                         args.video_duration, args.video_resolution)
        formatter = format_videos

    output = formatter(results, args.format)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"✓ 已保存至 {args.output}，共 {len(results)} 条结果", file=sys.stderr)
    else:
        print(output)
        print(f"\n共 {len(results)} 条结果", file=sys.stderr)


if __name__ == "__main__":
    main()
