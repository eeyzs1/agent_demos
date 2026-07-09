# Template: Data Pipeline

## When to Use
Task involves data ingestion, transformation, analysis, or ETL workflows.

## Default Constraints
- No data loss — every record is accounted for (ingested = processed + errored)
- All transformations are idempotent (safe to re-run)
- Data lineage is tracked (where did this value come from?)
- Schema changes are backward-compatible
- Error records are quarantined, not silently dropped
- Processing is observable (metrics, logs, alerts)

## Default Workflows
- Pipeline: define schema → ingest → validate → transform → output → audit
- Schema change: analyze impact → migrate forward → verify compatibility → deploy
- Data quality: define expectations → validate → quarantine violations → alert

## Default Skills
- Data schema design
- Transformation logic
- Error handling and dead letter queues
- Data quality validation
- Pipeline orchestration

## Default Agent Topology
Pipeline pattern:
- Agent 1 (Ingest): reads source data, validates schema, writes raw
- Agent 2 (Transform): reads raw, applies business logic, writes output
- Agent 3 (Validate): verifies output against expectations, generates audit report

## Default Verification
- Record count: ingested = processed + errored
- Schema validation passes
- Data quality checks pass
- No data leakage (PII/sensitive data detection)
- Transformation is idempotent (run twice, same result)
- Pipeline completes within time budget

## Quality Attributes Priority
1. Reliability (data integrity is paramount)
2. Maintainability (pipelines evolve frequently)
3. Cost (data processing can be expensive)
4. Speed (but not at cost of reliability)
