"""
期货行情K线可视化

支持日K线和分钟K线的交互式查看。
数据来源：vnpy SQLite 数据库（~/.vntrader/database.db）

启动：
    uv run python ai/chart/app.py
    浏览器访问：http://localhost:8050
"""

import re
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

# 导入主连映射表读取工具
sys.path.insert(0, str(Path(__file__).parent.parent))
from data_process.build_main_contract import MappingStore

# ─────────────────────────────────────────────────────────────
# 初始化数据
# ─────────────────────────────────────────────────────────────

db = get_database()
_mapping_store = MappingStore()

def load_contract_list() -> tuple[list[dict], dict[str, set]]:
    """加载所有合约列表（日K或分钟K均收录）。

    每次调用都重新查询数据库，确保能拿到运行期间新写入的合约（如主连）。
    结果会缓存在模块级变量里，可通过 reload_contracts() 刷新。
    """
    overviews = db.get_bar_overview()
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
    # LOCAL 主连合约置顶（XXX888.LOCAL），其余按交易所 + 合约倒序
    contracts.sort(
        key=lambda x: (
            0 if x["exchange"] == "LOCAL" else 1,
            x["exchange"],
            x["symbol"],
        ),
        reverse=False,
    )
    # LOCAL 内部按合约名倒序（最新月份在前），非 LOCAL 按原倒序
    local_contracts = [c for c in contracts if c["exchange"] == "LOCAL"]
    other_contracts = [c for c in contracts if c["exchange"] != "LOCAL"]
    local_contracts.sort(key=lambda x: x["symbol"])          # LOCAL 正序（888 品种字母序）
    other_contracts.sort(key=lambda x: (x["exchange"], x["symbol"]), reverse=True)
    contracts = local_contracts + other_contracts
    return contracts, contract_intervals


ALL_CONTRACTS, CONTRACT_INTERVALS = load_contract_list()
DEFAULT_CONTRACT = ALL_CONTRACTS[0]["value"] if ALL_CONTRACTS else ""


def reload_contracts() -> None:
    """重新从数据库加载合约列表，更新全局缓存。"""
    global ALL_CONTRACTS, CONTRACT_INTERVALS, DEFAULT_CONTRACT
    ALL_CONTRACTS, CONTRACT_INTERVALS = load_contract_list()
    if not DEFAULT_CONTRACT:
        DEFAULT_CONTRACT = ALL_CONTRACTS[0]["value"] if ALL_CONTRACTS else ""


# ─────────────────────────────────────────────────────────────
# Dash 应用
# ─────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    title="期货K线可视化",
    assets_folder=str(Path(__file__).parent / "assets"),
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
                # 合约搜索：输入框 + 下拉列表分离，避免 Dash 默认预填选中项的问题
                html.Div(
                    style={"display": "flex", "flexDirection": "column", "gap": "4px",
                           "flex": "1", "minWidth": "220px", "maxWidth": "360px"},
                    children=[
                        dcc.Input(
                            id="contract-search",
                            type="text",
                            placeholder="搜索合约（如 cu2606）",
                            debounce=False,
                            value="",
                            style={
                                "width": "100%",
                                "backgroundColor": COLORS["bg"],
                                "color": COLORS["text"],
                                "border": f"1px solid {COLORS['border']}",
                                "borderRadius": "6px",
                                "padding": "6px 10px",
                                "fontSize": "13px",
                                "outline": "none",
                                "boxSizing": "border-box",
                            },
                        ),
                        dcc.Dropdown(
                            id="contract-dropdown",
                            options=[{"label": c["label"], "value": c["value"]} for c in ALL_CONTRACTS],
                            value=DEFAULT_CONTRACT,
                            placeholder="选择合约",
                            searchable=False,
                            clearable=False,
                            style={
                                "backgroundColor": COLORS["bg"],
                                "color": COLORS["text"],
                                "border": f"1px solid {COLORS['border']}",
                                "borderRadius": "6px",
                            },
                        ),
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
    Output("contract-dropdown", "options"),
    Output("contract-dropdown", "value"),
    Input("contract-search", "value"),
    State("contract-dropdown", "value"),
)
def filter_contracts(search: str, current_value: str):
    """根据搜索框输入实时过滤合约列表。

    每次回调都重新从数据库加载合约列表，确保能看到运行期间新写入的合约（如主连）。
    同时保证 value 始终在 options 里，避免 Dash 自动置 None 导致空白图。
    """
    # 每次都重新加载，以获取最新的数据库状态（包括新生成的主连合约）
    reload_contracts()
    all_contracts = ALL_CONTRACTS

    if not search:
        opts = [{"label": c["label"], "value": c["value"]} for c in all_contracts]
    else:
        kw = search.strip().lower()
        filtered = [c for c in all_contracts if kw in c["label"].lower()]
        opts = [{"label": c["label"], "value": c["value"]} for c in filtered]

    if not opts:
        return [{"label": c["label"], "value": c["value"]} for c in all_contracts], current_value

    opt_values = {o["value"] for o in opts}
    if current_value in opt_values:
        return opts, current_value
    else:
        return opts, opts[0]["value"]


@app.callback(
    Output("kline-chart", "figure"),
    Output("contract-info", "children"),
    Input("contract-dropdown", "value"),
    Input("current-interval", "data"),
    Input("minute-range-dropdown", "value"),
)
def update_chart(vt_symbol: str, interval: str, minute_days: int):
    """更新K线图"""
    print(f"\n[DEBUG] update_chart called: vt_symbol={vt_symbol!r}, interval={interval!r}, minute_days={minute_days}")

    if not vt_symbol:
        print("[DEBUG] vt_symbol 为空，返回空图")
        return go.Figure(), ""

    try:
        symbol, exchange_str = vt_symbol.split(".")
        exchange = Exchange(exchange_str)
        print(f"[DEBUG] symbol={symbol!r}, exchange={exchange}")
    except Exception as e:
        print(f"[DEBUG] 解析合约格式出错: {e}")
        return go.Figure(), "合约格式错误"

    # 加载数据：直接查询数据库 overview，不依赖可能过时的全局缓存
    overviews = db.get_bar_overview()
    key = vt_symbol
    intervals_for_key = {
        o.interval
        for o in overviews
        if f"{o.symbol}.{o.exchange.value}" == key
    }
    has_daily = Interval.DAILY in intervals_for_key
    has_minute = Interval.MINUTE in intervals_for_key
    print(f"[DEBUG] intervals_for_key={intervals_for_key}, has_daily={has_daily}, has_minute={has_minute}")

    if interval == "daily":
        if not has_daily:
            print("[DEBUG] 无日K数据，降级显示分钟K")
            title_suffix = "分钟K（无日K数据）"
            start = datetime.now() - timedelta(days=minute_days or 3)
            bars = db.load_bar_data(symbol, exchange, Interval.MINUTE, start, datetime.now())
            print(f"[DEBUG] 分钟K(降级) 加载: {len(bars)} 根")
        else:
            daily_years = 3
            start_dt = datetime.now() - timedelta(days=365 * daily_years)
            end_dt = datetime.now()
            print(f"[DEBUG] 加载日K: symbol={symbol}, exchange={exchange}, start={start_dt.date()}, end={end_dt.date()}")
            bars = db.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)
            print(f"[DEBUG] 日K加载结果: {len(bars)} 根" + (f", 最早={bars[0].datetime}, 最新={bars[-1].datetime}" if bars else ", 空!"))
            title_suffix = "日K"
    else:
        if not has_minute:
            print("[DEBUG] 无分钟K数据")
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
        bars = db.load_bar_data(symbol, exchange, Interval.MINUTE, start, datetime.now())
        print(f"[DEBUG] 分钟K加载: {len(bars)} 根")
        title_suffix = f"分钟K（近{minute_days}天）"

    if not bars:
        print("[DEBUG] bars 为空，返回'暂无数据'图")
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

    # X轴用字符串标签（category类型），消除非交易时段空白
    if interval == "daily":
        x_labels = [d.strftime("%Y-%m-%d") for d in dts]
    else:
        x_labels = [d.strftime("%m-%d %H:%M") for d in dts]

    # 涨跌颜色
    vol_colors = [
        COLORS["green"] if c >= o else COLORS["red"]
        for o, c in zip(opens, closes)
    ]

    # Y轴范围：基于可见数据的 high/low 自适应，留5%边距
    price_min = min(lows)
    price_max = max(highs)
    price_pad = (price_max - price_min) * 0.05 if price_max > price_min else price_max * 0.01
    y_range = [price_min - price_pad, price_max + price_pad]

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
            x=x_labels,
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

    # ── 主连换月竖线标注（仅 LOCAL 交易所的主连品种，且日K视图下显示）──
    if exchange == Exchange.LOCAL and symbol.endswith("888") and interval == "daily":
        product = re.sub(r"\d", "", symbol.replace("888", "")) or symbol.replace("888", "")
        # 从合约代码推断原始交易所（LOCAL 主连对应多种交易所，通过大小写判断）
        # 大写 -> CZCE；小写通过 MappingStore 直接查 product
        # 这里直接遍历所有 exchange 找到有记录的那个
        switches = []
        for _exc_val in ["CZCE", "SHFE", "DCE", "INE", "GFEX", "CFFEX"]:
            _sw = _mapping_store.get_switches(product, _exc_val)
            if _sw:
                switches = _sw
                break

        # 构建日期 -> x轴字符串标签的查找表（category 轴必须用字符串，不能用整数索引）
        x_label_set: set = set(x_labels)

        for sw in switches[1:]:  # 跳过第一条（初始状态，不是「切换」）
            sw_str = sw["trade_date"].strftime("%Y-%m-%d")
            if sw_str not in x_label_set:
                # 该切换日不在当前加载范围内（比如早于 3 年前），跳过
                continue
            print(f"[DEBUG] 画换月线: {sw_str} -> {sw['dominant']}")
            # category 轴的 shape/annotation x 坐标必须用字符串标签
            fig.add_shape(
                type="line",
                x0=sw_str, x1=sw_str,
                y0=0, y1=1,
                xref="x",
                yref="paper",
                line={"color": "rgba(255,200,0,0.45)", "width": 1, "dash": "dot"},
            )
            fig.add_annotation(
                x=sw_str,
                y=0.99,
                xref="x",
                yref="paper",
                text=sw["dominant"],
                showarrow=False,
                font={"size": 9, "color": "rgba(255,200,0,0.85)"},
                textangle=-90,
                xanchor="left",
                yanchor="top",
            )

    # 成交量副图
    fig.add_trace(
        go.Bar(
            x=x_labels,
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

    # X 轴：category 类型，按序号排列，消除非交易时段空白
    # 不再设置 range——日K 已在加载阶段截断为最近 3 年，Plotly 直接全量渲染即可
    x_axis_common = {
        "type": "category",
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
        "nticks": 12,
        "tickangle": -30,
    }
    fig.update_layout(xaxis=x_axis_common, xaxis2=x_axis_common)

    # Y 轴：主图使用自适应范围，副图（成交量）自动
    fig.update_layout(
        yaxis={
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
            "range": y_range,      # 自适应范围，5%边距
            "fixedrange": False,   # 允许用户缩放
        },
        yaxis2={
            "showgrid": False,
            "zeroline": False,
            "tickfont": {"color": COLORS["text_dim"], "size": 10},
            "linecolor": COLORS["border"],
            "side": "right",
            "autorange": True,
        },
    )

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
    app.run(debug=True, host="0.0.0.0", port=8050)
