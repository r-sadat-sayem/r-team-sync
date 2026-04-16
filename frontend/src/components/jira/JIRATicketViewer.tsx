// components/jira/JIRATicketViewer.tsx
import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import type { JIRAApprovalForm } from '../../types';
import { useApp } from '../../context/AppContext';

import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Ticket, CheckCircle, AlertCircle, ChevronLeft, ExternalLink, Clock, User, Loader2, Link2, Link2Off, Eye, EyeOff, MessageSquare } from 'lucide-react';
import { api } from '../../services/api';


export function JIRATicketViewer() {
  const navigate = useNavigate();
  const { state, dispatch, activeTab, refreshJiraConnection } = useApp();
  const [approvalForm, setApprovalForm] = useState<JIRAApprovalForm>({
    decision: 'APPROVE',
    notes: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showApprovalForm, setShowApprovalForm] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState('');
  const [disconnecting, setDisconnecting] = useState(false);
  const [showPatForm, setShowPatForm] = useState(false);
  const [patForm, setPatForm] = useState({ base_url: '', username: '', api_token: '', project_key: '' });
  const [patError, setPatError] = useState('');
  const [savingPat, setSavingPat] = useState(false);
  const [showPat, setShowPat] = useState(false);

  const jira = state.jiraConnection;

  // Derive the board URL from the epic URL + board ID fetched from the API
  const [boardUrl, setBoardUrl] = useState<string | null>(null);
  useEffect(() => {
    const epicKey = activeTab.jiraResult?.epic_key;
    const epicUrl = activeTab.jiraResult?.epic_url;
    if (!epicKey || !epicUrl || !jira?.connected) return;

    const projectKey = epicKey.split('-')[0];
    // e.g. "https://org.atlassian.net/browse/TSA-3" → "https://org.atlassian.net"
    const cloudBase = epicUrl.replace(/\/browse\/.*$/, '');

    api.getJiraBoards(projectKey)
      .then(data => {
        const board = (data as any).boards?.[0];
        if (board?.id) {
          setBoardUrl(`${cloudBase}/jira/software/projects/${projectKey}/boards/${board.id}`);
        }
      })
      .catch(() => { /* board link is optional — fail silently */ });
  }, [activeTab.jiraResult?.epic_key, activeTab.jiraResult?.epic_url, jira?.connected]);

  const pollStatus = useCallback(async () => {
    try {
      await refreshJiraConnection();
    } finally {
      setConnecting(false);
    }
  }, [refreshJiraConnection]);

  const handleConnect = async () => {
    setConnecting(true);
    setConnectError('');
    try {
      const url = await api.getUserJiraConnectUrl();
      const popup = window.open(url, 'jira-oauth', 'width=520,height=680,left=200,top=100');

      const handler = (e: MessageEvent) => {
        if (e.data?.type === 'jira_oauth') {
          window.removeEventListener('message', handler);
          popup?.close();
          if (e.data.success === false) {
            setConnectError(e.data.message || 'JIRA OAuth failed. Check your Atlassian app callback URL and scopes.');
            setConnecting(false);
          } else {
            void pollStatus();
          }
        }
      };
      window.addEventListener('message', handler);

      const checkClosed = setInterval(() => {
        if (popup?.closed) {
          clearInterval(checkClosed);
          window.removeEventListener('message', handler);
          void pollStatus();
        }
      }, 500);
    } catch (err: any) {
      setConnectError(err.message || 'Failed to start JIRA OAuth. Is ATLASSIAN_CLIENT_ID configured?');
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await api.disconnectJira();
      dispatch({ type: 'SET_JIRA_CONNECTION', payload: { connected: false, user_name: null, cloud_name: null, user_email: null, auth_mode: null, project_url: null } });
    } finally {
      setDisconnecting(false);
    }
  };

  const handleSavePat = async (e: React.FormEvent) => {
    e.preventDefault();
    setPatError('');
    if (!patForm.base_url || !patForm.username || !patForm.api_token) {
      setPatError('Base URL, username and API token are required.');
      return;
    }
    setSavingPat(true);
    try {
      await api.saveJiraPat(patForm);
      await refreshJiraConnection();
      setShowPatForm(false);
      setPatForm({ base_url: '', username: '', api_token: '', project_key: '' });
    } catch (err: any) {
      setPatError(err.message || 'Failed to save credentials.');
    } finally {
      setSavingPat(false);
    }
  };

  const handleApprovalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    // JIRA creation is now handled inline in the chat flow via LangGraph.
    // This form is kept for legacy reference.
    dispatch({ type: 'SET_JIRA_APPROVAL_STATUS', payload: 'approved' });
    setShowApprovalForm(false);
    setIsSubmitting(false);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Done':
        return 'bg-status-success/20 text-status-success border-status-success/30';
      case 'In Progress':
        return 'bg-status-info/20 text-status-info border-status-info/30';
      default:
        return 'bg-text-muted/20 text-text-muted border-text-muted/30';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'Epic':
        return <div className="w-3 h-3 rounded-full bg-purple-500" />;
      case 'Task':
        return <div className="w-3 h-3 rounded bg-status-info" />;
      case 'Subtask':
        return <div className="w-3 h-3 rounded-sm bg-text-secondary" />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard')}>
            <ChevronLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
          <h1 className="text-2xl font-bold text-text-primary">JIRA Tickets</h1>
        </div>
        {boardUrl && (
          <Button variant="secondary" onClick={() => window.open(boardUrl, '_blank')}>
            <ExternalLink className="w-4 h-4 mr-2" />
            Open Board
          </Button>
        )}
      </div>

      {/* JIRA Account Connection */}
      <Card>
        <CardContent className="p-5 space-y-4">
          {/* Status row */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${jira?.connected ? 'bg-emerald-500/20' : 'bg-background-tertiary'}`}>
                <Ticket className={`w-4 h-4 ${jira?.connected ? 'text-emerald-400' : 'text-text-muted'}`} />
              </div>
              <div>
                <p className="text-sm font-medium text-text-primary">Atlassian / JIRA</p>
                {jira?.connected ? (
                  <p className="text-xs text-emerald-400 mt-0.5">
                    Connected as <strong>{jira.user_name}</strong>
                    {jira.cloud_name ? ` · ${jira.cloud_name}` : ''}
                    {jira.auth_mode === 'pat' && <span className="ml-1 opacity-70">(PAT)</span>}
                  </p>
                ) : (
                  <p className="text-xs text-text-muted mt-0.5">
                    Not connected — tickets will use the service account
                  </p>
                )}
              </div>
            </div>

            {jira?.connected ? (
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-xs text-emerald-400 font-medium">Connected</span>
                </div>
                {jira.project_url && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => window.open(jira.project_url!, '_blank')}
                    title="Open JIRA project"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </Button>
                )}
                <Button variant="secondary" size="sm" onClick={handleDisconnect} disabled={disconnecting}>
                  {disconnecting
                    ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Disconnecting…</>
                    : <><Link2Off className="w-4 h-4 mr-2" />Disconnect</>}
                </Button>
              </div>
            ) : (
              <div className="flex flex-col items-end gap-1">
                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="sm" onClick={handleConnect} disabled={connecting}>
                    {connecting
                      ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Connecting…</>
                      : <><Link2 className="w-4 h-4 mr-2" />Atlassian OAuth</>}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setShowPatForm(v => !v); setConnectError(''); }}
                  >
                    {showPatForm ? 'Cancel' : 'Use PAT'}
                  </Button>
                </div>
                {connectError && (
                  <p className="text-xs text-red-400 text-right max-w-xs">{connectError}</p>
                )}
              </div>
            )}
          </div>

          {/* PAT credentials form */}
          {!jira?.connected && showPatForm && (
            <form onSubmit={handleSavePat} className="space-y-3 pt-1 border-t border-white/10">
              <p className="text-xs text-text-muted pt-2">
                Enter your JIRA server credentials. The token is stored securely per your account.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="sm:col-span-2">
                  <label className="block text-xs font-medium text-text-secondary mb-1">JIRA Base URL</label>
                  <Input
                    placeholder="https://jira.your-company.com"
                    value={patForm.base_url}
                    onChange={e => setPatForm(f => ({ ...f, base_url: e.target.value }))}
                    disabled={savingPat}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Username</label>
                  <Input
                    placeholder="your_username"
                    value={patForm.username}
                    onChange={e => setPatForm(f => ({ ...f, username: e.target.value }))}
                    disabled={savingPat}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1">Project Key</label>
                  <Input
                    placeholder="PROJ"
                    value={patForm.project_key}
                    onChange={e => setPatForm(f => ({ ...f, project_key: e.target.value }))}
                    disabled={savingPat}
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs font-medium text-text-secondary mb-1">API Token / Personal Access Token</label>
                  <div className="relative">
                    <Input
                      type={showPat ? 'text' : 'password'}
                      placeholder="Paste your token here"
                      value={patForm.api_token}
                      onChange={e => setPatForm(f => ({ ...f, api_token: e.target.value }))}
                      disabled={savingPat}
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPat(v => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors"
                      tabIndex={-1}
                    >
                      {showPat ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>
              {patError && <p className="text-xs text-red-400">{patError}</p>}
              <Button type="submit" size="sm" className="w-full" disabled={savingPat}>
                {savingPat
                  ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving…</>
                  : <><CheckCircle className="w-4 h-4 mr-2" />Save & Connect</>}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      {/* Real tickets created via LangGraph backend */}
      {activeTab.jiraResult && (
        <Card className="border-l-4 border-l-purple-500">
          <CardContent className="p-5 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
                <CheckCircle className="w-4 h-4 text-emerald-400" />
                Tickets created from PRD
              </div>
              {activeTab.sessionId && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    dispatch({ type: 'RESTORE_SESSION', payload: { sessionId: activeTab.sessionId, label: activeTab.label } });
                    navigate('/');
                  }}
                  title="Open the chat session that generated these tickets"
                  className="text-text-muted hover:text-primary-light"
                >
                  <MessageSquare className="w-3.5 h-3.5 mr-1" />
                  <span className="text-xs">View Chat</span>
                </Button>
              )}
            </div>
            <div className="space-y-2">
              <a
                href={activeTab.jiraResult.epic_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 text-sm text-primary-light hover:underline"
              >
                <div className="w-3 h-3 rounded-full bg-purple-500 flex-shrink-0" />
                Epic: {activeTab.jiraResult.epic_key}
                <ExternalLink className="w-3 h-3" />
              </a>
              {activeTab.jiraResult.task_keys.map(key => (
                <div key={key} className="flex items-center gap-2 text-sm text-text-secondary pl-1">
                  <div className="w-2.5 h-2.5 rounded bg-blue-500 flex-shrink-0" />
                  Story: {key}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {showApprovalForm && activeTab.jiraApprovalStatus === 'pending' ? (
        <Card className="max-w-2xl">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-status-warning/20 flex items-center justify-center">
                <Clock className="w-5 h-5 text-status-warning" />
              </div>
              <div>
                <CardTitle>Approve JIRA Ticket Creation</CardTitle>
                <p className="text-sm text-text-muted">
                  Review the PRD summary and approve to create tickets
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {activeTab.currentPRD ? (
              <form onSubmit={handleApprovalSubmit} className="space-y-6">
                <div className="p-4 bg-background-tertiary rounded-lg border border-white/10">
                  <p className="text-sm text-text-secondary mb-2">PRD Summary</p>
                  <p className="font-medium text-text-primary">{activeTab.currentPRD.title}</p>
                  <div className="flex items-center gap-4 mt-3 text-xs text-text-muted">
                    <span>Quality: {activeTab.currentPRD.grade}</span>
                    <span>Test Cases: {activeTab.currentPRD.testCaseCount}</span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">
                    Decision
                  </label>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="decision"
                        value="APPROVE"
                        checked={approvalForm.decision === 'APPROVE'}
                        onChange={(e) => setApprovalForm({ ...approvalForm, decision: e.target.value as any })}
                        className="w-4 h-4 text-primary"
                      />
                      <span className="text-text-primary">Approve</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="decision"
                        value="REJECT"
                        checked={approvalForm.decision === 'REJECT'}
                        onChange={(e) => setApprovalForm({ ...approvalForm, decision: e.target.value as any })}
                        className="w-4 h-4 text-primary"
                      />
                      <span className="text-text-primary">Reject</span>
                    </label>
                  </div>
                </div>

                <Input
                  label="Notes (Optional)"
                  placeholder="Add any comments for the team..."
                  value={approvalForm.notes}
                  onChange={(e) => setApprovalForm({ ...approvalForm, notes: e.target.value })}
                />

                <Button type="submit" isLoading={isSubmitting} className="w-full">
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Submit Approval
                </Button>
              </form>
            ) : (
              <div className="text-center py-8">
                <AlertCircle className="w-12 h-12 text-status-warning mx-auto mb-4" />
                <h3 className="text-lg font-medium text-text-primary mb-2">No PRD Available</h3>
                <p className="text-text-secondary mb-4">
                  Generate a PRD first before creating JIRA tickets.
                </p>
                <Button onClick={() => navigate('/')}>Start Chat</Button>
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {state.jiraTickets.length === 0 && !activeTab.jiraResult ? (
            <Card className="text-center py-12">
              <Ticket className="w-16 h-16 text-text-muted mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-text-primary mb-2">No Tickets Yet</h3>
              <p className="text-text-secondary max-w-md mx-auto mb-6">
                JIRA tickets will appear here after you approve the creation from a PRD.
              </p>
              <Button onClick={() => setShowApprovalForm(true)}>
                Create Tickets
              </Button>
            </Card>
          ) : (
            state.jiraTickets.map((ticket) => (
              <Card key={ticket.id} className={ticket.type === 'Epic' ? 'border-l-4 border-l-purple-500' : ''}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className="mt-1">{getTypeIcon(ticket.type)}</div>
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-mono text-text-muted">{ticket.key}</span>
                          <span className={`px-2 py-0.5 rounded text-xs font-medium border ${getStatusColor(ticket.status)}`}>
                            {ticket.status}
                          </span>
                          <span className="px-2 py-0.5 rounded text-xs bg-background-tertiary text-text-secondary">
                            {ticket.type}
                          </span>
                        </div>
                        <h3 className="font-medium text-text-primary">{ticket.summary}</h3>
                        {ticket.description && (
                          <p className="text-sm text-text-secondary mt-1">{ticket.description}</p>
                        )}
                        {ticket.assignee && (
                          <div className="flex items-center gap-2 mt-2 text-sm text-text-muted">
                            <User className="w-4 h-4" />
                            {ticket.assignee}
                          </div>
                        )}
                      </div>
                    </div>
                    <Button variant="ghost" size="sm">
                      <ExternalLink className="w-4 h-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}
