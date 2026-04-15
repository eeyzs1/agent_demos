# Meta-Interpreter: Intent → Structured Task

## Purpose
Transform vague human intent into a structured task definition.

## Process

### Step 1: Classify Domain
Determine domain(s): software_development, data_processing, content_generation, automation, decision_support, hybrid

### Step 2: Extract Core Requirements
```yaml
task:
  name: [concise name]
  domain: [from classification]
  goal: [success in one sentence]
  scale: [personal|team|organization|public]
  quality_attributes: [ranked top 3]
  hard_constraints: [non-negotiable]
  soft_constraints: [preferences]
  unknowns: [what needs discovery]
  template: [template name or "custom"]
  acceptance_criteria: [measurable outcomes]
  assumptions: [assumptions made — user can correct]
```

### Step 3: Match Template
- Clear match → use that template
- Partial match → combine templates
- No match → generate from scratch

### Step 4: Define Acceptance Criteria
- What does "done" look like?
- What would the user say "this is exactly what I needed"?
- What would the user say "this is NOT what I wanted"?

### Step 5: Surface Assumptions
List every assumption. This is the ONLY point where human intervention is required.

## Anti-Patterns
- Do NOT add requirements the user didn't mention
- Do NOT skip unknowns — flag them explicitly
- Do NOT over-specify — leave room for harness-generator
- Do NOT assume the first statement is the real need
