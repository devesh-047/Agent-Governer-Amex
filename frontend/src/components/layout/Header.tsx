export function Header() {
  return (
    <header className="bg-background-surface border-b border-border-light shadow-sm">
      <div className="max-w-7xl mx-auto px-6 py-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-text-primary tracking-tight">
            AMEX AGENT GOVERNANCE
          </h1>
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-semantic-success-text animate-pulse" />
            <span className="text-xs text-text-secondary">Runtime connected</span>
            <span className="text-xs text-text-tertiary">· Updated 2s ago</span>
          </div>
        </div>
      </div>
    </header>
  );
}
