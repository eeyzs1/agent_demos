# META-HARNESS: Self-Bootstrapping Agent Infrastructure

## What This Is
A meta-harness that generates, executes, proves, and evolves task-specific harnesses and agents.
First principles driven. Evidence based. Never stops at one pass.

## The Core Loop (NOT a Pipeline)
```
┌─→ INTERPRET: What does the user actually need? (first principles)
│       ↓
│   GENERATE: Create harness + agents for THIS specific need
│       ↓
│   EXECUTE: Do the work within generated constraints
│       ↓
│   PROVE:   Produce EVIDENCE that output satisfies original need
│       ↓
│   JUDGE:   Does the evidence convince? ──→ NO → root cause → loop back
│       ↓
│   YES
│       ↓
└── EVOLVE:  What did we learn? Improve based on evidence. Then STOP.
```

## Architecture
```
AGENTS.md                  ← Auto-loaded by Trae (primary entry point)
CLAUDE.md                  ← Auto-loaded by Claude Code
META.md                    ← You are here. Full specification.
meta/
  interpreter.md           ← Intent → Structured Task (first principles)
  harness-generator.md     ← Task → Harness
  agent-factory.md         ← Harness → Agent Topology (generated, not selected)
  orchestrator.md          ← Loop execution + evidence traceability
evolution/                 ← Evidence-driven self-evolution
  framework.md             ← Genome, fitness, mutation, selection (all evidence-based)
  genome.md                ← Current evolvable state
  log.md                   ← Evolution history
templates/                 ← Domain templates (reference only, NOT starting point)
generated/                 ← Output: generated harness+agent configurations
memory/                    ← Meta-level memory (compounds over time)
scripts/                   ← Utility scripts (not entry points)
```

## First Principles (Override Everything)
1. Do not assume the user knows what they want — ask if unclear
2. If goal is clear but path isn't optimal, say so and suggest better
3. Chase root causes, never patch symptoms — every decision answers "why"
4. Output only what changes decisions — cut everything else

## Meta-Rules (Cannot Be Overridden)
1. No execution without interpretation
2. No agent without a harness
3. No constraint without a reason
4. No completion without EVIDENCE — output must prove it satisfies the original need
5. No single-pass execution — the loop continues until evidence proves success
6. No patching symptoms — always chase root causes
7. Every generation is logged
8. Every failure improves the meta (with root cause)
9. The meta-harness follows its own rules
10. Evolution never removes verification (cancer prevention)
11. Evolution never removes itself (suicide prevention)
12. All mutations are reversible
