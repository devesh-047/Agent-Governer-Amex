# Phase 1 Parallel Development Plan

**Project:** Governance Layer for Financial Agents (Amex CodeStop 2026, Phase 1 Hybrid v2)
**Status of repo at time of writing:** Greenfield. No existing backend, frontend, migrations, or infra config exist yet. This plan defines the target repository structure/contracts both developers scaffold toward, and divides the implementation work along a **conceptual ownership boundary** rather than an arbitrary file split.

**Revision note:** This version rebalances ownership from the original draft, in which Developer 1 held nearly the entire enforcement/gateway/runtime-safety path (identity, policy, spend, revocation, kill switch, fail-closed, metrics) while Developer 2 held only audit/dashboard/demo. That draft technically minimized file overlap but left D1 with almost all of the governance-critical backend logic. The division below instead splits governance itself into two coherent, technically substantial halves — **"what may this agent do and spend"** (D1) vs. **"is this agent allowed to operate right now, and can we prove what happened"** (D2) — so both developers own real backend/security logic, not just "backend vs. frontend."

---

## Architecture and Existing-Code Assessment

No code exists yet. The layout below is the design baseline both developers commit to on Day 1.

```
repo/
├── docker-compose.yml                  # SHARED — single owner: D1 (infra scaffold owner, not a claim on backend logic)
├── .env.example                        # SHARED — single owner: D1
├── README.md                           # joint, finalized at integration
├── tasks.md
├── backend/
│   ├── alembic.ini
│   ├── alembic/versions/               # ordered migrations
│   ├── app/
│   │   ├── main.py                     # FastAPI bootstrap + router registration — owner: D1
│   │   ├── config.py                   # owner: D1
│   │   ├── db/
│   │   │   ├── session.py              # owner: D1
│   │   │   └── models/
│   │   │       ├── agent.py            # owner: D1 (contract frozen with D2 input on identity/runtime fields — see Shared Agent Fields)
│   │   │       └── audit_log.py        # owner: D2
│   │   ├── schemas/
│   │   │   ├── action.py               # owner: D1 (ActionRequest/ActionDecision + DecisionEvent interface type)
│   │   │   ├── agent.py                # owner: D1, contract frozen with D2 input
│   │   │   └── audit.py                # owner: D2 (AuditLogEntry, RuntimeStatus, FleetState)
│   │   ├── policy/                     # owner: D1
│   │   │   ├── opa_client.py
│   │   │   ├── fallback.py
│   │   │   └── rego/
│   │   ├── services/
│   │   │   ├── spend.py                # owner: D1 — reserve_budget_atomic()
│   │   │   ├── identity.py             # owner: D2 — verify_identity()
│   │   │   ├── runtime_state.py        # owner: D2 — check_runtime_status(), revoke/restore/halt/resume logic, fail-closed wrapper
│   │   │   └── hash_chain.py           # owner: D2 — record_decision(), verify_chain()
│   │   ├── routers/
│   │   │   ├── action.py               # owner: D1 — POST /action-request (orchestration only)
│   │   │   ├── policies.py             # owner: D1 — policy config + spend reset/config
│   │   │   ├── runtime.py              # owner: D2 — revoke/restore/agent runtime status
│   │   │   ├── fleet.py                # owner: D2 — halt/resume
│   │   │   └── audit.py                # owner: D2 — activity feed, audit query, verify-chain
│   │   └── demo/
│   │       └── agents/                 # owner: D2 — three scripted agents + runner
│   └── tests/
│       ├── test_policy_enforcement.py  # owner: D1
│       ├── test_spend_cap.py           # owner: D1
│       ├── test_policy_latency.py      # owner: D1
│       ├── test_identity.py            # owner: D2
│       ├── test_runtime_safety.py      # owner: D2 (revoke/restore/halt/resume/fail-closed)
│       ├── test_audit_and_hash_chain.py# owner: D2
│       ├── test_tamper_detection.py    # owner: D2
│       └── test_demo_scenario_e2e.py   # joint — written last, during integration
└── frontend/
    └── src/
        ├── api/
        │   ├── client.ts              # SHARED — single owner: D2
        │   └── types.ts               # SHARED — single owner: D2, mirrors backend schemas from both developers
        ├── components/
        │   ├── ActivityFeed.tsx        # owner: D2 — calls D2 audit API
        │   ├── AuditLogTable.tsx       # owner: D2
        │   ├── RevokeRestoreControls.tsx # owner: D2 — calls D2 runtime API
        │   ├── FleetKillSwitch.tsx     # owner: D2 — calls D2 fleet API
        │   ├── PolicyConfigPanel.tsx   # owner: D2 (UI) — calls D1 policy API; contains no enforcement logic
        │   └── IntegrityCheckButton.tsx# owner: D2
        └── pages/
            └── Dashboard.tsx           # owner: D2
```

**Conceptual ownership boundary (drives every section below):**

- **Developer 1 — Policy & Financial Governance.** Answers *"What is this agent allowed to do, and how much financial authority does it have?"* Owns the orchestration endpoint, the OPA/Rego + fallback policy engine, permission enforcement, max-single-transaction enforcement, dynamic spend caps, atomic budget reservation, and the policy/spend Redis state and APIs.
- **Developer 2 — Runtime Safety, Audit & Operator Control.** Answers *"Is this agent operational, can we stop it instantly, and can we prove what happened?"* Owns identity verification, per-agent revocation/restore, the fleet kill switch/resume, fail-closed runtime behavior, the audit log + hash chain, chain-integrity verification, the operator dashboard, the scripted demo agents, and the six-beat orchestration.

**Why this split and not the file-count-minimizing one:** identity verification and runtime-safety checks (kill switch, revocation, fail-closed) are conceptually part of the same "is this agent allowed to operate" question as audit/proof — both are about *runtime trust*, independent of *what the agent is permitted to spend*. Grouping them with D2 gives D2 real backend/security ownership (not just persistence and UI) while D1 keeps a coherent, self-contained financial-governance domain. The one place this crosses a single file (`agents` table, which contains both policy fields and identity/runtime fields) is handled explicitly in "Shared Agent Fields" below rather than by splitting the file.

---

## Shared Contracts / Integration Contract

Frozen on Day 1 before either developer writes feature code. Changing any of them afterward requires both developers to agree synchronously (see Merge-Safety Rules).

### Action request contract — `POST /action-request`

**Request headers:**
- `X-Agent-Id: <agent_id>`
- `X-Agent-Secret: <shared_secret>`

**Request body (`ActionRequest`, owner: D1):**
```json
{
  "action_type": "refund | limit_adjustment | card_replacement",
  "amount": 125.00,
  "metadata": { "...": "optional, action-specific" }
}
```

**Response body (`ActionDecision`, owner: D1):**
```json
{
  "decision": "allow | deny",
  "reason": "string | null",
  "reason_code": "IDENTITY_FAILED | FLEET_HALTED | AGENT_REVOKED | PERMISSION_DENIED | AMOUNT_EXCEEDS_LIMIT | SPEND_CAP_EXCEEDED | RUNTIME_STATE_UNAVAILABLE | OK",
  "remaining_budget": 375.00,
  "audit_log_id": "uuid | null",
  "policy_version": "string"
}
```

**Critical request pipeline (must not change) — this is the backbone of the whole split:**

```
Agent Request
      ↓
FastAPI Gateway / Request Orchestration        (D1 — routers/action.py, owns the pipeline shape)
      ↓
Identity Verification                          (D2 — services/identity.verify_identity())
      ↓
Runtime Safety Check
  - fleet halted?
  - agent revoked?                             (D2 — services/runtime_state.check_runtime_status())
      ↓
Permission / OPA Policy Evaluation              (D1 — policy/opa_client.py + fallback.py)
      ↓
Transaction Limit + Spend Cap Enforcement       (D1 — services/spend.reserve_budget_atomic())
      ↓
ALLOW / DENY
      ↓
Audit Recording + Hash Chain                    (D2 — services/hash_chain.record_decision())
```

D1 owns the orchestration file (`routers/action.py`) and the *order* of the pipeline, but D1's code **calls** D2-owned functions rather than implementing identity/runtime-safety/audit logic itself:

```python
# owned and implemented by D2, called by D1's orchestration
verify_identity(agent_id: str, secret: str) -> IdentityResult
check_runtime_status(agent_id: str) -> RuntimeStatus   # { fleet_halted: bool, agent_revoked: bool }
record_decision(event: DecisionEvent) -> AuditWriteResult  # { audit_log_id, hash }

# owned and implemented by D1, called from within D1's own orchestration
evaluate_policy(agent, action_type, amount) -> PolicyResult
reserve_budget_atomic(agent_id: str, amount: float) -> SpendResult
```

Exact function names may be adjusted during implementation, but this call structure — D1 orchestrates and owns policy/spend logic, D2 owns identity/runtime-safety/audit logic and exposes it as callable functions — must be preserved. **Denial semantics:** any failed stage short-circuits immediately with `decision: "deny"` and the corresponding `reason_code`; later stages are never evaluated. HTTP status is `200` for a completed decision except `401` for identity failure. If D2's runtime-state check cannot reach Redis, it returns a `RuntimeStatus` indicating unavailable, and D1's orchestration treats that as `deny` + `reason_code: RUNTIME_STATE_UNAVAILABLE` (the fail-closed *behavior* is implemented inside D2's `check_runtime_status()`/`reserve_budget_atomic()` respectively — see Redis Ownership below for the split between runtime-safety fail-closed (D2) and spend-state fail-closed (D1, since `remaining_budget` is D1's Redis domain)).

### Control APIs

| Endpoint | Method | Owner | Purpose |
|---|---|---|---|
| `/agents/{agent_id}/revoke` | POST | **D2** | Set agent runtime status → `revoked` in Redis; logs the action |
| `/agents/{agent_id}/restore` | POST | **D2** | Set agent runtime status → `active` |
| `/fleet/halt` | POST | **D2** | Set `fleet_halted = true` in Redis; logs the action |
| `/fleet/resume` | POST | **D2** | Set `fleet_halted = false` |
| `/agents/{agent_id}/runtime-status` | GET | **D2** | Fetch live runtime status (revoked/active, fleet_halted) |
| `/agents/{agent_id}/reset-spend` | POST | **D1** | Reset `remaining_budget` to `daily_cap` (demo reset) |
| `/agents/{agent_id}/policy` | PUT | **D1** | Update permissions/max_single_amount/daily_cap |
| `/agents/{agent_id}` | GET | **D1** | Fetch combined `AgentStatus` view (policy fields from D1's model + live runtime fields via D2's `check_runtime_status()`) |
| `/agents` | GET | **D1** | List all agents + combined status (dashboard + demo agent bootstrap) |

Note on `/agents/{agent_id}` and `/agents`: these live in D1's `routers/policies.py`/`action.py` area because the *primary* record (the `agents` table) is D1's, but the handler calls D2's `check_runtime_status()` to fill in live revoked/fleet-halted fields rather than reading Redis directly — this keeps the runtime-safety Redis domain exclusively behind D2's function, per Redis Ownership below.

All control-API actions (revoke, restore, halt, resume) write an audit row via D2's own `record_decision()` — since D2 owns both the control endpoints and the audit-write path, this is an in-subsystem call, not a cross-developer dependency.

### Audit APIs (owner: D2)

| Endpoint | Method | Purpose |
|---|---|---|
| `/audit/feed` | GET | Recent decisions, polled every 1–2s for the live activity feed |
| `/audit/log` | GET | Filterable audit log: `?agent_id=&action_type=&decision=&from=&to=` |
| `/audit/verify-chain` | POST | Recompute hash chain top-to-bottom; returns `{ "intact": true }` or `{ "intact": false, "broken_at_row": 42 }` |

### Shared data structures

| Structure | Owner | Fields |
|---|---|---|
| `Agent` (DB model) | **D1** (contract frozen with D2 input — see Shared Agent Fields) | `id, name, permissions (jsonb), max_single_amount, daily_cap, shared_secret` (identity field, D2 requirement) |
| `ActionRequest` / `ActionDecision` | D1 | as above |
| `PolicyResult`, `SpendResult` | D1 | policy/spend internal contracts |
| `IdentityResult` | D2 | `{ valid: bool, agent_id: str | null }` |
| `RuntimeStatus` | D2 | `{ fleet_halted: bool, agent_revoked: bool, available: bool }` (`available: false` triggers fail-closed deny) |
| `AgentStatus` (composed API view) | **D1** (composes D1's own fields + calls D2's `check_runtime_status()` for live fields) | `id, name, permissions, max_single_amount, daily_cap, remaining_budget, status (active/revoked), fleet_halted` |
| `FleetState` | D2 | `{ fleet_halted: bool }` |
| `AuditLogEntry` | D2 | `id, timestamp, agent_id, action_type, amount, decision, reason, reason_code, policy_version, prev_hash, hash` |
| `DecisionEvent` (interface D1 calls into D2's `record_decision`) | D1 defines the shape, D2 implements the function | `{ agent_id, action_type, amount, decision, reason, reason_code, policy_version, timestamp }` |

---

## Redis Key Ownership

Redis is shared infrastructure (single `docker-compose.yml` service, owner D1 for the infra file itself), but **key-domain ownership is split by function, not assigned wholesale to one developer**:

```
agent:{id}:status         → owner: D2   (runtime active/revoked state — identity/runtime-safety domain)
fleet:halted               → owner: D2   (fleet-wide runtime safety state)
agent:{id}:remaining_budget → owner: D1   (financial/spend enforcement state)
```

**Rule:** neither developer reads or writes the other's Redis keys directly. D1's `reserve_budget_atomic()` only ever touches `agent:{id}:remaining_budget`. D2's `check_runtime_status()` only ever touches `agent:{id}:status` and `fleet:halted`. If D1's orchestration needs runtime status, it calls D2's function — it never issues its own Redis `GET` against `agent:{id}:status`. This is the Redis-layer equivalent of the file-ownership rule and is what keeps the two Redis-touching code paths mergeable without coordination.

**Fail-closed responsibility is correspondingly split:** D2's `check_runtime_status()` fails closed (returns `available: false` → deny) if Redis is unreachable for the `status`/`fleet:halted` keys. D1's `reserve_budget_atomic()` independently fails closed (deny) if Redis is unreachable for the `remaining_budget` key. Both are one `try/except` each, in each developer's own service file — not a shared implementation.

---

## Shared Agent Fields — Day-1 Contract

The `agents` table necessarily has one file owner (D1, since it holds `permissions`/`max_single_amount`/`daily_cap`), but it also holds `shared_secret`, which is D2's identity domain. Rather than giving both developers edit access to `agent.py`:

1. **D2 specifies the identity-field requirements on Day 1** before the model/migration is frozen: field name (`shared_secret`), type, and any constraints (e.g., generated at seed time, not rotated/expiring per §5.0 of the PRD).
2. **D1 incorporates those fields into the single model file and migration** as part of D1.2 (below).
3. After the Day-1 freeze, if D2 needs a new identity-related field on `Agent`, that's a message to D1, not a direct edit to `agent.py` — same rule as any other shared-contract change.
4. Runtime active/revoked state itself does **not** live as a column on `Agent` — it lives in Redis (`agent:{id}:status`) under D2's exclusive ownership, precisely so D2 never needs write access to `agent.py` after the Day-1 freeze.

---

## Developer 1 — Policy & Financial Governance

**Owns the question:** *"What is this agent allowed to do, and how much financial authority does it have?"*

### Ownership

- **Owns and creates:** `docker-compose.yml`, `.env.example`, `backend/app/main.py`, `backend/app/config.py`, `backend/app/db/session.py`, `backend/app/db/models/agent.py`, `backend/app/schemas/action.py`, `backend/app/schemas/agent.py`, `backend/app/policy/*`, `backend/app/services/spend.py`, `backend/app/routers/action.py`, `backend/app/routers/policies.py`, `backend/tests/test_policy_enforcement.py`, `backend/tests/test_spend_cap.py`, `backend/tests/test_policy_latency.py`, `backend/alembic/versions/0001_agents.py`.
- **May modify (with care):** `README.md` (own section only).
- **Must avoid editing:** `backend/app/db/models/audit_log.py`, `backend/app/schemas/audit.py`, `backend/app/services/identity.py`, `backend/app/services/runtime_state.py`, `backend/app/services/hash_chain.py`, `backend/app/routers/runtime.py`, `backend/app/routers/fleet.py`, `backend/app/routers/audit.py`, anything under `backend/app/demo/`, anything under `frontend/`, `backend/alembic/versions/0002_audit_log.py` and later, the `agent:{id}:status` / `fleet:halted` Redis keys.

**Important:** owning infrastructure scaffolding (`docker-compose.yml`, initial `main.py`, `.env.example`) is a file-ownership convenience to avoid two people editing deploy config — it is **not** a claim on backend functionality. D2 independently implements identity, runtime-safety, audit, and dashboard modules once the Day-1 scaffold and shared contracts exist; D1 does not build those subsystems.

### Tasks

#### D1.1 — Infrastructure & repo scaffolding
- **Objective:** Stand up the skeleton both developers build on: FastAPI app, Postgres, Redis, OPA containers, Alembic wired up, env template. This is purely enabling infrastructure, not a claim on any subsystem's logic.
- **Implementation requirements:** `docker-compose.yml` with services `api`, `postgres`, `redis`, `opa`; `backend/app/main.py` with an empty router-registration block (D1 will later register `action.py` and `policies.py` directly, and register D2's `runtime.py`/`fleet.py`/`audit.py` routers once D2 hands them off — see Merge-Safety Rules) and a health-check route; `.env.example` covering `DATABASE_URL`, `REDIS_URL`, `OPA_URL`; Alembic initialized with an empty baseline migration.
- **PRD requirement:** §7 (Tech Stack Decisions), Day 1 of §10.
- **Files:** `docker-compose.yml`, `.env.example`, `backend/app/main.py`, `backend/alembic.ini`, `backend/alembic/env.py`.
- **Dependencies:** None — Day 1 blocker for both developers; land and communicate immediately.
- **Definition of Done:** `docker compose up` brings up all four services; `GET /health` returns 200; empty Alembic migration applies cleanly.
- **Tests/verification:** Manual smoke test (`curl localhost:8000/health`).

#### D1.2 — Agent + policy data model & migration
- **Objective:** Create the `agents` table containing both policy fields (D1's domain) and the identity field D2 requires (`shared_secret`), per the Shared Agent Fields Day-1 contract.
- **Implementation requirements:** Model with `id, name, permissions (jsonb), max_single_amount, daily_cap, shared_secret` (§8). **Before finalizing**, D1 confirms the `shared_secret` field spec with D2 (type, generation approach) per Shared Agent Fields. No runtime `status` column — that lives in Redis under D2 ownership.
- **PRD requirement:** §8 Data Model, §5.1, §5.0 (identity field requirement, D2-specified).
- **Files:** `backend/app/db/models/agent.py`, `backend/alembic/versions/0001_agents.py`.
- **Dependencies:** D1.1; contract-only dependency on D2's identity-field spec (see Dependency and Handoff Points — this is a quick Day-1 conversation, not a blocking wait).
- **Definition of Done:** Migration creates the table with correct types/constraints, including the D2-specified `shared_secret` field; a seed script (`backend/app/db/seed.py`, D1-owned) inserts the three demo agents' base records with placeholder secrets.
- **Tests/verification:** `test_policy_enforcement.py` fixture confirms seeded agents load correctly.

#### D1.3 — Main action-request orchestration/gateway
- **Objective:** Implement `POST /action-request` as the single orchestration pipeline described in the Critical Request Pipeline, calling into D2's identity/runtime-safety/audit functions and D1's own policy/spend functions in the correct order.
- **Implementation requirements:** Pipeline exactly matching: `verify_identity()` (D2) → `check_runtime_status()` (D2) → `evaluate_policy()` (D1) → `reserve_budget_atomic()` (D1) → finalize decision → `record_decision()` (D2). Short-circuit at each stage. Until D2's real implementations land, D1 develops against **stub/mock versions** of `verify_identity`, `check_runtime_status`, and `record_decision` matching the frozen interface shapes — swapped for the real thing at integration with no orchestration code changes required.
- **PRD requirement:** §4 check order, §5 overview.
- **Files:** `backend/app/routers/action.py`, `backend/app/schemas/action.py` (includes the `DecisionEvent` interface type D1 defines and D2 implements against).
- **Dependencies:** D1.2. Contract-only dependency on D2's function signatures (agreed Day 1, not on D2's implementation being finished — see Dependency and Handoff Points).
- **Definition of Done:** Endpoint compiles and runs end-to-end against stubs, returning correctly-shaped `ActionDecision` objects for every short-circuit path; zero orchestration changes needed once D2's real functions are swapped in.
- **Tests/verification:** `test_policy_enforcement.py::test_check_order` — asserts stages run/short-circuit in the documented order using mocked D2 functions.

#### D1.4 — OPA/Rego policy integration
- **Objective:** Implement `evaluate_policy()`'s permission and max-single-transaction-amount checks via OPA.
- **Implementation requirements:** Rego policy: `allow { input.action in agent.permissions; input.amount <= agent.max_single_amount }`; `opa_client.py` calling the OPA container.
- **PRD requirement:** §5.1 Permission Model, §7 tech stack.
- **Files:** `backend/app/policy/opa_client.py`, `backend/app/policy/rego/*.rego`.
- **Dependencies:** D1.2 (needs `permissions`/`max_single_amount` fields).
- **Definition of Done:** Permission and max-amount violations correctly denied with `reason_code: PERMISSION_DENIED` / `AMOUNT_EXCEEDS_LIMIT` via OPA.
- **Tests/verification:** `test_policy_enforcement.py::test_opa_permission_and_limit`.

#### D1.5 — Plain-Python policy fallback
- **Objective:** Implement an equivalent `evaluate_policy()` path in plain Python against the same config structure, selectable via config flag, per the PRD's OPA-risk mitigation.
- **Implementation requirements:** `fallback.py` mirrors the Rego logic exactly; a config flag (`POLICY_ENGINE=opa|fallback`) selects the engine with no other code changes.
- **PRD requirement:** §7, §12 risk (OPA integration eats too much time → timeboxed fallback).
- **Files:** `backend/app/policy/fallback.py`.
- **Dependencies:** D1.4 (same test fixtures, parametrized over both engines).
- **Definition of Done:** Both OPA and fallback paths produce identical allow/deny results for the same test inputs.
- **Tests/verification:** `test_policy_enforcement.py::test_opa_fallback_parity` — parametrized over `POLICY_ENGINE=opa` and `POLICY_ENGINE=fallback`.

#### D1.6 — Dynamic spend caps + atomic budget reservation
- **Objective:** Implement `reserve_budget_atomic()` using atomic Redis operations against `agent:{id}:remaining_budget`, with no check-then-act race window, and its own independent fail-closed behavior for the spend-state Redis domain.
- **Implementation requirements:** `DECRBY` the requested amount first; if resulting value `< 0`, deny and issue a compensating `INCRBY` (§5.2); wrap Redis access in `try/except` — if `remaining_budget` is unreachable, deny with `reason_code: SPEND_CAP_EXCEEDED`'s sibling case (or a dedicated code, e.g. `SPEND_STATE_UNAVAILABLE`) rather than allowing.
- **PRD requirement:** §5.2 Dynamic Spend Caps (atomicity explicit); fail-closed principle applied to the spend-state Redis domain specifically (D2 owns the equivalent for runtime-safety keys).
- **Files:** `backend/app/services/spend.py`.
- **Dependencies:** D1.3, D1.2.
- **Definition of Done:** Concurrent requests near the cap boundary never both succeed when only one should; denied-for-cap requests leave `remaining_budget` unchanged; simulated Redis outage on this key results in deny.
- **Tests/verification:** `test_spend_cap.py::test_atomic_concurrent_requests`, `test_spend_cap.py::test_compensating_decrement`, `test_spend_cap.py::test_spend_state_fail_closed`.

#### D1.7 — Policy configuration API + spend reset/config API
- **Objective:** Implement `routers/policies.py`: `PUT /agents/{id}/policy`, `POST /agents/{id}/reset-spend`, plus the composed `GET /agents` / `GET /agents/{id}` views (which call D2's `check_runtime_status()` for live fields).
- **Implementation requirements:** Policy edits take effect on the *next* request (no caching that would mask a live edit), matching §5.5. `AgentStatus` response composes D1's own fields with a call into D2's `check_runtime_status()` — D1 never reads `agent:{id}:status`/`fleet:halted` directly.
- **PRD requirement:** §5.1 (policy profile), §5.5 (policy config panel backend), §5.2 (reset button).
- **Files:** `backend/app/routers/policies.py`, `backend/app/schemas/agent.py`.
- **Dependencies:** D1.2, D1.4/D1.5; contract-only dependency on D2's `check_runtime_status()` signature for the composed view (mockable — see Dependency and Handoff Points).
- **Definition of Done:** Editing an agent's `max_single_amount` via `PUT` changes the very next `/action-request` outcome without restart; `GET /agents/{id}` returns both policy and (mocked, then real) runtime fields.
- **Tests/verification:** `test_policy_enforcement.py::test_live_policy_edit`.

#### D1.8 — Policy & spend enforcement test suite
- **Objective:** Consolidate D1's automated test coverage: permission enforcement, OPA/fallback consistency, max-single-amount, dynamic spend caps, atomic concurrent spend, and policy-update-affects-future-decisions.
- **Implementation requirements:** Fixed suite of scripted violation attempts asserted 100% denied (feeds the §9 enforcement-accuracy metric); concurrency test for atomic spend.
- **PRD requirement:** §9 Policy enforcement accuracy.
- **Files:** `backend/tests/test_policy_enforcement.py`, `backend/tests/test_spend_cap.py`.
- **Dependencies:** D1.4–D1.7.
- **Definition of Done:** Test run reports 100% correct denial of the scripted violation suite; concrete pass/fail output usable in the submission writeup.
- **Tests/verification:** CI/local test run output.

#### D1.9 — Gateway/policy/spend latency metrics
- **Objective:** Produce the §9 gateway-latency measurement.
- **Implementation requirements:** Lightweight timing middleware or per-request instrumentation around the orchestration pipeline, reporting p50/p95 request latency.
- **PRD requirement:** §9 Latency (under ~100ms, measured).
- **Files:** `backend/app/middleware/timing.py` (new, D1-owned), `backend/tests/test_policy_latency.py`.
- **Dependencies:** D1.3.
- **Definition of Done:** A test/benchmark run produces a concrete latency number pastable into the submission writeup.
- **Tests/verification:** `test_policy_latency.py` output.

---

## Developer 2 — Runtime Safety, Audit & Operator Control

**Owns the question:** *"Is this agent operational, can we stop it instantly, and can we prove what happened?"*

### Ownership

- **Owns and creates:** `backend/app/services/identity.py`, `backend/app/services/runtime_state.py`, `backend/app/services/hash_chain.py`, `backend/app/db/models/audit_log.py`, `backend/app/schemas/audit.py`, `backend/app/routers/runtime.py`, `backend/app/routers/fleet.py`, `backend/app/routers/audit.py`, `backend/app/demo/agents/*`, `backend/tests/test_identity.py`, `backend/tests/test_runtime_safety.py`, `backend/tests/test_audit_and_hash_chain.py`, `backend/tests/test_tamper_detection.py`, `backend/alembic/versions/0002_audit_log.py`, all of `frontend/`.
- **May modify (with care):** `README.md` (own section only).
- **Must avoid editing:** `backend/app/main.py`, `backend/app/config.py`, `backend/app/db/session.py`, `backend/app/db/models/agent.py`, `backend/app/schemas/action.py`, `backend/app/schemas/agent.py`, `backend/app/policy/*`, `backend/app/services/spend.py`, `backend/app/routers/action.py`, `backend/app/routers/policies.py`, `docker-compose.yml`, `.env.example`, `backend/alembic/versions/0001_agents.py`, the `agent:{id}:remaining_budget` Redis key.

### Tasks

#### D2.1 — Identity contract + implementation
- **Objective:** Implement `verify_identity(agent_id, secret) -> IdentityResult`, and specify the `shared_secret` field requirement to D1 as the Day-1 handoff (Shared Agent Fields).
- **Implementation requirements:** Lookup agent by `agent_id` (via D1's `Agent` model, read-only from D2's side — no edits to `agent.py`), constant-time compare of `shared_secret`; returns `IdentityResult{ valid, agent_id }`. Per §5.0, document in code comments that this is intentionally not a rotating/expiring credential.
- **PRD requirement:** §5.0 Lightweight Identity Check.
- **Files:** `backend/app/services/identity.py`.
- **Dependencies:** Contract-only dependency on D1's `Agent` model existing with the `shared_secret` field D2 specified — D2 can write and unit-test `verify_identity()` against a mocked agent-lookup function before D1.2 lands, then swap in the real DB call once it's merged (see Dependency and Handoff Points).
- **Definition of Done:** Requests with wrong/missing secret produce `IdentityResult{ valid: false }`; correct requests pass.
- **Tests/verification:** `test_identity.py::test_identity_rejection` — wrong secret, missing header, correct secret cases.

#### D2.2 — Runtime safety Redis layer
- **Objective:** Implement `check_runtime_status(agent_id) -> RuntimeStatus`, establishing the `agent:{id}:status` and `fleet:halted` Redis key conventions under exclusive D2 ownership.
- **Implementation requirements:** Reads both keys, returns `RuntimeStatus{ fleet_halted, agent_revoked, available }`; wraps Redis access in `try/except` — connection error/timeout sets `available: false`, which D1's orchestration treats as fail-closed deny (§5.3 fail-closed principle, applied here to the runtime-safety key domain).
- **PRD requirement:** §5.3 Revocation & Emergency Stop (state layer), fail-closed behavior for kill-switch/revocation checks.
- **Files:** `backend/app/services/runtime_state.py`.
- **Dependencies:** D1.1 (Redis container available) — no dependency on D1's application code; can be developed and unit-tested in isolation against a local Redis instance.
- **Definition of Done:** Function correctly reflects live Redis state; simulated Redis outage (e.g., stop the Redis container in a test) results in `available: false`.
- **Tests/verification:** `test_runtime_safety.py::test_runtime_status_fail_closed`.

#### D2.3 — Per-agent revocation/restore
- **Objective:** Implement `POST /agents/{id}/revoke` and `POST /agents/{id}/restore` in `routers/runtime.py`, flipping `agent:{id}:status` in Redis.
- **Implementation requirements:** Revoke sets status to `revoked`; restore sets it to `active` (needed for demo reset). Both call D2's own `record_decision()` to log the control action (§5.3: "Both actions are themselves logged to the audit trail").
- **PRD requirement:** §5.3 per-agent revoke.
- **Files:** `backend/app/routers/runtime.py`.
- **Dependencies:** D2.2, D2.7 (audit write function, though this can also start against a local stub while D2.7 is in progress — same-developer, so purely sequencing, not a cross-developer blocker).
- **Definition of Done:** Revoked agent is denied on its very next `/action-request` (verified together with D1.3's orchestration); restore reverses it.
- **Tests/verification:** `test_runtime_safety.py::test_revoke_and_restore`.

#### D2.4 — Fleet kill switch/resume
- **Objective:** Implement `POST /fleet/halt` and `POST /fleet/resume` in `routers/fleet.py`, flipping `fleet:halted` in Redis.
- **Implementation requirements:** Halt/resume each call `record_decision()` to log the control action.
- **PRD requirement:** §5.3 fleet-wide kill switch.
- **Files:** `backend/app/routers/fleet.py`.
- **Dependencies:** D2.2, D2.7.
- **Definition of Done:** Fleet halt blocks all agents instantly (including previously-unrevoked ones), verified together with D1.3's orchestration; resume reverses it.
- **Tests/verification:** `test_runtime_safety.py::test_fleet_halt_and_resume`.

#### D2.5 — Fail-closed runtime behavior (consolidation)
- **Objective:** Ensure fail-closed behavior is consistently enforced across all runtime-safety paths (D2.2's core implementation) and explicitly verified end-to-end with D1's orchestration.
- **Implementation requirements:** Confirm `check_runtime_status()`'s `available: false` path is correctly interpreted as deny by D1's orchestration (joint verification, not a joint implementation — D2 owns the source of the signal, D1 owns interpreting it per the frozen `RuntimeStatus` contract).
- **PRD requirement:** §5.3 fail-closed behavior ("what happens if your control plane goes down?").
- **Files:** `backend/app/services/runtime_state.py` (no new file — this task is verification-focused).
- **Dependencies:** D2.2, D1.3.
- **Definition of Done:** End-to-end test: stop Redis mid-scenario, confirm `/action-request` denies with `RUNTIME_STATE_UNAVAILABLE` rather than allowing.
- **Tests/verification:** `test_runtime_safety.py::test_end_to_end_fail_closed` (integration-time test, run once both D1.3 and D2.2 exist).

#### D2.6 — Audit model + persistence
- **Objective:** Create the append-only Postgres `audit_log` table with hash-chain columns and DB-level immutability as a secondary safety net.
- **Implementation requirements:** Columns per §8: `id, timestamp, agent_id, action_type, amount, decision, reason, reason_code, policy_version, prev_hash, hash`. Revoke `UPDATE`/`DELETE` grants on the table for the application role.
- **PRD requirement:** §5.4 Audit Log, §8 Data Model.
- **Files:** `backend/app/db/models/audit_log.py`, `backend/alembic/versions/0002_audit_log.py` (must be ordered/numbered after D1's `0001_agents.py` — hard dependency, since `audit_log.agent_id` has an FK to `agents.id`).
- **Dependencies:** D1.2 (hard blocker — see Dependency and Handoff Points).
- **Definition of Done:** Migration applies cleanly on top of `0001_agents.py`; `UPDATE`/`DELETE` as the app DB role fails.
- **Tests/verification:** `test_audit_and_hash_chain.py::test_immutability_grants`.

#### D2.7 — Hash-chain integrity (`record_decision`)
- **Objective:** Implement `record_decision(event: DecisionEvent) -> AuditWriteResult` per the interface D1 defines in D1.3 — canonicalize, hash, persist, return the id/hash for D1's response.
- **Implementation requirements:** `SHA256(canonical_json(row) + prev_hash_of_last_row)`; canonicalization = sort keys alphabetically, strip whitespace, **before** hashing (§5.4 explicit gotcha).
- **PRD requirement:** §5.4 lightweight hash chain.
- **Files:** `backend/app/services/hash_chain.py`.
- **Dependencies:** D2.6; contract-only dependency on D1's `DecisionEvent` shape (frozen Day 1 — D2 can implement and unit-test against the agreed shape without D1's orchestration being finished).
- **Definition of Done:** Writing N sequential decisions produces a valid chain; function returns `(audit_log_id, hash)` in the exact shape D1's `ActionDecision.audit_log_id` expects.
- **Tests/verification:** `test_audit_and_hash_chain.py::test_chain_construction`.

#### D2.8 — Chain verification / tamper detection
- **Objective:** Implement `verify_chain()` — recompute the chain top-to-bottom and detect the exact row where a break occurs.
- **Implementation requirements:** Walk rows in order, recompute each hash, compare to stored `hash`; on mismatch, report the first offending row.
- **PRD requirement:** §5.4 tamper-check function, §9 audit integrity metric.
- **Files:** `backend/app/services/hash_chain.py`, `backend/app/routers/audit.py` (`POST /audit/verify-chain`).
- **Dependencies:** D2.7.
- **Definition of Done:** Verifying an untampered chain returns `{"intact": true}`; manually altering one row via raw SQL and re-verifying returns `{"intact": false, "broken_at_row": <row>}` — this is the §9 adversarial test.
- **Tests/verification:** `test_tamper_detection.py::test_adversarial_row_alteration`.

#### D2.9 — Audit/runtime read APIs
- **Objective:** Build the read-side endpoints: `/audit/feed`, `/audit/log`, `/agents/{id}/runtime-status`.
- **Implementation requirements:** `/audit/feed` returns most-recent-N decisions ordered by timestamp desc, cheap enough to poll every 1–2s; `/audit/log` supports `agent_id`, `action_type`, `decision`, `from`/`to` query params; `/agents/{id}/runtime-status` is a thin wrapper around `check_runtime_status()` for direct dashboard/demo use.
- **PRD requirement:** §5.5 (live activity feed, audit log table with filtering).
- **Files:** `backend/app/routers/audit.py`, `backend/app/schemas/audit.py`.
- **Dependencies:** D2.6, D2.7, D2.2.
- **Definition of Done:** All three endpoints return correctly filtered/live results against seeded data.
- **Tests/verification:** `test_audit_and_hash_chain.py::test_feed_and_filtering`.

#### D2.10 — React dashboard shell + API client/types
- **Objective:** Scaffold the frontend app and the single shared API client used by all dashboard features, including calls into D1's policy API.
- **Implementation requirements:** `frontend/src/api/client.ts` (fetch wrapper for every backend call — D1's `/agents`, `/agents/{id}/policy` included, since the dashboard is a client of both developers' APIs) and `frontend/src/api/types.ts` mirroring both developers' Pydantic schemas. `frontend/src/pages/Dashboard.tsx` as the shell page. The frontend must never implement enforcement rules itself — every control (revoke, kill switch, policy edit) is a thin call to the corresponding backend API.
- **PRD requirement:** §5.5 Operator Dashboard, §7 (React choice).
- **Files:** `frontend/src/api/client.ts`, `frontend/src/api/types.ts`, `frontend/src/pages/Dashboard.tsx`.
- **Dependencies:** Mockable dependency on D1's and D2's endpoint shapes (frozen in Shared Contracts) — D2 builds against mocks matching the documented shapes immediately, no need to wait for either backend to be finished.
- **Definition of Done:** Dashboard shell loads and successfully calls mocked, then live, `/agents` and `/audit/feed` endpoints.
- **Tests/verification:** Manual browser check.

#### D2.11 — Dashboard controls & views
- **Objective:** Build the remaining dashboard components: live activity feed, revoke/restore controls, fleet kill-switch/resume controls, policy config panel (UI only), audit log table + filters, and the Verify Chain Integrity button.
- **Implementation requirements:** Per component:
  - `ActivityFeed.tsx` — polls `/audit/feed` every 1–2s, color-coded allow/deny (D2 API).
  - `RevokeRestoreControls.tsx` — single-click + confirmation modal, calls `/agents/{id}/revoke` / `/restore` (D2 API).
  - `FleetKillSwitch.tsx` — single-click + confirmation modal, calls `/fleet/halt` / `/resume` (D2 API).
  - `PolicyConfigPanel.tsx` — calls D1's `PUT /agents/{id}/policy`; can be minimal per §10 cut-list (lowest priority within D2's UI work) — if cut, document the JSON-file-edit-and-restart fallback in the README instead.
  - `AuditLogTable.tsx` — filters matching `/audit/log` query params.
  - `IntegrityCheckButton.tsx` — calls `/audit/verify-chain`, shows "✅ chain intact" or "❌ break detected at row N."
- **PRD requirement:** §5.3, §5.4, §5.5 (all dashboard controls); §6 demo beats 3 and 5; §10 cut-list item 1 (policy panel) and item 2 (integrity button — backend endpoint D2.8 is not cuttable, only the button UI is).
- **Files:** `frontend/src/components/ActivityFeed.tsx`, `RevokeRestoreControls.tsx`, `FleetKillSwitch.tsx`, `PolicyConfigPanel.tsx`, `AuditLogTable.tsx`, `IntegrityCheckButton.tsx`.
- **Dependencies:** D2.10; mockable dependency on D1's policy endpoint (D2 can build `PolicyConfigPanel.tsx` against a mock before D1.7 lands) and D2's own runtime/fleet/audit endpoints (available as soon as D2.3/D2.4/D2.9 land, since same-developer sequencing).
- **Definition of Done:** Revoking Agent B causes its next request to be denied while A/C continue unaffected, visible live in the activity feed; kill switch halts all agents; integrity button correctly reports intact/broken states against a manually tampered row.
- **Tests/verification:** Manual run-through of demo beats 3, 5, 6; propagation timing cross-checked against D2.14's measured numbers.

#### D2.12 — Scripted demo agents + six-beat orchestration
- **Objective:** Build Agent A (compliant), Agent B (violator), Agent C (runaway), and a runner script executing the full six-beat scenario end-to-end.
- **Implementation requirements:** Each agent is a scripted HTTP client hitting `/action-request` with identity headers. Agent A issues in-policy refunds; Agent B attempts an out-of-scope action and an over-cap refund; Agent C rapid-fires legitimate-looking actions with slightly randomized intervals (§12 risk mitigation). The runner sequences: A runs → B violates → operator revokes B → C runs → operator hits kill switch → filter audit log + verify chain.
- **PRD requirement:** §6 Demo Scenario (all six beats), §12 (randomized intervals).
- **Files:** `backend/app/demo/agents/agent_a.py`, `agent_b.py`, `agent_c.py`, `runner.py`.
- **Dependencies:** Full backend (D1's orchestration + D2's runtime/audit) — this is the one D2 task that genuinely needs both subsystems substantially complete; everything else in D2's list is independently developable.
- **Definition of Done:** Running the script completes all six beats in under ~110 seconds without manual intervention (dashboard clicks can be simulated via direct API calls for the automated version; a separate manual/dashboard-driven walkthrough is used for the actual recorded demo).
- **Tests/verification:** `test_demo_scenario_e2e.py` (joint test, finalized once both subsystems are integrated).

#### D2.13 — Runtime-safety/audit test suite
- **Objective:** Consolidate D2's automated test coverage: identity failure, per-agent revocation, restore, fleet halt, fleet resume, fail-closed runtime behavior, audit completeness, hash-chain construction, tamper detection.
- **Implementation requirements:** Completeness check: run the demo scenario (or a fixed request suite) and assert audit-log row count equals requests sent (§9 audit completeness).
- **PRD requirement:** §9 Audit completeness, Audit integrity.
- **Files:** `backend/tests/test_identity.py`, `test_runtime_safety.py`, `test_audit_and_hash_chain.py`, `test_tamper_detection.py`.
- **Dependencies:** D2.1–D2.9.
- **Definition of Done:** All tests passing; completeness and integrity results captured as concrete numbers for the writeup.
- **Tests/verification:** CI/local test run output.

#### D2.14 — Revocation/kill-switch propagation metrics
- **Objective:** Produce the §9 measurements for per-agent revocation propagation time and fleet-wide kill-switch propagation time.
- **Implementation requirements:** Measure time between a control-API call (`/agents/{id}/revoke` or `/fleet/halt`) completing and the next `/action-request` from an affected agent being denied.
- **PRD requirement:** §9 Kill switch propagation time, per-agent revocation propagation time.
- **Files:** `backend/tests/test_runtime_safety.py` (or a dedicated `backend/tests/test_propagation.py`).
- **Dependencies:** D2.3, D2.4, D1.3 (needs the orchestration pipeline live to observe the deny).
- **Definition of Done:** Concrete propagation-time numbers for both revocation and kill-switch, pastable into the submission writeup.
- **Tests/verification:** Automated test output.

---

## File Ownership Map

| Path / Module | Owner | Notes |
|---|---|---|
| `docker-compose.yml` | D1 | Infra-scaffold ownership only; not a claim on backend logic |
| `.env.example` | D1 | Single owner; new variables documented centrally |
| `backend/app/main.py` | D1 | D2 hands off completed router objects (`runtime.py`, `fleet.py`, `audit.py`); D1 performs the `include_router` calls |
| `backend/app/config.py`, `db/session.py` | D1 | — |
| `backend/app/db/models/agent.py` | D1 | Contract frozen with D2 input on `shared_secret` field (Day-1 handoff, not joint editing) |
| `backend/app/db/models/audit_log.py` | D2 | FK to `agents.id`, depends on D1.2 landing first |
| `backend/app/schemas/action.py` | D1 | Includes `DecisionEvent` interface type D2 implements against |
| `backend/app/schemas/agent.py` | D1 | Contract frozen with D2 input |
| `backend/app/schemas/audit.py` | D2 | Includes `RuntimeStatus`, `FleetState`, `AuditLogEntry` |
| `backend/app/policy/*` | D1 | — |
| `backend/app/services/spend.py` | D1 | Owns `agent:{id}:remaining_budget` Redis key |
| `backend/app/services/identity.py` | D2 | — |
| `backend/app/services/runtime_state.py` | D2 | Owns `agent:{id}:status`, `fleet:halted` Redis keys |
| `backend/app/services/hash_chain.py` | D2 | Implements the `record_decision` interface D1 calls; D1 never edits this file |
| `backend/app/routers/action.py` | D1 | Orchestration only — calls D2's functions, never re-implements them |
| `backend/app/routers/policies.py` | D1 | Policy config + spend reset/config |
| `backend/app/routers/runtime.py` | D2 | Revoke/restore |
| `backend/app/routers/fleet.py` | D2 | Halt/resume |
| `backend/app/routers/audit.py` | D2 | Feed, log query, verify-chain |
| `backend/app/demo/agents/*` | D2 | — |
| `backend/alembic/versions/0001_agents.py` | D1 | Must merge/land before `0002` |
| `backend/alembic/versions/0002_audit_log.py` | D2 | Numbered after `0001`; hard dependency on it |
| `frontend/**` | D2 | Entire tree; components are clients of both developers' APIs but implement no enforcement logic |
| `backend/tests/test_policy_enforcement.py`, `test_spend_cap.py`, `test_policy_latency.py` | D1 | — |
| `backend/tests/test_identity.py`, `test_runtime_safety.py`, `test_audit_and_hash_chain.py`, `test_tamper_detection.py` | D2 | — |
| `backend/tests/test_demo_scenario_e2e.py` | Joint | Finalized during integration |
| `README.md` | Joint | Each developer edits only their own section |

---

## Merge-Safety Rules

1. Every shared file above has exactly one owner. The non-owner never edits that file directly.
2. If the non-owner needs a change in an owned file, they expose it as a module/function/router object and ask the owner to wire it in (e.g., D2 hands D1 a completed `runtime.py` router object for `main.py` registration).
3. **Migrations are strictly ordered, single-owner per file:** `0001_agents.py` (D1) before `0002_audit_log.py` (D2), due to the FK dependency. Neither developer edits the other's merged migration — a schema change becomes a new migration.
4. **Redis keys are owned by domain, not by developer convenience:** `agent:{id}:remaining_budget` is D1-only; `agent:{id}:status` and `fleet:halted` are D2-only. Neither developer's code reads or writes the other's keys directly — they call the owning developer's function instead.
5. Environment variables are proposed in PR descriptions and added to `.env.example` by D1 only.
6. Shared Pydantic contracts (`schemas/action.py`, `schemas/agent.py` owned by D1; `schemas/audit.py` owned by D2) are frozen per Shared Contracts on Day 1. Post-freeze changes require a message to the other developer before committing.
7. **The three cross-developer function interfaces — `verify_identity()`, `check_runtime_status()`, `record_decision()` — are the hard coupling points.** D1 calls them; D2 implements them. `evaluate_policy()` and `reserve_budget_atomic()` are the reverse: D1 implements, and in this plan D2 does not call them directly (D2's subsystems are independent of policy/spend logic). Neither developer edits the other's implementation of these functions.
8. `agents` table field additions after Day 1 go through the Shared Agent Fields handoff process (D2 requests, D1 implements), never a direct D2 edit to `agent.py`.
9. Avoid unrelated formatting/refactoring while implementing assigned tasks, especially in `main.py`.
10. Keep commits scoped to the assigned subsystem.
11. No duplicate implementations: the dashboard fetches `AgentStatus`/`RuntimeStatus` from backend endpoints rather than re-deriving state client-side; D1's orchestration never re-implements identity/runtime-safety checks locally "for convenience."
12. Rebase (don't merge-commit) onto the latest shared-contract-bearing commits before opening a final PR.

**Specific high-conflict files and designated owners:** `docker-compose.yml` → D1; `.env.example` → D1; `backend/app/main.py` → D1 (D2 contributes via exposed router objects only); `backend/app/schemas/action.py` & `agent.py` → D1; `backend/app/schemas/audit.py` → D2; `backend/app/services/hash_chain.py`, `identity.py`, `runtime_state.py` → D2 (D1 only calls them); `backend/app/services/spend.py` → D1 (D2 has no reason to call or edit it).

---

## Dependency and Handoff Points

| # | Producer | Consumer | Interface | Data shape | Dependency type |
|---|---|---|---|---|---|
| 1 | D1 (D1.2) | D2 (D2.1) | `agents` table with `shared_secret` field | Column exists per D2's Day-1 spec | **Contract-only** — D2 specifies the field shape Day 1; D1 implements it as part of D1.2. D2 can develop/unit-test `verify_identity()` against a mocked agent-lookup before D1.2 merges. |
| 2 | D1 (D1.2) | D2 (D2.6) | `agents.id` as FK target for `audit_log` | Existence of `agents` table with `id` PK | **Hard blocker** — D2.6's migration cannot be written/applied until D1.2's migration exists. Sequence accordingly (Day 1/2). |
| 3 | D1 (D1.3, interface only) | D2 (D2.7) | `record_decision(event: DecisionEvent) -> AuditWriteResult` signature | `DecisionEvent{agent_id, action_type, amount, decision, reason, reason_code, policy_version, timestamp}` → `{audit_log_id, hash}` | **Contract-only** — signature frozen Day 1; D2 implements against it immediately, D1 uses a local stub until D2's real function lands. |
| 4 | D2 (D2.1, interface only) | D1 (D1.3) | `verify_identity(agent_id, secret) -> IdentityResult` signature | `{valid: bool, agent_id: str|null}` | **Contract-only / mockable** — D1 develops the orchestration against a stub returning fixed `IdentityResult` values before D2's real implementation lands. |
| 5 | D2 (D2.2, interface only) | D1 (D1.3, D1.7) | `check_runtime_status(agent_id) -> RuntimeStatus` signature | `{fleet_halted, agent_revoked, available}` | **Contract-only / mockable** — same pattern; D1 stubs this until D2.2 is ready. |
| 6 | D1 (D1.7) | D2 (D2.10, D2.11) | `GET /agents`, `GET /agents/{id}`, `PUT /agents/{id}/policy` | Per Shared Contracts | **Mockable** — D2 builds `PolicyConfigPanel.tsx` and the shell against mocked JSON matching the documented shapes, swaps in real calls once D1.7 is live. |
| 7 | D2 (D2.3, D2.4, D2.9) | D2 (D2.11) | `/agents/{id}/revoke`, `/restore`, `/fleet/halt`, `/resume`, `/audit/feed`, `/audit/log`, `/audit/verify-chain` | Per Shared Contracts | **Same-developer sequencing** — not cross-developer, purely internal ordering within D2's own tasks. |
| 8 | D1 (whole orchestration) + D2 (whole runtime/audit) | D2 (D2.12 runner script) | Full running system | N/A | **Integration-time** — this is the one task in the whole plan that genuinely needs both subsystems substantially complete; the individual agent scripts (A/B/C) can be written and unit-tested against a stubbed gateway earlier. |
| 9 | D2 (D2.2) | D1 (via D1.3's interpretation of `available: false`) | Fail-closed signal | `RuntimeStatus.available: bool` | **Contract-only** — D1 only needs to know the field exists and its meaning; implementation timing doesn't block D1.3. |

**Both developers have independently schedulable work from Day 1:** D1 starts on infra scaffolding, the agent/policy model, and the orchestration skeleton against D2's stubbed interfaces. D2 starts on `verify_identity()`/`check_runtime_status()` against mocked agent lookups and a local Redis instance, and on the frontend shell against mocked API responses — none of this requires waiting on D1's implementation, only on the Day-1 frozen contracts.

---

## Parallel Development Timeline

| Day | Developer 1 | Developer 2 | Handoff needed before Day starts |
|---|---|---|---|
| **1** | D1.1 (scaffolding), D1.2 (agent/policy model — confirms `shared_secret` shape with D2 first) | Confirms `shared_secret` field spec with D1; starts D2.1 (`verify_identity`) against a mocked agent lookup; starts frontend shell scaffolding (`frontend/` skeleton) — no code dependency needed | D1.1 must land before either developer can run anything locally; the `shared_secret` field conversation happens before D1.2 is finalized |
| **2** | D1.3 (orchestration skeleton, against D2's stubbed interfaces), D1.4 (OPA integration) | D2.2 (runtime safety Redis layer, independent of D1's app code), D2.6 (audit_log migration — needs D1.2 merged) | D1.2 migration merged (blocks D2.6 only) |
| **3** | D1.5 (Python fallback), D1.6 (spend caps + atomic budget) | D2.3 (revoke/restore), D2.4 (kill switch/resume), D2.7 (hash chain `record_decision`, against the Day-1-frozen `DecisionEvent` shape) | `DecisionEvent` and `RuntimeStatus`/`IdentityResult` signatures agreed (Day 1 planning, not a coding blocker) |
| **4** | D1.7 (policy/spend config APIs) | D2.8 (chain verification), D2.9 (audit/runtime read APIs), D2.10 (dashboard shell — against mocks now that shapes are stable) | D1.3's stub-based orchestration stable enough for D2 to mock against |
| **5** | D1.8 (test suite), D1.9 (latency metrics) | D2.11 (all dashboard controls — revoke/restore, kill switch, policy panel, audit table, integrity button), D2.12 begins (demo agent scripts, unit-testable against stubs) | D1.7's policy endpoints live for D2 to point real `client.ts` calls at (D2.11's policy panel) |
| **6** | Swap D1's stubs for D2's real `verify_identity`/`check_runtime_status`/`record_decision`; support integration | D2.12 (runner script finished against the real integrated backend), D2.13 (full test suite), D2.14 (propagation metrics), integration support | Both subsystems feature-complete; this is the merge/integration day |
| **7 (Buffer)** | Fix anything broken by the Day 6 merge; no new feature work | Re-run/re-record demo if timing looked off; finish writeup | — |

---

## Mock/Stub Strategy

To keep both developers unblocked from Day 1, every cross-developer interface is developed against a stub/mock until the real implementation is ready:

- **D1's orchestration (`routers/action.py`)** is built from Day 2 against stub versions of `verify_identity()` (always returns valid), `check_runtime_status()` (always returns not-halted/not-revoked/available), and `record_decision()` (returns a fixed fake id/hash). These stubs live in D1's own test/dev fixtures, not in D2's files, and are swapped for real calls at integration with no change to the orchestration's control flow.
- **D2's `verify_identity()` and `check_runtime_status()`** are unit-tested from Day 1 against a mocked agent-lookup function and a local Redis instance respectively — neither needs D1's FastAPI app running.
- **D2's `record_decision()`** is unit-tested against the frozen `DecisionEvent` shape directly, without needing D1's orchestration to call it.
- **D2's frontend** is built from Day 1 against hand-written mock JSON matching every documented response shape in Shared Contracts, for both D1's and D2's endpoints, and switched to live calls incrementally as each backend endpoint comes online.
- **Integration-time-only work:** the full six-beat runner script (D2.12) and the fail-closed end-to-end test (D2.5) are the only pieces of work that require both subsystems substantially complete — everything else is contract-only or mockable.

---

## Testing Ownership

**Developer 1 primarily tests:**
- Permission enforcement (OPA and fallback)
- OPA/fallback consistency (parity test)
- Max-single-amount enforcement
- Dynamic spend caps
- Atomic concurrent spend requests
- Policy updates affecting future decisions
- Policy/spend gateway latency

**Developer 2 primarily tests:**
- Identity failure (missing/wrong/correct secret)
- Per-agent revocation
- Restore
- Fleet halt
- Fleet resume
- Fail-closed runtime-safety behavior (Redis outage on the `status`/`fleet:halted` keys)
- Audit completeness
- Hash-chain construction
- Tamper detection (adversarial row alteration)
- Revocation propagation timing
- Kill-switch propagation timing

**Joint:** the final six-beat end-to-end demo scenario test (`test_demo_scenario_e2e.py`) remains a shared integration responsibility even though D2 owns the runner/demo-agent implementation, since it exercises both subsystems together.

---

## Demo Ownership

D2 continues to own the scripted demo agents and orchestration, since it naturally connects to the dashboard/operator-control work D2 already owns. The demo explicitly exercises both developers' subsystems:

| Beat | Behavior | Subsystem(s) exercised |
|---|---|---|
| **1. Agent A — Compliant** | In-policy refunds within cap | D1 policy/spend enforcement (allows) → D2 audit/dashboard (displays) |
| **2. Agent B — Violator** | Out-of-scope action + over-cap refund | D1 (permission + spend-cap denial) |
| **3. Operator revokes Agent B** | Single-agent revoke | D2 runtime safety (revocation) |
| **4. Agent C — Runaway** | Rapid-fire legitimate-looking actions | Both — D1 evaluates each request, D2's runtime/audit layer observes and processes the traffic |
| **5. Operator hits fleet kill switch** | Single click | D2 runtime safety (fleet halt) |
| **6. Audit log + integrity check** | Filter log, verify chain | D2 (audit + hash chain) |

This distribution is worth stating explicitly in the submission writeup/presentation: it demonstrates that the demo's most "impressive" beats (revocation, kill switch, integrity check) showcase D2's runtime-safety/audit work, while the underlying denial-and-baseline beats (1, 2) showcase D1's policy/financial-governance work — both developers' contributions are visible in every run of the scenario, not siloed to a "backend" and "demo" half.

---

## Final Integration Sequence

1. **Shared contracts/schema foundations** — confirm `schemas/action.py`, `schemas/agent.py`, `schemas/audit.py`, and the `verify_identity`/`check_runtime_status`/`record_decision` interfaces match what was actually built.
2. **Independent subsystem implementation** — D1's orchestration (with stubbed D2 interfaces) and D2's identity/runtime/audit services are each fully tested in isolation.
3. **API/backend integration** — merge D2's `0002_audit_log.py` migration on top of D1's `0001_agents.py`; wire D2's `runtime.py`/`fleet.py`/`audit.py` routers into D1's `main.py`; swap D1's stubs for D2's real `verify_identity`, `check_runtime_status`, `record_decision`.
   - **D1 merges first**, since D2's migration and router-wiring both depend on D1's schema/app structure being the merge base.
4. **Dashboard integration** — point `frontend/src/api/client.ts` at the live backend (no more mocks); verify all components against real data.
5. **Scripted-agent integration** — run Agent A/B/C individually against the fully integrated backend.
6. **Full six-beat demo scenario** — run `runner.py` end-to-end; verify all six beats within the ~90–110s target.
7. **Metrics and validation** — capture all §9 metrics together: enforcement accuracy, gateway/policy latency (D1), audit completeness, audit integrity/tamper detection, revocation propagation, kill-switch propagation (D2).
8. **Deployment verification** — deploy the integrated system to the public URL; re-run the six-beat scenario once against the deployed instance before recording.

### Pre-Merge Checklists

**Developer 1, before merging:**
- [ ] `test_policy_enforcement.py`, `test_spend_cap.py`, `test_policy_latency.py` all passing
- [ ] No changes outside owned files (see File Ownership Map)
- [ ] `ActionRequest`/`ActionDecision`/`AgentStatus` schemas match Shared Contracts (or section updated and D2 notified)
- [ ] `agents` table includes the D2-specified `shared_secret` field exactly as agreed
- [ ] Alembic migration `0001_agents.py` verified to apply cleanly from empty DB
- [ ] New environment variables added to `.env.example` with comments
- [ ] Orchestration calls `verify_identity`/`check_runtime_status`/`record_decision` with the exact agreed signatures (even if still using stubs)
- [ ] Branch rebased onto latest `main`

**Developer 2, before merging:**
- [ ] `test_identity.py`, `test_runtime_safety.py`, `test_audit_and_hash_chain.py`, `test_tamper_detection.py` all passing
- [ ] No changes outside owned files (see File Ownership Map)
- [ ] `RuntimeStatus`/`AuditLogEntry`/`FleetState` schemas match Shared Contracts
- [ ] Alembic migration `0002_audit_log.py` verified to apply cleanly on top of `0001_agents.py`
- [ ] `verify_identity`, `check_runtime_status`, `record_decision` implementations match the interfaces D1's code calls, verified against real (non-mocked) calls
- [ ] Dashboard builds and runs against the real backend, not just mocks
- [ ] Branch rebased onto latest `main` (including D1's merged changes)

---

## PRD Coverage Matrix

| PRD Requirement | Developer | Task # | Integration Dependency | Verification Method |
|---|---|---|---|---|
| Lightweight agent identity (agent_id + shared secret) | D2 | D2.1 | Contract-only on D1's `shared_secret` field (D1.2) | `test_identity.py::test_identity_rejection` |
| Gateway `/action-request` orchestration | D1 | D1.3 | Contract-only on D2's function signatures | `test_policy_enforcement.py::test_check_order` |
| Correct enforcement/check order | D1 (orchestration) + D2 (identity/runtime functions it calls) | D1.3, D2.1, D2.2 | Mutual — signatures frozen Day 1 | `test_policy_enforcement.py::test_check_order` |
| Granular permission enforcement | D1 | D1.4, D1.5 | None | `test_policy_enforcement.py::test_opa_permission_and_limit` |
| Max single-transaction limit | D1 | D1.4, D1.5 | None | `test_policy_enforcement.py` |
| Dynamic daily spend caps | D1 | D1.6 | None | `test_spend_cap.py` |
| Atomic spend enforcement | D1 | D1.6 | None | `test_spend_cap.py::test_atomic_concurrent_requests` |
| Per-agent revocation | D2 | D2.3 | Integration-time with D1.3 for the deny-on-next-request check | `test_runtime_safety.py::test_revoke_and_restore`; demo beat 3 |
| Fleet-wide kill switch | D2 | D2.4 | Integration-time with D1.3 | `test_runtime_safety.py::test_fleet_halt_and_resume`; demo beat 5 |
| Fail-closed behavior | D1 (spend-state keys) + D2 (runtime-safety keys) | D1.6, D2.2, D2.5 | Integration-time end-to-end test | `test_spend_cap.py::test_spend_state_fail_closed`, `test_runtime_safety.py::test_end_to_end_fail_closed` |
| Postgres audit logging | D2 | D2.6, D2.7 | Hard blocker: D1.2's `agents` table | `test_audit_and_hash_chain.py` |
| SHA-256 hash-chain integrity | D2 | D2.7 | Contract-only on D1's `DecisionEvent` shape | `test_audit_and_hash_chain.py::test_chain_construction` |
| Chain-integrity verification / tamper detection | D2 | D2.8 | None | `test_tamper_detection.py::test_adversarial_row_alteration` |
| Operator dashboard | D2 | D2.10 | Mockable on both developers' endpoints | Manual + component checks |
| Live activity feed | D2 | D2.11 | D2.9 audit feed endpoint | Manual demo run |
| Policy configuration (display/editing) | D1 (API) + D2 (UI, client-only) | D1.7, D2.11 | Mockable — D2 builds UI against mocks first | Manual verification (lowest cut-list priority) |
| Audit-log UI/filtering | D2 | D2.9, D2.11 | None | Manual demo run |
| Verify Chain Integrity control | D2 | D2.8, D2.11 | None | Demo beat 6 |
| Three scripted demo agents | D2 | D2.12 | Integration-time — needs both subsystems | `test_demo_scenario_e2e.py` |
| Complete six-beat demo scenario | D2 (runner) + Joint (verification) | D2.12 | All D1 and D2 tasks | `test_demo_scenario_e2e.py`; recorded demo run |
| Enforcement accuracy measurement | D1 | D1.8 | None | Test suite output |
| Gateway latency measurement | D1 | D1.9 | None | Timing middleware output |
| Revocation propagation measurement | D2 | D2.14 | Needs D1.3's orchestration live | Test suite output |
| Kill-switch propagation measurement | D2 | D2.14 | Needs D1.3's orchestration live | Test suite output |
| Audit completeness testing | D2 | D2.13 | Full request/log pipeline | `test_audit_and_hash_chain.py` |
| Tamper-detection adversarial test | D2 | D2.8, D2.13 | None | `test_tamper_detection.py` |
| Deployment/demo readiness | Joint | Final Integration Sequence step 8 | All tasks | Deployed instance re-run |

---

## Final Consistency Check

1. **Every PRD requirement has a clear primary owner** — see PRD Coverage Matrix; the only jointly-attributed rows (check order, fail-closed, demo scenario, deployment) are joint by nature (they span both subsystems by definition), not because ownership is unclear.
2. **Both developers own meaningful backend/security functionality** — D1 owns the policy engine, spend-cap atomicity, and orchestration; D2 owns identity verification, revocation/kill-switch state machines, fail-closed runtime logic, and the cryptographic hash-chain/tamper-detection system. Neither is "just frontend" or "just plumbing."
3. **D1 owns Policy + Financial Governance** — confirmed throughout (D1.1–D1.9).
4. **D2 owns Runtime Safety + Audit + Operator Control** — confirmed throughout (D2.1–D2.14).
5. **`/action-request` has one orchestration owner (D1) but uses D2-owned interfaces** (`verify_identity`, `check_runtime_status`, `record_decision`) — confirmed in Critical Request Pipeline and D1.3.
6. **Redis keys have explicit domain ownership** — `remaining_budget` (D1) vs. `status`/`fleet:halted` (D2), documented in Redis Ownership with a no-cross-reads rule.
7. **No implementation responsibility is accidentally duplicated** — dashboard/demo agents call backend functions rather than reimplementing enforcement; D1 does not re-implement identity/runtime checks; D2 does not re-implement policy/spend logic.
8. **High-conflict files have one owner** — see File Ownership Map; `agents` model has a single file-owner (D1) with a documented Day-1 field-contract process for D2's identity-field input.
9. **Both developers can work substantially in parallel from Day 1** — see Parallel Development Timeline and Mock/Stub Strategy; only two true hard blockers exist (agents table before audit_log migration; agreed interface signatures before implementation, which is a same-day conversation, not a wait).
10. **Cross-developer interfaces are frozen early** — `verify_identity`, `check_runtime_status`, `record_decision`, `DecisionEvent`, `RuntimeStatus`, `IdentityResult` all specified in Shared Contracts before task work begins.
11. **Mock/stub strategies exist where one subsystem is unfinished** — see dedicated Mock/Stub Strategy section.
12. **Migration ordering remains safe** — `0001_agents.py` (D1) before `0002_audit_log.py` (D2), explicit FK dependency documented in three places (Architecture Assessment, D2.6, Dependency and Handoff Points).
13. **The six-beat demo still demonstrates every mandatory capability** — see Demo Ownership table; all five required capabilities (permissions, spend caps, per-agent revocation, fleet kill switch, audit log) plus the two credibility adds (fail-closed, tamper-check) are exercised.
14. **The final branches can merge with minimal manual conflict resolution** — disjoint file ownership preserved throughout despite the rebalancing; the only file touched by both developers' *concerns* (`agents` table) has a single file-owner and a documented contract-handoff process rather than joint edits.
15. **No Phase 1 PRD requirement has been lost during rebalancing** — cross-checked against PRD §5–§11 in the PRD Coverage Matrix; no Phase 2 scope (Go, Cedar, JWT/OAuth2.1, Prometheus/Grafana, KMS/anchoring, HITL) has been introduced.
