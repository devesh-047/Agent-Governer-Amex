import { useState } from 'react';
import { api } from '@/api';
import type { Scenario } from '@/api/types';

/**
 * ScenarioSelector - Debug control for switching demo scenarios
 *
 * This is an optional development tool for demo purposes.
 * It allows switching between NORMAL, RISK, and INCIDENT scenarios
 * to demonstrate different dashboard states.
 *
 * In production, this would be hidden behind a feature flag or removed.
 */
export function ScenarioSelector() {
  const [scenario, setScenario] = useState<Scenario>('NORMAL');
  const [isOpen, setIsOpen] = useState(false);

  const handleScenarioChange = async (newScenario: Scenario) => {
    await api.setScenario(newScenario);
    setScenario(newScenario);
    setIsOpen(false);
    // Force page reload to refresh all components
    window.location.reload();
  };

  const scenarioColors: Record<Scenario, string> = {
    NORMAL: 'bg-semantic-success-bg text-semantic-success-text border-semantic-success-border',
    RISK: 'bg-semantic-warning-bg text-semantic-warning-text border-semantic-warning-border',
    INCIDENT: 'bg-semantic-error-bg text-semantic-error-text border-semantic-error-border',
  };

  // Only show in development
  if (!import.meta.env.DEV) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 z-40">
      <div className="relative">
        {/* Dropdown button */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={`px-4 py-2 rounded-md border text-sm font-medium transition-colors ${scenarioColors[scenario]}`}
          aria-label="Select demo scenario"
        >
          Scenario: {scenario}
        </button>

        {/* Dropdown menu */}
        {isOpen && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-40"
              onClick={() => setIsOpen(false)}
            />

            {/* Menu */}
            <div className="absolute bottom-full right-0 mb-2 w-48 bg-background-surface border border-border-light rounded-md shadow-lg z-50">
              <div className="py-1">
                {(['NORMAL', 'RISK', 'INCIDENT'] as Scenario[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => handleScenarioChange(s)}
                    className={`w-full text-left px-4 py-2 text-sm transition-colors ${
                      scenario === s
                        ? 'bg-background-tertiary text-text-primary font-medium'
                        : 'text-text-secondary hover:bg-background-secondary'
                    }`}
                  >
                    <span className={`mr-2 ${scenario === s ? '' : 'text-text-tertiary'}`}>
                      {scenario === s ? '●' : '○'}
                    </span>
                    {s}
                    {s === 'NORMAL' && ' - Compliant'}
                    {s === 'RISK' && ' - Elevated Risk'}
                    {s === 'INCIDENT' && ' - Agent Revoked + Chain Break'}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
