"""
LLM 决策顾问
融合Alpha158因子、新闻情绪等多源数据，通过大模型生成交易建议
"""
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, date
from typing import List, Dict, Optional
from pathlib import Path


# ── CodeFlicker Agent Session Controller ──────────────────────────────────

# llm_advisor.py 在 ai/agent/DCE/decision_engine/
# agent-session-controller 在 ai/skills/
SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "skills" / "agent-session-controller" / "scripts"
DUET_API_URL = "http://localhost:3459"


def _run_script(script_name: str, *args: str) -> dict:
    """调用 agent-session-controller 的 shell 脚本，返回解析后的 JSON"""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return {"success": False, "error": f"脚本不存在：{script_path}"}
    
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


def _get_or_create_session(session_name: str = "DCE决策Agent") -> str:
    """优先复用已有同名 Session，不存在则新建，返回 session_id"""
    resp = _run_script("session-list.sh")
    sessions = resp.get("data", {}).get("sessionList", [])
    for s in sessions:
        if s.get("sessionName") == session_name:
            sid = s["sessionId"]
            print(f"  [Agent] 复用已有 Session：{session_name}（{sid[:8]}...）")
            return sid

    resp = _run_script("session-create.sh", session_name, "agent")
    sid = resp.get("data", {}).get("sessionId", "")
    if not sid:
        raise RuntimeError(f"创建 Session 失败：{resp}")
    print(f"  [Agent] 新建 Session：{session_name}（{sid[:8]}...）")
    return sid


def _send_task_and_wait(session_id: str, prompt: str, timeout: int = 300) -> str:
    """
    把 prompt 写入临时文件，通过 task-send.sh 发给 Agent，
    等待完成后拉取回复内容，返回报告文本
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt)
        task_file = f.name

    try:
        send_ts = int(time.time() * 1000) - 2000

        print(f"  [Agent] 发送决策分析任务...", flush=True)
        send_resp = _run_script("task-send.sh", session_id, "--file", task_file, "agent")
        if not send_resp.get("success"):
            raise RuntimeError(f"发送任务失败：{send_resp}")

        time.sleep(3)

        print(f"  [Agent] 等待 AI 分析（最长 {timeout}s）...", flush=True)
        deadline = time.time() + timeout
        last_dot = time.time()
        
        while time.time() < deadline:
            status_resp = _run_script("session-status.sh", session_id)
            data = status_resp.get("data", {})
            is_running = data.get("isRunning", True)
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
                print(f"\n  ✓ 分析完成", flush=True)
                break

            time.sleep(5)
        else:
            print(f"\n  ⚠️ 等待超时（{timeout}s）", flush=True)

        # 拉取消息
        search_options = json.dumps({
            "options": {"limit": 20, "order": "desc"},
            "textLimits": {"perMessage": 30000, "total": 150000},
        })
        msg_resp = _run_script("messages-search.sh", session_id, search_options)
        all_messages = msg_resp.get("data", {}).get("messages", [])
        all_messages.reverse()

        recent = [m for m in all_messages if m.get("ts", 0) >= send_ts]
        text_msgs = [
            m for m in recent
            if m.get("say") == "text" and not m.get("partial", False) and m.get("text", "").strip()
        ]

        if text_msgs:
            return text_msgs[-1].get("text", "")
        return ""

    finally:
        Path(task_file).unlink(missing_ok=True)


# ── Prompt 模板 ──────────────────────────────────────────────────────────

LLM_DECISION_PROMPT_TEMPLATE = """你是一位专业的商品期货分析师。请基于以下数据，生成 DCE（大商所）品种的交易决策建议。

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


# ── LLM Advisor 主类 ──────────────────────────────────────────────────────

class LLMAdvisor:
    """LLM 决策顾问（支持规则和Agent两种模式）"""
    
    def __init__(self, use_agent: bool = True):
        """
        初始化
        
        Args:
            use_agent: 是否使用 CodeFlicker Agent（True）还是规则模式（False）
        """
        self.report_dir = Path(__file__).parent.parent / "reports"
        self.report_dir.mkdir(exist_ok=True)
        self.use_agent = use_agent
        
        # 初始化 Agent Session
        if self.use_agent:
            try:
                self.session_id = _get_or_create_session("DCE决策Agent")
            except Exception as e:
                print(f"  ⚠️ Agent Session 初始化失败，将使用规则模式：{e}")
                self.use_agent = False
    
    def generate_decision_report(
        self,
        variety: str,
        variety_name: str,
        alpha_features: Dict,
        sentiment_result: Dict,
        target_date: Optional[date] = None
    ) -> Dict:
        """
        生成决策报告
        
        Args:
            variety: 品种代码
            variety_name: 品种名称
            alpha_features: Alpha158特征
            sentiment_result: 新闻情绪分析结果
            target_date: 目标日期
        
        Returns:
            决策报告
        """
        if target_date is None:
            target_date = alpha_features.get("_date", date.today())
        
        if self.use_agent:
            return self._generate_with_agent(
                variety, variety_name, alpha_features, sentiment_result, target_date
            )
        else:
            return self._generate_with_rules(
                variety, variety_name, alpha_features, sentiment_result, target_date
            )
    
    def _generate_with_agent(
        self,
        variety: str,
        variety_name: str,
        alpha_features: Dict,
        sentiment_result: Dict,
        target_date: date
    ) -> Dict:
        """通过 Agent 生成决策报告"""
        
        # 格式化 Alpha 特征
        alpha_features_text = []
        for key, value in alpha_features.items():
            if not key.startswith('_'):
                alpha_features_text.append(f"- {key}: {value}")
        alpha_features_text = "\n".join(alpha_features_text) if alpha_features_text else "无"
        
        # 构建 Prompt
        prompt = LLM_DECISION_PROMPT_TEMPLATE.format(
            variety=variety,
            variety_name=variety_name,
            date=target_date.isoformat(),
            alpha_features_text=alpha_features_text,
            sentiment_label=sentiment_result.get("sentiment_label", "中性"),
            sentiment_score=sentiment_result.get("sentiment_score", 0),
            sentiment_summary=sentiment_result.get("summary", "无"),
        )
        
        # 发送任务并等待
        try:
            llm_response = _send_task_and_wait(self.session_id, prompt, timeout=120)
        except Exception as e:
            print(f"  ⚠️ Agent 调用失败，回退到规则模式：{e}")
            return self._generate_with_rules(
                variety, variety_name, alpha_features, sentiment_result, target_date
            )
        
        if not llm_response:
            print(f"  ⚠️ Agent 无响应，回退到规则模式")
            return self._generate_with_rules(
                variety, variety_name, alpha_features, sentiment_result, target_date
            )
        
        # 解析 Agent 响应，提取评分和建议
        score, suggestion, action, risks = self._parse_llm_response(llm_response)
        
        # 提取关键特征
        close_price = alpha_features.get("_close", 0)
        volume = alpha_features.get("_volume", 0)
        return_5d = alpha_features.get("return_5d", 0)
        return_20d = alpha_features.get("return_20d", 0)
        
        return {
            "variety": variety,
            "variety_name": variety_name,
            "date": target_date.isoformat(),
            "timestamp": datetime.now().isoformat(),
            "source": "agent",
            
            # 市场数据
            "market_data": {
                "close_price": close_price,
                "volume": volume,
                "return_5d": f"{return_5d*100:.2f}%",
                "return_20d": f"{return_20d*100:.2f}%",
            },
            
            # 技术指标
            "technical": {
                "rsi_14": round(alpha_features.get("rsi_14", 50), 2),
                "bollinger_position": round(alpha_features.get("bollinger_position", 0.5), 2),
                "volume_ratio_5d": round(alpha_features.get("volume_ratio_5", 1.0), 2),
            },
            
            # 新闻情绪
            "sentiment": {
                "score": sentiment_result.get("sentiment_score", 0),
                "label": sentiment_result.get("sentiment_label", "中性"),
                "summary": sentiment_result.get("summary", ""),
                "key_points": sentiment_result.get("key_points", [])[:3],
            },
            
            # 决策建议（来自 Agent）
            "decision": {
                "综合得分": score,
                "market_view": suggestion,
                "action": action,
                "risks": risks,
            },
            
            # Agent 原始响应
            "llm_raw_response": llm_response,
        }
    
    def _parse_llm_response(self, response: str) -> tuple:
        """解析 Agent 响应，提取评分和建议"""
        score = 0
        suggestion = "中性"
        action = "观望为主"
        risks = []
        
        # 尝试提取评分
        import re
        score_patterns = [
            r'综合评分[：:]\s*([+-]?\d+)',
            r'评分[：:]\s*([+-]?\d+)',
            r'综合得分[：:]\s*([+-]?\d+)',
        ]
        for pattern in score_patterns:
            match = re.search(pattern, response)
            if match:
                try:
                    score = int(match.group(1))
                    break
                except:
                    pass
        
        # 尝试提取方向
        if any(word in response for word in ['强烈看多', '建议多头', '做多', '多头']):
            suggestion = "强烈看多"
            action = "建议多头建仓"
        elif any(word in response for word in ['偏多', '看多']):
            suggestion = "偏多"
            action = "可适量做多"
        elif any(word in response for word in ['强烈看空', '建议空头', '做空', '空头']):
            suggestion = "强烈看空"
            action = "建议空头建仓"
        elif any(word in response for word in ['偏空', '看空']):
            suggestion = "偏空"
            action = "可适量做空"
        
        # 尝试提取风险提示
        risk_pattern = r'风险[提示注意警示][：:]?\s*([^#\n]+)'
        for match in re.finditer(risk_pattern, response):
            risk_text = match.group(1).strip()
            if risk_text and len(risk_text) < 100:
                risks.append(risk_text)
        
        return score, suggestion, action, risks[:3]
    
    def _generate_with_rules(
        self,
        variety: str,
        variety_name: str,
        alpha_features: Dict,
        sentiment_result: Dict,
        target_date: date
    ) -> Dict:
        """基于规则生成决策报告（备用模式）"""
        
        # 提取关键特征
        close_price = alpha_features.get("_close", 0)
        volume = alpha_features.get("_volume", 0)
        
        # 短期趋势（5日收益率）
        return_5d = alpha_features.get("return_5d", 0)
        return_20d = alpha_features.get("return_20d", 0)
        
        # 技术指标
        rsi = alpha_features.get("rsi_14", 50)
        bollinger_position = alpha_features.get("bollinger_position", 0.5)
        
        # 成交量信号
        volume_ratio_5 = alpha_features.get("volume_ratio_5", 1.0)
        
        # 新闻情绪
        sentiment_score = sentiment_result.get("sentiment_score", 0)
        sentiment_label = sentiment_result.get("sentiment_label", "中性")
        
        # 综合评分（-100 到 100）
        score = 0
        
        # 1. 趋势得分 (权重40%)
        if return_5d > 0.03:
            score += 20
        elif return_5d > 0.01:
            score += 10
        elif return_5d < -0.03:
            score -= 20
        elif return_5d < -0.01:
            score -= 10
        
        if return_20d > 0.1:
            score += 20
        elif return_20d > 0.05:
            score += 10
        elif return_20d < -0.1:
            score -= 20
        elif return_20d < -0.05:
            score -= 10
        
        # 2. 技术指标得分 (权重30%)
        if rsi < 30:
            score += 15
        elif rsi < 40:
            score += 8
        elif rsi > 70:
            score -= 15
        elif rsi > 60:
            score -= 8
        
        if bollinger_position < 0.2:
            score += 10
        elif bollinger_position > 0.8:
            score -= 10
        
        # 3. 成交量得分 (权重15%)
        if volume_ratio_5 > 1.5:
            score += 8 if return_5d > 0 else -8
        
        # 4. 新闻情绪得分 (权重15%)
        score += sentiment_score * 15
        
        # 生成建议
        if score > 40:
            suggestion = "强烈看多"
            action = "建议多头建仓"
        elif score > 20:
            suggestion = "偏多"
            action = "可适量做多"
        elif score > -20:
            suggestion = "中性"
            action = "观望为主"
        elif score > -40:
            suggestion = "偏空"
            action = "可适量做空"
        else:
            suggestion = "强烈看空"
            action = "建议空头建仓"
        
        # 风险提示
        risks = []
        if abs(return_5d) > 0.05:
            risks.append("短期波动较大，注意控制仓位")
        if rsi > 70 or rsi < 30:
            risks.append("技术指标显示超买/超卖，可能反转")
        if volume_ratio_5 < 0.5:
            risks.append("成交量萎缩，趋势可能不可持续")
        if sentiment_score < -0.5:
            risks.append("新闻面偏空，谨慎做多")
        
        return {
            "variety": variety,
            "variety_name": variety_name,
            "date": target_date.isoformat(),
            "timestamp": datetime.now().isoformat(),
            "source": "rules",
            
            # 市场数据
            "market_data": {
                "close_price": close_price,
                "volume": volume,
                "return_5d": f"{return_5d*100:.2f}%",
                "return_20d": f"{return_20d*100:.2f}%",
            },
            
            # 技术指标
            "technical": {
                "rsi_14": round(rsi, 2),
                "bollinger_position": round(bollinger_position, 2),
                "volume_ratio_5d": round(volume_ratio_5, 2),
            },
            
            # 新闻情绪
            "sentiment": {
                "score": sentiment_score,
                "label": sentiment_label,
                "summary": sentiment_result.get("summary", ""),
                "key_points": sentiment_result.get("key_points", [])[:3],
            },
            
            # 决策建议
            "decision": {
                "综合得分": score,
                "market_view": suggestion,
                "action": action,
                "risks": risks,
            }
        }
    
    def generate_batch_report(
        self,
        reports: List[Dict],
        output_file: Optional[str] = None
    ) -> str:
        """
        生成批量决策报告（markdown格式）
        
        Args:
            reports: 决策报告列表
            output_file: 输出文件名
        
        Returns:
            报告内容（markdown）
        """
        if not reports:
            return "# 决策报告\n\n暂无数据"
        
        # 获取日期
        report_date = reports[0].get("date", date.today().isoformat())
        
        # 生成markdown
        md = f"# 大商所品种决策报告\n\n"
        md += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md += f"**报告日期**: {report_date}\n\n"
        md += f"**数据来源**: {'CodeFlicker Agent' if reports[0].get('source') == 'agent' else '规则引擎'}\n\n"
        md += "---\n\n"
        
        # 汇总表
        md += "## 一、决策汇总\n\n"
        md += "| 品种 | 收盘价 | 5日涨幅 | 20日涨幅 | 情绪 | 综合得分 | 建议 |\n"
        md += "|------|--------|---------|----------|------|----------|------|\n"
        
        for report in reports:
            variety_name = report.get("variety_name", "")
            market = report.get("market_data", {})
            decision = report.get("decision", {})
            sentiment = report.get("sentiment", {})
            
            md += f"| {variety_name} "
            md += f"| {market.get('close_price', 0):.2f} "
            md += f"| {market.get('return_5d', '0%')} "
            md += f"| {market.get('return_20d', '0%')} "
            md += f"| {sentiment.get('label', '中性')} "
            md += f"| {decision.get('综合得分', 0)} "
            md += f"| {decision.get('market_view', '中性')} |\n"
        
        md += "\n---\n\n"
        
        # 详细分析
        md += "## 二、详细分析\n\n"
        
        for report in reports:
            variety_name = report.get("variety_name", "")
            market = report.get("market_data", {})
            technical = report.get("technical", {})
            sentiment = report.get("sentiment", {})
            decision = report.get("decision", {})
            
            md += f"### {variety_name}\n\n"
            
            # 市场数据
            md += "**市场数据**\n"
            md += f"- 收盘价: {market.get('close_price', 0):.2f}\n"
            md += f"- 5日涨幅: {market.get('return_5d', '0%')}\n"
            md += f"- 20日涨幅: {market.get('return_20d', '0%')}\n"
            md += f"- 成交量: {market.get('volume', 0):.0f}\n\n"
            
            # 技术指标
            md += "**技术指标**\n"
            md += f"- RSI(14): {technical.get('rsi_14', 50):.1f}\n"
            md += f"- 布林带位置: {technical.get('bollinger_position', 0.5):.2f}\n"
            md += f"- 成交量比率(5日): {technical.get('volume_ratio_5d', 1.0):.2f}\n\n"
            
            # 新闻情绪
            md += "**新闻情绪**\n"
            md += f"- 情绪标签: {sentiment.get('label', '中性')}\n"
            md += f"- 情绪得分: {sentiment.get('score', 0):.2f}\n"
            md += f"- 摘要: {sentiment.get('summary', '无')}\n\n"
            
            # 决策建议
            md += "**决策建议**\n"
            md += f"- 综合得分: {decision.get('综合得分', 0)}\n"
            md += f"- 市场观点: {decision.get('market_view', '中性')}\n"
            md += f"- 操作建议: {decision.get('action', '观望')}\n"
            
            if decision.get('risks'):
                md += "\n⚠️ 风险提示:\n"
                for risk in decision['risks']:
                    md += f"- {risk}\n"
            
            # 如果有 Agent 原始响应，附在后面
            if report.get('llm_raw_response'):
                md += "\n<details>\n<summary>🤖 Agent 原始分析</summary>\n\n"
                md += f"{report['llm_raw_response']}\n\n"
                md += "</details>\n"
            
            md += "\n---\n\n"
        
        # 保存报告
        if output_file is None:
            output_file = f"decision_report_{report_date}.md"
        
        output_path = self.report_dir / output_file
        output_path.write_text(md, encoding='utf-8')
        
        print(f"✅ 报告已保存: {output_path}")
        
        return md


if __name__ == "__main__":
    # 测试
    advisor = LLMAdvisor(use_agent=False)  # 先用规则模式测试
    
    # 模拟数据
    alpha_features = {
        "_date": date.today(),
        "_close": 3500.0,
        "_volume": 150000,
        "return_5d": 0.025,
        "return_20d": 0.08,
        "rsi_14": 65,
        "bollinger_position": 0.7,
        "volume_ratio_5": 1.3,
    }
    
    sentiment_result = {
        "sentiment_score": 0.4,
        "sentiment_label": "偏多",
        "summary": "分析了10条新闻，整体情绪偏多",
        "key_points": [
            {"title": "豆粕期货创新高", "tendency": "利多"},
            {"title": "大豆供应趋紧", "tendency": "利多"},
        ]
    }
    
    report = advisor.generate_decision_report(
        "m", "豆粕", alpha_features, sentiment_result
    )
    
    print(json.dumps(report, ensure_ascii=False, indent=2))
    
    # 生成批量报告
    advisor.generate_batch_report([report])
