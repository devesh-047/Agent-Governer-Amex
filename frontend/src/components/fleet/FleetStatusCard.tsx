import { api } from '@/api';
import { usePolling } from '@/hooks/usePolling';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/ui/StatusBadge';

interface LastDecisionInfo {
  timestamp: string;
  decision: 'allow' | 'deny';
  actionType: string;
  amount: number;
  timeAgo: string;
}

interface FleetStatusCardProps {
  onOpenHaltModal: () => void;
}

/**
 * FleetStatusCard - Displays fleet-wide system status
 *
 * Shows:
 * - Fleet state (running/halted) with visual indicator
 * - Agent counts (active/revoked)
 * - Most recent decision from the system
 * - Halt/Resume Fleet button (opens modal)
 * - Refresh indicator showing polling is active
 */
export function FleetStatusCard({ onOpenHaltModal }: FleetStatusCardProps) {
  const { data: fleetState, isLoading: fleetLoading } = usePolling({
    pollFn: () => api.getFleetState(),
    interval: 2000,
  });

  const { data: agents } = usePolling({
    pollFn: () => api.getAgents(),
    interval: 2000,
  });

  const { data: activityFeed } = usePolling({
    pollFn: () => api.getActivityFeed(1),
    interval: 2000,
  });

  // Calculate agent counts
  const activeCount = agents?.filter((a) => a.status === 'active').length ?? 0;
  const revokedCount = agents?.filter((a) => a.status === 'revoked').length ?? 0;

  // Extract last decision info
  const lastDecision: LastDecisionInfo | null = activityFeed && activityFeed.length > 0
    ? {
        timestamp: activityFeed[0].timestamp,
        decision: activityFeed[0].decision,
        actionType: activityFeed[0].action_type,
        amount: activityFeed[0].amount,
        timeAgo: formatTimeAgo(activityFeed[0].timestamp),
      }
    : null;

  const isHalted = fleetState?.fleet_halted ?? false;
  const isOperational = !isHalted;

  return (
    <div className="bg-background-surface border border-border-light rounded-lg shadow-sm p-5">
      {/* Compact header with status */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-semibold text-text-primary">Fleet & System</h2>
          <div className="w-px h-4 bg-border-light" />
          <span className="text-xs text-text-tertiary">
            {fleetLoading ? 'Connecting...' : 'Refresh 2s'}
          </span>
        </div>
      </div>

      {/* Main status display - most prominent */}
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-border-light">
        <div className="flex items-center gap-3">
          {isOperational ? (
            <>
              <div className="w-3 h-3 rounded-full bg-semantic-success-text animate-pulse" />
              <span className="text-lg font-semibold text-text-primary tracking-tight">
                FLEET OPERATIONAL
              </span>
            </>
          ) : (
            <>
              <div className="w-3 h-3 rounded-full bg-semantic-error-text" />
              <span className="text-lg font-semibold text-text-primary tracking-tight">
                FLEET HALTED
              </span>
            </>
          )}
        </div>
        <Button
          variant={isOperational ? 'danger' : 'primary'}
          size="sm"
          onClick={onOpenHaltModal}
        >
          {isOperational ? 'HALT FLEET' : 'RESUME FLEET'}
        </Button>
      </div>

      {/* Compact details */}
      <div className="flex items-center gap-6 text-sm">
        <div className="flex items-center gap-2">
          <span className="text-text-tertiary">Agents:</span>
          <span className="font-medium text-text-primary">{activeCount}</span>
          <span className="text-text-tertiary">active</span>
          {revokedCount > 0 && (
            <>
              <span className="text-text-tertiary">·</span>
              <span className="font-medium text-text-primary">{revokedCount}</span>
              <span className="text-text-tertiary">revoked</span>
            </>
          )}
        </div>

        {lastDecision && (
          <div className="flex items-center gap-2">
            <span className="text-text-tertiary">Last:</span>
            <span
              className={`font-medium ${
                lastDecision.decision === 'allow'
                  ? 'text-semantic-success-text'
                  : 'text-semantic-error-text'
              }`}
            >
              {lastDecision.decision.toUpperCase()}
            </span>
            {lastDecision.amount > 0 && (
              <span className="text-text-primary">${lastDecision.amount.toFixed(0)}</span>
            )}
            <span className="text-text-tertiary text-xs">{lastDecision.timeAgo}</span>
          </div>
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
    return `${diff} second${diff !== 1 ? 's' : ''} ago`;
  }

  const minutes = Math.floor(diff / 60);
  if (minutes < 60) {
    return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
  }

  const hours = Math.floor(minutes / 60);
  return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
}
