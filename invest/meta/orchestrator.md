# Meta-Orchestrator: Loop Execution + Evidence Traceability

## Purpose
Execute work in a LOOP, not a single pass. After execution, PROVE the output
satisfies the original need. If not proven, diagnose root cause and loop back.

## The Execution Loop

```
EXECUTE → PROVE → JUDGE ──→ NOT PROVEN → diagnose root cause → loop back
                  ↓
                PROVEN → EVOLVE → STOP
```

## Process

1. **Build Dependency Graph**: Map task dependencies
2. **Assign Agents**: One primary agent per task
3. **Define Checkpoints**: Verify between every dependency boundary
4. **Execute**: Run the plan within generated harness
5. **Prove**: For EACH acceptance criterion, produce evidence
6. **Judge**: Does evidence prove the need is satisfied?
7. **Loop or Stop**: If not proven → root cause → loop. If proven → evolve.

## Evidence Traceability (Critical)

Every output must trace back to a specific acceptance criterion with evidence.

### Evidence Format
```yaml
criterion: [from interpreter's acceptance_criteria]
  evidence:
    type: [test_result|working_output|measurable_metric|demonstration]
    description: [what proves this criterion is met]
    location: [where to find the evidence]
    verdict: SATISFIED | NOT_SATISFIED
```

### Evidence Must Be:
- **Specific**: Not "it works" but "test X passes with output Y"
- **Verifiable**: Someone else could check the same evidence
- **Traceable**: Directly linked to an acceptance criterion

### If Evidence Cannot Be Produced:
The criterion is NOT met. Do NOT mark it as satisfied.
Diagnose root cause and loop back.

## Error Handling (Root Cause, Not Symptoms)

- **Timeout**: Why did it timeout? → scope too large? → split task
- **Verification Failure**: Why did it fail? → wrong approach? → redesign
- **Hallucination**: Why did agent go off-scope? → constraint gap? → add constraint
- **Goal Drift**: Why did output diverge from need? → unclear criteria? → re-interpret

Every error must answer "WHY did this happen at the root level?"
Never patch symptoms. Never add try/catch to hide errors.

## Anti-Patterns
- No single-pass execution — always loop until proven
- No "I think it's done" — only evidence proves completion
- No symptom patching — always chase root causes
- No skipping the PROVE step — it's not optional
