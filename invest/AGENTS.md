# Harness Engineering Framework — AGENT OPERATING INSTRUCTIONS

## ⚠️ MANDATORY: Read This Before Taking Any Action

You are operating inside a meta-harness system. You MUST follow these instructions.
Do NOT skip to coding. Do NOT plan on your own. Follow the protocol below.

## First Principles (Override Everything Else)

1. **Do not assume the user knows what they want.** When motivation or goal is unclear, STOP and discuss.
2. **If the goal is clear but the path isn't optimal, say so.** Suggest the better way directly.
3. **Chase root causes, never patch symptoms.** Every decision must answer "why".
4. **Output only what changes decisions.** Cut everything else.

## The Core Loop (NOT a Linear Pipeline)

The system NEVER stops after one execution. It loops until PROVEN done:

```
┌─→ INTERPRET: What does the user actually need? (first principles)
│       ↓
│   GENERATE: Create harness + agents for THIS specific need
│       ↓
│   EXECUTE: Do the work within generated constraints
│       ↓
│   PROVE:   Produce EVIDENCE that output satisfies original need
│       ↓
│   JUDGE:   Does the evidence convince? ──→ NO → diagnose root cause, loop back
│       ↓
│   YES
│       ↓
└── EVOLVE:  What did we learn? Improve the harness. Then STOP.
```

## Step-by-Step Protocol

### Step 1: Interpret (First Principles)
Read `meta/interpreter.md`. Follow its instructions exactly.
Key: Do NOT start from templates. Start from the user's raw need.
Question every assumption. If the goal is unclear, STOP and ask.

### Step 2: Generate Harness
After user confirms task definition, read `meta/harness-generator.md`.
Generate ONLY what's needed — no boilerplate, no "just in case" constraints.

### Step 3: Generate Agent Topology
Read `meta/agent-factory.md`. Generate topology from task analysis.

### Step 4: Execute
Read `meta/orchestrator.md`. Execute within generated harness.
After execution, do NOT stop. Continue to Step 5.

### Step 5: Prove (Evidence Traceability)
For EVERY acceptance criterion from Step 1:
- Produce specific evidence that it is satisfied
- Evidence must be: test results, working output, measurable metrics
- If you cannot produce evidence → the criterion is NOT met → loop back

### Step 6: Judge
Ask: "Does the evidence convincingly prove the output satisfies the user's original need?"
- If NO → diagnose root cause (not symptom), loop back to the failing step
- If YES → proceed to Step 7

### Step 7: Evolve
Read `evolution/framework.md`. Record what worked and what didn't.
Improve the harness based on evidence, not guesses.

## Absolute Rules (NEVER Violate)

1. No execution without interpretation — always interpret first
2. No agent without a harness — always generate constraints first
3. No constraint without a reason — every rule must answer "why"
4. No completion without EVIDENCE — output must prove it satisfies the original need
5. No single-pass execution — the loop continues until evidence proves success
6. No patching symptoms — always chase root causes
7. Every generation logged to `memory/generation-log.md`
8. Every failure logged to `memory/meta-mistakes.md` with ROOT CAUSE
9. Evolution never removes verification (cancer prevention)
10. Evolution never removes itself (suicide prevention)
11. All mutations must be reversible
12. Context files stay under 60 lines

## Architecture Reference
```
META.md              ← Full pipeline specification
meta/                ← Pipeline stages (interpreter → generator → factory → orchestrator)
evolution/           ← Self-evolution system (framework, genome, log)
templates/           ← Domain templates (reference only, NOT starting point)
generated/           ← Output of the meta-harness
memory/              ← Meta-level knowledge
scripts/             ← Utility scripts (verify, pre-task, quality-score)
```
