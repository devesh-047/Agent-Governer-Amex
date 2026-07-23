interface LoadingProps {
  size?: 'sm' | 'md' | 'lg';
  message?: string;
}

const sizeStyles = {
  sm: 'h-4 w-4 border-2',
  md: 'h-8 w-8 border-2',
  lg: 'h-12 w-12 border-4',
};

export function Loading({ size = 'md', message }: LoadingProps) {
  return (
    <div className="flex flex-col items-center justify-center space-y-4">
      <div
        className={`animate-spin rounded-full border-border-light border-t-brand-primary ${sizeStyles[size]}`}
      />
      {message && <p className="text-text-secondary text-sm">{message}</p>}
    </div>
  );
}

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function LoadingSpinner({ size = 'md', className = '' }: LoadingSpinnerProps) {
  return (
    <div
      className={`animate-spin rounded-full border-border-light border-t-brand-primary ${sizeStyles[size]} ${className}`}
    />
  );
}

interface InlineLoadingProps {
  message?: string;
}

export function InlineLoading({ message = 'Loading...' }: InlineLoadingProps) {
  return (
    <div className="flex items-center space-x-2 text-text-secondary">
      <LoadingSpinner size="sm" />
      <span className="text-sm">{message}</span>
    </div>
  );
}
