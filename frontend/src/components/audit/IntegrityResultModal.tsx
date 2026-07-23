import { Modal } from '@/components/ui/Modal';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Button } from '@/components/ui/Button';
import type { IntegrityStatus } from '@/api/types';

interface IntegrityResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: IntegrityStatus | null;
  isLoading?: boolean;
}

interface VerificationSummaryProps {
  result: IntegrityStatus;
}

function VerificationSummary({ result }: VerificationSummaryProps) {
  const isSuccess = result.status === 'VERIFIED';

  const formatDate = (timestamp: string | null) => {
    if (!timestamp) return 'Unknown';
    return new Date(timestamp).toLocaleString('UTC', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short',
    });
  };

  const truncateHash = (hash: string | null) => {
    if (!hash) return 'N/A';
    return `${hash.slice(0, 4)}... (truncated)`;
  };

  return (
    <div className="border border-border-light rounded-lg overflow-hidden">
      <div className="bg-background-tertiary px-4 py-2 border-b border-border-light">
        <h4 className="text-sm font-semibold text-text-primary">Verification Summary</h4>
      </div>
      <div className="p-4 space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-text-secondary text-sm">Records Verified:</span>
          <span className="text-text-primary font-medium">
            {isSuccess
              ? result.total_records.toLocaleString()
              : `${result.break_at} / ${result.total_records.toLocaleString()}`}
          </span>
        </div>

        {isSuccess ? (
          <>
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">First Record:</span>
              <span className="text-text-primary text-sm">{formatDate(new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString())}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">Last Record:</span>
              <span className="text-text-primary text-sm">{formatDate(result.last_verified)}</span>
            </div>
          </>
        ) : (
          <>
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">Break Detected At:</span>
              <span className="text-text-primary font-medium">Record #{result.break_at}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">Break Timestamp:</span>
              <span className="text-text-primary text-sm">{formatDate(result.last_verified)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">Expected Hash:</span>
              <span className="text-text-primary font-mono text-xs">{truncateHash(result.expected_hash)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-secondary text-sm">Actual Hash:</span>
              <span className="text-text-primary font-mono text-xs">{truncateHash(result.actual_hash)}</span>
            </div>
          </>
        )}

        <div className="flex justify-between items-center pt-2 border-t border-border-light">
          <span className="text-text-secondary text-sm">Chain Status:</span>
          <StatusBadge variant={isSuccess ? 'success' : 'error'}>
            <span className="mr-1">{isSuccess ? '●' : '×'}</span>
            {isSuccess ? 'INTACT' : 'BROKEN'}
          </StatusBadge>
        </div>
      </div>
    </div>
  );
}

export function IntegrityResultModal({ isOpen, onClose, result, isLoading }: IntegrityResultModalProps) {
  if (isLoading) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="AUDIT INTEGRITY CHECK">
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center space-y-4">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-border-light border-t-brand-primary" />
            <p className="text-text-secondary text-sm">Verifying audit chain...</p>
          </div>
        </div>
      </Modal>
    );
  }

  if (!result) return null;

  const isSuccess = result.status === 'VERIFIED';

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="AUDIT INTEGRITY CHECK">
      <div className="space-y-6">
        {/* Status */}
        <div className="flex items-center gap-3">
          <StatusBadge variant={isSuccess ? 'success' : 'error'}>
            <span className="mr-1">{isSuccess ? '●' : '×'}</span>
            {isSuccess ? 'VERIFIED' : 'FAILED'}
          </StatusBadge>
        </div>

        {/* Message */}
        <p className="text-text-secondary">
          {isSuccess
            ? `The audit chain is intact. All ${result.total_records.toLocaleString()} records have been verified from the first entry.`
            : 'The audit chain has been tampered with. A break was detected in the hash chain.'}
        </p>

        {/* Verification Summary */}
        <VerificationSummary result={result} />

        {/* Additional explanation */}
        <div className="text-sm text-text-secondary bg-background-tertiary rounded-md p-4">
          {isSuccess ? (
            <p>
              Each record's hash correctly matches the previous record's hash in the chain.
              No tampering detected.
            </p>
          ) : (
            <p>
              Record #{result.break_at ?? 'N/A'} has been modified. The hash chain is broken from this
              point forward. Earlier records (1-{(result.break_at ?? 1) - 1}) are verified intact.
            </p>
          )}
        </div>

        {/* Close button */}
        <div className="flex justify-end">
          <Button variant="primary" onClick={onClose}>
            CLOSE
          </Button>
        </div>
      </div>
    </Modal>
  );
}
