# Harness Engineering Framework

> Just say what you want. The system handles the rest.

## What Is This?

Imagine: you have an idea but don't know how to build it. You tell this system "I need a customer onboarding system", and it:

1. **Understands your idea** — translates vague intent into a clear task definition
2. **Designs how to work** — auto-generates rules, workflows, and checkpoints
3. **Assigns specialist roles** — creates a team of AI agents, each with a specific job
4. **Orchestrates execution** — plans who goes first, who goes next, who works in parallel
5. **Verifies results** — automatically checks if output meets the bar
6. **Gets smarter over time** — every mistake makes the system better
7. **Self-evolves** — actively optimizes its own rules, workflows, and agent configurations; the evolution rules themselves also evolve

**In one sentence**: This is an "evolving AI agent management system" — it ensures AI agents produce reliable work, and keeps getting more reliable.

---

## How Do I Use It?

### If You're Not a Developer

You don't need to know code. Just open this project in an AI coding tool and tell it what you want.

**Supported tools and context loading:**

| Tool | Rules File | Loading | What You Need to Do |
|------|-----------|---------|-------------------|
| **Trae** | `AGENTS.md` | ✅ Auto-loaded | Just open the project |
| **Claude Code** | `CLAUDE.md` | ✅ Auto-loaded | Just open the project |
| **Cursor** | `.cursorrules` | ⚠️ Manual | Copy `AGENTS.md` contents to `.cursorrules` |
| **Other AI tools** | — | ⚠️ Manual | Paste `AGENTS.md` contents into the conversation as context |

**Critical: The AI MUST read the rules file to follow the pipeline.** If the AI doesn't read the rules, it will skip the pipeline and start working on its own — that's not what we want.

**Examples — just say:**

- "I need a customer onboarding system"
- "Build me a competitor price monitoring tool"
- "I want to automate our weekly report generation"
- "Create a SaaS for freelance invoicing"

The AI **automatically reads the project rules** (no manual action needed), then:
- Parses your requirements
- Generates constraints and workflows tailored to the task
- Creates specialized agents to execute
- Verifies the results meet your standards

**You only need to do two things:**
1. **Say what you want** (the vaguer, the better — the system will help you clarify)
2. **Confirm assumptions** (the system will list its assumptions; just confirm or correct them)

**Why will the AI follow the rules?** Because the rule files (`AGENTS.md` / `CLAUDE.md`) are auto-loaded by the AI IDE as "project rules" — the AI reads them before every conversation. These aren't suggestions — they're the AI's operating instructions.

**What if the AI doesn't read the rules?** You'll notice the AI starts coding or planning immediately instead of asking you to confirm the task definition first. In that case, manually paste the contents of `AGENTS.md` into the conversation.

### If You're a Software Engineer

This project is a **self-bootstrapping meta-harness** — it's not a harness for a specific project, it's a **harness that generates harnesses**.

**Core formula:**
```
Agent = Model + Harness
```
- The Model provides intelligence
- The Harness makes that intelligence reliably useful
- **A better Harness often matters more than a better Model**

**Compilation pipeline:**
```
Vague Intent → [Interpreter] → Structured Task Definition
                      ↓
               [Harness Generator] → Constraints, Workflows, Skills
                      ↓
               [Agent Factory] → Specialized Agent Topology (generated, not selected)
                      ↓
               [Orchestrator] → Execution Plan
                      ↓
               Agents execute within generated harness → Results
                      ↓
               Failure feedback → Meta-Harness improves
                      ↓
               [Evolution] → Harness + Agents + Evolution Rules self-improve
```

**Quick start:**

1. Open this project in Trae / Claude Code
2. Tell the AI what you want (e.g., "I need a customer onboarding system")
3. The AI auto-reads project rules and follows the pipeline
4. Confirm the assumptions the AI lists
5. The AI generates harness + agent configurations and executes

---

## Project Structure

```
README.md           ← Chinese version
README_EN.md        ← You are here
AGENTS.md           ← ⚡ Auto-loaded project rules (Trae entry point)
CLAUDE.md           ← ⚡ Auto-loaded project rules (Claude Code entry point)
META.md             ← The system's DNA (full pipeline specification)
│
meta/               ← The four stages of the compilation pipeline
  interpreter.md      Step 1: Intent → Structured Task
  harness-generator.md Step 2: Task → Harness
  agent-factory.md    Step 3: Harness → Agent Topology
  orchestrator.md     Step 4: Agents → Execution Plan
  examples/           Reference examples (not preset templates)
    topologies.md       Agent topology examples
│
evolution/          ← Self-evolution system
  framework.md        Evolution algorithm (genome, fitness, mutation, selection)
  genome.md           Current evolvable state (what can mutate)
  log.md              Evolution history (fossil record)
│
templates/          ← Domain templates (building blocks for generation)
  web-app/            Web application
  api-service/        API service
  data-pipeline/      Data pipeline
  content-system/     Content system
  automation/         Automation
│
generated/          ← Generation output (result of each compilation)
memory/             ← Meta-knowledge (cross-project, compounding over time)
  generation-log.md   Every generation is tracked
  meta-mistakes.md    Generation failures → pipeline improvements
  task-patterns.md    Known task patterns (faster interpretation)
  decisions.md        Architecture decision records
  progress.md         Execution progress
│
scripts/            ← Verification and check scripts (bash: Linux/macOS/WSL)
  verify-spec.md      Declarative: WHAT to check
  verify.sh           Executable: HOW to check
  pre-task.sh         Pre-task validation
  quality-score.sh    Health metrics
```

---

## Key Concepts

### What Is a Harness?

A Harness is a **constraints + tools + verification** system built around AI agents. Just as a horse needs a harness to run in the right direction, AI agents need a harness to produce reliably.

Without a harness: the agent might get it right, might get it wrong — you won't know which.
With a harness: mistakes get caught, correct work gets verified, results are predictable.

### Why a "Meta"-Harness?

Regular harness: humans manually write rules → agents follow rules
Meta-harness: humans provide intent → **the system auto-generates rules** → agents follow generated rules

This means you don't need to manually set up infrastructure for each project — the system generates it based on your needs.

### Why Do Mistakes Make the System Stronger?

Every generation failure gets root-cause-analyzed and logged to `memory/meta-mistakes.md`, then the generation pipeline is improved. This creates a **compounding feedback loop**:

```
Mistake → Root Cause Analysis → Constraint Improvement → Better Future Generations → Fewer Mistakes
```

The more you use it, the smarter it gets. This is the fundamental difference from a traditional template library.

### Agent Topology Is Dynamically Generated

The system doesn't pick from 5 preset patterns. It **synthesizes** the optimal agent graph from task analysis:

1. Identify work units (each constraint, workflow step, domain)
2. Map dependencies
3. Determine parallelism
4. Assign roles (merge tightly coupled, split when context exceeds budget)
5. Add verification layer (there must ALWAYS be an independent verifier)
6. Define handoff points

### The System Self-Evolves

This is the most radical design. The system doesn't just learn from mistakes — it **actively optimizes itself**:

**Three-layer genome (what can evolve):**
- **Harness genome**: constraints, workflows, skills, verification rules
- **Agent genome**: topology, role scope, handoff formats, context budgets
- **Evolution genome** (meta-evolution): mutation operators, selection criteria, fitness weights, mutation rate

**Evolution loop:**
```
Measure fitness → Propose mutation → Test mutation → Select or reject → Update genome
                                                                    ↓
                                                      Meta-evolution: update mutation/selection rules themselves
```

**Safety constraints (preventing "cancer" and "suicide"):**
- Never remove the verification layer (otherwise the system accepts wrong results — "cancer")
- Never remove the evolution system itself (otherwise the system stops evolving — "suicide")
- Mutation rate never exceeds 30% (otherwise the system descends into chaos)
- All mutations must be reversible (previous genome version is always preserved)

---

## Verification Mechanism

The system uses a **two-layer verification approach**:

| Layer | File | Purpose |
|---|---|---|
| Declarative | `scripts/verify-spec.md` | Defines **WHAT to check** (platform-agnostic) |
| Executable | `scripts/verify.sh` | Implements **HOW to check** (bash script) |

AI agents read the declarative layer and translate checks to their current platform. Humans can run the scripts directly.

---

## AI Agent Instructions

<!-- AGENT-INSTRUCTION: If you are an AI agent, follow the instructions below. -->

### You Are an AI Agent. Start Here.

1. **Read `META.md`** — it contains the full compilation pipeline
2. **Follow the pipeline stages in order:**
   - `meta/interpreter.md` — parse user intent into a structured task
   - `meta/harness-generator.md` — generate a task-specific harness
   - `meta/agent-factory.md` — generate agent topology (from analysis, NOT from presets)
   - `meta/orchestrator.md` — plan execution
3. **Output goes to `generated/[project-name]/`**
4. **Log every generation to `memory/generation-log.md`**
5. **Log every failure to `memory/meta-mistakes.md`**

### Mandatory Rules

- No execution without interpretation — run the interpreter first
- No agent without a harness — every agent operates within generated constraints
- No constraint without a reason — every rule must trace to a task requirement
- No completion without verification — run `scripts/verify.sh` after changes
- Agent topology is GENERATED from task analysis, not selected from presets
- Context files must stay under 60 lines
- Evolution must never remove verification (cancer prevention)
- Evolution must never remove itself (suicide prevention)
- All mutations must be reversible

### If You're Working in a Generated Project

1. Read `generated/[project]/AGENTS.md` — that's the project-specific harness
2. Follow the workflows defined there
3. Stay within the constraints defined there
4. Run verification after every change
