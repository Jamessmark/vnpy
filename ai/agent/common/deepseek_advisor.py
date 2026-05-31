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
import re
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

from openai import OpenAI
from dotenv import load_dotenv

# 复用 prompt 模板和报告渲染逻辑
from ai.agent.common.llm_advisor import (
    _DEFAULT_PROMPT_TEMPLATE,
    _GROUP_PROMPT_TEMPLATE,
    LLMAdvisor,          # 只继承报告生成 / 评分提取部分，不用 Session
)

_ENV_PATH = Path(__file__).parents[3] / ".env"
load_dotenv(_ENV_PATH)

_MODEL        = "deepseek-v4-pro"
_BASE_URL     = "https://api.deepseek.com/v1"
_MAX_TOKENS_SINGLE = 2048   # 单品种分析
_MAX_TOKENS_PER_VARIETY = 1200  # 分组分析每品种预留 token
_TEMPERATURE  = 0.3


def _build_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_APIKEY", "").strip()
    if not api_key:
        raise RuntimeError(".env 中未配置 DEEPSEEK_APIKEY")
    return OpenAI(api_key=api_key, base_url=_BASE_URL)


def _call_deepseek(client: OpenAI, prompt: str, max_tokens: int = _MAX_TOKENS_SINGLE) -> str:
    """调用 DeepSeek API，返回文本回复。"""
    resp = client.chat.completions.create(
        model       = _MODEL,
        messages    = [{"role": "user", "content": prompt}],
        max_tokens  = max_tokens,
        temperature = _TEMPERATURE,
        stream      = False,
    )
    return resp.choices[0].message.content or ""


def _format_alpha_features(features: Dict) -> str:
    """
    将 Alpha158 原始因子转换为自然语言描述，提升 LLM 理解率。
    返回多段文字，取代原来的 `- key: value` 列表。
    """
    f = features
    lines = []

    close = f.get("_close", 0)

    # ── 价格走势（收益率）──────────────────────────────────────────────────
    r1  = f.get("return_1d",  0) * 100
    r5  = f.get("return_5d",  0) * 100
    r10 = f.get("return_10d", 0) * 100
    r20 = f.get("return_20d", 0) * 100
    r60 = f.get("return_60d", 0) * 100
    lines.append(
        f"【价格走势】近1日 {r1:+.2f}%，近5日 {r5:+.2f}%，近10日 {r10:+.2f}%，"
        f"近20日 {r20:+.2f}%，近60日 {r60:+.2f}%"
    )

    # ── 均线系统 ───────────────────────────────────────────────────────────
    ma5  = f.get("ma_5",  0)
    ma10 = f.get("ma_10", 0)
    ma20 = f.get("ma_20", 0)
    ma30 = f.get("ma_30", 0)
    ma60 = f.get("ma_60", 0)
    d5   = f.get("close_div_ma_5",  0) * 100
    d10  = f.get("close_div_ma_10", 0) * 100
    d20  = f.get("close_div_ma_20", 0) * 100
    d60  = f.get("close_div_ma_60", 0) * 100

    # 判断均线多空排列
    mas = [ma5, ma10, ma20, ma30, ma60]
    if all(mas[i] > mas[i+1] for i in range(len(mas)-1)):
        arrangement = "多头排列（短均线 > 长均线）"
    elif all(mas[i] < mas[i+1] for i in range(len(mas)-1)):
        arrangement = "空头排列（短均线 < 长均线）"
    else:
        arrangement = "均线交叉混乱（无明确趋势）"

    lines.append(
        f"【均线系统】MA5={ma5:.2f} MA10={ma10:.2f} MA20={ma20:.2f} MA60={ma60:.2f}，"
        f"{arrangement}。"
        f"收盘偏离MA5={d5:+.1f}%，MA20={d20:+.1f}%，MA60={d60:+.1f}%"
    )

    # ── 波动率 ─────────────────────────────────────────────────────────────
    v5  = f.get("volatility_5d",  0) * 100
    v20 = f.get("volatility_20d", 0) * 100
    v60 = f.get("volatility_60d", 0) * 100
    if v5 > v20 * 1.3:
        vol_trend = "近期波动率明显扩大（短期波动 > 中期波动 30%+）"
    elif v5 < v20 * 0.7:
        vol_trend = "近期波动率明显收窄（短期波动 < 中期波动 30%-）"
    else:
        vol_trend = "波动率平稳"
    lines.append(
        f"【波动率】5日={v5:.2f}% 20日={v20:.2f}% 60日={v60:.2f}%，{vol_trend}"
    )

    # ── 成交量 ─────────────────────────────────────────────────────────────
    vr5  = f.get("volume_ratio_5",  1)
    vr10 = f.get("volume_ratio_10", 1)
    vr20 = f.get("volume_ratio_20", 1)

    def vol_desc(ratio):
        if ratio > 1.5:   return f"明显放量（×{ratio:.1f}）"
        elif ratio > 1.1: return f"温和放量（×{ratio:.1f}）"
        elif ratio < 0.6: return f"明显缩量（×{ratio:.1f}）"
        elif ratio < 0.9: return f"温和缩量（×{ratio:.1f}）"
        else:             return f"量能正常（×{ratio:.1f}）"

    lines.append(
        f"【成交量】相对5日均量: {vol_desc(vr5)}，"
        f"相对10日均量: {vol_desc(vr10)}，"
        f"相对20日均量: {vol_desc(vr20)}"
    )

    # ── RSI ───────────────────────────────────────────────────────────────
    rsi = f.get("rsi_14", 50)
    if rsi > 80:   rsi_desc = "严重超买（>80）"
    elif rsi > 70: rsi_desc = "超买区间（70-80）"
    elif rsi > 60: rsi_desc = "偏强（60-70）"
    elif rsi > 40: rsi_desc = "中性区间（40-60）"
    elif rsi > 30: rsi_desc = "偏弱（30-40）"
    elif rsi > 20: rsi_desc = "超卖区间（20-30）"
    else:          rsi_desc = "严重超卖（<20）"
    lines.append(f"【RSI(14)】{rsi:.1f}，{rsi_desc}")

    # ── MACD ──────────────────────────────────────────────────────────────
    macd = f.get("macd", 0)
    if macd > 0:
        macd_desc = f"零轴上方 +{macd:.2f}，多头动能"
    elif macd > -5:
        macd_desc = f"零轴略下方 {macd:.2f}，弱势整理"
    else:
        macd_desc = f"零轴深度下方 {macd:.2f}，空头趋势"
    lines.append(f"【MACD】{macd_desc}")

    # ── 布林带 ────────────────────────────────────────────────────────────
    b_upper = f.get("bollinger_upper", 0)
    b_lower = f.get("bollinger_lower", 0)
    b_pos   = f.get("bollinger_position", 0.5)
    if b_pos > 0.9:   b_desc = "贴近上轨（超买警戒）"
    elif b_pos > 0.7: b_desc = "上半区运行（偏强）"
    elif b_pos > 0.3: b_desc = "中轨附近震荡"
    elif b_pos > 0.1: b_desc = "下半区运行（偏弱）"
    else:             b_desc = "贴近下轨（超卖支撑）"
    lines.append(
        f"【布林带】上轨={b_upper:.2f} 下轨={b_lower:.2f}，"
        f"价格处于布林带 {b_pos:.0%} 位置，{b_desc}"
    )

    # ── 近期价格区间 ───────────────────────────────────────────────────────
    h5  = f.get("high_5d",  close)
    l5  = f.get("low_5d",   close)
    h20 = f.get("high_20d", close)
    l20 = f.get("low_20d",  close)
    pp5  = f.get("price_position_5d",  0.5) * 100
    pp20 = f.get("price_position_20d", 0.5) * 100
    lines.append(
        f"【价格区间】5日区间 [{l5:.2f}, {h5:.2f}]，当前价格处于5日区间 {pp5:.0f}% 位置；"
        f"20日区间 [{l20:.2f}, {h20:.2f}]，处于20日区间 {pp20:.0f}% 位置"
    )

    return "\n".join(lines)


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

        alpha_text = _format_alpha_features(alpha_features)

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

    def generate_group_report(
        self,
        group_name:        str,
        varieties:         List[str],
        variety_names:     Dict[str, str],
        alpha_results:     Dict[str, Dict],
        sentiment_results: Dict[str, Dict],
        target_date:       Optional[date] = None,
    ) -> List[Dict]:
        """
        对一个产业链分组的多个品种合并调用一次 DeepSeek，
        从返回文本中拆解出每个品种的报告字典，格式与
        generate_decision_report() 完全一致。

        Args:
            group_name:        分组名称，如「豆系」
            varieties:         本组品种代码列表
            variety_names:     品种代码→中文名
            alpha_results:     {variety: alpha_features_dict}
            sentiment_results: {variety: sentiment_result_dict}
            target_date:       目标日期

        Returns:
            List[Dict]，每个元素与 generate_decision_report() 返回格式相同。
        """
        # 只处理有 alpha 数据的品种
        valid = [v for v in varieties if v in alpha_results]
        if not valid:
            return []

        if target_date is None:
            first = next(iter(alpha_results[valid[0]].get("_date", None) for _ in [1]))
            target_date = first if first else date.today()
        if not isinstance(target_date, date):
            target_date = date.today()

        # ── 拼接各品种数据块 ───────────────────────────────────────────────────
        varieties_data_parts = []
        for v in valid:
            vname       = variety_names.get(v, v)
            alpha_text  = _format_alpha_features(alpha_results[v])
            sent        = sentiment_results.get(v, {})
            news_list   = sent.get("news", [])
            if news_list:
                news_lines = []
                for i, n in enumerate(news_list, 1):
                    title    = n.get("title", "").strip()
                    source   = n.get("source", "")
                    pub_time = (n.get("publish_time") or "")[:10]
                    content  = (n.get("content") or "").strip()[:150]
                    news_lines.append(
                        f"{i}. [{pub_time}][{source}] {title}"
                        + (f"\n   摘要：{content}" if content else "")
                    )
                news_text = "\n".join(news_lines)
            else:
                news_text = "（未获取到新闻，请仅依据技术指标分析）"

            part = (
                f"### {vname}（代码: {v}，收盘价: {alpha_results[v].get('_close', 0):.2f}）\n\n"
                f"**技术数据**\n{alpha_text}\n\n"
                f"**近期新闻（共 {len(news_list)} 条）**\n{news_text}"
            )
            varieties_data_parts.append(part)

        varieties_data      = "\n\n---\n\n".join(varieties_data_parts)
        variety_names_list  = "、".join(variety_names.get(v, v) for v in valid)

        prompt = _GROUP_PROMPT_TEMPLATE.format(
            exchange_name       = self.exchange_name,
            group_name          = group_name,
            date                = target_date.isoformat(),
            varieties_data      = varieties_data,
            variety_names_list  = variety_names_list,
        )

        print(f"  [DeepSeek] 分析分组 【{group_name}】({variety_names_list})...", end="", flush=True)
        llm_response = ""
        max_tokens = _MAX_TOKENS_PER_VARIETY * len(valid)
        try:
            llm_response = _call_deepseek(self._client, prompt, max_tokens=max_tokens)
            print(" ✓")
        except Exception as e:
            print(f" ❌ {e}")

        # ── 从 LLM 回复中拆解各品种 ────────────────────────────────────────────
        results = []
        for v in valid:
            vname      = variety_names.get(v, v)
            # 找 ## 品种名 开头的块
            block_pat  = rf"##\s*{re.escape(vname)}[\s\S]*?(?=\n##\s+(?!.*### )|\Z)"
            block_m    = re.search(block_pat, llm_response)
            variety_llm = block_m.group(0).strip() if block_m else ""

            results.append({
                "variety":      v,
                "variety_name": vname,
                "date":         target_date.isoformat(),
                "timestamp":    datetime.now().isoformat(),
                "exchange":     self.exchange_name,
                "close_price":  alpha_results[v].get("_close", 0),
                "llm_prompt":   prompt,
                "llm_response": variety_llm,
                "_group":       group_name,
            })

        return results
