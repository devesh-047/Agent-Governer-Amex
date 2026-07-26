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

export interface Agent {
  id: string;
  name: string;
  description: string; // The backend doesn't have a description field, but UI might need it. We will map name or leave it empty in client.
  permissions: string[];
  max_single_amount: number;
  daily_cap: number;
  remaining_budget: number | null;
  status: 'active' | 'revoked';
  runtime_status: 'active' | 'revoked' | null;
  fleet_halted: boolean | null;
}

// FleetState (D2 - fleet-wide state)
export interface FleetState {
  fleet_halted: boolean;
}

// ============================================================================
// UI-SPECIFIC TYPES (not frozen contracts)
// ============================================================================

// Removed Scenario

// Removed MockAgent and AgentLastDecision

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

export interface ActionExecutionResponse {
  decision: 'allow' | 'deny';
  reason_code: string;
  reason: string | null;
  remaining_budget: number;
  audit_log_id?: string;
  hash?: string;
  execution_time_ms?: number;
}

