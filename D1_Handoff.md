# D1 → D2 Handoff Guide

**For:** Developer 2
**Purpose:** What D1 has built so far, what's ready for you to use, and what you need to do to integrate.

---

## 1. Quick Status

| Feature | Status | D2 Action Needed |
|---------|--------|-------------------|
| `agents` table + migration | READY FOR INTEGRATION | Set your `audit_log` migration's `down_revision` to `09ee32e4e00a` |
| Postgres + Redis (docker-compose) | READY FOR INTEGRATION | Use the same `docker-compose.yml` — don't spin up your own instances |
| `AgentLookup` implementation | INTEGRATED | Wired in main.py, tested with real Postgres |
| `RedisClient` implementation | INTEGRATED | Wired in main.py, tested with real Redis |
| `/action-request` orchestration | NOT STARTED | Will call your `verify_identity()` / `check_runtime_status()` once both are wired |
| OPA policy check | NOT STARTED | — |
| Spend caps | NOT STARTED | — |

---

## 2. What's Been Built

### `docker-compose.yml` (repo root)
Spins up **Postgres** (port `5432`) and **Redis** (port `6379`) as containers. This is the shared local dev environment — please use this instead of installing Postgres/Redis natively, so we're both running identical setups.

```bash
docker compose up -d
docker compose ps   # confirm both are "Up"
```

### `.env.example` (repo root)
Copy this to `.env` locally:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/governance
REDIS_URL=redis://localhost:6379/0
```
`.env` itself is gitignored — never committed.

### `db/base.py`
Declares `Base` (SQLAlchemy declarative base — every model inherits from this), `engine`, `SessionLocal`, and a `get_db()` FastAPI dependency. If you need a DB session in your own code, import `SessionLocal` from here rather than creating your own engine.

### `db/models/agent.py` — the `agents` table
```python
class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    permissions = Column(JSONB, nullable=False, default=list)
    max_single_amount = Column(Numeric(12, 2), nullable=False)
    daily_cap = Column(Numeric(12, 2), nullable=False)
    status = Column(String, nullable=False, default="active")  # "active" | "revoked" (persisted record)
    shared_secret = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Note on `status`:** this column is the *persisted* record only — used to re-seed Redis on restart. Your live `agent:{id}:status` key in Redis remains the actual source of truth `check_runtime_status()` reads. Don't treat this column as authoritative at request time.

### Migration `09ee32e4e00a_create_agents_table.py`
Already applied (`alembic upgrade head` run, table exists in Postgres). **`down_revision = None`** since it's first in the chain.

### `scripts/seed_agent.py`
Inserts one test agent for local testing:
- `permissions: ["refund", "card_replacement"]`
- `max_single_amount: 1000.00`, `daily_cap: 5000.00`
- `status: "active"`, `shared_secret: "test-secret-123"`

Run with `python -m scripts.seed_agent`. Useful if you want a real agent row to test your revoke/restore endpoints or audit FK against.

### `services/agent_lookup.py` — `AgentLookup` implementation
```python
class D1AgentLookup(AgentLookup):
    def get_agent_secret(self, agent_id: str) -> str | None:
        db = SessionLocal()
        try:
            agent = db.query(Agent).filter_by(id=agent_id).first()
            return agent.shared_secret if agent else None
        finally:
            db.close()
```
This is what gets passed to your `set_agent_lookup()` at app startup. Not yet wired into a running app (no `main.py` orchestration exists yet) — currently only tested in isolation.

---

## 3. Critical Info You Need

- **Migration revision ID is `09ee32e4e00a`, not a placeholder like `"0001"`.** Your `audit_log` migration must set `down_revision = "09ee32e4e00a"` exactly, or the FK dependency chain breaks.
- **`shared_secret` lives on the `agents` table**, populated per-agent. Your `verify_identity()` gets it via `AgentLookup.get_agent_secret(agent_id)`, not by querying the table directly — don't add a direct DB dependency on your side, go through the protocol as agreed.
- **`agents.status` vs Redis `agent:{id}:status`:** two separate things on purpose — Postgres is the durable record (survives container restarts), Redis is the live value your `check_runtime_status()` reads. When you build revoke/restore, you'll be writing to Redis; the Postgres column is not something you need to touch for that logic to work, though we may want a startup script later that seeds Redis from Postgres on boot (not built yet — flagging for later).

---

## 4. What I Need From You

- **Push/merge your `services/identity.py` branch** so I can wire `AgentLookup` into a real `set_agent_lookup()` call and test `/action-request`'s identity step end-to-end. I did a temporary local merge to sanity-check it works, but haven't merged for real yet.
- Once your `audit_log` migration is ready, ping me before you merge — I want to confirm the FK resolves cleanly against `09ee32e4e00a` on a fresh `alembic upgrade head` run.

---

## 5. Not Started Yet (in progress, in this order)

1. `RedisClient` implementation for your `check_runtime_status()`
2. `/action-request` endpoint wiring identity → runtime status → policy → spend cap → decision → audit
3. OPA/Rego policy check + Python fallback
4. Spend cap logic (atomic Redis `DECRBY`)
5. Policy config API + spend reset API
6. Tests + latency middleware