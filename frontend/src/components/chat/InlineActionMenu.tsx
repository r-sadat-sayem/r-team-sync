// components/chat/InlineActionMenu.tsx
// Post-PRD action menu — shown after PRD generation completes.
// User can trigger email, test cases, JIRA creation, or finish.
import { Mail, TestTube, Ticket, CheckCircle2, Loader2, Award } from 'lucide-react';
import { Button } from '../ui/Button';
import type { InterruptPayload } from '../../types';

interface Props {
  interrupt: InterruptPayload;
  isLoading: boolean;
  onSubmit: (data: { action: string }) => void;
}

const gradeColors: Record<string, string> = {
  A: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30',
  B: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
  C: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  D: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
  F: 'text-red-400 bg-red-400/10 border-red-400/30',
};

export function InlineActionMenu({ interrupt, isLoading, onSubmit }: Props) {
  const { score, grade, actions_taken = [] } = interrupt;
  const done = (action: string) => actions_taken.includes(action);

  return (
    <div className="max-w-xl w-full bg-background-tertiary border border-white/10 rounded-2xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
          <CheckCircle2 className="w-4 h-4 text-primary-light" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-text-primary">PRD ready!</p>
          <p className="text-xs text-text-muted mt-0.5">{interrupt.message}</p>
        </div>
        {score !== undefined && grade && (
          <span className={`px-2 py-1 rounded-lg text-xs font-bold border flex-shrink-0 flex items-center gap-1 ${gradeColors[grade] ?? gradeColors.F}`}>
            <Award className="w-3 h-3" />{grade} · {score}/100
          </span>
        )}
      </div>

      {/* Action buttons */}
      <div className="grid grid-cols-2 gap-2">
        <Button
          variant={done('email') ? 'ghost' : 'secondary'}
          disabled={isLoading || done('email')}
          onClick={() => onSubmit({ action: 'email' })}
          className="flex items-center justify-center gap-2"
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
          {done('email') ? 'Email sent ✓' : 'Send Email'}
        </Button>

        <Button
          variant={done('test_cases') ? 'ghost' : 'secondary'}
          disabled={isLoading || done('test_cases')}
          onClick={() => onSubmit({ action: 'test_cases' })}
          className="flex items-center justify-center gap-2"
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <TestTube className="w-4 h-4" />}
          {done('test_cases') ? 'Tests generated ✓' : 'Generate Test Cases'}
        </Button>

        <Button
          variant={done('jira') ? 'ghost' : 'secondary'}
          disabled={isLoading || done('jira')}
          onClick={() => onSubmit({ action: 'jira' })}
          className="flex items-center justify-center gap-2"
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Ticket className="w-4 h-4" />}
          {done('jira') ? 'JIRA created ✓' : 'Create JIRA Tickets'}
        </Button>

        <Button
          variant="ghost"
          disabled={isLoading}
          onClick={() => onSubmit({ action: 'done' })}
          className="flex items-center justify-center gap-2"
        >
          <CheckCircle2 className="w-4 h-4" />
          Done
        </Button>
      </div>
    </div>
  );
}
