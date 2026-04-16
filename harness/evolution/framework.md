# Evolution Framework

## Purpose
Enable generated harnesses and agents to self-evolve. The evolution system itself also evolves.

## The Evolution Loop
```
Measure fitness → Propose mutation → Test mutation → Select or reject → Update genome
                                                              ↓
                                              Meta-evolution: update mutation/selection rules
```

## Genome (What Can Evolve)

### Level 1: Harness Genome
- Constraints (add/remove/modify rules)
- Workflows (add/remove/reorder steps)
- Skills (add/remove capabilities)
- Verification (add/remove checks, adjust thresholds)

### Level 2: Agent Genome
- Topology (add/remove agents, change connections)
- Scope (expand/restrict read/write/execute boundaries)
- Handoff formats (change data structures between agents)
- Context budget (adjust max_context_lines per role)

### Level 3: Evolution Genome (meta-evolution)
- Mutation operators (how mutations are proposed)
- Selection criteria (what counts as "better")
- Fitness weights (which metrics matter most)
- Mutation rate (how aggressively to mutate)

## Fitness Function
```yaml
fitness:
  dimensions:
    - name: verification_pass_rate
      weight: 0.3
      measure: percentage of tasks that pass all verification gates
      target: "> 95%"
    
    - name: task_completion_rate
      weight: 0.25
      measure: percentage of tasks completed without escalation
      target: "> 90%"
    
    - name: error_recurrence_rate
      weight: 0.2
      measure: percentage of mistakes that repeat
      target: "< 10%"
    
    - name: time_to_completion
      weight: 0.15
      measure: average time from task start to verified completion
      target: "decreasing trend"
    
    - name: constraint_efficiency
      weight: 0.1
      measure: ratio of constraints that prevented real failures vs total
      target: "> 50%"

  composite: weighted_sum(dimensions)
  direction: maximize
```

## Mutation Operators

### Constraint Mutations
- ADD: new constraint from mistake analysis or pattern recognition
- REMOVE: constraint that hasn't triggered in N generations (dead code)
- STRENGTHEN: make constraint more specific (narrow scope)
- WEAKEN: make constraint less restrictive (widen scope)
- MERGE: combine two related constraints into one
- SPLIT: break one constraint into two more specific ones

### Workflow Mutations
- INSERT_STEP: add a step between existing steps
- REMOVE_STEP: remove a step that doesn't add value
- REORDER: swap the order of two adjacent steps
- PARALLELIZE: convert sequential steps to parallel
- SEQUENTIALIZE: convert parallel steps to sequential

### Agent Mutations
- ADD_ROLE: introduce a new specialist agent
- REMOVE_ROLE: remove an underutilized agent
- MERGE_ROLES: combine two tightly coupled agents
- SPLIT_ROLE: divide an overloaded agent
- RESCOPE: change an agent's read/write/execute boundaries
- REWEIGHT: adjust context budget allocation

### Meta-Mutations (evolve the evolution system)
- ADJUST_FITNESS_WEIGHTS: change which metrics matter most
- ADJUST_MUTATION_RATE: change how aggressively to mutate
- ADD_MUTATION_OPERATOR: introduce a new type of mutation
- REMOVE_MUTATION_OPERATOR: remove an ineffective operator
- ADJUST_SELECTION_THRESHOLD: change how strict selection is

## Selection Mechanism

### A/B Testing Protocol
1. Record current fitness score (baseline)
2. Apply mutation to a COPY of the current genome
3. Run N tasks with the mutated genome
4. Compare fitness score against baseline
5. If fitness improved → adopt mutation, log to evolution-log.md
6. If fitness degraded → reject mutation, log why
7. If fitness unchanged → keep mutation if it reduces complexity, otherwise reject

### Safety Constraints on Evolution
- Never remove the verification layer (this would be cancer)
- Never remove the evolution system itself (this would be suicide)
- Never increase mutation rate above 30% per generation (this would be chaos)
- Every mutation must be reversible (keep previous genome version)
- Human can veto any mutation (mark as rejected in evolution-log.md)

## Evolution Triggers
- After every N completed tasks (periodic evolution)
- After every meta-mistake (reactive evolution)
- When fitness score drops below threshold (emergency evolution)
- When a new task pattern is detected (adaptive evolution)
