# D2 → D1 Integration & Handoff Guide

**For:** Developer 1
**Purpose:** Understand what D2 has implemented and how to integrate with it, without inspecting D2's codebase.

---

## 1. Quick Status

| Feature | Status | D1 Action Needed |
|---------|--------|------------------|
| Identity verification | IMPLEMENTED / NOT INTEGRATED | Provide Agent model + AgentLookup implementation |
| Runtime status (check_runtime_status) | IMPLEMENTED / NOT INTEGRATED | Provide Redis client implementation |
| Agent revoke/restore | NOT STARTED | - |
| Fleet halt/resume | NOT STARTED | - |
| Audit persistence | NOT STARTED | D1.2 (agents migration) must land first |
| Audit integrity verification | NOT STARTED | - |
| Audit query APIs | NOT STARTED | - |
| Frontend dashboard | NOT STARTED | - |
| Demo agents (6-beat scenario) | NOT STARTED | - |

**Status Legend:**
- `NOT STARTED` - No implementation exists yet
- `IN PROGRESS` - Currently being implemented
- `IMPLEMENTED / NOT INTEGRATED` - Code exists, tests pass, awaiting D1 integration
- `READY FOR INTEGRATION` - Fully tested and documented
- `INTEGRATED` - D1 has successfully integrated
- `BLOCKED` - Waiting on D1 or external dependency

---

## 2. How D1 and D2 Fit Together

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AGENT REQUEST                                 │
│  POST /action-request                                                │
│  Headers: X-Agent-Id, X-Agent-Secret                                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    D1: ORCHESTRATION (/action-request)                │
│  Step 1: Identity Check → D2.verify_identity()                       │
│          [IMPLEMENTED]                                               │
│                                                                       │
│  Step 2: Runtime Safety → D2.check_runtime_status()                   │
│          [IMPLEMENTED / NOT INTEGRATED]                               │
│                                                                       │
│  Step 3: Policy Evaluation → D1.evaluate_policy()                     │
│          [D1-OWNED]                                                   │
│                                                                       │
│  Step 4: Spend Check → D1.reserve_budget_atomic()                     │
│          [D1-OWNED]                                                   │
│                                                                       │
│  Step 5: Decision → ALLOW or DENY                                     │
│                                                                       │
│  Step 6: Audit Write → D2.record_decision()                          │
│          [PLANNED]                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Current state:** Identity verification and runtime status are implemented and tested. Agent revoke/restore, fleet halt/resume, and audit write are planned.

---

## 3. Integration Points

### 3.1 Identity Verification (IMPLEMENTED / NOT INTEGRATED)

**What it does:** Validates agent credentials using timing-safe comparison. Returns whether credentials are valid and which agent ID authenticated.

**D1 calls:**
```python
from services.identity import verify_identity, set_agent_lookup

# During app startup - ONCE
set_agent_lookup(your_agent_lookup_implementation)

# In request pipeline
result = verify_identity(agent_id, secret)
if not result.valid:
    return HTTP 401 Unauthorized
```

**Input:**
| Field | Type | Description |
|-------|------|-------------|
| agent_id | str | Agent identifier from request header |
| secret | str | Shared secret from request header |

**Output (IdentityResult):**
| Field | Type | Description |
|-------|------|-------------|
| valid | bool | True if credentials match |
| agent_id | str \| None | Agent ID when valid=True, None when valid=False |

**Example flow:**
```
Agent Request → Extract X-Agent-Id, X-Agent-Secret
    → verify_identity(agent_id, secret)
    → IdentityResult(valid=True/False)
    → If False: Return 401
    → If True: Continue to runtime check
```

**Failure behavior:**
- Invalid credentials: Returns `IdentityResult(valid=False, agent_id=None)`
- Unknown agent: Returns `IdentityResult(valid=False, agent_id=None)`
- Lookup not configured: Returns `IdentityResult(valid=False, agent_id=None)` (fail-closed)
- No exceptions thrown for invalid input

**Security properties:**
- Timing-safe comparison prevents timing attacks
- Supports full Unicode character set
- Secrets never logged or exposed in exceptions
- Fail-closed when agent lookup is not configured

**What D1 must provide:**
1. The `Agent` database model with a `shared_secret` column
2. A concrete implementation of the `AgentLookup` protocol
3. Call `set_agent_lookup()` once during application startup

**AgentLookup protocol (D2 defines, D1 implements):**
```python
from services.identity import AgentLookup

class D1AgentLookup:
    def get_agent_secret(self, agent_id: str) -> Optional[str]:
        # Query your database for agent by agent_id
        # Return agent.shared_secret if found, else None
        ...
```

**Integration example:**
```python
# In your D1 code (e.g., main.py or app initialization)
from services.identity import set_agent_lookup

# Implement the AgentLookup protocol using your database architecture
# D1 controls the concrete implementation details
set_agent_lookup(your_agent_lookup_implementation)
```

---

### 3.2 Runtime Status (IMPLEMENTED / NOT INTEGRATED)

**What it does:** Validates runtime safety state using Redis-backed fleet and agent status tracking. Returns whether the fleet is halted, the agent is revoked, and the runtime state is available.

**D1 calls:**
```python
from services.runtime_state import check_runtime_status, set_redis_client

# During app startup - ONCE
set_redis_client(your_redis_client_implementation)

# In request pipeline
status = check_runtime_status(agent_id)
if not status.available:
    return HTTP 503 Service Unavailable  # RUNTIME_STATE_UNAVAILABLE
if status.fleet_halted or status.agent_revoked:
    return HTTP 403 Forbidden  # RUNTIME_STATE_DENY
```

**Input:**
| Field | Type | Description |
|-------|------|-------------|
| agent_id | str | Agent identifier from identity check |

**Output (RuntimeStatus):**
| Field | Type | Description |
|-------|------|-------------|
| fleet_halted | bool | True if fleet-wide kill switch is active |
| agent_revoked | bool | True if this specific agent is revoked |
| available | bool | False if Redis unreachable or state is malformed |

**Redis Keys (D2-owned, NO TTL):**
| Key | Canonical Values | Meaning |
|-----|-----------------|---------|
| `fleet:halted` | "true", "false" | Fleet-wide kill switch state |
| `agent:{id}:status` | "active", "revoked" | Per-agent revocation state |

**Canonical value contract (strict):**
- NO support for 1/0, yes/no, or other boolean representations
- Case-sensitive matching only (no "True", "FALSE", etc.)
- Both bytes and str types are accepted
- Invalid UTF-8 bytes trigger fail-closed

**Overlay model (missing keys):**
- Missing `fleet:halted` → fleet_halted=False (fleet operational)
- Missing `agent:{id}:status` → agent_revoked=False (agent active)
- Both keys missing → fully operational (available=True)

**Example flow:**
```
Agent Request → check_runtime_status(agent_id)
    → Read fleet:halted and agent:{id}:status from Redis
    → Parse values against canonical forms
    → RuntimeStatus(fleet_halted, agent_revoked, available)
    → If available=False: Return 503
    → If fleet_halted=True or agent_revoked=True: Return 403
    → Otherwise: Continue to policy evaluation
```

**Failure behavior:**
- Redis not configured: Returns `RuntimeStatus(available=False)`
- Redis connection error: Returns `RuntimeStatus(available=False)`
- Malformed/unrecognized value: Returns `RuntimeStatus(available=False)`
- Decode failure (invalid UTF-8): Returns `RuntimeStatus(available=False)`
- Empty/None agent_id: Returns `RuntimeStatus(available=False)`
- Unexpected data type: Returns `RuntimeStatus(available=False)`

**Safety properties:**
- Fail-closed: Any error or malformed state → available=False
- Strict parsing: Only canonical values accepted
- Overlay model: Missing keys → operational defaults
- No silent failures: All errors surface as unavailable state
- Fail-closed handling for Redis errors and malformed runtime state
- Thread-safe: Concurrent reads are safe

**What D1 must provide:**
1. A concrete implementation of the `RedisClient` protocol
2. Call `set_redis_client()` once during application startup
3. Ensure Redis is accessible before accepting requests

**RedisClient protocol (D2 defines, D1 implements):**
```python
from services.runtime_state import set_redis_client, RedisClient

class D1RedisClient:
    def __init__(self, redis_url: str):
        import redis
        self.client = redis.from_url(redis_url)

    def get(self, key: str) -> Optional[Union[str, bytes]]:
        # Return the raw Redis response (str, bytes, or None)
        # Redis errors MUST propagate to _redis_get() for fail-closed handling
        return self.client.get(key)

# During app initialization
set_redis_client(D1RedisClient(redis_url))
```

**Integration status:** IMPLEMENTED / NOT INTEGRATED
- D2 code is complete and tested (46 passing tests)
- Awaiting D1's Redis client implementation
- D2.3 (revoke/restore) and D2.4 (halt/resume) are NOT implemented yet
- State changes (write operations) must wait for D2.3/D2.4

---

## 4. D2-Owned Runtime State

**Redis keys (D2-owned, NO TTL):**
- `agent:{id}:status` - Runtime status: "active" or "revoked"
- `fleet:halted` - Fleet-wide halt flag: "true" or "false"

**State persistence:** Runtime safety keys have NO TTL. State changes occur ONLY through explicit revoke/restore/halt/resume operations (D2.3, D2.4 - NOT YET IMPLEMENTED).

---

## 5. Database & Migration Dependencies

### D2 Migration Prerequisites

| Migration | Owner | Status | Dependencies |
|----------|-------|--------|--------------|
| `0001_agents.py` | D1 | NOT STARTED | None |
| `0002_audit_log.py` | D2 | NOT STARTED | BLOCKED on `0001_agents.py` |

**D2's audit_log migration (0002) requires D1's agents migration (0001) to exist first** due to the foreign key: `audit_log.agent_id → agents.id`.

### D1 Prerequisites for D2

Before D2 can implement certain features, D1 must provide:

| Feature | D1 Prerequisite | Status |
|---------|-----------------|--------|
| Identity verification | `Agent` model with `shared_secret` column, `AgentLookup` implementation | IMPLEMENTED / NOT INTEGRATED |
| Runtime status | Redis infrastructure, `RedisClient` implementation | IMPLEMENTED / NOT INTEGRATED |
| Audit persistence | `agents` table with `id` primary key | NOT STARTED |

---

## 6. APIs Exposed by D2

*This section will be populated as endpoints are implemented.*

**Planned endpoints (per tasks-detailed.md):**

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/agents/{id}/revoke` | POST | Set agent to revoked | NOT STARTED |
| `/agents/{id}/restore` | POST | Set agent to active | NOT STARTED |
| `/fleet/halt` | POST | Set fleet_halted = true | NOT STARTED |
| `/fleet/resume` | POST | Set fleet_halted = false | NOT STARTED |
| `/audit/feed` | GET | Recent decisions for activity feed | NOT STARTED |
| `/audit/log` | GET | Filterable audit log | NOT STARTED |
| `/audit/verify-chain` | POST | Verify hash chain integrity | NOT STARTED |
| `/agents/{id}/runtime-status` | GET | Fetch live runtime status | NOT STARTED |

---

## 7. What D2 Currently Needs From D1

### Active Integration Requirements

For Identity Verification (D2.1) and Runtime Status (D2.2), D1 needs to provide:

**Identity Verification (D2.1):**
1. **Agent database model** with `shared_secret` column
2. **AgentLookup protocol implementation** that queries the database
3. **One-time call to `set_agent_lookup()`** during application initialization

**Runtime Status (D2.2):**
1. **Redis client** (redis-py or equivalent) accessible from application
2. **RedisClient protocol implementation** wrapping the Redis client
3. **One-time call to `set_redis_client()`** during application initialization

### Why D2 Needs This

D2's runtime functions don't directly access external dependencies. Instead, they use dependency injection:

- D2 defines the `AgentLookup` and `RedisClient` protocols (interfaces)
- D2 provides `set_agent_lookup()` and `set_redis_client()` to inject concrete implementations
- D1 implements these protocols using their infrastructure
- D1 calls the setters once at startup

This keeps D2's logic independent of D1's infrastructure while enabling clean integration.

### Current D1 Dependencies

D2.1 and D2.2 are implemented and tested. Integration requires D1 to provide:

**For D2.1 (Identity):**
1. **Agent database model** with `shared_secret` column (D1.2)
2. **AgentLookup protocol implementation** that queries the database
3. **One-time call to `set_agent_lookup()`** during application initialization

**For D2.2 (Runtime):**
1. **Redis infrastructure** (D1's docker-compose provides this)
2. **RedisClient protocol implementation** wrapping the Redis client
3. **One-time call to `set_redis_client()`** during application initialization

No code blockers exist for D2.1/D2.2, but integration is incomplete until D1 provides these implementations.

---

## 8. Integration Checklist

Use this checklist when integrating D2 work into D1's orchestration.

### Before Integration

- [ ] Read D2_HANDOFF.md "Quick Status" section
- [ ] Identify which D2 features are READY FOR INTEGRATION
- [ ] Review D2-owned Redis keys (ensure no conflicts)
- [ ] Verify D1 prerequisites are met (agents table, migrations, Redis)

### During Integration

- [ ] Import D2 functions into D1's orchestration
- [ ] Wire D2 calls in the correct order (Identity → Runtime → Policy → Spend → Decision → Audit)
- [ ] Call `set_agent_lookup()` once during app initialization
- [ ] Call `set_redis_client()` once during app initialization
- [ ] Translate IdentityResult/RuntimeStatus responses appropriately
- [ ] Handle HTTP 401 for identity failures (not 200 with decision:deny)
- [ ] Handle HTTP 503 for runtime unavailable (available=False)
- [ ] Handle HTTP 403 for runtime deny (fleet_halted/agent_revoked)

### After Integration

- [ ] Run D2's unit tests to ensure no regression
- [ ] Run end-to-end test with both subsystems
- [ ] Verify audit log entries are written for all decisions
- [ ] Update D2_HANDOFF.md status to INTEGRATED

---

## 9. Recent D2 Changes

### 2026-07-22: D2.2 Runtime Status (IMPLEMENTED)

**Files created/modified:**
- `services/runtime_state.py` - Complete implementation with fail-closed behavior
- `tests/test_runtime_safety.py` - 46 comprehensive tests, all passing

**What was implemented:**
- `check_runtime_status(agent_id) -> RuntimeStatus`
- `set_redis_client(client)` - Module-level dependency injection
- `reset_redis_client()` - Test cleanup utility
- `RedisClient` protocol - D1's integration point
- `RuntimeStatus` dataclass - Frozen schema
- Overlay model (missing keys → operational defaults)
- Strict canonical value parsing (no 1/0, case-sensitive)
- Fail-closed behavior on Redis errors/malformed values
- UTF-8 decode error handling
- Thread-safe concurrent reads

**Tests performed (46 passing):**
- Valid operational states (all keys missing, fleet halted, agent revoked)
- Redis unreachable/unconfigured scenarios
- Parse failures (decode errors, unrecognized values, unexpected types)
- Data type variations (bytes, str, None)
- Canonical value strictness (rejects 1/0, case variations)
- Multiple agents with independent status
- Concurrent read safety
- Module-level dependency injection verification
- Frozen contract signature verification
- RuntimeStatus immutability

**Integration status:** IMPLEMENTED / NOT INTEGRATED
- D2 code is complete and tested
- Awaiting D1's Redis client implementation
- D2.3 (revoke/restore) and D2.4 (halt/resume) are NOT implemented yet

---

### 2026-07-21: D2.1 Identity Verification (IMPLEMENTED)

**Files created/modified:**
- `services/identity.py` - Complete implementation with timing-safe comparison
- `tests/test_identity.py` - 24 comprehensive tests, all passing

**What was implemented:**
- `verify_identity(agent_id, secret) -> IdentityResult`
- `set_agent_lookup(lookup)` - Module-level dependency injection
- `reset_agent_lookup()` - Test cleanup utility
- `AgentLookup` protocol - D1's integration point
- `IdentityResult` dataclass - Frozen schema
- Timing-safe comparison with `hmac.compare_digest()`
- Full Unicode/bytes support
- Fail-closed behavior when lookup not configured
- No secret logging/exposure

**Tests performed (24 passing):**
- Valid credentials acceptance
- Invalid credentials rejection
- Unknown agent handling
- Empty/malformed input handling
- Security properties (timing-safe, case-sensitive, no leakage)
- Integration cases (multiple agents, special/unicode characters)
- Module-level dependency injection verification
- Frozen contract signature verification

**Integration status:** IMPLEMENTED / NOT INTEGRATED
- D2 code is complete and tested
- Awaiting D1's Agent model and AgentLookup implementation

---

## 10. Frozen Integration Contracts

These are the cross-developer interfaces agreed upon on Day 1 (from tasks-detailed.md). D2 implements these; D1 consumes them.

### Identity Verification

```python
# D2 implements, D1 calls
verify_identity(agent_id: str, secret: str) -> IdentityResult

# Returns
{
    "valid": bool,
    "agent_id": str | None  # None when valid=False
}
```

**D1 usage:** Call first in the pipeline. If `valid=False`, return HTTP 401.

---

### Runtime Status

```python
# D2 implements, D1 calls
check_runtime_status(agent_id: str) -> RuntimeStatus

# Returns
{
    "fleet_halted": bool,
    "agent_revoked": bool,
    "available": bool  # False if Redis unreachable → fail-closed deny
}
```

**D1 usage:** Call after identity check. If `available=False`, return HTTP 503 (RUNTIME_STATE_UNAVAILABLE). If `fleet_halted=True` or `agent_revoked=True`, return HTTP 403 (RUNTIME_STATE_DENY). Otherwise, continue to policy evaluation.

**Redis keys (D2-owned):**
- `fleet:halted` stores "true" (halted) or "false" (operational)
- `agent:{id}:status` stores "active" (operational) or "revoked" (blocked)

**Integration:** D1 must call `set_redis_client()` once during app initialization with a concrete `RedisClient` implementation.

---

### Decision Event

```python
# D1 defines shape, D2 consumes
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

**D2 usage:** D2's `record_decision()` accepts this shape and writes it to the audit log with hash chain.

---

### Audit Write Result

```python
# D2 implements, D1 consumes
{
    "audit_log_id": UUID,
    "hash": str
}
```

**D1 usage:** Include `audit_log_id` in `ActionDecision` response to agent.

---

## Appendix: D2 File Ownership

D2 owns these files (per tasks-detailed.md):

| File | Purpose |
|------|---------|
| `services/identity.py` | `verify_identity()` |
| `services/runtime_state.py` | `check_runtime_status()`, revoke/restore/halt/resume logic |
| `services/hash_chain.py` | `record_decision()`, `verify_chain()` |
| `db/models/audit_log.py` | Audit log table model |
| `routers/runtime.py` | `/agents/{id}/revoke`, `/restore` |
| `routers/fleet.py` | `/fleet/halt`, `/resume` |
| `routers/audit.py` | `/audit/feed`, `/audit/log`, `/audit/verify-chain` |
| `schemas/audit.py` | D2-owned schemas (AuditLogEntry, FleetState) |
| `demo/agents/*` | Three scripted demo agents + runner |
| `frontend/**` | Entire React dashboard |

D2 NEVER edits D1-owned files.
