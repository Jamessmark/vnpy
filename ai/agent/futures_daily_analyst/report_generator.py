"""
报告生成模块
将 K 线数据发送给 CodeFlicker Agent，由 Agent 自行搜索新闻并生成期货执行计划报告
"""

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# agent-session-controller 脚本目录（项目内）
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "agent-session-controller" / "scripts"
DUET_API_URL = "http://localhost:3459"

# ── Prompt 模板 ────────────────────────────────────────────────────

TASK_PROMPT_TEMPLATE = """你是一位专业的商品期货分析师。请完成以下任务，生成今日（{date}）全品种期货执行计划报告。

## 第一步：搜索今日相关新闻

请使用 web_search 工具，分别搜索以下关键词，获取最新资讯（每组取 5 条）：

1. `原油价格 OPEC 今日` — 能源市场
2. `国内商品期货 今日行情` — 整体商品市场
3. `美伊战争 中东局势 最新` — 地缘政治
4. `农产品期货 棉花 白糖 菜粕 今日` — 农产品板块

## 第二步：分析以下全品种 K 线行情数据（近 {bar_days} 个交易日日 K 线）

所有品种均来自郑商所（CZCE）主连合约，含换月记录。

{kline_section}

## 第三步：生成完整报告

综合以上新闻和 K 线数据，按如下结构输出 Markdown 格式报告：

---

# 期货每日执行计划 [{date}]

## 一、市场整体概览
（2-3 段，总结今日商品市场整体氛围、主要驱动因素、板块分化情况）

## 二、重要新闻摘要
（按主题归类，要点形式，每条不超过 50 字，共 6-10 条）

## 三、全品种逐一分析

> 对以下每个品种分别给出简洁分析，格式统一：
> - **走势特征**：（3 行以内，结合 K 线 + 持仓量 + 换月）
> - **操作建议**：（方向：做多/做空/观望，理由一句话）
> - **关注价位**：支撑 xxx / 压力 xxx

{symbol_sections_placeholder}

## 四、趋势确定性排行榜（本日最值得关注）

> 综合技术面（趋势强度、成交量配合、持仓量变化）和基本面（新闻驱动），
> 从所有品种中筛选出 **趋势最明确、可操作性最强** 的 3-5 个品种：

| 排名 | 品种 | 方向 | 确定性评分(1-10) | 核心逻辑（一句话） |
|------|------|------|----------------|-------------------|
| 1 | ... | 做多/做空 | x | ... |
| 2 | ... | 做多/做空 | x | ... |
| 3 | ... | 做多/做空 | x | ... |

**操作优先级说明**：（2-3 行，说明为何这几个品种优先级最高，以及当前需要规避的高风险品种）

## 五、风险提示
（3 条，当前最重要的系统性风险和个别品种风险）

## 六、数据来源说明
- 行情数据：vnpy 数据库（CZCE 主连日 K 线，含换月记录，2020 年至今）
- 新闻数据：web_search 实时搜索（{date}）
- 报告生成时间：{datetime_str}
"""


# ── 数据格式化 ─────────────────────────────────────────────────────

def _format_kline_section(market_data: list[dict]) -> tuple[str, int]:
    """将 K 线数据格式化为 Prompt 中的文字段落，返回 (section_text, bar_days)"""
    lines = []
    bar_days = 0
    for item in market_data:
        name     = item.get("name", "")
        symbol   = item.get("symbol", "")
        stats    = item.get("stats", {})
        bars     = item.get("bars", [])
        switches = item.get("switches", [])

        bar_days = max(bar_days, len(bars))

        if not bars:
            lines.append(f"### {name}（{symbol}）\n*无数据*\n")
            continue

        oi_chg = stats.get("oi_chg", 0)
        oi_dir = "+" if oi_chg > 0 else "-" if oi_chg < 0 else "="
        trend  = stats.get("trend", "")
        lines.append(f"### {name}（{symbol}）")
        # 压缩统计行为一行，减少 Token 消耗
        lines.append(
            f"cls={stats.get('latest_close','N/A')} H={stats.get('period_high','N/A')} "
            f"L={stats.get('period_low','N/A')} chg={stats.get('total_chg_pct',0):+.2f}%({trend}) "
            f"vol={stats.get('avg_volume',0):,} oi={stats.get('latest_oi',0):,}({oi_dir}{abs(oi_chg):,})"
        )

        if switches:
            lines.append(f"sw: {' | '.join(switches)}")

        lines.append("")
        lines.append("| 日期 | 开 | 高 | 低 | 收 | 涨跌% | 成交量 | 持仓量 |")
        lines.append("|------|-----|-----|-----|-----|-------|--------|--------|")
        for bar in bars:
            chg = f"{bar.get('chg_pct', 0):+.2f}%"
            lines.append(
                f"| {bar['date']} | {bar['open']} | {bar['high']} | "
                f"{bar['low']} | {bar['close']} | {chg} | "
                f"{bar['volume']:,} | {bar['open_interest']:,} |"
            )
        lines.append("")
    return "\n".join(lines), bar_days


# ── Agent Session Controller 调用 ──────────────────────────────────

def _run_script(script_name: str, *args: str) -> dict:
    """调用 agent-session-controller 的 shell 脚本，返回解析后的 JSON"""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        raise FileNotFoundError(
            f"脚本不存在：{script_path}\n"
            "请确认 CodeFlicker 已安装并运行 codeflicker.debugServer.start"
        )
    result = subprocess.run(
        ["/bin/bash", str(script_path), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "DUET_API_URL": DUET_API_URL},
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"success": False, "error": result.stdout + result.stderr}


def _get_or_create_session(session_name: str = "期货执行计划Agent") -> str:
    """优先复用已有同名 Session，不存在则新建，返回 session_id"""
    resp     = _run_script("session-list.sh")
    sessions = resp.get("data", {}).get("sessionList", [])
    for s in sessions:
        if s.get("sessionName") == session_name:
            sid = s["sessionId"]
            print(f"  [Agent] 复用已有 Session：{session_name}（{sid[:8]}...）")
            return sid

    resp = _run_script("session-create.sh", session_name, "agent")
    sid  = resp.get("data", {}).get("sessionId", "")
    if not sid:
        raise RuntimeError(f"创建 Session 失败：{resp}")
    print(f"  [Agent] 新建 Session：{session_name}（{sid[:8]}...）")
    return sid


def _send_task_and_wait(session_id: str, prompt: str, timeout: int = 600) -> str:
    """
    把 prompt 写入临时文件，通过 task-send.sh 发给 Agent（agent 模式，可自行搜索新闻），
    等待完成后拉取回复内容，返回报告文本
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt)
        task_file = f.name

    try:
        # 在发送之前记录时间戳，并留 2 秒余量，防止消息 ts 早于 send_ts
        send_ts = int(time.time() * 1000) - 2000

        print(f"  [Agent] 发送分析任务（Agent 将自行搜索新闻）...", flush=True)
        send_resp = _run_script("task-send.sh", session_id, "--file", task_file, "agent")
        if not send_resp.get("success"):
            raise RuntimeError(f"发送任务失败：{send_resp}")

        # 等待 Agent 开始处理
        time.sleep(3)

        # 轮询等待完成
        print(f"  [Agent] 等待 AI 分析（含新闻搜索，最长 {timeout}s）...", flush=True)
        deadline = time.time() + timeout
        last_dot = time.time()
        while time.time() < deadline:
            status_resp  = _run_script("session-status.sh", session_id)
            data         = status_resp.get("data", {})
            is_running   = data.get("isRunning", True)
            last_say     = data.get("lastMessageSay", "")
            waiting      = data.get("waitingForUserInput", False)
            last_msg_ts  = data.get("lastMessageTs", 0)

            if time.time() - last_dot >= 10:
                print(".", end="", flush=True)
                last_dot = time.time()

            if waiting:
                # 有命令/工具需要审批，自动批准
                ask_type = data.get("askType", "")
                print(f"\n  [Agent] 等待审批（{ask_type}），自动批准...", flush=True)
                _run_script("task-respond.sh", session_id, "approve", ask_type or "command")
                time.sleep(2)
                continue

            if not is_running and last_msg_ts >= send_ts:
                print(f"\n  ✓ 分析完成（{last_say}）", flush=True)
                break

            time.sleep(5)
        else:
            print(f"\n  ⚠️  等待超时（{timeout}s）", flush=True)

        # 拉取全部消息，Python 手动过滤本次回复
        # 倒序取最新 20 条，避免 asc+limit=100 在消息过多时错过最终 text
        search_options = json.dumps({
            "options": {"limit": 20, "order": "desc"},
            "textLimits": {"perMessage": 30000, "total": 150000},
        })
        msg_resp     = _run_script("messages-search.sh", session_id, search_options)
        all_messages = msg_resp.get("data", {}).get("messages", [])
        all_messages.reverse()  # desc 取到的是逆序，还原为时间正序

        # 只保留本次发送之后的消息，取 say=text + partial=False 的最后一条
        recent    = [m for m in all_messages if m.get("ts", 0) >= send_ts]
        text_msgs = [
            m for m in recent
            if m.get("say") == "text" and not m.get("partial", False) and m.get("text", "").strip()
        ]

        print(f"  [Agent] 最新 {len(all_messages)} 条消息，本次之后 {len(recent)} 条，有效 text {len(text_msgs)} 条", flush=True)

        if text_msgs:
            return text_msgs[-1].get("text", "")
        return ""

    finally:
        Path(task_file).unlink(missing_ok=True)


# ── 对外接口 ───────────────────────────────────────────────────────

def generate_report(
    market_data: list[dict[str, Any]],
    report_date: datetime | None = None,
    review_memory: str = "",
    **kwargs,
) -> str:
    """
    通过 CodeFlicker Agent 生成期货执行计划报告
    Agent 会自行使用 web_search 搜索新闻，无需外部传入新闻数据

    Args:
        market_data:    K 线数据列表
        report_date:    报告日期
        review_memory:  昨日复盘结论（可选），注入 Prompt 作为背景参考

    Returns:
        str: Markdown 报告全文
    """
    if report_date is None:
        report_date = datetime.now()

    date_str     = report_date.strftime("%Y-%m-%d")
    datetime_str = report_date.strftime("%Y-%m-%d %H:%M:%S")

    kline_section, bar_days = _format_kline_section(market_data)

    # 动态生成品种小节标题占位符
    symbol_sections = []
    for item in market_data:
        if item.get("bars"):
            symbol_sections.append(f"### {item.get('name', '')}（{item.get('symbol', '')}）")
    symbol_sections_placeholder = "\n".join(symbol_sections) if symbol_sections else "（无有效品种数据）"

    # 将昨日复盘结论注入 Prompt（如有）
    review_section = ""
    if review_memory.strip():
        review_section = f"""
## 背景参考：昨日复盘结论

> 以下是对昨日执行计划的复盘，请在今日分析时参考其中的改进建议和持续跟踪品种：

{review_memory[:2000]}

---
"""

    prompt = review_section + TASK_PROMPT_TEMPLATE.format(
        date=date_str,
        datetime_str=datetime_str,
        bar_days=bar_days,
        kline_section=kline_section,
        symbol_sections_placeholder=symbol_sections_placeholder,
    )

    session_id = _get_or_create_session("期货执行计划Agent")
    report     = _send_task_and_wait(session_id, prompt, timeout=900)

    if not report:
        print("  ⚠️  Agent 无响应，输出原始数据摘要", flush=True)
        return (
            f"# 期货每日执行计划 [{date_str}]\n\n"
            f"> ⚠️ Agent 未返回分析结果\n\n"
            f"## K 线数据\n\n{kline_section}"
        )

    return report


def save_report(report: str, reports_dir: Path, report_date: datetime | None = None) -> Path:
    """保存报告到 reports/ 目录"""
    if report_date is None:
        report_date = datetime.now()

    reports_dir.mkdir(parents=True, exist_ok=True)
    filename    = report_date.strftime("%Y%m%d") + ".md"
    output_path = reports_dir / filename
    output_path.write_text(report, encoding="utf-8")
    return output_path
