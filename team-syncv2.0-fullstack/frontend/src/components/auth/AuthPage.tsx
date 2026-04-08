import React, { useState } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { LockKeyhole, Sparkles } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { Button } from '../ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Input } from '../ui/Input';

interface AuthPageProps {
  mode: 'login' | 'signup';
}

export function AuthPage({ mode }: AuthPageProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user, isLoading, login, signup } = useAuth();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(searchParams.get('auth_error'));
  const [submitting, setSubmitting] = useState(false);

  if (!isLoading && user) {
    return <Navigate to="/" replace />;
  }

  const isSignup = mode === 'signup';

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (isSignup) await signup(displayName, email, password);
      else await login(email, password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogleLogin = () => {
    window.location.href = api.getGoogleLoginUrl();
  };

  return (
    <div className="min-h-screen bg-background-primary flex items-center justify-center px-6 py-12">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(79,70,229,0.16),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(59,130,246,0.14),transparent_28%)] pointer-events-none" />
      <div className="relative w-full max-w-5xl grid lg:grid-cols-[1.2fr_0.8fr] gap-8 items-stretch">
        <div className="hidden lg:flex flex-col justify-between rounded-3xl border border-white/10 bg-background-secondary p-10">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-2 text-sm text-primary-light">
              <Sparkles className="w-4 h-4" />
              TeamSync AI
            </div>
            <h1 className="mt-6 text-4xl font-bold text-text-primary leading-tight">
              Sign in to keep PRDs, chat sessions, Gmail, and JIRA access tied to your account.
            </h1>
            <p className="mt-4 text-base text-text-secondary max-w-xl">
              This app now uses account-based access instead of a shared browser key. Your sessions and integrations stay scoped to your login.
            </p>
          </div>
          <div className="grid gap-3 text-sm text-text-secondary">
            <p>Persistent chat ownership across refreshes</p>
            <p>Per-user Gmail and JIRA OAuth connections</p>
            <p>Global Gmail SMTP fallback when OAuth is not connected</p>
          </div>
        </div>

        <Card className="self-center">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center">
                <LockKeyhole className="w-6 h-6 text-white" />
              </div>
              <div>
                <CardTitle>{isSignup ? 'Create account' : 'Sign in'}</CardTitle>
                <p className="text-sm text-text-muted">
                  {isSignup ? 'Open registration for your workspace.' : 'Use your TeamSync account to continue.'}
                </p>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Button type="button" variant="secondary" className="w-full" onClick={handleGoogleLogin}>
                <svg viewBox="0 0 24 24" className="w-4 h-4 mr-2" aria-hidden="true">
                  <path fill="#EA4335" d="M12 10.2v3.9h5.4c-.2 1.3-1.5 3.9-5.4 3.9-3.2 0-5.9-2.7-5.9-6s2.7-6 5.9-6c1.8 0 3 .8 3.7 1.5l2.5-2.4C16.7 3.6 14.6 2.7 12 2.7 6.9 2.7 2.8 6.8 2.8 12S6.9 21.3 12 21.3c6.9 0 8.6-4.8 8.6-7.3 0-.5-.1-.9-.1-1.3H12Z" />
                  <path fill="#34A853" d="M2.8 12c0 5.2 4.1 9.3 9.2 9.3 5.3 0 8.6-3.6 8.6-8.7 0-.6-.1-1-.2-1.5H12v3.9h5.4c-.5 2.3-2.4 3.9-5.4 3.9-3.2 0-5.9-2.7-5.9-6Z" opacity=".001" />
                  <path fill="#FBBC05" d="M4.9 7.6 8.1 10c.9-1.8 2.2-3 3.9-3 1.8 0 3 .8 3.7 1.5l2.5-2.4C16.7 3.6 14.6 2.7 12 2.7c-3.6 0-6.8 2.1-8.2 4.9Z" />
                  <path fill="#4285F4" d="M12 21.3c2.5 0 4.7-.8 6.3-2.2l-3-2.4c-.8.6-1.8 1-3.3 1-2.9 0-4.9-1.9-5.7-4.4l-3.2 2.5c1.4 2.8 4.4 4.5 8.9 4.5Z" />
                </svg>
                Continue with Google
              </Button>

              <div className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-text-muted">
                <div className="h-px flex-1 bg-white/10" />
                <span>or</span>
                <div className="h-px flex-1 bg-white/10" />
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
              {isSignup && (
                <Input
                  label="Display Name"
                  placeholder="Your name"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  required
                />
              )}
              <Input
                label="Email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
              <Input
                label="Password"
                type="password"
                placeholder="At least 8 characters"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
              {error && (
                <div className="rounded-lg border border-status-error/30 bg-status-error/10 px-4 py-3 text-sm text-status-error">
                  {error}
                </div>
              )}
              <Button type="submit" className="w-full" isLoading={submitting}>
                {isSignup ? 'Create account' : 'Sign in'}
              </Button>
              </form>
            </div>
            <p className="mt-6 text-sm text-text-secondary">
              {isSignup ? 'Already have an account?' : 'Need an account?'}{' '}
              <Link to={isSignup ? '/login' : '/signup'} className="text-primary-light hover:underline">
                {isSignup ? 'Sign in' : 'Create one'}
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
