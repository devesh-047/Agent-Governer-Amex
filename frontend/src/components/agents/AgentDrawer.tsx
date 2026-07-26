import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { ChevronDown, ChevronUp, Copy, Check, X, ShieldAlert, ShieldCheck, DollarSign, Lock, AlertTriangle, Key, Play } from 'lucide-react';
import { api } from '@/api';
import { toast } from '@/components/ui/Toast';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { ProgressBar } from '@/components/ui/ProgressBar';
import type { Agent, ActionExecutionResponse } from '@/api/types';

interface AgentDrawerProps {
  isOpen: boolean;
  agentId: string | null;
  onClose: () => void;
  onAgentRevoked?: (agentId: string) => void;
  onAgentRestored?: (agentId: string) => void;
  onAgentMutated?: () => void;
}

interface RecentDecision {
  timestamp: string;
  decision: 'allow' | 'deny';
  action_type: string;
  amount: number;
  reason: string | null;
  timeAgo: string;
}

export function AgentDrawer({ isOpen, agentId, onClose, onAgentRevoked, onAgentRestored, onAgentMutated }: AgentDrawerProps) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showRevokeConfirm, setShowRevokeConfirm] = useState(false);
  const [isResettingSpend, setIsResettingSpend] = useState(false);
  const [isEditingPolicy, setIsEditingPolicy] = useState(false);
  const [recentDecisions, setRecentDecisions] = useState<RecentDecision[]>([]);
  const [showFullUuid, setShowFullUuid] = useState(false);
  const [copiedUuid, setCopiedUuid] = useState(false);

  // Test Agent Action State
  const [testActionType, setTestActionType] = useState<string>('');
  const [testAmount, setTestAmount] = useState<string>('100');
  const [availableActions, setAvailableActions] = useState<string[]>([]);
  const [isExecutingAction, setIsExecutingAction] = useState(false);
  const [testActionResult, setTestActionResult] = useState<ActionExecutionResponse | null>(null);
  const [isSystemAgent, setIsSystemAgent] = useState(false);


  useEffect(() => {
    if (isOpen && agentId) {
      setIsLoading(true);
      setShowFullUuid(false);
      api.getAgent(agentId)
        .then((data) => {
          setAgent(data);
          return api.getActivityFeed(50);
        })
        .then((feed) => {
          const agentDecisions = feed
            .filter((e) => e.agent_id === agentId)
            .slice(0, 10)
            .map((e) => ({
              timestamp: e.timestamp,
              decision: e.decision,
              action_type: e.action_type,
              amount: e.amount,
              reason: e.reason,
              timeAgo: formatTimeAgo(e.timestamp),
            }));
          setRecentDecisions(agentDecisions);
        })
        .catch((error) => {
          console.error('Failed to load agent:', error);
          toast.error('Failed to load agent details');
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setAgent(null);
      setRecentDecisions([]);
      setShowRevokeConfirm(false);
      setTestActionResult(null);
    }
  }, [isOpen, agentId]);

  // Pre-populate sensible defaults based on selected agent ID
  useEffect(() => {
    if (!agent) return;

    const isSys =
      agent.id === '00000000-0000-0000-0000-000000000001' ||
      agent.name.toLowerCase().includes('system') ||
      agent.permissions.includes('system');

    setIsSystemAgent(isSys);

    if (!isSys) {
      const nameLower = agent.name.toLowerCase();
      const idLower = agent.id.toLowerCase();

      if (idLower === '11111111-1111-1111-1111-111111111111' || idLower.includes('agent_a') || nameLower.includes('payment')) {
        setTestActionType('refund');
        setTestAmount('100');
        setAvailableActions(['refund', 'limit_adjustment', 'payment_processing']);
      } else if (idLower === '22222222-2222-2222-2222-222222222222' || idLower.includes('agent_b') || nameLower.includes('travel')) {
        setTestActionType('travel_booking');
        setTestAmount('50');
        setAvailableActions(['travel_booking', 'refund', 'hotel_reservation']);
      } else if (idLower === '33333333-3333-3333-3333-333333333333' || idLower.includes('agent_c') || nameLower.includes('reward') || nameLower.includes('point')) {
        setTestActionType('points_adjustment');
        setTestAmount('50');
        setAvailableActions(['points_adjustment', 'refund', 'cashback_issue']);
      } else {
        const defaultAct = agent.permissions.length > 0 ? agent.permissions[0] : 'refund';
        setTestActionType(defaultAct);
        setTestAmount('100');
        const actionsSet = new Set([...agent.permissions, 'refund', 'travel_booking', 'points_adjustment']);
        setAvailableActions(Array.from(actionsSet));
      }
    }
  }, [agent?.id]);


  const handleExecuteTestAction = async () => {
    if (!agent || !testActionType || !testAmount) return;

    setIsExecutingAction(true);
    try {
      const amountNum = parseFloat(testAmount);
      const result = await api.executeAction(agent.id, testActionType, amountNum, agent.name);

      setTestActionResult(result);

      // Re-fetch agent to update remaining budget in drawer immediately
      const updatedAgent = await api.getAgent(agent.id);
      setAgent(updatedAgent);

      // Re-fetch activity feed for drawer recent decisions list
      const feed = await api.getActivityFeed(50);
      const agentDecisions = feed
        .filter((e) => e.agent_id === agent.id)
        .slice(0, 10)
        .map((e) => ({
          timestamp: e.timestamp,
          decision: e.decision,
          action_type: e.action_type,
          amount: e.amount,
          reason: e.reason,
          timeAgo: formatTimeAgo(e.timestamp),
        }));
      setRecentDecisions(agentDecisions);

      // Trigger live refresh on main dashboard
      onAgentMutated?.();

      if (result.decision === 'allow') {
        toast.success(`Action ALLOWED! Remaining budget: $${result.remaining_budget.toLocaleString()}`);
      } else {
        toast.error(`Action DENIED: ${result.reason || result.reason_code}`);
      }
    } catch (error: any) {
      console.error('Failed to execute test action:', error);
      toast.error(error.message || 'Failed to execute test action');
    } finally {
      setIsExecutingAction(false);
    }
  };


  // ESC key listener
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [isOpen, onClose]);

  const handleRevokeAgent = async () => {
    if (!agent) return;

    try {
      await api.revokeAgent(agent.id);
      toast.success(`Agent "${agent.name}" revoked successfully`);
      setShowRevokeConfirm(false);
      onAgentRevoked?.(agent.id);
      onClose();
    } catch (error) {
      console.error('Failed to revoke agent:', error);
      toast.error('Failed to revoke agent');
    }
  };

  const handleRestoreAgent = async () => {
    if (!agent) return;

    try {
      await api.restoreAgent(agent.id);
      toast.success(`Agent "${agent.name}" restored successfully`);
      onAgentRestored?.(agent.id);
      onClose();
    } catch (error) {
      console.error('Failed to restore agent:', error);
      toast.error('Failed to restore agent');
    }
  };

  const handleResetSpend = async () => {
    if (!agent) return;
    setIsResettingSpend(true);
    try {
      await api.resetSpend(agent.id);
      toast.success(`Spend limit reset for "${agent.name}"`);
      onAgentMutated?.();
      const updatedAgent = await api.getAgent(agent.id);
      setAgent(updatedAgent);
    } catch (error: any) {
      console.error('Failed to reset spend:', error);
      toast.error(error.message || 'Failed to reset spend limit');
    } finally {
      setIsResettingSpend(false);
    }
  };

  const copyUuid = () => {
    if (!agent) return;
    navigator.clipboard.writeText(agent.id);
    setCopiedUuid(true);
    setTimeout(() => setCopiedUuid(false), 1500);
  };

  if (!isOpen) return null;

  const spent = agent && agent.remaining_budget !== null ? agent.daily_cap - agent.remaining_budget : 0;
  const percentUsed = agent ? (spent / agent.daily_cap) * 100 : 0;

  // Case-insensitive checks for status to handle API responses cleanly
  const isRevoked = agent ? agent.status?.toLowerCase() === 'revoked' || agent.runtime_status?.toLowerCase() === 'revoked' : false;
  const isHalted = agent?.fleet_halted === true;

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-40 transition-opacity duration-200 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      {/* Slide-over Drawer */}
      <div
        className={`fixed top-0 right-0 h-full w-full max-w-2xl bg-white shadow-2xl z-50 transform transition-transform duration-200 ease-out border-l border-slate-200 ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-slate-400 font-medium animate-pulse">
            Loading agent details...
          </div>
        ) : agent ? (
          <div className="h-full flex flex-col">
            {/* Drawer Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-[#4A0E17]">
                    AGENT DETAILS
                  </h2>
                </div>
                <h3 className="text-lg font-extrabold text-slate-900 mt-0.5">{agent.name}</h3>
              </div>

              <button
                onClick={onClose}
                className="text-slate-400 hover:text-slate-700 p-2 rounded-lg hover:bg-slate-200/50 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Scrollable Body */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

              {/* Collapsible Full UUID Section (Hidden by default) */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Key className="w-4 h-4 text-slate-500" />
                    <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">
                      Agent Identifier
                    </span>
                  </div>
                  <button
                    onClick={() => setShowFullUuid(!showFullUuid)}
                    className="text-xs font-semibold text-slate-600 hover:text-slate-900 flex items-center gap-1 cursor-pointer bg-white px-2.5 py-1 rounded border border-slate-200 shadow-2xs"
                  >
                    {showFullUuid ? (
                      <>Hide Full UUID <ChevronUp className="w-3.5 h-3.5" /></>
                    ) : (
                      <>Expand Full UUID <ChevronDown className="w-3.5 h-3.5" /></>
                    )}
                  </button>
                </div>

                {!showFullUuid ? (
                  <div className="mt-2 text-xs font-mono text-slate-500 bg-white p-2 rounded border border-slate-200/60 flex items-center justify-between">
                    <span>ID: {agent.id.length > 16 ? `${agent.id.slice(0, 14)}...` : agent.id}</span>
                    <span className="text-[11px] text-slate-400 font-sans">(Click expand to view complete UUID)</span>
                  </div>
                ) : (
                  <div className="mt-3 space-y-2">
                    <div className="bg-slate-900 text-emerald-400 p-3 rounded-lg font-mono text-xs break-all select-all flex items-start justify-between gap-2 border border-slate-800">
                      <span>{agent.id}</span>
                      <button
                        onClick={copyUuid}
                        className="text-slate-400 hover:text-white shrink-0 p-1 rounded hover:bg-slate-800 transition-colors"
                        title="Copy UUID"
                      >
                        {copiedUuid ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>
                    <p className="text-[11px] text-slate-500">
                      Full system UUID used for governance policy matching & cryptographic logging.
                    </p>
                  </div>
                )}
              </div>

              {/* Section 1: Identity & Runtime */}
              <SectionDivider title="IDENTITY & RUNTIME STATE" />
              <div className="space-y-4">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{agent.name}</p>
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">{agent.description}</p>
                </div>

                <div className="grid grid-cols-2 gap-4 text-xs bg-white border border-slate-200/80 rounded-xl p-4">
                  <div>
                    <span className="text-slate-400 block mb-1 font-medium">Governance Status:</span>
                    {isRevoked && isHalted ? (
                      <StatusBadge variant="error">REVOKED · FLEET HALTED</StatusBadge>
                    ) : isRevoked ? (
                      <StatusBadge variant="warning">REVOKED</StatusBadge>
                    ) : isHalted ? (
                      <StatusBadge variant="error">HALTED BY FLEET</StatusBadge>
                    ) : (
                      <StatusBadge variant="success">ACTIVE & OPERATIONAL</StatusBadge>
                    )}
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-1 font-medium">Runtime Execution:</span>
                    <span className="font-bold text-slate-900">
                      {isRevoked && isHalted
                        ? 'NON-OPERATIONAL (REVOKED + HALTED)'
                        : isRevoked
                        ? 'NON-OPERATIONAL (REVOKED)'
                        : isHalted
                        ? 'NON-OPERATIONAL (FLEET HALTED)'
                        : 'OPERATIONAL'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-1 font-medium">Registered:</span>
                    <span className="text-slate-700 font-medium">January 15, 2026</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-1 font-medium">Last Decision:</span>
                    <span className="text-slate-700 font-medium">
                      {recentDecisions.length > 0 ? recentDecisions[0].timeAgo : 'No activity'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Section 2: Spend Controls */}
              <SectionDivider
                title="DAILY SPEND CONTROLS"
                rightElement={
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleResetSpend}
                    disabled={isResettingSpend}
                  >
                    {isResettingSpend ? 'RESETTING...' : 'RESET DAILY SPEND'}
                  </Button>
                }
              />
              <div className="space-y-3 bg-white border border-slate-200/80 rounded-xl p-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block font-medium">Daily Cap</span>
                    <span className="text-sm font-bold text-slate-900">${agent.daily_cap.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-medium">Remaining</span>
                    <span className="text-sm font-bold text-emerald-700">
                      ${agent.remaining_budget !== null ? agent.remaining_budget.toLocaleString() : 'N/A'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-medium">Max Single Tx</span>
                    <span className="text-sm font-bold text-slate-900">${agent.max_single_amount.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-medium">Spent Today</span>
                    <span className="text-sm font-bold text-slate-900">${spent.toLocaleString()}</span>
                  </div>
                </div>

                <div className="pt-2">
                  <ProgressBar
                    value={spent}
                    max={agent.daily_cap}
                    color={percentUsed >= 90 ? 'error' : percentUsed >= 70 ? 'warning' : 'primary'}
                  />
                </div>
              </div>

              {/* Section 3: Policy Permissions */}
              <SectionDivider
                title="POLICY PERMISSIONS"
                rightElement={
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setIsEditingPolicy(!isEditingPolicy)}
                  >
                    {isEditingPolicy ? 'CANCEL' : 'EDIT POLICY'}
                  </Button>
                }
              />
              <div className="bg-white border border-slate-200/80 rounded-xl p-4">
                {isEditingPolicy ? (
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      if (!agent) return;
                      const fd = new FormData(e.currentTarget);
                      const max_single = parseFloat(fd.get('max_single') as string);
                      const daily_cap = parseFloat(fd.get('daily_cap') as string);

                      try {
                        const updated = await api.updatePolicy(agent.id, agent.permissions, max_single, daily_cap);
                        toast.success(`Policy updated for "${agent.name}"`);
                        setAgent(updated);
                        setIsEditingPolicy(false);
                        onAgentMutated?.();
                      } catch (error: any) {
                        console.error('Failed to update policy:', error);
                        toast.error(error.message || 'Failed to update policy');
                      }
                    }}
                    className="space-y-4 bg-slate-50 p-4 rounded-lg border border-slate-200"
                  >
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Max Single Amount ($)</label>
                      <input
                        type="number"
                        name="max_single"
                        defaultValue={agent.max_single_amount}
                        className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-sm text-slate-900 focus:outline-none focus:border-[#4A0E17]"
                        min="0"
                        step="0.01"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Daily Cap ($)</label>
                      <input
                        type="number"
                        name="daily_cap"
                        defaultValue={agent.daily_cap}
                        className="w-full bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-sm text-slate-900 focus:outline-none focus:border-[#4A0E17]"
                        min="0"
                        step="0.01"
                      />
                    </div>
                    <Button type="submit" variant="primary" className="w-full">
                      SAVE POLICY LIMITS
                    </Button>
                  </form>
                ) : (
                  <div className="space-y-2">
                    {agent.permissions.map((perm) => (
                      <div key={perm} className="flex items-center gap-2 text-xs">
                        <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-[10px]">
                          ✓
                        </span>
                        <span className="font-bold text-slate-900 font-mono">{perm}</span>
                        <span className="text-slate-500 text-xs ml-2">
                          ({getPermissionDescription(perm)})
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Section 4: Test Agent Action (Interactive Live Demo) */}
              <SectionDivider title="TEST AGENT ACTION" />
              {isSystemAgent ? (
                <div className="bg-slate-100 border border-slate-200 rounded-xl p-4 text-center text-xs font-semibold text-slate-500">
                  System agents cannot initiate financial actions.
                </div>
              ) : (
                <div className="bg-white border border-slate-200/80 rounded-xl p-4 space-y-4 shadow-2xs">
                  {/* Informative message if Fleet Halted or Agent Revoked */}
                  {(isHalted || isRevoked) && (
                    <div className="bg-amber-50 border border-amber-200/80 rounded-lg p-3 flex items-start gap-2.5 text-xs text-amber-800">
                      <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-bold">Test Action Disabled: </span>
                        {isRevoked && isHalted
                          ? 'Agent is revoked and fleet is halted by operator. Restore agent and resume fleet to enable test actions.'
                          : isRevoked
                          ? 'Agent is currently revoked. Restore agent to enable test actions.'
                          : 'Fleet is currently halted by operator. Resume fleet to enable test actions.'}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">
                        Action Type
                      </label>
                      <select
                        aria-label="Action Type"
                        value={testActionType}
                        onChange={(e) => setTestActionType(e.target.value)}
                        disabled={isHalted || isRevoked || isExecutingAction}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#4A0E17]/20 focus:border-[#4A0E17] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                      >
                        {availableActions.map((act) => (
                          <option key={act} value={act}>
                            {act}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">
                        Amount (₹ / $)
                      </label>
                      <input
                        type="number"
                        min="0"
                        step="1"
                        aria-label="Amount"
                        value={testAmount}
                        onChange={(e) => setTestAmount(e.target.value)}
                        disabled={isHalted || isRevoked || isExecutingAction}
                        className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#4A0E17]/20 focus:border-[#4A0E17] disabled:opacity-50 disabled:cursor-not-allowed"
                        placeholder="Enter amount"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <p className="text-[11px] text-slate-400">
                      Submits live request to <code className="font-mono bg-slate-100 px-1 py-0.5 rounded text-slate-600">/action-request</code>
                    </p>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleExecuteTestAction}
                      disabled={isHalted || isRevoked || isExecutingAction || !testActionType || !testAmount}
                    >
                      {isExecutingAction ? (
                        <span className="flex items-center gap-1.5">
                          <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          EXECUTING...
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5">
                          <Play className="w-3.5 h-3.5 fill-current" />
                          EXECUTE ACTION
                        </span>
                      )}
                    </Button>
                  </div>

                  {/* Execution Result Output */}
                  {testActionResult && (
                    <div className="mt-4 border-t border-slate-200/80 pt-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                          Execution Result
                        </span>
                        <StatusBadge
                          variant={testActionResult.decision === 'allow' ? 'success' : 'error'}
                        >
                          {testActionResult.decision === 'allow' ? '✓ ALLOW' : '✕ DENY'}
                        </StatusBadge>
                      </div>

                      <div className="bg-slate-50 rounded-xl p-3.5 space-y-2 border border-slate-200/60 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-slate-500 font-medium">Reason Code:</span>
                          <span className="font-mono font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
                            {testActionResult.reason_code}
                          </span>
                        </div>

                        <div className="flex items-start justify-between gap-2">
                          <span className="text-slate-500 font-medium shrink-0">Reason Message:</span>
                          <span className="text-slate-800 font-medium text-right break-words">
                            {testActionResult.reason || 'OK'}
                          </span>
                        </div>

                        <div className="flex items-center justify-between">
                          <span className="text-slate-500 font-medium">Remaining Budget:</span>
                          <span className="font-bold text-emerald-700">
                            ${testActionResult.remaining_budget.toLocaleString()}
                          </span>
                        </div>

                        {testActionResult.execution_time_ms !== undefined && (
                          <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-200/40 pt-2 mt-1">
                            <span>Execution Latency:</span>
                            <span className="font-mono font-medium">{testActionResult.execution_time_ms} ms</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Section 5: Decision Log */}
              <SectionDivider title="RECENT DECISIONS (Last 10)" />

              <div className="bg-white border border-slate-200/80 rounded-xl p-3 space-y-2">
                {recentDecisions.length > 0 ? (
                  recentDecisions.map((decision, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-3 text-xs py-2 border-b border-slate-100 last:border-0"
                    >
                      <span className="text-slate-400 font-mono text-[11px] w-14">
                        {decision.timeAgo}
                      </span>
                      <span
                        className={`font-extrabold px-1.5 py-0.5 rounded text-[10px] ${
                          decision.decision === 'allow'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}
                      >
                        {decision.decision.toUpperCase()}
                      </span>
                      <span className="text-slate-900 font-bold w-14 text-right">
                        {decision.amount > 0 ? `$${decision.amount}` : '—'}
                      </span>
                      <span className="text-slate-700 font-mono font-medium">{decision.action_type}</span>
                      <span className="text-slate-400 text-[11px] flex-1 truncate text-right">
                        {decision.reason || ''}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="text-slate-400 text-xs text-center py-4">
                    No decisions recorded for this agent
                  </div>
                )}
              </div>

              {/* Section 5: Runtime Controls */}
              <SectionDivider title="RUNTIME ACTION CONTROLS" />
              <div className="bg-white border border-slate-200/80 rounded-xl p-4">
                {!showRevokeConfirm ? (
                  <>
                    {!isRevoked ? (
                      <>
                        <Button
                          variant="danger"
                          className="w-full"
                          onClick={() => setShowRevokeConfirm(true)}
                        >
                          REVOKE AGENT
                        </Button>
                        <p className="text-xs text-slate-500 mt-2 text-center">
                          Immediately prevents this agent from processing requests. All actions will be denied.
                        </p>
                      </>
                    ) : (
                      <>
                        <Button
                          variant="primary"
                          className="w-full"
                          onClick={handleRestoreAgent}
                        >
                          RESTORE AGENT
                        </Button>
                        <p className="text-xs text-slate-500 mt-2 text-center">
                          Restores agent to active operational status in runtime environment.
                        </p>
                      </>
                    )}
                  </>
                ) : (
                  <div className="space-y-4 bg-rose-50/60 p-4 rounded-xl border border-rose-200">
                    <div className="flex items-center gap-2 text-rose-800 text-sm font-bold">
                      <AlertTriangle className="w-5 h-5 text-rose-600" />
                      CONFIRM REVOCATION
                    </div>
                    <p className="text-xs text-slate-700">
                      You are about to REVOKE agent: <span className="font-bold text-slate-900">{agent.name}</span>
                    </p>
                    <div className="bg-white rounded-lg p-3 text-xs text-slate-600 border border-rose-200 space-y-1">
                      <p className="font-bold text-rose-700 uppercase tracking-wider text-[10px]">OPERATIONAL EFFECT:</p>
                      <ul className="list-disc list-inside space-y-1 text-[11px]">
                        <li>All future requests from this agent will be DENIED</li>
                        <li>Reversible at any time via RESTORE</li>
                        <li>Does NOT disrupt other active agents</li>
                      </ul>
                    </div>
                    <div className="flex gap-3">
                      <Button variant="secondary" className="flex-1" onClick={() => setShowRevokeConfirm(false)}>
                        CANCEL
                      </Button>
                      <Button variant="danger" className="flex-1" onClick={handleRevokeAgent}>
                        CONFIRM REVOCATION
                      </Button>
                    </div>
                  </div>
                )}
              </div>

            </div>
          </div>
        ) : null}
      </div>
    </>
  );
}

function formatTimeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = Math.floor((now - then) / 1000);

  if (diff < 60) return `${diff}s ago`;
  const minutes = Math.floor(diff / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function getPermissionDescription(permission: string): string {
  const descriptions: Record<string, string> = {
    refund: 'Process customer refunds',
    limit_adjustment: 'Adjust credit limits',
    card_replacement: 'Issue replacement cards',
  };
  return descriptions[permission] || 'Custom permission action';
}

interface SectionDividerProps {
  title: string;
  rightElement?: ReactNode;
}

function SectionDivider({ title, rightElement }: SectionDividerProps) {
  return (
    <div className="flex items-center justify-between pb-2 border-b border-slate-200">
      <h3 className="text-xs font-bold text-slate-600 uppercase tracking-wider">{title}</h3>
      {rightElement}
    </div>
  );
}

