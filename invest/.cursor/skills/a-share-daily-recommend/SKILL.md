---
name: a-share-daily-recommend
description: >-
  Runs A-share main-board quant screening with dual scores (tech_score +
  news_score), keeps raw news for the Cursor agent final judgment, and produces
  a daily recommendation report with Chinese reasons, risks, and confidence.
  Use when the user asks for 每日荐股, A股推荐, 股票推荐带理由, daily recommend,
  tech/news dual indicators, or wants the agent to judge stock recommendations.
---

# A股每日荐股（双指标 + Agent 终审）

你是**最终研判 LLM**。流水线提供：

1. **tech_score (0–100)** — 行情技术（RSI/MACD/均线/量/布林）  
2. **news_score (0–100)** — 新闻关键词极性 + 覆盖度  
3. **combined_score** — 默认 `0.6*tech + 0.4*news`  
4. **news[] 原文标题** — 终审必读，勿只看分数  
5. **scores.fundamental** — 基本面代理（0–1）  
6. **fundamentals** — 真实 PE(TTM)/PB/ROE/同比（akshare），投研增强优先用此  

**禁止**默认调用外部 `LLM_API_*`（除非用户明确要求）。

项目根：`generated/automated-trading-system/`

字段见 [reference.md](reference.md)；判断格式见 [judgment-schema.md](judgment-schema.md)。  
终审时**必须加载**投研增强 skill：[`../a-share-research-enhance/SKILL.md`](../a-share-research-enhance/SKILL.md)（清单见同目录 `checklist.md`）。

## 工作流

```
进度:
- [ ] 1. prepare brief（tech + news 双指标）
- [ ] 2. 读 agent_brief.json
- [ ] 3. 加载 a-share-research-enhance → 估值/质量/证伪
- [ ] 4. 你终审 → agent_judgments.json（含 research 块）
- [ ] 5. finalize 报告
- [ ] 6. 向用户摘要（含 tech/news/置信度 + 估值/质量观）
```

### 1. 准备 brief

```bash
python scripts/prepare_agent_brief.py
```

可选：`--top 30` `--max-score 400` `--as-of YYYY-MM-DD`

产出：`output/snapshots/<as_of>/agent_brief.json`（含 `tech_score`/`news_score`/`news[]`）

### 2–4. 终审（双指标 + 投研增强）

对每个候选：

1. 综合 **tech + news + 原文标题**
2. 按 `a-share-research-enhance` 填写 `research`（估值三维观 / 质量观 / falsifiers）
3. 用 research 结论微调 `action_hint` / `confidence`，并补充 `VALUATION`/`QUALITY`/`DATA` 类 reasons 或 risks

硬性输出要求：

- 措辞用「关注/观察」，禁止「稳赚/必涨/强烈买入」
- reasons ≥ 3（覆盖技术面、消息面，Top 候选尽量含估值或质量）
- risks ≥ 1；Top 候选 `research.falsifiers` ≥ 1
- confidence 0–100
- action_hint ∈ `strong_watch` | `watch` | `avoid`
- 每条 judgment 含 `research` 对象（见 judgment-schema）

写入：`output/snapshots/<as_of>/agent_judgments.json`

### 5. 报告

```bash
python scripts/finalize_from_judgments.py --as-of YYYY-MM-DD
```

### 6. 回复用户

表格至少含：代码、名称、**技术分**、**消息分**、综合分、置信度、建议、估值观、质量观、一句话理由 + 报告路径 + 免责声明。

## 硬约束

1. 主板池（600/601/603、000/001/002）  
2. Top10 + 观察池10  
3. 不下单  
4. 不把 API Key 写入报告/git  
5. 终审必须由当前对话中的你完成  
6. 不默认调用 Longbridge/外部券商 CLI；投研增强只用本项目数据  
