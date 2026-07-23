import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AuditIntegrityCard } from '@/components/audit/AuditIntegrityCard';
import { usePolling } from '@/hooks/usePolling';

// Mock usePolling hook
vi.mock('@/hooks/usePolling', () => ({
  usePolling: vi.fn(),
}));

// Mock api
vi.mock('@/api', () => ({
  api: {
    getIntegrityStatus: vi.fn(),
    verifyChain: vi.fn(),
  },
}));

const mockOnVerify = vi.fn();

describe('AuditIntegrityCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Integrity VERIFIED/FAILED/UNKNOWN states render', () => {
    it('renders VERIFIED state correctly', () => {
      (usePolling as vi.Mock).mockReturnValue({
        data: {
          status: 'VERIFIED',
          last_verified: '2026-07-23T10:00:00Z',
          total_records: 1250,
          break_at: null,
          expected_hash: null,
          actual_hash: null,
        },
        isLoading: false,
      });

      render(<AuditIntegrityCard onVerify={mockOnVerify} />);

      expect(screen.getByText(/VERIFIED/i)).toBeInTheDocument();
    });

    it('renders FAILED state correctly', () => {
      (usePolling as vi.Mock).mockReturnValue({
        data: {
          status: 'FAILED',
          last_verified: '2026-07-23T09:00:00Z',
          total_records: 1200,
          break_at: 845,
          expected_hash: 'abc123',
          actual_hash: 'def456',
        },
        isLoading: false,
      });

      render(<AuditIntegrityCard onVerify={mockOnVerify} />);

      expect(screen.getByText(/FAILED/i)).toBeInTheDocument();
      expect(screen.getByText(/Break detected at record #845/i)).toBeInTheDocument();
    });

    it('renders UNKNOWN state correctly', () => {
      (usePolling as vi.Mock).mockReturnValue({
        data: {
          status: 'UNKNOWN',
          last_verified: null,
          total_records: 0,
          break_at: null,
          expected_hash: null,
          actual_hash: null,
        },
        isLoading: false,
      });

      render(<AuditIntegrityCard onVerify={mockOnVerify} />);

      expect(screen.getByText(/UNKNOWN/i)).toBeInTheDocument();
    });
  });
});
