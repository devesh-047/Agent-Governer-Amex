# Phase 1 Task Plan (Simplified)

Two developers, two coherent halves of the governance system. Full rationale/detail lives in `tasks-detailed.md` — this version is for quick day-to-day reference.

---

## The split, in one sentence each

- **Developer 1 — Policy & Financial Governance:** decides *what an agent may do and spend.*
- **Developer 2 — Runtime Safety, Audit & Operator Control:** decides *whether an agent may run right now, and proves what happened.*

## The request pipeline (memorize this order)

```
Request → Identity check (D2) → Fleet halted? / Agent revoked? (D2)
        → Permission + amount check (D1) → Spend cap check (D1)
        → ALLOW/DENY → Write to audit log (D2)
```

D1 owns the endpoint that runs this pipeline. D1 calls three functions D2 writes:
`verify_identity()`, `check_runtime_status()`, `record_decision()`.
D2 never calls into D1's policy/spend code.

---

## Developer 1 — build order

| # | Task | Files | Depends on |
|---|---|---|---|
| 1 | Scaffold repo (docker-compose, FastAPI skeleton, Postgres/Redis/OPA, Alembic) | `docker-compose.yml`, `.env.example`, `main.py` | — |
| 2 | `agents` table (permissions, max amount, daily cap, shared_secret) | `db/models/agent.py`, migration `0001` | Ask D2 what `shared_secret` needs first |
| 3 | `/action-request` endpoint — the pipeline above, using stubs for D2's 3 functions | `routers/action.py` | Task 2 |
| 4 | OPA/Rego policy check (permissions + max amount) | `policy/opa_client.py`, `.rego` files | Task 2 |
| 5 | Python fallback for policy (in case OPA stalls) | `policy/fallback.py` | Task 4 |
| 6 | Spend caps — atomic Redis decrement, no race conditions | `services/spend.py` | Task 3 |
| 7 | Policy config API + spend reset API | `routers/policies.py` | Tasks 4–6 |
| 8 | Tests: permission/limit/spend-cap correctness, concurrency | `tests/test_policy_enforcement.py`, `test_spend_cap.py` | Tasks 4–7 |
| 9 | Latency measurement | `middleware/timing.py` | Task 3 |

**Owns:** `main.py`, `docker-compose.yml`, `.env.example`, `db/models/agent.py`, `policy/*`, `services/spend.py`, `routers/action.py`, `routers/policies.py`.
**Owns this Redis key:** `agent:{id}:remaining_budget`.
**Never touches:** anything under `services/identity.py`, `services/runtime_state.py`, `services/hash_chain.py`, `routers/runtime.py`, `routers/fleet.py`, `routers/audit.py`, `frontend/`.

---

## Developer 2 — build order

| # | Task | Files | Depends on |
|---|---|---|---|
| 1 | Identity check (`agent_id` + secret) | `services/identity.py` | Tell D1 what field you need on Day 1; build against a mock until then |
| 2 | Runtime state in Redis: agent status + fleet halted flag | `services/runtime_state.py` | Nothing (just needs Redis running) |
| 3 | Revoke / restore endpoints | `routers/runtime.py` | Task 2 |
| 4 | Fleet halt / resume endpoints | `routers/fleet.py` | Task 2 |
| 5 | Fail-closed check: Redis down → deny, not allow | `services/runtime_state.py` | Task 2, verified with D1 at integration |
| 6 | Audit log table (append-only, hash-chain columns) | `db/models/audit_log.py`, migration `0002` | D1's `agents` migration must land first |
| 7 | Hash-chain write function (`record_decision`) | `services/hash_chain.py` | Task 6, agreed function shape with D1 |
| 8 | Chain verify / tamper detection | `services/hash_chain.py`, `routers/audit.py` | Task 7 |
| 9 | Audit feed + filtered log API | `routers/audit.py` | Tasks 6–8 |
| 10 | Dashboard shell + API client | `frontend/src/api/*`, `Dashboard.tsx` | Build against mocks first |
| 11 | Dashboard controls: activity feed, revoke/kill buttons, policy panel, audit table, integrity button | `frontend/src/components/*` | Task 10 |
| 12 | Three demo agents (compliant / violator / runaway) + full 6-beat script | `demo/agents/*` | Needs both subsystems mostly done |
| 13 | Tests: identity, revocation, kill switch, fail-closed, audit completeness, tamper detection | `tests/test_identity.py`, `test_runtime_safety.py`, `test_audit_and_hash_chain.py`, `test_tamper_detection.py` | Tasks 1–9 |
| 14 | Revocation/kill-switch propagation timing | test file | Needs D1's endpoint live |

**Owns:** `services/identity.py`, `services/runtime_state.py`, `services/hash_chain.py`, `db/models/audit_log.py`, `routers/runtime.py`, `routers/fleet.py`, `routers/audit.py`, `demo/*`, all of `frontend/`.
**Owns these Redis keys:** `agent:{id}:status`, `fleet:halted`.
**Never touches:** `main.py`, `docker-compose.yml`, `.env.example`, `db/models/agent.py`, `policy/*`, `services/spend.py`, `routers/action.py`, `routers/policies.py`.

---

## Three rules that prevent merge conflicts

1. **One file, one owner** — see the "Owns" lists above. If you need something in the other person's file, ask them to add it — don't edit it yourself.
2. **Talk to Redis only through your own keys** — D1 touches `remaining_budget` only; D2 touches `status`/`fleet:halted` only. If you need the other's state, call their function, don't read their key.
3. **Build against stubs, swap in the real thing later.** D1 fakes D2's 3 functions until they're ready. D2 fakes D1's agent data / endpoints until they're ready. Nobody should be blocked waiting on the other past Day 1–2.

## Hard sequencing (the only two things that truly block)

- D2's audit_log migration needs D1's `agents` migration to exist first (foreign key).
- D1 and D2 need to agree on the shape of `verify_identity()`, `check_runtime_status()`, and `record_decision()` on Day 1 — a 15-minute conversation, not a blocker.

## Six-beat demo — who it's proving

| Beat | What happens | Whose work it proves |
|---|---|---|
| 1 | Agent A does normal in-policy stuff | D1 (allows) + D2 (logs it) |
| 2 | Agent B tries something out of policy / over budget | D1 |
| 3 | Operator revokes Agent B | D2 |
| 4 | Agent C fires rapidly (runaway) | Both |
| 5 | Operator hits fleet kill switch | D2 |
| 6 | Audit log filter + integrity check | D2 |

## Everything from the PRD is covered by:

Identity → D2.1 · Permissions/limits → D1.4-5 · Spend caps → D1.6 · Fail-closed → D1.6 + D2.5 · Revocation → D2.3 · Kill switch → D2.4 · Audit log → D2.6-7 · Hash chain/tamper check → D2.7-8 · Dashboard → D2.10-11 · Demo agents/scenario → D2.12 · Latency/accuracy metrics → D1.8-9 · Propagation metrics → D2.14
