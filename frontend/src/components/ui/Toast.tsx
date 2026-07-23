import { createRoot } from 'react-dom/client';
import { useEffect, useState } from 'react';

type ToastVariant = 'success' | 'error' | 'info';

interface ToastMessage {
  id: string;
  variant: ToastVariant;
  message: string;
}

let toastRoot: ReturnType<typeof createRoot> | null = null;
let toasts: ToastMessage[] = [];
let listeners: Set<(toasts: ToastMessage[]) => void> = new Set();

function getOrCreateRoot() {
  if (!toastRoot) {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className =
      'fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none';
    document.body.appendChild(container);
    toastRoot = createRoot(container);
  }
  return toastRoot;
}

function notifyListeners() {
  listeners.forEach((listener) => listener([...toasts]));
}

function addToast(variant: ToastVariant, message: string): void {
  const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  toasts.push({ id, variant, message });
  notifyListeners();

  // Auto-dismiss after 3 seconds
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id);
    notifyListeners();
  }, 3000);
}

export const toast = {
  success(message: string): void {
    addToast('success', message);
  },
  error(message: string): void {
    addToast('error', message);
  },
  info(message: string): void {
    addToast('info', message);
  },
};

export function ToastContainer() {
  const [currentToasts, setCurrentToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    listeners.add(setCurrentToasts);
    setCurrentToasts([...toasts]);

    return () => {
      listeners.delete(setCurrentToasts);
    };
  }, []);

  if (currentToasts.length === 0) return null;

  return (
    <>
      {currentToasts.map((t) => (
        <ToastItem key={t.id} variant={t.variant} message={t.message} />
      ))}
    </>
  );
}

interface ToastItemProps {
  variant: ToastVariant;
  message: string;
}

function ToastItem({ variant, message }: ToastItemProps) {
  const styles: Record<ToastVariant, string> = {
    success:
      'bg-semantic-success-bg border-semantic-success-border text-semantic-success-text',
    error: 'bg-semantic-error-bg border-semantic-error-border text-semantic-error-text',
    info: 'bg-brand-primary-bg border-brand-primary text-white',
  };

  const icons: Record<ToastVariant, string> = {
    success: '✓',
    error: '×',
    info: 'ⓘ',
  };

  return (
    <div
      className={`${styles[variant]} border rounded-lg shadow-lg px-4 py-3 pointer-events-auto min-w-[300px] max-w-md animate-slideIn`}
    >
      <div className="flex items-start gap-3">
        <span className="text-lg font-bold">{icons[variant]}</span>
        <p className="text-sm font-medium flex-1">{message}</p>
      </div>
    </div>
  );
}
