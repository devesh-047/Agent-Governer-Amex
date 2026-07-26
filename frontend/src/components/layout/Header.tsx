import { useState, useEffect } from 'react';
import { Shield, RefreshCw, AlertTriangle, Play } from 'lucide-react';
import { usePolling } from '@/hooks/usePolling';
import { api } from '@/api';

interface HeaderProps {
  onOpenHaltModal?: () => void;
  onRefreshAll?: () => void;
}

export function Header({ onOpenHaltModal, onRefreshAll }: HeaderProps) {
  const [lastUpdated, setLastUpdated] = useState<string>('Just now');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const { data: fleetState, refetch: refetchFleet } = usePolling({
    pollFn: () => api.getFleetState(),
    interval: 2000,
  });

  const isHalted = fleetState?.fleet_halted ?? false;

  useEffect(() => {
    const updateTimestamp = () => {
      const now = new Date();
      setLastUpdated(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    };
    updateTimestamp();
    const interval = setInterval(updateTimestamp, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleManualRefresh = () => {
    setIsRefreshing(true);
    refetchFleet();
    onRefreshAll?.();
    setTimeout(() => {
      setIsRefreshing(false);
      const now = new Date();
      setLastUpdated(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    }, 400);
  };

  return (
    <header className="bg-gradient-to-r from-[#3B0912] via-[#4A0E17] to-[#59101E] border-b border-[#631522] text-white shadow-md sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* Left: Branding & Subtitle */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-white/10 border border-white/20 flex items-center justify-center shadow-inner">
              <Shield className="w-5 h-5 text-amber-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-bold tracking-wider text-white font-sans">
                  AMEX AGENT GOVERNANCE
                </h1>
                <span className="bg-amber-400/20 text-amber-200 border border-amber-400/30 text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-widest">
                  PROD
                </span>
              </div>
              <p className="text-xs text-rose-200/80 font-normal">
                Governance Layer for Financial Agents
              </p>
            </div>
          </div>

          {/* Right: Runtime Indicator, Timestamp, Refresh & Halt Action */}
          <div className="flex items-center flex-wrap gap-2.5 sm:gap-4">
            {/* Runtime Indicator */}
            <div className="flex items-center gap-2 bg-black/20 border border-white/10 px-2.5 py-1 rounded-md">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-xs font-medium text-emerald-300">Runtime Connected</span>
            </div>

            {/* Timestamp */}
            <div className="hidden md:flex items-center gap-1.5 text-xs text-rose-200/70 font-mono">
              <span>Updated: {lastUpdated}</span>
            </div>

            {/* Refresh Button */}
            <button
              onClick={handleManualRefresh}
              className="bg-white/10 hover:bg-white/20 active:bg-white/30 text-white border border-white/20 px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all shadow-xs focus:outline-none focus:ring-2 focus:ring-white/40 cursor-pointer"
              title="Refresh Dashboard Data"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>

            {/* HALT FLEET / RESUME FLEET Primary Action Button */}
            {onOpenHaltModal && (
              <button
                onClick={onOpenHaltModal}
                className={`font-bold px-3.5 py-1.5 rounded-lg shadow-sm text-xs border flex items-center gap-1.5 transition-all cursor-pointer ${
                  isHalted
                    ? 'bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white border-emerald-500 focus:ring-2 focus:ring-emerald-400/40'
                    : 'bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white border-rose-500 focus:ring-2 focus:ring-rose-400/40'
                }`}
              >
                {isHalted ? (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>RESUME FLEET</span>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>HALT FLEET</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

