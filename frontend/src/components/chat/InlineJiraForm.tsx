// components/chat/InlineJiraForm.tsx
// Rendered inline when interrupt.form === 'jira_form' | 'jira_auto_confirm'.
// Auto-confirm: if already connected, counts down 5s then submits automatically.
// Full form:    shown when not connected or user cancels the countdown.
import React, { useState, useCallback, useEffect } from 'react';
import {
  Ticket, ExternalLink, CheckCircle, Loader2, User, SkipForward,
  Timer, ChevronDown, ChevronUp, Pencil,
} from 'lucide-react';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { api } from '../../services/api';
import { useApp } from '../../context/AppContext';
import type { InterruptPayload } from '../../types';

// ── Shared submit payload ────────────────────────────────────────────────────

export interface JiraFormSubmitData extends Record<string, string> {
  decision: string;
  assignee_email: string;
  notes: string;
  project_key: string;
  epic_title: string;
  epic_description: string;
  parent_epic_key: string;
}

interface Props {
  interrupt: InterruptPayload;
  sessionId: string;
  isLoading: boolean;
  onSubmit: (data: JiraFormSubmitData) => void;
}

// ── Reusable select style ─────────────────────────────────────────────────────

const SELECT_CLS =
  'w-full bg-background-secondary border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary/50 disabled:opacity-50';

// ── Component ────────────────────────────────────────────────────────────────

export function InlineJiraForm({ interrupt, sessionId, isLoading, onSubmit }: Props) {
  const { state, refreshJiraConnection } = useApp();
  const globalJira = state.jiraConnection;

  // ── OAuth connection state ─────────────────────────────────────────────────
  const [connected, setConnected] = useState(
    globalJira?.connected ?? interrupt.jira_connected ?? false,
  );
  const [jiraUser, setJiraUser]   = useState(globalJira?.user_name ?? interrupt.jira_user ?? null);
  const [jiraCloud, setJiraCloud] = useState(globalJira?.cloud_name ?? interrupt.jira_cloud ?? null);
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState('');

  // ── Form fields ────────────────────────────────────────────────────────────
  const projects = interrupt.available_projects ?? [];
  const [projectKey, setProjectKey] = useState(
    projects[0]?.key ?? interrupt.default_project ?? '',
  );
  const [assigneeEmail, setAssigneeEmail] = useState('');
  const [emailError, setEmailError]       = useState('');
  const [notes, setNotes]                 = useState('');

  // Epic fields — pre-filled from PRD extraction
  const [epicTitle, setEpicTitle]             = useState(interrupt.epic_title_preview ?? '');
  const [epicDescription, setEpicDescription] = useState(interrupt.epic_description_preview ?? '');

  // Parent epic — user can link to existing Epic instead of creating a new one
  const [parentEpicKey, setParentEpicKey] = useState('');
  const [epics, setEpics] = useState<{ key: string; summary: string }[]>(
    interrupt.available_epics ?? [],
  );
  const [loadingEpics, setLoadingEpics] = useState(false);
  const [epicMode, setEpicMode] = useState<'new' | 'existing'>('new');

  // Collapsible "Advanced" section for description + parent-epic picker
  const [showAdvanced, setShowAdvanced] = useState(false);

  // ── Auto-confirm countdown ─────────────────────────────────────────────────
  const isAutoConfirm = interrupt.auto_confirm === true;
  const [countdown, setCountdown] = useState(interrupt.countdown_seconds ?? 5);
  const [cancelled, setCancelled] = useState(false);

  // ── Sync when global Jira connection changes ───────────────────────────────
  useEffect(() => {
    if (globalJira?.connected) {
      setConnected(true);
      setJiraUser(globalJira.user_name);
      setJiraCloud(globalJira.cloud_name);
    }
  }, [globalJira?.connected, globalJira?.user_name, globalJira?.cloud_name]);

  // ── Auto-confirm tick ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAutoConfirm || cancelled || isLoading) return;
    if (countdown <= 0) {
      onSubmit(buildPayload('approve'));
      return;
    }
    const t = setTimeout(() => setCountdown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown, cancelled, isAutoConfirm, isLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Refresh epics when project changes ────────────────────────────────────
  const fetchEpics = useCallback(async (key: string) => {
    if (!key || !connected) return;
    setLoadingEpics(true);
    try {
      const data = await api.getJiraEpics(key);
      setEpics(data.epics);
    } catch {
      // non-fatal — epics list just stays empty
    } finally {
      setLoadingEpics(false);
    }
  }, [connected]);

  const handleProjectChange = (key: string) => {
    setProjectKey(key);
    setParentEpicKey('');
    void fetchEpics(key);
  };

  // ── OAuth popup ───────────────────────────────────────────────────────────
  const pollStatus = useCallback(async () => {
    try {
      const s = await api.getJiraAuthStatus(sessionId);
      if (s.connected) {
        setConnected(true);
        setJiraUser(s.user_name);
        setJiraCloud(s.cloud_name);
        void refreshJiraConnection();
        void fetchEpics(projectKey);
      }
    } catch { /* silent */ } finally {
      setConnecting(false);
    }
  }, [sessionId, refreshJiraConnection, fetchEpics, projectKey]);

  const handleConnect = async () => {
    setConnecting(true);
    setConnectError('');
    try {
      const url = await api.getJiraConnectUrl(sessionId);
      const popup = window.open(url, 'jira-oauth', 'width=520,height=680,left=200,top=100');
      const handler = (e: MessageEvent) => {
        if (e.data?.type === 'jira_oauth') {
          window.removeEventListener('message', handler);
          popup?.close();
          if (e.data.success === false) {
            setConnectError(e.data.message || 'JIRA OAuth failed.');
            setConnecting(false);
          } else {
            pollStatus();
          }
        }
      };
      window.addEventListener('message', handler);
      const checkClosed = setInterval(() => {
        if (popup?.closed) {
          clearInterval(checkClosed);
          window.removeEventListener('message', handler);
          pollStatus();
        }
      }, 500);
    } catch (err: any) {
      setConnectError(err.message || 'Failed to start JIRA OAuth.');
      setConnecting(false);
    }
  };

  // ── Build submit payload ──────────────────────────────────────────────────
  const buildPayload = (decision: string): JiraFormSubmitData => ({
    decision,
    assignee_email: assigneeEmail,
    notes,
    project_key:   projectKey,
    epic_title:    epicMode === 'new' ? epicTitle : '',
    epic_description: epicMode === 'new' ? epicDescription : '',
    parent_epic_key:  epicMode === 'existing' ? parentEpicKey : '',
  });

  const handleApprove = (e: React.FormEvent) => {
    e.preventDefault();
    if (assigneeEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(assigneeEmail)) {
      setEmailError('Invalid email address');
      return;
    }
    setEmailError('');
    onSubmit(buildPayload('approve'));
  };

  const handleSkip = () => onSubmit(buildPayload('skip'));

  // ── Project selector (shared between auto-confirm and full form) ──────────
  const ProjectField = ({ disabled = false }: { disabled?: boolean }) => (
    <div>
      <label className="block text-xs font-medium text-text-secondary mb-1">Project</label>
      {projects.length > 0 ? (
        <select
          value={projectKey}
          onChange={e => handleProjectChange(e.target.value)}
          disabled={disabled || isLoading}
          className={SELECT_CLS}
        >
          {projects.map(p => (
            <option key={p.key} value={p.key}>{p.name} ({p.key})</option>
          ))}
        </select>
      ) : (
        <Input
          placeholder="e.g. TSA"
          value={projectKey}
          onChange={e => handleProjectChange(e.target.value.toUpperCase())}
          disabled={disabled || isLoading}
        />
      )}
    </div>
  );

  // ── Auto-confirm view ─────────────────────────────────────────────────────
  if (isAutoConfirm && !cancelled) {
    return (
      <div className="max-w-md w-full bg-background-tertiary border border-white/10 rounded-2xl p-5 space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
            <Timer className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-text-primary">Creating JIRA tickets</p>
            <p className="text-xs text-text-muted mt-0.5">
              As <strong>{jiraUser ?? interrupt.jira_user}</strong>
              {(jiraCloud ?? interrupt.jira_cloud) ? ` · ${jiraCloud ?? interrupt.jira_cloud}` : ''}
            </p>
          </div>
          <div className="ml-auto w-9 h-9 rounded-full bg-emerald-500/20 border-2 border-emerald-500/40 flex items-center justify-center flex-shrink-0">
            <span className="text-sm font-bold text-emerald-400">{countdown}</span>
          </div>
        </div>

        <div className="space-y-2">
          <ProjectField />
          <Input
            type="email"
            placeholder="Assignee email (optional)"
            value={assigneeEmail}
            onChange={e => setAssigneeEmail(e.target.value)}
          />
        </div>

        <div className="flex gap-2">
          <Button type="button" variant="ghost" className="flex-1" onClick={() => setCancelled(true)}>
            Cancel / Edit
          </Button>
          <Button
            type="button"
            className="flex-1"
            onClick={() => onSubmit(buildPayload('approve'))}
            disabled={isLoading}
          >
            {isLoading
              ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Creating…</>
              : <><Ticket className="w-4 h-4 mr-2" />Create Now</>
            }
          </Button>
        </div>
      </div>
    );
  }

  // ── Full form view ────────────────────────────────────────────────────────
  return (
    <div className="max-w-lg w-full bg-background-tertiary border border-white/10 rounded-2xl p-5 space-y-4">

      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
          <Ticket className="w-4 h-4 text-primary-light" />
        </div>
        <div>
          <p className="text-sm font-medium text-text-primary">Create JIRA tickets</p>
          <p className="text-xs text-text-muted mt-0.5">{interrupt.message}</p>
        </div>
      </div>

      {/* OAuth status */}
      {connected ? (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>
            Connected as <strong>{jiraUser}</strong>
            {jiraCloud ? ` on ${jiraCloud}` : ''}
          </span>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-text-muted">
            Connect your Atlassian account to create tickets under your identity.
          </p>
          <Button
            type="button"
            variant="secondary"
            className="w-full"
            onClick={handleConnect}
            disabled={connecting || isLoading}
          >
            {connecting
              ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Connecting…</>
              : <><ExternalLink className="w-4 h-4 mr-2" />Connect JIRA</>
            }
          </Button>
          {connectError && <p className="text-xs text-red-400">{connectError}</p>}
          <p className="text-xs text-text-muted text-center">or skip to finish without creating tickets</p>
        </div>
      )}

      <form onSubmit={handleApprove} className="space-y-4">

        {/* ── Project ── */}
        <ProjectField />

        {/* ── Epic section ── */}
        <div className="border border-white/10 rounded-xl overflow-hidden">
          {/* Epic mode tabs */}
          <div className="flex border-b border-white/10">
            <button
              type="button"
              onClick={() => setEpicMode('new')}
              className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                epicMode === 'new'
                  ? 'bg-primary/10 text-primary-light'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Create new Epic
            </button>
            <button
              type="button"
              onClick={() => { setEpicMode('existing'); if (!epics.length) void fetchEpics(projectKey); }}
              className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                epicMode === 'existing'
                  ? 'bg-primary/10 text-primary-light'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Use existing Epic
            </button>
          </div>

          <div className="p-3 space-y-3">
            {epicMode === 'new' ? (
              <>
                {/* Epic title */}
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">
                    <span className="flex items-center gap-1">
                      <Pencil className="w-3 h-3" /> Epic title
                    </span>
                  </label>
                  <Input
                    placeholder="[PRD] Feature name"
                    value={epicTitle}
                    onChange={e => setEpicTitle(e.target.value)}
                    disabled={isLoading}
                  />
                </div>

                {/* Advanced toggle — description */}
                <button
                  type="button"
                  onClick={() => setShowAdvanced(v => !v)}
                  className="flex items-center gap-1 text-xs text-text-muted hover:text-text-secondary transition-colors"
                >
                  {showAdvanced ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  {showAdvanced ? 'Hide' : 'Edit'} Epic description
                </button>

                {showAdvanced && (
                  <div>
                    <textarea
                      rows={3}
                      placeholder="Optional Epic description…"
                      value={epicDescription}
                      onChange={e => setEpicDescription(e.target.value)}
                      disabled={isLoading}
                      className="w-full bg-background-secondary border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary/50 resize-none disabled:opacity-50"
                    />
                  </div>
                )}

                {/* Hierarchy preview */}
                <div className="px-2.5 py-2 rounded-lg bg-primary/5 border border-primary/10">
                  <p className="text-xs font-medium text-text-secondary mb-1">Proposed structure</p>
                  <div className="text-xs text-text-muted space-y-0.5 font-mono">
                    <p className="text-primary-light truncate">Epic — {epicTitle || '[PRD] Feature'}</p>
                    <p className="pl-3 text-text-muted">├── Story (FR1, FR2 … per requirement)</p>
                    <p className="pl-6 text-text-muted">└── Subtask (TC per test case)</p>
                  </div>
                </div>
              </>
            ) : (
              <>
                {/* Existing epic picker */}
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">
                    Parent Epic
                    {loadingEpics && <span className="ml-2 text-text-muted">(loading…)</span>}
                  </label>
                  {epics.length > 0 ? (
                    <select
                      value={parentEpicKey}
                      onChange={e => setParentEpicKey(e.target.value)}
                      disabled={isLoading || loadingEpics}
                      className={SELECT_CLS}
                    >
                      <option value="">— select an Epic —</option>
                      {epics.map(ep => (
                        <option key={ep.key} value={ep.key}>{ep.key}: {ep.summary}</option>
                      ))}
                    </select>
                  ) : (
                    <Input
                      placeholder="e.g. TSA-1"
                      value={parentEpicKey}
                      onChange={e => setParentEpicKey(e.target.value.toUpperCase())}
                      disabled={isLoading}
                    />
                  )}
                </div>
                {parentEpicKey && (
                  <p className="text-xs text-text-muted">
                    Stories will be created under <strong className="text-primary-light">{parentEpicKey}</strong>.
                  </p>
                )}
              </>
            )}
          </div>
        </div>

        {/* ── Assignee ── */}
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1.5">
            <span className="flex items-center gap-1.5">
              <User className="w-3 h-3" />
              Assignee email <span className="text-text-muted font-normal">(optional)</span>
            </span>
          </label>
          <Input
            type="email"
            placeholder="teammate@company.com"
            value={assigneeEmail}
            onChange={e => setAssigneeEmail(e.target.value)}
            error={emailError}
            disabled={isLoading}
          />
        </div>

        {/* ── Notes ── */}
        <Input
          placeholder="Notes for the team (optional)"
          value={notes}
          onChange={e => setNotes(e.target.value)}
          disabled={isLoading}
        />

        {/* ── Actions ── */}
        <div className="flex gap-2">
          <Button type="submit" className="flex-1" disabled={isLoading}>
            {isLoading
              ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Creating…</>
              : <><Ticket className="w-4 h-4 mr-2" />Approve &amp; Create</>
            }
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={handleSkip}
            disabled={isLoading}
            title="Skip JIRA creation"
          >
            <SkipForward className="w-4 h-4" />
          </Button>
        </div>

        {interrupt.hint && (
          <p className="text-xs text-text-muted text-center">{interrupt.hint}</p>
        )}
      </form>
    </div>
  );
}
