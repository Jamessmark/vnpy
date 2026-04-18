# 大商所数据驱动的AI决策系统（无回测版）

## 1. 项目目标

**核心理念**：不做模型训练和回测，直接用Alpha158特征值 + 基本面数据 + 新闻情绪 → 大模型综合决策

### 1.1 简化架构

```
┌─────────────────────────────────────────────────────┐
│            DCE AI 决策系统（无回测版）                 │
└─────────────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬──────────────┐
        ▼             ▼             ▼              ▼
   ┌────────┐   ┌────────┐   ┌─────────┐   ┌──────────┐
   │数据采集│   │因子计算│   │新闻情绪 │   │LLM决策   │
   │ DCE API│   │Alpha158│   │RSS/搜索 │   │生成报告  │
   └────┬───┘   └───┬────┘   └────┬────┘   └─────┬────┘
        │           │             │              │
        └───────────┴─────────────┴──────────────┘
                             │
                      ┌──────▼──────┐
                      │ 决策报告.md │
                      └─────────────┘
```

---

## 2. 数据需求（最小化）

### 2.1 时长需求

```
Alpha158 最长窗口: 60天（ts_mean/ts_std等60日指标）
大模型分析窗口: 最近7-30天的趋势
─────────────────────────────────────────────────
推荐数据范围: 2025-11-01 ~ 2026-04-19（约100个交易日）
```

| 数据类型 | 历史深度 | 数据量 |
|---------|---------|--------|
| 日K线 | 100天 | 每品种1-2MB，共50MB |
| 仓单数据 | 30天 | <5MB |
| 会员排名 | 30天 | <10MB |
| 新闻 | 最近1天 | 实时抓取 |

### 2.2 每日运行流程

```python
# 每天17:00运行
1. 增量下载当日数据（日K线 + 仓单 + 会员排名）
2. 计算全品种Alpha158特征（基于最近100天数据）
3. 提取最近7天的因子趋势
4. 抓取当日新闻并打分
5. 融合数据 → LLM生成报告
```

---

## 3. 数据采集层

### 3.1 合约数据结构设计 ⚠️ **核心架构**

#### 数据输出要求

**每个品种输出4种数据文件**（参考 `ai/data_process/build_main_contract.py` 架构）：

| 文件类型 | Symbol格式 | 说明 | 用途 |
|---------|-----------|------|------|
| **旧主力合约** | `a2505.parquet` | 上一个主力合约（无数据则去掉） | 历史回溯分析 |
| **新主力合约** | `a2507.parquet` | 当前主力合约 | 实盘交易参考 |
| **次主力合约** | `a2509.parquet` | 次主力合约 | 主力切换预判 |
| **加权合成合约** | `a888.parquet` | **旧主力+新主力+次主力**加权合成 | **Alpha158计算** ⭐ |

**加权合成规则**（参考 `_weighted_bar` 函数）：
```python
# 包含3个合约：旧主力（如有数据）+ 新主力 + 次主力
contracts = [old_main, new_main, sub_main]  # 旧主力无数据时自动过滤

# 价格：按成交量加权
total_volume = sum(c.volume for c in contracts)
if total_volume > 0:
    weighted_close = sum(c.close * c.volume for c in contracts) / total_volume
    weighted_high = sum(c.high * c.volume for c in contracts) / total_volume
    weighted_low = sum(c.low * c.volume for c in contracts) / total_volume
    weighted_open = sum(c.open * c.volume for c in contracts) / total_volume
else:
    # 成交量为0（罕见），简单均价
    weighted_close = sum(c.close for c in contracts) / len(contracts)

# 量能：直接求和（3个合约的量能相加）
total_volume = sum(c.volume for c in contracts)
total_open_interest = sum(c.open_interest for c in contracts)
total_turnover = sum(c.turnover for c in contracts)
```

#### 主力合约识别规则（平滑换月机制）

参考 `build_dominant_mapping()` 函数逻辑：

```python
def identify_main_and_sub(variety: str, date: str, all_contracts: list) -> tuple[str, str]:
    """
    识别主力和次主力合约（带平滑机制）
    
    平滑规则：
    1. 主力合约：连续5天持仓量第一，才触发切换
    2. 次主力合约：连续5天持仓量第二，才触发切换
    3. 强制保护：主力和次主力绝对不能是同一个合约
    
    Args:
        variety: 品种代码（如"a"）
        date: 交易日（"20260419"）
        all_contracts: 当日所有合约列表 [{symbol, open_interest, ...}]
    
    Returns:
        (主力合约symbol, 次主力合约symbol)
    """
    # 按持仓量降序排序
    sorted_contracts = sorted(
        all_contracts, 
        key=lambda x: x['open_interest'], 
        reverse=True
    )
    
    # 实时第一名和第二名
    real_main = sorted_contracts[0]['symbol']
    real_sub = sorted_contracts[1]['symbol'] if len(sorted_contracts) > 1 else real_main
    
    # 平滑计数器（从数据库或缓存读取）
    pending_main_count = get_pending_count(variety, real_main, 'main')
    pending_sub_count = get_pending_count(variety, real_sub, 'sub')
    
    # 当前平滑主力
    current_main = get_current_main(variety)
    current_sub = get_current_sub(variety)
    
    # 判断主力是否切换
    if real_main == current_main:
        # 持续领先，重置计数
        reset_pending_count(variety, 'main')
    elif pending_main_count + 1 >= 5:  # 连续5天
        # 触发切换
        current_main = real_main
        reset_pending_count(variety, 'main')
        log_switch(variety, date, 'main', real_main)
    else:
        # 累加计数
        increment_pending_count(variety, real_main, 'main')
    
    # 判断次主力是否切换（同理）
    if real_sub == current_sub:
        reset_pending_count(variety, 'sub')
    elif real_sub == current_main:
        # 如果次主力其实是当前主力，不切换
        reset_pending_count(variety, 'sub')
    elif pending_sub_count + 1 >= 5:
        current_sub = real_sub
        reset_pending_count(variety, 'sub')
    else:
        increment_pending_count(variety, real_sub, 'sub')
    
    # 强制保护
    if current_sub == current_main and len(sorted_contracts) > 1:
        current_sub = real_sub
    
    return current_main, current_sub
```

#### 主力映射表持久化（SQLite）

**数据库路径**: `data/dce/main_contract_mapping.db`

**表结构**:
```sql
CREATE TABLE main_contract_mapping (
    product        TEXT NOT NULL,     -- 品种前缀（如"a"）
    exchange       TEXT NOT NULL,     -- 交易所（"DCE"）
    trade_date     TEXT NOT NULL,     -- 交易日（"2026-04-19"）
    dominant       TEXT NOT NULL,     -- 主力合约（"a2507"）
    sub_dominant   TEXT,              -- 次主力合约（"a2509"）
    open_interest  REAL NOT NULL,     -- 主力合约持仓量
    PRIMARY KEY (product, exchange, trade_date)
);
```

**核心查询接口**（参考 `MappingStore` 类）:

```python
class DCEMappingStore:
    """主力合约映射表的 SQLite 持久化层"""
    
    def save_mapping(self, variety: str, date: str, main: str, sub: str, oi: float):
        """保存某天的主力映射"""
        pass
    
    def get_dominant(self, variety: str, date: str) -> str:
        """查询某天的主力合约"""
        pass
    
    def get_switches(self, variety: str) -> list[dict]:
        """返回该品种所有换月节点"""
        # [{"date": "2026-04-16", "dominant": "a2507"}]
        pass
    
    def get_latest_date(self, variety: str) -> str:
        """返回该品种映射表中最新的交易日"""
        pass
```

### 3.2 DCE API 采集器

**文件**: `ai/agent/DCE/data_collector/dce_collector.py`

#### 采集内容

| 接口 | 数据 | 更新频率 | 用途 |
|------|------|---------|------|
| `dayQuotes` | **全部合约**日K线（OHLCV+持仓量） | 每日 | 主力/次主力识别 + 加权合成 |
| `wbillWeeklyQuotes` | 仓单日报 | 每日 | 基本面分析 |
| `memberDealPosi` | 会员排名 | 每日 | 机构动向 |
| `dayTradPara` | 交易参数（保证金/手续费） | 变动时 | 风险提示 |

**重要**：必须下载**全部合约**（不能只下载主力），才能动态识别主力和次主力

#### 存储结构

```
data/dce/
  ├── raw_contracts/              # 原始合约数据（全部合约）
  │   ├── a/                      # 豆一
  │   │   ├── a2505.parquet       # 单个合约历史
  │   │   ├── a2507.parquet
  │   │   ├── a2509.parquet
  │   │   └── ...
  │   ├── m/                      # 豆粕
  │   └── ...
  │
  ├── main_contracts/             # ⭐ 4种主力相关合约（参考 build_main_contract.py）
  │   ├── a2505.parquet           # 旧主力（如无数据则不存在）
  │   ├── a2507.parquet           # 新主力（当前主力）
  │   ├── a2509.parquet           # 次主力
  │   ├── a888.parquet            # ⭐ 加权合成（主力+次主力）→ 用于Alpha158
  │   ├── m2507.parquet
  │   ├── m2509.parquet
  │   ├── m2511.parquet
  │   ├── m888.parquet            # ⭐ 加权合成
  │   └── ...
  │
  ├── main_contract_mapping.db    # ⭐ SQLite数据库（主力映射表）
  │   # 表结构：
  │   # product | exchange | trade_date | dominant | sub_dominant | open_interest
  │   # a       | DCE      | 2026-04-19 | a2507    | a2509        | 150000
  │
  ├── warehouse_bill.parquet      # 仓单历史
  ├── member_ranking.parquet      # 会员排名历史
  └── trade_params.parquet        # 交易参数历史
```

**说明**：
- `raw_contracts/`: 保存全部合约原始数据，用于主力识别
- `main_contracts/`: 只保存4种关键合约（旧主力、新主力、次主力、888加权）
- `a888.parquet`: **加权合成合约，用于Alpha158计算**（价格按成交量加权，量能求和）
- `main_contract_mapping.db`: SQLite数据库，记录每日主力和次主力变化

#### 增量更新流程（参考 build_main_contract.py）

```python
def daily_update():
    """
    每日17:00执行的完整流程
    
    核心逻辑：参考 build_main_contract.py 的 process_product() 函数
    """
    
    trade_date = get_latest_trade_date()  # DCE API获取
    
    # Step 1: 下载全部合约日K线
    all_quotes = download_day_quotes(trade_date, varietyId="all")
    
    # Step 2: 按品种分组存储原始数据
    for variety in VARIETIES:
        variety_quotes = all_quotes.filter(pl.col("varietyId") == variety)
        
        # 保存原始合约数据
        for contract in variety_quotes["contractId"].unique():
            contract_data = variety_quotes.filter(pl.col("contractId") == contract)
            append_to_parquet(f"raw_contracts/{variety}/{contract}.parquet", contract_data)
    
    # Step 3: 更新每个品种的主力映射表 + 生成4种合约文件
    mapping_store = DCEMappingStore()  # SQLite数据库连接
    
    for variety in VARIETIES:
        update_main_contracts(variety, trade_date, mapping_store)
    
    # Step 4: 下载基本面数据
    for variety in FOCUS_VARIETIES:  # 重点品种
        warehouse = download_warehouse_bill(trade_date, variety)
        append_to_parquet("warehouse_bill.parquet", warehouse)
    
    # Step 5: 下载会员排名（只下载主力合约）
    for variety in VARIETIES:
        main_contract = mapping_store.get_dominant(variety, "DCE", trade_date)
        ranking = download_member_ranking(trade_date, main_contract)
        append_to_parquet("member_ranking.parquet", ranking)
    
    mapping_store.close()


def update_main_contracts(variety: str, date: str, mapping_store: DCEMappingStore):
    """
    更新品种的主力映射表 + 生成4种合约文件
    
    参考：build_main_contract.py 的 build_dominant_mapping() + build_main_daily_bars()
    """
    
    # 1. 加载当日全部合约数据
    all_contracts = load_contracts(variety, date)
    
    # 2. 识别主力和次主力（带平滑机制）
    new_main, new_sub = identify_main_and_sub(variety, date, all_contracts)
    
    # 3. 获取昨日主力和次主力
    prev_date = get_previous_trade_date(date)
    old_main = mapping_store.get_dominant(variety, "DCE", prev_date)
    old_sub = mapping_store.get_sub_dominant(variety, "DCE", prev_date)
    
    # 4. 保存主力映射到数据库
    mapping_store.save_mapping(
        product=variety,
        exchange="DCE",
        mapping=[{
            "trade_date": date,
            "dominant": new_main,
            "sub_dominant": new_sub,
            "open_interest": all_contracts[new_main]['open_interest']
        }]
    )
    
    # 5. 生成4种合约文件 ⭐
    
    # 5.1 旧主力合约（如果昨日有主力且不等于今日主力）
    if old_main and old_main != new_main and old_main in all_contracts:
        save_contract_data(f"main_contracts/{old_main}.parquet", all_contracts[old_main])
    
    # 5.2 新主力合约
    save_contract_data(f"main_contracts/{new_main}.parquet", all_contracts[new_main])
    
    # 5.3 次主力合约
    if new_sub != new_main:  # 强制保护：主力和次主力不能相同
        save_contract_data(f"main_contracts/{new_sub}.parquet", all_contracts[new_sub])
    
    # 5.4 加权合成合约（888）⭐ 最重要！
    weighted_bar = calculate_weighted_bar(
        variety,
        all_contracts[new_main],
        all_contracts[new_sub]
    )
    save_contract_data(f"main_contracts/{variety}888.parquet", weighted_bar)
    
    # 6. 记录换月日志
    if old_main and new_main != old_main:
        log_switch(variety, date, old_main, new_main)


def calculate_weighted_bar(
    variety: str, 
    old_main_bar: dict | None,  # 旧主力（可能为None）
    new_main_bar: dict,          # 新主力（必须有）
    sub_bar: dict                # 次主力（必须有）
) -> dict:
    """
    计算加权合成K线（参考 `_weighted_bar` 函数）
    
    包含3个合约：旧主力（如有数据） + 新主力 + 次主力
    
    价格：按成交量加权
    量能：直接求和
    """
    # 收集有效合约
    contracts = []
    if old_main_bar and old_main_bar.get('volume', 0) > 0:
        contracts.append(old_main_bar)
    contracts.append(new_main_bar)
    if sub_bar['symbol'] != new_main_bar['symbol']:  # 强制保护：主力次主力不能相同
        contracts.append(sub_bar)
    
    if not contracts:
        raise ValueError("No valid contracts for weighted bar")
    
    total_volume = sum(c['volume'] for c in contracts)
    
    if total_volume > 0:
        weighted_open = sum(c['open'] * c['volume'] for c in contracts) / total_volume
        weighted_high = sum(c['high'] * c['volume'] for c in contracts) / total_volume
        weighted_low = sum(c['low'] * c['volume'] for c in contracts) / total_volume
        weighted_close = sum(c['close'] * c['volume'] for c in contracts) / total_volume
    else:
        # 成交量为0（罕见），简单均价
        n = len(contracts)
        weighted_open = sum(c['open'] for c in contracts) / n
        weighted_high = sum(c['high'] for c in contracts) / n
        weighted_low = sum(c['low'] for c in contracts) / n
        weighted_close = sum(c['close'] for c in contracts) / n
    
    return {
        "symbol": f"{variety}888",  # 例如 a888
        "datetime": new_main_bar['datetime'],
        "open": weighted_open,
        "high": weighted_high,
        "low": weighted_low,
        "close": weighted_close,
        "volume": total_volume,  # 3个合约量能求和
        "open_interest": sum(c['open_interest'] for c in contracts),
        "turnover": sum(c['turnover'] for c in contracts),
    }
```

### 3.3 数据质量保障

- **缺失值处理**: 前向填充（forward fill）
- **异常值检测**: 涨跌停判断、成交量突变识别
- **数据一致性**: 主力和次主力强制不能相同

---

## 4. 因子计算层（无训练版）

### 4.1 Alpha158 特征计算

**目标**: 只计算158个特征值，不训练模型

```python
from vnpy.alpha.dataset.datasets import Alpha158

# 加载最近100天数据
df = pl.read_parquet("data/dce/daily_quotes/*.parquet")

# 计算Alpha158（无需label）
dataset = Alpha158(
    df=df,
    train_period=None,  # 不训练
    valid_period=None,
    test_period=None
)

# 只计算特征
features_df = dataset.cal_features()  # 返回158列特征值
```

### 4.2 特征分组与排名

将158个特征归类为可解释的指标：

```python
feature_groups = {
    "趋势强度": [
        "ma_5", "ma_10", "ma_20",    # 均线系统
        "beta_5", "beta_20",          # 趋势斜率
        "rank_20"                     # 相对强弱
    ],
    "动量指标": [
        "roc_5", "roc_10", "roc_20",  # 涨跌幅
        "cntp_20", "sump_20",         # 上涨天数占比
        "rsv_20"                      # KDJ的RSV
    ],
    "波动率": [
        "std_5", "std_20",            # 标准差
        "klen", "ksft",               # K线形态
        "max_20", "min_20"            # 极值
    ],
    "量价关系": [
        "corr_5", "corr_20",          # 价量相关性
        "vma_5", "vstd_20",           # 成交量均值/标准差
        "vsump_20"                    # 放量天数占比
    ],
}

def calculate_scores(features_df):
    """计算每个品种的综合评分"""
    scores = {}
    for variety in varieties:
        variety_features = features_df.filter(pl.col("symbol") == variety)
        
        # 对每组特征求均值（归一化到0-100）
        trend_score = normalize(variety_features[feature_groups["趋势强度"]].mean())
        momentum_score = normalize(variety_features[feature_groups["动量指标"]].mean())
        volatility_score = normalize(variety_features[feature_groups["波动率"]].mean())
        volume_score = normalize(variety_features[feature_groups["量价关系"]].mean())
        
        # 加权综合评分
        total_score = (
            trend_score * 0.4 + 
            momentum_score * 0.3 + 
            volume_score * 0.2 + 
            volatility_score * 0.1
        )
        
        scores[variety] = {
            "总分": round(total_score, 2),
            "趋势分": round(trend_score, 2),
            "动量分": round(momentum_score, 2),
            "波动分": round(volatility_score, 2),
            "量能分": round(volume_score, 2),
        }
    
    return scores
```

### 4.3 历史趋势提取

```python
def extract_trend_7d(features_df):
    """提取最近7天的因子演变"""
    last_7_days = features_df.tail(7)
    
    trends = {}
    for variety in varieties:
        var_data = last_7_days.filter(pl.col("symbol") == variety)
        
        trends[variety] = {
            "动量趋势": "上升" if var_data["roc_5"][-1] > var_data["roc_5"][0] else "下降",
            "趋势加速": var_data["beta_20"].diff().mean(),  # 斜率变化率
            "量能变化": var_data["vma_5"].pct_change().mean(),
            "7日涨跌": (var_data["close"][-1] / var_data["close"][0] - 1) * 100,
        }
    
    return trends
```

---

## 5. 新闻情绪层

### 5.1 新闻源配置

复用 `ai/news/fetchers/news_summary.py`，扩展关键词：

```json
{
  "dce_agriculture": [
    "大豆", "豆粕", "豆油", "棕榈油", "玉米", 
    "CBOT大豆", "南美大豆", "美豆", "巴西大豆"
  ],
  "dce_chemicals": [
    "聚乙烯", "PVC", "聚丙烯", "乙二醇", "苯乙烯", 
    "原油价格", "化工品", "石化", "乙烯"
  ],
  "dce_energy": [
    "焦煤", "焦炭", "铁矿石", "煤炭", "钢铁", 
    "动力煤", "粗钢产量", "高炉开工率"
  ],
  "macro": [
    "美联储", "加息", "降息", "通胀", "CPI", "PPI", 
    "GDP", "PMI", "中美贸易", "关税"
  ]
}
```

### 5.2 LLM 情绪打分

```python
def sentiment_analysis(news_text, variety):
    prompt = f"""
    分析以下新闻对大商所品种【{variety}】的影响：
    
    新闻: {news_text}
    
    输出JSON格式：
    {{
      "sentiment": "positive/neutral/negative",
      "score": 0.7,  // -1到1的分数
      "confidence": 0.85,
      "reasoning": "南美干旱导致大豆减产预期，利多豆类期货"
    }}
    """
    
    response = llm.call(prompt)
    return parse_json(response)
```

### 5.3 情绪聚合

```python
def aggregate_sentiment(news_list, variety):
    """按品种聚合新闻情绪"""
    relevant_news = filter_by_keywords(news_list, variety_keywords[variety])
    
    if not relevant_news:
        return {"score": 0, "confidence": 0, "summary": "无相关新闻"}
    
    # 时间加权（最近的新闻权重更高）
    weighted_score = 0
    total_weight = 0
    for i, news in enumerate(relevant_news):
        weight = 1.0 / (i + 1)  # 越新权重越高
        weighted_score += news["score"] * weight * news["confidence"]
        total_weight += weight * news["confidence"]
    
    avg_score = weighted_score / total_weight if total_weight > 0 else 0
    
    return {
        "score": round(avg_score, 2),
        "confidence": round(total_weight / len(relevant_news), 2),
        "summary": summarize_news(relevant_news[:3])  # 摘要前3条
    }
```

---

## 6. LLM 决策层

### 6.1 数据融合

```python
def prepare_decision_context(trade_date):
    """准备给LLM的完整上下文"""
    
    # 1. 计算Alpha158特征分数
    features_df = calculate_alpha158()
    scores = calculate_scores(features_df)
    trends = extract_trend_7d(features_df)
    
    # 2. 加载基本面数据
    warehouse = load_warehouse_data(trade_date)
    member_ranking = load_member_ranking(trade_date)
    
    # 3. 新闻情绪
    news = fetch_latest_news()
    sentiment = {v: aggregate_sentiment(news, v) for v in varieties}
    
    # 4. 融合为统一格式
    context = {
        "trade_date": trade_date,
        "varieties": {}
    }
    
    for variety in varieties:
        context["varieties"][variety] = {
            "name": variety_names[variety],  # "豆一"
            "code": variety,                  # "a"
            
            # Alpha158 评分
            "quant_score": scores[variety]["总分"],
            "trend_score": scores[variety]["趋势分"],
            "momentum_score": scores[variety]["动量分"],
            "volume_score": scores[variety]["量能分"],
            
            # 7日趋势
            "trend_7d": trends[variety]["动量趋势"],
            "change_7d_pct": trends[variety]["7日涨跌"],
            
            # 基本面
            "warehouse_change": warehouse.get(variety, {}).get("变化率", 0),
            "member_net_position": member_ranking.get(variety, {}).get("净持仓", 0),
            
            # 新闻情绪
            "sentiment_score": sentiment[variety]["score"],
            "sentiment_confidence": sentiment[variety]["confidence"],
            "sentiment_summary": sentiment[variety]["summary"],
            
            # 市场行情
            "close": get_latest_close(variety),
            "change_1d_pct": get_change_pct(variety, days=1),
        }
    
    return context
```

### 6.2 Prompt 工程

```python
SYSTEM_PROMPT = """
你是一位专业的期货量化分析师，精通技术分析、基本面分析和市场情绪分析。

你的任务：
1. 综合量化评分、7日趋势、基本面数据、新闻情绪，生成交易建议
2. 识别关键风险点（保证金上调、政策变化、黑天鹅事件）
3. 提供清晰的操作理由和止损止盈位

输出要求：
- 推荐Top5做多品种 + Top3做空品种（按综合评分排序）
- 每个品种的详细分析（量化信号+基本面+新闻影响）
- 整体市场风险评估
- 格式：Markdown
"""

def generate_user_prompt(context):
    return f"""
# 大商所品种决策分析 [{context['trade_date']}]

## 一、量化评分榜（Alpha158）

| 品种 | 总分 | 趋势分 | 动量分 | 量能分 | 7日涨跌 |
|------|------|--------|--------|--------|---------|
{format_score_table(context)}

## 二、基本面数据

{format_fundamentals(context)}

## 三、新闻情绪

{format_sentiment(context)}

## 四、市场行情

{format_market_overview(context)}

---

请生成今日交易建议报告（Markdown格式）。
"""
```

### 6.3 报告生成

```python
def generate_report(trade_date):
    """生成决策报告"""
    
    # 1. 准备数据
    context = prepare_decision_context(trade_date)
    
    # 2. 调用LLM
    system_prompt = SYSTEM_PROMPT
    user_prompt = generate_user_prompt(context)
    
    report = llm.call(
        model="gpt-4o-mini",
        system=system_prompt,
        user=user_prompt,
        temperature=0.7
    )
    
    # 3. 保存报告
    report_path = f"ai/agent/DCE/reports/{trade_date}.md"
    Path(report_path).write_text(report, encoding="utf-8")
    
    print(f"✅ 报告已生成: {report_path}")
    return report
```

---

## 7. 实施路径（精简版）

### Phase 1: 数据采集（2-3天）⚠️ **增加合约处理**

**目标**: 稳定获取DCE API全部数据 + 主力连续合约生成

- [x] 测试脚本已完成（`test_dce_api.py`）
- [ ] 实现 `dce_collector.py`（核心采集器）
  - [ ] 全合约日K线下载
  - [ ] 仓单/会员排名/交易参数采集
- [ ] **实现 `main_contract_manager.py`（合约换月处理）** ⭐
  - [ ] 主力合约识别算法
  - [ ] 换月规则判断
  - [ ] 价格连续化调整
  - [ ] 换月事件日志
- [ ] 历史数据回填（100天全合约数据）
- [ ] 增量更新机制 + 定时任务
- [ ] 数据质量检查报告

**验证标准**:
- 26个品种全合约数据完整（包含非主力合约）
- 主力连续合约价格无异常跳空
- 换月记录完整（main_contract_history.parquet）
- 数据缺失率<0.1%

**预计时间**: 2-3天（合约处理增加1天工作量）

### Phase 2: 因子计算（1天）

- [ ] Alpha158 适配（无label版本）
- [ ] 特征分组与评分函数
- [ ] 7日趋势提取函数

**验证**: 所有品种特征计算成功，无NaN

### Phase 3: 新闻情绪（1天）

- [ ] 扩展新闻关键词配置
- [ ] LLM情绪打分接口
- [ ] 品种情绪聚合算法

**验证**: 新闻覆盖>30条，情绪打分置信度>0.7

### Phase 4: 决策系统（1-2天）

- [ ] 数据融合模块
- [ ] Prompt模板 + LLM调用
- [ ] 报告生成器

**验证**: 报告生成时间<3分钟，格式稳定

---

## 8. 目录结构

```
ai/agent/DCE/
├── README.md
├── plan.md                        # 本计划
├── requirements.txt
│
├── data_collector/
│   ├── __init__.py
│   ├── dce_collector.py          # DCE API 采集器
│   ├── main_contract_manager.py  # ⭐ 主力合约识别与换月处理
│   ├── config.py                 # 品种列表、API配置
│   └── scheduler.py              # 定时任务
│
├── factor_analysis/
│   ├── __init__.py
│   ├── alpha158_calculator.py    # 特征计算（基于连续合约）
│   └── score_ranking.py          # 评分排名
│
├── news_sentiment/
│   ├── __init__.py
│   ├── news_fetcher.py           # 复用 ai/news/fetchers
│   └── sentiment_analyzer.py     # LLM情绪打分
│
├── decision_engine/
│   ├── __init__.py
│   ├── data_fusion.py            # 多维数据融合
│   ├── llm_advisor.py            # LLM决策
│   └── report_generator.py       # Markdown报告生成
│
├── run.py                         # 主入口
├── config.yaml                    # 全局配置
│
├── data/                          # 数据存储（.gitignore）
│   └── dce/
│       ├── raw_contracts/        # ⭐ 原始全合约数据
│       │   ├── a/
│       │   ├── m/
│       │   └── ...
│       ├── continuous/           # ⭐ 主力连续合约
│       │   ├── a_main_continuous.parquet
│       │   └── ...
│       ├── main_contract_history.parquet  # ⭐ 换月记录
│       ├── warehouse_bill.parquet
│       ├── member_ranking.parquet
│       └── trade_params.parquet
│
└── reports/                       # 决策报告
    ├── 20260419.md
    └── ...
```

---

## 9. 成本与预期

### 成本

| 项目 | 费用 |
|------|------|
| DCE API | 免费 |
| LLM调用（GPT-4o-mini） | ~$0.3/天（约2元/月） |
| 开发时间 | 4-5天 |

### 效果预期

**1个月后**:
- 每日稳定生成报告
- 品种推荐与量化信号一致性>75%
- 重大新闻事件捕捉准确率>80%

**3个月后**:
- 决策准确率逐步提升（通过人工反馈优化Prompt）
- 可考虑加入实盘验证（小仓位跟踪）

---

## 10. 关键风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| **合约换月处理错误** ⚠️ | Alpha158计算错误、价格跳空 | 1. 严格测试换月算法<br>2. 人工复核换月记录<br>3. 可视化检查连续合约价格 |
| **主力合约识别滞后** | 实际主力已切换但系统未识别 | 1. 多维度判断（持仓+成交量）<br>2. 提前20天预警<br>3. 保留原始全合约数据 |
| DCE API限频 | 下载失败、数据缺失 | 批量查询（varietyId=all）+ sleep(1) |
| Alpha158特征无效 | 决策准确率低 | 结合基本面+新闻降低权重 |
| LLM幻觉 | 编造不存在的新闻 | 约束输出格式+人工复核 |
| 数据缺失 | 特征计算失败 | 前向填充+异常值检测 |

---

## 11. 下一步行动

**今晚立即开始**:

```bash
# 1. 创建目录
mkdir -p ai/agent/DCE/{data_collector,factor_analysis,news_sentiment,decision_engine,data/dce,reports}

# 2. 测试DCE API历史深度
uv run python ai/data_process/test_dce_api.py --test-history

# 3. 开始编写 dce_collector.py
```

**明天**:
- 完成数据采集器
- 历史数据回填（100天）

**后天**:
- Alpha158特征计算
- 生成第一份决策报告

🎯 **目标**: 3-4天内完成第一版，开始每日自动生成决策报告！
