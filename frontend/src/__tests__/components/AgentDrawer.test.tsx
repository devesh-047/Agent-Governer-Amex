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
    executeAction: vi.fn(),
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
    apiModule.api.executeAction.mockResolvedValue({
      decision: 'allow',
      reason_code: 'OK',
      reason: null,
      remaining_budget: 615,
      audit_log_id: 'test-audit-id',
      hash: 'test-hash',
      execution_time_ms: 25,
    });
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

  describe('Test Agent Action section', () => {
    it('pre-populates defaults and executes action successfully', async () => {
      const user = userEvent.setup();

      render(
        <AgentDrawer
          isOpen={true}
          agentId="agent_a_01"
          onClose={() => {}}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('TEST AGENT ACTION')).toBeInTheDocument();
        expect(screen.getByRole('combobox', { name: /Action Type/i })).toHaveValue('refund');
      });

      const executeButton = screen.getByRole('button', { name: /EXECUTE ACTION/i });
      expect(executeButton).toBeEnabled();

      await user.click(executeButton);

      await waitFor(() => {
        expect(apiModule.api.executeAction).toHaveBeenCalled();
        expect(screen.getByText(/ALLOW/i)).toBeInTheDocument();
      });
    });



    it('disables controls when agent is revoked', async () => {
      apiModule.api.getAgent.mockResolvedValue({
        ...mockAgent,
        status: 'REVOKED',
      });

      render(
        <AgentDrawer
          isOpen={true}
          agentId="agent_a_01"
          onClose={() => {}}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('TEST AGENT ACTION')).toBeInTheDocument();
      });

      expect(screen.getByText(/Agent is currently revoked/i)).toBeInTheDocument();
      const executeButton = screen.getByRole('button', { name: /EXECUTE ACTION/i });
      expect(executeButton).toBeDisabled();
    });

    it('shows message for system agents', async () => {
      apiModule.api.getAgent.mockResolvedValue({
        ...mockAgent,
        id: '00000000-0000-0000-0000-000000000001',
        name: 'System Agent',
      });

      render(
        <AgentDrawer
          isOpen={true}
          agentId="00000000-0000-0000-0000-000000000001"
          onClose={() => {}}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('System agents cannot initiate financial actions.')).toBeInTheDocument();
      });
    });
  });
});

