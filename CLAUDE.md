---
title: Agent Governance System - Single Developer Implementation
description: Runtime safety, policy enforcement, audit integrity, and dashboard implementation
---

# Agent Governance System - Implementation Workspace

**Status:** Single developer (D2) owns all remaining implementation after D1/D2 integration checkpoint (2026-07-23).

## Ownership Model (Updated 2026-07-24)

**All remaining implementation is owned by D2.** The previous D1/D2 split has been merged.

**Previously D1-owned, now D2-owned:**
- `routers/action.py` — /action-request orchestration
- `routers/policies.py` — policy/spend config APIs
- `schemas/action.py` — ActionRequest/ActionDecision/DecisionEvent
- `schemas/agent.py` — Agent, AgentStatus schemas
- `policy/opa_client.py` — OPA integration
- `policy/fallback.py` — Python fallback
- `services/spend.py` — spend caps
- `middleware/timing.py` — latency measurement
- `tests/test_policy_*.py` — policy tests
- `tests/test_spend_cap.py` — spend tests
- `tests/test_policy_latency.py` — latency tests

**Originally D2-owned, still D2-owned:**
- `services/identity.py` — verify_identity ✅ COMPLETE
- `services/runtime_state.py` — check_runtime_status ✅ COMPLETE
- `services/hash_chain.py` — record_decision, verify_chain (TO DO)
- `db/models/audit_log.py` — audit log table (TO DO)
- `routers/runtime.py` — revoke/restore (TO DO)
- `routers/fleet.py` — halt/resume (TO DO)
- `routers/audit.py` — audit APIs (TO DO)
- `schemas/audit.py` — D2-owned schemas (TO DO)
- `demo/agents/*` — scripted demo agents (TO DO)
- `frontend/**` — React dashboard ✅ COMPLETE (mock-based)

**Shared infrastructure (maintained by D2):**
- `main.py`, `docker-compose.yml`, `.env.example` — environment
- `db/models/agent.py` — agent model ✅ EXISTS
- `scripts/agent_lookup.py` — AgentLookup ✅ EXISTS

## Conceptual Domains (Still Useful for Understanding)

**Policy & Financial Governance:** "What is this agent allowed to do and spend?"
**Runtime Safety, Audit & Operator Control:** "Is this agent operational, can we stop it, and can we prove what happened?"

These domains help understand the architecture but no longer represent ownership boundaries.

## Source of Truth

1. **PRD_AMEX_hybrid (1).md** - System architecture, requirements, non-goals
2. **PRD/tasks.md** - High-level task plan (updated for single developer)
3. **PRD/tasks-detailed.md** - Detailed implementation tasks with acceptance criteria
4. **D2_HANDOFF.md** - Current status and integration roadmap

**Frozen contracts:** The following function signatures and data structures are frozen. Changes require explicit review.

## Gateway Check Order (Canonical - Authoritative)

This is the definitive order for the /action-request pipeline. DO NOT change.

```
1. Identity verification (verify_identity) ✅ COMPLETE
   → Returns 401 if failed

2. Fleet halted check (check_runtime_status) ✅ COMPLETE
   → Returns 403 if fleet_halted=True

3. Agent revoked check (check_runtime_status) ✅ COMPLETE
   → Returns 403 if agent_revoked=True

4. Permission/max-amount policy evaluation (evaluate_policy)
   → Denies if action not in permissions or amount > max_single_amount

5. Spend-cap reservation (reserve_budget_atomic)
   → Denies if remaining_budget insufficient (atomic DECRBY)

6. ALLOW/DENY decision
   → Final decision with reason_code

7. Audit recording (record_decision)
   → Writes to audit_log with hash chain for ALL decisions
```

All denied requests short-circuit immediately - later stages are never evaluated.

**Implemented functions:**
- `verify_identity(agent_id, secret) -> IdentityResult` ✅
- `check_runtime_status(agent_id) -> RuntimeStatus` ✅

**To be implemented:**
- `evaluate_policy(agent, action_type, amount) -> PolicyResult`
- `reserve_budget_atomic(agent_id, amount) -> SpendResult`
- `record_decision(event: DecisionEvent) -> AuditWriteResult`

## Redis Key Usage

| Key | Purpose | Service |
|-----|---------|---------|
| `agent:{id}:status` | Runtime safety (active/revoked) | check_runtime_status(), revoke/restore |
| `fleet:halted` | Fleet-wide emergency stop | check_runtime_status(), halt/resume |
| `agent:{id}:remaining_budget` | Daily spend cap tracking | reserve_budget_atomic() |

**State persistence**: All Redis keys have NO TTL. State changes occur ONLY through explicit operations:
- Runtime state: revoke/restore/halt/resume operations
- Spend state: reset_spend operation

## Frozen Contracts

These interfaces are defined by tasks-detailed.md and should not be changed without review.

### DecisionEvent (D1 defines shape, D2 consumes)
```python
{
    "agent_id": str,
    "action_type": str,
    "amount": float,
    "decision": "allow" | "deny",
    "reason": str | None,
    "reason_code": str,
    "policy_version": str,
    "timestamp": datetime
}
```
**D2 schema rule**: This is D1's canonical type. D2 does NOT create a duplicate definition. Import from D1's schemas when available; use temporary mock/test representation during independent development.

### IdentityResult (D2 defines and implements)
```python
{
    "valid": bool,
    "agent_id": str | None
}
```

### RuntimeStatus (D2 defines and implements)
```python
{
    "fleet_halted": bool,
    "agent_revoked": bool,
    "available": bool  # False if Redis unreachable → fail-closed deny
}
```

### AuditWriteResult (D2 defines and implements)
```python
{
    "audit_log_id": UUID,
    "hash": str
}
```

## Schema Files to Create

- `schemas/action.py` - ActionRequest, ActionDecision, DecisionEvent
- `schemas/agent.py` - Agent, AgentStatus, policy-related schemas
- `schemas/audit.py` - AuditLogEntry, RuntimeStatus, FleetState, IntegrityStatus

**Implementation notes:**
- DecisionEvent shape is frozen (see tasks-detailed.md)
- RuntimeStatus is already defined in services/runtime_state.py
- Import/use types consistently across services and routers

## Technical Dependencies

**Audit migration dependency:**
- audit_log migration requires agents migration (revision: `09ee32e4e00a`) to exist first (FK dependency)
- ✅ Already satisfied - agents table exists
- New migration should use `alembic revision -m "create audit log table"` and set `down_revision = "09ee32e4e00a"`
- Migration filename is NOT required to be "0002_audit_log.py"

**Service dependencies:**
- Hash chain write (record_decision) requires audit_log table to exist
- Chain verification (verify_chain) requires hash chain write
- Revoke/halt APIs require record_decision (to log control actions)
- Policy fallback (fallback.py) should match OPA logic exactly
- /action-request orchestration requires all services to be complete

**Incremental testing:**
- Each milestone adds its own tests immediately
- Final testing phase means E2E, demo validation, metrics, regression

## Six-Beat Demo (All Implemented by D2)

| Beat | Behavior | Implementation |
|------|----------|----------------|
| 1 | Agent A compliant | Policy + spend enforcement allows, dashboard displays feed |
| 2 | Agent B violates | Policy + spend enforcement denies, dashboard displays denial |
| 3 | Revoke Agent B | Runtime safety - per-agent revocation |
| 4 | Agent C runaway | Dashboard observes rapid-fire requests |
| 5 | Fleet kill switch | Runtime safety - fleet-wide halt |
| 6 | Audit log + integrity | Audit integrity - tamper check |

## Standard Workflow for Implementation Tasks

1. **READ CONTEXT** - Review tasks-detailed.md for the specific task
2. **INSPECT CURRENT REPO** - Check what exists, identify dependencies
3. **PLAN** - Design implementation approach
4. **IMPLEMENT ONE TASK ONLY** - Implement single task, do not skip ahead
5. **RUN FOCUSED TESTS** - Test the specific thing just implemented
6. **VERIFY** - Ensure all tests pass
7. **EXPLAIN CHANGES TO USER** - What changed, why, data flow, failure modes, tests
8. **STOP BEFORE NEXT TASK** - Do not automatically continue

**Documentation rules:**
- Update D2_HANDOFF.md after each task completion
- Document actual implemented behavior, not just the plan
- Do NOT mark a feature READY if tests have not passed

## Post-Implementation Explanation Template

After each implementation, explain:
- **What changed**: Files created/modified, functions added
- **Why designed this way**: Architectural reasoning, alternatives considered
- **Request/data flow**: How data flows through the component
- **Failure modes**: What can go wrong, how it's handled
- **Tests performed**: What was tested, how to verify

## Git Strategy

Current branch: `feat/d2-runtime-safety`

Commits should be small and logically scoped:
```
feat(services): implement hash-chain write with canonicalization
feat(routers): add audit feed and query APIs
feat(services): implement OPA policy integration
```

Use conventional commit format: `<type>: <scope>: <description>`

## Key Architectural Invariants

1. **Fail-closed**: If Redis is unreachable, deny the request (for both runtime-safety and spend-state keys)
2. **Check order matters**: Identity → Runtime safety → Policy → Spend → Decision → Audit
3. **Hash chain canonicalization**: Sort keys alphabetically, strip whitespace BEFORE hashing
4. **Audit append-only**: Never UPDATE/DELETE audit_log rows
5. **Dashboard is view-only**: All enforcement lives in backend
6. **Runtime state persistence**: No TTLs on safety keys; explicit operations only

## Current Test Status

**89 tests passing:**
- 24 identity unit tests
- 46 runtime state unit tests
- 7 identity integration tests (real Postgres)
- 9 Redis integration tests (real Redis)
- 3 startup wiring tests

## Next Steps

See PRD/tasks.md and D2_HANDOFF.md for the full implementation roadmap organized by vertical milestones.

**Immediate next milestone: Milestone A (Audit Foundation)**
- Task 2.1: Audit log table + migration
- Task 2.2: Hash-chain write function
- Task 2.3: Chain verification

**Implementation order summary:**
```
Milestone A: Audit Foundation (2.1 → 2.2 → 2.3)
    ↓
Milestone B: Runtime Control APIs (3.1 → 3.2)
    ↓
Milestone C: Policy + Spend (2.4, then 2.5 → 2.6)
    ↓
Milestone D: Orchestration (4.1)
    ↓
Milestone E: Remaining APIs (3.3 → 3.4 → 3.5 → 3.6 → 3.7)
    ↓
Milestone F: Frontend Integration (5.1 → 5.2)
    ↓
Milestone G: Demo + E2E + Metrics (6.1 → 6.2 → 6.3)
```

Each milestone includes its own tests. Final milestone G means full E2E validation.
