interface ProgressBarProps {
  value: number;
  max: number;
  className?: string;
  color?: 'primary' | 'success' | 'warning' | 'error';
}

const colorStyles = {
  primary: 'bg-[#4A0E17]',
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
  error: 'bg-rose-600',
};

export function ProgressBar({ value, max, className = '', color = 'primary' }: ProgressBarProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div className={`w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200/60 ${className}`}>
      <div
        className={`h-full rounded-full transition-all duration-300 ease-out ${colorStyles[color]}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}

