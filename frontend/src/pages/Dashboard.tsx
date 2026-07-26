import { useState } from 'react';
import { Header } from '@/components/layout/Header';
import { PageContainer } from '@/components/layout/PageContainer';
import { FleetStatusCard } from '@/components/fleet/FleetStatusCard';
import { AgentsSection } from '@/components/agents/AgentsSection';
import { ActivityFeedCard } from '@/components/activity/ActivityFeedCard';
import { AuditIntegrityCard } from '@/components/audit/AuditIntegrityCard';
import { IntegrityResultModal } from '@/components/audit/IntegrityResultModal';
import { AgentDrawer } from '@/components/agents/AgentDrawer';
import { FleetHaltModal } from '@/components/fleet/FleetHaltModal';
import { ToastContainer } from '@/components/ui/Toast';
import { usePolling } from '@/hooks/usePolling';
import { api } from '@/api';
import type { IntegrityStatus } from '@/api/types';

/**
 * Dashboard - Main AMEX Governance Dashboard
 */
export function Dashboard() {
  const [drawerAgentId, setDrawerAgentId] = useState<string | null>(null);
  const [haltModalOpen, setHaltModalOpen] = useState(false);
  const [integrityModalOpen, setIntegrityModalOpen] = useState(false);
  const [integrityResult, setIntegrityResult] = useState<IntegrityStatus | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [agentsRefreshKey, setAgentsRefreshKey] = useState(0);

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
    refetchFleetState();
    setAgentsRefreshKey((prev) => prev + 1);
  };

  const handleAgentMutated = () => {
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

  const handleRefreshAll = () => {
    refetchFleetState();
    setAgentsRefreshKey((prev) => prev + 1);
  };

  return (
    <>
      <Header
        onOpenHaltModal={handleOpenHaltModal}
        onRefreshAll={handleRefreshAll}
      />

      <PageContainer>
        <div className="py-6 space-y-6">
          {/* Overview Section: 4 KPI Summary Cards */}
          <FleetStatusCard onOpenHaltModal={handleOpenHaltModal} />

          {/* Two-Column Grid: Agent List & Live Activity Feed */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            <div className="min-w-0">
              <AgentsSection
                key={agentsRefreshKey}
                onOpenAgentDrawer={handleOpenAgentDrawer}
              />
            </div>

            <div className="min-w-0 h-full">
              <ActivityFeedCard />
            </div>
          </div>

          {/* Audit Integrity Footer Banner */}
          <AuditIntegrityCard onVerify={handleVerifyIntegrity} />
        </div>
      </PageContainer>

      {/* Agent Details Drawer */}
      <AgentDrawer
        isOpen={drawerAgentId !== null}
        agentId={drawerAgentId}
        onClose={handleCloseDrawer}
        onAgentRevoked={handleAgentMutated}
        onAgentRestored={handleAgentMutated}
        onAgentMutated={handleAgentMutated}
      />

      {/* Fleet Halt / Resume Modal */}
      <FleetHaltModal
        isOpen={haltModalOpen}
        isHalted={isHalted}
        onClose={handleCloseHaltModal}
        onSuccess={handleHaltModalSuccess}
      />

      {/* Cryptographic Chain Integrity Modal */}
      <IntegrityResultModal
        isOpen={integrityModalOpen}
        onClose={handleCloseIntegrityModal}
        result={integrityResult}
        isLoading={isVerifying}
      />

      {/* Toast Notification Layer */}
      <ToastContainer />
    </>
  );
}

