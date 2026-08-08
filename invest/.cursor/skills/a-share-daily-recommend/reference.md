# Reference — A股每日荐股（双指标）

## Dual scores

| Score | Range | Source |
|-------|-------|--------|
| `tech_score` | 0–100 | RSI / MACD / MA / volume / Bollinger via `StockScreener._score_technical` |
| `news_score` | 0–100 | Keyword polarity on fetched headlines (`NewsScorer`) |
| `combined_score` | 0–100 | `tech_weight*tech + news_weight*news` (default 0.6/0.4) |

Raw `news[]` titles stay in `agent_brief.json` for Cursor agent final judgment.

Legacy screener field `sentiment` is **not** news — ignore it; use `news_score`.

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
