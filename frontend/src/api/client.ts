import type {
  AgentStatus,
  FleetState,
  ActivityEvent,
  IntegrityStatus,
  MockAgent,
  Scenario,
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
