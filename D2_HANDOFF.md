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
| Frontend dashboard (Phase 1) | IMPLEMENTED / MOCK-BASED | Swap mocks to real API when D2 endpoints ready |
| Demo agents (6-beat scenario) | NOT STARTED | - |

**Status Legend:**
- `NOT STARTED` - No implementation exists yet
- `IN PROGRESS` - Currently being implemented
- `IMPLEMENTED / NOT INTEGRATED` - Code exists, tests pass, awaiting D1 integration
- `IMPLEMENTED / MOCK-BASED` - UI complete with mock data; backend integration pending
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

## 6. Frontend Dashboard (Phase 1 - MOCK-BASED)

### 6.1 Overview

**Status:** IMPLEMENTED / MOCK-BASED

The React dashboard is fully built and functional with deterministic mock data. All UI controls simulate backend operations. When D2 endpoints are ready, the single `src/api/index.ts` file will be updated to swap mocks for real fetch calls.

**What exists:**
- Complete responsive dashboard (768px+)
- Fleet status card with halt/resume controls
- Agent list with status indicators
- Agent detail drawer with revoke/restore controls
- Live activity feed
- Audit integrity verification with result modal
- Scenario selector for demo (dev only)

**What is mock-backed:**
- ALL API calls use `src/api/mocks.ts` (in-memory state)
- No real backend integration yet
- State persists only within browser session
- Scenario selector (NORMAL, RISK, INCIDENT) drives demo states

### 6.2 Frontend Architecture

```
frontend/
├── src/
│   ├── api/
│   │   ├── index.ts         # EXPORT: api (mocks → real client swap point)
│   │   ├── client.ts        # GovernanceApi interface (contracts)
│   │   ├── mocks.ts         # Mock implementation (Phase 1)
│   │   └── types.ts         # TypeScript types matching frozen contracts
│   ├── components/
│   │   ├── fleet/           # FleetStatusCard, FleetHaltModal
│   │   ├── agents/          # AgentsSection, AgentDrawer
│   │   ├── activity/        # ActivityFeedCard
│   │   ├── audit/           # AuditIntegrityCard, IntegrityResultModal
│   │   └── ui/              # Button, Modal, Toast, Loading, StatusBadge
│   ├── pages/               # Dashboard.tsx (main page)
│   └── hooks/               # usePolling.ts (live updates)
```

### 6.3 API Client Contract

The frontend consumes this single interface (`src/api/client.ts`):

```typescript
export interface GovernanceApi {
  // Fleet & System (D2)
  getFleetState(): Promise<FleetState>;
  haltFleet(): Promise<void>;
  resumeFleet(): Promise<void>;

  // Agents (D1 + D2 composed)
  getAgents(): Promise<AgentStatus[]>;
  getAgent(agentId: string): Promise<MockAgent>;

  // Agent Runtime Safety (D2)
  revokeAgent(agentId: string): Promise<void>;
  restoreAgent(agentId: string): Promise<void>;

  // Activity Feed (D2)
  getActivityFeed(limit?: number): Promise<ActivityEvent[]>;

  // Audit Integrity (D2)
  getIntegrityStatus(): Promise<IntegrityStatus>;
  verifyChain(): Promise<IntegrityStatus>;

  // Scenario control (mock-only, for demo)
  setScenario(scenario: Scenario): Promise<void>;
  getCurrentScenario(): Promise<Scenario>;
}
```

**Phase 1:** `api` exports `mockApi` (from `src/api/mocks.ts`)
**Phase 2+:** Change `src/api/index.ts` line 13 to export real client

### 6.4 Frontend Components

| Component | Purpose | Mock/Real |
|-----------|---------|-----------|
| `FleetStatusCard` | Shows fleet-wide halt status + halt button | Mock |
| `FleetHaltModal` | Confirmation modal for halt/resume | Mock |
| `AgentsSection` | List of all agents with status badges | Mock |
| `AgentDrawer` | Slide-out drawer with agent details + revoke/restore | Mock |
| `ActivityFeedCard` | Recent decision events (allow/deny) | Mock |
| `AuditIntegrityCard` | Shows last verified status + verify button | Mock |
| `IntegrityResultModal` | Displays hash chain verification results | Mock |
| `ScenarioSelector` | Dev-only dropdown to switch NORMAL/RISK/INCIDENT | Mock |

### 6.5 Type Definitions (src/api/types.ts)

These TypeScript types match the frozen backend contracts:

**RuntimeStatus (D2.2 - D2 owns this schema)**
```typescript
export interface RuntimeStatus {
  fleet_halted: boolean;
  agent_revoked: boolean;
  available: boolean;
}
```

**AgentStatus (D1.7 - D1 owns, includes D2 runtime status)**
```typescript
export interface AgentStatus {
  id: string;
  name: string;
  permissions: string[];
  max_single_amount: number;
  daily_cap: number;
  remaining_budget: number;
  status: 'active' | 'revoked';
  fleet_halted: boolean; // from RuntimeStatus
}
```

**IntegrityStatus (D2.9 - D2 owns)**
```typescript
export interface IntegrityStatus {
  status: 'UNKNOWN' | 'VERIFIED' | 'FAILED';
  last_verified: string | null;
  total_records: number;
  break_at: number | null;          // Index where chain broke
  expected_hash: string | null;    // Expected hash at break point
  actual_hash: string | null;       // Actual hash (mismatch if failed)
}
```

### 6.6 How Mock-to-Real Integration Works

**Current (Phase 1):**
```typescript
// src/api/index.ts
export const api: GovernanceApi = mockApi;
```

**When D2 endpoints are ready:**
1. Implement `src/api/real.ts` with fetch-based client
2. Change one line in `src/api/index.ts`:
```typescript
export const api: GovernanceApi = realApi; // Was: mockApi
```

**No other frontend changes needed** — all components use `api` through the `GovernanceApi` interface.

### 6.7 Mock Data Behavior

**Scenarios (controlled by ScenarioSelector):**
- `NORMAL`: All agents active, normal activity, integrity verified
- `RISK`: Agent C near spend cap, some denials
- `INCIDENT`: Agent B revoked, integrity verification fails at record 424

**Deterministic mock state (src/api/mocks.ts):**
- 3 base agents: Agent A (refund bot), Agent B (limit adjuster), Agent C (card replacement)
- In-memory state: agents, activity feed, integrity status
- Fleet halt updates all agent statuses to `FLEET_HALTED`
- Revoke/restore update individual agent status
- Activity feed tracks all events (decisions, halt/resume, revoke/restore)

### 6.8 Responsive Design

- **Desktop (>= 1280px):** Agents and Activity side-by-side (2-column grid)
- **Tablet (768px - 1279px):** Vertically stacked, still functional
- **Mobile (< 768px):** Warning banner displayed, not officially supported

### 6.9 Backend Integration Requirements

When D2 implements these endpoints, the frontend will call:

| D2 Endpoint | Frontend Use |
|-------------|--------------|
| `GET /fleet/state` | `getFleetState()` - FleetStatusCard |
| `POST /fleet/halt` | `haltFleet()` - FleetHaltModal |
| `POST /fleet/resume` | `resumeFleet()` - FleetHaltModal |
| `POST /agents/{id}/revoke` | `revokeAgent()` - AgentDrawer |
| `POST /agents/{id}/restore` | `restoreAgent()` - AgentDrawer |
| `GET /audit/feed?limit=N` | `getActivityFeed()` - ActivityFeedCard |
| `GET /audit/integrity` | `getIntegrityStatus()` - AuditIntegrityCard |
| `POST /audit/verify-chain` | `verifyChain()` - AuditIntegrityCard |

**D1-owned endpoints (frontend also calls):**
| D1 Endpoint | Frontend Use |
|-------------|--------------|
| `GET /agents` | `getAgents()` - AgentsSection (includes D2 runtime status composed in) |

---

## 7. APIs Exposed by D2 (Backend)

*This section tracks D2 backend endpoints. See Section 6 for frontend status.*

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

**Additional endpoints expected by frontend (see Section 6.9):**
- `GET /fleet/state` - Fleet state for dashboard
- `GET /audit/integrity` - Current integrity status

---

## 8. What D2 Currently Needs From D1

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

## 9. Integration Checklist

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

## 10. Recent D2 Changes

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

### 2026-07-23: Frontend Dashboard Phase 1 (IMPLEMENTED / MOCK-BASED)

**Files created/modified:**
- `frontend/src/api/index.ts` - API export (mocks → real client swap point)
- `frontend/src/api/client.ts` - GovernanceApi interface (contracts)
- `frontend/src/api/mocks.ts` - Complete mock implementation with deterministic state
- `frontend/src/api/types.ts` - TypeScript types matching frozen contracts
- `frontend/src/components/fleet/` - FleetStatusCard, FleetHaltModal
- `frontend/src/components/agents/` - AgentsSection, AgentDrawer
- `frontend/src/components/activity/` - ActivityFeedCard
- `frontend/src/components/audit/` - AuditIntegrityCard, IntegrityResultModal
- `frontend/src/components/ui/` - Button, Modal, Toast, Loading, StatusBadge, ProgressBar
- `frontend/src/components/debug/` - ScenarioSelector (dev only)
- `frontend/src/hooks/usePolling.ts` - Live update polling hook
- `frontend/src/pages/Dashboard.tsx` - Main dashboard page
- `frontend/src/main.tsx` - React entry point
- `frontend/src/App.tsx` - Root component with error boundary
- `frontend/package.json` - Dependencies (React, TypeScript, Vite, TailwindCSS)
- `frontend/vite.config.ts` - Vite build configuration
- `frontend/tsconfig.json` - TypeScript configuration
- `frontend/tailwind.config.js` - TailwindCSS configuration
- `frontend/index.html` - HTML entry point
- `frontend/postcss.config.js` - PostCSS configuration

**What was implemented:**
- Complete responsive React dashboard with deterministic mock data
- Fleet status card with halt/resume controls (simulated)
- Agent list with status indicators and detail drawer
- Agent revoke/restore controls (simulated)
- Live activity feed showing recent decisions
- Audit integrity verification with result modal
- Scenario selector (NORMAL, RISK, INCIDENT) for demo scenarios
- Single API interface (`GovernanceApi`) for clean mock-to-real swap
- TypeScript types matching frozen backend contracts
- Responsive design (768px+ officially supported)
- Polling hook for live updates (2-second interval)
- Toast notifications for user feedback

**Mock behavior:**
- 3 base agents: Agent A (refund bot), Agent B (limit adjuster), Agent C (card replacement)
- In-memory state: agents, activity feed, integrity status
- Fleet halt updates all agents to `FLEET_HALTED` status
- Revoke/restore updates individual agent status
- Activity feed tracks all events (decisions, halt/resume, revoke/restore)
- Integrity verification simulates success (NORMAL/RISK) or failure (INCIDENT at record 424)

**Integration points documented:**
- `src/api/index.ts` line 13: Swap `mockApi` → `realApi` when backend ready
- `src/api/client.ts`: `GovernanceApi` interface defines all required endpoints
- Frontend expects D2 endpoints (see Section 6.9): GET/POST for fleet, agents, audit
- Frontend also calls D1 endpoint: GET /agents (composed with D2 runtime status)

**Integration status:** IMPLEMENTED / MOCK-BASED
- UI complete and functional with deterministic mock data
- No real backend integration yet
- When D2 implements endpoints, change ONE line in `src/api/index.ts`
- All components use `api` through `GovernanceApi` interface (no breaking changes)

**What is NOT real yet:**
- All data comes from `src/api/mocks.ts` (in-memory, browser session only)
- No actual HTTP requests to backend
- No real Redis or database interaction
- Revoke/restore/halt/resume are simulated (no state persistence)

---

## 11. Frozen Integration Contracts

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
