import { Users, ShieldCheck, ShieldAlert, Activity, DollarSign, ArrowUpRight } from 'lucide-react';
import { api } from '@/api';
import { usePolling } from '@/hooks/usePolling';

interface FleetStatusCardProps {
  onOpenHaltModal: () => void;
}

/**
 * FleetStatusCard (Overview KPI Cards)
 *
 * Displays four compact KPI cards:
 * 1. Total Agents (Active vs Revoked breakdown)
 * 2. Fleet Status (Operational / Halted with quick action)
 * 3. Allow Rate (Percentage derived from live activity feed)
 * 4. Total Spend Today (Summed across all agent daily budgets)
 */
export function FleetStatusCard({ onOpenHaltModal }: FleetStatusCardProps) {
  const { data: fleetState } = usePolling({
    pollFn: () => api.getFleetState(),
    interval: 2000,
  });

  const { data: agents } = usePolling({
    pollFn: () => api.getAgents(),
    interval: 2000,
  });

  const { data: activityFeed } = usePolling({
    pollFn: () => api.getActivityFeed(50),
    interval: 2000,
  });

  const isHalted = fleetState?.fleet_halted ?? false;
  const isOperational = !isHalted;

  // 1. Total Agents Metrics
  const totalAgents = agents?.length ?? 0;
  const activeCount = agents?.filter((a) => a.status === 'active' || a.runtime_status === 'active').length ?? 0;
  const revokedCount = agents?.filter((a) => a.status === 'revoked' || a.runtime_status === 'revoked').length ?? 0;

  // 2. Allow Rate Metrics
  const totalEvents = activityFeed?.length ?? 0;
  const allowedEvents = activityFeed?.filter((e) => e.decision === 'allow').length ?? 0;
  const allowRateFormatted = totalEvents > 0
    ? `${((allowedEvents / totalEvents) * 100).toFixed(1)}%`
    : '100%';

  // 3. Spend Metrics
  const totalSpendToday = agents?.reduce((sum, agent) => {
    const spent = agent.daily_cap - (agent.remaining_budget ?? agent.daily_cap);
    return sum + Math.max(0, spent);
  }, 0) ?? 0;

  const totalDailyCap = agents?.reduce((sum, agent) => sum + agent.daily_cap, 0) ?? 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* KPI 1: Total Agents */}
      <div className="bg-white border border-slate-200/80 rounded-xl p-4 shadow-sm hover:shadow-md transition-all">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Total Agents
          </span>
          <div className="p-2 rounded-lg bg-rose-50 text-[#4A0E17]">
            <Users className="w-4 h-4" />
          </div>
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-2xl font-extrabold text-slate-900 tracking-tight">
            {totalAgents}
          </span>
          <div className="flex items-center gap-1.5 text-xs font-semibold">
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              {activeCount} Active
            </span>
            {revokedCount > 0 && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
                {revokedCount} Revoked
              </span>
            )}
          </div>
        </div>
        <p className="text-[11px] text-slate-400 mt-2 font-medium">
          Configured governance runtime agents
        </p>
      </div>

      {/* KPI 2: Fleet Status */}
      <div
        className={`border rounded-xl p-4 shadow-sm hover:shadow-md transition-all ${
          isHalted
            ? 'bg-rose-50/40 border-rose-200'
            : 'bg-white border-slate-200/80'
        }`}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Fleet Status
          </span>
          <div
            className={`p-2 rounded-lg ${
              isHalted ? 'bg-rose-100 text-rose-700' : 'bg-emerald-50 text-emerald-700'
            }`}
          >
            {isHalted ? <ShieldAlert className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
          </div>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                isHalted ? 'bg-rose-600' : 'bg-emerald-500 animate-pulse'
              }`}
            />
            <span
              className={`text-lg font-extrabold tracking-tight ${
                isHalted ? 'text-rose-700' : 'text-emerald-700'
              }`}
            >
              {isHalted ? 'HALTED' : 'OPERATIONAL'}
            </span>
          </div>
          <button
            onClick={onOpenHaltModal}
            className={`text-xs font-bold px-2.5 py-1 rounded-md transition-colors cursor-pointer border ${
              isOperational
                ? 'bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100'
                : 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
            }`}
          >
            {isOperational ? 'Halt Fleet' : 'Resume'}
          </button>
        </div>
        <p className="text-[11px] text-slate-400 mt-2 font-medium">
          {isOperational ? 'All governance policies enforcing' : 'All agent actions currently blocked'}
        </p>
      </div>

      {/* KPI 3: Allow Rate */}
      <div className="bg-white border border-slate-200/80 rounded-xl p-4 shadow-sm hover:shadow-md transition-all">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Allow Rate
          </span>
          <div className="p-2 rounded-lg bg-emerald-50 text-emerald-700">
            <Activity className="w-4 h-4" />
          </div>
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-2xl font-extrabold text-slate-900 tracking-tight">
            {allowRateFormatted}
          </span>
          <span className="text-xs font-semibold text-slate-500 flex items-center gap-0.5">
            {allowedEvents} / {totalEvents} actions
          </span>
        </div>
        <p className="text-[11px] text-slate-400 mt-2 font-medium">
          Evaluated from recent policy decisions
        </p>
      </div>

      {/* KPI 4: Total Spend Today */}
      <div className="bg-white border border-slate-200/80 rounded-xl p-4 shadow-sm hover:shadow-md transition-all">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Total Spend Today
          </span>
          <div className="p-2 rounded-lg bg-amber-50 text-amber-700">
            <DollarSign className="w-4 h-4" />
          </div>
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-2xl font-extrabold text-slate-900 tracking-tight">
            ${Math.round(totalSpendToday).toLocaleString()}
          </span>
          <span className="text-xs font-semibold text-slate-500">
            Cap: ${totalDailyCap.toLocaleString()}
          </span>
        </div>
        <p className="text-[11px] text-slate-400 mt-2 font-medium">
          Cumulative daily agent spending
        </p>
      </div>
    </div>
  );
}

