import type {
  Agent,
  FleetState,
  ActivityEvent,
  IntegrityStatus,
  ActionExecutionResponse,
} from './types';

/**
 * GovernanceApi - Interface for all backend API calls
 *
 * This is the SINGLE client for all D1 and D2 endpoints.
 * The frontend NEVER implements enforcement - only calls backend.
 *
 * Endpoint ownership:
 * - D2 endpoints: getFleetState, haltFleet, resumeFleet, getAgent,
 *                revokeAgent, restoreAgent, verifyChain
 * - D1 endpoints: getAgents (includes D2 runtime status composed in)
 *
 * During Phase 1-2, this interface is implemented by mocks.
 * When D1/D2 endpoints are ready, we swap in the real fetch-based client.
 */
export interface GovernanceApi {
  // Fleet & System (D2)
  getFleetState(): Promise<FleetState>;
  haltFleet(): Promise<void>;
  resumeFleet(): Promise<void>;

  // Agents (D1 + D2 composed)
  getAgents(): Promise<Agent[]>;
  getAgent(agentId: string): Promise<Agent>;

  // Policy & Spend (D1)
  updatePolicy(agentId: string, permissions: string[], max_single_amount: number, daily_cap: number): Promise<Agent>;
  resetSpend(agentId: string): Promise<void>;

  // Agent Runtime Safety (D2)
  revokeAgent(agentId: string): Promise<void>;
  restoreAgent(agentId: string): Promise<void>;

  // Action Request Execution (Gateway)
  executeAction(agentId: string, actionType: string, amount: number, agentName?: string): Promise<ActionExecutionResponse>;

  // Activity Feed (D2)
  getActivityFeed(limit?: number): Promise<ActivityEvent[]>;

  // Audit Integrity (D2)
  getIntegrityStatus(): Promise<IntegrityStatus>;
  verifyChain(): Promise<IntegrityStatus>;

}

