import { useState } from 'react';
import { FleetStatusCard } from '@/components/fleet/FleetStatusCard';
import { AgentsSection } from '@/components/agents/AgentsSection';
import { ActivityFeedCard } from '@/components/activity/ActivityFeedCard';
import { AuditIntegrityCard } from '@/components/audit/AuditIntegrityCard';
import { IntegrityResultModal } from '@/components/audit/IntegrityResultModal';
import { AgentDrawer } from '@/components/agents/AgentDrawer';
import { FleetHaltModal } from '@/components/fleet/FleetHaltModal';
import { ScenarioSelector } from '@/components/debug/ScenarioSelector';
import { ToastContainer } from '@/components/ui/Toast';
import { usePolling } from '@/hooks/usePolling';
import { api } from '@/api';
import type { IntegrityStatus } from '@/api/types';

/**
 * Dashboard - Main dashboard page
 *
 * Layout:
 * - Wide screens (>= 1280px): Agents | Activity (side by side)
 * - Narrower screens: Stack vertically
 *
 * Composes all dashboard components:
 * - FleetStatusCard: Fleet-wide status and controls
 * - AgentsSection: List of all agents with status
 * - ActivityFeedCard: Live activity feed
 * - AgentDrawer: Slide-out drawer for agent details
 * - FleetHaltModal: Modal for halt/resume operations
 * - ToastContainer: Toast notifications
 */
export function Dashboard() {
  const [drawerAgentId, setDrawerAgentId] = useState<string | null>(null);
  const [haltModalOpen, setHaltModalOpen] = useState(false);
  const [integrityModalOpen, setIntegrityModalOpen] = useState(false);
  const [integrityResult, setIntegrityResult] = useState<IntegrityStatus | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [agentsRefreshKey, setAgentsRefreshKey] = useState(0);

  // Poll fleet state to determine if halt modal should show halt or resume
  const { data: fleetState, refetch: refetchFleetState } = usePolling({
    pollFn: () => api.getFleetState(),
    interval: 2000,
  });

  const isHalted = fleetState?.fleet_halted ?? false;

  const handleOpenAgentDrawer = (agentId: string) => {
    setDrawerAgentId(agentId);
  };

  const handleCloseDrawer = () => {
    setDrawerAgentId(null);
  };

  const handleOpenHaltModal = () => {
    setHaltModalOpen(true);
  };

  const handleCloseHaltModal = () => {
    setHaltModalOpen(false);
  };

  const handleHaltModalSuccess = () => {
    // Immediately refetch fleet state and agents
    refetchFleetState();
    setAgentsRefreshKey((prev) => prev + 1);
  };

  const handleAgentRevoked = () => {
    // Trigger immediate refresh of agents
    setAgentsRefreshKey((prev) => prev + 1);
  };

  const handleAgentRestored = () => {
    // Trigger immediate refresh of agents
    setAgentsRefreshKey((prev) => prev + 1);
  };

  const handleVerifyIntegrity = async () => {
    setIsVerifying(true);
    setIntegrityModalOpen(true);
    try {
      const result = await api.verifyChain();
      setIntegrityResult(result);
    } catch (error) {
      console.error('Failed to verify chain:', error);
      setIntegrityResult({
        status: 'UNKNOWN',
        last_verified: null,
        total_records: 0,
        break_at: null,
        expected_hash: null,
        actual_hash: null,
      });
    } finally {
      setIsVerifying(false);
    }
  };

  const handleCloseIntegrityModal = () => {
    setIntegrityModalOpen(false);
  };

  return (
    <>
      <div className="py-6 space-y-5">
        {/* Fleet Status Card - Full width, most prominent */}
        <FleetStatusCard onOpenHaltModal={handleOpenHaltModal} />

        {/* Two-column layout for Agents and Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Agents Section */}
          <div className="min-w-0">
            <AgentsSection
              key={agentsRefreshKey}
              onOpenAgentDrawer={handleOpenAgentDrawer}
            />
          </div>

          {/* Activity Feed */}
          <div className="min-w-0">
            <ActivityFeedCard />
          </div>
        </div>

        {/* Audit Integrity Card - Full width, secondary */}
        <AuditIntegrityCard onVerify={handleVerifyIntegrity} />

        {/* Mobile warning - shows on small screens */}
        <div className="md:hidden bg-background-tertiary border border-border-light rounded-lg p-3 text-center">
          <p className="text-text-secondary text-sm">
            For the best experience, use a larger screen (768px or wider).
          </p>
        </div>
      </div>

      {/* Agent Detail Drawer */}
      <AgentDrawer
        isOpen={drawerAgentId !== null}
        agentId={drawerAgentId}
        onClose={handleCloseDrawer}
        onAgentRevoked={handleAgentRevoked}
        onAgentRestored={handleAgentRestored}
      />

      {/* Fleet Halt/Resume Modal */}
      <FleetHaltModal
        isOpen={haltModalOpen}
        isHalted={isHalted}
        onClose={handleCloseHaltModal}
        onSuccess={handleHaltModalSuccess}
      />

      {/* Integrity Result Modal */}
      <IntegrityResultModal
        isOpen={integrityModalOpen}
        onClose={handleCloseIntegrityModal}
        result={integrityResult}
        isLoading={isVerifying}
      />

      {/* Scenario Selector (dev only) */}
      <ScenarioSelector />

      {/* Toast Container */}
      <ToastContainer />
    </>
  );
}
