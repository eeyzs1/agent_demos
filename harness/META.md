# META-HARNESS: Self-Bootstrapping Agent Infrastructure

## What This Is
A meta-harness that generates task-specific harnesses and agents from vague intent.
Generated harnesses and agents self-evolve. The evolution system itself also evolves.

## The Compilation Pipeline
```
Vague Intent → [Interpreter] → Structured Task
Structured Task → [Harness Generator] → Task-Specific Harness
Task-Specific Harness → [Agent Factory] → Specialized Agents
Specialized Agents + Harness → [Orchestrator] → Execution
Execution Results → [Evolution] → Improved Harness + Agents + Evolution Rules
```

## Architecture
```
META.md                    ← You are here. Full pipeline specification.
AGENTS.md                  ← Auto-loaded by Trae as project rules
CLAUDE.md                  ← Auto-loaded by Claude Code as project rules
meta/
  interpreter.md           ← Intent → Structured Task Definition
  harness-generator.md     ← Task Definition → Harness
  agent-factory.md         ← Harness → Agent Configurations
  orchestrator.md          ← Agents + Harness → Execution Plan
evolution/                 ← Self-evolution system
  framework.md             ← Evolution algorithm (genome, fitness, mutation, selection)
  genome.md                ← Current evolvable state (what can mutate)
  log.md                   ← Evolution history (fossil record)
templates/                 ← Reusable building blocks
generated/                 ← Output: generated harness+agent configurations
memory/                    ← Meta-level memory (compounds over time)
scripts/                   ← Utility scripts (not entry points)
```

## How to Bootstrap
1. User provides vague intent in their AI IDE (Trae/Claude Code/Cursor)
2. AI IDE auto-loads project rules (AGENTS.md for Trae, CLAUDE.md for Claude Code)
3. Rules instruct the AI to follow the pipeline below
4. Agent follows `meta/interpreter.md` to parse intent into structured task
5. Agent follows `meta/harness-generator.md` to generate a harness
6. Agent follows `meta/agent-factory.md` to create agent configurations
7. Agent follows `meta/orchestrator.md` to plan execution
8. Generated output goes to `generated/[project-name]/`
9. Execution begins with generated harness+agents
10. After execution, `evolution/framework.md` runs the evolution loop
11. Mutations that improve fitness are adopted, logged to `evolution/log.md`

## Meta-Rules (Cannot Be Overridden)
1. No execution without interpretation
2. No agent without a harness
3. No constraint without a reason
4. No completion without verification
5. Every generation is logged
6. Every failure improves the meta
7. The meta-harness follows its own rules
8. Evolution never removes the verification layer (cancer prevention)
9. Evolution never removes itself (suicide prevention)
10. All mutations are reversible (previous genome version is always preserved)
