// components/layout/Header.tsx

import { useLocation } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/Button';
import { Trash2, Sparkles, Menu, X, LogOut } from 'lucide-react';

interface HeaderProps {
  onMenuToggle: () => void;
  sidebarOpen: boolean;
}

function getPageTitle(pathname: string): string | null {
  if (pathname === '/') return null;
  if (pathname === '/history') return 'Conversation History';
  if (pathname === '/dashboard') return 'Dashboard';
  if (pathname.startsWith('/prd')) return 'PRD Viewer';
  if (pathname === '/email') return 'Email';
  if (pathname === '/jira') return 'JIRA Tickets';
  if (pathname.startsWith('/projects')) return 'Projects';
  return null;
}

export function Header({ onMenuToggle, sidebarOpen }: HeaderProps) {
  const { dispatch, activeTab } = useApp();
  const { user, logout } = useAuth();
  const { pathname } = useLocation();

  const pageTitle = getPageTitle(pathname);

  const handleClearChat = () => {
    if (confirm('Are you sure you want to clear the current chat?')) {
      dispatch({ type: 'CLEAR_CHAT' });
    }
  };

  const modeTitle =
    activeTab.currentMode === 'analyze' ? 'Requirements Gathering' :
    activeTab.currentMode === 'generate' ? 'Generating PRD…' :
    'PRD Complete';

  return (
    <header className="h-14 lg:h-16 bg-background-secondary/50 backdrop-blur-md border-b border-white/8 px-3 md:px-4 lg:px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Left: hamburger + title */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onMenuToggle}
          aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          aria-expanded={sidebarOpen}
          className="lg:hidden p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/8 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary flex-shrink-0"
        >
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>

        <h2 className="text-sm lg:text-lg font-semibold text-text-primary truncate">
          {pageTitle ?? modeTitle}
        </h2>

        {activeTab.currentPRD && !pageTitle && (
          <span className="hidden sm:inline-flex flex-shrink-0 px-2 py-1 bg-primary/20 text-primary-light text-xs rounded-full border border-primary/30">
            {activeTab.currentPRD.grade} Grade
          </span>
        )}
      </div>

      {/* Right: user info + actions */}
      <div className="flex items-center gap-2 lg:gap-3 flex-shrink-0">
        {user && (
          <div className="hidden md:flex flex-col items-end mr-1 lg:mr-2">
            <span className="text-sm text-text-primary leading-tight">{user.display_name}</span>
            <span className="text-xs text-text-muted leading-tight">{user.email}</span>
          </div>
        )}

        {activeTab.messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={handleClearChat} className="hidden sm:inline-flex">
            <Trash2 className="w-4 h-4 sm:mr-2" />
            <span className="hidden sm:inline">Clear Chat</span>
          </Button>
        )}

        <Button variant="secondary" size="sm" onClick={() => void logout()}>
          <LogOut className="w-4 h-4 sm:hidden" />
          <span className="hidden sm:inline">Sign Out</span>
        </Button>

        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-background-tertiary rounded-lg border border-white/10">
          <Sparkles className="w-4 h-4 text-primary-light" />
          <span className="text-sm text-text-secondary">Sam is ready</span>
        </div>
      </div>
    </header>
  );
}
