import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { api } from '@/api';
import { toast } from '@/components/ui/Toast';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { ProgressBar } from '@/components/ui/ProgressBar';
import type { MockAgent } from '@/api/types';

interface AgentDrawerProps {
  isOpen: boolean;
  agentId: string | null;
  onClose: () => void;
  onAgentRevoked?: (agentId: string) => void;
  onAgentRestored?: (agentId: string) => void;
}

interface RecentDecision {
  timestamp: string;
  decision: 'allow' | 'deny';
  action_type: string;
  amount: number;
  reason: string | null;
  timeAgo: string;
}

/**
 * AgentDrawer - Slide-out drawer showing detailed agent information
 *
 * Features:
 * - Slides in from right with 200ms animation
 * - ESC key closes drawer
 * - Overlay click closes drawer
 * - Shows agent identity, runtime status, spend, permissions (read-only), recent decisions
 * - Revoke/Restore agent buttons with confirmation
 */
export function AgentDrawer({ isOpen, agentId, onClose, onAgentRevoked, onAgentRestored }: AgentDrawerProps) {
  const [agent, setAgent] = useState<MockAgent | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showRevokeConfirm, setShowRevokeConfirm] = useState(false);
  const [recentDecisions, setRecentDecisions] = useState<RecentDecision[]>([]);

  // Load agent data when drawer opens
  useEffect(() => {
    if (isOpen && agentId) {
      setIsLoading(true);
      api.getAgent(agentId)
        .then((data) => {
          setAgent(data);
          // Load recent decisions for this agent
          return api.getActivityFeed(50);
        })
        .then((feed) => {
          const agentDecisions = feed
            .filter((e) => e.agent_id === agentId)
            .slice(0, 10)
            .map((e) => ({
              timestamp: e.timestamp,
              decision: e.decision,
              action_type: e.action_type,
              amount: e.amount,
              reason: e.reason,
              timeAgo: formatTimeAgo(e.timestamp),
            }));
          setRecentDecisions(agentDecisions);
        })
        .catch((error) => {
          console.error('Failed to load agent:', error);
          toast.error('Failed to load agent details');
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setAgent(null);
      setRecentDecisions([]);
      setShowRevokeConfirm(false);
    }
  }, [isOpen, agentId]);

  // ESC key closes drawer
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [isOpen, onClose]);

  const handleRevokeAgent = async () => {
    if (!agent) return;

    try {
      await api.revokeAgent(agent.id);
      toast.success(`Agent "${agent.name}" revoked successfully`);
      setShowRevokeConfirm(false);
      onAgentRevoked?.(agent.id);
      onClose();
    } catch (error) {
      console.error('Failed to revoke agent:', error);
      toast.error('Failed to revoke agent');
    }
  };

  const handleRestoreAgent = async () => {
    if (!agent) return;

    try {
      await api.restoreAgent(agent.id);
      toast.success(`Agent "${agent.name}" restored successfully`);
      onAgentRestored?.(agent.id);
      onClose();
    } catch (error) {
      console.error('Failed to restore agent:', error);
      toast.error('Failed to restore agent');
    }
  };

  if (!isOpen) return null;

  const spent = agent ? agent.daily_cap - agent.remaining_budget : 0;
  const percentUsed = agent ? (spent / agent.daily_cap) * 100 : 0;

  return (
    <>
      {/* Overlay backdrop */}
      <div
        className={`fixed inset-0 bg-black/30 backdrop-blur-sm z-40 transition-opacity duration-200 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={`fixed top-0 right-0 h-full w-full max-w-2xl bg-background-surface shadow-2xl z-50 transform transition-transform duration-200 ease-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-text-secondary">Loading agent details...</div>
          </div>
        ) : agent ? (
          <div className="h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-light">
              <div>
                <h2 className="text-lg font-semibold text-text-primary">AGENT DETAILS</h2>
                <p className="text-sm text-text-secondary mt-1">{agent.name}</p>
              </div>
              <button
                onClick={onClose}
                className="text-text-tertiary hover:text-text-secondary transition-colors p-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Content - scrollable */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
              {/* ID */}
              <div className="text-xs text-text-tertiary font-mono">ID: {agent.id}</div>

              {/* Section divider helper */}
              <SectionDivider title="IDENTITY & RUNTIME" />
              <div className="space-y-4">
                <div>
                  <p className="text-base font-medium text-text-primary">{agent.name}</p>
                  <p className="text-sm text-text-secondary mt-1">{agent.description}</p>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-text-secondary">Status:</span>{' '}
                    {(() => {
                      const isRevoked = agent.status === 'REVOKED';
                      const isHalted = agent.fleet_halted;
                      if (isRevoked && isHalted) {
                        return <StatusBadge variant="error">REVOKED · FLEET HALTED</StatusBadge>;
                      } else if (isRevoked) {
                        return <StatusBadge variant="warning">REVOKED</StatusBadge>;
                      } else if (isHalted) {
                        return <StatusBadge variant="error">HALTED BY FLEET</StatusBadge>;
                      } else {
                        return <StatusBadge variant="success">ACTIVE</StatusBadge>;
                      }
                    })()}
                  </div>
                  <div>
                    <span className="text-text-secondary">Runtime:</span>{' '}
                    <span className="text-text-primary font-medium">
                      {(() => {
                        const isRevoked = agent.status === 'REVOKED';
                        const isHalted = agent.fleet_halted;
                        if (isRevoked && isHalted) return 'NON-OPERATIONAL (REVOKED + HALTED)';
                        if (isRevoked) return 'NON-OPERATIONAL (REVOKED)';
                        if (isHalted) return 'NON-OPERATIONAL (FLEET HALTED)';
                        return 'OPERATIONAL';
                      })()}
                    </span>
                  </div>
                  <div>
                    <span className="text-text-secondary">Registered:</span>{' '}
                    <span className="text-text-primary">January 15, 2026</span>
                  </div>
                  <div>
                    <span className="text-text-secondary">Last Activity:</span>{' '}
                    <span className="text-text-primary">
                      {agent.last_decision
                        ? formatTimeAgo(agent.last_decision.timestamp)
                        : 'No activity'}
                    </span>
                  </div>
                </div>
              </div>

              <SectionDivider title="SPEND" />
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-text-secondary">Daily Cap:</span>{' '}
                    <span className="text-text-primary font-medium">
                      ${agent.daily_cap.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-text-secondary">Remaining:</span>{' '}
                    <span className="text-text-primary font-medium">
                      ${agent.remaining_budget.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-text-secondary">Max Single Tx:</span>{' '}
                    <span className="text-text-primary font-medium">
                      ${agent.max_single_amount.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-text-secondary">Spent Today:</span>{' '}
                    <span className="text-text-primary font-medium">
                      ${spent.toLocaleString()}
                    </span>
                  </div>
                </div>

                <ProgressBar
                  value={spent}
                  max={agent.daily_cap}
                  color={percentUsed >= 90 ? 'error' : percentUsed >= 70 ? 'warning' : 'primary'}
                />
              </div>

              <SectionDivider title="PERMISSIONS (read-only)" />
              <div className="space-y-2">
                {agent.permissions.map((perm) => (
                  <div key={perm} className="flex items-center gap-2 text-sm">
                    <span className="text-semantic-success-text font-bold">✓</span>
                    <span className="text-text-primary font-mono">{perm}</span>
                    <span className="text-text-secondary text-xs ml-2">
                      {getPermissionDescription(perm)}
                    </span>
                  </div>
                ))}
              </div>

              <SectionDivider
                title="RECENT DECISIONS (Last 10)"
                rightElement={<span className="text-xs text-text-secondary font-normal">VIEW ALL</span>}
              />
              <div className="space-y-2">
                {recentDecisions.length > 0 ? (
                  recentDecisions.map((decision, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-3 text-sm py-1 border-b border-border-light last:border-0"
                    >
                      <span className="text-text-tertiary text-xs w-16">
                        {decision.timeAgo}
                      </span>
                      <span
                        className={`font-bold ${
                          decision.decision === 'allow'
                            ? 'text-semantic-success-text'
                            : 'text-semantic-error-text'
                        }`}
                      >
                        {decision.decision === 'allow' ? '●' : '×'}
                      </span>
                      <span
                        className={`font-medium ${
                          decision.decision === 'allow'
                            ? 'text-semantic-success-text'
                            : 'text-semantic-error-text'
                        } w-10`}
                      >
                        {decision.decision.toUpperCase()}
                      </span>
                      <span className="text-text-primary w-16 text-right">
                        {decision.amount > 0 ? `$${decision.amount}` : '—'}
                      </span>
                      <span className="text-text-primary font-mono">{decision.action_type}</span>
                      <span className="text-text-secondary text-xs flex-1 truncate">
                        {decision.reason || ''}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="text-text-tertiary text-sm text-center py-4">
                    No recent decisions
                  </div>
                )}
              </div>

              <SectionDivider title="RUNTIME CONTROL" />
              <div>
                {!showRevokeConfirm ? (
                  <>
                    {agent.status === 'ACTIVE' ? (
                      <>
                        <Button
                          variant="danger"
                          className="w-full"
                          onClick={() => setShowRevokeConfirm(true)}
                        >
                          REVOKE AGENT
                        </Button>
                        <p className="text-xs text-text-secondary mt-3 text-center">
                          Immediately prevent this agent from processing requests. All actions will
                          be denied.
                        </p>
                      </>
                    ) : (
                      <>
                        <Button
                          variant="primary"
                          className="w-full"
                          onClick={handleRestoreAgent}
                        >
                          RESTORE AGENT
                        </Button>
                        <p className="text-xs text-text-secondary mt-3 text-center">
                          Restore this agent to active operational status.
                        </p>
                      </>
                    )}
                  </>
                ) : (
                  <div className="space-y-4">
                    <div className="text-semantic-warning-text text-sm">
                      ⚠ CONFIRM REVOCATION
                    </div>
                    <p className="text-sm text-text-secondary">
                      You are about to REVOKE agent:
                    </p>
                    <p className="text-base font-medium text-text-primary">{agent.name}</p>
                    <div className="bg-background-tertiary rounded p-3 text-xs text-text-secondary space-y-1">
                      <p>WHAT THIS MEANS:</p>
                      <ul className="list-disc list-inside space-y-1">
                        <li>All future requests from this agent will be DENIED</li>
                        <li>This is reversible via RESTORE</li>
                        <li>This does NOT affect other agents</li>
                        <li>This action is logged to the audit trail</li>
                      </ul>
                    </div>
                    <div className="flex gap-4">
                      <Button variant="secondary" className="flex-1" onClick={onClose}>
                        CANCEL
                      </Button>
                      <Button
                        variant="danger"
                        className="flex-1"
                        onClick={handleRevokeAgent}
                      >
                        CONFIRM REVOCATION
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </>
  );
}

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

function getPermissionDescription(permission: string): string {
  const descriptions: Record<string, string> = {
    refund: 'Process customer refunds',
    limit_adjustment: 'Adjust credit limits',
    card_replacement: 'Issue replacement cards',
  };
  return descriptions[permission] || 'Custom action';
}

interface SectionDividerProps {
  title: string;
  rightElement?: ReactNode;
}

function SectionDivider({ title, rightElement }: SectionDividerProps) {
  return (
    <div className="flex items-center justify-between pb-2 border-b border-border-light">
      <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
      {rightElement}
    </div>
  );
}
