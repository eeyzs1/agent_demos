# Meta-Harness — AGENT OPERATING INSTRUCTIONS

## ⚠️ MANDATORY: Read This Before Taking Any Action

This project is a META-HARNESS — it does NOT do the work itself.
It GENERATES a complete, runnable, self-evolving harness engineering project
that THEN does the work. Your job is to run the generation pipeline.

## First Principles (Override Everything Else)

1. **Do not assume the user knows what they want.** When unclear, STOP and discuss.
2. **If the goal is clear but the path isn't optimal, say so.** Suggest the better way.
3. **Chase root causes, never patch symptoms.** Every decision must answer "why".
4. **Output only what changes decisions.** Cut everything else.

## The Core Loop

```
┌─→ INTERPRET: What does the user actually need? (first principles)
│       ↓
│   GENERATE: Create a COMPLETE harness project (7 layers + 2 cross-cutting + evolution)
│       ↓
│   PROVE:   Does the generated project cover all 7 layers? Can it run? Can it evolve?
│       ↓
│   JUDGE:   Is the generated project sufficient? ──→ NO → root cause → loop back
│       ↓
│   YES
│       ↓
└── EVOLVE:  What did we learn about generation? Improve the meta-harness.
```

## Step-by-Step Protocol

### Step 1: Interpret (First Principles)
Read `meta/interpreter.md`. Understand the REAL need.
Do NOT start from templates. Start from the problem.

### Step 2: Generate Complete Harness Project
Read `meta/harness-generator.md`. Generate ALL seven layers:
1. Context Engineering (AGENTS.md, context loader, knowledge index)
2. Tool Integration (schemas, sandbox, permissions, MCP)
3. Memory & State (session state, long-term memory, snapshots, compression)
4. Planning & Orchestration (DAG, flow control, sub-agents, budgets)
5. Verification & Guardrails (format validators, consistency, security, self-check)
6. Feedback & Self-Healing (error capture, retry, optimization loop, human interface)
7. Constraints & Entropy (architecture rules, enforcement, entropy reduction, cost)

Plus two cross-cutting systems:
- Security & Isolation (sandbox, encryption, audit)
- Observability & Governance (tracing, metrics, replay, versioning)

Plus self-evolution system (evidence-driven).

### Step 3: Generate Agent Topology
Read `meta/agent-factory.md`. Generate topology from task analysis.

### Step 4: Prove Completeness
For each of the 7 layers + 2 cross-cutting systems:
- Verify at least one concrete artifact was generated
- Verify artifacts are executable, not just documentation
- Verify evidence traceability exists

### Step 5: Judge
Can the generated project actually run and self-evolve?
If NO → diagnose root cause, loop back.

### Step 6: Evolve Meta-Harness
What did we learn about the generation process? Improve `meta/` and `templates/`.

## Absolute Rules

1. No execution without interpretation
2. No agent without a harness
3. No constraint without a reason
4. No completion without EVIDENCE
5. No single-pass execution — loop until proven
6. No patching symptoms — chase root causes
7. Generate EXECUTABLE systems, not just documents
8. Every generated layer must have concrete artifacts
9. Evolution never removes verification or itself
10. All mutations reversible
