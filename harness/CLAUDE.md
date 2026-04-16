# Harness Engineering Framework — AGENT OPERATING INSTRUCTIONS

## ⚠️ MANDATORY: Read This Before Taking Any Action

You are operating inside a meta-harness system. You MUST follow these instructions.
Do NOT skip to coding. Do NOT plan on your own. Follow the pipeline below.

## When User Gives a Task (ANY task)

STOP. Do NOT start coding. Do NOT start planning on your own.
Follow this exact pipeline:

### Step 1: Interpret Intent
Read `meta/interpreter.md` and follow its instructions.
Parse the user's intent into a structured task definition.
Output the task definition and present assumptions to the user for confirmation.

### Step 2: Generate Harness
After user confirms the task definition, read `meta/harness-generator.md`.
Generate a task-specific harness in `generated/[task-name]/`.

### Step 3: Generate Agent Topology
Read `meta/agent-factory.md`. Generate agent configurations.
Do NOT pick from preset patterns — generate topology from task analysis.

### Step 4: Plan Execution
Read `meta/orchestrator.md`. Create an execution plan.

### Step 5: Execute
Execute within the generated harness. Follow its constraints and workflows.

### Step 6: Verify
Run verification after every change. No task is complete until verification passes.

### Step 7: Evolve
After execution, read `evolution/framework.md`. Measure fitness.
If fitness can improve, propose and test mutations.

## When Working in a Generated Project

If `generated/[project]/AGENTS.md` exists, read it and follow its rules.
That file contains the project-specific harness — constraints, workflows, skills.

## Absolute Rules (NEVER Violate)

1. No execution without interpretation — always run the interpreter first
2. No agent without a harness — always generate constraints before executing
3. No constraint without a reason — every rule must trace to a requirement
4. No completion without verification — run verification after every change
5. Every generation logged to `memory/generation-log.md`
6. Every failure logged to `memory/meta-mistakes.md`
7. Evolution never removes verification (cancer prevention)
8. Evolution never removes itself (suicide prevention)
9. All mutations must be reversible
10. Context files stay under 60 lines

## Architecture Reference
```
META.md              ← Full pipeline specification
meta/                ← Pipeline stages (interpreter → generator → factory → orchestrator)
evolution/           ← Self-evolution system (framework, genome, log)
templates/           ← Domain templates (web-app, api-service, data-pipeline, content-system, automation)
generated/           ← Output of the meta-harness
memory/              ← Meta-level knowledge (generation-log, meta-mistakes, task-patterns, decisions, progress)
scripts/             ← Utility scripts (verify, pre-task, quality-score)
```
