import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AgentDrawer } from '@/components/agents/AgentDrawer';
import * as apiModule from '@/api';

// Mock api
vi.mock('@/api', () => ({
  api: {
    getAgent: vi.fn(),
    getActivityFeed: vi.fn(),
    revokeAgent: vi.fn(),
    restoreAgent: vi.fn(),
  },
}));

// Mock toast
vi.mock('@/components/ui/Toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const mockAgent = {
  id: 'agent_a_01',
  name: 'Payment Refund Bot',
  description: 'Handles customer refund requests',
  status: 'ACTIVE',
  daily_cap: 1000,
  remaining_budget: 715,
  max_single_amount: 200,
  permissions: ['refund', 'limit_adjustment'],
  last_decision: null,
  fleet_halted: false,
};

describe('AgentDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiModule.api.getAgent.mockResolvedValue(mockAgent);
    apiModule.api.getActivityFeed.mockResolvedValue([]);
  });

  describe('Revoke changes only target agent', () => {
    it('revokes only the intended agent', async () => {
      const user = userEvent.setup();
      const onAgentRevoked = vi.fn();

      render(
        <AgentDrawer
          isOpen={true}
          agentId="agent_a_01"
          onClose={() => {}}
          onAgentRevoked={onAgentRevoked}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('AGENT DETAILS')).toBeInTheDocument();
      });

      // Click revoke button
      const revokeButton = screen.getByRole('button', { name: /revoke agent/i });
      await user.click(revokeButton);

      // Should show confirmation heading
      expect(screen.getAllByText(/CONFIRM REVOCATION/i)).toHaveLength(2);

      // Confirm revoke - use the button text exactly
      const confirmButtons = screen.getAllByRole('button');
      const confirmButton = confirmButtons.find(btn => btn.textContent === 'CONFIRM REVOCATION');
      expect(confirmButton).toBeDefined();
      await user.click(confirmButton!);

      await waitFor(() => {
        expect(apiModule.api.revokeAgent).toHaveBeenCalledWith('agent_a_01');
        expect(apiModule.api.revokeAgent).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('Restore changes only intended agent', () => {
    it('restores only the intended agent', async () => {
      const user = userEvent.setup();
      const onAgentRestored = vi.fn();

      apiModule.api.getAgent.mockResolvedValue({
        ...mockAgent,
        id: 'agent_b_02',
        name: 'Another Agent',
        status: 'REVOKED',
      });

      render(
        <AgentDrawer
          isOpen={true}
          agentId="agent_b_02"
          onClose={() => {}}
          onAgentRestored={onAgentRestored}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('AGENT DETAILS')).toBeInTheDocument();
      });

      // Click restore button
      const restoreButton = screen.getByRole('button', { name: /restore agent/i });
      await user.click(restoreButton);

      await waitFor(() => {
        expect(apiModule.api.restoreAgent).toHaveBeenCalledWith('agent_b_02');
        expect(apiModule.api.restoreAgent).toHaveBeenCalledTimes(1);
      });
    });
  });
});
