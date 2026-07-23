# PRD: Governance Layer for Financial Agents
**Amex CodeStop 2026 — Phase 1 Submission (Hybrid v2)**

> This version merges the original build-plan PRD with the strongest, cheapest additions from the deep-research doc. Nothing here requires a new language, a new SDK, or more than ~1–2 extra hours of work per addition. Anything from the research doc that would meaningfully risk the timeline (Go rewrite, Cedar, JWT/OAuth2.1, Prometheus/Grafana, real hash-chain infra, HITL) is explicitly named and deferred to Phase 2.

---

## 1. Problem Statement

Banks are moving toward fleets of autonomous AI agents handling real financial actions (refunds, credit limit changes, approvals). Without a control layer, one misbehaving or compromised agent can cause uncontrolled financial exposure with no way to detect it in real time or stop it fast. This project builds that control layer: a policy-enforced gateway that every agent action must pass through, with live spend tracking, instant revocation, and a full audit trail.

**We are not building smarter agents. We are building the infrastructure that makes any agent safe to deploy.**

---

## 2. Goals for Phase 1

1. Deploy a **working, publicly reachable demo** — not a slide deck describing one.
2. Prove all five required capabilities live: **permissions, spend caps, per-agent revocation, fleet-wide kill switch, audit log.**
3. Run a scripted 3-agent scenario, under 2 minutes, no narration needed, that visibly demonstrates *all five* capabilities — including per-agent revocation, which the original demo script omitted.
4. Keep agent logic trivial — all engineering effort goes into the policy engine, real-time enforcement, and dashboard.
5. Ship a small number of "credibility" details (fail-closed behavior, tamper-evident logging, atomicity) cheaply rather than skipping them entirely — these are what separate a toy demo from an infrastructure pitch, and doc 2's research confirms they're the details judges look for.

## 3. Non-Goals (explicitly out of scope for Phase 1 — and explicitly *not* revisited from doc 2)

- **Go rewrite of the gateway.** FastAPI stays. Go is a real production choice but a language switch mid-week is pure risk with no demo-visible payoff.
- **AWS Cedar as the policy engine.** OPA/Rego (with a plain-Python conditional fallback) stays as specified in the original PRD. Cedar's claimed latency advantage is not judged in a hackathon demo, and adopting a new SDK this week is not worth it.
- **JWT / OAuth 2.1 identity.** A static per-agent ID + shared-secret header is sufficient to demonstrate "identity is checked" (see §5.0, new). Full token infrastructure is Phase 2.
- Real LLM-driven agents (agents remain scripted action generators)
- Real banking backend integration
- Multi-tenant / multi-bank support
- User-facing (card member) UI — operator-facing only
- Horizontal scaling / production-grade infra — single-instance deployment is fine
- Prometheus/Grafana observability stack — not needed to prove the five required capabilities
- Human-in-the-loop approval workflow — good Phase 2 story, not required this week
- Full cryptographic hash-chain infrastructure (KMS-backed signing, external anchoring) — see §5.4 for the lightweight version we *are* doing

---

## 4. System Architecture

Unchanged from the original PRD, with one addition (dotted): a lightweight identity check at the gateway edge.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Agent A     │     │  Agent B     │     │  Agent C     │
│ (well-       │     │ (violator)   │     │ (runaway)    │
│  behaved)    │     │              │     │              │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │  POST /action-request (agent_id + shared secret header)
       └───────────────┬───────────────┬─────────┘
                        ▼
              ┌───────────────────┐
              │   Gateway API      │  (FastAPI)
              │  - verify agent_id/secret (new, cheap)
              │  - check fleet_halted flag FIRST
              │  - check agent revoked status NEXT
              │  - fetch agent state│
              └─────────┬──────────┘
                        ▼
              ┌───────────────────┐
              │   Policy Engine    │  (OPA/Rego, Python-conditional fallback)
              │  - permission check│
              │  - spend cap check │
              └─────────┬──────────┘
                 allow ─┴─ deny
                        ▼
        ┌───────────────────────────────┐
        │  Redis (live spend counters,  │
        │  agent status: active/revoked,│
        │  fleet_halted flag)           │
        └───────────────┬───────────────┘
                        ▼
        ┌───────────────────────────────┐
        │  Postgres (append-only audit  │
        │  log + lightweight hash chain)│
        └───────────────┬───────────────┘
                        ▼
              ┌───────────────────┐
              │  Operator Dashboard│ (React)
              │  - live activity   │
              │  - per-agent config│
              │  - revoke / kill   │
              │  - audit log view  │
              │  - tamper-check btn│ (new)
              └───────────────────┘
```

**Design principle (unchanged):** every agent action is a single HTTP call to the Gateway. Nothing an agent does reaches a "real" system without first clearing policy. This makes the demo trivially provable.

**Check order at the gateway (important, and worth stating explicitly in the writeup):** identity → fleet kill switch → per-agent revocation → policy engine (permissions + spend cap). Kill switch and revocation are checked *before* the policy engine runs, not after — that's what makes them "instant" regardless of policy complexity, and it's a detail worth calling out to judges.

---

## 5. Core Components

### 5.0 Lightweight Identity Check (new, small addition)

- Each agent is issued a static `agent_id` and a shared-secret header value at registration time (stored in the `agents` table, not rotated, not expiring).
- Gateway rejects any request with a missing/incorrect secret before it reaches policy evaluation.
- This is **not** a real auth system — say so plainly in the writeup: *"Phase 1 uses static per-agent credentials to demonstrate identity verification as a gate; Phase 2 would replace this with short-lived JWTs issued via OAuth 2.1 client-credentials flow."*
- Cost: ~30–60 minutes. Payoff: closes an obvious gap a judge would ask about ("how do you know it's really Agent A?"), without adding real engineering risk.

### 5.1 Permission Model
*(unchanged from original PRD)*
- Each agent has a registered **policy profile**: a list of allowed action types (`refund`, `limit_adjustment`, `card_replacement`, etc.) and per-action constraints (e.g., max single-transaction amount).
- Stored as structured config (JSON/YAML) loaded into OPA as data — editing this config live re-evaluates without a redeploy.
- Rego policy example (conceptual):
  - `allow { input.action in agent.permissions; input.amount <= agent.max_single_amount }`

### 5.2 Dynamic Spend Caps
*(unchanged from original PRD, with one clarifying addition)*
- Each agent has a `daily_cap` and a `remaining_budget` tracked in Redis as an atomic counter.
- Every allowed action decrements the counter **before** the action is confirmed to the agent, using Redis `DECRBY` with a post-check; if the result goes negative, the action is denied and the amount is added back (compensating decrement). Because each Redis command is atomic, there is no window where two concurrent requests can both read a stale "sufficient balance" — this is worth one explicit sentence in the writeup so judges don't mistake it for a naive check-then-act race.
- If a request would push spend past the cap, the request is denied regardless of individual permission.
- Counters reset via a manual "reset day" button on the dashboard (not a real 24hr wait).

### 5.3 Revocation & Emergency Stop
*(unchanged from original PRD — but see §6, demo script now explicitly exercises both)*
- **Per-agent revoke**: dashboard button flips agent status to `revoked` in Redis. Gateway checks this on every request — revoked agents denied instantly.
- **Fleet-wide kill switch**: single dashboard action sets a global `fleet_halted` flag in Redis. Checked first, before identity/policy — cheapest possible check, near-instant even under load.
- Both actions are themselves logged to the audit trail (who/what triggered it, when).
- **Fail-closed behavior (new, cheap, high credibility):** if the Gateway cannot reach Redis (connection error or timeout), it denies the request rather than allowing it. One `try/except` around the Redis calls. This directly answers "what happens if your control plane goes down?" — a question judges are likely to ask given the framing of this challenge — without needing any new infrastructure.

### 5.4 Audit Log
- Every gateway decision (allow or deny) is written to Postgres as an append-only row: `timestamp, agent_id, action_type, amount, decision, reason, policy_version`.
- **Lightweight hash chain (upgraded from "mention as Phase 2"):** add two columns, `prev_hash` and `hash`. On insert, compute `SHA256(canonical_json(row) + prev_hash_of_last_row)`. This is a small, self-contained addition (~1–2 hours: one Python function + two columns) and it turns "immutable-in-spirit" into something you can actually demonstrate breaking.
  - **Canonicalization matters**: sort keys alphabetically and strip whitespace before hashing, or the verification step will produce false positives. This is the one real gotcha the research doc flags, and it's worth heeding since it costs nothing to do right the first time.
  - DB-level immutability (revoked UPDATE/DELETE grants) stays as the secondary safety net, as in the original PRD.
  - **Do not** attempt KMS-backed signing, external anchoring, or a real blockchain — that's genuinely Phase 2 scope and adds no demo value over a hash chain.
- **Tamper-check demo button (new, dashboard):** a small "Verify Chain Integrity" action that recomputes hashes top-to-bottom and reports either "✅ chain intact" or "❌ break detected at row N." This turns the audit log from a passive table into an active proof point, and it's cheap to build since the hashing function already exists from the write path.
- Dashboard audit log view: filterable by agent, action type, decision, time range.

### 5.5 Operator Dashboard
*(unchanged from original PRD, plus one addition)*
- **Live activity feed** — poll every 1–2s, color-coded allow/deny.
- **Policy config panel** — edit an agent's permissions/spend cap, effective on next request.
- **Revoke / Kill Switch controls** — prominent, single-click, confirmation modal.
- **Audit log table** — searchable history.
- **Verify Chain Integrity button** — see §5.4.

---

## 6. Demo Scenario (Phase 1 Submission Video) — Revised

The original 3-agent table only exercised policy denial and the fleet kill switch. The problem statement explicitly asks for **"one agent or the entire fleet"** — the old script never showed single-agent revocation. Fixed below, still ~90–110 seconds.

| Beat | Behavior | What it proves |
|---|---|---|
| **1. Agent A — Compliant** | Issues normal in-policy refunds within cap | Baseline: system doesn't just block everything |
| **2. Agent B — Violator** | Attempts an out-of-scope action and an over-cap refund | Permission model + spend cap enforcement, live deny on dashboard |
| **3. Operator revokes Agent B specifically** | Operator clicks "Revoke" on Agent B only | **Per-agent revocation** — Agent B's next request is denied instantly while A and C keep running unaffected. This is the missing beat from the original script. |
| **4. Agent C — Runaway** | Rapid-fires legitimate-looking actions to simulate a compromised agent | Justifies the kill switch |
| **5. Operator hits fleet kill switch** | Single click | **Fleet-wide halt** — all agents (including still-active A) stop instantly, dashboard reflects it live |
| **6. Close on audit log + integrity check** | Filter the log to show the full trace; click "Verify Chain Integrity" | Full traceability *and* a live tamper-evidence proof, not just a static table |

Total added time over the original script: roughly 15–20 seconds (one revoke click + one integrity-check click). Worth it — it now visibly proves all five required capabilities instead of three.

---

## 7. Tech Stack Decisions

Unchanged from the original PRD. Explicitly **not** adopting doc 2's "recommended MVP stack" (Go, Cedar, JWT/OAuth2.1) for Phase 1 — those are named as considered-and-deferred, see §3.

| Layer | Choice | Why |
|---|---|---|
| Policy engine | **OPA (Rego)**, plain-Python fallback if integration stalls | Purpose-built, credible to cite; fallback protects the timeline |
| Gateway backend | **FastAPI (Python)** | Fastest to iterate on for a hackathon |
| Live state | **Redis** | Atomic counters, instant status checks, fail-closed on outage |
| Audit storage | **Postgres** | Durable, queryable, now with lightweight hash chain |
| Dashboard | **React** | Fast to build a live-updating UI; polling is fine |
| Identity | **Static agent_id + shared secret** | Demonstrates the check exists without building real auth this week |
| Deployment | **Single-VM or Railway/Render style PaaS** | Live and reachable beats infra sophistication |

---

## 8. Data Model (minimum viable, updated)

**agents**: `id, name, permissions (jsonb), max_single_amount, daily_cap, status (active/revoked), shared_secret`
**audit_log**: `id, timestamp, agent_id, action_type, amount, decision, reason, policy_version, prev_hash, hash`
**fleet_state** (Redis): `fleet_halted: bool`
**spend_state** (Redis): `agent:{id}:remaining_budget`

Changes from original: `shared_secret` added to `agents`; `prev_hash`/`hash` added to `audit_log`.

---

## 9. Success Metrics

- **Policy enforcement accuracy**: 100% of scripted violation attempts correctly denied (test with a fixed suite before recording demo)
- **Latency**: gateway decision time under ~100ms per request (measured, not assumed — cite the actual number)
- **Kill switch propagation time**: measured time from click to all agents receiving a deny
- **Per-agent revocation propagation time** *(new)*: same measurement, for the single-agent case — cheap to capture alongside the fleet-wide number and directly answers the "one agent or the fleet" requirement with data instead of just a demo clip
- **Audit completeness**: every request has a corresponding log row (`requests sent == log rows written`)
- **Audit integrity** *(new)*: run the adversarial test — manually alter one historical row via raw SQL, run the Verify Chain Integrity check, confirm it flags the exact row. Report this as a measured result, same spirit as the latency number.

---

## 10. Build Sequence — 6 Build Days + 1 Buffer Day

The original PRD deliberately avoided a fixed timeline. With a 7-day window, 6 days are allocated to actual build/demo/writeup work, and **Day 7 is held entirely in reserve** — no new work is scheduled against it. That's deliberate: something in a week-long build always breaks (a dependency, a deploy, a flaky demo run), and having a genuinely empty day to absorb that is worth more than squeezing extra polish into Day 6.

| Day | Focus | Notes |
|---|---|---|
| **1** | Data model (Postgres + Redis) + Gateway skeleton (`/action-request`, logs everything, no policy logic yet) + shared-secret identity check | Deploy to a public URL *today*, even bare-bones — never leave first deploy to the final hours |
| **2** | OPA integration: permission + spend cap rules, wired into gateway. Fallback to Python conditionals if OPA stalls by midday | Timebox OPA integration — don't let it eat into day 3 |
| **3** | Revocation + kill switch flags (checked first, before policy) + fail-closed Redis behavior | This is the highest-value day for the "instant" demo story |
| **4** | Audit log + lightweight hash chain + tamper-check function | Canonicalize JSON before hashing — see §5.4 gotcha |
| **5** | Three scripted agents + dashboard: activity feed → revoke/kill controls → policy config panel → audit log view (in that priority order) | Activity feed + kill switch matter most for the demo; policy config panel can be minimal |
| **6** | Full scenario end-to-end (§6 script), time every metric in §9, fix rough edges, redeploy, record demo video, write submission doc | This is now a full day — start the run-throughs early rather than late, so recording isn't the last thing attempted |
| **7 (Buffer)** | **No new work scheduled.** Reserved for: fixing anything that broke on Day 6, a re-record if the demo timing looked off, last-minute deploy issues, or finishing the writeup if it ran long | If Day 6 genuinely finishes clean with time to spare, this becomes optional polish — but plan as if you'll need it, because you probably will |

**Cut list — if behind schedule by end of Day 4, cut in this order** (moved up from Day 5 since Day 6 now carries more — video + writeup — and needs to start on time):
1. Live policy-config-editor UI → fall back to editing a JSON file and restarting the gateway (mention "live-editable in production" in the writeup, demo it as a config change + restart instead)
2. Tamper-check dashboard button → fall back to running the integrity check as a terminal script during the demo (still satisfies §9's audit-integrity metric, just less polished)
3. Per-agent daily-cap "reset day" button → hardcode a fresh cap per demo run instead
4. **Do not cut:** identity check, fail-closed Redis behavior, fleet kill switch, per-agent revocation, or the audit log itself — these are the five required capabilities plus the one cheap credibility add (fail-closed) that's most likely to come up in Q&A.

**Why Day 6 and not Day 7 absorbs video+writeup:** if recording or writing surfaces a bug (a metric that doesn't measure cleanly, a demo beat that doesn't read well on camera), you want a full untouched day left to fix it — not zero days.

---

## 11. Submission Checklist

- [ ] Project description document
- [ ] Presentation deck (architecture diagram, problem framing, demo screenshots)
- [ ] Deployed, publicly reachable link
- [ ] Demo video showing the full 6-beat scenario (§6) end-to-end, including per-agent revocation
- [ ] Repo link with README explaining setup/run instructions
- [ ] Explicit callouts in the writeup for all measured metrics in §9 (latency, enforcement accuracy, fleet kill-switch propagation, per-agent revocation propagation, audit integrity detection)
- [ ] One paragraph in the writeup naming what's deferred to Phase 2 (Go, Cedar, JWT/OAuth2.1, full hash-chain infra, HITL, Prometheus/Grafana) and why — shows the team scoped deliberately rather than ran out of time

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| OPA integration eats too much time | Timeboxed to Day 2; fallback is plain Python conditionals against the same config structure — mention OPA as intended choice even if Phase 1 uses the fallback |
| Live dashboard updates are finicky | Polling (1–2s interval) instead of WebSockets — invisible to judges in a short demo |
| Deployment breaks last-minute | Deploy Day 1, keep deploying incrementally |
| Demo timing looks scripted/fake | Slightly randomize agent action intervals so it reads as "live system," not "canned animation" |
| Hash-chain addition slips the schedule | It's scoped to ~1–2 hours specifically because it reuses the existing audit-write path; if it's taking longer than that, cut per the list in §10 rather than letting it bleed into Day 5+ |
| Team pulled toward doc 2's fuller stack (Go/Cedar/JWT) mid-week | This document is the single source of truth for Phase 1 scope — doc 2 is background reading and a Phase 2 roadmap, not the build target. Reference §3 and §7 if this comes up. |

---

## 13. What Changed From the Original PRD (summary for the team)

**Added:**
- Per-agent revocation beat in the demo script (was missing — the original only showed policy denial + fleet kill switch)
- Static identity check (agent_id + shared secret)
- Fail-closed behavior on Redis outage
- Lightweight hash-chained audit log + tamper-check verification
- Per-agent revocation propagation time as a measured metric
- Day-by-day timeline with an explicit cut list

**Explicitly not adopted from the research doc (and why):**
- Go gateway rewrite — no demo-visible payoff for the risk of a language switch this week
- AWS Cedar — OPA already satisfies the problem statement's named example; switching engines is not judged
- JWT/OAuth 2.1 — static credentials prove the same concept for a fraction of the effort
- Prometheus/Grafana, full hash-chain infra (KMS/anchoring), HITL workflow — genuine Phase 2 scope, correctly identified as such in the research doc itself
