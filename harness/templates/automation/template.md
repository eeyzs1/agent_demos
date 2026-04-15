# Template: Automation

## When to Use
Task involves automating workflows, scheduling tasks, monitoring systems, or
creating event-driven processes.

## Default Constraints
- Every automation has a manual override
- Every action is logged with who/what/when/why
- Failed automations alert a human, not silently retry forever
- Automations are idempotent — safe to trigger multiple times
- Rate limits on all external interactions
- Circuit breakers on all external dependencies

## Default Workflows
- Create: define trigger → define conditions → define actions → add safety → test → deploy
- Debug: reproduce trigger → trace execution path → identify failure → fix → verify
- Scale: identify bottleneck → optimize or parallelize → load test → verify

## Default Skills
- Workflow design (trigger → condition → action)
- Error handling and retry logic
- Monitoring and alerting
- Integration with external systems
- Idempotency patterns

## Default Agent Topology
Planner-Executor pattern:
- Planner: designs the automation flow, defines triggers, conditions, and actions
- Executor: implements each automation step with safety measures

## Default Verification
- Automation triggers correctly
- Conditions are evaluated accurately
- Actions produce expected results
- Error handling works (simulate failures)
- Idempotency verified (trigger twice, same result)
- Manual override works
- Logging captures all relevant information

## Quality Attributes Priority
1. Reliability (automations run unattended)
2. Maintainability (automations change frequently)
3. Security (automations have system access)
4. Cost (failed automations waste resources)
