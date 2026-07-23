import type { GovernanceApi } from './client';
import type {
  FleetState,
  AgentStatus,
  ActivityEvent,
  IntegrityStatus,
  MockAgent,
  Scenario,
} from './types';

// ============================================================================
// IN-MOCK STATE (deterministic, no real backend)
// ============================================================================

let currentScenario: Scenario = 'NORMAL';
let fleetHalted = false;
let fleetHaltedAt: string | null = null;
const agents = new Map<string, MockAgent>();
const activityFeed: ActivityEvent[] = [];
let integrityStatus: IntegrityStatus;

// ============================================================================
// SCENARIO INITIALIZATION
// ============================================================================

function initializeScenario(scenario: Scenario) {
  currentScenario = scenario;
  activityFeed.length = 0;

  // Define base agents for all scenarios
  const baseAgents: MockAgent[] = [
    {
      id: 'agent_a_01',
      name: 'Agent A — Payment Refund Bot',
      description: 'Handles customer refund requests up to $200 per transaction',
      status: 'ACTIVE',
      fleet_halted: false,
      daily_cap: 1000,
      remaining_budget: 715,
      max_single_amount: 200,
      permissions: ['refund'],
      last_decision: {
        timestamp: new Date(Date.now() - 5000).toISOString(),
        decision: 'allow',
        action_type: 'refund',
        amount: 75,
        reason: 'Approved within policy',
      },
    },
    {
      id: 'agent_b_01',
      name: 'Agent B — Limit Adjustment Agent',
      description: 'Handles credit limit adjustment requests',
      status: 'ACTIVE',
      fleet_halted: false,
      daily_cap: 500,
      remaining_budget: 350,
      max_single_amount: 150,
      permissions: ['limit_adjustment', 'refund'],
      last_decision: {
        timestamp: new Date(Date.now() - 8000).toISOString(),
        decision: 'allow',
        action_type: 'limit_adjustment',
        amount: 0,
        reason: 'Approved within policy',
      },
    },
    {
      id: 'agent_c_01',
      name: 'Agent C — Card Replacement Service',
      description: 'Issues replacement cards for lost/stolen cards',
      status: 'ACTIVE',
      fleet_halted: false,
      daily_cap: 2000,
      remaining_budget: 750,
      max_single_amount: 50,
      permissions: ['card_replacement'],
      last_decision: {
        timestamp: new Date(Date.now() - 15000).toISOString(),
        decision: 'deny',
        action_type: 'card_replacement',
        amount: 50,
        reason: 'Daily spend cap exceeded',
      },
    },
  ];

  agents.clear();
  baseAgents.forEach((a) => agents.set(a.id, { ...a }));

  // Scenario-specific adjustments
  if (scenario === 'RISK') {
    const agentC = agents.get('agent_c_01')!;
    agentC.remaining_budget = 50; // Near cap
    agentC.last_decision = {
      timestamp: new Date(Date.now() - 3000).toISOString(),
      decision: 'deny',
      action_type: 'card_replacement',
      amount: 25,
      reason: 'Approaching daily cap',
    };
  }

  if (scenario === 'INCIDENT') {
    const agentB = agents.get('agent_b_01')!;
    agentB.status = 'REVOKED';
    agentB.last_decision = {
      timestamp: new Date(Date.now() - 10000).toISOString(),
      decision: 'deny',
      action_type: 'limit_adjustment',
      amount: 0,
      reason: 'Agent revoked by operator',
    };
  }

  // Generate initial activity feed
  generateInitialActivity();

  // Set integrity status
  integrityStatus = {
    status: 'VERIFIED',
    last_verified: new Date(Date.now() - 120000).toISOString(),
    total_records: activityFeed.length + 800, // Simulate existing records
    break_at: null,
    expected_hash: null,
    actual_hash: null,
  };
}

function generateInitialActivity() {
  const now = Date.now();
  const events: ActivityEvent[] = [
    {
      id: 'evt_001',
      timestamp: new Date(now - 5000).toISOString(),
      agent_id: 'agent_a_01',
      agent_name: 'Agent A',
      decision: 'allow',
      action_type: 'refund',
      amount: 75,
      reason: null,
    },
    {
      id: 'evt_002',
      timestamp: new Date(now - 8000).toISOString(),
      agent_id: 'agent_b_01',
      agent_name: 'Agent B',
      decision: 'allow',
      action_type: 'limit_adjustment',
      amount: 150,
      reason: null,
    },
    {
      id: 'evt_003',
      timestamp: new Date(now - 15000).toISOString(),
      agent_id: 'agent_c_01',
      agent_name: 'Agent C',
      decision: 'deny',
      action_type: 'card_replacement',
      amount: 50,
      reason: 'Daily spend cap exceeded',
    },
    {
      id: 'evt_004',
      timestamp: new Date(now - 22000).toISOString(),
      agent_id: 'agent_a_01',
      agent_name: 'Agent A',
      decision: 'allow',
      action_type: 'refund',
      amount: 125,
      reason: null,
    },
    {
      id: 'evt_005',
      timestamp: new Date(now - 28000).toISOString(),
      agent_id: 'agent_b_01',
      agent_name: 'Agent B',
      decision: 'allow',
      action_type: 'refund',
      amount: 85,
      reason: null,
    },
  ];

  activityFeed.length = 0;
  activityFeed.push(...events);
}

function addActivityEvent(event: ActivityEvent) {
  activityFeed.unshift(event);
  if (activityFeed.length > 50) {
    activityFeed.pop();
  }
}

// Initialize on load
initializeScenario('NORMAL');

// ============================================================================
// MOCK API IMPLEMENTATION
// ============================================================================

export const mockApi: GovernanceApi = {
  async getFleetState(): Promise<FleetState> {
    return { fleet_halted: fleetHalted };
  },

  async haltFleet(): Promise<void> {
    fleetHalted = true;
    fleetHaltedAt = new Date().toISOString();

    // Fleet halt is global state - do NOT mutate individual agent statuses
    // Agents remain in their intrinsic ACTIVE/REVOKED state
    // UI components derive display state from fleet_halted + agent.status

    // Add halt event to activity
    addActivityEvent({
      id: `evt_${Date.now()}_halt`,
      timestamp: fleetHaltedAt,
      agent_id: 'system',
      agent_name: 'System',
      decision: 'deny',
      action_type: 'fleet_halt',
      amount: 0,
      reason: 'Fleet halted by operator',
    });
  },

  async resumeFleet(): Promise<void> {
    fleetHalted = false;
    const resumeTime = new Date().toISOString();

    // Fleet resume is global state - do NOT mutate individual agent statuses
    // Agents remain in their intrinsic ACTIVE/REVOKED state
    // UI components derive display state from fleet_halted + agent.status

    // Add resume event
    addActivityEvent({
      id: `evt_${Date.now()}_resume`,
      timestamp: resumeTime,
      agent_id: 'system',
      agent_name: 'System',
      decision: 'allow',
      action_type: 'fleet_resume',
      amount: 0,
      reason: 'Fleet resumed by operator',
    });
  },

  async getAgents(): Promise<AgentStatus[]> {
    return Array.from(agents.values()).map((a) => ({
      id: a.id,
      name: a.name,
      permissions: a.permissions,
      max_single_amount: a.max_single_amount,
      daily_cap: a.daily_cap,
      remaining_budget: a.remaining_budget,
      status: a.status === 'ACTIVE' ? 'active' : 'revoked',
      fleet_halted: fleetHalted,
    }));
  },

  async getAgent(agentId: string): Promise<MockAgent> {
    const agent = agents.get(agentId);
    if (!agent) {
      throw new Error(`Agent ${agentId} not found`);
    }
    return { ...agent, fleet_halted: fleetHalted };
  },

  async revokeAgent(agentId: string): Promise<void> {
    const agent = agents.get(agentId);
    if (!agent) return;

    agent.status = 'REVOKED';
    agent.last_decision = {
      timestamp: new Date().toISOString(),
      decision: 'deny',
      action_type: 'agent_revoked',
      amount: 0,
      reason: 'Agent revoked by operator',
    };

    addActivityEvent({
      id: `evt_${Date.now()}_revoke_${agentId}`,
      timestamp: agent.last_decision.timestamp,
      agent_id: agentId,
      agent_name: agent.name.split('—')[0].trim(),
      decision: 'deny',
      action_type: 'agent_revoke',
      amount: 0,
      reason: `Agent ${agent.name} revoked by operator`,
    });
  },

  async restoreAgent(agentId: string): Promise<void> {
    const agent = agents.get(agentId);
    if (!agent) return;

    // Restore agent's intrinsic status to ACTIVE
    // If fleet is halted, UI will still show agent as blocked by fleet halt
    agent.status = 'ACTIVE';

    agent.last_decision = {
      timestamp: new Date().toISOString(),
      decision: 'allow',
      action_type: 'agent_restored',
      amount: 0,
      reason: 'Agent restored by operator',
    };

    addActivityEvent({
      id: `evt_${Date.now()}_restore_${agentId}`,
      timestamp: agent.last_decision.timestamp,
      agent_id: agentId,
      agent_name: agent.name.split('—')[0].trim(),
      decision: 'allow',
      action_type: 'agent_restore',
      amount: 0,
      reason: `Agent ${agent.name} restored by operator`,
    });
  },

  async getActivityFeed(limit?: number): Promise<ActivityEvent[]> {
    return limit ? activityFeed.slice(0, limit) : [...activityFeed];
  },

  async getIntegrityStatus(): Promise<IntegrityStatus> {
    return { ...integrityStatus };
  },

  async verifyChain(): Promise<IntegrityStatus> {
    const result: IntegrityStatus = {
      status: 'VERIFIED',
      last_verified: new Date().toISOString(),
      total_records: activityFeed.length + 800,
      break_at: null,
      expected_hash: null,
      actual_hash: null,
    };

    // Simulate failure in INCIDENT scenario
    if (currentScenario === 'INCIDENT') {
      result.status = 'FAILED';
      result.break_at = 424;
      result.total_records = 847;
      result.expected_hash =
        'a3f7e9c2b1d8f4a6e5c7b9d2a1f8e3c4b5d6a7c8e9f0a1b2c3d4e5f6a7b8c9d';
      result.actual_hash =
        'x9m4k8j2n5p1q3r6s9t2u5v8w1x4y7z0a2b4c6d8e1f3g5h7i9j0k2l4m6';
    }

    integrityStatus = result;
    return result;
  },

  async setScenario(scenario: Scenario): Promise<void> {
    initializeScenario(scenario);
    // Fleet halt state is independent - agents stay in their intrinsic state
    // UI derives display state from fleet_halted + agent.status
  },

  async getCurrentScenario(): Promise<Scenario> {
    return currentScenario;
  },
};
