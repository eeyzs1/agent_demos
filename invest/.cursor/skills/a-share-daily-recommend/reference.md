# Reference — A股每日荐股（双指标 + 投研增强）

## Dual scores

| Score | Range | Source |
|-------|-------|--------|
| `tech_score` | 0–100 | RSI / MACD / MA / volume / Bollinger via `StockScreener._score_technical` |
| `news_score` | 0–100 | Keyword polarity on fetched headlines (`NewsScorer`) |
| `combined_score` | 0–100 | `tech_weight*tech + news_weight*news` (default 0.6/0.4) |
| `scores.fundamental` | 0–1 | PE/PB/ROE/增长代理（筛股器），供投研增强 |
| `fundamentals` | object | 真实快照：`pe_ttm` / `pb` / `roe` / `revenue_yoy` / `net_profit_yoy`（akshare） |

Raw `news[]` titles stay in `agent_brief.json` for Cursor agent final judgment.

`fundamentals.data_sparse=true` means PE/PB/ROE all missing — do not invent multiples.

Legacy screener field `sentiment` is **not** news — ignore it; use `news_score`.

## Skills

| Skill | Role |
|-------|------|
| `a-share-daily-recommend` | 编排：brief → 终审 → 报告 |
| `a-share-research-enhance` | 终审插件：估值观 / 质量观 / 证伪条件 |

Research checklist: `../a-share-research-enhance/checklist.md`

## Paths

| Item | Path |
|------|------|
| Trading system | `generated/automated-trading-system/` |
| Config | `config/default.yaml` → `recommend.dual_scores` |
| Brief | `output/snapshots/<as_of>/agent_brief.json` |
| Judgments | `output/snapshots/<as_of>/agent_judgments.json` |
| Report | `output/reports/<as_of>_daily_recommend.md` |

## Scripts

```bash
python scripts/prepare_agent_brief.py
python scripts/finalize_from_judgments.py --as-of YYYY-MM-DD
```
