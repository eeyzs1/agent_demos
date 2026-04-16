# Harness Engineering Framework

## What This Is
A SELF-BOOTSTRAPPING meta-harness that generates, executes, and EVOLVES task-specific harnesses and agents.
Give it a fuzzy goal → it generates the harness + agents → they execute → they self-evolve.

## Two Modes of Operation

### Mode 1: Meta-Harness (Generate + Evolve)
You have a vague intent and need the system to figure out everything.
→ Read `META.md` and follow the compilation pipeline.

### Mode 2: Generated Harness (Execute)
You are working within a generated harness for a specific project.
→ Read the generated `AGENTS.md` in `generated/[project]/`.

## Architecture
```
META.md                  ← Meta-harness bootstrap DNA
meta/                    ← Compilation pipeline (4 stages)
evolution/               ← Self-evolution system
  framework.md             Genome, fitness, mutation, selection
  genome.md                Current evolvable state
  log.md                   Evolution history
templates/               ← Reusable building blocks
generated/               ← Output of the meta-harness
memory/                  ← Meta-level knowledge (cross-project)
scripts/                 ← Platform-agnostic (bash: Linux/macOS/WSL)
```

## Meta-Rules
1. No execution without interpretation
2. No agent without a harness
3. No constraint without a reason
4. No completion without verification
5. Every generation is logged
6. Every failure improves the meta
7. The meta-harness follows its own rules
8. Evolution never removes verification (cancer prevention)
9. Evolution never removes itself (suicide prevention)
10. All mutations are reversible

## Quick Start
```bash
./scripts/bootstrap.sh "我需要一个客户入驻系统"
```
Then an agent reads META.md and follows the pipeline.
After execution, the evolution loop runs automatically.
