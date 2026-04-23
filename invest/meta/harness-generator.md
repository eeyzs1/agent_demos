# Meta-Harness-Generator: Task → Harness

## Purpose
Take a structured task definition and generate a task-specific harness.

## Generation Steps

1. **Select Base**: Match task domain to template in `templates/`
2. **Generate Constraints**: Each hard_constraint → constraint file. Each quality_attribute → implicit constraints (reliability→error handling, security→auth/validation, etc.)
3. **Generate Workflows**: Base flow: define→plan→execute→verify→record. Add domain-specific steps.
4. **Generate Skills**: Derive from task requirements. One skill = one focused capability.
5. **Generate Verification**: Each acceptance criterion → binary PASS/FAIL check.
6. **Generate AGENTS.md**: Project-specific master context under 60 lines.

## Output Structure
```
generated/[project-name]/
├── AGENTS.md              ← Project-specific context
├── .agents/
│   ├── constraints/       ← Generated constraints
│   ├── workflows/         ← Generated workflows
│   └── skills/            ← Generated skills
├── scripts/
│   ├── verify.sh          ← Generated verification
│   └── pre-task.sh        ← Generated pre-task checks
└── config/
    └── harness.yaml       ← Generated configuration
```

## Quality Check
- [ ] Every hard_constraint has a constraint file
- [ ] Every workflow has verification steps
- [ ] Every acceptance criterion has a check
- [ ] AGENTS.md is under 60 lines
- [ ] No orphaned or missing constraints

## Anti-Patterns
- No constraints without a requirement trace
- No verbatim template copies — adapt to the task
- No over-constraining — only prevent real failure modes
- No skipping verification — if unverifiable, requirement is vague
