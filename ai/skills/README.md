# AI Skills

本目录存放项目自定义的 CodeFlicker Skills，用于增强 AI Agent 的专项能力。

---

## 目录结构

```
ai/skills/
├── web-search-1.0.0/          # 网页搜索
├── technical-analyst-0.1.0/   # K线图技术分析
└── news-summary-1.0.1/        # 国际新闻摘要
```

---

## Skills 一览

### 1. web-search `v1.0.0`

**功能**：通过 DuckDuckGo API 搜索网页、新闻、图片和视频，无需 API Key。

**适用场景**：
- 搜索网页资料、最新信息
- 查找新闻文章（支持按时间过滤）
- 搜索图片（支持尺寸/颜色/类型过滤）
- 搜索视频（支持时长/分辨率过滤）
- 研究调查、事实核查

**核心用法**：
```bash
# 基本网页搜索
python scripts/search.py "<关键词>"

# 搜索最新新闻
python scripts/search.py "<关键词>" --type news --time-range d

# 输出 Markdown 格式
python scripts/search.py "<关键词>" --format markdown --output result.md

# 搜索图片
python scripts/search.py "<关键词>" --type images --image-size Large
```

**依赖**：`duckduckgo-search`（`uv add duckduckgo-search`）

---

### 2. technical-analyst `v0.1.0`

**功能**：对股票、指数、加密货币、外汇的**周线图**进行纯技术面分析，输出结构化分析报告。

**适用场景**：
- 用户提供 K 线图图片，要求技术分析
- 趋势识别、支撑/阻力位判断
- 均线分析（20/50/200 周均线）
- 成交量分析
- 概率加权情景规划（2-4 个情景，概率之和 100%）

**工作流程**：
1. 读取 `references/technical_analysis_framework.md` 方法论
2. 系统性分析图表（趋势→支撑压力→均线→成交量→形态）
3. 生成 2-4 个概率情景（多/空/中性）
4. 使用 `assets/analysis_template.md` 模板生成报告
5. 报告命名：`[SYMBOL]_technical_analysis_[YYYY-MM-DD].md`

**特点**：
- 纯图表分析，不参考新闻/基本面
- 客观中立，提供多空双向情景
- 输出规范化 Markdown 报告

**附带资源**：
- `references/technical_analysis_framework.md` — 技术分析方法论
- `assets/analysis_template.md` — 报告输出模板

---

### 3. news-summary `v1.0.1`

**功能**：从 BBC、Reuters、NPR、Al Jazeera 等国际权威 RSS 源抓取新闻，生成结构化简报，可选生成语音摘要。

**适用场景**：
- 获取每日新闻简报
- 了解世界/财经/科技动态
- 生成语音新闻播报（需 OpenAI TTS API Key）

**RSS 来源**：
| 来源 | 视角 | 频道 |
|------|------|------|
| BBC | 英国/国际 | 世界、财经、科技、头条 |
| Reuters | 国际财经 | 全球新闻 |
| NPR | 美国视角 | 综合新闻 |
| Al Jazeera | 全球南方视角 | 全球新闻 |

**输出格式示例**：
```
📰 News Summary [日期]

🌍 WORLD
- [头条1]
- [头条2]

💼 BUSINESS
- [头条1]

💻 TECH
- [头条1]
```

**语音功能**：可调用 OpenAI TTS（`tts-1-hd`，`onyx` 音色）生成 MP3 语音播报，约 2 分钟时长。

---

## 注意事项

- 这些 Skills 位于 `ai/skills/`，不在 CodeFlicker 默认扫描路径（`skills/` 或 `.codeflicker/skills/`）
- 使用时需手动指定路径加载，或通过 `read_file` 读取对应 SKILL.md 内容
