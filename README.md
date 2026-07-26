# Financial Agent Governance Layer

> **A real-time, deterministic governance, runtime safety, and cryptographic audit framework for AI Agents executing financial actions.**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0.0-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6.svg)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D.svg)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Executive Summary & Motivation

As Autonomous AI Agents transition from passive research assistants to active execution agents in enterprise environments (e.g., initiating refunds, managing travel bookings, adjusting loyalty reward points, ordering card replacements), financial institutions face unprecedented risks:
- **Runaway Agent Loops**: An agent trapped in a tool-use loop could exhaust credit limits or issue thousands of unauthorized transactions in seconds.
- **Policy Slippage & Prompt Injection**: An agent swayed by malicious context might bypass single-transaction threshold rules or invoke forbidden tools.
- **Audit Tampering & Non-Repudiation**: Traditional application logs can be altered or truncated, failing strict regulatory compliance (e.g., PCI-DSS, SOX).

**Financial Agent Governance Layer** resolves these challenges by inserting an immutable, fail-closed governance barrier between autonomous AI agents and core financial execution APIs. Every action is identity-verified, policy-checked, budget-reserved in sub-millisecond in-memory storage, and cryptographically anchored in a tamper-evident audit chain.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Agent Framework
        A[AI Agent / LLM Worker]
    end

    subgraph Governance Gateway [FastAPI Backend - Port 8000]
        B[POST /action-request]
        C{1. Identity Verification}
        D{2. Runtime Safety Check}
        E{3. Policy Engine}
        F{4. Atomic Spend Cap}
        G[5. Cryptographic Hash Chain Write]
    end

    subgraph In-Memory State [Redis 7]
        H[Fleet Halt State: fleet:halted]
        I[Agent Status: agent:id:status]
        J[Atomic Budget Counter: agent:id:remaining_budget]
    end

    subgraph Relational Persistence [PostgreSQL 16]
        K[(Agent Metadata)]
        L[(Audit Log Hash Chain)]
    end

    subgraph Operator Dashboard [React + Vite Frontend - Port 5173]
        M[Live Dashboard & Fleet Control Switch]
    end

    A -->|X-Agent-Id & X-Agent-Secret| B
    B --> C
    C -->|HMAC Constant Time| K
    C -->|Pass| D
    D -->|Read State| H
    D -->|Read Status| I
    D -->|Pass| E
    E -->|OPA Rego / Python Fallback| E
    E -->|Allowed| F
    F -->|DECRBY Cents| J
    F -->|Reserved| G
    G -->|Advisory Lock & SHA-256| L
    G -->|Response 200 OK| A
    M -->|Real-time Poll & Control Actions| B
```

### Architectural Components

1. **Frontend (Operator Dashboard)**: Built with React 18, TypeScript, Vite, and Tailwind CSS. Features real-time state synchronization, interactive agent management drawers, fleet kill switches, live action test runners, and cryptographic chain verification indicators.
2. **Backend (Governance Gateway)**: Built with Python 3.12 and FastAPI. Implements a multi-stage, fail-closed execution pipeline (`Identity → Runtime State → Policy Engine → Spend Cap → Audit Logger`).
3. **PostgreSQL Database**: Primary relational store for agent identity, permissions, spending caps, and the append-only `audit_log` table equipped with SHA-256 cryptographic linkage.
4. **Redis In-Memory State**: Low-latency cache providing sub-millisecond atomic counter management (`DECRBY`/`INCRBY`) for spend caps, as well as immediate flag lookups for runtime revocations and fleet-wide halts.
5. **Policy Engine**: Open Policy Agent (OPA) integration running Rego rules with a built-in Python fallback evaluator to guarantee high-availability policy decisions.
6. **Cryptographic Audit Chain**: Ensures log integrity using PostgreSQL advisory locks (`pg_advisory_xact_lock`) for strict write serialization and SHA-256 hash link calculations (`hash = SHA256(canonical_json + prev_hash)`).
7. **Demo Infrastructure**: Deterministic database seed script (`demo/seed.py`) and automated 6-beat scenario runner (`demo/runner.py`) demonstrating compliant actions, policy violations, agent revocations, runaway requests, fleet halts, and audit verification.

---

## ⭐ Feature List

- 🔒 **Identity Verification**: Timing-safe credential comparison using `hmac.compare_digest()` to prevent timing side-channel attacks during agent lookup and authentication.
- 🛡️ **Policy Enforcement**: Fine-grained capability verification checking whether requested action types match agent permissions and respecting maximum per-transaction amounts.
- 💰 **Atomic Spend Caps**: Double-entry budget tracking in Redis stored as integer cents to eliminate floating-point rounding errors. Utilizes compensating increments (`INCRBY`) and budget rollbacks in case downstream audit operations fail.
- 🚫 **Runtime Revocation**: Per-agent runtime status control capable of instantaneously revoking single agents without affecting the rest of the fleet.
- 🛑 **Fleet Halt (Kill Switch)**: Global emergency break that blocks all incoming agent action requests across the entire infrastructure in sub-millisecond speed.
- 📜 **Tamper-Evident Hash Chain**: Every governance decision (both `allow` and `deny`) is appended to an immutable chain linked cryptographically to the preceding record's SHA-256 hash.
- 🔍 **Chain Integrity Verification**: Dedicated endpoint and UI card to verify the full cryptographic sequence from genesis to the latest record, pinpointing exact row index breaks if data tampering occurs.
- 📊 **Live Operator Dashboard**: High-density UI displaying real-time metrics, fleet state, agent status drawers, action feeds, and live test action triggers.
- 🧪 **Automated Demo Runner**: Scripted 6-beat workflow that executes end-to-end verification of all safety controls.

---

## 🛠️ Technology Stack

| Domain | Technology | Version / Specification |
| :--- | :--- | :--- |
| **Frontend** | React, TypeScript, Vite, Tailwind CSS, Lucide Icons | React 18.3, TypeScript 5.5, Vite 5.3 |
| **Backend** | Python, FastAPI, Uvicorn, Pydantic v2 | Python 3.12, FastAPI 1.0, Pydantic 2.x |
| **Database & ORM** | PostgreSQL, SQLAlchemy, Alembic | PostgreSQL 16, SQLAlchemy 2.0 |
| **Cache & State** | Redis | Redis 7.0 |
| **Policy Engine** | Open Policy Agent (OPA) / Rego | Native OPA / Python Fallback |
| **Testing** | Pytest, Vitest, Testing Library | Pytest 9.x, Vitest 2.x |
| **Containerization** | Docker, Docker Compose | Docker Compose v2 |

---

## 📂 Repository Structure

```
Agent-Governer-Amex/
├── alembic/                  # Database migration scripts & history
│   └── versions/             # DB schema migration definitions
├── db/                       # Database connections & SQLAlchemy models
│   ├── base.py               # Engine & SessionLocal setup
│   └── models/               # Agent & AuditLog ORM models
├── demo/                     # Demonstration infrastructure & test scenarios
│   ├── agents.py             # Demo HTTP client wrapper for agents
│   ├── runner.py             # Automated 6-Beat Demo Execution Script
│   └── seed.py               # Deterministic environment reset & seed script
├── frontend/                 # React + TypeScript + Vite Dashboard
│   ├── src/
│   │   ├── api/              # API fetch client & type definitions
│   │   ├── components/       # UI Cards, Agent Drawers, Modals & Headers
│   │   ├── hooks/            # Custom data fetching & polling hooks
│   │   ├── pages/            # Dashboard main view
│   │   └── __tests__/        # Vitest component test suites
│   ├── package.json          # Frontend npm dependencies & scripts
│   └── vite.config.ts        # Vite configuration & dev server proxy
├── middleware/               # FastAPI custom middleware (Timing headers)
├── policy/                   # OPA Rego policy rules & client evaluator
│   ├── rego/policy.rego      # Rego rules definition
│   ├── opa_client.py         # OPA HTTP client & evaluator
│   └── fallback.py           # Native Python fallback policy engine
├── routers/                  # FastAPI router modules
│   ├── action.py             # Gateway /action-request orchestration
│   ├── audit.py              # Audit logs & hash chain verification APIs
│   ├── fleet.py              # Fleet halt & resume switch APIs
│   ├── policies.py           # Policy rules querying APIs
│   └── runtime.py            # Agent listing & runtime revocation APIs
├── schemas/                  # Pydantic schemas for requests/responses
├── scripts/                  # Helper & setup scripts
│   ├── agent_lookup.py       # D1 Agent lookup adapter
│   └── seed_agent.py         # Single agent seed helper script
├── services/                 # Core Governance Domain Services
│   ├── hash_chain.py         # SHA-256 Audit log writer & chain verifier
│   ├── identity.py           # Timing-safe HMAC identity verification
│   ├── redis_client.py       # Redis connection factory
│   ├── runtime_state.py      # Runtime status & fleet state checking
│   └── spend.py              # Atomic spend reservation & budget management
├── tests/                    # Backend Pytest unit & integration test suites
├── docker-compose.yml        # Docker setup for PostgreSQL & Redis
├── main.py                   # FastAPI Application Bootstrap & Wiring
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
└── README.md                 # Project documentation
```

---

## ⚡ Installation & Setup

### Prerequisites
- **Python**: 3.12 or later
- **Node.js**: v18 or later (npm v9+)
- **Docker & Docker Compose**: Installed and running

### Step 1: Clone Repository
```bash
git clone https://github.com/your-org/Agent-Governer-Amex.git
cd Agent-Governer-Amex
```

### Step 2: Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Ensure your `.env` contains:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/governance
REDIS_URL=redis://localhost:6379/0
```

### Step 3: Backend Virtual Environment & Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 4: Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

---

## 🚀 Running the Project

### 1. Start Support Infrastructure (PostgreSQL & Redis)
```bash
docker compose up -d
```
*Verify containers are healthy with `docker compose ps`.*

### 2. Apply Database Migrations
```bash
source .venv/bin/activate
alembic upgrade head
```

### 3. Start Backend Governance Server
```bash
source .venv/bin/activate
PYTHONPATH=. uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
*Backend API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.*

### 4. Start Operator Dashboard Frontend
In a new terminal window:
```bash
cd frontend
npm run dev
```
*Frontend application will be accessible at `http://localhost:5173`.*

---

## 🎬 Running the Demo

The repository includes a self-contained, automated demo suite that populates the environment with deterministic agents and executes a 6-beat governance scenario.

### 1. Seed the Environment
Resets PostgreSQL tables, initializes Redis counters, and seeds 4 standard demo agents:
```bash
PYTHONPATH=. python -m demo.seed
```

### 2. Run the Automated Demo Script
Ensure the backend server is running (`http://localhost:8000`), then run:
```bash
PYTHONPATH=. python -m demo.runner
```

### 3. Interactive Web Dashboard
Open `http://localhost:5173` in your browser while running the backend.
- View real-time active agents, remaining daily budgets, and spend utilization bars.
- Click any agent card to open the **Agent Detail Drawer**.
- Use the **Test Agent Action** form inside the drawer to trigger live requests.
- Trigger **Halt Fleet** or **Revoke Agent** to observe instantaneous 403 Forbidden responses.
- Click **Verify Hash Chain** to execute full SHA-256 audit chain validation.

---

## 📖 Manual Demo Walkthrough (6-Beat Scenario)

| Beat | Scenario | Action / Endpoint | Expected Governance Result |
| :---: | :--- | :--- | :--- |
| **Beat 1** | **Compliant Refund** | Agent A requests `$100.00` refund (`max: $500.00`) | ✅ **ALLOWED** (200 OK). Budget decremented to `$1,900.00`. Audit logged with SHA-256 hash. |
| **Beat 2** | **Policy Limit Violation** | Agent B requests `$1,000.00` travel booking (`max: $100.00`) | ❌ **DENIED** (200 OK with `decision: deny`). Reason: `AMOUNT_EXCEEDS_LIMIT`. No budget consumed. |
| **Beat 3** | **Agent Revocation** | Operator revokes Agent B (`POST /agents/{id}/revoke`). Agent B requests `$50.00`. | 🛑 **BLOCKED** (403 Forbidden). Reason: `AGENT_REVOKED`. Instant runtime kill switch enforced. |
| **Beat 4** | **Rapid In-Policy Requests** | Agent C issues 3 consecutive `$50.00` points adjustments | ✅ **ALLOWED** (200 OK). Atomic Redis DECRBY guarantees race-safe budget reservation. |
| **Beat 5** | **Fleet Kill Switch** | Operator triggers global halt (`POST /fleet/halt`). Agent A requests `$50.00`. | ⛔ **BLOCKED** (403 Forbidden). Reason: `FLEET_HALTED`. All agents instantly frozen. |
| **Beat 6** | **Audit Chain Integrity** | Trigger verification (`POST /audit/verify-chain`) | 🔒 **VERIFIED** (`intact: true`). All SHA-256 hash links checked sequentially. |

---

## 🧪 Testing

### Backend Unit & Integration Tests
Run all 170+ backend test cases covering identity verification, policy fallback, atomic spend reservation, advisory locking, and API endpoints:
```bash
source .venv/bin/activate
PYTHONPATH=. pytest
```

### Frontend Unit & Component Tests
Run frontend test suites with Vitest:
```bash
cd frontend
npm run test:run
```

---

## 🔌 API Overview

### Governance & Actions
- `POST /action-request`: Gateway endpoint for agent action evaluation. Requires `X-Agent-Id` and `X-Agent-Secret` headers.

### Fleet & Runtime Control
- `GET /fleet/state`: Get global fleet halt status.
- `POST /fleet/halt`: Immediately freeze all fleet operations.
- `POST /fleet/resume`: Resume normal fleet operations.
- `GET /agents`: List all registered agents with current remaining budgets and statuses.
- `GET /agents/{agent_id}/runtime-status`: Fetch runtime status of a specific agent.
- `POST /agents/{agent_id}/revoke`: Instantly revoke an agent.
- `POST /agents/{agent_id}/restore`: Restore a revoked agent to active status.

### Audit & Cryptographic Integrity
- `GET /audit/feed`: Stream recent audit log records for live feeds.
- `GET /audit/log`: Filterable audit log endpoint.
- `POST /audit/verify-chain`: Perform full cryptographic hash-chain verification.
- `GET /audit/integrity`: Retrieve current hash chain integrity status.

---

## 🖼️ Screenshots

*(Placeholders for release screenshots)*

| Dashboard Overview | Agent Detail & Action Trigger | Audit Chain Verification |
| :---: | :---: | :---: |
| `![Dashboard Overview](docs/screenshots/dashboard.png)` | `![Agent Drawer](docs/screenshots/agent_drawer.png)` | `![Audit Verification](docs/screenshots/audit_verify.png)` |

---

## 🔮 Future Improvements

- 🔑 **Hardware Security Module (HSM) Integration**: Asymmetric signing of audit records using KMS/HSM keys for zero-trust public non-repudiation.
- 📡 **Server-Sent Events (SSE) / WebSocket Push**: Real-time push stream for audit logs and fleet status updates to eliminate UI polling.
- 🌐 **Multi-Tenant Policy Scoping**: Role-based access control (RBAC) and dynamic tenant-scoped policy bundle loading.
- 🔄 **Redis Cluster & High-Availability Persistence**: Distributed lock orchestration across multi-region Redis deployments.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
