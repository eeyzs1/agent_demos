# Harness Engineering Framework

## What This Is
A SELF-BOOTSTRAPPING meta-harness that generates task-specific harnesses and agents from vague intent.
Give it a fuzzy goal → it generates the harness + agents → they execute.

## Two Modes of Operation

### Mode 1: Meta-Harness (Generate)
You have a vague intent and need the system to figure out everything.
→ Read `META.md` and follow the compilation pipeline.

### Mode 2: Generated Harness (Execute)
You are working within a generated harness for a specific project.
→ Read the generated `AGENTS.md` in `generated/[project]/`.

## Architecture
```
META.md                  ← Meta-harness bootstrap DNA
meta/
  interpreter.md         ← Intent → Structured Task
  harness-generator.md   ← Task → Harness
  agent-factory.md       ← Harness → Agents (topology GENERATED, not selected)
  orchestrator.md        ← Agents → Execution Plan
templates/               ← Reusable building blocks
generated/               ← Output of the meta-harness
memory/                  ← Meta-level knowledge (cross-project)
scripts/                 ← Platform-agnostic (bash, works on Linux/macOS/WSL)
  verify-spec.md         ← Declarative: WHAT to check (agents translate to HOW)
```

## Meta-Rules
1. No execution without interpretation
2. No agent without a harness
3. No constraint without a reason
4. No completion without verification
5. Every generation is logged
6. Every failure improves the meta
7. The meta-harness follows its own rules

## Quick Start
```bash
# Give a vague intent, get a generated harness+agents
./scripts/bootstrap.sh "I need a customer onboarding system"
```
Then an agent reads META.md and follows the pipeline.
