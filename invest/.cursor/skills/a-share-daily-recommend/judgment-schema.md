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

        {"code": "QUALITY", "text": "基本面代理分偏强，质量观支撑关注"},

        {"code": "COMBO", "text": "双指标与质量观同向，仍具观察价值"}

      ],

      "risks": [

        {"code": "VALUATION", "text": "估值观偏贵或证据不足时需折价置信度"}

      ],

      "news_summary": "近端新闻未显示重大利好或利空。",

      "research": {

        "valuation_view": "fair",

        "quality_view": "strong",

        "data_sparse": false,

        "caveats": [],

        "falsifiers": ["若出现减持或处罚类标题则降为 avoid"],

        "notes": "fundamental 代理偏强；无精确 PE 分位数据"

      }

    }

  ]

}

```



Rules:



- Include **every** symbol from `agent_brief.json` → `candidates` (or note skips).

- Prefer citing both **tech_score** and **news_score** from the brief in reasons.

- Still read raw `news[]` titles — score is compressed; text may change the call.

- Apply **a-share-research-enhance** checklist; each judgment SHOULD include `research`.

- Top 候选：`research.falsifiers` ≥ 1；观察池可短，但至少有 `valuation_view` / `quality_view`.

- `valuation_view`: `cheap` | `fair` | `expensive` | `unknown`

- `quality_view`: `strong` | `average` | `weak` | `unknown`

- `action_hint`: only `strong_watch` | `watch` | `avoid`

- `confidence`: integer 0–100

- Each reason/risk text: Chinese, ≤40 chars preferred

- Reason/risk codes may include: `TECH` `NEWS` `COMBO` `VALUATION` `QUALITY` `DATA` `AGENT`


