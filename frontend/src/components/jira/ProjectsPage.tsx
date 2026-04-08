// components/jira/ProjectsPage.tsx
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ChevronLeft, CheckCircle, ExternalLink, Folders,
  Kanban, Link2, Loader2, Plus, Search, X,
} from 'lucide-react';
import { api } from '../../services/api';
import { useApp } from '../../context/AppContext';
import { Card, CardContent } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';

interface JiraProject {
  id: string;
  key: string;
  name: string;
  projectTypeKey?: string;
  avatarUrls?: Record<string, string>;
}

interface JiraBoard {
  id: number;
  name: string;
  type: string;
  self?: string;
  location?: { projectKey?: string; projectName?: string };
}

// ── Derive cloud base URL from the stored project_url or cloud_name ──────────
function cloudBase(
  projectUrl: string | null | undefined,
  cloudName: string | null | undefined,
): string | null {
  if (projectUrl) return projectUrl.replace(/\/(browse|projects)\/.*$/, '');
  if (cloudName) {
    if (cloudName.startsWith('http://') || cloudName.startsWith('https://')) {
      return cloudName.replace(/\/$/, '');
    }
    // cloud_name may be "myorg" or "myorg.atlassian.net"
    const host = cloudName.includes('.') ? cloudName : `${cloudName}.atlassian.net`;
    return `https://${host}`;
  }
  return null;
}

// ── Direct-create modal ───────────────────────────────────────────────────────

interface CreateModalProps {
  projectKey: string;
  cloudUrl: string | null;
  defaultPrd?: string;
  onClose: () => void;
}

function CreateModal({ projectKey, cloudUrl: _cloudUrl, defaultPrd, onClose }: CreateModalProps) {
  const [prd, setPrd] = useState(defaultPrd ?? '');
  const [assignee, setAssignee] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ epic_key: string; epic_url: string; task_keys: string[] } | null>(null);
  const [error, setError] = useState('');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prd.trim()) { setError('Paste PRD markdown to create tickets.'); return; }
    setError('');
    setLoading(true);
    try {
      const r = await api.createJiraTickets({
        prd_markdown: prd,
        feature_name: projectKey,
        project_key: projectKey,
        assignee_email: assignee,
      });
      setResult(r);
    } catch (err: any) {
      setError(err.message || 'Creation failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg bg-background-secondary border border-white/10 rounded-2xl p-6 space-y-4 shadow-2xl">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-text-primary">Create tickets in <span className="font-mono text-primary-light">{projectKey}</span></h3>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {result ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-emerald-400 text-sm">
              <CheckCircle className="w-4 h-4" />
              Tickets created successfully
            </div>
            <a
              href={result.epic_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 text-sm text-primary-light hover:underline"
            >
              <div className="w-3 h-3 rounded-full bg-purple-500 flex-shrink-0" />
              Epic: {result.epic_key}
              <ExternalLink className="w-3 h-3" />
            </a>
            {result.task_keys.map(k => (
              <div key={k} className="flex items-center gap-2 text-sm text-text-secondary pl-1">
                <div className="w-2.5 h-2.5 rounded bg-blue-500 flex-shrink-0" />
                Story: {k}
              </div>
            ))}
            <Button className="w-full" onClick={onClose}>Done</Button>
          </div>
        ) : (
          <form onSubmit={handleCreate} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1">PRD Markdown</label>
              <textarea
                className="w-full h-40 bg-background-tertiary border border-white/10 rounded-lg p-3 text-sm text-text-primary resize-none focus:outline-none focus:border-primary/50 font-mono"
                placeholder="Paste your PRD markdown here…"
                value={prd}
                onChange={e => setPrd(e.target.value)}
                disabled={loading}
              />
            </div>
            <Input
              type="email"
              placeholder="Assignee email (optional)"
              value={assignee}
              onChange={e => setAssignee(e.target.value)}
              disabled={loading}
            />
            {error && <p className="text-red-400 text-xs">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading
                ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Creating…</>
                : <><Plus className="w-4 h-4 mr-2" />Create Tickets</>
              }
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}

// ── Project detail (boards list) ──────────────────────────────────────────────

function ProjectDetail({
  projectKey,
  cloudUrl,
  projectType,
  defaultPrd,
}: {
  projectKey: string;
  cloudUrl: string | null;
  projectType?: string;
  defaultPrd?: string;
}) {
  const navigate = useNavigate();
  const [boards, setBoards] = useState<JiraBoard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError('');
    api.getJiraBoards(projectKey)
      .then(r => setBoards(r.boards))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [projectKey]);

  const openBoard = (board: JiraBoard) => {
    if (!cloudUrl) return;
    const isBusiness = projectType === 'business';
    const path = isBusiness
      ? `core/projects/${projectKey}/board`
      : `software/projects/${projectKey}/boards/${board.id}`;
    window.open(`${cloudUrl}/${path}`, '_blank');
  };

  return (
    <>
      {showCreate && (
        <CreateModal
          projectKey={projectKey}
          cloudUrl={cloudUrl}
          defaultPrd={defaultPrd}
          onClose={() => setShowCreate(false)}
        />
      )}

      <div className="space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate('/projects')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              All Projects
            </Button>
            <h2 className="text-xl font-bold text-text-primary">
              Boards — <span className="font-mono text-primary-light">{projectKey}</span>
            </h2>
          </div>
          <div className="flex items-center gap-2">
            {cloudUrl && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => window.open(`${cloudUrl}/projects/${projectKey}`, '_blank')}
                title="Open project in Jira"
              >
                <ExternalLink className="w-4 h-4 mr-1" />
                Open in Jira
              </Button>
            )}
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <Plus className="w-4 h-4 mr-1" />
              Create Tickets
            </Button>
          </div>
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-text-secondary py-8">
            <Loader2 className="w-4 h-4 animate-spin" />Loading boards…
          </div>
        )}
        {error && <p className="text-red-400 text-sm">{error}</p>}
        {!loading && !error && boards.length === 0 && (
          <Card>
            <CardContent className="py-10 text-center text-text-muted">
              No boards found for this project.
            </CardContent>
          </Card>
        )}

        <div className="grid gap-3">
          {boards.map(board => (
            <Card key={board.id}>
              <CardContent className="p-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                    <Kanban className="w-4 h-4 text-blue-400" />
                  </div>
                  <div>
                    <p className="font-medium text-text-primary">{board.name}</p>
                    <p className="text-xs text-text-muted capitalize">{board.type} board · ID {board.id}</p>
                  </div>
                </div>
                {cloudUrl && (
                  <Button variant="ghost" size="sm" onClick={() => openBoard(board)} title="Open board in Jira">
                    <ExternalLink className="w-4 h-4" />
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </>
  );
}

// ── Projects list ─────────────────────────────────────────────────────────────

export function ProjectsPage() {
  const navigate = useNavigate();
  const { key } = useParams<{ key?: string }>();
  const { state } = useApp();
  const jira = state.jiraConnection;
  const cloud = cloudBase(jira?.project_url, jira?.cloud_name);

  const [query, setQuery] = useState('');
  const [projects, setProjects] = useState<JiraProject[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);

  // Latest PRD from any chat tab — pre-fills the create modal
  const defaultPrd = state.tabs
    .map(t => t.currentPRD?.content)
    .filter(Boolean)[0] ?? '';

  const fetchProjects = useCallback((q: string) => {
    setLoading(true);
    setError('');
    api.getJiraProjects(q || undefined)
      .then(r => { setProjects(r.projects); setLoaded(true); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Auto-load when connected; only show data if Jira is connected
  useEffect(() => {
    if (jira?.connected) fetchProjects('');
  }, [jira?.connected, fetchProjects]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchProjects(query);
  };

  // ── Project detail view ──────────────────────────────────────────────────
  if (key) {
    const proj = projects.find(p => p.key === key);
    return (
      <ProjectDetail
        projectKey={key}
        cloudUrl={cloud}
        projectType={proj?.projectTypeKey}
        defaultPrd={defaultPrd}
      />
    );
  }

  // ── Not connected ────────────────────────────────────────────────────────
  if (!jira?.connected) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-text-primary flex items-center gap-3">
          <Folders className="w-6 h-6 text-primary-light" />
          Projects
        </h1>
        <Card className="max-w-md">
          <CardContent className="p-6 text-center space-y-4">
            <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center mx-auto">
              <Link2 className="w-6 h-6 text-primary-light" />
            </div>
            <div>
              <p className="font-medium text-text-primary mb-1">Connect your Jira account</p>
              <p className="text-sm text-text-muted">
                Link your Atlassian account once and browse all projects seamlessly.
              </p>
            </div>
            <Button className="w-full" onClick={() => navigate('/jira')}>
              Go to JIRA Settings
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Connected: project list ──────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary flex items-center gap-3">
            <Folders className="w-6 h-6 text-primary-light" />
            Projects
          </h1>
          <p className="text-xs text-text-muted mt-1">
            Browsing as <strong>{jira.user_name}</strong>
            {jira.cloud_name ? ` · ${jira.cloud_name}` : ''}
          </p>
        </div>
        {loaded && (
          <span className="text-sm text-text-muted">
            {projects.length} project{projects.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted pointer-events-none" />
          <Input
            placeholder="Search by project name or key…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button type="submit" disabled={loading}>
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
        </Button>
      </form>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {loading && (
        <div className="flex items-center gap-2 text-text-secondary py-8">
          <Loader2 className="w-4 h-4 animate-spin" />Loading projects…
        </div>
      )}

      {!loading && loaded && projects.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-text-muted">
            No projects found{query ? ` for "${query}"` : ''}.
          </CardContent>
        </Card>
      )}

      <div className="grid gap-3">
        {projects.map(project => (
          <Card
            key={project.id}
            className="cursor-pointer hover:border-primary/40 transition-colors"
            onClick={() => navigate(`/projects/${project.key}`)}
          >
            <CardContent className="p-4 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                {project.avatarUrls?.['24x24'] ? (
                  <img src={project.avatarUrls['24x24']} alt="" className="w-9 h-9 rounded-lg" />
                ) : (
                  <div className="w-9 h-9 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-bold text-primary-light">
                      {project.key.slice(0, 2)}
                    </span>
                  </div>
                )}
                <div>
                  <p className="font-medium text-text-primary">{project.name}</p>
                  <p className="text-xs text-text-muted font-mono">{project.key}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {cloud && (
                  <button
                    className="text-text-muted hover:text-text-secondary transition-colors"
                    onClick={e => { e.stopPropagation(); window.open(`${cloud}/projects/${project.key}`, '_blank'); }}
                    title="Open in Jira"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </button>
                )}
                <ChevronLeft className="w-4 h-4 text-text-muted rotate-180" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
