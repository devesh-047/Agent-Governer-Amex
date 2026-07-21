---
title: Agent Governance System - Developer 2 Workspace
description: D2-owned runtime safety, audit integrity, and dashboard implementation
---

# Agent Governance System - Developer 2 Workspace

**You are operating in Developer 2's workspace.**

## Developer 2 Ownership

**Domain**: "Is this agent operational RIGHT NOW, can we stop it instantly, and can we PROVE what happened?"

**D2 owns exclusively**:
- `services/identity.py` - `verify_identity()`
- `services/runtime_state.py` - `check_runtime_status()`, fail-closed behavior
- `services/hash_chain.py` - `record_decision()`, `verify_chain()`
- `db/models/audit_log.py` - audit log table with hash-chain columns
- `routers/runtime.py` - `/agents/{id}/revoke`, `/restore`
- `routers/fleet.py` - `/fleet/halt`, `/resume`
- `routers/audit.py` - `/audit/feed`, `/audit/log`, `/audit/verify-chain`
- `demo/agents/*` - scripted demo agents + runner
- `frontend/**` - entire React dashboard

**D2 NEVER touches** (D1 domain - stop and request handoff):
- `main.py`, `docker-compose.yml`, `.env.example`
- `db/models/agent.py`
- `schemas/action.py`, `schemas/agent.py`
- `policy/*`
- `services/spend.py`
- `routers/action.py`, `routers/policies.py`
- Redis key: `agent:{id}:remaining_budget`

## Source of Truth

1. **PRD_AMEX_hybrid (1).md** - System architecture, requirements, non-goals
2. **tasks.md** - High-level task split
3. **tasks-detailed.md** - Detailed D2 tasks, contracts, migration ordering

**Never silently change frozen cross-developer contracts.**

## Critical Request Pipeline (MEMORIZE)

```
Request → Identity check (D2) → Runtime safety check (D2) → Permission/spend evaluation (D1) → ALLOW/DENY → Audit write (D2)
```

D1 orchestrates. D2 implements the three functions D1 calls:
- `verify_identity(agent_id, secret) -> IdentityResult`
- `check_runtime_status(agent_id) -> RuntimeStatus`
- `record_decision(event: DecisionEvent) -> AuditWriteResult`

## Redis Key Ownership

| Key | Owner | Domain |
|-----|-------|--------|
| `agent:{id}:status` | D2 | Runtime safety (active/revoked) |
| `fleet:halted` | D2 | Fleet-wide emergency stop |
| `agent:{id}:remaining_budget` | D1 | Financial governance |

**Rule**: Never read/write the other developer's keys. Call their function instead.

**State persistence**: Runtime safety state (`agent:{id}:status`, `fleet:halted`) has NO TTL. State changes occur ONLY through explicit revoke/restore/halt/resume operations.

## Cross-Developer Contracts (Frozen Day 1)

These interfaces are defined by tasks-detailed.md. Do NOT change them unilaterally.

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

## Schema File Ownership

- `schemas/action.py` - D1 owns (ActionRequest, ActionDecision, DecisionEvent interface)
- `schemas/agent.py` - D1 owns (Agent, AgentStatus, policy schemas)
- `schemas/audit.py` - D2 owns ONLY genuinely D2-owned schemas (AuditLogEntry, RuntimeStatus, FleetState)

**D2 schema rules**:
1. Create schemas/audit.py ONLY for D2-owned schemas required by tasks-detailed.md
2. Do NOT duplicate D1's canonical contract types
3. Import D1 types when available; use mock/test representation during independent development
4. If a canonical contract type belongs to D1, DO NOT create a duplicate

## Dependency Awareness

**Hard blocker**: D2's audit_log migration (0002) requires D1's agents migration (0001) to exist first (FK dependency).

**Otherwise, D2 can work independently**:
- Identity verify - mock agent lookup
- Runtime state - needs only Redis (available via D1's docker-compose)
- Hash chain - contract-only on DecisionEvent shape (use mock representation)
- Dashboard - build against mocked API shapes

## Six-Beat Demo (D2 Orchestrates)

| Beat | Behavior | D2 Responsibility |
|------|----------|-------------------|
| 1 | Agent A compliant | Dashboard displays activity feed |
| 2 | Agent B violates | Dashboard displays denial |
| 3 | Revoke Agent B | **D2 runtime safety** - per-agent revocation |
| 4 | Agent C runaway | Dashboard observes rapid-fire requests |
| 5 | Fleet kill switch | **D2 runtime safety** - fleet-wide halt |
| 6 | Audit log + integrity | **D2 audit integrity** - tamper check |

## Standard Workflow for Non-Trivial D2 Tasks

1. **READ CONTEXT** - Review tasks-detailed.md for the specific D2.X task
2. **INSPECT CURRENT REPO** - Check what exists, identify dependencies
3. **PLAN** - Design implementation approach
4. **ARCHITECTURE-GUARDIAN REVIEW** - Verify no D1/D2 boundary violations
5. **USER/PLAN CHECKPOINT** - Present plan to user, wait for approval
6. **IMPLEMENT ONE TASK ONLY** - Implement single D2.X task, not D2.X+1
7. **RUN FOCUSED TESTS** - Test the specific thing just implemented
8. **TEST-REVIEW-ENGINEER ADVERSARIAL REVIEW** - Independent adversarial review
9. **FIX IF REQUIRED** - Address findings from review
10. **EXPLAIN CHANGES TO USER** - What changed, why, data flow, failure modes, tests
11. **STOP BEFORE NEXT TASK** - Do not automatically continue

## Post-Implementation Explanation Template

After each implementation, explain:
- **What changed**: Files created/modified, functions added
- **Why designed this way**: Architectural reasoning, alternatives considered
- **Request/data flow**: How data flows through the component
- **Failure modes**: What can go wrong, how it's handled
- **Tests performed**: What was tested, how to verify
- **Integration assumptions**: What's mocked, what depends on D1

## Git Strategy (One D2 Feature Branch)

Single branch: `feat/d2-runtime-safety`

Commits should be small and logically scoped:
```
d2: identity: implement verify_identity with constant-time secret comparison
d2: runtime: implement check_runtime_status with fail-closed behavior
d2: audit: add hash-chain write function with canonicalization
```

Use conventional commit format: `d2: <scope>: <description>`

## When D2 Work Appears to Require D1 Changes

**STOP and explain the required handoff instead of editing the file.**

Example scenarios:
- "This needs a new field on the Agent model" → Tell D1 to add it; D2 specifies requirement
- "This needs schemas/action.py to change" → STOP; that's D1's file
- "This needs to call D1's policy function" → That's fine (D1 implements, D2 calls)
- "This needs to read agent:{id}:remaining_budget" → STOP; call D1's function instead

## Always Prefer Mocks/Stubs

When D1 functionality is unavailable:
1. Build against the frozen contract/interface
2. Mock the D1 function/endpoint
3. Document the mock in code comments
4. Swap in real implementation at integration time

## Key Architectural Invariants

1. **Fail-closed**: If Redis is unreachable for runtime-safety keys, deny the request
2. **Check order matters**: Identity → Runtime safety → Policy → Spend → Decision → Audit
3. **Hash chain canonicalization**: Sort keys alphabetically, strip whitespace BEFORE hashing
4. **Audit append-only**: Never UPDATE/DELETE audit_log rows
5. **Dashboard is view-only**: All enforcement lives in backend
6. **Runtime state persistence**: No TTLs on safety keys; explicit operations only
