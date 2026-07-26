import { Dashboard } from './pages/Dashboard';
import { ErrorBoundary } from './components/ErrorBoundary';

function App() {
  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-slate-100/70 text-slate-900 font-sans antialiased">
        <Dashboard />
      </div>
    </ErrorBoundary>
  );
}

export default App;

