import { ReactNode, ButtonHTMLAttributes } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: 'bg-brand-primary text-white hover:bg-brand-secondary focus:ring-2 focus:ring-brand-primary',
  secondary: 'bg-background-tertiary text-text-primary border border-border-medium hover:bg-background-secondary',
  danger: 'bg-semantic-error-text text-white hover:bg-red-700 focus:ring-2 focus:ring-semantic-error-border',
  ghost: 'bg-transparent text-text-secondary hover:bg-background-tertiary hover:text-text-primary',
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2',
  lg: 'px-6 py-3 text-lg',
};

const baseStyles = 'rounded-md font-medium transition-duration-normal transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background-primary disabled:opacity-50 disabled:cursor-not-allowed';

export function Button({ variant = 'primary', size = 'md', children, className = '', ...props }: ButtonProps) {
  return (
    <button
      className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
