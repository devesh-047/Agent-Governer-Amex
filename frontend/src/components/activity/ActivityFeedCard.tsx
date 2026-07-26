import { useRef } from 'react';
import { CheckCircle2, XCircle, Activity, Radio } from 'lucide-react';
import { api } from '@/api';
import { usePolling } from '@/hooks/usePolling';
import type { ActivityEvent } from '@/api/types';

/**
 * ActivityFeedCard - Displays live activity feed
 *
 * Shows last 10 events with:
 * - Decision icon & indicator (ALLOW: CheckCircle2 emerald / DENY: XCircle rose)
 * - Agent name and action type
 * - Amount or deny reason
 * - Right-aligned timestamp (HH:MM:SS format)
 * - Polls every 2 seconds
 */
export function ActivityFeedCard() {
  const { data: events, isLoading } = usePolling({
    pollFn: () => api.getActivityFeed(10),
    interval: 2000,
  });

  const previousIds = useRef<Set<string>>(new Set());

  if (events) {
    const newIds = new Set(events.map((e) => e.id));
    previousIds.current = newIds;
  }

  return (
    <div className="bg-white border border-slate-200/80 rounded-xl shadow-sm p-5 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-emerald-50 text-emerald-700">
            <Radio className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900 tracking-tight">Live Activity Feed</h2>
            <p className="text-xs text-slate-500 font-normal">Real-time policy decision stream</p>
          </div>
        </div>
        <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200/60 flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
          {isLoading ? 'Connecting...' : 'Polling (2s)'}
        </span>
      </div>

      {/* Feed List */}
      <div className="space-y-2 flex-1 overflow-y-auto pr-0.5">
        {isLoading && !events ? (
          <div className="text-slate-400 text-sm py-8 text-center animate-pulse">
            Connecting to decision stream...
          </div>
        ) : events && events.length > 0 ? (
          events.map((event) => <ActivityEventRow key={event.id} event={event} />)
        ) : (
          <div className="text-slate-400 text-sm py-8 text-center">No activity recorded yet</div>
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
      className={`p-3 rounded-lg border transition-all duration-200 ${
        isAllowed
          ? 'bg-slate-50/80 border-slate-200/80 hover:bg-slate-50'
          : 'bg-rose-50/40 border-rose-200/80 hover:bg-rose-50/60'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        {/* Left: Icon + Decision Badge + Action info */}
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          {/* Decision Icon */}
          <div className="shrink-0">
            {isAllowed ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            ) : (
              <XCircle className="w-5 h-5 text-rose-600" />
            )}
          </div>

          {/* Decision Tag */}
          <span
            className={`text-[11px] font-extrabold px-2 py-0.5 rounded tracking-wide shrink-0 ${
              isAllowed
                ? 'bg-emerald-100/80 text-emerald-800'
                : 'bg-rose-100/80 text-rose-800'
            }`}
          >
            {isAllowed ? 'ALLOW' : 'DENY'}
          </span>

          {/* Agent & Action details */}
          <div className="min-w-0 flex-1 text-xs">
            <span className="font-bold text-slate-900 truncate">{event.agent_name}</span>
            <span className="text-slate-400 mx-1 font-mono">·</span>
            <span className="text-slate-700 font-medium">{event.action_type}</span>
            {event.amount > 0 && (
              <span className="font-bold text-slate-900 ml-1">
                (${event.amount.toLocaleString()})
              </span>
            )}
            {!isAllowed && event.reason && (
              <p className="text-rose-700 text-[11px] font-medium mt-0.5 truncate">
                Reason: {event.reason}
              </p>
            )}
          </div>
        </div>

        {/* Right: Monospace Timestamp */}
        <div className="text-xs font-mono text-slate-400 shrink-0 font-medium bg-white/80 px-2 py-0.5 rounded border border-slate-200/60">
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

