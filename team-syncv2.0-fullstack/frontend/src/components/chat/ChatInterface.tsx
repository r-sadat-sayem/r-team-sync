// components/chat/ChatInterface.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useApp } from '../../context/AppContext';
import { api } from '../../services/api';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { InlineEmailForm } from './InlineEmailForm';
import { InlineJiraForm } from './InlineJiraForm';
import { Send, Bot, User, Loader2, ExternalLink, RefreshCw } from 'lucide-react';
import type { Message, PRDDocument, SSEEvent } from '../../types';

// ── Helpers ───────────────────────────────────────────────────────────────

function buildMessage(content: string, role: 'user' | 'assistant'): Message {
  return {
    id: `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    role,
    content,
    timestamp: new Date(),
  };
}

function extractTitle(md: string): string | null {
  const m = md.match(/\*\*Project Name\*\*[:\s]+([^\n\r]+)/i);
  return m ? m[1].trim() : null;
}

function parseSections(md: string) {
  const out: { id: string; title: string; level: number; content: string }[] = [];
  const re = /^(#{1,6})\s+(.+)$/gm;
  let m;
  while ((m = re.exec(md)) !== null)
    out.push({ id: `s-${out.length}`, title: m[2], level: m[1].length, content: '' });
  return out;
}

function countTC(md: string): number {
  return (md.match(/TC\d{2,}|Test Case\s*\d+/gi) || []).length;
}

// ── Component ─────────────────────────────────────────────────────────────

export function ChatInterface() {
  const { state, dispatch } = useApp();
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Streaming state — refs avoid stale closure issues inside the generator loop
  const [streamingText, setStreamingText] = useState('');
  const [statusLabel, setStatusLabel] = useState('');
  const streamRef = useRef('');
  const prdAccRef  = useRef('');   // accumulates PRD tokens specifically
  const inPRDRef   = useRef(false); // true while generate_prd is streaming

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages, streamingText, state.interrupt]);

  // ── Flush streaming buffer → committed message ──────────────────────────
  const flushStream = useCallback(() => {
    const text = streamRef.current.trim();
    if (text) {
      dispatch({ type: 'ADD_MESSAGE', payload: buildMessage(text, 'assistant') });
    }
    streamRef.current = '';
    setStreamingText('');
    setStatusLabel('');
  }, [dispatch]);

  // ── Process a single SSE event ──────────────────────────────────────────
  const handleEvent = useCallback((ev: SSEEvent) => {
    switch (ev.type) {
      case 'token': {
        streamRef.current += ev.content;
        setStreamingText(streamRef.current);
        if (inPRDRef.current) prdAccRef.current += ev.content;
        break;
      }
      case 'status': {
        setStatusLabel(ev.message);
        // When generate_prd starts, reset the PRD accumulator
        if (ev.message.toLowerCase().includes('writing prd')) {
          inPRDRef.current = true;
          prdAccRef.current = '';
          // Start fresh streaming display for the PRD
          streamRef.current = '';
          setStreamingText('');
        }
        break;
      }
      case 'prd_complete': {
        inPRDRef.current = false;
        const markdown = prdAccRef.current || streamRef.current;
        const prd: PRDDocument = {
          id: `prd-${Date.now()}`,
          title: extractTitle(markdown) || 'Untitled PRD',
          content: markdown,
          qualityScore: ev.score,
          grade: ev.grade as any,
          createdAt: new Date(),
          sections: parseSections(markdown),
          testCaseCount: countTC(markdown),
          fileName: ev.file_name,
          sessionId: state.sessionId ?? undefined,
        };
        dispatch({ type: 'SET_CURRENT_PRD', payload: prd });
        dispatch({ type: 'ADD_PRD_TO_HISTORY', payload: prd });
        dispatch({ type: 'SET_MODE', payload: 'complete' });
        break;
      }
      case 'email_sent': {
        dispatch({ type: 'SET_EMAIL_STATUS', payload: 'sent' });
        break;
      }
      case 'jira_created': {
        dispatch({
          type: 'SET_JIRA_RESULT',
          payload: { epic_key: ev.epic_key, epic_url: ev.epic_url, task_keys: ev.task_keys },
        });
        break;
      }
      case 'interrupt': {
        // Flush any streaming text before showing the form
        flushStream();
        const { type: _, ...payload } = ev as any;
        dispatch({ type: 'SET_INTERRUPT', payload });
        break;
      }
      case 'turn_end': {
        flushStream();
        if (ev.session_id) {
          dispatch({ type: 'SET_SESSION', payload: ev.session_id });
          localStorage.setItem('current_session_id', ev.session_id);
        }
        dispatch({ type: 'SET_TYPING', payload: false });
        break;
      }
      case 'error': {
        flushStream();
        setError(ev.message);
        dispatch({ type: 'SET_TYPING', payload: false });
        break;
      }
    }
  }, [dispatch, flushStream]);

  // ── Run stream ───────────────────────────────────────────────────────────
  const runStream = useCallback(async (
    generator: AsyncGenerator<SSEEvent>,
  ) => {
    setError(null);
    dispatch({ type: 'SET_TYPING', payload: true });
    try {
      for await (const ev of generator) {
        handleEvent(ev);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Connection error';
      setError(msg);
      dispatch({ type: 'SET_TYPING', payload: false });
      flushStream();
    }
  }, [dispatch, handleEvent, flushStream]);

  // ── Send chat message ─────────────────────────────────────────────────
  const handleSend = async () => {
    if (!input.trim() || state.isTyping) return;
    const text = input.trim();
    setInput('');
    dispatch({ type: 'ADD_MESSAGE', payload: buildMessage(text, 'user') });
    await runStream(api.streamChat(text, state.sessionId));
  };

  // ── Resume: email form ────────────────────────────────────────────────
  const handleEmailSubmit = async (data: { name: string; email: string }) => {
    dispatch({ type: 'SET_INTERRUPT', payload: null });
    if (!state.sessionId) return;
    await runStream(api.resumeSession(state.sessionId, data));
  };

  // ── Resume: JIRA form ─────────────────────────────────────────────────
  const handleJiraSubmit = async (data: {
    decision: string;
    assignee_email: string;
    notes: string;
  }) => {
    dispatch({ type: 'SET_INTERRUPT', payload: null });
    if (!state.sessionId) return;
    await runStream(api.resumeSession(state.sessionId, data));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── JIRA result card (shown after create_jira completes) ───────────────
  const jiraCard = state.jiraResult && (
    <div className="flex gap-4">
      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0">
        <Bot className="w-5 h-5 text-white" />
      </div>
      <div className="max-w-[80%] bg-background-tertiary border border-white/10 rounded-2xl px-5 py-4 space-y-3">
        <p className="text-sm font-medium text-text-primary">JIRA tickets created ✓</p>
        <div className="space-y-1.5">
          <a
            href={state.jiraResult.epic_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-sm text-primary-light hover:underline"
          >
            <span className="w-2 h-2 rounded-full bg-purple-400 flex-shrink-0" />
            Epic: {state.jiraResult.epic_key}
            <ExternalLink className="w-3 h-3" />
          </a>
          {state.jiraResult.task_keys.map(key => (
            <div key={key} className="flex items-center gap-2 text-sm text-text-secondary">
              <span className="w-2 h-2 rounded bg-blue-400 flex-shrink-0" />
              Story: {key}
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-1">

        {state.messages.length === 0 && !state.isTyping && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center mb-4">
              <Bot className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-text-primary mb-2">
              Welcome to TeamSync AI
            </h3>
            <p className="text-text-secondary max-w-md">
              I'm Sam, your AI Product Analyst. Describe your feature idea and I'll help
              you create a comprehensive PRD — then email it and create JIRA tickets.
            </p>
            <div className="mt-6 flex gap-2 flex-wrap justify-center">
              {['Mobile expense tracking app', 'Team collaboration tool', 'AI writing assistant'].map(s => (
                <button
                  key={s}
                  onClick={() => setInput(`I want to build a ${s}`)}
                  className="px-4 py-2 bg-background-tertiary border border-white/10 rounded-lg text-sm text-text-secondary hover:text-text-primary hover:border-primary/50 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Committed messages */}
        {state.messages.map(msg => (
          <div key={msg.id} className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
              msg.role === 'user'
                ? 'bg-primary/20 text-primary-light'
                : 'bg-gradient-to-br from-primary to-primary-light text-white'
            }`}>
              {msg.role === 'user' ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
            </div>
            <div className={`max-w-[80%] rounded-2xl px-5 py-3 ${
              msg.role === 'user'
                ? 'bg-primary text-white'
                : 'bg-background-tertiary border border-white/10'
            }`}>
              {msg.role === 'assistant' ? (
                <div className="text-sm leading-relaxed prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm leading-relaxed">{msg.content}</p>
              )}
            </div>
          </div>
        ))}

        {/* JIRA result card (once created) */}
        {jiraCard}

        {/* Streaming message (live tokens) */}
        {streamingText && (
          <div className="flex gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div className="max-w-[80%] bg-background-tertiary border border-white/10 rounded-2xl px-5 py-3">
              <div className="text-sm leading-relaxed prose prose-invert prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingText}</ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {/* Typing / status indicator */}
        {state.isTyping && !streamingText && (
          <div className="flex gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div className="bg-background-tertiary border border-white/10 rounded-2xl px-5 py-3">
              {statusLabel ? (
                <p className="text-sm text-text-muted flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {statusLabel}
                </p>
              ) : (
                <div className="flex gap-1 py-1">
                  {[0, 150, 300].map(d => (
                    <span key={d} className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: `${d}ms` }} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Inline email form */}
        {state.interrupt?.form === 'email_form' && state.sessionId && (
          <div className="flex gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <InlineEmailForm
              interrupt={state.interrupt}
              sessionId={state.sessionId}
              isLoading={state.isTyping}
              onSubmit={handleEmailSubmit}
            />
          </div>
        )}

        {/* Inline JIRA form */}
        {state.interrupt?.form === 'jira_form' && state.sessionId && (
          <div className="flex gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <InlineJiraForm
              interrupt={state.interrupt}
              sessionId={state.sessionId}
              isLoading={state.isTyping}
              onSubmit={handleJiraSubmit}
            />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
            <span className="flex-1">{error}</span>
            <button onClick={() => setError(null)} className="hover:opacity-70">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input bar — disabled while a form is shown */}
      <div className={`flex gap-3 transition-opacity ${state.interrupt ? 'opacity-40 pointer-events-none' : ''}`}>
        <div className="flex-1">
          <Input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={state.interrupt ? 'Fill in the form above to continue…' : 'Describe your feature idea…'}
            disabled={state.isTyping || !!state.interrupt}
          />
        </div>
        <Button
          onClick={handleSend}
          disabled={!input.trim() || state.isTyping || !!state.interrupt}
          className="px-4"
        >
          {state.isTyping ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
        </Button>
      </div>
    </div>
  );
}
