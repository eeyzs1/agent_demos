# agent_judgments.json schema

Write this file to `output/snapshots/<as_of>/agent_judgments.json`.

```json
{
  "as_of": "2026-08-07",
  "judge": "cursor-agent",
  "market_overview": "一句话市场/样本概况（可基于 brief.meta）",
  "judgments": [
    {
      "symbol": "600519",
      "name": "贵州茅台",
      "action_hint": "watch",
      "confidence": 72,
      "reasons": [
        {"code": "TECH", "text": "技术分偏强，均线/动量特征相对积极"},
        {"code": "NEWS", "text": "消息分中性偏正，未见重大利空标题"},
        {"code": "COMBO", "text": "双指标综合后仍具关注价值"}
      ],
      "risks": [
        {"code": "VALUATION", "text": "估值与拥挤交易风险需警惕"}
      ],
      "news_summary": "近端新闻未显示重大利好或利空。"
    }
  ]
}
```

Rules:

- Include **every** symbol from `agent_brief.json` → `candidates` (or note skips).
- Prefer citing both **tech_score** and **news_score** from the brief in reasons.
- Still read raw `news[]` titles — score is compressed; text may change the call.
- `action_hint`: only `strong_watch` | `watch` | `avoid`
- `confidence`: integer 0–100
- Each reason/risk text: Chinese, ≤40 chars preferred
