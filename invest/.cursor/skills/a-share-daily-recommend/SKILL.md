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

**禁止**默认调用外部 `LLM_API_*`（除非用户明确要求）。

项目根：`generated/automated-trading-system/`

字段见 [reference.md](reference.md)；判断格式见 [judgment-schema.md](judgment-schema.md)。

## 工作流

```
进度:
- [ ] 1. prepare brief（tech + news 双指标）
- [ ] 2. 读 agent_brief.json
- [ ] 3. 你终审 → agent_judgments.json
- [ ] 4. finalize 报告
- [ ] 5. 向用户摘要（含 tech/news/置信度）
```

### 1. 准备 brief

```bash
python scripts/prepare_agent_brief.py
```

可选：`--top 30` `--max-score 400` `--as-of YYYY-MM-DD`

产出：`output/snapshots/<as_of>/agent_brief.json`（含 `tech_score`/`news_score`/`news[]`）

### 2–3. 终审

对每个候选综合双指标 + 原文：

- 措辞用「关注/观察」，禁止「稳赚/必涨/强烈买入」
- reasons ≥ 3（尽量覆盖技术面与消息面）；risks ≥ 1
- confidence 0–100
- action_hint ∈ `strong_watch` | `watch` | `avoid`

写入：`output/snapshots/<as_of>/agent_judgments.json`

### 4. 报告

```bash
python scripts/finalize_from_judgments.py --as-of YYYY-MM-DD
```

### 5. 回复用户

表格至少含：代码、名称、**技术分**、**消息分**、综合分、置信度、建议、一句话理由 + 报告路径 + 免责声明。

## 硬约束

1. 主板池（600/601/603、000/001/002）  
2. Top10 + 观察池10  
3. 不下单  
4. 不把 API Key 写入报告/git  
5. 终审必须由当前对话中的你完成
