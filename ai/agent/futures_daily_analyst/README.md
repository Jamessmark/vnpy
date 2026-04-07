# 期货每日执行计划 Agent

## 方案概述

每天下午 17:00 自动运行，综合**行情数据 + 新闻资讯**，由 LLM 生成当日期货操作建议。

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    scheduler.py（定时触发）                    │
│                    每天 17:00 执行 run_agent()                │
└──────────────────────────┬──────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐
    │ data_loader │ │ news_fetcher│ │   report_generator  │
    │             │ │             │ │                     │
    │ 从 vnpy DB  │ │ DuckDuckGo  │ │  LLM (OpenAI)       │
    │ 取最近7天   │ │ 新闻搜索    │ │  生成 Markdown 报告  │
    │ 日K线数据   │ │ + RSS 摘要  │ │  含操作建议          │
    └──────┬──────┘ └──────┬──────┘ └──────────┬──────────┘
           │               │                    │
           └───────────────┴────────────────────┘
                                   │
                           ┌───────▼────────┐
                           │  reports/ 目录  │
                           │  YYYYMMDD.md   │
                           └────────────────┘
```

---

## 监控品种

| 品种 | 主连合约 | 交易所 |
|------|---------|--------|
| 甲醇 | MA888   | LOCAL  |
| 聚乙烯（LLDPE）| L888 | LOCAL |
| 生猪 | LH888   | LOCAL  |

---

## 新闻搜索关键词

| 主题 | 关键词 |
|------|--------|
| 石油 | crude oil OPEC 原油 WTI Brent 油价 |
| 化工 | 甲醇 化工品 methanol 乙烯 聚乙烯 化工市场 |
| 美伊局势 | 美伊战争 Iran US sanctions 伊朗制裁 中东局势 |

---

## 数据流程

### Step 1：K 线数据加载
- 调用 `vnpy.trader.database.get_database()` 加载数据库
- 品种：MA888.LOCAL / L888.LOCAL / LH888.LOCAL（主连数据存储于 LOCAL 交易所）
- 区间：近 7 个交易日
- 提取：日期、开/高/低/收、成交量、持仓量
- 计算衍生指标：5日涨跌幅、振幅、成交量均值偏离

### Step 2：新闻获取
- 使用 `ai/news/fetchers/web_search.py` 的 `WebSearch` 类
- 搜索引擎：DuckDuckGo news API
- 时间范围：最近 1 天（`time_range="d"`）
- 每个主题取前 5 条，共 3 个主题
- 提取：标题、来源、时间、摘要

### Step 3：LLM 报告生成
- 模型：gpt-4o-mini（可配置）
- 输入：K 线数据摘要 + 新闻列表
- 输出：Markdown 格式操作建议
- 报告结构：
  ```
  # 期货每日执行计划 [日期]
  ## 一、市场行情概览
  ## 二、重要新闻摘要
  ## 三、品种分析与建议
    ### 甲醇（MA）
    ### 聚乙烯（L）
    ### 生猪（LH）
  ## 四、风险提示
  ```

### Step 4：报告保存
- 路径：`ai/agent/futures_daily_analyst/reports/YYYYMMDD.md`
- 同时打印到控制台

---

## 文件结构

```
ai/agent/futures_daily_analyst/
├── README.md              ← 本文件
├── run.py                 ← 主入口（单次运行 / 定时调度）
├── data_loader.py         ← K 线数据加载模块
├── news_fetcher.py        ← 新闻搜索模块
├── report_generator.py    ← LLM 报告生成模块
├── config.py              ← 配置（品种、关键词、LLM 参数）
└── reports/               ← 自动生成的报告目录
    └── YYYYMMDD.md
```

---

## 运行方式

```bash
# 单次立即运行
uv run python ai/agent/futures_daily_analyst/run.py

# 定时运行（每天 17:00）
uv run python ai/agent/futures_daily_analyst/run.py --schedule

# 指定日期（调试用）
uv run python ai/agent/futures_daily_analyst/run.py --date 2026-04-06
```

---

## 依赖

- `vnpy`（已安装）：读取数据库 K 线
- `ddgs`（已安装）：DuckDuckGo 新闻搜索
- `openai`（已安装）：LLM 报告生成
- `schedule`：定时任务（需安装）

```bash
uv add schedule
```

> LLM 调用使用 CodeFlicker 运行环境提供的 OpenAI Key，无需手动配置。
