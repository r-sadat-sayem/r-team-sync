// components/chat/ChatInterface.tsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useApp } from '../../context/AppContext';
import { api } from '../../services/api';
import { Button } from '../ui/Button';
import { InlineEmailForm } from './InlineEmailForm';
import { InlineJiraForm, type JiraFormSubmitData } from './InlineJiraForm';
import { InlineActionMenu } from './InlineActionMenu';
import { InlinePRDOutlineForm } from './InlinePRDOutlineForm';
import { PRDArtifactCard } from './PRDArtifactCard';
import { Send, Bot, User, Loader2, ExternalLink, RefreshCw, Paperclip, X, FileText, Image as ImageIcon, Copy, Check, List, ListOrdered, Bold, Italic, CornerDownLeft } from 'lucide-react';
import type { Message, PRDDocument, SSEEvent, UploadedFile } from '../../types';

// ── Helpers ───────────────────────────────────────────────────────────────

function normalizeAssistantContent(content: string): string {
  return content
    .replace(/\r\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

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

function renderMarkdown(content: string) {
  return (
    <div className="markdown-content chat-markdown text-sm leading-7 text-text-primary max-w-none min-w-0 overflow-hidden">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node: _node, ...props }) => (
            <a
              {...props}
              target="_blank"
              rel="noreferrer"
              className="text-primary-light underline underline-offset-2 break-all"
            />
          ),
          p: ({ node: _node, ...props }) => <p {...props} className="mb-3 last:mb-0 break-words" />,
          ul: ({ node: _node, ...props }) => <ul {...props} className="list-disc pl-5 space-y-2 mb-3" />,
          ol: ({ node: _node, ...props }) => <ol {...props} className="list-decimal pl-5 space-y-2 mb-3" />,
          li: ({ node: _node, ...props }) => <li {...props} className="break-words" />,
          blockquote: ({ node: _node, ...props }) => (
            <blockquote {...props} className="border-l-4 border-primary/70 pl-4 italic text-text-secondary my-4" />
          ),
          code: ({ node: _node, className, children, ...props }) => {
            const isBlock = Boolean(className?.includes('language-'));
            if (isBlock) {
              return (
                <code {...props} className={`${className || ''} font-mono text-[13px] leading-6`}>
                  {children}
                </code>
              );
            }
            return (
              <code {...props} className="rounded-md bg-black/30 px-1.5 py-0.5 font-mono text-[13px] text-primary-light break-words">
                {children}
              </code>
            );
          },
          pre: ({ node: _node, ...props }) => (
            <pre {...props} className="my-4 overflow-x-auto rounded-xl border border-white/10 bg-black/35 p-4 text-[13px] leading-6" />
          ),
          table: ({ node: _node, ...props }) => (
            <div className="my-4 overflow-x-auto">
              <table {...props} className="min-w-full border-collapse text-left text-sm" />
            </div>
          ),
          thead: ({ node: _node, ...props }) => <thead {...props} className="bg-white/5" />,
          th: ({ node: _node, ...props }) => (
            <th {...props} className="border border-white/10 px-3 py-2 font-semibold text-text-primary" />
          ),
          td: ({ node: _node, ...props }) => (
            <td {...props} className="border border-white/10 px-3 py-2 align-top text-text-secondary" />
          ),
          h1: ({ node: _node, ...props }) => <h1 {...props} className="mt-1 mb-4 text-2xl font-bold text-text-primary" />,
          h2: ({ node: _node, ...props }) => <h2 {...props} className="mt-6 mb-3 text-xl font-semibold text-text-primary" />,
          h3: ({ node: _node, ...props }) => <h3 {...props} className="mt-5 mb-2 text-lg font-semibold text-text-primary" />,
          hr: ({ node: _node, ...props }) => <hr {...props} className="my-5 border-white/10" />,
        }}
      >
        {normalizeAssistantContent(content)}
      </ReactMarkdown>
    </div>
  );
}

// ── CopyButton ────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <button
      onClick={copy}
      aria-label={copied ? 'Copied' : 'Copy message'}
      className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-lg hover:bg-white/10 text-text-muted hover:text-text-secondary flex-shrink-0 self-start mt-1"
    >
      {copied
        ? <Check className="w-3.5 h-3.5 text-green-400" />
        : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

// ── Component ─────────────────────────────────────────────────────────────

const ALLOWED_TYPES = new Set([
  'application/pdf', 'text/plain', 'text/markdown',
  'application/json', 'text/xml', 'application/xml',
  'image/png', 'image/jpeg', 'image/webp', 'image/gif',
]);
const MAX_FILE_BYTES = 10 * 1024 * 1024;

function isImageType(contentType: string) {
  return contentType.startsWith('image/');
}

export function ChatInterface() {
  const { state, dispatch, activeTab } = useApp();
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  // File upload state
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const [stagePreviews, setStagePreviews] = useState<string[]>([]); // object URLs for images
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Streaming state — refs avoid stale closure issues inside the generator loop
  const [streamingText, setStreamingText] = useState('');
  const [statusLabel, setStatusLabel] = useState('');
  const streamRef  = useRef('');
  const prdAccRef     = useRef('');    // accumulates PRD tokens specifically
  const inPRDRef      = useRef(false); // true while generate_prd is streaming
  const tcAccRef      = useRef('');    // accumulates test case tokens
  const inTCRef       = useRef(false); // true while generate_test_cases is streaming
  const inOutlineRef  = useRef(false); // true while generate_prd_outline is streaming

  // Stable ref so callbacks always see the current activeTab without staleness
  const activeTabRef = useRef(activeTab);
  activeTabRef.current = activeTab;

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef   = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeTab.messages, streamingText, activeTab.interrupt]);

  // Auto-resize textarea whenever input changes
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [input]);

  // ── File staging helpers ──────────────────────────────────────────────────
  const stageFiles = useCallback((incoming: FileList | File[]) => {
    const valid: File[] = [];
    const rejected: string[] = [];
    Array.from(incoming).forEach(f => {
      if (!ALLOWED_TYPES.has(f.type)) {
        rejected.push(`${f.name}: unsupported type`);
      } else if (f.size > MAX_FILE_BYTES) {
        rejected.push(`${f.name}: exceeds 10 MB`);
      } else {
        valid.push(f);
      }
    });
    if (rejected.length) setError(rejected.join(', '));
    if (!valid.length) return;

    setStagedFiles(prev => [...prev, ...valid]);
    setStagePreviews(prev => [
      ...prev,
      ...valid.map(f => isImageType(f.type) ? URL.createObjectURL(f) : ''),
    ]);
  }, []);

  const removeStagedFile = useCallback((index: number) => {
    setStagedFiles(prev => prev.filter((_, i) => i !== index));
    setStagePreviews(prev => {
      const url = prev[index];
      if (url) URL.revokeObjectURL(url);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  // Revoke object URLs on unmount
  useEffect(() => {
    return () => { stagePreviews.forEach(u => { if (u) URL.revokeObjectURL(u); }); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Drag-and-drop ────────────────────────────────────────────────────────
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node)) setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files.length) stageFiles(e.dataTransfer.files);
  }, [stageFiles]);

  // ── Flush streaming buffer → committed message ──────────────────────────
  const flushStream = useCallback(() => {
    const text = streamRef.current.trim();
    if (text) {
      dispatch({ type: 'ADD_MESSAGE', payload: buildMessage(normalizeAssistantContent(text), 'assistant') });
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
        if (inTCRef.current)  tcAccRef.current  += ev.content;
        break;
      }
      case 'jira_progress': {
        setStatusLabel(ev.message);
        break;
      }
      case 'status': {
        setStatusLabel(ev.message);
        if (ev.message.toLowerCase().includes('planning prd outline')) {
          inOutlineRef.current = true;
          streamRef.current = '';
          setStreamingText('');
        }
        if (ev.message.toLowerCase().includes('writing prd')) {
          inPRDRef.current = true;
          prdAccRef.current = '';
          streamRef.current = '';
          setStreamingText('');
        }
        if (ev.message.toLowerCase().includes('generating test cases')) {
          inTCRef.current  = true;
          tcAccRef.current = '';
          streamRef.current = '';
          setStreamingText('');
        }
        break;
      }
      case 'test_cases_complete': {
        inTCRef.current = false;
        const tcMarkdown = tcAccRef.current;
        const tc: PRDDocument = {
          id:            `tc-${Date.now()}`,
          title:         'Test Cases',
          content:       tcMarkdown,
          qualityScore:  0,
          grade:         'A' as const,
          createdAt:     new Date(),
          sections:      [],
          testCaseCount: ev.tc_count,
          fileName:      ev.file_name,
          docType:       'test_cases',
          sessionId:     activeTabRef.current.sessionId,
        };
        dispatch({ type: 'ADD_PRD_TO_HISTORY', payload: tc });
        streamRef.current = '';
        tcAccRef.current  = '';
        setStreamingText('');
        dispatch({
          type: 'ADD_MESSAGE',
          payload: {
            id:        `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            role:      'artifact',
            content:   tc.title,
            timestamp: new Date(),
            metadata:  { prdId: tc.id, docType: 'test_cases' },
          },
        });
        break;
      }
      case 'prd_deprecated': {
        const currentPRDId = activeTabRef.current?.currentPRD?.id;
        if (currentPRDId) {
          dispatch({ type: 'MARK_PRD_DEPRECATED', payload: currentPRDId });
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
          sessionId: activeTabRef.current.sessionId,
          version: ev.prd_version,
        };
        dispatch({ type: 'SET_CURRENT_PRD', payload: prd });
        dispatch({ type: 'ADD_PRD_TO_HISTORY', payload: prd });
        dispatch({ type: 'SET_MODE', payload: 'complete' });
        // Clear stream buffer — show compact artifact card instead of full markdown
        streamRef.current = '';
        prdAccRef.current = '';
        setStreamingText('');
        dispatch({
          type: 'ADD_MESSAGE',
          payload: {
            id:        `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`,
            role:      'artifact',
            content:   prd.title,
            timestamp: new Date(),
            metadata:  { prdId: prd.id },
          },
        });
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
        // Outline tokens must not appear as a committed message — the outline
        // is already in the interrupt payload and will render in InlinePRDOutlineForm.
        if (inOutlineRef.current) {
          inOutlineRef.current = false;
          streamRef.current = '';
          setStreamingText('');
        }
        flushStream();
        const { type: _, ...payload } = ev as any;
        dispatch({ type: 'SET_INTERRUPT', payload });
        break;
      }
      case 'turn_end': {
        flushStream();
        if (ev.session_id) {
          dispatch({ type: 'SET_SESSION', payload: ev.session_id });
          // saveChatTabs is called inside the reducer; no separate api.setSessionId needed
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
  const runStream = useCallback(async (generator: AsyncGenerator<SSEEvent>) => {
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
    if ((!input.trim() && stagedFiles.length === 0) || activeTab.isTyping || isUploading) return;
    const filesToUpload = [...stagedFiles];
    // If the user attached files but wrote no text, use a sensible default
    const text = input.trim() || (filesToUpload.length
      ? `Please use the attached ${filesToUpload.length === 1 ? 'file' : 'files'} as context for our conversation.`
      : '');
    const previewsSnapshot = [...stagePreviews];

    setInput('');
    setStagedFiles([]);
    setStagePreviews([]);

    // Build the user message — include attachment stubs for immediate display
    let attachments: UploadedFile[] | undefined;
    if (filesToUpload.length) {
      attachments = filesToUpload.map(f => ({
        filename: f.name,
        content_type: f.type,
        preview: isImageType(f.type) ? previewsSnapshot[filesToUpload.indexOf(f)] : f.name,
      }));
    }
    dispatch({
      type: 'ADD_MESSAGE',
      payload: { ...buildMessage(text, 'user'), attachments },
    });

    // Upload files first (they'll be injected into LangGraph state before the chat turn)
    if (filesToUpload.length) {
      setIsUploading(true);
      try {
        await api.uploadFiles(activeTab.sessionId, filesToUpload);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed');
        setIsUploading(false);
        return;
      } finally {
        setIsUploading(false);
        // Revoke stale object URLs
        previewsSnapshot.forEach(u => { if (u) URL.revokeObjectURL(u); });
      }
    }

    await runStream(api.streamChat(text, activeTab.sessionId));
  };

  // ── Resume: PRD outline form ──────────────────────────────────────────
  const handlePRDOutlineSubmit = async (data: { decision: string; feedback?: string }) => {
    dispatch({ type: 'SET_INTERRUPT', payload: null });
    if (!activeTab.sessionId) return;
    await runStream(api.resumeSession(activeTab.sessionId, data));
  };

  // ── Resume: email form ────────────────────────────────────────────────
  const handleEmailSubmit = async (data: { name: string; email: string }) => {
    dispatch({ type: 'SET_INTERRUPT', payload: null });
    if (!activeTab.sessionId) return;
    await runStream(api.resumeSession(activeTab.sessionId, data));
  };

  // ── Resume: post-PRD action menu ─────────────────────────────────────
  const handleActionMenuSubmit = async (data: { action: string }) => {
    dispatch({ type: 'SET_INTERRUPT', payload: null });
    if (!activeTab.sessionId) return;
    await runStream(api.resumeSession(activeTab.sessionId, data));
  };

  // ── Resume: JIRA form ─────────────────────────────────────────────────
  const handleJiraSubmit = async (data: JiraFormSubmitData) => {
    dispatch({ type: 'SET_INTERRUPT', payload: null });
    if (!activeTab.sessionId) return;
    await runStream(api.resumeSession(activeTab.sessionId, data));
  };

  // ── Formatting toolbar ───────────────────────────────────────────────────
  const insertFormat = useCallback((type: 'bullet' | 'numbered' | 'bold' | 'italic') => {
    const el = textareaRef.current;
    if (!el) return;
    const start = el.selectionStart;
    const end   = el.selectionEnd;
    const sel   = input.slice(start, end);

    let insert = '';
    let cursorOffset = 0;

    switch (type) {
      case 'bullet':
        insert = sel
          ? sel.split('\n').map(l => `- ${l}`).join('\n')
          : '- ';
        cursorOffset = sel ? insert.length : 2;
        break;
      case 'numbered':
        insert = sel
          ? sel.split('\n').map((l, i) => `${i + 1}. ${l}`).join('\n')
          : '1. ';
        cursorOffset = sel ? insert.length : 3;
        break;
      case 'bold':
        insert = sel ? `**${sel}**` : '**bold**';
        cursorOffset = sel ? insert.length : 2;
        break;
      case 'italic':
        insert = sel ? `_${sel}_` : '_italic_';
        cursorOffset = sel ? insert.length : 1;
        break;
    }

    const next = input.slice(0, start) + insert + input.slice(end);
    setInput(next);
    requestAnimationFrame(() => {
      if (el) {
        const pos = start + cursorOffset;
        el.setSelectionRange(pos, pos);
        el.focus();
      }
    });
  }, [input]);

  // ── Keyboard handler with auto-list continuation ──────────────────────────
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== 'Enter' || e.shiftKey) return;

    const el = textareaRef.current;
    if (!el) { e.preventDefault(); handleSend(); return; }

    const cursor    = el.selectionStart;
    const before    = input.slice(0, cursor);
    const lastLine  = before.split('\n').pop() ?? '';

    // Bullet list continuation: "- text" or "* text"
    const bulletMatch = lastLine.match(/^(\s*[-*]) (.+)$/);
    if (bulletMatch) {
      e.preventDefault();
      const marker  = `${bulletMatch[1]} `;
      const newText = input.slice(0, cursor) + `\n${marker}` + input.slice(cursor);
      setInput(newText);
      requestAnimationFrame(() => {
        const pos = cursor + 1 + marker.length;
        el.setSelectionRange(pos, pos);
      });
      return;
    }

    // Empty bullet ("- " or "* " with nothing after) → strip the marker
    const emptyBullet = lastLine.match(/^(\s*[-*])\s*$/);
    if (emptyBullet) {
      e.preventDefault();
      const lineStart = before.lastIndexOf('\n') + 1;
      const newText   = input.slice(0, lineStart) + input.slice(cursor);
      setInput(newText);
      requestAnimationFrame(() => el.setSelectionRange(lineStart, lineStart));
      return;
    }

    // Numbered list continuation: "1. text"
    const numMatch = lastLine.match(/^(\s*)(\d+)\. (.+)$/);
    if (numMatch) {
      e.preventDefault();
      const indent  = numMatch[1];
      const marker  = `${indent}${parseInt(numMatch[2]) + 1}. `;
      const newText = input.slice(0, cursor) + `\n${marker}` + input.slice(cursor);
      setInput(newText);
      requestAnimationFrame(() => {
        const pos = cursor + 1 + marker.length;
        el.setSelectionRange(pos, pos);
      });
      return;
    }

    // Empty numbered item ("1. " with nothing after) → strip the marker
    const emptyNum = lastLine.match(/^(\s*)\d+\.\s*$/);
    if (emptyNum) {
      e.preventDefault();
      const lineStart = before.lastIndexOf('\n') + 1;
      const newText   = input.slice(0, lineStart) + input.slice(cursor);
      setInput(newText);
      requestAnimationFrame(() => el.setSelectionRange(lineStart, lineStart));
      return;
    }

    // Default: send
    e.preventDefault();
    handleSend();
  };

  // ── JIRA result card ──────────────────────────────────────────────────
  const jiraCard = activeTab.jiraResult && (
    <div className="flex gap-4" role="status" aria-label="JIRA tickets created">
      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0">
        <Bot className="w-5 h-5 text-white" aria-hidden="true" />
      </div>
      <div className="max-w-[85%] sm:max-w-[80%] bg-background-tertiary border border-white/10 rounded-2xl px-5 py-4 space-y-3">
        <p className="text-sm font-medium text-text-primary">JIRA tickets created ✓</p>
        <div className="space-y-1.5">
          <a
            href={activeTab.jiraResult.epic_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-sm text-primary-light hover:underline"
          >
            <span className="w-2 h-2 rounded-full bg-purple-400 flex-shrink-0" aria-hidden="true" />
            Epic: {activeTab.jiraResult.epic_key}
            <ExternalLink className="w-3 h-3" aria-hidden="true" />
          </a>
          {activeTab.jiraResult.task_keys.map(key => (
            <div key={key} className="flex items-center gap-2 text-sm text-text-secondary">
              <span className="w-2 h-2 rounded bg-blue-400 flex-shrink-0" aria-hidden="true" />
              Story: {key}
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-full" role="region" aria-label="Chat conversation">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.txt,.md,.json,.xml,image/png,image/jpeg,image/webp,image/gif"
        className="hidden"
        onChange={e => { if (e.target.files?.length) stageFiles(e.target.files); e.target.value = ''; }}
        aria-hidden="true"
      />

      {/* Messages — also serves as drop zone */}
      <div
        className={`flex-1 overflow-y-auto space-y-4 mb-4 pr-1 relative transition-colors ${isDragging ? 'outline-dashed outline-2 outline-primary/50 rounded-xl bg-primary/5' : ''}`}
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Messages"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isDragging && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
            <div className="flex flex-col items-center gap-2 text-primary-light">
              <Paperclip className="w-8 h-8" />
              <p className="text-sm font-medium">Drop files to attach</p>
            </div>
          </div>
        )}
        {activeTab.messages.length === 0 && !activeTab.isTyping && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div
              className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center mb-4"
              aria-hidden="true"
            >
              <Bot className="w-8 h-8 text-white" />
            </div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">
              Welcome to TeamSync AI
            </h2>
            <p className="text-text-secondary max-w-md">
              I'm Sam, your AI Product Analyst. Describe your feature idea and I'll help
              you create a comprehensive PRD — then email it and create JIRA tickets.
            </p>
            <div className="mt-6 flex gap-2 flex-wrap justify-center px-4" role="list" aria-label="Example prompts">
              {['Mobile expense tracking app', 'Team collaboration tool', 'AI writing assistant'].map(s => (
                <button
                  key={s}
                  role="listitem"
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
        {activeTab.messages.map(msg => (
          <div
            key={msg.id}
            className={`flex gap-4 min-w-0 message-enter group ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
            <div
              aria-hidden="true"
              className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                msg.role === 'user'
                  ? 'bg-primary/20 text-primary-light'
                  : 'bg-gradient-to-br from-primary to-primary-light text-white'
              }`}
            >
              {msg.role === 'user' ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
            </div>
            <div
              className={`max-w-[85%] sm:max-w-[80%] min-w-0 rounded-2xl ${
                msg.role === 'artifact'
                  ? ''
                  : msg.role === 'user'
                    ? 'bg-primary text-white px-5 py-3'
                    : 'bg-background-tertiary border border-white/10 px-5 py-3'
              }`}
              aria-label={msg.role === 'user' ? 'You' : msg.role === 'artifact' ? 'PRD artifact' : 'Sam'}
            >
              {msg.role === 'artifact' ? (
                (() => {
                  const prd = state.prdHistory.find(p => p.id === msg.metadata?.prdId);
                  return prd
                    ? <PRDArtifactCard prd={prd} />
                    : <p className="text-sm text-text-muted italic px-5 py-3 bg-background-tertiary border border-white/10 rounded-2xl">PRD artifact unavailable</p>;
                })()
              ) : msg.role === 'assistant' ? (
                renderMarkdown(msg.content)
              ) : (
                <>
                  {msg.attachments && msg.attachments.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-2">
                      {msg.attachments.map((att, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-1.5 bg-white/10 rounded-lg px-2 py-1 text-xs text-white/80 max-w-[160px]"
                        >
                          {isImageType(att.content_type)
                            ? <ImageIcon className="w-3.5 h-3.5 flex-shrink-0" />
                            : <FileText className="w-3.5 h-3.5 flex-shrink-0" />}
                          <span className="truncate">{att.filename}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
                </>
              )}
            </div>
            {msg.role === 'assistant' && <CopyButton text={msg.content} />}
          </div>
        ))}

        {/* JIRA result card */}
        {jiraCard}

        {/* Streaming message (live tokens) */}
        {streamingText && (
          <div className="flex gap-4 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0" aria-hidden="true">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div className="max-w-[80%] min-w-0 bg-background-tertiary border border-white/10 rounded-2xl px-5 py-3">
              {inPRDRef.current ? (
                <p className="text-sm text-text-muted flex items-center gap-2" aria-live="polite">
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  {statusLabel || 'Generating PRD document…'}
                </p>
              ) : (
                renderMarkdown(streamingText)
              )}
            </div>
          </div>
        )}

        {/* Typing / status indicator */}
        {activeTab.isTyping && !streamingText && (
          <div className="flex gap-4" role="status" aria-label={statusLabel || 'Sam is thinking'}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0" aria-hidden="true">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div className="bg-background-tertiary border border-white/10 rounded-2xl px-5 py-3">
              {statusLabel ? (
                <p className="text-sm text-text-muted flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  {statusLabel}
                </p>
              ) : (
                <div className="flex gap-1 py-1" aria-hidden="true">
                  {[0, 150, 300].map(d => (
                    <span key={d} className="w-2 h-2 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: `${d}ms` }} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Inline email form */}
        {activeTab.interrupt?.form === 'email_form' && activeTab.sessionId && (
          <div className="flex gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0" aria-hidden="true">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <InlineEmailForm
              interrupt={activeTab.interrupt}
              sessionId={activeTab.sessionId}
              isLoading={activeTab.isTyping}
              onSubmit={handleEmailSubmit}
            />
          </div>
        )}

        {/* Inline JIRA form */}
        {activeTab.interrupt?.form === 'jira_form' && activeTab.sessionId && (
          <div className="flex gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0" aria-hidden="true">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <InlineJiraForm
              interrupt={activeTab.interrupt}
              sessionId={activeTab.sessionId}
              isLoading={activeTab.isTyping}
              onSubmit={handleJiraSubmit}
            />
          </div>
        )}

        {/* PRD outline approval form */}
        {activeTab.interrupt?.form === 'prd_outline_form' && activeTab.sessionId && (
          <div className="flex gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0" aria-hidden="true">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <InlinePRDOutlineForm
              interrupt={activeTab.interrupt}
              isLoading={activeTab.isTyping}
              onSubmit={handlePRDOutlineSubmit}
            />
          </div>
        )}

        {/* Post-PRD action menu */}
        {activeTab.interrupt?.form === 'post_prd_actions' && activeTab.sessionId && (
          <div className="flex gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center flex-shrink-0" aria-hidden="true">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <InlineActionMenu
              interrupt={activeTab.interrupt}
              isLoading={activeTab.isTyping}
              onSubmit={handleActionMenuSubmit}
            />
          </div>
        )}

        {/* Error */}
        {error && (
          <div
            role="alert"
            className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm"
          >
            <span className="flex-1">{error}</span>
            <button
              onClick={() => setError(null)}
              aria-label="Dismiss error"
              className="hover:opacity-70"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Post-workflow continuation hint */}
      {activeTab.currentMode === 'complete' && !activeTab.interrupt && !activeTab.isTyping && (
        <p className="text-xs text-text-muted mb-2 text-center" aria-live="polite">
          PRD complete — ask a follow-up question or request refinements
        </p>
      )}

      {/* Staged file chips */}
      {stagedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2 px-1" aria-label="Files to attach">
          {stagedFiles.map((file, i) => (
            <div
              key={i}
              className="flex items-center gap-1.5 bg-background-tertiary border border-white/10 rounded-lg pl-2 pr-1 py-1 text-xs text-text-secondary max-w-[180px]"
            >
              {isImageType(file.type) ? (
                stagePreviews[i]
                  ? <img src={stagePreviews[i]} alt="" className="w-5 h-5 rounded object-cover flex-shrink-0" />
                  : <ImageIcon className="w-3.5 h-3.5 flex-shrink-0 text-blue-400" />
              ) : (
                <FileText className="w-3.5 h-3.5 flex-shrink-0 text-amber-400" />
              )}
              <span className="truncate flex-1">{file.name}</span>
              <button
                onClick={() => removeStagedFile(i)}
                className="ml-1 p-0.5 hover:text-text-primary rounded"
                aria-label={`Remove ${file.name}`}
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div
        className={`chat-input-bar flex flex-col gap-1.5 transition-opacity ${activeTab.interrupt ? 'opacity-40 pointer-events-none' : ''}`}
        role="group"
        aria-label="Message input"
      >
        {/* Formatting toolbar */}
        <div className="flex items-center gap-0.5 px-1">
          <button
            type="button"
            onClick={() => insertFormat('bullet')}
            disabled={activeTab.isTyping || !!activeTab.interrupt}
            title="Bullet list (- item)"
            aria-label="Insert bullet list"
            className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/8 disabled:opacity-30 transition-colors"
          >
            <List className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => insertFormat('numbered')}
            disabled={activeTab.isTyping || !!activeTab.interrupt}
            title="Numbered list (1. item)"
            aria-label="Insert numbered list"
            className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/8 disabled:opacity-30 transition-colors"
          >
            <ListOrdered className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => insertFormat('bold')}
            disabled={activeTab.isTyping || !!activeTab.interrupt}
            title="Bold (**text**)"
            aria-label="Bold"
            className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/8 disabled:opacity-30 transition-colors"
          >
            <Bold className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => insertFormat('italic')}
            disabled={activeTab.isTyping || !!activeTab.interrupt}
            title="Italic (_text_)"
            aria-label="Italic"
            className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/8 disabled:opacity-30 transition-colors"
          >
            <Italic className="w-3.5 h-3.5" />
          </button>

          <span className="ml-auto flex items-center gap-1 text-[10px] text-text-muted select-none">
            <CornerDownLeft className="w-3 h-3" />
            <span>Send</span>
            <span className="opacity-50 mx-1">·</span>
            <kbd className="font-mono">Shift</kbd><span>+</span><CornerDownLeft className="w-3 h-3" />
            <span>New line</span>
          </span>
        </div>

        {/* Textarea + action buttons row */}
        <div className="flex gap-2 items-end">
          {/* Paperclip — attach files */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={activeTab.isTyping || !!activeTab.interrupt || isUploading}
            aria-label="Attach files"
            className="flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-xl border border-white/10 bg-background-tertiary text-text-muted hover:text-text-primary hover:border-primary/40 disabled:opacity-40 disabled:cursor-not-allowed transition-colors self-end mb-0"
          >
            {isUploading
              ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              : <Paperclip className="w-4 h-4" aria-hidden="true" />}
          </button>

          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={activeTab.interrupt ? 'Fill in the form above to continue…' : 'Describe your feature idea…'}
            disabled={activeTab.isTyping || !!activeTab.interrupt || isUploading}
            aria-label="Message"
            aria-disabled={activeTab.isTyping || !!activeTab.interrupt || isUploading}
            rows={1}
            className="flex-1 resize-none px-4 py-2.5 bg-background-tertiary border border-white/10 rounded-xl text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all duration-200 min-h-[42px] max-h-[200px] overflow-y-auto leading-relaxed disabled:opacity-50"
          />

          <Button
            onClick={handleSend}
            disabled={(!input.trim() && stagedFiles.length === 0) || activeTab.isTyping || !!activeTab.interrupt || isUploading}
            aria-label={activeTab.isTyping || isUploading ? 'Sending…' : 'Send message'}
            className="px-4 self-end"
          >
            {activeTab.isTyping || isUploading
              ? <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
              : <Send className="w-5 h-5" aria-hidden="true" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
