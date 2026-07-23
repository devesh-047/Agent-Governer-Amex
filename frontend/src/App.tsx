import { Header } from './components/layout/Header';
import { PageContainer } from './components/layout/PageContainer';
import { Dashboard } from './pages/Dashboard';
import { ErrorBoundary } from './components/ErrorBoundary';

function App() {
  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-background-primary">
        <Header />
        <PageContainer>
          <Dashboard />
        </PageContainer>
      </div>
    </ErrorBoundary>
  );
}

export default App;
