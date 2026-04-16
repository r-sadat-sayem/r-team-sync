// components/prd/PRDViewer.tsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useApp } from '../../context/AppContext';
import { api } from '../../services/api';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { Download, Copy, Check, FileText, ChevronLeft, Mail, Ticket, ChevronDown, AlertTriangle, MessageSquare } from 'lucide-react';
import type { PRDDocument } from '../../types';

export function PRDViewer() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { activeTab, dispatch } = useApp();
  const [prd, setPrd] = useState<PRDDocument | null>(null);
  const [copied, setCopied] = useState(false);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [tocOpen, setTocOpen] = useState(false);

  useEffect(() => {
    if (id) {
      const found = api.getPRDById(id);
      if (found) {
        setPrd(found);
      }
    } else if (activeTab.currentPRD) {
      setPrd(activeTab.currentPRD);
    }
  }, [id, activeTab.currentPRD]);

  const handleCopy = async () => {
    if (prd?.content) {
      await navigator.clipboard.writeText(prd.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    if (prd?.content) {
      const blob = new Blob([prd.content], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = prd.fileName || `${prd.title.replace(/\s+/g, '_').toLowerCase()}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'A': return 'text-grade-a bg-grade-a/20 border-grade-a/30';
      case 'B': return 'text-grade-b bg-grade-b/20 border-grade-b/30';
      case 'C': return 'text-grade-c bg-grade-c/20 border-grade-c/30';
      case 'D': return 'text-grade-d bg-grade-d/20 border-grade-d/30';
      default: return 'text-grade-f bg-grade-f/20 border-grade-f/30';
    }
  };

  if (!prd) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-8rem)] text-center">
        <FileText className="w-16 h-16 text-text-muted mb-4" />
        <h3 className="text-xl font-semibold text-text-primary mb-2">No PRD Selected</h3>
        <p className="text-text-secondary max-w-md mb-6">
          Start a conversation in the chat to generate a PRD, or select one from your history.
        </p>
        <Button onClick={() => navigate('/')}>
          Start New Chat
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-4">
          {id && (
            <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              Back
            </Button>
          )}
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-text-primary">{prd.title}</h1>
            <p className="text-sm text-text-muted">
              Created {new Date(prd.createdAt).toLocaleDateString()}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Quality Badge */}
          <span className={`px-3 py-1 rounded-full text-sm font-medium border ${getGradeColor(prd.grade)}`}>
            {prd.grade} Grade • {prd.qualityScore}/100
          </span>

          {/* Chat reference */}
          {prd.sessionId && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                dispatch({ type: 'RESTORE_SESSION', payload: { sessionId: prd.sessionId!, label: prd.title } });
                navigate('/');
              }}
              title="Open the chat session that generated this PRD"
            >
              <MessageSquare className="w-4 h-4 mr-2" />
              View Chat
            </Button>
          )}

          {/* Actions */}
          <Button variant="secondary" size="sm" onClick={handleCopy}>
            {copied ? <Check className="w-4 h-4 mr-2" /> : <Copy className="w-4 h-4 mr-2" />}
            {copied ? 'Copied!' : 'Copy'}
          </Button>
          <Button variant="secondary" size="sm" onClick={handleDownload}>
            <Download className="w-4 h-4 mr-2" />
            Download
          </Button>
          <Button size="sm" onClick={() => navigate('/email')}>
            <Mail className="w-4 h-4 mr-2" />
            Email
          </Button>
          <Button size="sm" variant="secondary" onClick={() => navigate('/jira')}>
            <Ticket className="w-4 h-4 mr-2" />
            JIRA
          </Button>
        </div>
      </div>

      {/* Deprecated banner */}
      {prd.deprecated && (
        <div className="px-4 py-3 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-amber-400">Deprecated Version</p>
            <p className="text-xs text-amber-300/70">
              A newer version of this PRD was generated in the same session.
            </p>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Table of Contents */}
        <Card className="lg:col-span-1 h-fit">
          {/* Mobile toggle */}
          <button
            className="lg:hidden w-full flex items-center justify-between px-6 py-4 border-b border-white/8 text-sm font-medium text-text-primary"
            onClick={() => setTocOpen(v => !v)}
            aria-expanded={tocOpen}
            aria-controls="toc-content"
          >
            <span>Table of Contents</span>
            <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${tocOpen ? 'rotate-180' : ''}`} />
          </button>
          {/* Desktop header */}
          <CardHeader className="hidden lg:block">
            <CardTitle className="text-sm">Contents</CardTitle>
          </CardHeader>
          <div id="toc-content" className={tocOpen ? 'block' : 'hidden lg:block'}>
            <CardContent>
              <nav className="space-y-1">
                {prd.sections.map((section) => (
                  <button
                    key={section.id}
                    onClick={() => {
                      setActiveSection(section.id);
                      document.getElementById(section.title.toLowerCase().replace(/\s+/g, '-'))?.scrollIntoView({ behavior: 'smooth' });
                    }}
                    className={`block w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                      activeSection === section.id
                        ? 'bg-primary/20 text-primary-light'
                        : 'text-text-secondary hover:text-text-primary hover:bg-white/5'
                    }`}
                    style={{ paddingLeft: `${section.level * 12 + 12}px` }}
                  >
                    {section.title}
                  </button>
                ))}
              </nav>
            </CardContent>
          </div>
        </Card>

        {/* PRD Content */}
        <Card className="lg:col-span-3">
          <CardContent className="p-8">
            <div className="markdown-content prose prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {prd.content}
              </ReactMarkdown>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
