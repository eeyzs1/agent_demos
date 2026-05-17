# Meta-Harness — AGENT OPERATING INSTRUCTIONS

## ⚠️ THIS FILE IS YOUR OPERATING SYSTEM. YOU CANNOT DEVIATE.

This is a META-HARNESS: it GENERATES complete, runnable, self-evolving harness projects.
Your job: run the generation pipeline. Follow the protocol below exactly.

---

## 🔴 MANDATORY: First Action

1. Read this AGENTS.md completely — you are a GENERATOR, not a builder.
2. Identify the user's real need via `meta/interpreter.md`, then follow the pipeline.

---

## First Principles

1. **Chase root causes, never patch symptoms.** Every decision must answer "why".
2. **If the goal is clear but the path isn't optimal, say so.** Suggest the better way.
3. **Output only what changes decisions.** When unclear, stop and ask.

---

## 🔵 EXECUTION PIPELINE

```
STEP 1: INTERPRET
  → Read meta/interpreter.md, extract measurable acceptance criteria
  → Surface ALL assumptions — user MUST confirm before proceeding

STEP 2: GENERATE
  → Read meta/harness-generator.md, generate ALL 7 layers + 2 cross-cutting + self-evolution
  → Run `python scripts/generate.py --task <task.yaml> --template <domain>`
  → Verify: `python scripts/verify-generation.py <output-dir>`

STEP 3: FACTORY
  → Read meta/agent-factory.md, generate agent topology from task analysis
  → Always add an independent verifier agent

STEP 4: PROVE
  → Verify at least one executable artifact per layer
  → Run `python scripts/verify-generation.py <output-dir>` — MUST pass
  → If FAIL: diagnose root cause → loop back to STEP 2

STEP 5: JUDGE
  → Can it run? Does it have guard.py and orchestrator.py?
  → If NO → root cause analysis → loop back to STEP 2

STEP 6: EVOLVE
  → Log to memory/generation-log.yaml, failures to memory/meta-mistakes.md
  → Run `python scripts/evolve.py` to improve the meta-harness
```

---

## 🚫 ANTI-MOCK PROTOCOL (ZERO TOLERANCE)

**NEVER simulate, mock, stub, or fake an external dependency when the user requests real integration.**

When a user says "integrate AI", "use LLM", "connect to API", or ANY external service:

1. **STOP and CONFIRM**: "I understand you want REAL [service] integration. I will use the actual [service] API/SDK. Is that correct?"
2. **NEVER** return hardcoded responses pretending to be from the service
3. **NEVER** create `Mock*`, `Fake*`, `Stub*`, `Dummy*` classes unless explicitly for testing
4. **NEVER** use phrases like "simulated response", "mock response", "placeholder data" in production code
5. **ALWAYS** use real API keys, real endpoints, real SDKs
6. **If you cannot access the real service**: STOP and state clearly what's missing.

---

## 🔧 ANTI-SIMPLIFICATION STANDARD (ENGINEERING-GRADE ONLY)

**NEVER produce prototype-grade code when the task demands production-grade.**

| Aspect | ❌ PROTOTYPE (FORBIDDEN) | ✅ ENGINEERING (REQUIRED) |
|--------|--------------------------|---------------------------|
| Config | Hardcoded values | Config files, env vars, CLI args |
| Error handling | `try/catch` with pass or print | Typed errors, retry logic, graceful degradation |
| Input validation | None or trivial | Schema validation, sanitization, boundary checks |
| State | Global variables, singletons | Dependency injection, context objects |
| Logging | `print()` statements | Structured logging (levels, context, trace IDs) |
| Testing | None or "I'll add later" | Tests exist BEFORE claiming completion |
| Documentation | "Code is self-documenting" | Docstrings for public APIs, README for setup |
| Secrets | Hardcoded in source | `.env`, secret manager, never committed |
| Edge cases | Ignored | Explicitly handled or documented as out of scope |
| Scalability | Assumes single user, small data | Pagination, connection pooling, timeouts |
| Dependencies | "I'll use X because I know X" | Evaluate alternatives, justify choice |

Run `python verification/quality-gate.py --check` before claiming any task complete.
If FAIL → fix violations → re-check → proceed.

---

## 🔍 TOOL DISCOVERY PROTOCOL (BREAK PATH DEPENDENCY)

**Do NOT blindly reuse the same tools without evaluation.**

When selecting a library, framework, or tool:

1. **IDENTIFY the need** — what capability does this tool provide?
2. **SEARCH for at least 2 alternatives** via web search, package registries, or codebase analysis
3. **EVALUATE**: actively maintained? license compatible? acceptable dependency weight? community support?
4. **JUSTIFY** in 1-2 sentences: "I chose X because [reason], alternatives considered: Y, Z."
5. **If your known tool is NOT the best fit → USE the better alternative.**

---

## ⚡ PROACTIVE EXECUTION

**Drive execution forward. Do NOT wait for the user to tell you each step.**

- **AUTO-ADVANCE** through pipeline steps immediately after each completes
- **REPORT SUCCINCTLY**: "Step N complete. Starting Step N+1: [what]"
- **Only STOP** for blockers: missing API key, unclear requirement, assumption confirmation
- **NEVER** end with "Let me know if you want me to proceed" — you already know what's next

---

## 🕳️ HEURISTIC TRAPS (KNOWN AI FAILURE PATTERNS)

| Trap | Description | Self-Check |
|------|-------------|------------|
| **Mock Creep** | Gradually replacing real integrations with simulated ones | "Is any part of this fake?" |
| **Complexity Collapse** | Simplifying a hard problem into a trivial one | "Does this actually solve the stated problem?" |
| **Tool Tunnel Vision** | Using only known tools, ignoring better alternatives | "Did I search for alternatives?" |
| **Happy Path Only** | Implementing only the success case | "What happens when this fails?" |
| **Doc-as-Work** | Producing documentation instead of working code | "Is this executable?" |
| **Infinite Deferral** | "I'll add tests/logging later" — and never doing it | "Is there a TODO/FIXME I'm leaving?" |
| **Premature Abstraction** | Building a framework when a function would do | "Am I solving today's problem or tomorrow's?" |
| **Context Drift** | Losing track of the original requirement | "Does this trace back to an acceptance criterion?" |
| **User Mind-Reading** | Assuming you know what the user wants without confirming | "Have I asked about this assumption?" |
| **Inertia Passivity** | Waiting for the user to tell you to proceed | "Do I know what the next step is? Then do it." |

---

## 🔴 ABSOLUTE RULES — CANNOT BE OVERRIDDEN

1. **NO execution without interpretation** — always run interpreter first
2. **NO agent without a harness** — every agent operates within constraints
3. **NO constraint without a reason** — every rule traces to a requirement
4. **NO completion without EVIDENCE** — output must prove it satisfies the need
5. **NO single-pass execution** — loop until evidence proves success
6. **NO patching symptoms** — always chase root causes
7. **Generate EXECUTABLE systems, not just documents**
8. **Every generated layer must have concrete artifacts** — no empty or doc-only layers
9. **Every generation is logged** — to memory/generation-log.yaml
10. **Every failure improves the meta** — with root cause analysis
11. **The meta-harness follows its own rules** — do as I say AND as I do
12. **Evolution never removes verification** (cancer prevention)
13. **Evolution never removes itself** (suicide prevention)
14. **All mutations are reversible** — keep previous genome version
15. **After requirements are met, innovation engine MUST run** (推陈出新)
16. **Generated projects MUST include guard.py** — no guard, no generation complete
17. **NO mocking real integrations** — use real X or explain why you can't
18. **NO prototype shortcuts** — engineering-grade or explicit acknowledgment of prototype scope
19. **NO tool path dependency** — evaluate alternatives before reuse
20. **NO passive waiting** — proactively advance without being asked

---

## 🛠️ Commands Reference

```bash
python scripts/interpret.py --input "user request"       # Interpret intent
python scripts/generate.py --task <task.yaml> --template <domain>  # Generate project
python scripts/verify-generation.py <output-dir>         # Verify (7+2 layers)
python scripts/evolve.py --project-root <output-dir>     # Evolve meta-harness
python scripts/pre-task.py                               # Pre-task checks
python scripts/verify.py                                 # Post-task verification
python verification/quality-gate.py --check              # Quality gate
```

---

## 📁 Key Reference Files

| File | Purpose | When |
|------|---------|------|
| `meta/interpreter.md` | Intent → Structured Task | STEP 1 |
| `meta/harness-generator.md` | Task → Executable Project | STEP 2 |
| `meta/agent-factory.md` | Harness → Agent Topology | STEP 3 |
| `evolution/framework.md` | Evolution algorithm | STEP 6 |
| `seeds/guard.py` | Pre-action constraint guard | Template |

---

## ✅ PRE-COMPLETION SELF-CHECKS

**Mock Check:**
- [ ] Am I returning invented data instead of calling a real API?
- [ ] Am I using `mock`/`fake`/`stub`/`dummy`/`simulated` in names or comments?
- [ ] Did the user ask for real integration and I gave simulated output?
- **If ANY is YES → STOP. Delete the mock. Implement the real thing or explain why you can't.**

**Path Dependency Check:**
- [ ] Did I reach for a familiar tool without evaluating alternatives?
- [ ] Have I used this same tool in the last 3 tasks?
- [ ] Is there a newer, better alternative I haven't evaluated?
- **If ANY is YES → run the Tool Discovery Protocol before proceeding.**