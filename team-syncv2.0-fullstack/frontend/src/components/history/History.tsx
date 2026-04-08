// components/history/History.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { api } from '../../services/api';
import { Button } from '../ui/Button';
import { Card, CardContent } from '../ui/Card';
import {
  History as HistoryIcon,
  FileText,
  Trash2,
  ExternalLink,
  MessageSquare,
  Award,
  Calendar,
  TestTube,
  Search,
  X,
} from 'lucide-react';
import type { PRDDocument } from '../../types';

const gradeColors: Record<string, string> = {
  A: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30',
  B: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
  C: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  D: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
  F: 'text-red-400 bg-red-400/10 border-red-400/30',
};

const gradeBg: Record<string, string> = {
  A: 'border-l-emerald-500',
  B: 'border-l-blue-500',
  C: 'border-l-yellow-500',
  D: 'border-l-orange-500',
  F: 'border-l-red-500',
};

export function History() {
  const navigate  = useNavigate();
  const { dispatch } = useApp();
  const [search, setSearch]         = useState('');
  const [confirmClear, setConfirmClear] = useState(false);

  // Always read fresh from localStorage so deletions reflect immediately
  const [history, setHistory] = useState<PRDDocument[]>(() => api.getPRDHistory());

  const filtered = search.trim()
    ? history.filter(p =>
        p.title.toLowerCase().includes(search.toLowerCase()) ||
        p.fileName?.toLowerCase().includes(search.toLowerCase())
      )
    : history;

  const handleDelete = (id: string) => {
    const updated = history.filter(p => p.id !== id);
    api.replacePRDHistory(updated);
    setHistory(updated);
    // Sync context so Dashboard stays accurate
    dispatch({ type: 'SET_CURRENT_PRD', payload: null });
  };

  const handleClearAll = () => {
    api.clearPRDHistory();
    setHistory([]);
    dispatch({ type: 'SET_CURRENT_PRD', payload: null });
    setConfirmClear(false);
  };

  const handleOpen = (prd: PRDDocument) => {
    navigate(`/prd/${prd.id}`);
  };

  const handleResumeSession = (prd: PRDDocument) => {
    if (!prd.sessionId) return;
    // Opens a new tab (or switches to an existing one) with this session
    dispatch({ type: 'RESTORE_SESSION', payload: { sessionId: prd.sessionId, label: prd.title } });
    navigate('/');
  };

  const formatDate = (d: Date) =>
    new Date(d).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center">
            <HistoryIcon className="w-5 h-5 text-primary-light" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Conversation History</h1>
            <p className="text-sm text-text-muted">
              {history.length} PRD{history.length !== 1 ? 's' : ''} generated
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          {/* Search */}
          <div className="relative flex-1 sm:flex-none">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none" />
            <input
              type="text"
              placeholder="Search PRDs…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 pr-8 py-2 bg-background-tertiary border border-white/10 rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary/50 w-full sm:w-56"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Clear all */}
          {history.length > 0 && (
            confirmClear ? (
              <div className="flex items-center gap-2">
                <span className="text-sm text-status-error">Clear all?</span>
                <Button variant="ghost" size="sm" onClick={handleClearAll}
                  className="text-status-error hover:text-status-error">Yes</Button>
                <Button variant="ghost" size="sm" onClick={() => setConfirmClear(false)}>No</Button>
              </div>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => setConfirmClear(true)}>
                <Trash2 className="w-4 h-4 mr-2" />
                Clear all
              </Button>
            )
          )}
        </div>
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <Card>
          <CardContent className="py-16 text-center">
            {search ? (
              <>
                <Search className="w-12 h-12 text-text-muted mx-auto mb-4" />
                <h3 className="text-lg font-medium text-text-primary mb-2">No results for "{search}"</h3>
                <p className="text-text-secondary text-sm">Try a different search term.</p>
              </>
            ) : (
              <>
                <HistoryIcon className="w-12 h-12 text-text-muted mx-auto mb-4" />
                <h3 className="text-lg font-medium text-text-primary mb-2">No history yet</h3>
                <p className="text-text-secondary text-sm mb-6">
                  Start a conversation and generate your first PRD.
                </p>
                <Button onClick={() => navigate('/')}>
                  <MessageSquare className="w-4 h-4 mr-2" />
                  Start Chat
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* History list */}
      <div className="space-y-3">
        {filtered.map(prd => (
          <Card
            key={prd.id}
            className={`border-l-4 ${gradeBg[prd.grade] ?? 'border-l-text-muted'} hover:border-white/20 transition-colors cursor-pointer`}
            onClick={() => handleOpen(prd)}
          >
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-4">

                {/* Left: icon + info */}
                <div className="flex items-start gap-4 min-w-0 flex-1">
                  <div className="w-10 h-10 rounded-xl bg-background-secondary border border-white/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <FileText className="w-5 h-5 text-text-secondary" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-semibold text-text-primary truncate">{prd.title}</h3>
                    <p className="text-xs text-text-muted mt-0.5 truncate">
                      {prd.fileName || `${prd.title.toLowerCase().replace(/\s+/g, '_')}.md`}
                    </p>

                    {/* Meta row */}
                    <div className="flex items-center flex-wrap gap-3 mt-2">
                      <span className={`px-2 py-0.5 rounded-md text-xs font-bold border flex items-center gap-1 ${gradeColors[prd.grade] ?? gradeColors.F}`}>
                        <Award className="w-3 h-3" />
                        {prd.grade} · {prd.qualityScore}/100
                      </span>
                      <span className="flex items-center gap-1 text-xs text-text-muted">
                        <TestTube className="w-3 h-3" />
                        {prd.testCaseCount} test cases
                      </span>
                      <span className="flex items-center gap-1 text-xs text-text-muted">
                        <Calendar className="w-3 h-3" />
                        {formatDate(prd.createdAt)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right: actions */}
                <div
                  className="flex items-center gap-1 flex-shrink-0"
                  onClick={e => e.stopPropagation()}
                >
                  {prd.sessionId && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleResumeSession(prd)}
                      title="Resume this session in chat"
                    >
                      <MessageSquare className="w-4 h-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleOpen(prd)}
                    title="View PRD"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(prd.id)}
                    title="Delete"
                    className="text-text-muted hover:text-status-error"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>

              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
