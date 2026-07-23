import { api } from '@/api';
import { usePolling } from '@/hooks/usePolling';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { ProgressBar } from '@/components/ui/ProgressBar';
import type { AgentStatus } from '@/api/types';

interface AgentDisplayInfo {
  id: string;
  name: string;
  status: 'active' | 'revoked' | 'halted' | 'revoked-halted';
  dailyCap: number;
  spent: number;
  remaining: number;
  lastDecision: {
    decision: 'allow' | 'deny';
    action: string;
    amount: number;
    timeAgo: string;
  } | null;
}

interface AgentsSectionProps {
  onOpenAgentDrawer: (agentId: string) => void;
}

/**
 * AgentsSection - Displays list of all agents with their status
 *
 * Shows for each agent:
 * - Human-readable name
 * - Status indicator (Active/Revoked/Halted)
 * - Daily cap and spent amount with progress bar
 * - Last decision summary
 * - View Details button (opens drawer)
 */
export function AgentsSection({ onOpenAgentDrawer }: AgentsSectionProps) {
  const { data: agents, isLoading, error } = usePolling({
    pollFn: () => api.getAgents(),
    interval: 2000,
  });

  // Transform agents to display format
  const agentList: AgentDisplayInfo[] =
    agents?.map((agent) => {
      const spent = agent.daily_cap - agent.remaining_budget;
      const remaining = agent.remaining_budget;

      // Determine effective status - show compound status when both revoked and halted
      let status: 'active' | 'revoked' | 'halted' | 'revoked-halted';
      if (agent.fleet_halted && agent.status === 'revoked') {
        status = 'revoked-halted'; // Both conditions - agent is revoked AND fleet is halted
      } else if (agent.fleet_halted) {
        status = 'halted';
      } else if (agent.status === 'revoked') {
        status = 'revoked';
      } else {
        status = 'active';
      }

      return {
        id: agent.id,
        name: agent.name,
        status,
        dailyCap: agent.daily_cap,
        spent,
        remaining,
        lastDecision: null, // Will be populated from activity feed
      };
    }) ?? [];

  // Get activity feed to populate last decisions
  const { data: activityFeed } = usePolling({
    pollFn: () => api.getActivityFeed(50),
    interval: 2000,
  });

  // Map activity feed to agents for last decision
  const lastDecisionMap = new Map<string, AgentDisplayInfo['lastDecision']>();
  activityFeed?.forEach((event) => {
    if (!lastDecisionMap.has(event.agent_id)) {
      lastDecisionMap.set(event.agent_id, {
        decision: event.decision,
        action: event.action_type,
        amount: event.amount,
        timeAgo: formatTimeAgo(event.timestamp),
      });
    }
  });

  // Update last decisions in agent list - create new array instead of mutating
  const agentListWithDecisions = agentList.map((agent) => ({
    ...agent,
    lastDecision: lastDecisionMap.get(agent.id) ?? null,
  }));

  const handleViewDetails = (agentId: string) => {
    onOpenAgentDrawer(agentId);
  };

  if (isLoading && !agents) {
    return (
      <div className="bg-background-surface border border-border-light rounded-lg shadow-sm p-5">
        <h2 className="text-base font-semibold text-text-primary mb-4">Agents</h2>
        <div className="text-text-tertiary text-sm">Loading agents...</div>
      </div>
    );
  }

  if (error && !agents) {
    return (
      <div className="bg-background-surface border border-border-light rounded-lg shadow-sm p-5">
        <h2 className="text-base font-semibold text-text-primary mb-4">Agents</h2>
        <div className="text-semantic-error-text text-sm">
          Error loading agents: {error.message}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-background-surface border border-border-light rounded-lg shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-text-primary">Agents</h2>
        <span className="text-xs text-text-tertiary">{agentListWithDecisions.length} total</span>
      </div>

      {agentListWithDecisions.length === 0 ? (
        <div className="text-text-tertiary text-sm">No agents configured</div>
      ) : (
        <div className="space-y-3">
          {agentListWithDecisions.map((agent) => (
            <AgentCard key={agent.id} agent={agent} onViewDetails={handleViewDetails} />
          ))}
        </div>
      )}
    </div>
  );
}

interface AgentCardProps {
  agent: AgentDisplayInfo;
  onViewDetails: (agentId: string) => void;
}

function AgentCard({ agent, onViewDetails }: AgentCardProps) {
  const percentUsed = (agent.spent / agent.dailyCap) * 100;
  // Semantic thresholds: Normal < 50%, Warning 50-80%, Critical > 80%
  const riskLevel: 'normal' | 'warning' | 'critical' =
    percentUsed >= 80 ? 'critical' : percentUsed >= 50 ? 'warning' : 'normal';
  const progressColor: 'primary' | 'success' | 'warning' | 'error' =
    riskLevel === 'critical' ? 'error' : riskLevel === 'warning' ? 'warning' : 'primary';

  const riskLabel = riskLevel === 'critical' ? 'Critical' : riskLevel === 'warning' ? 'Warning' : '';
  const riskColor = riskLevel === 'critical' ? 'text-semantic-error-text' :
                    riskLevel === 'warning' ? 'text-semantic-warning-text' : '';

  return (
    <div className="bg-background-secondary rounded-lg p-4 border border-border-light hover:border-border-medium transition-colors">
      {/* Header row: Name + Status + View link */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <StatusIndicator status={agent.status} />
            <h3 className="text-base font-semibold text-text-primary truncate">{agent.name}</h3>
            {riskLabel && (
              <span className={`text-xs font-medium ${riskColor}`}>{riskLabel}</span>
            )}
          </div>
          <div className="text-xs text-text-tertiary font-mono">{agent.id}</div>
        </div>
        <button
          className="text-text-secondary hover:text-text-primary text-sm flex items-center gap-1 transition-colors ml-3"
          onClick={() => onViewDetails(agent.id)}
        >
          <span className="underline">View</span>
          <span>→</span>
        </button>
      </div>

      {/* Spend progress */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-text-primary">
            <span className="font-medium">${agent.spent.toLocaleString()}</span>
            <span className="text-text-secondary"> spent</span>
          </span>
          <span className="text-text-secondary">
            ${agent.remaining.toLocaleString()} remaining
          </span>
        </div>
        <ProgressBar value={agent.spent} max={agent.dailyCap} color={progressColor} />
        <div className="text-xs text-text-tertiary mt-1">Daily limit ${agent.dailyCap.toLocaleString()}</div>
      </div>

      {/* Last decision */}
      <div className="pt-2 border-t border-border-light">
        <div className="text-xs text-text-tertiary mb-1">Last decision</div>
        {agent.lastDecision ? (
          <div className="flex items-center gap-2 text-sm">
            <span
              className={`font-semibold ${
                agent.lastDecision.decision === 'allow'
                  ? 'text-semantic-success-text'
                  : 'text-semantic-error-text'
              }`}
            >
              {agent.lastDecision.decision.toUpperCase()}
            </span>
            <span className="text-text-primary">
              {agent.lastDecision.action}
              {agent.lastDecision.amount > 0 && (
                <span> · ${agent.lastDecision.amount}</span>
              )}
            </span>
            <span className="text-text-tertiary text-xs ml-auto">
              {agent.lastDecision.timeAgo}
            </span>
          </div>
        ) : (
          <div className="text-sm text-text-tertiary">No activity yet</div>
        )}
      </div>
    </div>
  );
}

interface StatusIndicatorProps {
  status: 'active' | 'revoked' | 'halted' | 'revoked-halted';
}

function StatusIndicator({ status }: StatusIndicatorProps) {
  const config = {
    active: { symbol: '●', color: 'text-semantic-success-text', label: 'Agent is active and operational' },
    revoked: { symbol: '!', color: 'text-semantic-warning-text', label: 'Agent is revoked' },
    halted: { symbol: '×', color: 'text-semantic-error-text', label: 'Fleet is halted' },
    'revoked-halted': { symbol: '!×', color: 'text-semantic-error-text', label: 'Agent is revoked and fleet is halted' },
  };

  const { symbol, color, label } = config[status];

  return <span className={`text-lg font-bold ${color}`} aria-label={label} role="status">{symbol}</span>;
}

/**
 * Format timestamp as "X seconds/minutes ago"
 */
function formatTimeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = Math.floor((now - then) / 1000);

  if (diff < 60) {
    return `${diff}s ago`;
  }

  const minutes = Math.floor(diff / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}
