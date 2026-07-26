import { ShieldCheck, ShieldAlert, Shield, ArrowRight } from 'lucide-react';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Button } from '@/components/ui/Button';
import { usePolling } from '@/hooks/usePolling';
import { api } from '@/api';
import type { IntegrityStatus } from '@/api/types';

const statusVariantMap: Record<IntegrityStatus['status'], 'success' | 'warning' | 'error' | 'neutral'> = {
  VERIFIED: 'success',
  UNKNOWN: 'neutral',
  FAILED: 'error',
};

interface AuditIntegrityCardProps {
  onVerify: () => void;
}

export function AuditIntegrityCard({ onVerify }: AuditIntegrityCardProps) {
  const { data: integrityStatus, isLoading } = usePolling({
    pollFn: () => api.getIntegrityStatus(),
    interval: 10000,
  });

  if (!integrityStatus || isLoading) {
    return (
      <div className="bg-white border border-slate-200/80 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-base font-bold text-slate-900">Audit Trail Integrity</h3>
        </div>
        <div className="text-slate-400 text-sm animate-pulse">Verifying cryptographic chain...</div>
      </div>
    );
  }

  const variant = statusVariantMap[integrityStatus.status];

  const formatLastVerified = (timestamp: string | null) => {
    if (!timestamp) return 'Never';
    const now = new Date();
    const verified = new Date(timestamp);
    const diffMs = now.getTime() - verified.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  };

  const isVerified = integrityStatus.status === 'VERIFIED';
  const isFailed = integrityStatus.status === 'FAILED';

  return (
    <div className="bg-white border border-slate-200/80 rounded-xl p-5 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div className="flex items-center gap-3.5">
        <div
          className={`p-3 rounded-xl ${
            isVerified
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/60'
              : isFailed
              ? 'bg-rose-50 text-rose-700 border border-rose-200/60'
              : 'bg-slate-100 text-slate-600 border border-slate-200'
          }`}
        >
          {isVerified ? (
            <ShieldCheck className="w-6 h-6" />
          ) : isFailed ? (
            <ShieldAlert className="w-6 h-6" />
          ) : (
            <Shield className="w-6 h-6" />
          )}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-slate-900 tracking-tight">
              Cryptographic Audit Chain
            </h3>
            <StatusBadge variant={variant}>
              {integrityStatus.status}
            </StatusBadge>
          </div>
          <p className="text-xs text-slate-500 mt-0.5 font-medium">
            {integrityStatus.total_records.toLocaleString()} audit records tracked
            · Last checked: {formatLastVerified(integrityStatus.last_verified)}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button variant="secondary" size="sm" onClick={onVerify} className="w-full sm:w-auto">
          <span>Run Integrity Audit</span>
          <ArrowRight className="w-3.5 h-3.5 ml-1" />
        </Button>
      </div>

      {isFailed && integrityStatus.break_at && (
        <div className="w-full mt-3 bg-rose-50 border border-rose-200 rounded-lg p-3 text-xs text-rose-700 font-medium">
          Break detected at record #{integrityStatus.break_at}
        </div>
      )}

    </div>
  );
}

