// App.tsx

import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { Layout } from './components/layout/Layout';
import { ChatInterface } from './components/chat/ChatInterface';
import { PRDViewer } from './components/prd/PRDViewer';
import { EmailForm } from './components/email/EmailForm';
import { JIRATicketViewer } from './components/jira/JIRATicketViewer';
import { Dashboard } from './components/dashboard/Dashboard';
import './styles/globals.css';

function App() {
  return (
    <AppProvider>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<ChatInterface />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/prd" element={<PRDViewer />} />
            <Route path="/prd/:id" element={<PRDViewer />} />
            <Route path="/email" element={<EmailForm />} />
            <Route path="/jira" element={<JIRATicketViewer />} />
          </Routes>
        </Layout>
      </Router>
    </AppProvider>
  );
}

export default App;
