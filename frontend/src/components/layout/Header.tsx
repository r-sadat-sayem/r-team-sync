// components/layout/Header.tsx

import { useLocation } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/Button';
import { Trash2, Sparkles, Menu, X, LogOut, FileText, Loader2, CheckCircle2 } from 'lucide-react';

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

  // ── Chat status panel (shown on "/" route) ──────────────────────────────
  const isChat = !pageTitle;

  const statusDot =
    activeTab.isTyping                         ? 'bg-blue-400 animate-pulse' :
    activeTab.currentMode === 'analyze'        ? 'bg-blue-400/60' :
    activeTab.currentMode === 'generate'       ? 'bg-amber-400 animate-pulse' :
    /* complete */                               'bg-emerald-400';

  const phaseLabel =
    activeTab.currentMode === 'analyze'  ? (activeTab.messages.length === 0 ? 'Ready' : 'Gathering Requirements') :
    activeTab.currentMode === 'generate' ? 'Generating PRD…' :
    /* complete */                          'PRD Ready';

  const phaseIcon =
    activeTab.isTyping                         ? <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" /> :
    activeTab.currentMode === 'complete'       ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> :
    activeTab.currentMode === 'generate'       ? <FileText className="w-3.5 h-3.5 text-amber-400" /> :
    /* analyze */                                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${statusDot}`} />;

  const tipText =
    activeTab.isTyping                                                                  ? '' :
    activeTab.interrupt                                                                 ? 'Fill in the form below to continue' :
    activeTab.currentMode === 'analyze' && activeTab.messages.length === 0             ? 'Describe your feature idea to get started' :
    activeTab.currentMode === 'analyze'                                                ? 'Share more details — Sam will signal when ready to generate' :
    activeTab.currentMode === 'complete' && activeTab.currentPRD                       ? 'Type "email", "test cases", "jira", or "regenerate prd" to continue' :
    /* generate / fallback */                                                            '';

  const gradeColors: Record<string, string> = {
    A: 'bg-emerald-400/15 text-emerald-400 border-emerald-400/30',
    B: 'bg-blue-400/15 text-blue-400 border-blue-400/30',
    C: 'bg-yellow-400/15 text-yellow-400 border-yellow-400/30',
    D: 'bg-orange-400/15 text-orange-400 border-orange-400/30',
    F: 'bg-red-400/15 text-red-400 border-red-400/30',
  };

  return (
    <header className="h-14 lg:h-16 bg-background-secondary/50 backdrop-blur-md border-b border-white/8 px-3 md:px-4 lg:px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Left: hamburger + title / status */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onMenuToggle}
          aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          aria-expanded={sidebarOpen}
          className="lg:hidden p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/8 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary flex-shrink-0"
        >
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>

        {isChat ? (
          /* ── Chat status panel ── */
          <div className="flex items-center gap-2 min-w-0">
            {/* Phase icon + label */}
            <div className="flex items-center gap-1.5 flex-shrink-0">
              {phaseIcon}
              <span className="text-sm font-semibold text-text-primary whitespace-nowrap">
                {phaseLabel}
              </span>
            </div>

            {/* Grade badge (complete only) */}
            {activeTab.currentPRD && activeTab.currentMode === 'complete' && (
              <span className={`hidden sm:inline-flex flex-shrink-0 px-2 py-0.5 text-xs font-bold rounded-full border ${gradeColors[activeTab.currentPRD.grade] ?? gradeColors.F}`}>
                {activeTab.currentPRD.grade} · {activeTab.currentPRD.qualityScore}/100
              </span>
            )}

            {/* Separator + contextual tip */}
            {tipText && (
              <>
                <span className="hidden lg:inline text-white/15 flex-shrink-0">·</span>
                <span className="hidden lg:block text-xs text-text-muted truncate max-w-xs" aria-live="polite">
                  {tipText}
                </span>
              </>
            )}
          </div>
        ) : (
          /* ── Other page title ── */
          <h2 className="text-sm lg:text-lg font-semibold text-text-primary truncate">
            {pageTitle}
          </h2>
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
