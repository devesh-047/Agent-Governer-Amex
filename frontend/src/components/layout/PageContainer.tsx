import { ReactNode } from 'react';

interface PageContainerProps {
  children: ReactNode;
}

export function PageContainer({ children }: PageContainerProps) {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6">
      {children}
    </div>
  );
}
