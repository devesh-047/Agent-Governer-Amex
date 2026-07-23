interface ProgressBarProps {
  value: number;
  max: number;
  className?: string;
  color?: 'primary' | 'success' | 'warning' | 'error';
}

const colorStyles = {
  primary: 'bg-brand-primary',
  success: 'bg-semantic-success-text',
  warning: 'bg-semantic-warning-text',
  error: 'bg-semantic-error-text',
};

export function ProgressBar({ value, max, className = '', color = 'primary' }: ProgressBarProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div className={`w-full bg-background-tertiary rounded-full h-2 overflow-hidden ${className}`}>
      <div
        className={`h-full rounded-full transition-all duration-300 ease-out ${colorStyles[color]}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}
