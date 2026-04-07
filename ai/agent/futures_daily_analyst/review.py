"""
昨日报告复盘模块
在每日生成新报告之前，先对昨日报告进行复盘：
  1. 找到昨日报告
  2. 结合今日实际 K 线，让 Agent 对比"昨日预测 vs 今日实际"
  3. 生成精简的反思 Memory（300 字以内的 tips），保存到 memories/
  4. 返回 tips 供今日报告注入背景
"""

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# agent-session-controller 脚本目录
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "agent-session-controller" / "scripts"
DUET_API_URL = "http://localhost:3459"

MEMORY_DIR  = Path(__file__).parent / "memories"
REPORTS_DIR = Path(__file__).parent / "reports"

# ── Prompt：目标是生成精简可用的反思 tips ──────────────────────────
REVIEW_PROMPT_TEMPLATE = """请完成一次期货复盘，生成精简的反思 Memory 供今日分析使用。

## 昨日执行计划（{yesterday}）

{yesterday_report}

## 今日实际 K 线（{today}）

{kline_section}

---

对比昨日报告的操作建议与今日实际涨跌，找出哪里判断对了、哪里判断错了。

**直接输出以下格式，不需要任何额外说明：**

复盘：{yesterday} → {today}

命中：
- [品种] 预测方向 → 实际走势，对在哪（一句话）

失误：
- [品种] 预测方向 → 实际走势，错在哪（一句话）

今日 tips：
- [具体可操作的建议，例如"MA888 持仓持续流出，不宜追多"]
- [另一条 tip]
- [另一条 tip]（共 2-3 条）

注意：
- 总字数不超过 300 字
- tips 必须具体到品种和价位/信号，避免"注意风险"这类空话
- 若昨日数据不足（节假日/数据缺失），命中/失误写"无"，tips 直接基于今日K线数据提炼
"""


def _run_script(script_name: str, *args: str) -> dict:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return {"success": False, "error": f"脚本不存在：{script_path}"}
    result = subprocess.run(
        ["/bin/bash", str(script_path), *args],
        capture_output=True, text=True,
        env={**os.environ, "DUET_API_URL": DUET_API_URL},
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"success": False, "error": result.stdout + result.stderr}


def _get_or_create_session(session_name: str = "期货执行计划Agent") -> str:
    resp     = _run_script("session-list.sh")
    sessions = resp.get("data", {}).get("sessionList", [])
    for s in sessions:
        if s.get("sessionName") == session_name:
            return s["sessionId"]
    resp = _run_script("session-create.sh", session_name, "agent")
    sid  = resp.get("data", {}).get("sessionId", "")
    if not sid:
        raise RuntimeError(f"创建 Session 失败：{resp}")
    return sid


def _send_and_wait(session_id: str, prompt: str, timeout: int = 180) -> str:
    """发送复盘 Prompt 并等待回复，返回 tips 文本"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt)
        task_file = f.name

    try:
        # 在发送之前记录时间戳，留 2 秒余量，防止消息 ts 早于 send_ts
        send_ts   = int(time.time() * 1000) - 2000
        send_resp = _run_script("task-send.sh", session_id, "--file", task_file, "agent")
        if not send_resp.get("success"):
            return ""

        time.sleep(3)

        deadline = time.time() + timeout
        last_dot = time.time()
        while time.time() < deadline:
            status = _run_script("session-status.sh", session_id)
            data   = status.get("data", {})

            if time.time() - last_dot >= 10:
                print(".", end="", flush=True)
                last_dot = time.time()

            if data.get("waitingForUserInput"):
                ask_type = data.get("askType", "command")
                _run_script("task-respond.sh", session_id, "approve", ask_type)
                time.sleep(2)
                continue

            if not data.get("isRunning", True) and data.get("lastMessageTs", 0) >= send_ts:
                print(f"\n  ✓ 复盘完成", flush=True)
                break

            time.sleep(5)
        else:
            print(f"\n  ⚠️  复盘超时（{timeout}s）", flush=True)

        # 拉取回复
        search_opts = json.dumps({
            "options": {"limit": 100, "order": "asc"},
            "textLimits": {"perMessage": 5000, "total": 20000},
        })
        msg_resp  = _run_script("messages-search.sh", session_id, search_opts)
        all_msgs  = msg_resp.get("data", {}).get("messages", [])
        recent    = [m for m in all_msgs if m.get("ts", 0) >= send_ts]
        text_msgs = [
            m for m in recent
            if m.get("say") == "text" and not m.get("partial", False) and m.get("text", "").strip()
        ]
        return text_msgs[-1].get("text", "") if text_msgs else ""

    finally:
        Path(task_file).unlink(missing_ok=True)


def find_yesterday_report(today: datetime) -> tuple[Path | None, str]:
    """查找最近一份报告（向前最多找 7 天，兼容节假日），返回 (路径, 内容)"""
    for delta in range(1, 8):
        candidate = today - timedelta(days=delta)
        path = REPORTS_DIR / candidate.strftime("%Y%m%d.md")
        if path.exists():
            return path, path.read_text(encoding="utf-8")
    return None, ""


def run_review(
    market_data: list[dict[str, Any]],
    report_date: datetime | None = None,
) -> str:
    """
    执行复盘流程：
      1. 找昨日报告
      2. 结合今日 K 线让 Agent 生成精简反思 tips
      3. 保存到 memories/review_YYYYMMDD.md
    返回 tips 文本（供今日报告 Prompt 注入）
    """
    if report_date is None:
        report_date = datetime.now()

    today_str = report_date.strftime("%Y-%m-%d")

    # ── 找昨日报告 ────────────────────────────────────────────────
    report_path, yesterday_report = find_yesterday_report(report_date)
    if not report_path:
        print("  [复盘] 未找到历史报告，跳过", flush=True)
        return ""

    yesterday_str = report_path.stem                                      # "20260406"
    yesterday_fmt = f"{yesterday_str[:4]}-{yesterday_str[4:6]}-{yesterday_str[6:]}"
    print(f"  [复盘] 对比昨日报告：{report_path.name} → 今日 {today_str}", flush=True)

    # ── 格式化今日 K 线 ───────────────────────────────────────────
    from report_generator import _format_kline_section
    kline_section, _ = _format_kline_section(market_data)

    # ── 构建 Prompt（昨日报告截取前 6000 字，避免过长）────────────
    prompt = REVIEW_PROMPT_TEMPLATE.format(
        yesterday=yesterday_fmt,
        today=today_str,
        yesterday_report=yesterday_report[:6000],
        kline_section=kline_section,
    )

    # ── 发给 Agent ────────────────────────────────────────────────
    print(f"  [复盘] 发送给 Agent 生成反思 tips...", flush=True)
    session_id  = _get_or_create_session("期货执行计划Agent")
    review_text = _send_and_wait(session_id, prompt, timeout=180)

    if not review_text:
        print("  [复盘] Agent 未返回结果，跳过", flush=True)
        return ""

    # ── 保存 memories/ ──────────────────────────────────────────────
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    memory_file = MEMORY_DIR / f"review_{yesterday_str}.md"
    memory_file.write_text(review_text, encoding="utf-8")
    print(f"  [复盘] tips 已保存：{memory_file}", flush=True)

    return review_text


def load_latest_memory(report_date: datetime | None = None) -> str:
    """
    加载最近一份复盘 tips，注入今日报告的 Prompt 背景
    只返回最新一份（不超过 800 字，保持精简）
    """
    if report_date is None:
        report_date = datetime.now()

    if not MEMORY_DIR.exists():
        return ""

    files = sorted(MEMORY_DIR.glob("review_*.md"), reverse=True)
    if not files:
        return ""

    content = files[0].read_text(encoding="utf-8").strip()
    return content[:800]
