// components/jira/JIRATicketViewer.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { JIRAApprovalForm } from '../../types';
import { useApp } from '../../context/AppContext';

import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Ticket, CheckCircle, AlertCircle, ChevronLeft, ExternalLink, Clock, User } from 'lucide-react';


export function JIRATicketViewer() {
  const navigate = useNavigate();
  const { state, dispatch } = useApp();
  const [approvalForm, setApprovalForm] = useState<JIRAApprovalForm>({
    decision: 'APPROVE',
    notes: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showApprovalForm, setShowApprovalForm] = useState(true);

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
        {state.jiraResult?.epic_url && (
          <Button variant="secondary" onClick={() => window.open(state.jiraResult!.epic_url, '_blank')}>
            <ExternalLink className="w-4 h-4 mr-2" />
            Open Epic
          </Button>
        )}
      </div>

      {/* Real tickets created via LangGraph backend */}
      {state.jiraResult && (
        <Card className="border-l-4 border-l-purple-500">
          <CardContent className="p-5 space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              Tickets created from PRD
            </div>
            <div className="space-y-2">
              <a
                href={state.jiraResult.epic_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 text-sm text-primary-light hover:underline"
              >
                <div className="w-3 h-3 rounded-full bg-purple-500 flex-shrink-0" />
                Epic: {state.jiraResult.epic_key}
                <ExternalLink className="w-3 h-3" />
              </a>
              {state.jiraResult.task_keys.map(key => (
                <div key={key} className="flex items-center gap-2 text-sm text-text-secondary pl-1">
                  <div className="w-2.5 h-2.5 rounded bg-blue-500 flex-shrink-0" />
                  Story: {key}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {showApprovalForm && state.jiraApprovalStatus === 'pending' ? (
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
            {state.currentPRD ? (
              <form onSubmit={handleApprovalSubmit} className="space-y-6">
                <div className="p-4 bg-background-tertiary rounded-lg border border-white/10">
                  <p className="text-sm text-text-secondary mb-2">PRD Summary</p>
                  <p className="font-medium text-text-primary">{state.currentPRD.title}</p>
                  <div className="flex items-center gap-4 mt-3 text-xs text-text-muted">
                    <span>Quality: {state.currentPRD.grade}</span>
                    <span>Test Cases: {state.currentPRD.testCaseCount}</span>
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
          {state.jiraTickets.length === 0 ? (
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
