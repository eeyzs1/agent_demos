# Architecture Decision Records

## Purpose
Document WHY architectural decisions were made.
Agents need to understand context to make consistent decisions.

## Decisions

### ADR-001: Five-Layer Harness Architecture
- Date: 2026-04-14
- Context: Need agent-agnostic quality infrastructure
- Decision: Organize harness into 5 layers (Identity, Constraints, Workflows, Verification, Memory)
- Alternatives: Single config file; prompt-only approach; tool-specific setup
- Why: Layers separate concerns. Each layer has a clear purpose and can evolve independently.
- Consequences: More files to maintain, but each file is small and focused.

### ADR-002: Mistake-Driven Constraint Evolution
- Date: 2026-04-14
- Context: Agents repeat the same mistakes across sessions
- Decision: Every mistake must produce a new or strengthened constraint
- Alternatives: Manual rule curation; ignoring mistakes; hoping agents learn
- Why: Without feedback loops, the harness degrades. With them, it compounds value over time.
- Consequences: Constraint set grows. Requires periodic pruning.

### ADR-003: Meta-Harness Self-Bootstrapping Architecture
- Date: 2026-04-14
- Context: Static harnesses require human setup for each new project/task type
- Decision: Build a meta-harness that generates task-specific harnesses from vague intent
- Alternatives: Manual harness creation per project; prompt-only approach; single generic harness
- Why: The real bottleneck isn't agent quality — it's harness setup time and expertise. A meta-harness eliminates both by compiling intent into infrastructure.
- Consequences: More complex system, but eliminates the human bottleneck. The meta-harness must be stable and self-improving.

### ADR-004: Compilation Pipeline (Interpreter → Generator → Factory → Orchestrator)
- Date: 2026-04-14
- Context: Need a deterministic process for turning vague intent into execution
- Decision: Four-stage compilation pipeline with clear inputs/outputs at each stage
- Alternatives: Single monolithic generation step; iterative refinement only
- Why: Each stage has a distinct responsibility. Separation enables independent improvement. Clear interfaces between stages enable debugging when generation fails.
- Consequences: More files to read, but each is focused. Pipeline can be extended at any stage.

### ADR-005: Template-Based Generation with Override
- Date: 2026-04-14
- Context: Generating from scratch every time is slow and error-prone
- Decision: Use domain templates as base, adapt to specific task requirements
- Alternatives: Always generate from scratch; rigid templates with no adaptation
- Why: Templates encode accumulated knowledge. Starting from a template is faster and more reliable than starting from zero. Adaptation ensures the harness fits the specific task.
- Consequences: Templates must be maintained. Bad templates produce bad harnesses. Template quality is a meta-concern that must be tracked.

### ADR-006: Self-Evolving Architecture with Meta-Evolution
- Date: 2026-04-14
- Context: Passive mistake-driven feedback is insufficient — the system only improves when it fails. No mechanism for proactive optimization.
- Decision: Add an evolution layer with three-tier genome (harness, agent, evolution rules) and A/B testing selection. The evolution genome itself can evolve (meta-evolution).
- Alternatives: Passive mistake-driven only; manual optimization; genetic algorithm without meta-evolution
- Why: Passive feedback is reactive. Evolution is proactive. Meta-evolution ensures the optimization process itself improves over time, preventing stagnation.
- Consequences: More complex system. Risk of destabilizing mutations. Mitigated by safety constraints (no removing verification, no removing evolution, mutation rate cap, reversibility).
