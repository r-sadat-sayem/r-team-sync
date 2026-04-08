// components/chat/InlinePRDOutlineForm.tsx
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CheckCircle2, Pencil, Send, Loader2, ListChecks } from 'lucide-react';
import { Button } from '../ui/Button';
import type { InterruptPayload } from '../../types';

interface Props {
  interrupt: InterruptPayload;
  isLoading: boolean;
  onSubmit: (data: { decision: string; feedback?: string }) => void;
}

export function InlinePRDOutlineForm({ interrupt, isLoading, onSubmit }: Props) {
  const [mode, setMode]         = useState<'review' | 'revise'>('review');
  const [feedback, setFeedback] = useState('');
  const [fbError, setFbError]   = useState('');

  const handleApprove = () => {
    onSubmit({ decision: 'approve' });
  };

  const handleRevise = () => {
    const trimmed = feedback.trim();
    if (!trimmed) { setFbError('Please describe what to change.'); return; }
    setFbError('');
    onSubmit({ decision: 'revise', feedback: trimmed });
  };

  return (
    <div className="max-w-xl w-full bg-background-tertiary border border-white/10 rounded-2xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
          <ListChecks className="w-4 h-4 text-primary-light" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-text-primary">PRD Outline Ready</p>
          <p className="text-xs text-text-muted mt-0.5">{interrupt.message}</p>
        </div>
      </div>

      {/* Outline preview */}
      {interrupt.outline && (
        <div className="rounded-xl bg-black/20 border border-white/5 px-4 py-3 max-h-72 overflow-y-auto">
          <div className="text-sm text-text-secondary leading-relaxed markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {interrupt.outline}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {mode === 'review' ? (
        /* ── Approve / request changes ── */
        <div className="flex gap-2">
          <Button
            className="flex-1"
            onClick={handleApprove}
            disabled={isLoading}
          >
            {isLoading
              ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Generating…</>
              : <><CheckCircle2 className="w-4 h-4 mr-2" />Looks good — generate PRD</>}
          </Button>
          <Button
            variant="secondary"
            onClick={() => setMode('revise')}
            disabled={isLoading}
          >
            <Pencil className="w-4 h-4 mr-2" />Request changes
          </Button>
        </div>
      ) : (
        /* ── Revision feedback ── */
        <div className="space-y-3">
          <textarea
            className="w-full rounded-xl bg-black/20 border border-white/10 px-3 py-2 text-sm text-text-primary placeholder-text-muted resize-none focus:outline-none focus:border-primary/50 transition-colors"
            rows={3}
            placeholder="Describe what you'd like changed…"
            value={feedback}
            onChange={e => { setFeedback(e.target.value); setFbError(''); }}
            disabled={isLoading}
            autoFocus
          />
          {fbError && <p className="text-xs text-red-400">{fbError}</p>}
          <div className="flex gap-2">
            <Button className="flex-1" onClick={handleRevise} disabled={isLoading}>
              {isLoading
                ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Sending…</>
                : <><Send className="w-4 h-4 mr-2" />Send feedback</>}
            </Button>
            <Button variant="ghost" onClick={() => setMode('review')} disabled={isLoading}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
