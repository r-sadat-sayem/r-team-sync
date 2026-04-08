// components/dashboard/Dashboard.tsx

import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { api } from '../../services/api';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { FileText, Mail, Ticket, Clock, Star, ArrowRight, Plus } from 'lucide-react';
import type { ActivityItem } from '../../types';

export function Dashboard() {
  const navigate = useNavigate();
  const { state } = useApp();
  const history = api.getPRDHistory();

  const stats = {
    totalPRDs: history.length,
    averageQuality: history.length > 0
      ? Math.round(history.reduce((acc, prd) => acc + prd.qualityScore, 0) / history.length)
      : 0,
    totalJIRATickets: state.jiraTickets.length,
    emailsSent: history.filter(prd => prd.grade).length,
  };

  const recentActivity: ActivityItem[] = [
    ...history.slice(0, 5).map((prd, index) => ({
      id: `prd-${index}`,
      type: 'prd_created' as const,
      description: `PRD "${prd.title}" generated with ${prd.grade} grade`,
      timestamp: new Date(prd.createdAt),
      metadata: { qualityScore: prd.qualityScore },
    })),
  ];

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'A': return 'text-grade-a';
      case 'B': return 'text-grade-b';
      case 'C': return 'text-grade-c';
      case 'D': return 'text-grade-d';
      default: return 'text-grade-f';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Dashboard</h1>
          <p className="text-text-secondary">Overview of your PRD automation activity</p>
        </div>
        <Button onClick={() => navigate('/')}>
          <Plus className="w-4 h-4 mr-2" />
          New PRD
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-muted">Total PRDs</p>
                <p className="text-3xl font-bold text-text-primary mt-1">{stats.totalPRDs}</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
                <FileText className="w-6 h-6 text-primary-light" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-muted">Avg Quality</p>
                <div className="flex items-baseline gap-2 mt-1">
                  <p className="text-3xl font-bold text-text-primary">{stats.averageQuality}</p>
                  <span className="text-sm text-text-muted">/100</span>
                </div>
              </div>
              <div className="w-12 h-12 rounded-xl bg-grade-b/20 flex items-center justify-center">
                <Star className="w-6 h-6 text-grade-b" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-muted">JIRA Tickets</p>
                <p className="text-3xl font-bold text-text-primary mt-1">{stats.totalJIRATickets}</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-status-info/20 flex items-center justify-center">
                <Ticket className="w-6 h-6 text-status-info" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-muted">Emails Sent</p>
                <p className="text-3xl font-bold text-text-primary mt-1">{stats.emailsSent}</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-status-success/20 flex items-center justify-center">
                <Mail className="w-6 h-6 text-status-success" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent PRDs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Recent PRDs</CardTitle>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <div className="text-center py-8">
                <FileText className="w-12 h-12 text-text-muted mx-auto mb-3" />
                <p className="text-text-secondary mb-4">No PRDs generated yet</p>
                <Button size="sm" onClick={() => navigate('/')}>Create First PRD</Button>
              </div>
            ) : (
              <div className="space-y-3">
                {history.slice(0, 5).map((prd) => (
                  <div
                    key={prd.id}
                    onClick={() => navigate(`/prd/${prd.id}`)}
                    className="flex items-center justify-between p-3 rounded-lg bg-background-tertiary hover:bg-white/5 cursor-pointer transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-text-muted" />
                      <div>
                        <p className="font-medium text-text-primary text-sm">{prd.title}</p>
                        <p className="text-xs text-text-muted">
                          {new Date(prd.createdAt).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-sm font-medium ${getGradeColor(prd.grade)}`}>
                        {prd.grade}
                      </span>
                      <ArrowRight className="w-4 h-4 text-text-muted" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Activity Timeline */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            {recentActivity.length === 0 ? (
              <div className="text-center py-8">
                <Clock className="w-12 h-12 text-text-muted mx-auto mb-3" />
                <p className="text-text-secondary">No activity yet</p>
              </div>
            ) : (
              <div className="space-y-4">
                {recentActivity.map((activity) => (
                  <div key={activity.id} className="flex gap-3">
                    <div className="w-2 h-2 rounded-full bg-primary mt-2 flex-shrink-0" />
                    <div>
                      <p className="text-sm text-text-primary">{activity.description}</p>
                      <p className="text-xs text-text-muted">
                        {new Date(activity.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
