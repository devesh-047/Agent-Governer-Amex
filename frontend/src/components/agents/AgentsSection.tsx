import { useState } from 'react';
import { ChevronDown, ChevronUp, Copy, Check, Eye, ShieldAlert, ShieldCheck, Cpu } from 'lucide-react';
import { api } from '@/api';
import { usePolling } from '@/hooks/usePolling';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { ProgressBar } from '@/components/ui/ProgressBar';

interface AgentDisplayInfo {
  id: string;
  name: string;
  status: 'active' | 'revoked' | 'halted' | 'revoked-halted';
  dailyCap: number;
  spent: number;
  remaining: number;
  behaviour: 'Compliant' | 'Policy Violator' | 'Runaway' | 'System';
  lastDecision: {
    decision: 'allow' | 'deny';
    action: string;
    amount: number;
    reason?: string | null;
    timeAgo: string;
  } | null;
}

interface AgentsSectionProps {
  onOpenAgentDrawer: (agentId: string) => void;
}

/**
 * AgentsSection - Displays list of all agents with their status, metrics, and actions
 */
export function AgentsSection({ onOpenAgentDrawer }: AgentsSectionProps) {
  const { data: agents, isLoading, error } = usePolling({
    pollFn: () => api.getAgents(),
    interval: 2000,
  });

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
        reason: event.reason,
        timeAgo: formatTimeAgo(event.timestamp),
      });
    }
  });

  // Transform agents to display format
  const agentList: AgentDisplayInfo[] =
    agents?.map((agent) => {
      const spent = Math.max(0, agent.daily_cap - (agent.remaining_budget ?? agent.daily_cap));
      const remaining = agent.remaining_budget ?? 0;

      const isRevoked = agent.status === 'revoked' || agent.runtime_status === 'revoked';
      const isHalted = agent.fleet_halted === true;
      let status: 'active' | 'revoked' | 'halted' | 'revoked-halted';
      if (isRevoked && isHalted) {
        status = 'revoked-halted';
      } else if (isHalted) {
        status = 'halted';
      } else if (isRevoked) {
        status = 'revoked';
      } else {
        status = 'active';
      }

      const lastDec = lastDecisionMap.get(agent.id) ?? null;

      // Determine Behaviour Badge
      let behaviour: 'Compliant' | 'Policy Violator' | 'Runaway' | 'System' = 'Compliant';
      if (agent.name.toLowerCase().includes('system') || agent.id.toLowerCase().includes('system')) {
        behaviour = 'System';
      } else if (isRevoked || lastDec?.decision === 'deny') {
        behaviour = 'Policy Violator';
      } else if ((spent / agent.daily_cap) >= 0.8) {
        behaviour = 'Runaway';
      }

      return {
        id: agent.id,
        name: agent.name,
        status,
        dailyCap: agent.daily_cap,
        spent,
        remaining,
        behaviour,
        lastDecision: lastDec,
      };
    }) ?? [];

  const handleViewDetails = (agentId: string) => {
    onOpenAgentDrawer(agentId);
  };

  if (isLoading && !agents) {
    return (
      <div className="bg-white border border-slate-200/80 rounded-xl shadow-sm p-6">
        <h2 className="text-base font-bold text-slate-900 mb-4">Agents Fleet</h2>
        <div className="text-slate-400 text-sm animate-pulse">Loading agent fleet...</div>
      </div>
    );
  }

  if (error && !agents) {
    return (
      <div className="bg-white border border-slate-200/80 rounded-xl shadow-sm p-6">
        <h2 className="text-base font-bold text-slate-900 mb-4">Agents Fleet</h2>
        <div className="text-rose-600 text-sm font-medium">
          Failed to load agents: {error.message}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200/80 rounded-xl shadow-sm p-5">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
        <div>
          <h2 className="text-base font-bold text-slate-900 tracking-tight">Agents Fleet</h2>
          <p className="text-xs text-slate-500 font-normal">Active financial agent instances</p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-700">
          {agentList.length} Total
        </span>
      </div>

      {agentList.length === 0 ? (
        <div className="text-slate-400 text-sm text-center py-6">No active agents found</div>
      ) : (
        <div className="space-y-4">
          {agentList.map((agent) => (
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
  const [showFullUuid, setShowFullUuid] = useState(false);
  const [copied, setCopied] = useState(false);

  const percentUsed = Math.min(100, Math.max(0, (agent.spent / agent.dailyCap) * 100));
  const riskLevel: 'normal' | 'warning' | 'critical' =
    percentUsed >= 80 ? 'critical' : percentUsed >= 50 ? 'warning' : 'normal';
  const progressColor: 'primary' | 'success' | 'warning' | 'error' =
    riskLevel === 'critical' ? 'error' : riskLevel === 'warning' ? 'warning' : 'primary';

  const copyUuid = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(agent.id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const getBehaviourStyle = (b: AgentDisplayInfo['behaviour']) => {
    switch (b) {
      case 'Compliant':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'Policy Violator':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'Runaway':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'System':
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  const getStatusBadgeVariant = (s: AgentDisplayInfo['status']) => {
    switch (s) {
      case 'active':
        return { variant: 'success' as const, label: 'ACTIVE' };
      case 'revoked':
        return { variant: 'warning' as const, label: 'REVOKED' };
      case 'halted':
        return { variant: 'error' as const, label: 'HALTED' };
      case 'revoked-halted':
        return { variant: 'error' as const, label: 'REVOKED · HALTED' };
    }
  };

  const statusInfo = getStatusBadgeVariant(agent.status);
  const shortenedId = agent.id.length > 12 ? `${agent.id.slice(0, 10)}...` : agent.id;

  return (
    <div className="bg-slate-50/70 hover:bg-slate-50 border border-slate-200 rounded-xl p-4 transition-all duration-200 shadow-2xs hover:shadow-sm">
      {/* Top Row: Name, Badges & View button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center flex-wrap gap-2 mb-1">
            <h3 className="text-base font-bold text-slate-900 truncate tracking-tight">
              {agent.name}
            </h3>
            {/* Behaviour Badge */}
            <span
              className={`text-[11px] font-bold px-2 py-0.5 rounded-md border ${getBehaviourStyle(
                agent.behaviour
              )}`}
            >
              {agent.behaviour}
            </span>
            {/* Status Badge */}
            <StatusBadge variant={statusInfo.variant}>
              {statusInfo.label}
            </StatusBadge>
          </div>

          {/* Collapsible UUID (Hidden by default) */}
          <div className="flex items-center gap-2 mt-1 text-xs text-slate-400 font-mono">
            <span>ID:</span>
            {!showFullUuid ? (
              <span className="bg-slate-200/60 px-1.5 py-0.5 rounded text-slate-600 font-medium">
                {shortenedId}
              </span>
            ) : (
              <span className="bg-slate-900 text-emerald-400 px-2 py-0.5 rounded select-all break-all">
                {agent.id}
              </span>
            )}
            <button
              onClick={() => setShowFullUuid(!showFullUuid)}
              className="text-[11px] text-slate-500 hover:text-slate-800 font-sans flex items-center gap-0.5 underline cursor-pointer"
            >
              {showFullUuid ? (
                <>Hide ID <ChevronUp className="w-3 h-3" /></>
              ) : (
                <>Expand ID <ChevronDown className="w-3 h-3" /></>
              )}
            </button>
            {showFullUuid && (
              <button
                onClick={copyUuid}
                className="text-slate-400 hover:text-slate-700 p-0.5 transition-colors"
                title="Copy full UUID"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>
        </div>

        {/* View Details Action Button */}
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onViewDetails(agent.id)}
          className="self-start sm:self-center shrink-0"
        >
          <span>View Details</span>
          <Eye className="w-3.5 h-3.5 ml-0.5" />
        </Button>
      </div>

      {/* Spend Progress Section */}
      <div className="bg-white border border-slate-200/80 rounded-lg p-3 mb-3">
        <div className="flex items-center justify-between text-xs font-medium mb-1.5">
          <span className="text-slate-700">
            Spent: <span className="font-bold text-slate-900">${agent.spent.toLocaleString()}</span>
          </span>
          <span className="text-slate-500">
            Remaining: <span className="font-bold text-emerald-700">${agent.remaining.toLocaleString()}</span>
          </span>
        </div>
        <ProgressBar value={agent.spent} max={agent.dailyCap} color={progressColor} />
        <div className="flex items-center justify-between text-[11px] text-slate-400 mt-1.5 font-medium">
          <span>Daily Limit: ${agent.dailyCap.toLocaleString()}</span>
          <span>{percentUsed.toFixed(1)}% utilized</span>
        </div>
      </div>

      {/* Last Decision Footer */}
      <div className="flex items-center justify-between text-xs pt-1.5 border-t border-slate-200/60">
        <span className="text-slate-400 font-medium">Last Decision:</span>
        {agent.lastDecision ? (
          <div className="flex items-center gap-2">
            <span
              className={`font-bold px-1.5 py-0.5 rounded text-[11px] ${
                agent.lastDecision.decision === 'allow'
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : 'bg-rose-50 text-rose-700 border border-rose-200'
              }`}
            >
              {agent.lastDecision.decision.toUpperCase()}
            </span>
            <span className="text-slate-700 font-medium truncate max-w-[180px]">
              {agent.lastDecision.action}
              {agent.lastDecision.amount > 0 && ` ($${agent.lastDecision.amount})`}
            </span>
            <span className="text-slate-400 text-[11px] font-mono">
              {agent.lastDecision.timeAgo}
            </span>
          </div>
        ) : (
          <span className="text-slate-400 font-normal italic">No recent decisions</span>
        )}
      </div>
    </div>
  );
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

