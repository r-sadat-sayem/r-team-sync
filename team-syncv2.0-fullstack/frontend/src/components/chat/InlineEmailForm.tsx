// components/chat/InlineEmailForm.tsx
// Rendered inline in the chat flow when interrupt.form === 'email_form'
import React, { useState } from 'react';
import { Mail, Send, Loader2, Award } from 'lucide-react';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';

interface Props {
  message: string;
  score?: number;
  grade?: string;
  isLoading: boolean;
  onSubmit: (data: { name: string; email: string }) => void;
}

export function InlineEmailForm({ message, score, grade, isLoading, onSubmit }: Props) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [errors, setErrors] = useState<{ name?: string; email?: string }>({});

  const gradeColors: Record<string, string> = {
    A: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30',
    B: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
    C: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
    D: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
    F: 'text-red-400 bg-red-400/10 border-red-400/30',
  };

  const validate = () => {
    const e: typeof errors = {};
    if (!name.trim()) e.name = 'Name is required';
    if (!email.trim()) e.email = 'Email is required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) e.email = 'Invalid email';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = (ev: React.FormEvent) => {
    ev.preventDefault();
    if (validate()) onSubmit({ name: name.trim(), email: email.trim() });
  };

  return (
    <div className="max-w-md w-full bg-background-tertiary border border-white/10 rounded-2xl p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
          <Mail className="w-4 h-4 text-primary-light" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-text-primary">Email your PRD</p>
          <p className="text-xs text-text-muted mt-0.5">{message}</p>
        </div>
        {score !== undefined && grade && (
          <span className={`px-2 py-1 rounded-lg text-xs font-bold border flex-shrink-0 flex items-center gap-1 ${gradeColors[grade] || gradeColors.F}`}>
            <Award className="w-3 h-3" />
            {grade} · {score}/100
          </span>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <Input
          placeholder="Your full name"
          value={name}
          onChange={e => setName(e.target.value)}
          error={errors.name}
          disabled={isLoading}
        />
        <Input
          type="email"
          placeholder="your@email.com"
          value={email}
          onChange={e => setEmail(e.target.value)}
          error={errors.email}
          disabled={isLoading}
        />
        <Button
          type="submit"
          className="w-full"
          disabled={isLoading}
        >
          {isLoading
            ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Sending…</>
            : <><Send className="w-4 h-4 mr-2" />Send PRD</>
          }
        </Button>
      </form>
    </div>
  );
}
