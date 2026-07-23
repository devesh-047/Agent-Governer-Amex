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

const statusLabelMap: Record<IntegrityStatus['status'], string> = {
  VERIFIED: 'VERIFIED',
  UNKNOWN: 'UNKNOWN',
  FAILED: 'FAILED',
};

interface AuditIntegrityCardProps {
  onVerify: () => void;
}

export function AuditIntegrityCard({ onVerify }: AuditIntegrityCardProps) {
  const { data: integrityStatus, isLoading } = usePolling({
    pollFn: () => api.getIntegrityStatus(),
    interval: 10000, // 10 seconds - less frequent than activity feed
  });

  if (!integrityStatus || isLoading) {
    return (
      <div className="bg-background-surface border border-border-light rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-text-primary">Audit Integrity</h3>
        </div>
        <div className="flex items-center justify-center py-6">
          <div className="animate-pulse flex space-x-2">
            <div className="w-2 h-2 bg-text-tertiary rounded-full animate-bounce" />
            <div className="w-2 h-2 bg-text-tertiary rounded-full animate-bounce delay-100" />
            <div className="w-2 h-2 bg-text-tertiary rounded-full animate-bounce delay-200" />
          </div>
        </div>
      </div>
    );
  }

  const variant = statusVariantMap[integrityStatus.status];
  const statusLabel = statusLabelMap[integrityStatus.status];

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

  const statusIcon = integrityStatus.status === 'VERIFIED'
    ? '●'
    : integrityStatus.status === 'FAILED'
    ? '×'
    : '○';

  return (
    <div className="bg-background-surface border border-border-light rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-text-primary">Audit Integrity</h3>
        <Button
          variant="secondary"
          size="sm"
          onClick={onVerify}
          aria-label="Verify audit chain integrity now"
        >
          Verify Now
        </Button>
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <StatusBadge variant={variant}>
            <span className="mr-1">{statusIcon}</span>
            {statusLabel}
          </StatusBadge>
          <span className="text-xs text-text-tertiary">
            {formatLastVerified(integrityStatus.last_verified)}
          </span>
        </div>

        <div className="flex items-center gap-4 text-sm">
          <span className="text-text-tertiary">{integrityStatus.total_records.toLocaleString()} records</span>
        </div>

        {integrityStatus.status === 'FAILED' && integrityStatus.break_at && (
          <div className="bg-semantic-error-bg border border-semantic-error-border rounded-md p-3">
            <p className="text-semantic-error-text text-sm font-medium">
              Break detected at record #{integrityStatus.break_at}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
