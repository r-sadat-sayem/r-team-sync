// components/prd/PRDViewer.tsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useApp } from '../../context/AppContext';
import { api } from '../../services/api';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { Download, Copy, Check, FileText, ChevronLeft, Mail, Ticket } from 'lucide-react';
import type { PRDDocument } from '../../types';

export function PRDViewer() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { state } = useApp();
  const [prd, setPrd] = useState<PRDDocument | null>(null);
  const [copied, setCopied] = useState(false);
  const [activeSection, setActiveSection] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      const found = api.getPRDById(id);
      if (found) {
        setPrd(found);
      }
    } else if (state.currentPRD) {
      setPrd(state.currentPRD);
    }
  }, [id, state.currentPRD]);

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
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {id && (
            <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              Back
            </Button>
          )}
          <div>
            <h1 className="text-2xl font-bold text-text-primary">{prd.title}</h1>
            <p className="text-sm text-text-muted">
              Created {new Date(prd.createdAt).toLocaleDateString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Quality Badge */}
          <span className={`px-3 py-1 rounded-full text-sm font-medium border ${getGradeColor(prd.grade)}`}>
            {prd.grade} Grade • {prd.qualityScore}/100
          </span>

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

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Table of Contents */}
        <Card className="lg:col-span-1 h-fit">
          <CardHeader>
            <CardTitle className="text-sm">Contents</CardTitle>
          </CardHeader>
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
