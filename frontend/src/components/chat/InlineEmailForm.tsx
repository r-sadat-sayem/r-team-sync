// components/chat/InlineEmailForm.tsx
import React, { useState, useCallback } from 'react';
import { Mail, Send, Loader2, Award, ExternalLink, CheckCircle, SkipForward } from 'lucide-react';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { api } from '../../services/api';
import type { InterruptPayload } from '../../types';

interface Props {
  interrupt: InterruptPayload;
  sessionId: string;
  isLoading: boolean;
  onSubmit: (data: { name: string; email: string }) => void;
}

const gradeColors: Record<string, string> = {
  A: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30',
  B: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
  C: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  D: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
  F: 'text-red-400 bg-red-400/10 border-red-400/30',
};

export function InlineEmailForm({ interrupt, sessionId, isLoading, onSubmit }: Props) {
  const [step, setStep]             = useState<'confirm' | 'form'>('confirm');
  const [name, setName]             = useState('');
  const [email, setEmail]           = useState('');
  const [errors, setErrors]         = useState<{ name?: string; email?: string }>({});
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected]   = useState(interrupt.gmail_connected ?? false);
  const [gmailUser, setGmailUser]   = useState(interrupt.gmail_user ?? null);

  const { score, grade } = interrupt;

  const pollStatus = useCallback(async () => {
    try {
      const s = await api.getGmailAuthStatus(sessionId);
      if (s.connected) { setConnected(true); setGmailUser(s.email); }
    } catch { /* silent */ }
    finally { setConnecting(false); }
  }, [sessionId]);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      const url = await api.getGmailConnectUrl(sessionId);
      const popup = window.open(url, 'gmail-oauth', 'width=520,height=680,left=200,top=100');
      const handler = (e: MessageEvent) => {
        if (e.data?.type === 'gmail_oauth') {
          window.removeEventListener('message', handler);
          popup?.close();
          pollStatus();
        }
      };
      window.addEventListener('message', handler);
      const t = setInterval(() => {
        if (popup?.closed) { clearInterval(t); window.removeEventListener('message', handler); pollStatus(); }
      }, 500);
    } catch { setConnecting(false); }
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
    <div className="w-full max-w-md bg-background-tertiary border border-white/10 rounded-2xl p-4 sm:p-5 space-y-4">
      {step === 'confirm' ? (
        /* ── Confirm step ── */
        <>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
              <Mail className="w-4 h-4 text-primary-light" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-text-primary">PRD ready!</p>
              <p className="text-xs text-text-muted mt-0.5">Would you like to email it to someone?</p>
            </div>
            {score !== undefined && grade && (
              <span className={`px-2 py-1 rounded-lg text-xs font-bold border flex-shrink-0 flex items-center gap-1 ${gradeColors[grade] ?? gradeColors.F}`}>
                <Award className="w-3 h-3" />{grade} · {score}/100
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Button className="flex-1" onClick={() => setStep('form')} disabled={isLoading}>
              <Mail className="w-4 h-4 mr-2" />Send Email →
            </Button>
            <Button
              variant="ghost"
              onClick={() => onSubmit({ name: '', email: '__skip__' })}
              disabled={isLoading}
              title="Skip email"
            >
              <SkipForward className="w-4 h-4" />
            </Button>
          </div>
        </>
      ) : (
        /* ── Form step ── */
        <>
          {/* Header */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary/20 flex items-center justify-center flex-shrink-0">
              <Mail className="w-4 h-4 text-primary-light" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-text-primary">Email your PRD</p>
              <p className="text-xs text-text-muted mt-0.5">{interrupt.message}</p>
            </div>
            {score !== undefined && grade && (
              <span className={`px-2 py-1 rounded-lg text-xs font-bold border flex-shrink-0 flex items-center gap-1 ${gradeColors[grade] ?? gradeColors.F}`}>
                <Award className="w-3 h-3" />{grade} · {score}/100
              </span>
            )}
          </div>

          {/* Gmail connection status */}
          {connected ? (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              <span>Sending as <strong>{gmailUser}</strong></span>
            </div>
          ) : (
            <div className="space-y-2">
              <Button type="button" variant="secondary" className="w-full"
                onClick={handleConnect} disabled={connecting || isLoading}>
                {connecting
                  ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Connecting…</>
                  : <><ExternalLink className="w-4 h-4 mr-2" />Connect Gmail to send</>}
              </Button>
              <p className="text-xs text-text-muted text-center">
                or continue — email will use the shared sender account
              </p>
            </div>
          )}

          {/* Recipient form */}
          <form onSubmit={handleSubmit} className="space-y-3">
            <Input placeholder="Recipient's full name" value={name}
              onChange={e => setName(e.target.value)} error={errors.name} disabled={isLoading} />
            <Input type="email" placeholder="recipient@email.com" value={email}
              onChange={e => setEmail(e.target.value)} error={errors.email} disabled={isLoading} />
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading
                ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Sending…</>
                : <><Send className="w-4 h-4 mr-2" />Send PRD</>}
            </Button>
          </form>
        </>
      )}
    </div>
  );
}
