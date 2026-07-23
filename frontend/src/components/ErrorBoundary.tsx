import { Component, ReactNode } from 'react';
import { Button } from '@/components/ui/Button';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: { componentStack: string }) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: undefined });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background-primary flex items-center justify-center p-4">
          <div className="bg-background-surface border border-border-light rounded-lg p-8 max-w-md w-full">
            <div className="text-center space-y-6">
              {/* Error icon */}
              <div className="flex justify-center">
                <div className="w-16 h-16 bg-semantic-error-bg rounded-full flex items-center justify-center">
                  <svg
                    className="w-8 h-8 text-semantic-error-text"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                </div>
              </div>

              {/* Error message */}
              <div>
                <h1 className="text-xl font-semibold text-text-primary mb-2">
                  Something went wrong
                </h1>
                <p className="text-text-secondary text-sm">
                  An unexpected error occurred. Please try refreshing the page.
                </p>
              </div>

              {/* Error details (in development) */}
              {import.meta.env.DEV && this.state.error && (
                <div className="bg-background-tertiary rounded-md p-4 text-left">
                  <p className="text-text-tertiary text-xs font-mono break-all">
                    {this.state.error.message}
                  </p>
                </div>
              )}

              {/* Reset button */}
              <Button variant="primary" onClick={this.handleReset} className="w-full">
                Refresh Page
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
