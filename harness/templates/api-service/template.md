# Template: API Service

## When to Use
Task involves building a backend API service (REST, GraphQL, gRPC).

## Default Constraints
- API versioning from day one
- All endpoints have rate limiting
- Request/response schemas are explicit and validated
- No business logic in route handlers
- Database access only through repository layer
- Structured error responses with error codes
- API documentation auto-generated from code

## Default Workflows
- Feature: define contract → implement repository → implement service → implement route → test → document
- Bugfix: reproduce via API call → trace through layers → fix at correct layer → test → verify
- Performance: profile → identify bottleneck → optimize → benchmark → verify no regression

## Default Skills
- API contract design (OpenAPI/GraphQL schema)
- Database query optimization
- Authentication middleware
- Error handling patterns
- API documentation

## Default Agent Topology
Planner-Executor pattern:
- Planner: designs API contracts, data models, and service interfaces
- Executor: implements each endpoint with repository pattern

## Default Verification
- API contract tests pass
- Unit tests for each layer
- Integration tests for endpoints
- Lint and type check pass
- No unhandled error paths
- Response times within budget

## Quality Attributes Priority
1. Reliability (other services depend on this)
2. Maintainability (APIs live long)
3. Speed (latency matters)
4. Security (data exposure risk)
