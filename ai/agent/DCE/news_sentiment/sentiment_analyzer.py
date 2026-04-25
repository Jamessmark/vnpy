"""
新闻情绪分析器
从东方财富等渠道获取新闻，并使用LLM分析情绪
"""
import re
import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup


class NewsSentimentAnalyzer:
    """新闻情绪分析器"""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36"
        }
    
    def fetch_eastmoney_news(
        self,
        keyword: str,
        days: int = 7
    ) -> List[Dict]:
        """
        从东方财富获取新闻
        
        Args:
            keyword: 搜索关键词（如"豆粕"、"铁矿石"）
            days: 最近N天的新闻
        
        Returns:
            新闻列表 [{"title": str, "content": str, "publish_time": datetime, "url": str}]
        """
        news_list = []
        
        try:
            # 东方财富期货新闻列表页
            # 注意：实际URL可能需要调整
            search_url = f"https://so.eastmoney.com/news/s?keyword={keyword}"
            
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 解析新闻列表（示例，实际选择器需要根据页面结构调整）
            news_items = soup.select('.news-item')  # 需要根据实际页面调整
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for item in news_items[:20]:  # 最多取20条
                try:
                    title_elem = item.select_one('.news-title')
                    time_elem = item.select_one('.news-time')
                    link_elem = item.select_one('a')
                    
                    if not (title_elem and time_elem and link_elem):
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    url = link_elem.get('href', '')
                    time_text = time_elem.get_text(strip=True)
                    
                    # 解析时间
                    publish_time = self._parse_time(time_text)
                    
                    if publish_time < cutoff_date:
                        break
                    
                    # 获取新闻正文（可选）
                    content = self._fetch_article_content(url)
                    
                    news_list.append({
                        "title": title,
                        "content": content,
                        "publish_time": publish_time,
                        "url": url,
                        "source": "东方财富"
                    })
                    
                    time.sleep(0.5)  # 避免请求过快
                    
                except Exception as e:
                    print(f"  解析新闻失败: {e}")
                    continue
        
        except Exception as e:
            print(f"❌ 获取新闻失败: {e}")
        
        return news_list
    
    def _fetch_article_content(self, url: str) -> str:
        """获取新闻正文（简化版）"""
        try:
            if not url or not url.startswith('http'):
                return ""
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 移除脚本和样式
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 提取正文（需要根据实际页面调整选择器）
            content_elem = soup.select_one('.article-content, .news-content, article')
            
            if content_elem:
                content = content_elem.get_text(separator='\n', strip=True)
                # 限制长度
                return content[:2000]
            
            return ""
        
        except Exception:
            return ""
    
    def _parse_time(self, time_text: str) -> datetime:
        """解析时间文本"""
        now = datetime.now()
        
        # 处理相对时间（如"2小时前"、"昨天"）
        if '分钟前' in time_text:
            minutes = int(re.search(r'(\d+)', time_text).group(1))
            return now - timedelta(minutes=minutes)
        elif '小时前' in time_text:
            hours = int(re.search(r'(\d+)', time_text).group(1))
            return now - timedelta(hours=hours)
        elif '昨天' in time_text:
            return now - timedelta(days=1)
        elif '前天' in time_text:
            return now - timedelta(days=2)
        else:
            # 尝试解析绝对时间
            try:
                return datetime.strptime(time_text, "%Y-%m-%d %H:%M")
            except:
                try:
                    return datetime.strptime(time_text, "%m-%d %H:%M")
                except:
                    return now
    
    def analyze_sentiment_with_llm(
        self,
        news_list: List[Dict],
        variety: str
    ) -> Dict:
        """
        使用LLM分析新闻情绪（简化版）
        
        Args:
            news_list: 新闻列表
            variety: 品种名称
        
        Returns:
            情绪分析结果
        """
        if not news_list:
            return {
                "sentiment_score": 0,  # -1到1之间
                "sentiment_label": "中性",
                "key_points": [],
                "summary": "未找到相关新闻"
            }
        
        # 简化版：基于关键词打分
        # 实际应该调用 OpenAI/Claude 等 LLM API
        
        positive_keywords = ["上涨", "突破", "利好", "增长", "强势", "看多", "反弹"]
        negative_keywords = ["下跌", "破位", "利空", "下滑", "疲软", "看空", "回调"]
        
        score = 0
        key_points = []
        
        for news in news_list[:10]:  # 只分析前10条
            title = news.get("title", "")
            content = news.get("content", "")
            text = title + " " + content
            
            # 计算正负面关键词出现次数
            pos_count = sum(1 for kw in positive_keywords if kw in text)
            neg_count = sum(1 for kw in negative_keywords if kw in text)
            
            score += (pos_count - neg_count)
            
            # 提取关键信息
            if pos_count > 0 or neg_count > 0:
                key_points.append({
                    "title": title,
                    "time": news.get("publish_time"),
                    "tendency": "利多" if pos_count > neg_count else "利空"
                })
        
        # 归一化分数到 [-1, 1]
        if score > 5:
            score = 1.0
        elif score < -5:
            score = -1.0
        else:
            score = score / 5.0
        
        # 判断情绪标签
        if score > 0.3:
            label = "偏多"
        elif score < -0.3:
            label = "偏空"
        else:
            label = "中性"
        
        summary = f"分析了{len(news_list)}条新闻，整体情绪{label}（得分: {score:.2f}）"
        
        return {
            "sentiment_score": score,
            "sentiment_label": label,
            "key_points": key_points[:5],  # 最多5个关键点
            "summary": summary,
            "news_count": len(news_list)
        }
    
    def analyze_variety(
        self,
        variety: str,
        variety_name: str,
        days: int = 7
    ) -> Dict:
        """
        分析某品种的新闻情绪
        
        Args:
            variety: 品种代码（如"a"）
            variety_name: 品种名称（如"豆一"）
            days: 分析最近N天的新闻
        
        Returns:
            分析结果
        """
        print(f"📰 获取 {variety_name} 新闻...")
        news_list = self.fetch_eastmoney_news(variety_name, days)
        
        print(f"🤖 分析新闻情绪...")
        sentiment = self.analyze_sentiment_with_llm(news_list, variety_name)
        
        return {
            "variety": variety,
            "variety_name": variety_name,
            "news": news_list,
            **sentiment
        }


# 品种名称映射
VARIETY_NAMES = {
    "a": "豆一",
    "b": "豆二",
    "c": "玉米",
    "cs": "玉米淀粉",
    "m": "豆粕",
    "y": "豆油",
    "p": "棕榈油",
    "jd": "鸡蛋",
    "l": "塑料",
    "v": "PVC",
    "pp": "聚丙烯",
    "j": "焦炭",
    "jm": "焦煤",
    "i": "铁矿石",
    "eg": "乙二醇",
    "eb": "苯乙烯",
    "pg": "液化石油气",
}


if __name__ == "__main__":
    # 测试
    analyzer = NewsSentimentAnalyzer()
    
    result = analyzer.analyze_variety("m", "豆粕", days=7)
    
    print(f"\n✅ {result['variety_name']} 情绪分析完成")
    print(f"  情绪标签: {result['sentiment_label']}")
    print(f"  情绪得分: {result['sentiment_score']:.2f}")
    print(f"  新闻数量: {result['news_count']}")
    print(f"  摘要: {result['summary']}")
