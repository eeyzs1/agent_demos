# Meta-Orchestrator: Execution Planning

## Purpose
Take harness + agent configs → execution plan with order, dependencies, parallelism.

## Process

1. **Build Dependency Graph**: Map task dependencies (A→B→C, A→C parallel with B)
2. **Assign Agents**: One primary agent per task. Dependencies = order. Independent = parallel.
3. **Define Checkpoints**: Between every dependency boundary. Verify before handoff.
4. **Create Execution Plan**:
```yaml
execution:
  project: [name]
  phases:
    - name: [phase]
      parallel: [true/false]
      tasks:
        - agent: [name]
          task_card: [path]
          input/output: [formats]
          timeout: [duration]
      checkpoint:
        verify: [what to check]
        on_fail: [retry/escalate/abort]
  completion:
    criteria: [final acceptance]
```
5. **Track Progress**: Log to `memory/progress.md`. Monitor timeouts. Retry with context.

## Error Handling
- **Timeout**: Capture state → retry with fresh session + specific instructions → 3 retries → escalate
- **Verification Failure**: Capture failure → route back with failure details only → 3 retries → escalate
- **Hallucination**: Discard out-of-scope output → log to `memory/meta-mistakes.md` → add constraint → retry

## Anti-Patterns
- No simultaneous execution without checkpoints
- No infinite retries — hard limits
- No skipping checkpoints to save time
- No runtime plan modification by agents
