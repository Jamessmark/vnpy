"""
期货行情K线可视化

支持日K线和分钟K线的交互式查看。
数据来源：vnpy SQLite 数据库（~/.vntrader/database.db）

启动：
    uv run python ai/chart/app.py
    浏览器访问：http://localhost:8050
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 确保能导入项目根目录的 vnpy
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import dash
from dash import dcc, html, Input, Output, State, callback_context
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from vnpy.trader.database import get_database
from vnpy.trader.constant import Exchange, Interval

# ─────────────────────────────────────────────────────────────
# 初始化数据
# ─────────────────────────────────────────────────────────────

db = get_database()

def load_contract_list() -> list[dict]:
    """加载所有合约列表（日K或分钟K均收录）"""
    overviews = db.get_bar_overview()
    # 记录每个合约有哪些 interval
    contract_intervals: dict[str, set] = {}
    contract_meta: dict[str, dict] = {}
    for o in overviews:
        if o.interval not in (Interval.DAILY, Interval.MINUTE):
            continue
        key = f"{o.symbol}.{o.exchange.value}"
        if key not in contract_intervals:
            contract_intervals[key] = set()
            contract_meta[key] = {
                "label": key,
                "value": key,
                "symbol": o.symbol,
                "exchange": o.exchange.value,
            }
        contract_intervals[key].add(o.interval)

    contracts = list(contract_meta.values())
    # 按交易所 + 合约代码排序
    contracts.sort(key=lambda x: (x["exchange"], x["symbol"]))
    return contracts, contract_intervals


ALL_CONTRACTS, CONTRACT_INTERVALS = load_contract_list()
DEFAULT_CONTRACT = ALL_CONTRACTS[0]["value"] if ALL_CONTRACTS else ""


# ─────────────────────────────────────────────────────────────
# Dash 应用
# ─────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    title="期货K线可视化",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

# ── 样式常量 ──────────────────────────────────────────────────
COLORS = {
    "bg": "#0f1117",
    "panel": "#1a1d27",
    "border": "#2d3145",
    "text": "#e0e0e0",
    "text_dim": "#8888aa",
    "accent": "#5b8af5",
    "green": "#26a69a",
    "red": "#ef5350",
    "volume": "#4a5568",
}

LAYOUT_STYLE = {
    "backgroundColor": COLORS["bg"],
    "color": COLORS["text"],
    "fontFamily": "'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    "minHeight": "100vh",
    "margin": "0",
    "padding": "0",
}

# ── 布局 ──────────────────────────────────────────────────────
app.layout = html.Div(
    style=LAYOUT_STYLE,
    children=[
        # 顶部导航栏
        html.Div(
            style={
                "backgroundColor": COLORS["panel"],
                "borderBottom": f"1px solid {COLORS['border']}",
                "padding": "12px 24px",
                "display": "flex",
                "alignItems": "center",
                "gap": "24px",
                "flexWrap": "wrap",
            },
            children=[
                html.Span(
                    "📈 期货K线",
                    style={"fontSize": "18px", "fontWeight": "700", "color": COLORS["accent"], "whiteSpace": "nowrap"},
                ),
                # 合约搜索
                html.Div(
                    style={"flex": "1", "minWidth": "220px", "maxWidth": "360px"},
                    children=[
                        dcc.Dropdown(
                            id="contract-dropdown",
                            options=[{"label": c["label"], "value": c["value"]} for c in ALL_CONTRACTS],
                            value=DEFAULT_CONTRACT,
                            placeholder="搜索合约（如 cu2606）",
                            searchable=True,
                            clearable=False,
                            style={
                                "backgroundColor": COLORS["bg"],
                                "color": COLORS["text"],
                                "border": f"1px solid {COLORS['border']}",
                                "borderRadius": "6px",
                            },
                        )
                    ],
                ),
                # 周期切换
                html.Div(
                    style={"display": "flex", "gap": "8px"},
                    children=[
                        html.Button(
                            "日K",
                            id="btn-daily",
                            n_clicks=0,
                            style={
                                "backgroundColor": COLORS["accent"],
                                "color": "#fff",
                                "border": "none",
                                "borderRadius": "6px",
                                "padding": "6px 18px",
                                "cursor": "pointer",
                                "fontWeight": "600",
                                "fontSize": "14px",
                            },
                        ),
                        html.Button(
                            "分钟K",
                            id="btn-minute",
                            n_clicks=0,
                            style={
                                "backgroundColor": COLORS["panel"],
                                "color": COLORS["text"],
                                "border": f"1px solid {COLORS['border']}",
                                "borderRadius": "6px",
                                "padding": "6px 18px",
                                "cursor": "pointer",
                                "fontWeight": "600",
                                "fontSize": "14px",
                            },
                        ),
                    ],
                ),
                # 日期范围（仅分钟K可用）
                html.Div(
                    id="date-range-container",
                    style={"display": "none", "alignItems": "center", "gap": "8px"},
                    children=[
                        html.Span("最近", style={"color": COLORS["text_dim"], "fontSize": "13px"}),
                        dcc.Dropdown(
                            id="minute-range-dropdown",
                            options=[
                                {"label": "1天", "value": 1},
                                {"label": "3天", "value": 3},
                                {"label": "7天", "value": 7},
                            ],
                            value=3,
                            clearable=False,
                            style={
                                "width": "90px",
                                "backgroundColor": COLORS["bg"],
                                "color": COLORS["text"],
                                "border": f"1px solid {COLORS['border']}",
                                "borderRadius": "6px",
                            },
                        ),
                    ],
                ),
                # 合约信息展示
                html.Div(
                    id="contract-info",
                    style={"color": COLORS["text_dim"], "fontSize": "12px", "whiteSpace": "nowrap"},
                ),
            ],
        ),

        # 隐藏状态：当前周期
        dcc.Store(id="current-interval", data="daily"),

        # 主图区域
        html.Div(
            style={"padding": "16px 24px"},
            children=[
                dcc.Loading(
                    id="loading",
                    type="circle",
                    color=COLORS["accent"],
                    children=[
                        dcc.Graph(
                            id="kline-chart",
                            config={
                                "displayModeBar": True,
                                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                                "scrollZoom": True,
                                "displaylogo": False,
                            },
                            style={"height": "78vh"},
                        )
                    ],
                )
            ],
        ),
    ],
)


# ─────────────────────────────────────────────────────────────
# 回调
# ─────────────────────────────────────────────────────────────

@app.callback(
    Output("current-interval", "data"),
    Output("btn-daily", "style"),
    Output("btn-minute", "style"),
    Output("date-range-container", "style"),
    Input("btn-daily", "n_clicks"),
    Input("btn-minute", "n_clicks"),
    State("current-interval", "data"),
)
def toggle_interval(n_daily, n_minute, current):
    """切换日K / 分钟K"""
    ctx = callback_context
    if not ctx.triggered:
        triggered = "btn-daily"
    else:
        triggered = ctx.triggered[0]["prop_id"].split(".")[0]

    active_style = {
        "backgroundColor": COLORS["accent"],
        "color": "#fff",
        "border": "none",
        "borderRadius": "6px",
        "padding": "6px 18px",
        "cursor": "pointer",
        "fontWeight": "600",
        "fontSize": "14px",
    }
    inactive_style = {
        "backgroundColor": COLORS["panel"],
        "color": COLORS["text"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "6px",
        "padding": "6px 18px",
        "cursor": "pointer",
        "fontWeight": "600",
        "fontSize": "14px",
    }

    if triggered == "btn-minute":
        interval = "minute"
        date_range_style = {"display": "flex", "alignItems": "center", "gap": "8px"}
        return interval, inactive_style, active_style, date_range_style
    else:
        interval = "daily"
        date_range_style = {"display": "none"}
        return interval, active_style, inactive_style, date_range_style


@app.callback(
    Output("kline-chart", "figure"),
    Output("contract-info", "children"),
    Input("contract-dropdown", "value"),
    Input("current-interval", "data"),
    Input("minute-range-dropdown", "value"),
)
def update_chart(vt_symbol: str, interval: str, minute_days: int):
    """更新K线图"""
    if not vt_symbol:
        return go.Figure(), ""

    try:
        symbol, exchange_str = vt_symbol.split(".")
        exchange = Exchange(exchange_str)
    except Exception:
        return go.Figure(), "合约格式错误"

    # 加载数据
    key = vt_symbol
    has_daily = Interval.DAILY in CONTRACT_INTERVALS.get(key, set())
    has_minute = Interval.MINUTE in CONTRACT_INTERVALS.get(key, set())

    if interval == "daily":
        if not has_daily:
            # 没有日K，降级显示分钟K
            title_suffix = "分钟K（无日K数据）"
            start = datetime.now() - timedelta(days=minute_days or 3)
            bars = db.load_bar_data(symbol, exchange, Interval.MINUTE, start, datetime.now())
        else:
            bars = db.load_bar_data(
                symbol, exchange, Interval.DAILY,
                datetime(2000, 1, 1), datetime.now()
            )
            title_suffix = "日K"
    else:
        if not has_minute:
            info_text = "⚠️ 该合约无分钟K数据（仅有历史日K线）"
            fig = go.Figure()
            fig.update_layout(
                paper_bgcolor=COLORS["bg"],
                plot_bgcolor=COLORS["bg"],
                font={"color": COLORS["text"]},
                annotations=[{
                    "text": "该合约无分钟K数据",
                    "x": 0.5, "y": 0.5,
                    "xref": "paper", "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 18, "color": COLORS["text_dim"]},
                }],
            )
            return fig, info_text
        start = datetime.now() - timedelta(days=minute_days or 3)
        bars = db.load_bar_data(
            symbol, exchange, Interval.MINUTE, start, datetime.now()
        )
        title_suffix = f"分钟K（近{minute_days}天）"

    if not bars:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=COLORS["bg"],
            plot_bgcolor=COLORS["bg"],
            font={"color": COLORS["text"]},
            annotations=[{
                "text": "暂无数据",
                "x": 0.5, "y": 0.5,
                "xref": "paper", "yref": "paper",
                "showarrow": False,
                "font": {"size": 20, "color": COLORS["text_dim"]},
            }],
        )
        return fig, "暂无数据"

    # 构建数据序列
    dts = [b.datetime for b in bars]
    opens = [b.open_price for b in bars]
    highs = [b.high_price for b in bars]
    lows = [b.low_price for b in bars]
    closes = [b.close_price for b in bars]
    volumes = [b.volume for b in bars]

    # 涨跌颜色
    vol_colors = [
        COLORS["green"] if c >= o else COLORS["red"]
        for o, c in zip(opens, closes)
    ]

    # 双子图：主图（K线）+ 副图（成交量）
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    # K线主图
    fig.add_trace(
        go.Candlestick(
            x=dts,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            name=vt_symbol,
            increasing={"fillcolor": COLORS["green"], "line": {"color": COLORS["green"], "width": 1}},
            decreasing={"fillcolor": COLORS["red"], "line": {"color": COLORS["red"], "width": 1}},
            hoverinfo="x+y",
        ),
        row=1, col=1,
    )

    # 成交量副图
    fig.add_trace(
        go.Bar(
            x=dts,
            y=volumes,
            name="成交量",
            marker_color=vol_colors,
            opacity=0.85,
            hoverinfo="x+y",
        ),
        row=2, col=1,
    )

    # 布局
    latest = bars[-1]
    price_change = latest.close_price - bars[0].open_price if len(bars) > 1 else 0
    pct_change = price_change / bars[0].open_price * 100 if bars[0].open_price else 0
    change_color = COLORS["green"] if price_change >= 0 else COLORS["red"]
    change_symbol = "▲" if price_change >= 0 else "▼"

    fig.update_layout(
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["bg"],
        font={"color": COLORS["text"], "family": "'Inter', 'PingFang SC', sans-serif"},
        margin={"l": 60, "r": 20, "t": 40, "b": 20},
        legend={"bgcolor": "rgba(0,0,0,0)", "font": {"size": 11}},
        hovermode="x unified",
        hoverlabel={
            "bgcolor": COLORS["panel"],
            "bordercolor": COLORS["border"],
            "font": {"color": COLORS["text"], "size": 12},
        },
        xaxis_rangeslider_visible=False,
        title={
            "text": f"<b>{vt_symbol}</b>  {title_suffix}  "
                    f"<span style='color:{change_color}'>{change_symbol} {abs(price_change):.2f} ({pct_change:+.2f}%)</span>",
            "font": {"size": 14, "color": COLORS["text"]},
            "x": 0.01,
            "xanchor": "left",
        },
    )

    # X 轴样式
    for xaxis in ["xaxis", "xaxis2"]:
        fig.update_layout(**{
            xaxis: {
                "showgrid": True,
                "gridcolor": COLORS["border"],
                "gridwidth": 0.5,
                "zeroline": False,
                "tickfont": {"color": COLORS["text_dim"], "size": 11},
                "linecolor": COLORS["border"],
                "showspikes": True,
                "spikecolor": COLORS["text_dim"],
                "spikethickness": 1,
                "spikedash": "dot",
            }
        })

    # Y 轴样式
    for yaxis in ["yaxis", "yaxis2"]:
        fig.update_layout(**{
            yaxis: {
                "showgrid": True,
                "gridcolor": COLORS["border"],
                "gridwidth": 0.5,
                "zeroline": False,
                "tickfont": {"color": COLORS["text_dim"], "size": 11},
                "linecolor": COLORS["border"],
                "side": "right",
                "showspikes": True,
                "spikecolor": COLORS["text_dim"],
                "spikethickness": 1,
                "spikedash": "dot",
            }
        })

    # 合约信息摘要
    info = (
        f"{len(bars)} 根K线  |  "
        f"最新: {latest.close_price:.2f}  |  "
        f"最高: {max(highs):.2f}  最低: {min(lows):.2f}"
    )

    return fig, info


# ─────────────────────────────────────────────────────────────
# 启动
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 启动期货K线可视化...")
    print("📌 浏览器访问: http://localhost:8050")
    print("   Ctrl+C 退出\n")
    app.run(debug=False, host="0.0.0.0", port=8050)
