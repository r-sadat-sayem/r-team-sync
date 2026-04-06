// components/chat/InlineJiraForm.tsx
// Rendered inline when interrupt.form === 'jira_form'.
// Shows a "Connect JIRA" button if jira_connected is false.
import React, { useState, useCallback } from 'react';
import { Ticket, ExternalLink, CheckCircle, Loader2, User, SkipForward } from 'lucide-react';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { api } from '../../services/api';
import type { InterruptPayload } from '../../types';

interface Props {
  interrupt: InterruptPayload;
  sessionId: string;
  isLoading: boolean;
  onSubmit: (data: { decision: string; assignee_email: string; notes: string }) => void;
}

export function InlineJiraForm({ interrupt, sessionId, isLoading, onSubmit }: Props) {
  const [connected, setConnected] = useState(interrupt.jira_connected ?? false);
  const [jiraUser, setJiraUser] = useState(interrupt.jira_user ?? null);
  const [jiraCloud, setJiraCloud] = useState(interrupt.jira_cloud ?? null);
  const [connecting, setConnecting] = useState(false);
  const [assigneeEmail, setAssigneeEmail] = useState('');
  const [notes, setNotes] = useState('');
  const [emailError, setEmailError] = useState('');

  // Poll status after OAuth popup closes
  const pollStatus = useCallback(async () => {
    try {
      const s = await api.getJiraAuthStatus(sessionId);
      if (s.connected) {
        setConnected(true);
        setJiraUser(s.user_name);
        setJiraCloud(s.cloud_name);
      }
    } catch {
      // silent — user can retry
    } finally {
      setConnecting(false);
    }
  }, [sessionId]);

  const handleConnect = async () => {
    if (!interrupt.connect_url) return;
    setConnecting(true);

    try {
      const url = await api.getJiraConnectUrl(sessionId);
      const popup = window.open(url, 'jira-oauth', 'width=520,height=680,left=200,top=100');

      // Listen for the OAuth callback's postMessage
      const handler = (e: MessageEvent) => {
        if (e.data?.type === 'jira_oauth') {
          window.removeEventListener('message', handler);
          popup?.close();
          pollStatus();
        }
      };
      window.addEventListener('message', handler);

      // Fallback: if popup closed without postMessage, poll after 3s
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
    onSubmit({ decision: 'approve', assignee_email: assigneeEmail, notes });
  };

  const handleSkip = () => {
    onSubmit({ decision: 'skip', assignee_email: '', notes: '' });
  };

  return (
    <div className="max-w-md w-full bg-background-tertiary border border-white/10 rounded-2xl p-5 space-y-4">
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

      {/* JIRA connection status */}
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
            Board access is respected automatically.
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

      {/* Approval form — shown once connected or always (user can skip auth) */}
      <form onSubmit={handleApprove} className="space-y-3">
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
          <Button
            type="submit"
            className="flex-1"
            disabled={isLoading}
          >
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
