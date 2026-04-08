// components/chat/InlineJiraForm.tsx
// Rendered inline when interrupt.form === 'jira_form' | 'jira_auto_confirm'.
// Auto-confirm: if already connected, counts down 5s then submits automatically.
// Full form:    shown when not connected or user cancels the countdown.
import React, { useState, useCallback, useEffect } from 'react';
import { Ticket, ExternalLink, CheckCircle, Loader2, User, SkipForward, Timer } from 'lucide-react';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { api } from '../../services/api';
import { useApp } from '../../context/AppContext';
import type { InterruptPayload } from '../../types';

interface Props {
  interrupt: InterruptPayload;
  sessionId: string;
  isLoading: boolean;
  onSubmit: (data: { decision: string; assignee_email: string; notes: string; project_key: string }) => void;
}

export function InlineJiraForm({ interrupt, sessionId, isLoading, onSubmit }: Props) {
  const { state, refreshJiraConnection } = useApp();
  const globalJira = state.jiraConnection;

  const [connected, setConnected] = useState(
    globalJira?.connected ?? interrupt.jira_connected ?? false,
  );
  const [jiraUser, setJiraUser] = useState(
    globalJira?.user_name ?? interrupt.jira_user ?? null,
  );
  const [jiraCloud, setJiraCloud] = useState(
    globalJira?.cloud_name ?? interrupt.jira_cloud ?? null,
  );
  const [connecting, setConnecting] = useState(false);
  const [assigneeEmail, setAssigneeEmail] = useState('');
  const [notes, setNotes] = useState('');
  const [emailError, setEmailError] = useState('');
  const [projectKey, setProjectKey] = useState(interrupt.default_project ?? '');

  // Auto-confirm countdown state
  const isAutoConfirm = interrupt.auto_confirm === true;
  const [countdown, setCountdown] = useState(interrupt.countdown_seconds ?? 5);
  const [cancelled, setCancelled] = useState(false);

  // Sync local state when global connection changes (e.g. connected from JIRA tab)
  useEffect(() => {
    if (globalJira?.connected) {
      setConnected(true);
      setJiraUser(globalJira.user_name);
      setJiraCloud(globalJira.cloud_name);
    }
  }, [globalJira?.connected, globalJira?.user_name, globalJira?.cloud_name]);

  // Auto-confirm countdown tick
  useEffect(() => {
    if (!isAutoConfirm || cancelled || isLoading) return;
    if (countdown <= 0) {
      onSubmit({ decision: 'approve', assignee_email: assigneeEmail, notes, project_key: projectKey });
      return;
    }
    const t = setTimeout(() => setCountdown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown, cancelled, isAutoConfirm, isLoading, assigneeEmail, notes, projectKey, onSubmit]);

  const pollStatus = useCallback(async () => {
    try {
      const s = await api.getJiraAuthStatus(sessionId);
      if (s.connected) {
        setConnected(true);
        setJiraUser(s.user_name);
        setJiraCloud(s.cloud_name);
        void refreshJiraConnection();
      }
    } catch {
      // silent — user can retry
    } finally {
      setConnecting(false);
    }
  }, [sessionId, refreshJiraConnection]);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      const url = await api.getJiraConnectUrl(sessionId);
      const popup = window.open(url, 'jira-oauth', 'width=520,height=680,left=200,top=100');
      const handler = (e: MessageEvent) => {
        if (e.data?.type === 'jira_oauth') {
          window.removeEventListener('message', handler);
          popup?.close();
          pollStatus();
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
    } catch {
      setConnecting(false);
    }
  };

  const handleApprove = (e: React.FormEvent) => {
    e.preventDefault();
    if (assigneeEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(assigneeEmail)) {
      setEmailError('Invalid email address');
      return;
    }
    setEmailError('');
    onSubmit({ decision: 'approve', assignee_email: assigneeEmail, notes, project_key: projectKey });
  };

  const handleSkip = () => {
    onSubmit({ decision: 'skip', assignee_email: '', notes: '', project_key: projectKey });
  };

  const projects = interrupt.available_projects ?? [];

  // ── Auto-confirm view (connected, counting down) ─────────────────────────
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

        {/* Optional overrides while countdown is running */}
        <div className="space-y-2">
          {projects.length > 0 ? (
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Project</label>
              <select
                value={projectKey}
                onChange={e => setProjectKey(e.target.value)}
                className="w-full bg-background-secondary border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary/50"
              >
                {projects.map(p => (
                  <option key={p.key} value={p.key}>{p.name} ({p.key})</option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">Project key</label>
              <Input
                placeholder="e.g. TSA"
                value={projectKey}
                onChange={e => setProjectKey(e.target.value.toUpperCase())}
              />
            </div>
          )}
          <Input
            type="email"
            placeholder="Assignee email (optional)"
            value={assigneeEmail}
            onChange={e => setAssigneeEmail(e.target.value)}
          />
        </div>

        <div className="flex gap-2">
          <Button
            type="button"
            variant="ghost"
            className="flex-1"
            onClick={() => setCancelled(true)}
          >
            Cancel / Edit
          </Button>
          <Button
            type="button"
            className="flex-1"
            onClick={() => onSubmit({ decision: 'approve', assignee_email: assigneeEmail, notes, project_key: projectKey })}
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
    <div className="max-w-md w-full bg-background-tertiary border border-white/10 rounded-2xl p-5 space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
          <Ticket className="w-4 h-4 text-primary-light" />
        </div>
        <div>
          <p className="text-sm font-medium text-text-primary">Create JIRA tickets</p>
          <p className="text-xs text-text-muted mt-0.5">{interrupt.message}</p>
        </div>
      </div>

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
          <p className="text-xs text-text-muted text-center">
            or skip to finish without creating tickets
          </p>
        </div>
      )}

      <form onSubmit={handleApprove} className="space-y-3">
        {projects.length > 0 && (
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1">Project</label>
            <select
              value={projectKey}
              onChange={e => setProjectKey(e.target.value)}
              disabled={isLoading}
              className="w-full bg-background-secondary border border-white/10 rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary/50"
            >
              {projects.map(p => (
                <option key={p.key} value={p.key}>{p.name} ({p.key})</option>
              ))}
            </select>
          </div>
        )}

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

        <Input
          placeholder="Notes for the team (optional)"
          value={notes}
          onChange={e => setNotes(e.target.value)}
          disabled={isLoading}
        />

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
