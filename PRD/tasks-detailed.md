# Phase 1 Implementation Plan (Single Developer)

**Project:** Governance Layer for Financial Agents (Amex CodeStop 2026, Phase 1 Hybrid v2)
**Status:** D1/D2 integration checkpoint complete (2026-07-23). One developer (D2) now owns all remaining implementation.
**Last Updated:** 2026-07-24

---

## What Changed

**Previous two-developer split is dissolved.** All remaining work is now owned by a single developer (D2).

**Complete work:**
- D1.1: Infrastructure (docker-compose, FastAPI, Postgres, Redis, OPA)
- D1.2: Agent + policy data model with shared_secret
- D1.AgentLookup: Database lookup implementation
- D1.RedisClient: Redis client adapter
- D2.1: Identity verification (INTEGRATED)
- D2.2: Runtime safety state (INTEGRATED)
- D2.FE: Frontend dashboard Phase 1 (mock-based)

**Remaining work:** 19 tasks across 5 phases (see below)

---

## Conceptual Domains (Still Useful for Understanding)

**Policy & Financial Governance:** "What is this agent allowed to do and spend?"
**Runtime Safety, Audit & Operator Control:** "Is this agent operational, can we stop it, and can we prove what happened?"

These conceptual domains help understand the architecture, but no longer represent developer ownership boundaries.

---

## Current Architecture Assessment (2026-07-24)

**Infrastructure exists:**
- docker-compose.yml (Postgres + Redis + OPA)
- .env.example with DATABASE_URL and REDIS_URL
- main.py with bootstrap wiring
- alembic configured with agents migration (09ee32e4e00a)

**Models exist:**
- db/models/agent.py (id, name, permissions, max_single_amount, daily_cap, status, shared_secret)
- db/base.py (SQLAlchemy setup)

**Services exist (D2.1, D2.2 integrated):**
- services/identity.py (verify_identity ✅)
- services/runtime_state.py (check_runtime_status ✅)
- services/redis_client.py (ProductionRedisClient ✅)
- scripts/agent_lookup.py (D1AgentLookup ✅)

**Frontend exists (mock-based):**
- frontend/src/** (complete React dashboard with mocks)

**Tests exist (89 passing):**
- tests/test_identity.py (24 tests)
- tests/test_runtime_safety.py (46 tests)
- tests/test_integration_identity.py (7 tests)
- tests/test_integration_redis.py (9 tests)
- tests/test_startup_wiring.py (3 tests)

**Missing:**
- routers/ directory (no FastAPI routers yet)
- schemas/ directory (no Pydantic schemas yet)
- policy/ directory (no OPA/Rego or fallback)
- services/spend.py (no spend caps)
- services/hash_chain.py (no audit/integrity)
- db/models/audit_log.py (no audit table)
- demo/ directory (no scripted agents)
- middleware/ directory (no latency tracking)
- audit_log migration (depends on agents migration ✅)

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

## File Ownership (Updated for Single Developer)

**All remaining implementation is now owned by D2.** The previous D1/D2 split no longer applies for coordination purposes.

**Previously D1-owned, now D2-owned:**
- `routers/action.py` — orchestration endpoint
- `routers/policies.py` — policy/spend config APIs
- `schemas/action.py` — ActionRequest/ActionDecision/DecisionEvent
- `schemas/agent.py` — Agent, AgentStatus schemas
- `policy/opa_client.py` — OPA integration
- `policy/fallback.py` — Python fallback
- `services/spend.py` — spend caps
- `middleware/timing.py` — latency measurement
- `tests/test_policy_enforcement.py` — policy tests
- `tests/test_spend_cap.py` — spend cap tests
- `tests/test_policy_latency.py` — latency tests

**Already D2-owned and complete:**
- `services/identity.py` — verify_identity ✅
- `services/runtime_state.py` — check_runtime_status ✅
- `services/redis_client.py` — ProductionRedisClient ✅
- `frontend/**` — React dashboard ✅ (mock-based)

**D2-owned, to be implemented:**
- `services/hash_chain.py` — record_decision, verify_chain
- `db/models/audit_log.py` — audit table model
- `routers/runtime.py` — revoke/restore endpoints
- `routers/fleet.py` — halt/resume endpoints
- `routers/audit.py` — audit APIs
- `schemas/audit.py` — D2-owned schemas
- `demo/agents/*` — scripted demo agents
- `tests/test_audit_and_hash_chain.py` — audit tests
- `tests/test_tamper_detection.py` — integrity tests
- `tests/test_propagation.py` — metrics tests
- `alembic/versions/0002_audit_log.py` — audit migration

**Shared infrastructure (maintained by D2):**
- `docker-compose.yml`, `.env.example` — environment
- `main.py` — application bootstrap
- `db/models/agent.py` — agent model (already exists)
- `scripts/agent_lookup.py` — AgentLookup (already exists)

---

## Implementation Tasks (Single Developer Order)

**Phase 1: Core Services**

### Milestone A: Audit Foundation (Sequential)

### Task 2.1 — Audit Log Model + Migration

**Milestone A: Audit Foundation (Sequential: 2.1 → 2.2 → 2.3)**

#### D1.1 — Infrastructure & repo scaffolding — ✅ COMPLETE
- **Status:** Done (docker-compose.yml, .env.example, main.py, alembic.ini)
- **Migration:** agents migration (09ee32e4e00a) applied

#### D1.2 — Agent + policy data model & migration — ✅ COMPLETE
- **Status:** Done (db/models/agent.py with shared_secret field)
- **Migration:** 09ee32e4e00a_create_agents_table.py applied

#### D1.3 — Main action-request orchestration/gateway — TO DO (Task 4.1 below)
- **Will be implemented after policy/spend/audit services are complete**

#### D1.4 — OPA/Rego policy integration — TO DO (Task 2.5 below)

#### D1.5 — Plain-Python policy fallback — TO DO (Task 2.6 below)

**Policy stream (sequential: 2.5 → 2.6):**
- See tasks.md for detailed requirements

#### D1.6 — Dynamic spend caps + atomic budget reservation — TO DO (Task 2.4 below)

**Milestone C: Policy + Spend (Independent workstreams)**

**Spend stream (independent):**

#### D1.7 — Policy configuration API + spend reset/config API — TO DO (Task 3.6-3.7 below)

#### D1.8 — Policy & spend enforcement test suite — TO DO (Task 6.2 below)

#### D1.9 — Gateway/policy/spend latency metrics — TO DO (Task 6.3 below)

**Milestone D: Full /action-request Orchestration**
- Task 4.1 (D1.3): /action-request endpoint
- Requires: Milestones A + C complete, D2.1✅, D2.2✅
- Pipeline: Identity → Fleet halted → Agent revoked → Permission/max-amount → Spend cap → ALLOW/DENY → Audit recording

**Milestone E: Remaining APIs**
- Tasks 3.3-3.7: Audit APIs, policy APIs, spend reset, agent/status APIs
- Requires: Milestones A + B + C

**Milestone F: Frontend Real-Backend Integration**
- Tasks 5.1-5.2: Real API client, verification
- Requires: Milestone E complete

**Milestone G: Demo + E2E + Metrics**
- Task 6.1: Demo agents + runner
- Task 6.2: Complete test suite + regression
- Task 6.3: Metrics collection
- Requires: Full system (Milestones D + E + F)

---

## [ARCHIVED] Historical D1/D2 Split

The following sections are preserved for historical attribution only. They do NOT govern current implementation.

---

## [ARCHIVED] Historical Developer 2 — Runtime Safety, Audit & Operator Control

**The following section is preserved for historical attribution only. Current implementation follows the single-developer model documented above.**

---

**Owns the question:** *"Is this agent operational, can we stop it instantly, and can we prove what happened?"*

### Ownership

- **Owns and creates:** `backend/app/services/identity.py`, `backend/app/services/runtime_state.py`, `backend/app/services/hash_chain.py`, `backend/app/db/models/audit_log.py`, `backend/app/schemas/audit.py`, `backend/app/routers/runtime.py`, `backend/app/routers/fleet.py`, `backend/app/routers/audit.py`, `backend/app/demo/agents/*`, `backend/tests/test_identity.py`, `backend/tests/test_runtime_safety.py`, `backend/tests/test_audit_and_hash_chain.py`, `backend/tests/test_tamper_detection.py`, `backend/alembic/versions/0002_audit_log.py`, all of `frontend/`.
- **May modify (with care):** `README.md` (own section only).
- **Must avoid editing:** `backend/app/main.py`, `backend/app/config.py`, `backend/app/db/session.py`, `backend/app/db/models/agent.py`, `backend/app/schemas/action.py`, `backend/app/schemas/agent.py`, `backend/app/policy/*`, `backend/app/services/spend.py`, `backend/app/routers/action.py`, `backend/app/routers/policies.py`, `docker-compose.yml`, `.env.example`, `backend/alembic/versions/0001_agents.py`, the `agent:{id}:remaining_budget` Redis key.

### Tasks

#### D2.1 — Identity contract + implementation — ✅ COMPLETE (INTEGRATED)
- **Status:** Done (services/identity.py)
- **Integration:** Wired with D1AgentLookup in main.py
- **Tests:** 24 passing

#### D2.2 — Runtime safety Redis layer — ✅ COMPLETE (INTEGRATED)
- **Status:** Done (services/runtime_state.py)
- **Integration:** Wired with ProductionRedisClient in main.py
- **Tests:** 46 passing

#### D2.3 — Per-agent revocation/restore — TO DO (Task 3.1 below)

#### D2.4 — Fleet kill switch/resume — TO DO (Task 3.2 below)

**Milestone B: Runtime Control APIs (Uses audit foundation from A)**

#### D2.5 — Fail-closed runtime behavior (consolidation) — ✅ COMPLETE
- **Status:** Verified in integration tests

#### D2.6 — Audit model + persistence — TO DO (Task 2.1 below)

#### D2.7 — Hash-chain integrity (`record_decision`) — TO DO (Task 2.2 below)

#### D2.8 — Chain verification / tamper detection — TO DO (Task 2.3 below)

#### D2.9 — Audit/runtime read APIs — TO DO (Tasks 3.3-3.5 below)

#### D2.10 — React dashboard shell + API client/types — ✅ COMPLETE (MOCK-BASED)
- **Status:** Done (frontend/src/**)
- **Note:** Currently uses mocks; real backend integration is Task 5.1 below

#### D2.11 — Dashboard controls & views — ✅ COMPLETE (MOCK-BASED)
- **Status:** All components built with mocks
- **Note:** Real backend integration is Task 5.1 below

#### D2.12 — Scripted demo agents + six-beat orchestration — TO DO (Task 6.1 below)

#### D2.13 — Runtime-safety/audit test suite — PARTIALLY COMPLETE
- **Status:** Identity and runtime tests done (89 passing total)
- **Remaining:** Audit/integrity tests (Task 6.2 below)

#### D2.14 — Revocation/kill-switch propagation metrics — TO DO (Task 6.3 below)

---

## [ARCHIVED] Historical File Ownership Map

**The following section is preserved for historical attribution only. Current implementation follows the single-developer model documented above.**

---

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

## [ARCHIVED] Historical Dependency and Handoff Points

**The following section is preserved for historical reference. Current dependencies are documented in the milestones section above.**

---

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

## [ARCHIVED] Historical Parallel Development Timeline

**The following section is preserved for historical reference. Current implementation follows the vertical milestone order documented above.**

---

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

## [ARCHIVED] Historical Mock/Stub Strategy

**Preserved for reference. Current implementation can still use mocks during development, but there are no cross-developer coordination requirements.**

---

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
