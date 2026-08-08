# Automated Trading System — Daily Recommend

A-share **main-board** screening + news context → **LLM** daily recommendation report.

## Setup

```bash
cd generated/automated-trading-system
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
# Edit .env — set LLM_API_KEY / LLM_API_BASE / LLM_MODEL
```

## Daily report (Cursor agent as final judge — preferred)

In Cursor, invoke skill **a-share-daily-recommend** (or say「每日荐股」).

Manual steps:

```bash
python scripts/prepare_agent_brief.py
# Agent writes output/snapshots/<date>/agent_judgments.json
python scripts/finalize_from_judgments.py --as-of YYYY-MM-DD
```

## Daily report (external LLM via .env)

```bash
python -m trading_system.cli.main recommend daily --top 10
```

Outputs:

- `output/reports/YYYY-MM-DD_daily_recommend.md`
- `output/reports/YYYY-MM-DD_daily_recommend.json`

## Schedule (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/schedule-daily-recommend.ps1 -Register
```

## Notes

- Trading / auto-order is **out of scope** for this milestone (advice only).
- Without `LLM_API_KEY`, the system falls back to rule-based reasons and marks `llm_status: fallback`.
