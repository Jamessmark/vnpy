"""
LLM 决策顾问框架 — 通用版

提供多源数据融合（技术因子 + 新闻资讯）→ LLM 生成交易建议的通用流程。
与交易所无关；各交易所 Agent 只需传入自定义 prompt 模板即可复用。

用法示例：
    from ai.agent.common.llm_advisor import LLMAdvisor

    advisor = LLMAdvisor(exchange_name="大商所")
    report  = advisor.generate_decision_report(
        variety="m", variety_name="豆粕",
        alpha_features=..., sentiment_result=...
    )
    advisor.generate_batch_report([report])
"""
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# CodeFlicker Agent Session Controller 工具函数
# ─────────────────────────────────────────────────────────────────────────────

_SCRIPTS_DIR = Path(__file__).parents[3] / "ai" / "skills" / "agent-session-controller" / "scripts"
_DUET_API_URL = "http://localhost:3459"


def _run_script(script_name: str, *args: str) -> dict:
    script_path = _SCRIPTS_DIR / script_name
    if not script_path.exists():
        return {"success": False, "error": f"脚本不存在：{script_path}"}
    result = subprocess.run(
        ["/bin/bash", str(script_path), *args],
        capture_output=True, text=True,
        env={**os.environ, "DUET_API_URL": _DUET_API_URL},
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"success": False, "error": result.stdout + result.stderr}


def _get_or_create_session(session_name: str) -> str:
    resp = _run_script("session-list.sh")
    for s in resp.get("data", {}).get("sessionList", []):
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


def _send_task_and_wait(session_id: str, prompt: str, timeout: int = 300) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt)
        task_file = f.name
    try:
        send_ts = int(time.time() * 1000) - 2000
        print("  [Agent] 发送决策分析任务...", flush=True)
        send_resp = _run_script("task-send.sh", session_id, "--file", task_file, "agent")
        if not send_resp.get("success"):
            raise RuntimeError(f"发送任务失败：{send_resp}")

        time.sleep(3)
        print(f"  [Agent] 等待 AI 分析（最长 {timeout}s）...", flush=True)
        deadline = time.time() + timeout
        last_dot = time.time()

        while time.time() < deadline:
            status_resp = _run_script("session-status.sh", session_id)
            data        = status_resp.get("data", {})
            if time.time() - last_dot >= 10:
                print(".", end="", flush=True)
                last_dot = time.time()
            if data.get("waitingForUserInput", False):
                ask_type = data.get("askType", "")
                print(f"\n  [Agent] 等待审批（{ask_type}），自动批准...", flush=True)
                _run_script("task-respond.sh", session_id, "approve", ask_type or "command")
                time.sleep(2)
                continue
            if not data.get("isRunning", True) and data.get("lastMessageTs", 0) >= send_ts:
                print("\n  ✓ 分析完成", flush=True)
                break
            time.sleep(5)
        else:
            print(f"\n  ⚠️ 等待超时（{timeout}s）", flush=True)

        search_options = json.dumps({
            "options": {"limit": 20, "order": "desc"},
            "textLimits": {"perMessage": 30000, "total": 150000},
        })
        msg_resp     = _run_script("messages-search.sh", session_id, search_options)
        all_messages = msg_resp.get("data", {}).get("messages", [])
        all_messages.reverse()
        recent    = [m for m in all_messages if m.get("ts", 0) >= send_ts]
        text_msgs = [
            m for m in recent
            if m.get("say") == "text" and not m.get("partial", False) and m.get("text", "").strip()
        ]
        return text_msgs[-1].get("text", "") if text_msgs else ""
    finally:
        Path(task_file).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 默认决策 Prompt 模板
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_PROMPT_TEMPLATE = """你是一位专业的商品期货分析师。请基于以下数据，生成 {exchange_name} 品种的交易决策建议。

## 品种信息
- 品种代码：{variety}
- 品种名称：{variety_name}
- 分析日期：{date}

## 技术分析数据（Alpha158因子）
{alpha_features_text}

## 近期新闻资讯（共 {news_count} 条）
{news_text}

## 任务要求
请综合以上技术面数据和新闻资讯，生成如下格式的决策建议：

### 市场分析
（2-3句话分析当前市场状态，结合新闻中的关键信息）

### 技术面判断
（基于RSI、布林带、均线等指标判断）

### 新闻情绪判断
（基于上述新闻内容，判断当前市场情绪：偏多/偏空/中性，并说明主要利多和利空因素）

### 综合评分
给出综合评分（-100到100）：
- 正值表示看多，负值表示看空
- 解释评分的依据（技术面+新闻面各占比）

### 交易建议
- **方向**：做多 / 做空 / 观望
- **理由**：一句话说明依据
- **风险提示**：1-2条需要注意的风险

### 关注价位
- 支撑位：xxx
- 压力位：xxx
- 止损位：xxx

请直接输出分析结果，不需要额外的格式说明。
"""


# ─────────────────────────────────────────────────────────────────────────────
# LLMAdvisor 主类
# ─────────────────────────────────────────────────────────────────────────────

class LLMAdvisor:
    """LLM 决策顾问（通用版）"""

    def __init__(
        self,
        exchange_name: str = "商品期货",
        session_name: Optional[str] = None,
        report_dir: Optional[Path] = None,
        prompt_template: Optional[str] = None,
    ):
        self.exchange_name   = exchange_name
        self.prompt_template = prompt_template or _DEFAULT_PROMPT_TEMPLATE
        self.report_dir      = report_dir or (Path(__file__).parent.parent / "reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        _name = session_name or f"{exchange_name}决策Agent"
        self.session_id = _get_or_create_session(_name)

    def generate_decision_report(
        self,
        variety: str,
        variety_name: str,
        alpha_features: Dict,
        sentiment_result: Dict,
        target_date: Optional[date] = None,
    ) -> Dict:
        """生成单品种决策报告，返回包含 LLM 完整输出和输入 Prompt 的字典"""
        if target_date is None:
            target_date = alpha_features.get("_date", date.today())

        alpha_text = "\n".join(
            f"- {k}: {v}"
            for k, v in alpha_features.items()
            if not k.startswith("_")
        ) or "无"

        news_list = sentiment_result.get("news", [])
        if news_list:
            news_lines = []
            for i, n in enumerate(news_list, 1):
                title    = n.get("title", "").strip()
                source   = n.get("source", "")
                pub_time = (n.get("publish_time") or "")[:10]
                content  = (n.get("content") or "").strip()[:200]
                news_lines.append(
                    f"{i}. [{pub_time}][{source}] {title}"
                    + (f"\n   摘要：{content}" if content else "")
                )
            news_text = "\n".join(news_lines)
        else:
            news_text = "（未获取到新闻，请仅依据技术指标分析）"

        prompt = self.prompt_template.format(
            exchange_name       = self.exchange_name,
            variety             = variety,
            variety_name        = variety_name,
            date                = target_date.isoformat(),
            alpha_features_text = alpha_text,
            news_count          = len(news_list),
            news_text           = news_text,
        )

        llm_response = ""
        try:
            llm_response = _send_task_and_wait(self.session_id, prompt, timeout=120)
        except Exception as e:
            print(f"  ⚠️ Agent 调用失败：{e}")

        return {
            "variety":          variety,
            "variety_name":     variety_name,
            "date":             target_date.isoformat(),
            "timestamp":        datetime.now().isoformat(),
            "exchange":         self.exchange_name,
            "close_price":      alpha_features.get("_close", 0),
            "llm_prompt":       prompt,
            "llm_response":     llm_response,
        }

    @staticmethod
    def _extract_score(llm_response: str) -> float:
        """
        从 LLM 返回文本中提取综合评分（-100 ~ 100）。
        只在 '### 综合评分' 段落正文中查找，跳过含「到」的范围说明行。
        找不到则返回 0.0。
        """
        # 定位 '### 综合评分' 段落（到下一个 ### 或文末）
        block = re.search(
            r"###\s*综合评分[^\n]*\n(.*?)(?=\n###|\Z)",
            llm_response, re.S
        )
        if not block:
            return 0.0
        text = block.group(1)

        for line in text.splitlines():
            # 跳过范围说明行，如「-100到100」「（-100到100）」
            if "到" in line and re.search(r"-?\d+到\d+", line):
                continue
            # 优先匹配「评分：+72」「: -45」「= 80」
            m = re.search(r"[：:=]\s*([+-]?\d+(?:\.\d+)?)", line)
            if not m:
                # 其次匹配「+72分」「-45分」
                m = re.search(r"([+-]\d+(?:\.\d+)?)\s*分", line)
            if not m:
                # 再次匹配独立数字（不含「到」已过滤）
                m = re.search(r"\b([+-]?\d{1,3}(?:\.\d+)?)\b", line)
            if m:
                try:
                    val = float(m.group(1))
                    if -100 <= val <= 100:
                        return val
                except ValueError:
                    pass
        return 0.0

    @staticmethod
    def _extract_direction(llm_response: str) -> str:
        """从 LLM 返回中提取操作方向（做多/做空/观望）"""
        # 只从 '### 交易建议' 段落中提取，避免误匹配模板占位符
        block = re.search(
            r"###\s*交易建议[^\n]*\n(.*?)(?=\n###|\Z)",
            llm_response, re.S
        )
        text = block.group(1) if block else ""
        m = re.search(r"\*{0,2}方向\*{0,2}[：:]\s*([^\n，,/／]+)", text)
        if m:
            direction = m.group(1).strip()
            # 排除占位符「做多 / 做空 / 观望」
            if "/" not in direction and "／" not in direction:
                return direction
        # fallback：在交易建议段落里找第一个明确方向词
        for word in ["做多", "做空", "观望"]:
            if word in text:
                return word
        return "—"

    @staticmethod
    def _extract_reason(llm_response: str) -> str:
        """从 LLM 返回中提取一句话理由"""
        m = re.search(r"\*{0,2}理由\*{0,2}[：:]\s*([^\n]{1,80})", llm_response)
        if m:
            return m.group(1).strip()
        return ""

    def generate_batch_report(
        self,
        reports: List[Dict],
        output_file: Optional[str] = None,
    ) -> str:
        """
        生成 Markdown 报告：
          - 头部：按综合评分绝对值由高到低的核心建议摘要表
          - 正文：各品种完整 LLM 分析（同样按绝对值排序）+ 折叠 Prompt
        """
        if not reports:
            return "# 决策报告\n\n暂无数据"

        report_date = reports[0].get("date", date.today().isoformat())
        exchange    = reports[0].get("exchange", self.exchange_name)

        # 为每个报告附加提取到的评分/方向/理由，并按 |score| 降序排列
        enriched = []
        for r in reports:
            resp  = r.get("llm_response", "")
            score = self._extract_score(resp)
            enriched.append({
                **r,
                "_score":     score,
                "_direction": self._extract_direction(resp),
                "_reason":    self._extract_reason(resp),
            })
        enriched.sort(key=lambda x: abs(x["_score"]), reverse=True)

        # ── 报告头部 ──────────────────────────────────────────────────────────
        md  = f"# {exchange} 品种决策报告\n\n"
        md += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += f"**报告日期**: {report_date}\n\n"
        md += "---\n\n"

        # ── 核心建议摘要表（按评分绝对值排序）────────────────────────────────
        md += "## 📊 核心建议速览\n\n"
        md += "| 品种 | 收盘价 | 综合评分 | 方向 | 核心理由 |\n"
        md += "|------|--------|----------|------|----------|\n"
        for r in enriched:
            vname  = r.get("variety_name", "")
            close  = r.get("close_price", 0)
            score  = r["_score"]
            direc  = r["_direction"]
            reason = r["_reason"] or "—"
            score_str = f"{score:+.0f}" if score != 0 else "0"
            md += f"| {vname} | {close:.2f} | {score_str} | {direc} | {reason} |\n"
        md += "\n---\n\n"

        # ── 各品种详细分析 ────────────────────────────────────────────────────
        for r in enriched:
            vname = r.get("variety_name", "")
            close = r.get("close_price", 0)
            score = r["_score"]
            score_str = f"{score:+.0f}" if score != 0 else "0"
            md += f"## {vname}（收盘价: {close:.2f} | 综合评分: {score_str}）\n\n"

            llm_resp = r.get("llm_response", "")
            if llm_resp:
                md += llm_resp.strip() + "\n\n"
            else:
                md += "_LLM 未返回分析结果_\n\n"

            llm_prompt = r.get("llm_prompt", "")
            if llm_prompt:
                md += f"<details>\n<summary>📤 发送至 LLM 的完整输入 ({vname})</summary>\n\n"
                md += f"```\n{llm_prompt}\n```\n\n</details>\n\n"

            md += "---\n\n"

        if output_file is None:
            output_file = f"decision_report_{report_date}.md"

        output_path = self.report_dir / output_file
        output_path.write_text(md, encoding="utf-8")
        print(f"✅ 报告已保存: {output_path}")
        return md
