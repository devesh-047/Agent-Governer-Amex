# Agent Governance Dashboard

Operator visibility and control interface for the Agent Governance System.

## What This Frontend Is

This is the **Phase 1 operator dashboard** for the Agent Governance System. It provides real-time visibility into agent fleet status, individual agent states, live activity feeds, and audit integrity controls.

**Phase 1 Status**: The dashboard currently runs in **mock mode** with deterministic scenarios. No real backend is required for manual testing. All data is simulated locally using three predefined scenarios (NORMAL, RISK, INCIDENT).

**Key Features**:
- Fleet-wide status monitoring with halt/resume controls
- Per-agent status, policy view, and revoke/restore controls
- Live activity feed with color-coded allow/deny decisions
- Audit log viewer with filtering
- Audit integrity verification with tamper detection

## Prerequisites

- **Node.js** v18 or higher (verified working with v20+)
- **npm** v9 or higher (comes with Node.js)

Verify installation:
```bash
node --version
npm --version
```

## Installation

From the repository root:

```bash
cd frontend
npm install
```

## Run Locally

Start the development server:

```bash
npm run dev
```

The dashboard will be available at: **http://localhost:3000** (or another port if 3000 is in use)

## Manual Testing Guide

### 1. Initial Dashboard Load
- Open http://localhost:3000
- Verify fleet status shows "RUNNING" (green)
- Confirm three agent cards are visible
- Check activity feed shows recent events

### 2. Inspect Agent Details
- Click **"VIEW DETAILS"** on any agent card
- Agent drawer slides in from the right
- Review agent information: policy, permissions, spend cap, status

### 3. Revoke an Agent
- In the agent drawer, click **"REVOKE AGENT"**
- Confirmation modal appears
- Click **"CONFIRM REVOKE"**
- Agent status changes to "REVOKED" (red)
- Activity feed shows revocation event
- Agent actions now show "DENIED" in activity feed

### 4. Restore the Agent
- With the same agent drawer open, click **"RESTORE AGENT"**
- Confirmation modal appears
- Click **"CONFIRM RESTORE"**
- Agent status returns to "ACTIVE" (green)
- Activity feed shows restoration event

### 5. Halt the Fleet
- In the fleet status section, click **"HALT FLEET"**
- Type **"HALT"** to confirm (safety measure)
- Click **"CONFIRM HALT"**
- Fleet status changes to "HALTED" (red)
- All agent cards show halted state
- "RESUME FLEET" button becomes available

### 6. Observe Fleet-Halted State
- While fleet is halted, monitoring continues
- Activity feed still updates (monitoring is independent)
- New agent requests would be denied (simulated in mock mode)

### 7. Resume the Fleet
- Click **"RESUME FLEET"**
- Type **"RESUME"** to confirm
- Click **"CONFIRM RESUME"**
- Fleet status returns to "RUNNING" (green)
- Operations return to normal

### 8. Audit Integrity Check
- Scroll to "Audit Integrity" section
- Click **"VERIFY INTEGRITY"** button
- System displays either:
  - Green checkmark: "Chain intact - all entries verified"
  - Red warning: "Break detected at entry N" with details

### 9. Test Different Scenarios
- In bottom-right corner, find scenario selector (dev mode only)
- Select **"NORMAL"** - steady operations, occasional denials
- Select **"RISK"** - elevated risk patterns, more denials
- Select **"INCIDENT"** - simulated security incident, rapid denials

## Mock Mode

The dashboard currently operates entirely on deterministic mock data:

**Three Scenarios**:
- **NORMAL**: Standard operations with mostly allowed actions
- **RISK**: Elevated suspicious activity, increased denials
- **INCIDENT**: Active security incident with rapid-fire denials

**Scenario Selector**: Located in bottom-right corner (development mode only). Switch between scenarios to see how the dashboard displays different operational states.

**No Backend Required**: All data is generated locally. The `src/api/mocks.ts` file provides deterministic responses that simulate the eventual backend API behavior.

## Available Commands

```bash
# Start development server (http://localhost:3000)
npm run dev

# Build for production
npm run build

# Type-check without building
npm run typecheck

# Preview production build
npm run preview

# Run automated tests
npm run test:run

# Run tests with UI
npm run test:ui

# Run tests in watch mode
npm run test
```

## Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts      # API client (will connect to real backend)
│   │   ├── mocks.ts       # Deterministic mock data
│   │   └── types.ts       # TypeScript types
│   ├── components/
│   │   ├── layout/        # Header, PageContainer
│   │   ├── ActivityFeed.tsx
│   │   ├── AgentCard.tsx
│   │   ├── AgentDrawer.tsx
│   │   ├── AuditLogTable.tsx
│   │   ├── FleetStatus.tsx
│   │   ├── IntegrityCheck.tsx
│   │   ├── RevokeRestoreControls.tsx
│   │   └── ...
│   ├── pages/
│   │   └── Dashboard.tsx  # Main dashboard page
│   ├── hooks/
│   │   └── useAgents.ts   # Agent state management
│   └── styles/
│       └── index.css      # Tailwind directives
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## Troubleshooting

### Dependencies not installed
**Error**: `Cannot find module 'react'` or similar

**Solution**:
```bash
rm -rf node_modules package-lock.json
npm install
```

### Port already in use
**Error**: `Port 3000 is already in use`

**Solution**: Either stop the process using port 3000 or edit `vite.config.ts` to use a different port.

### Type errors
**Error**: TypeScript errors in editor

**Solution**:
```bash
npm run typecheck
```

## Current Limitations

**Phase 1 Scope**:
- Backend APIs are not yet wired - all data is mocked
- Policy configuration panel is read-only display
- Mock actions simulate expected behavior without real enforcement
- Mobile responsiveness (<768px) is not a Phase 1 target
- Real-time WebSocket updates not yet implemented (polling only)

**Future Work**:
- Connect to real D1/D2 backend APIs
- Enable policy configuration edits
- Add WebSocket-based real-time updates
- Extend mobile support
- Add historical analytics and reporting

## Architecture Notes

The frontend is designed as a **view-only layer**. All policy enforcement, spend limits, and security decisions are implemented in the backend (D1/D2 domains). The dashboard:

- Displays what the backend reports
- Sends commands to backend endpoints
- Never implements security logic client-side
- Polls for updates (1-2 second intervals in Phase 1)

This ensures that even if the frontend is compromised, the system's security guarantees remain intact.
