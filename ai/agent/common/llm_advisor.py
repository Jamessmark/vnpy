"""
LLM 决策顾问框架 — 通用版

提供多源数据融合（技术因子 + 新闻情绪）→ LLM 生成交易建议的通用流程。
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
from typing import Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# CodeFlicker Agent Session Controller 工具函数
# ─────────────────────────────────────────────────────────────────────────────

# ai/agent/common/llm_advisor.py → parents[0]=common/, parents[1]=agent/, parents[2]=ai/, parents[3]=vnpy/
_SCRIPTS_DIR = Path(__file__).parents[3] / "ai" / "skills" / "agent-session-controller" / "scripts"
_DUET_API_URL = "http://localhost:3459"


def _run_script(script_name: str, *args: str) -> dict:
    """调用 agent-session-controller 的 shell 脚本，返回解析后的 JSON"""
    script_path = _SCRIPTS_DIR / script_name
    if not script_path.exists():
        return {"success": False, "error": f"脚本不存在：{script_path}"}

    result = subprocess.run(
        ["/bin/bash", str(script_path), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "DUET_API_URL": _DUET_API_URL},
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"success": False, "error": result.stdout + result.stderr}


def _get_or_create_session(session_name: str) -> str:
    """优先复用已有同名 Session，不存在则新建，返回 session_id"""
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
    """
    把 prompt 写入临时文件，通过 task-send.sh 发给 Agent，
    等待完成后拉取回复内容，返回报告文本。
    """
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
        deadline  = time.time() + timeout
        last_dot  = time.time()

        while time.time() < deadline:
            status_resp = _run_script("session-status.sh", session_id)
            data        = status_resp.get("data", {})
            is_running  = data.get("isRunning", True)
            last_msg_ts = data.get("lastMessageTs", 0)

            if time.time() - last_dot >= 10:
                print(".", end="", flush=True)
                last_dot = time.time()

            if data.get("waitingForUserInput", False):
                ask_type = data.get("askType", "")
                print(f"\n  [Agent] 等待审批（{ask_type}），自动批准...", flush=True)
                _run_script("task-respond.sh", session_id, "approve", ask_type or "command")
                time.sleep(2)
                continue

            if not is_running and last_msg_ts >= send_ts:
                print("\n  ✓ 分析完成", flush=True)
                break

            time.sleep(5)
        else:
            print(f"\n  ⚠️ 等待超时（{timeout}s）", flush=True)

        # 拉取消息
        search_options = json.dumps({
            "options": {"limit": 20, "order": "desc"},
            "textLimits": {"perMessage": 30000, "total": 150000},
        })
        msg_resp    = _run_script("messages-search.sh", session_id, search_options)
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
# 默认决策 Prompt 模板（可被子类/调用方替换）
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_PROMPT_TEMPLATE = """你是一位专业的商品期货分析师。请基于以下数据，生成 {exchange_name} 品种的交易决策建议。

## 品种信息
- 品种代码：{variety}
- 品种名称：{variety_name}
- 分析日期：{date}

## 技术分析数据（Alpha158因子）
{alpha_features_text}

## 新闻情绪分析
- 情绪标签：{sentiment_label}
- 情绪得分：{sentiment_score}（范围 -1 到 1）
- 摘要：{sentiment_summary}

## 任务要求
请综合以上数据，生成如下格式的决策建议：

### 市场分析
（2-3句话分析当前市场状态）

### 技术面判断
（基于RSI、布林带、均线等指标判断）

### 综合评分
给出综合评分（-100到100）：
- 正值表示看多，负值表示看空
- 解释评分的依据

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
    """
    LLM 决策顾问（通用版）

    支持规则模式（内置算分逻辑）和 Agent 模式（CodeFlicker Agent）。
    各交易所 Agent 可通过 exchange_name / prompt_template 参数定制化。
    """

    def __init__(
        self,
        exchange_name: str = "商品期货",
        session_name: Optional[str] = None,
        use_agent: bool = True,
        report_dir: Optional[Path] = None,
        prompt_template: Optional[str] = None,
    ):
        """
        Args:
            exchange_name:   交易所名称（用于 prompt 中，如 "大商所"、"上期所"）
            session_name:    CodeFlicker Agent Session 名称；None 则自动生成
            use_agent:       True = 优先使用 CodeFlicker Agent；False = 仅使用规则模式
            report_dir:      报告输出目录；None 则使用调用文件同级的 reports/ 目录
            prompt_template: 自定义 prompt 模板；None 则使用内置默认模板
        """
        self.exchange_name   = exchange_name
        self.prompt_template = prompt_template or _DEFAULT_PROMPT_TEMPLATE
        self.report_dir      = report_dir or (Path(__file__).parent.parent / "reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.use_agent       = use_agent

        if self.use_agent:
            _name = session_name or f"{exchange_name}决策Agent"
            try:
                self.session_id = _get_or_create_session(_name)
            except Exception as e:
                print(f"  ⚠️ Agent Session 初始化失败，将使用规则模式：{e}")
                self.use_agent = False

    # ── 主入口 ────────────────────────────────────────────────────────────────

    def generate_decision_report(
        self,
        variety: str,
        variety_name: str,
        alpha_features: Dict,
        sentiment_result: Dict,
        target_date: Optional[date] = None,
    ) -> Dict:
        """
        生成单品种决策报告。

        Args:
            variety:          品种代码
            variety_name:     品种名称
            alpha_features:   Alpha158 特征字典
            sentiment_result: 新闻情绪分析结果
            target_date:      目标日期

        Returns:
            决策报告字典
        """
        if target_date is None:
            target_date = alpha_features.get("_date", date.today())

        if self.use_agent:
            return self._generate_with_agent(
                variety, variety_name, alpha_features, sentiment_result, target_date
            )
        return self._generate_with_rules(
            variety, variety_name, alpha_features, sentiment_result, target_date
        )

    # ── Agent 模式 ────────────────────────────────────────────────────────────

    def _generate_with_agent(
        self,
        variety: str,
        variety_name: str,
        alpha_features: Dict,
        sentiment_result: Dict,
        target_date: date,
    ) -> Dict:
        alpha_text = "\n".join(
            f"- {k}: {v}"
            for k, v in alpha_features.items()
            if not k.startswith("_")
        ) or "无"

        prompt = self.prompt_template.format(
            exchange_name   = self.exchange_name,
            variety         = variety,
            variety_name    = variety_name,
            date            = target_date.isoformat(),
            alpha_features_text = alpha_text,
            sentiment_label = sentiment_result.get("sentiment_label", "中性"),
            sentiment_score = sentiment_result.get("sentiment_score", 0),
            sentiment_summary = sentiment_result.get("summary", "无"),
        )

        try:
            llm_response = _send_task_and_wait(self.session_id, prompt, timeout=120)
        except Exception as e:
            print(f"  ⚠️ Agent 调用失败，回退到规则模式：{e}")
            return self._generate_with_rules(variety, variety_name, alpha_features, sentiment_result, target_date)

        if not llm_response:
            print("  ⚠️ Agent 无响应，回退到规则模式")
            return self._generate_with_rules(variety, variety_name, alpha_features, sentiment_result, target_date)

        score, suggestion, action, risks = self._parse_llm_response(llm_response)
        close_price = alpha_features.get("_close", 0)
        volume      = alpha_features.get("_volume", 0)
        return_5d   = alpha_features.get("return_5d", 0)
        return_20d  = alpha_features.get("return_20d", 0)

        # 完整 alpha 特征（调试用）
        alpha_features_full = {
            k: v for k, v in alpha_features.items() if not str(k).startswith("_")
        }

        # 完整情绪结果（调试用，包含原始新闻列表）
        sentiment_full = {
            k: v for k, v in sentiment_result.items()
            if k not in ("variety", "variety_name")
        }

        return {
            "variety":      variety,
            "variety_name": variety_name,
            "date":         target_date.isoformat(),
            "timestamp":    datetime.now().isoformat(),
            "exchange":     self.exchange_name,
            "source":       "agent",
            "market_data": {
                "close_price": close_price,
                "volume":      volume,
                "return_5d":   f"{return_5d * 100:.2f}%",
                "return_20d":  f"{return_20d * 100:.2f}%",
            },
            "technical": {
                "rsi_14":             round(alpha_features.get("rsi_14", 50), 2),
                "bollinger_position":  round(alpha_features.get("bollinger_position", 0.5), 2),
                "volume_ratio_5d":     round(alpha_features.get("volume_ratio_5", 1.0), 2),
            },
            "sentiment": {
                "score":      sentiment_result.get("sentiment_score", 0),
                "label":      sentiment_result.get("sentiment_label", "中性"),
                "summary":   sentiment_result.get("summary", ""),
                "key_points": sentiment_result.get("key_points", [])[:3],
            },
            "decision": {
                "综合得分":    score,
                "market_view": suggestion,
                "action":      action,
                "risks":       risks,
            },
            # ── 调试信息 ──────────────────────────────────────────────────────
            "alpha_features_full": alpha_features_full,
            "sentiment_full":     sentiment_full,
            "llm_prompt":        prompt,
            "llm_raw_response":  llm_response,
        }

    def _parse_llm_response(self, response: str) -> Tuple:
        """从 LLM 文本中提取评分、建议、方向、风险"""
        score      = 0
        suggestion = "中性"
        action     = "观望为主"
        risks: List[str] = []

        for pattern in [r"综合评分[：:]\s*([+-]?\d+)", r"评分[：:]\s*([+-]?\d+)", r"综合得分[：:]\s*([+-]?\d+)"]:
            m = re.search(pattern, response)
            if m:
                try:
                    score = int(m.group(1))
                    break
                except ValueError:
                    pass

        if any(w in response for w in ["强烈看多", "建议多头", "做多", "多头"]):
            suggestion, action = "强烈看多", "建议多头建仓"
        elif any(w in response for w in ["偏多", "看多"]):
            suggestion, action = "偏多", "可适量做多"
        elif any(w in response for w in ["强烈看空", "建议空头", "做空", "空头"]):
            suggestion, action = "强烈看空", "建议空头建仓"
        elif any(w in response for w in ["偏空", "看空"]):
            suggestion, action = "偏空", "可适量做空"

        for m in re.finditer(r"风险[提示注意警示][：:]?\s*([^#\n]+)", response):
            risk_text = m.group(1).strip()
            if risk_text and len(risk_text) < 100:
                risks.append(risk_text)

        return score, suggestion, action, risks[:3]

    # ── 规则模式 ──────────────────────────────────────────────────────────────

    def _generate_with_rules(
        self,
        variety: str,
        variety_name: str,
        alpha_features: Dict,
        sentiment_result: Dict,
        target_date: date,
    ) -> Dict:
        """内置规则打分（不依赖 LLM）"""
        close_price     = alpha_features.get("_close", 0)
        volume          = alpha_features.get("_volume", 0)
        return_5d       = alpha_features.get("return_5d", 0)
        return_20d      = alpha_features.get("return_20d", 0)
        rsi             = alpha_features.get("rsi_14", 50)
        bollinger_pos   = alpha_features.get("bollinger_position", 0.5)
        volume_ratio_5  = alpha_features.get("volume_ratio_5", 1.0)
        sentiment_score = sentiment_result.get("sentiment_score", 0)
        sentiment_label = sentiment_result.get("sentiment_label", "中性")

        score = 0
        # 趋势 (40%)
        if return_5d > 0.03:   score += 20
        elif return_5d > 0.01: score += 10
        elif return_5d < -0.03: score -= 20
        elif return_5d < -0.01: score -= 10
        if return_20d > 0.1:   score += 20
        elif return_20d > 0.05: score += 10
        elif return_20d < -0.1: score -= 20
        elif return_20d < -0.05: score -= 10
        # 技术指标 (30%)
        if rsi < 30:   score += 15
        elif rsi < 40: score += 8
        elif rsi > 70: score -= 15
        elif rsi > 60: score -= 8
        if bollinger_pos < 0.2:   score += 10
        elif bollinger_pos > 0.8: score -= 10
        # 成交量 (15%)
        if volume_ratio_5 > 1.5:
            score += 8 if return_5d > 0 else -8
        # 情绪 (15%)
        score += int(sentiment_score * 15)

        if score > 40:      suggestion, action = "强烈看多", "建议多头建仓"
        elif score > 20:    suggestion, action = "偏多",     "可适量做多"
        elif score > -20:   suggestion, action = "中性",     "观望为主"
        elif score > -40:   suggestion, action = "偏空",     "可适量做空"
        else:               suggestion, action = "强烈看空", "建议空头建仓"

        risks: List[str] = []
        if abs(return_5d) > 0.05:
            risks.append("短期波动较大，注意控制仓位")
        if rsi > 70 or rsi < 30:
            risks.append("技术指标显示超买/超卖，可能反转")
        if volume_ratio_5 < 0.5:
            risks.append("成交量萎缩，趋势可能不可持续")
        if sentiment_score < -0.5:
            risks.append("新闻面偏空，谨慎做多")

        # ── 调试信息 ────────────────────────────────────────────────────
        alpha_features_full = {
            k: v for k, v in alpha_features.items() if not str(k).startswith("_")
        }
        sentiment_full = {
            k: v for k, v in sentiment_result.items()
            if k not in ("variety", "variety_name")
        }

        return {
            "variety":      variety,
            "variety_name": variety_name,
            "date":         target_date.isoformat(),
            "timestamp":    datetime.now().isoformat(),
            "exchange":     self.exchange_name,
            "source":       "rules",
            "market_data": {
                "close_price": close_price,
                "volume":      volume,
                "return_5d":   f"{return_5d * 100:.2f}%",
                "return_20d":  f"{return_20d * 100:.2f}%",
            },
            "technical": {
                "rsi_14":             round(rsi, 2),
                "bollinger_position": round(bollinger_pos, 2),
                "volume_ratio_5d":    round(volume_ratio_5, 2),
            },
            "sentiment": {
                "score":      sentiment_score,
                "label":      sentiment_label,
                "summary":    sentiment_result.get("summary", ""),
                "key_points": sentiment_result.get("key_points", [])[:3],
            },
            # ── 调试信息 ──────────────────────────────────────────────────────
            "alpha_features_full": alpha_features_full,
            "sentiment_full":     sentiment_full,
            "llm_prompt":        None,
            "llm_raw_response":  None,
        }

    # ── 批量报告 ──────────────────────────────────────────────────────────────

    def generate_batch_report(
        self,
        reports: List[Dict],
        output_file: Optional[str] = None,
    ) -> str:
        """
        生成 Markdown 格式的批量决策报告并保存文件。

        Returns:
            报告内容字符串
        """
        if not reports:
            return "# 决策报告\n\n暂无数据"

        report_date = reports[0].get("date", date.today().isoformat())
        exchange    = reports[0].get("exchange", self.exchange_name)
        source_name = "CodeFlicker Agent" if reports[0].get("source") == "agent" else "规则引擎"

        md  = f"# {exchange} 品种决策报告\n\n"
        md += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += f"**报告日期**: {report_date}\n\n"
        md += f"**数据来源**: {source_name}\n\n"
        md += "---\n\n"

        md += "## 一、决策汇总\n\n"
        md += "| 品种 | 收盘价 | 5日涨幅 | 20日涨幅 | 情绪 | 综合得分 | 建议 |\n"
        md += "|------|--------|---------|----------|------|----------|------|\n"
        for r in reports:
            mkt = r.get("market_data", {})
            dec = r.get("decision", {})
            sen = r.get("sentiment", {})
            md += (
                f"| {r.get('variety_name', '')} "
                f"| {mkt.get('close_price', 0):.2f} "
                f"| {mkt.get('return_5d', '0%')} "
                f"| {mkt.get('return_20d', '0%')} "
                f"| {sen.get('label', '中性')} "
                f"| {dec.get('综合得分', 0)} "
                f"| {dec.get('market_view', '中性')} |\n"
            )

        md += "\n---\n\n## 二、详细分析\n\n"
        for r in reports:
            mkt = r.get("market_data", {})
            tec = r.get("technical", {})
            sen = r.get("sentiment", {})
            dec = r.get("decision", {})
            md += f"### {r.get('variety_name', '')}\n\n"
            md += "**市场数据**\n"
            md += f"- 收盘价: {mkt.get('close_price', 0):.2f}\n"
            md += f"- 5日涨幅: {mkt.get('return_5d', '0%')}\n"
            md += f"- 20日涨幅: {mkt.get('return_20d', '0%')}\n"
            md += f"- 成交量: {mkt.get('volume', 0):.0f}\n\n"
            md += "**技术指标**\n"
            md += f"- RSI(14): {tec.get('rsi_14', 50):.1f}\n"
            md += f"- 布林带位置: {tec.get('bollinger_position', 0.5):.2f}\n"
            md += f"- 成交量比率(5日): {tec.get('volume_ratio_5d', 1.0):.2f}\n\n"
            md += "**新闻情绪**\n"
            md += f"- 情绪标签: {sen.get('label', '中性')}\n"
            md += f"- 情绪得分: {sen.get('score', 0):.2f}\n"
            md += f"- 摘要: {sen.get('summary', '无')}\n\n"
            md += "**决策建议**\n"
            md += f"- 综合得分: {dec.get('综合得分', 0)}\n"
            md += f"- 市场观点: {dec.get('market_view', '中性')}\n"
            md += f"- 操作建议: {dec.get('action', '观望')}\n"
            if dec.get("risks"):
                md += "\n⚠️ 风险提示:\n"
                for risk in dec["risks"]:
                    md += f"- {risk}\n"
            if r.get("llm_raw_response"):
                md += "\n<details>\n<summary>🤖 Agent 原始分析</summary>\n\n"
                md += f"{r['llm_raw_response']}\n\n</details>\n"
            md += "\n---\n\n"

        # ── 三、调试信息 ────────────────────────────────────────────────────
        md += "## 三、调试信息\n\n"
        for r in reports:
            vname = r.get("variety_name", "")
            source = r.get("source", "?")

            # 1) Alpha158 全量因子
            md += f"<details>\n<summary>🔬 Alpha158 全量因子 ({vname})</summary>\n\n"
            alpha_full = r.get("alpha_features_full", {})
            if alpha_full:
                md += "| 指标名 | 值 |\n|------|------|\n"
                for k, v in sorted(alpha_full.items()):
                    try:
                        md += f"| {k} | {v:.6f} |\n"
                    except Exception:
                        md += f"| {k} | {v} |\n"
            else:
                md += "_无数据_\n"
            md += "\n</details>\n\n"

            # 2) 原始新闻列表
            md += f"<details>\n<summary>📰 原始新闻列表 ({vname})</summary>\n\n"
            sen_full = r.get("sentiment_full", {})
            news_list = sen_full.get("news", [])
            if news_list:
                for i, n in enumerate(news_list, 1):
                    md += f"**{i}. {n.get('title', '无标题')}**  \n"
                    md += f"   _时间_: {n.get('publish_time', 'N/A')} | "
                    md += f"_来源_: {n.get('source', 'N/A')}  \n"
                    content = (n.get("content") or "")[:300]
                    if content:
                        md += f"   内容: {content}...\n"
                    md += "\n"
            else:
                md += "_未获取到新闻_\n"
            md += "\n</details>\n\n"

            # 3) 情绪分析详情
            md += f"<details>\n<summary>🧠 情绪分析详情 ({vname})</summary>\n\n"
            if sen_full:
                for k, v in sen_full.items():
                    if k == "news":
                        continue
                    md += f"- **{k}**: {v}\n"
            else:
                md += "_无数据_\n"
            md += "\n</details>\n\n"

            # 4) 发送给 LLM 的完整 prompt
            md += f"<details>\n<summary>📤 发送至 LLM 的完整 Prompt ({vname})</summary>\n\n"
            llm_prompt = r.get("llm_prompt")
            if llm_prompt:
                md += f"```\n{llm_prompt}\n```\n\n"
            else:
                md += "_规则模式，未调用 LLM_\n\n"
            md += "\n</details>\n\n"

            # 5) LLM 原始响应
            md += f"<details>\n<summary>📥 LLM 原始响应 ({vname})</summary>\n\n"
            llm_resp = r.get("llm_raw_response")
            if llm_resp:
                md += f"```\n{llm_resp}\n```\n\n"
            else:
                md += "_规则模式，无 LLM 响应_\n\n"
            md += "\n</details>\n\n"

            md += "---\n\n"

        if output_file is None:
            output_file = f"decision_report_{report_date}.md"

        output_path = self.report_dir / output_file
        output_path.write_text(md, encoding="utf-8")
        print(f"✅ 报告已保存: {output_path}")
        return md


if __name__ == "__main__":
    advisor = LLMAdvisor(exchange_name="大商所", use_agent=False)

    alpha_features = {
        "_date":       date.today(),
        "_close":      3500.0,
        "_volume":     150000,
        "return_5d":   0.025,
        "return_20d":  0.08,
        "rsi_14":      65,
        "bollinger_position": 0.7,
        "volume_ratio_5":     1.3,
    }
    sentiment_result = {
        "sentiment_score": 0.4,
        "sentiment_label": "偏多",
        "summary":         "分析了10条新闻，整体情绪偏多",
        "key_points":      [],
    }

    report = advisor.generate_decision_report("m", "豆粕", alpha_features, sentiment_result)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    advisor.generate_batch_report([report])
