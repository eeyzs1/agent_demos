# Template: Web Application

## When to Use
Task involves building a user-facing web application with frontend + backend.

## Default Constraints
- Frontend and backend are separate layers
- No business logic in presentation layer
- No direct database access from frontend
- All API endpoints have input validation
- Authentication required for non-public endpoints
- Responsive design (mobile-first)

## Default Workflows
- Feature: define → design API → implement backend → implement frontend → integrate → test → review
- Bugfix: reproduce → diagnose root cause → fix → test → verify → prevent
- Deploy: build → test → stage → verify → promote → monitor

## Default Skills
- API design (REST/GraphQL endpoint design)
- Frontend component development
- Database schema design
- Authentication/authorization
- Testing (unit + integration + E2E)

## Default Agent Topology
Three-Agent pattern:
- Planner: designs API contracts and component structure
- Executor: implements backend and frontend
- Verifier: runs tests, checks accessibility, validates API contracts

## Default Verification
- Lint passes (frontend + backend)
- Type check passes
- Unit tests pass
- Integration tests pass
- Build succeeds
- No console errors in production build
- API contract tests pass

## Quality Attributes Priority
1. Reliability (users depend on this)
2. Security (user data is involved)
3. Usability (user-facing product)
4. Maintainability (will evolve over time)
5. Speed (performance matters but not at cost of reliability)
