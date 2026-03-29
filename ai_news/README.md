# 新闻情绪分析辅助交易策略方案

## 一、方案概述

通过定时抓取 Google News / BBC RSS 新闻，调用 LLM API 对新闻进行情绪分析，生成结构化的情绪信号，供 VeighNa 量化策略读取并辅助交易决策。

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────┐
│                    新闻数据层                         │
│  Google News RSS（按关键词搜索）                       │
│  BBC RSS（世界/商业/科技）                             │
└────────────────────┬────────────────────────────────┘
                     │ 每 5 分钟拉取一次
                     ▼
┌─────────────────────────────────────────────────────┐
│                    情绪分析层                         │
│  LLM API（GPT-4o-mini）                              │
│  输入：新闻标题 + 摘要                                │
│  输出：情绪分数（-1 ~ +1）+ 相关品种 + 简要理由        │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│                    信号存储层                         │
│  SQLite 数据库（本地）                                │
│  字段：时间、标题、情绪分数、相关品种、置信度、原文链接  │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│                    策略决策层                         │
│  VeighNa CTA/组合策略                                │
│  读取情绪信号，结合技术指标过滤，决定是否开平仓          │
└─────────────────────────────────────────────────────┘
```

---

## 三、关注品种与关键词映射

| 品种 | VeighNa 合约 | 关键词（Google News 搜索） |
|------|-------------|--------------------------|
| 股指期货 | IF.CFFEX、IC.CFFEX | `"China stock" OR "CSI 300" OR "A-share"` |
| 原油 | SC.INE | `"crude oil" OR "OPEC" OR "Middle East"` |
| 黄金 | AU.SHFE | `"gold price" OR "Fed rate" OR "inflation"` |
| 铜 | CU.SHFE | `"copper" OR "China demand" OR "manufacturing"` |

---

## 四、模块设计

### 4.1 新闻抓取模块（`fetcher.py`）

- 定时（每 5 分钟）请求 RSS URL
- 去重（通过新闻链接/标题 hash 过滤已处理的条目）
- 按发布时间过滤（只处理最近 30 分钟内的新闻）
- 输出：`List[NewsItem]`

```python
# 数据结构示意
@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    published_at: datetime
    source: str  # "bbc" / "google_news"
    keyword: str  # 命中的关键词
```

### 4.2 情绪分析模块（`analyzer.py`）

- 调用 LLM API，每次批量传入 5-10 条新闻
- Prompt 设计：让模型返回 JSON 格式，包含分数和原因
- 输出：`SentimentResult`

**Prompt 示例：**
```
你是一名专业的金融新闻分析师。分析以下新闻对 {品种} 价格的情绪影响。

新闻列表：
1. {title1} - {summary1}
2. {title2} - {summary2}

对每条新闻返回 JSON：
{
  "score": -1.0 到 1.0,  // 负数看空，正数看多
  "confidence": 0 到 1,  // 置信度
  "reason": "简要说明"
}
```

### 4.3 信号存储模块（`storage.py`）

- 写入 SQLite 数据库 `news_sentiment.db`
- 提供查询接口：按品种、时间范围查询聚合情绪分数

**数据库表结构：**
```sql
CREATE TABLE sentiment_signals (
    id          INTEGER PRIMARY KEY,
    created_at  DATETIME,
    published_at DATETIME,
    title       TEXT,
    url         TEXT UNIQUE,
    source      TEXT,
    keyword     TEXT,
    symbol      TEXT,      -- 相关品种，如 "AU.SHFE"
    score       REAL,      -- 情绪分数 -1 ~ 1
    confidence  REAL,      -- 置信度 0 ~ 1
    reason      TEXT       -- LLM 给出的理由
);
```

### 4.4 策略集成模块（`signal_reader.py`）

提供给 VeighNa 策略调用的接口：

```python
def get_latest_sentiment(symbol: str, minutes: int = 60) -> float:
    """
    获取指定品种最近 N 分钟的加权平均情绪分数
    返回 -1 ~ 1 之间的浮点数
    """
```

### 4.5 主调度程序（`main.py`）

- 使用 `APScheduler` 每 5 分钟执行一次抓取 + 分析
- 日志记录
- 异常自动重试

---

## 五、VeighNa 策略集成方式

推荐将情绪信号作为**过滤器**，而非独立信号，避免误操作：

```python
class AuSentimentStrategy(CtaTemplate):
    """黄金情绪辅助策略"""

    def on_bar(self, bar: BarData):
        # 1. 技术指标计算（如均线）
        fast_ma = self.am.sma(10)
        slow_ma = self.am.sma(20)

        # 2. 读取情绪信号
        sentiment = get_latest_sentiment("AU.SHFE", minutes=60)

        # 3. 只有情绪与技术方向一致时才开仓
        if fast_ma > slow_ma and sentiment > 0.3:
            self.buy(bar.close_price, 1)   # 技术多头 + 情绪偏多 → 买入
        elif fast_ma < slow_ma and sentiment < -0.3:
            self.sell(bar.close_price, 1)  # 技术空头 + 情绪偏空 → 卖出
```

---

## 六、文件结构

```
news_sentiment/
├── README.md           # 本文档
├── main.py             # 主调度程序（定时运行）
├── fetcher.py          # 新闻抓取模块
├── analyzer.py         # LLM 情绪分析模块
├── storage.py          # SQLite 数据存储
├── signal_reader.py    # 供 VeighNa 策略调用的信号接口
├── config.py           # 配置（关键词、品种映射、API 参数）
└── strategies/
    └── au_sentiment_strategy.py  # 示例：黄金情绪策略
```

---

## 七、依赖

```
feedparser       # RSS 解析
openai           # LLM API 调用
apscheduler      # 定时任务
python-dotenv    # 读取 .env 配置
```

---

## 八、待确认事项

- [ ] 使用的 LLM API 提供商（OpenAI / DeepSeek / 其他）
- [ ] 关注的核心品种（股指 / 原油 / 黄金 / 铜）
- [ ] 情绪信号的使用方式（过滤器 / 仓位调节 / 独立信号）
- [ ] 是否需要情绪信号的可视化看板
- [ ] 是否需要历史回测（用历史新闻验证信号有效性）
