import type {
  Agent,
  FleetState,
  ActivityEvent,
  IntegrityStatus,
  ActionExecutionResponse,
} from './types';
import type { GovernanceApi } from './client';

const API_BASE_URL = 'http://localhost:8000';

const KNOWN_AGENT_SECRETS: Record<string, string> = {
  '11111111-1111-1111-1111-111111111111': 'secret-compliant-A',
  '22222222-2222-2222-2222-222222222222': 'secret-violator-B',
  '33333333-3333-3333-3333-333333333333': 'secret-runaway-C',
  '00000000-0000-0000-0000-000000000001': 'system-secret',
  'agent_a_01': 'secret-compliant-A',
  'agent_b_02': 'secret-violator-B',
  'agent_c_03': 'secret-runaway-C',
  'agent_d_04': 'system-secret',
};

function getAgentSecret(agentId: string, agentName?: string): string {
  if (KNOWN_AGENT_SECRETS[agentId]) {
    return KNOWN_AGENT_SECRETS[agentId];
  }
  const name = (agentName || '').toLowerCase();
  const id = agentId.toLowerCase();

  if (name.includes('system') || id.includes('system') || id === '00000000-0000-0000-0000-000000000001') {
    return 'system-secret';
  }
  if (name.includes('travel') || name.includes('violator') || id.includes('22222222') || id.includes('agent_b')) {
    return 'secret-violator-B';
  }
  if (name.includes('reward') || name.includes('runaway') || id.includes('33333333') || id.includes('agent_c')) {
    return 'secret-runaway-C';
  }
  if (name.includes('payment') || name.includes('compliant') || id.includes('11111111') || id.includes('agent_a')) {
    return 'secret-compliant-A';
  }
  return 'secret-compliant-A';
}

async function fetchWithHandling<T>(url: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${url}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
  } catch (error) {
    // Network errors (e.g. CORS, server down)
    throw new Error(`Network error: Could not connect to backend. Please ensure it is running.`);
  }

  if (!response.ok) {
    let errorMessage = `HTTP Error ${response.status}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
      }
    } catch (e) {
      // Failed to parse JSON error response, use default message
    }
    
    // Customize error message for 503 Fail-Closed scenarios
    if (response.status === 503) {
      throw new Error(`Service Unavailable: ${errorMessage}`);
    }

    throw new Error(errorMessage);
  }

  return response.json();
}

export const fetchApi: GovernanceApi = {
  // Fleet & System
  async getFleetState(): Promise<FleetState> {
    const data = await fetchWithHandling<{ fleet_halted: boolean; available: boolean }>('/fleet/state');
    return {
      fleet_halted: data.fleet_halted,
    };
  },

  async haltFleet(): Promise<void> {
    await fetchWithHandling('/fleet/halt', { method: 'POST' });
  },

  async resumeFleet(): Promise<void> {
    await fetchWithHandling('/fleet/resume', { method: 'POST' });
  },

  // Agents
  async getAgents(): Promise<Agent[]> {
    const data = await fetchWithHandling<Agent[]>('/agents');
    // Map data just in case description is missing, we populate it
    return data.map(agent => ({
      ...agent,
      description: agent.description || `${agent.name} handler`,
    }));
  },

  async getAgent(agentId: string): Promise<Agent> {
    const agents = await this.getAgents();
    const agent = agents.find(a => a.id === agentId);
    if (!agent) {
      throw new Error(`Agent ${agentId} not found`);
    }
    return agent;
  },

  async updatePolicy(agentId: string, permissions: string[], max_single_amount: number, daily_cap: number): Promise<Agent> {
    const data = await fetchWithHandling<Agent>(`/agents/${agentId}/policy`, {
      method: 'PUT',
      body: JSON.stringify({
        permissions,
        max_single_amount,
        daily_cap
      })
    });
    return {
      ...data,
      description: data.description || `${data.name} handler`,
    };
  },

  async resetSpend(agentId: string): Promise<void> {
    await fetchWithHandling(`/agents/${agentId}/reset-spend`, { method: 'POST' });
  },

  // Agent Runtime Safety
  async revokeAgent(agentId: string): Promise<void> {
    await fetchWithHandling(`/agents/${agentId}/revoke`, { method: 'POST' });
  },

  async restoreAgent(agentId: string): Promise<void> {
    await fetchWithHandling(`/agents/${agentId}/restore`, { method: 'POST' });
  },

  // Action Request Execution (Gateway)
  async executeAction(agentId: string, actionType: string, amount: number, agentName?: string): Promise<ActionExecutionResponse> {
    const startTime = performance.now();
    const secret = getAgentSecret(agentId, agentName);

    try {
      const response = await fetch(`${API_BASE_URL}/action-request`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Agent-Id': agentId,
          'X-Agent-Secret': secret,
        },
        body: JSON.stringify({
          action_type: actionType,
          amount: amount,
        }),
      });

      const endTime = performance.now();
      const execution_time_ms = Math.round(endTime - startTime);

      const data = await response.json();

      if (!response.ok) {
        // Backend returns detail object for 403 (FLEET_HALTED, AGENT_REVOKED) or 503
        if (data.detail && typeof data.detail === 'object' && data.detail.decision) {
          return {
            decision: data.detail.decision as 'allow' | 'deny',
            reason_code: data.detail.reason_code || 'DENIED',
            reason: data.detail.reason || 'Action denied by governance pipeline',
            remaining_budget: data.detail.remaining_budget ?? 0,
            audit_log_id: data.detail.audit_log_id || '',
            hash: data.detail.hash || '',
            execution_time_ms,
          };
        }
        throw new Error(data.detail || `HTTP error ${response.status}`);
      }

      return {
        decision: data.decision as 'allow' | 'deny',
        reason_code: data.reason_code,
        reason: data.reason || (data.decision === 'allow' ? 'OK' : null),
        remaining_budget: data.remaining_budget,
        audit_log_id: data.audit_log_id,
        hash: data.hash,
        execution_time_ms,
      };
    } catch (error: any) {
      if (error && typeof error === 'object' && error.decision) {
        return error;
      }
      throw error;
    }
  },

  // Activity Feed
  async getActivityFeed(limit: number = 50): Promise<ActivityEvent[]> {
    const data = await fetchWithHandling<any[]>(`/audit/feed?limit=${limit}`);
    return data.map(event => ({
      id: event.id,
      timestamp: event.timestamp,
      agent_id: event.agent_id,
      agent_name: event.agent_id.split('-')[0], // The backend doesn't return agent_name, we simplify for now.
      decision: event.decision as 'allow' | 'deny',
      action_type: event.action_type,
      amount: event.amount,
      reason: event.reason,
    }));
  },

  // Audit Integrity
  async getIntegrityStatus(): Promise<IntegrityStatus> {
    const data = await fetchWithHandling<any>('/audit/integrity');
    return {
      status: data.intact ? 'VERIFIED' : (data.error_type ? 'FAILED' : 'UNKNOWN'),
      last_verified: new Date().toISOString(),
      total_records: data.verified_count,
      break_at: data.broken_at_row,
      expected_hash: null,
      actual_hash: null,
    };
  },

  async verifyChain(): Promise<IntegrityStatus> {
    const data = await fetchWithHandling<any>('/audit/verify-chain', { method: 'POST' });
    return {
      status: data.intact ? 'VERIFIED' : 'FAILED',
      last_verified: new Date().toISOString(),
      total_records: data.verified_count,
      break_at: data.broken_at_row,
      expected_hash: null,
      actual_hash: null,
    };
  },

}

