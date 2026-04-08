// components/chat/PRDArtifactCard.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Download, ExternalLink,
  ChevronDown, ChevronRight, Award, TestTube, LayoutList,
} from 'lucide-react';
import { Button } from '../ui/Button';
import type { PRDDocument } from '../../types';

interface Props {
  prd: PRDDocument;
}

const gradeColors: Record<string, string> = {
  A: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30',
  B: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
  C: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  D: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
  F: 'text-red-400 bg-red-400/10 border-red-400/30',
};

export function PRDArtifactCard({ prd }: Props) {
  const navigate = useNavigate();
  const [previewOpen, setPreviewOpen] = useState(false);

  const isTC = prd.docType === 'test_cases';

  const handleDownload = () => {
    const blob = new Blob([prd.content], { type: 'text/markdown' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = prd.fileName || `${prd.title.replace(/\s+/g, '_').toLowerCase()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const sectionCount = prd.sections?.length ?? 0;
  const createdDate  = new Date(prd.createdAt).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });

  return (
    <div className="max-w-md w-full bg-background-tertiary border border-white/10 rounded-2xl p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
          {isTC
            ? <TestTube className="w-4 h-4 text-primary-light" />
            : <FileText className="w-4 h-4 text-primary-light" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-text-primary truncate">
            {isTC ? 'Test Cases: ' : ''}{prd.title}
          </p>
          <p className="text-xs text-text-muted mt-0.5 truncate">
            {prd.fileName || `${prd.title.replace(/\s+/g, '_').toLowerCase()}.md`}
          </p>
        </div>
        {isTC ? (
          <span className="px-2 py-1 rounded-lg text-xs font-bold border flex-shrink-0 flex items-center gap-1 text-violet-400 bg-violet-400/10 border-violet-400/30">
            <TestTube className="w-3 h-3" />{prd.testCaseCount} TCs
          </span>
        ) : (
          <span className={`px-2 py-1 rounded-lg text-xs font-bold border flex-shrink-0 flex items-center gap-1 ${gradeColors[prd.grade] ?? gradeColors.F}`}>
            <Award className="w-3 h-3" />{prd.grade} · {prd.qualityScore}/100
          </span>
        )}
      </div>

      {/* Meta row */}
      <div className="flex items-center gap-4 text-xs text-text-muted pl-0.5">
        {!isTC && sectionCount > 0 && (
          <span className="flex items-center gap-1">
            <LayoutList className="w-3 h-3" />{sectionCount} sections
          </span>
        )}
        {isTC && (
          <span className="flex items-center gap-1">
            <TestTube className="w-3 h-3" />{prd.testCaseCount} test cases
          </span>
        )}
        <span>{createdDate}</span>
      </div>

      {/* Collapsible preview */}
      <button
        onClick={() => setPreviewOpen(v => !v)}
        className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary transition-colors"
      >
        {previewOpen
          ? <ChevronDown className="w-3.5 h-3.5" />
          : <ChevronRight className="w-3.5 h-3.5" />}
        {previewOpen ? 'Hide preview' : 'Preview'}
      </button>
      {previewOpen && (
        <div className="max-h-48 overflow-y-auto rounded-lg bg-black/20 border border-white/5 p-3">
          <pre className="text-xs text-text-secondary whitespace-pre-wrap font-mono leading-5">
            {prd.content.slice(0, 600)}{prd.content.length > 600 ? '\n…' : ''}
          </pre>
        </div>
      )}

      {/* Action row */}
      <div className="flex flex-wrap gap-2 pt-0.5">
        <Button variant="secondary" size="sm" className="flex-1" onClick={handleDownload}>
          <Download className="w-3.5 h-3.5 mr-1.5" />Download .md
        </Button>
        {!isTC && (
          <Button variant="ghost" size="sm" className="flex-1" onClick={() => navigate(`/prd/${prd.id}`)}>
            <ExternalLink className="w-3.5 h-3.5 mr-1.5" />Open in Viewer
          </Button>
        )}
      </div>
    </div>
  );
}
