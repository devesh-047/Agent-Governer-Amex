import { ReactNode } from 'react';

type StatusVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral';

interface StatusBadgeProps {
  variant: StatusVariant;
  children: ReactNode;
}

const variantStyles: Record<StatusVariant, string> = {
  success: 'bg-semantic-success-bg text-semantic-success-text border-semantic-success-border',
  warning: 'bg-semantic-warning-bg text-semantic-warning-text border-semantic-warning-border',
  error: 'bg-semantic-error-bg text-semantic-error-text border-semantic-error-border',
  info: 'bg-semantic-info-bg text-semantic-info-text border-semantic-info-border',
  neutral: 'bg-background-tertiary text-text-tertiary border-border-medium',
};

export function StatusBadge({ variant, children }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded-md border ${variantStyles[variant]}`}
    >
      {children}
    </span>
  );
}
