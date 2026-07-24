# Phase 1 Task Plan (Simplified)

**Status:** Single developer (D2) now owns all remaining implementation after D1/D2 integration checkpoint 2026-07-23.

Full rationale/detail lives in `tasks-detailed.md` — this version is for quick day-to-day reference.

---

## Ownership Model (Updated)

**Previous two-developer split is dissolved.** One developer now implements all remaining work in optimal sequence.

**Conceptual domains (still useful for understanding architecture):**
- **Policy & Financial Governance:** "What is this agent allowed to do and spend?"
- **Runtime Safety, Audit & Operator Control:** "Is this agent operational, can we stop it, and can we prove what happened?"

---

## What's Complete (Integration Checkpoint 2026-07-23)

**Completed D1 Work:**
- D1.1: Infrastructure (docker-compose, FastAPI, Postgres, Redis, OPA)
- D1.2: Agent + policy data model (agents table with shared_secret)
- D1.L: AgentLookup implementation (scripts/agent_lookup.py)
- D1.R: Redis client adapter (services/redis_client.py)

**Completed D2 Work:**
- D2.1: Identity verification (services/identity.py) — INTEGRATED
- D2.2: Runtime safety state (services/runtime_state.py) — INTEGRATED
- D2.FE: Frontend dashboard Phase 1 (frontend/src/**) — MOCK-BASED

**Integration:**
- Bootstrap wiring in main.py
- 89 tests passing

## The request pipeline (memorize this order)

```
Request → Identity check (✅ D2 complete) → Fleet halted? / Agent revoked? (✅ D2 complete)
        → Permission + amount check (TO DO) → Spend cap check (TO DO)
        → ALLOW/DENY → Write to audit log (TO DO)
```

---

## Remaining Implementation (All owned by D2)

### Phase 1: Core Services

**Audit Stream (sequential):**
| # | Task | Files | Dependencies |
|---|------|-------|--------------|
| 1 | Audit log table + migration | `db/models/audit_log.py`, migration | D1.2 ✅ |
| 2 | Hash-chain write (record_decision) | `services/hash_chain.py` | Task 1 |
| 3 | Chain verification (verify_chain) | `services/hash_chain.py` | Task 2 |

**Spend (independent):**
| # | Task | Files | Dependencies |
|---|------|-------|--------------|
| 4 | Spend caps + atomic budget | `services/spend.py` | D1.2 ✅ |

**Policy Stream (sequential):**
| # | Task | Files | Dependencies |
|---|------|-------|--------------|
| 5 | OPA/Rego policy integration | `policy/opa_client.py`, `.rego` | D1.2 ✅ |
| 6 | Python fallback for policy | `policy/fallback.py` | Task 5 |

**Testing (incremental with each):**
- Tasks 1-3: audit model tests, hash-chain tests, tamper detection tests
- Task 4: spend atomicity, fail-closed, concurrency tests
- Tasks 5-6: policy enforcement, OPA/fallback parity tests

### Phase 2: API Endpoints (depend on Phase 1)

| # | Task | Files | Dependencies |
|---|------|-------|--------------|
| 7 | Agent revoke/restore endpoints | `routers/runtime.py` | Task 2, D2.2 ✅ |
| 8 | Fleet halt/resume endpoints | `routers/fleet.py` | Task 2, D2.2 ✅ |
| 9 | Audit feed API (GET /audit/feed) | `routers/audit.py` | Task 1 |
| 10 | Audit query API (GET /audit/log) | `routers/audit.py` | Task 1 |
| 11 | Verify chain API (POST /audit/verify-chain) | `routers/audit.py` | Task 3 |
| 12 | Policy config API (PUT /agents/{id}/policy) | `routers/policies.py` | Tasks 4-6 |
| 13 | Spend reset API (POST /agents/{id}/reset-spend) | `routers/policies.py` | Task 4 |

### Phase 3: Orchestration (depends on Phase 1 + 2)

| # | Task | Files | Dependencies |
|---|------|-------|--------------|
| 14 | /action-request endpoint (full pipeline) | `routers/action.py`, `schemas/action.py` | Tasks 2,4-6, D2.1✅, D2.2✅ |

### Phase 4: Frontend Integration (depends on Phase 2 APIs)

| # | Task | Files | Dependencies |
|---|------|-------|--------------|
| 15 | Real API client (swap mocks) | `frontend/src/api/real.ts` | Tasks 7-13 |
| 16 | End-to-end frontend verification | manual | Task 15 |

### Phase 5: Demo & Testing (depends on everything)

| # | Task | Files | Dependencies |
|---|------|-------|--------------|
| 17 | Three demo agents + runner script | `demo/agents/*` | Task 14 |
| 18 | Complete test suite | `tests/test_policy*.py`, `test_audit*.py` | All implementation |
| 19 | Metrics collection (latency, propagation) | `middleware/timing.py` | Tasks 7-8, 14 |

---

## Previously Owned by D1 (Now D2)

The following tasks were originally assigned to D1 but are now implemented by D2:

**Files now owned by D2:**
- `routers/action.py` — orchestration endpoint
- `routers/policies.py` — policy/spend config APIs
- `schemas/action.py` — request/response schemas
- `schemas/agent.py` — agent schemas
- `policy/opa_client.py` — OPA integration
- `policy/fallback.py` — Python fallback
- `services/spend.py` — spend caps
- `middleware/timing.py` — latency
- `tests/test_policy_*.py` — policy tests
- `tests/test_spend_cap.py` — spend tests
- `tests/test_policy_latency.py` — latency tests

---

## Recommended Implementation Order (Vertical Milestones)

**Milestone A: Audit Foundation**
```
Task 1 (audit model/migration)
  → Task 2 (record_decision/hash chain)
  → Task 3 (verify_chain/tamper detection)
  → Tests: audit model, hash-chain, tamper detection
```

**Milestone B: Runtime Control APIs**
```
Task 7 (revoke/restore endpoints)
  → Task 8 (fleet halt/resume endpoints)
  → Tests: runtime control, fail-closed behavior
  (Uses audit foundation from A so control actions can be logged)
```

**Milestone C: Policy + Spend**
```
Task 4 (atomic spend caps)
  → Task 5 (OPA policy integration)
  → Task 6 (Python fallback)
  → Tests: spend atomicity/fail-closed/concurrency, policy enforcement, OPA/fallback parity
```

**Milestone D: Full /action-request Orchestration**
```
Task 14 (full pipeline)
  → Tests: check order, pipeline integration
  Pipeline: Identity → Fleet halted → Agent revoked
          → Permission/max-amount → Spend cap → ALLOW/DENY → Audit recording
```

**Milestone E: Remaining APIs**
```
Task 9 (audit feed API)
  → Task 10 (audit query API)
  → Task 11 (verify chain API)
  → Task 12 (policy config API)
  → Task 13 (spend reset API)
  → Task (agent/status APIs for frontend)
  → Tests: API integration
```

**Milestone F: Frontend Real-Backend Integration**
```
Task 15 (real API client, swap mocks)
  → Task 16 (end-to-end frontend verification)
```

**Milestone G: Demo + E2E + Metrics**
```
Task 17 (demo agents + runner)
  → Task 18 (complete test suite, regression testing)
  → Task 19 (metrics collection)
  → Deployment readiness
```

**Key Dependencies:**
- Audit stream (1→2→3) is sequential
- Policy stream (5→6) is sequential
- Runtime APIs (7→8) use audit foundation (A)
- Orchestration (D) needs audit (A), policy/spend (C), and identity/runtime (✅ complete)
- Frontend (F) needs APIs (E)
- Demo (G) needs full system (D+E+F)

---

## Three Rules That Still Apply

1. **One file, one owner** — All remaining files are now D2-owned
2. **Redis key domain ownership:**
   - `agent:{id}:remaining_budget` — D1 → D2 (spend enforcement)
   - `agent:{id}:status` — D2 (runtime safety) ✅
   - `fleet:halted` — D2 (fleet safety) ✅
3. **Frozen contracts remain frozen** — Do not change function signatures agreed upon on Day 1

---

## Hard Technical Dependencies (Still Apply)

- Audit_log migration (Task 1) requires agents migration (D1.2 ✅)
- Hash chain write (Task 2) requires audit_log table (Task 1)
- Chain verify (Task 3) requires hash chain write (Task 2)
- Revoke/halt APIs (Tasks 7-8) require record_decision (Task 2)
- Orchestration (Task 14) requires all services working

---

## Six-Beat Demo (Who It Proves)

| Beat | What happens | Implementation |
|---|---|---|
| 1 | Agent A does normal in-policy stuff | Tasks 4-6 (policy/spend), 14 (orchestration), 2 (audit) |
| 2 | Agent B tries out-of-policy / over-budget | Tasks 4-6 (policy/spend) |
| 3 | Operator revokes Agent B | Tasks 7 (revoke endpoint) |
| 4 | Agent C fires rapidly (runaway) | Task 14 (orchestration), all services |
| 5 | Operator hits fleet kill switch | Tasks 8 (halt endpoint) |
| 6 | Audit log filter + integrity check | Tasks 9-11 (audit APIs), 3 (verify) |

---

## PRD Coverage (All Requirements Mapped)

**Complete:** Identity (D2.1✅), Runtime state (D2.2✅), Frontend shell (D2.FE✅)

**Remaining:** Permissions/limits (Tasks 5-6), Spend caps (Task 4), Fail-closed (Task 4), Revocation (Task 7), Kill switch (Task 8), Audit log (Tasks 1-3), Hash chain (Tasks 2-3), Dashboard real (Tasks 15-16), Demo (Task 17), Metrics (Task 19)

No PRD requirements have been dropped.

---

## Gateway Check Order (Canonical)

This is the authoritative order for the /action-request pipeline:

```
1. Identity verification (verify_identity) ✅ COMPLETE
2. Fleet halted check (check_runtime_status) ✅ COMPLETE
3. Agent revoked check (check_runtime_status) ✅ COMPLETE
4. Permission/max-amount policy evaluation (evaluate_policy)
5. Spend-cap reservation (reserve_budget_atomic)
6. ALLOW/DENY decision
7. Audit recording (record_decision)
```

All denied requests short-circuit immediately with appropriate `reason_code`.

---

## Alembic Migration Notes

**Existing migration:** `09ee32e4e00a_create_agents_table.py` (revision: `09ee32e4e00a`)

**New audit migration should:**
- Use `alembic revision -m "create audit log table"`
- Set `down_revision = "09ee32e4e00a"`
- NOT be required to use filename "0002_audit_log.py"
- Create foreign key: `audit_log.agent_id → agents.id`

---

## [ARCHIVED] Historical D1/D2 Split

The following sections are preserved for historical attribution only. They do NOT govern current implementation.

**Completed D1 Work:**
- D1.1: Infrastructure (docker-compose, FastAPI, Postgres, Redis, OPA)
- D1.2: Agent + policy data model (agents table with shared_secret)
- D1.L: AgentLookup implementation
- D1.R: Redis client adapter

**Completed D2 Work:**
- D2.1: Identity verification
- D2.2: Runtime safety state
- D2.FE: Frontend dashboard Phase 1

**Current Status:** Single developer (D2) owns all remaining implementation.
