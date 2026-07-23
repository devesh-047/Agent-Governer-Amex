import { useState, useEffect } from 'react';
import { api } from '@/api';
import { toast } from '@/components/ui/Toast';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/ui/StatusBadge';

interface FleetHaltModalProps {
  isOpen: boolean;
  isHalted: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

/**
 * FleetHaltModal - Modal for fleet halt/resume operations
 *
 * Features:
 * - Type "HALT" confirmation (case-insensitive) for halt operation
 * - Simple confirmation for resume operation
 * - ESC key closes modal
 * - Visual feedback for current fleet state
 */
export function FleetHaltModal({ isOpen, isHalted, onClose, onSuccess }: FleetHaltModalProps) {
  const [confirmText, setConfirmText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const canConfirm = confirmText.trim().toUpperCase() === 'HALT';

  // Reset form when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setConfirmText('');
      setIsSubmitting(false);
    }
  }, [isOpen]);

  // ESC key closes modal
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [isOpen, onClose]);

  const handleHaltFleet = async () => {
    if (!canConfirm || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await api.haltFleet();
      toast.success('Fleet halted successfully');
      setConfirmText('');
      onClose();
      onSuccess?.();
    } catch (error) {
      console.error('Failed to halt fleet:', error);
      toast.error('Failed to halt fleet');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResumeFleet = async () => {
    if (isSubmitting) return;

    setIsSubmitting(true);
    try {
      await api.resumeFleet();
      toast.success('Fleet resumed successfully');
      onClose();
      onSuccess?.();
    } catch (error) {
      console.error('Failed to resume fleet:', error);
      toast.error('Failed to resume fleet');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal content */}
      <div className="relative bg-background-surface rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-text-tertiary hover:text-text-secondary transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {!isHalted ? (
          <>
            {/* Halt Confirmation */}
            <div className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-semantic-error-bg flex items-center justify-center">
                  <svg className="w-6 h-6 text-semantic-error-text" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-text-primary">HALT FLEET</h2>
              </div>

              <p className="text-text-secondary">
                This will immediately stop ALL agents from processing requests. Every agent
                action will be denied until the fleet is resumed.
              </p>

              <p className="text-sm text-text-secondary">This action is logged to the audit trail.</p>

              <div className="border-t border-border-light pt-4">
                <label htmlFor="halt-confirm-input" className="block text-sm text-text-secondary mb-2">
                  Type "HALT" to confirm:
                </label>
                <input
                  id="halt-confirm-input"
                  type="text"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  placeholder="HALT"
                  className="w-full px-4 py-2 bg-background-secondary border border-border-medium rounded-lg text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-semantic-error-border focus:border-transparent"
                  autoFocus
                />
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
                  CANCEL
                </Button>
                <Button
                  variant="danger"
                  onClick={handleHaltFleet}
                  disabled={!canConfirm || isSubmitting}
                >
                  {isSubmitting ? 'HALTING...' : 'CONFIRM HALT'}
                </Button>
              </div>
            </div>
          </>
        ) : (
          <>
            {/* Resume Confirmation */}
            <div className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-brand-primary-bg flex items-center justify-center">
                  <svg className="w-6 h-6 text-brand-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-text-primary">RESUME FLEET</h2>
              </div>

              <p className="text-text-secondary">
                You are about to RESUME the halted fleet:
              </p>

              <div className="bg-background-secondary rounded-lg p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Current State:</span>
                  <StatusBadge variant="error">FLEET HALTED</StatusBadge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">After Resume:</span>
                  <StatusBadge variant="success">OPERATIONAL</StatusBadge>
                </div>
              </div>

              <div className="bg-background-tertiary rounded p-3 text-xs text-text-secondary space-y-1">
                <p className="font-medium text-text-primary">WHAT THIS MEANS:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>The fleet will return to OPERATIONAL status</li>
                  <li>Agents that are ACTIVE (not REVOKED) will process requests again</li>
                  <li>Agents that are REVOKED will remain blocked</li>
                  <li>This action is logged to the audit trail</li>
                </ul>
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
                  CANCEL
                </Button>
                <Button
                  variant="primary"
                  onClick={handleResumeFleet}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'RESUMING...' : '▶ CONFIRM RESUME'}
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
