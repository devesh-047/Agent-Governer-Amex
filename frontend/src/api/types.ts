// ============================================================================
// TYPES THAT MATCH FROZEN BACKEND CONTRACTS
// See CLAUDE.md, tasks-detailed.md for D1/D2 ownership
// ============================================================================

// RuntimeStatus (D2.2 - D2 owns this schema)
// From services/runtime_state.py check_runtime_status()
export interface RuntimeStatus {
  fleet_halted: boolean;
  agent_revoked: boolean;
  available: boolean;
}

// AuditLogEntry (D2.6-2.9 - D2 owns audit persistence)
// From db/models/audit_log.py
export interface AuditLogEntry {
  id: string;
  timestamp: string;
  agent_id: string;
  action_type: string;
  amount: number;
  decision: 'allow' | 'deny';
  reason: string | null;
  reason_code: string;
  policy_version: string;
  prev_hash: string;
  hash: string;
}

// AgentStatus (D1.7 - D1 owns this schema)
// Includes both D1 fields (policy, spend) and D2 fields (runtime status)
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

// FleetState (D2 - fleet-wide state)
export interface FleetState {
  fleet_halted: boolean;
}

// ============================================================================
// UI-SPECIFIC TYPES (not frozen contracts)
// ============================================================================

export type Scenario = 'NORMAL' | 'RISK' | 'INCIDENT';

export interface AgentLastDecision {
  timestamp: string;
  decision: 'allow' | 'deny';
  action_type: string;
  amount: number;
  reason: string;
}

export interface MockAgent {
  id: string;
  name: string;
  description: string;
  status: 'ACTIVE' | 'REVOKED'; // Intrinsic agent state only
  fleet_halted: boolean; // Global fleet state (for deriving display state)
  daily_cap: number;
  remaining_budget: number;
  max_single_amount: number;
  permissions: string[];
  last_decision: AgentLastDecision | null;
}

export interface ActivityEvent {
  id: string;
  timestamp: string;
  agent_id: string;
  agent_name: string;
  decision: 'allow' | 'deny';
  action_type: string;
  amount: number;
  reason: string | null;
}

export interface IntegrityStatus {
  status: 'UNKNOWN' | 'VERIFIED' | 'FAILED';
  last_verified: string | null;
  total_records: number;
  break_at: number | null;
  expected_hash: string | null;
  actual_hash: string | null;
}
