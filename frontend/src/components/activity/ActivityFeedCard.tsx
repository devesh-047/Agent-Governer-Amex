import { useRef } from 'react';
import { api } from '@/api';
import { usePolling } from '@/hooks/usePolling';
import type { ActivityEvent } from '@/api/types';

/**
 * ActivityFeedCard - Displays live activity feed
 *
 * Shows last 10 events with:
 * - Timestamp (HH:MM:SS format)
 * - Decision indicator with color (● ALLOW / × DENY)
 * - Agent name
 * - Action type and amount (or reason for deny)
 *
 * Polls every 2 seconds and updates with fade-in animation for new events.
 */
export function ActivityFeedCard() {
  const { data: events, isLoading } = usePolling({
    pollFn: () => api.getActivityFeed(10),
    interval: 2000,
  });

  // Use a ref to track previous events for fade-in animation
  const previousIds = useRef<Set<string>>(new Set());

  // Update previous ids when events change
  if (events) {
    const newIds = new Set(events.map((e) => e.id));
    previousIds.current = newIds;
  }

  return (
    <div className="bg-background-surface border border-border-light rounded-lg shadow-sm p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-semibold text-text-primary">Live Activity</h2>
          <div className="w-2 h-2 rounded-full bg-semantic-success-text animate-pulse" />
        </div>
        <span className="text-xs text-text-tertiary">
          {isLoading ? 'Connecting...' : 'Live'}
        </span>
      </div>

      {/* Feed */}
      <div className="space-y-1.5">
        {isLoading && !events ? (
          <div className="text-text-tertiary text-sm py-4">Loading activity...</div>
        ) : events && events.length > 0 ? (
          events.map((event) => <ActivityEventRow key={event.id} event={event} />)
        ) : (
          <div className="text-text-tertiary text-sm py-4">No activity yet</div>
        )}
      </div>
    </div>
  );
}

interface ActivityEventRowProps {
  event: ActivityEvent;
}

function ActivityEventRow({ event }: ActivityEventRowProps) {
  const time = formatTimestamp(event.timestamp);
  const isAllowed = event.decision === 'allow';

  return (
    <div
      className={`px-3 py-2.5 rounded border-l-2 ${
        isAllowed ? 'border-l-semantic-success-text bg-background-secondary' : 'border-l-semantic-error-text bg-background-secondary'
      } transition-all duration-200 ease-out`}
    >
      <div className="flex items-center gap-3">
        {/* Decision indicator - compact */}
        <span
          className={`text-sm font-bold ${
            isAllowed ? 'text-semantic-success-text' : 'text-semantic-error-text'
          }`}
          aria-label={isAllowed ? 'Request allowed' : 'Request denied'}
          role="status"
        >
          {isAllowed ? '●' : '×'}
        </span>

        {/* Decision label */}
        <span
          className={`text-xs font-semibold w-12 ${
            isAllowed ? 'text-semantic-success-text' : 'text-semantic-error-text'
          }`}
        >
          {isAllowed ? 'ALLOW' : 'DENY'}
        </span>

        {/* Agent name and action - combined for better scanability */}
        <div className="flex-1 min-w-0">
          <div className="text-sm text-text-primary">
            <span className="font-medium">{event.agent_name}</span>
            <span className="text-text-tertiary mx-1">·</span>
            {event.amount > 0 && <span className="text-text-primary">${event.amount} </span>}
            <span className="text-text-secondary">{event.action_type}</span>
            {!isAllowed && event.reason && (
              <span className="text-semantic-error-text ml-1">— {event.reason}</span>
            )}
          </div>
        </div>

        {/* Timestamp - right-aligned */}
        <div className="text-xs text-text-tertiary font-mono">
          {time}
        </div>
      </div>
    </div>
  );
}

/**
 * Format timestamp as HH:MM:SS
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${hours}:${minutes}:${seconds}`;
}
