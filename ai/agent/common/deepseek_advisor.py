"""
DeepSeek LLM 决策顾问

使用 DeepSeek-V4-Pro 模型，通过 OpenAI 兼容接口进行期货品种决策分析。
复用 llm_advisor.py 的 Prompt 模板、评分提取和报告生成逻辑。

所需 .env 配置：
    DEEPSEEK_APIKEY=sk-xxxx

用法：
    from ai.agent.common.deepseek_advisor import DeepSeekAdvisor

    advisor = DeepSeekAdvisor(exchange_name="大商所", report_dir=Path("reports"))
    report  = advisor.generate_decision_report(
        variety="m", variety_name="豆粕",
        alpha_features=..., sentiment_result=...
    )
    advisor.generate_batch_report([report])
"""
import os
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

from openai import OpenAI
from dotenv import load_dotenv

# 复用 prompt 模板和报告渲染逻辑
from ai.agent.common.llm_advisor import (
    _DEFAULT_PROMPT_TEMPLATE,
    LLMAdvisor,          # 只继承报告生成 / 评分提取部分，不用 Session
)

_ENV_PATH = Path(__file__).parents[3] / ".env"
load_dotenv(_ENV_PATH)

_MODEL        = "deepseek-v4-pro"
_BASE_URL     = "https://api.deepseek.com/v1"
_MAX_TOKENS   = 2048
_TEMPERATURE  = 0.3


def _build_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_APIKEY", "").strip()
    if not api_key:
        raise RuntimeError(".env 中未配置 DEEPSEEK_APIKEY")
    return OpenAI(api_key=api_key, base_url=_BASE_URL)


def _call_deepseek(client: OpenAI, prompt: str) -> str:
    """调用 DeepSeek API，返回文本回复。"""
    resp = client.chat.completions.create(
        model       = _MODEL,
        messages    = [{"role": "user", "content": prompt}],
        max_tokens  = _MAX_TOKENS,
        temperature = _TEMPERATURE,
        stream      = False,
    )
    return resp.choices[0].message.content or ""


class DeepSeekAdvisor:
    """
    使用 DeepSeek-V4-Pro 生成期货决策报告。

    接口与 LLMAdvisor 完全一致，可直接替换。
    """

    def __init__(
        self,
        exchange_name:   str            = "商品期货",
        report_dir:      Optional[Path] = None,
        prompt_template: Optional[str]  = None,
    ):
        self.exchange_name   = exchange_name
        self.prompt_template = prompt_template or _DEFAULT_PROMPT_TEMPLATE
        self.report_dir      = report_dir or (Path(__file__).parent.parent / "reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._client = _build_client()

    # ── 复用 LLMAdvisor 的静态方法 ─────────────────────────────────────────
    _extract_score     = staticmethod(LLMAdvisor._extract_score)
    _extract_direction = staticmethod(LLMAdvisor._extract_direction)
    _extract_reason    = staticmethod(LLMAdvisor._extract_reason)
    generate_batch_report = LLMAdvisor.generate_batch_report

    # ── 核心：生成单品种决策报告 ────────────────────────────────────────────
    def generate_decision_report(
        self,
        variety:          str,
        variety_name:     str,
        alpha_features:   Dict,
        sentiment_result: Dict,
        target_date:      Optional[date] = None,
    ) -> Dict:
        """
        调用 DeepSeek 生成单品种决策报告。

        Returns:
            与 LLMAdvisor.generate_decision_report() 格式完全一致的字典。
        """
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

        print(f"  [DeepSeek] 分析 {variety_name}({variety})...", end="", flush=True)
        llm_response = ""
        try:
            llm_response = _call_deepseek(self._client, prompt)
            print(" ✓")
        except Exception as e:
            print(f" ❌ {e}")

        return {
            "variety":      variety,
            "variety_name": variety_name,
            "date":         target_date.isoformat(),
            "timestamp":    datetime.now().isoformat(),
            "exchange":     self.exchange_name,
            "close_price":  alpha_features.get("_close", 0),
            "llm_prompt":   prompt,
            "llm_response": llm_response,
        }
