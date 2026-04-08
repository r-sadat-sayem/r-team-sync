// App.tsx
import { BrowserRouter as Router, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { useParams } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Layout } from './components/layout/Layout';
import { ChatPage } from './components/chat/ChatPage';
import { PRDViewer } from './components/prd/PRDViewer';
import { EmailForm } from './components/email/EmailForm';
import { JIRATicketViewer } from './components/jira/JIRATicketViewer';
import { ProjectsPage } from './components/jira/ProjectsPage';
import { Dashboard } from './components/dashboard/Dashboard';
import { History } from './components/history/History';
import { AuthPage } from './components/auth/AuthPage';
import './styles/globals.css';

function ProtectedLayout() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background-primary flex items-center justify-center text-text-secondary">
        Loading TeamSync…
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}

function LegacyBrowseRedirect() {
  const { key } = useParams<{ key?: string }>();
  return <Navigate to={key ? `/projects/${key}` : '/projects'} replace />;
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <AppProvider>
          <Routes>
            <Route path="/login" element={<AuthPage mode="login" />} />
            <Route path="/signup" element={<AuthPage mode="signup" />} />
            <Route element={<ProtectedLayout />}>
              <Route path="/" element={<ChatPage />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/history" element={<History />} />
              <Route path="/prd" element={<PRDViewer />} />
              <Route path="/prd/:id" element={<PRDViewer />} />
              <Route path="/email" element={<EmailForm />} />
              <Route path="/jira" element={<JIRATicketViewer />} />
              <Route path="/projects" element={<ProjectsPage />} />
              <Route path="/projects/:key" element={<ProjectsPage />} />
              <Route path="/browse" element={<Navigate to="/projects" replace />} />
              <Route path="/browse/:key" element={<LegacyBrowseRedirect />} />
            </Route>
          </Routes>
        </AppProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
