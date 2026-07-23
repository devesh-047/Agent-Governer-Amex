import { useState, useEffect, useCallback, useRef } from 'react';

interface UsePollingOptions<T> {
  /**
   * The async function to call on each poll
   */
  pollFn: () => Promise<T>;

  /**
   * Polling interval in milliseconds
   * @default 2000
   */
  interval?: number;

  /**
   * Whether polling is enabled
   * @default true
   */
  enabled?: boolean;

  /**
   * Callback when polling encounters an error
   */
  onError?: (error: Error) => void;
}

interface UsePollingResult<T> {
  /**
   * The current data from the latest successful poll
   */
  data: T | null;

  /**
   * Whether a poll is currently in flight
   */
  isLoading: boolean;

  /**
   * The last error encountered (if any)
   */
  error: Error | null;

  /**
   * Manually trigger a poll outside the normal interval
   */
  refetch: () => Promise<void>;

  /**
   * The number of successful polls completed
   */
  pollCount: number;
}

/**
 * Custom hook for polling data at regular intervals
 *
 * Features:
 * - Configurable interval (default 2000ms)
 * - Automatic cleanup on unmount
 * - Error handling without stopping the poll
 * - Manual refetch capability
 * - Loading state tracking
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = usePolling({
 *   pollFn: () => api.getFleetState(),
 *   interval: 2000,
 *   enabled: true,
 *   onError: (err) => console.error('Poll error:', err),
 * });
 * ```
 */
export function usePolling<T>({
  pollFn,
  interval = 2000,
  enabled = true,
  onError,
}: UsePollingOptions<T>): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [pollCount, setPollCount] = useState(0);

  // Use refs to avoid stale closures in setTimeout
  const enabledRef = useRef(enabled);
  const pollFnRef = useRef(pollFn);
  const onErrorRef = useRef(onError);

  // Keep refs in sync with props
  useEffect(() => {
    enabledRef.current = enabled;
    pollFnRef.current = pollFn;
    onErrorRef.current = onError;
  }, [enabled, pollFn, onError]);

  const performPoll = useCallback(async () => {
    if (!enabledRef.current) return;

    try {
      const result = await pollFnRef.current();
      setData(result);
      setError(null);
      setPollCount((prev) => prev + 1);
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      onErrorRef.current?.(error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Manual refetch function
  const refetch = useCallback(async () => {
    setIsLoading(true);
    await performPoll();
  }, [performPoll]);

  // Set up polling interval
  useEffect(() => {
    if (!enabled) return;

    // Initial poll
    setIsLoading(true);
    performPoll();

    // Set up interval
    const intervalId = setInterval(() => {
      performPoll();
    }, interval);

    // Cleanup
    return () => {
      clearInterval(intervalId);
    };
  }, [interval, enabled, performPoll]);

  return {
    data,
    isLoading,
    error,
    refetch,
    pollCount,
  };
}
