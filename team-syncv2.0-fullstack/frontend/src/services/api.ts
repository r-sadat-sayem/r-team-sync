// services/api.ts — FastAPI LangGraph backend client
// All chat calls are SSE streams. localStorage handles PRD/ticket persistence.
import type { SSEEvent, PRDDocument, JIRATicket, Message } from '../types';

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_KEY = import.meta.env.VITE_API_KEY || 'dev-change-me';

const BASE_HEADERS = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY,
};

// ── SSE stream reader ─────────────────────────────────────────────────────

async function* readSSE(response: Response): AsyncGenerator<SSEEvent> {
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error((err as any).detail || `HTTP ${response.status}`);
  }
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop()!;
    for (const chunk of chunks) {
      if (chunk.startsWith('data: ')) {
        try {
          yield JSON.parse(chunk.slice(6)) as SSEEvent;
        } catch {
          // skip malformed line
        }
      }
    }
  }
}

// ── API methods ───────────────────────────────────────────────────────────

class TeamSyncAPI {

  // Stream a chat message. Yields SSEEvents until turn_end.
  async *streamChat(message: string, sessionId: string | null): AsyncGenerator<SSEEvent> {
    const res = await fetch(`${API_URL}/api/v1/chat`, {
      method: 'POST',
      headers: BASE_HEADERS,
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    yield* readSSE(res);
  }

  // Resume a suspended graph (after email/JIRA form). Yields SSEEvents.
  async *resumeSession(
    sessionId: string,
    data: Record<string, string>,
  ): AsyncGenerator<SSEEvent> {
    const res = await fetch(`${API_URL}/api/v1/sessions/${sessionId}/resume`, {
      method: 'POST',
      headers: BASE_HEADERS,
      body: JSON.stringify({ data }),
    });
    yield* readSSE(res);
  }

  // Gmail OAuth
  async getGmailConnectUrl(sessionId: string): Promise<string> {
    const res = await fetch(
      `${API_URL}/api/v1/email/auth/connect?session_id=${encodeURIComponent(sessionId)}`,
      { headers: BASE_HEADERS },
    );
    if (!res.ok) throw new Error('Failed to get Gmail connect URL');
    return (await res.json()).url as string;
  }

  async getGmailAuthStatus(sessionId: string): Promise<{ connected: boolean; email: string | null; name: string | null }> {
    const res = await fetch(
      `${API_URL}/api/v1/email/auth/status?session_id=${encodeURIComponent(sessionId)}`,
      { headers: BASE_HEADERS },
    );
    if (!res.ok) throw new Error('Failed to get Gmail status');
    return res.json();
  }

  // Get JIRA OAuth connect URL — opens in a popup tab.
  async getJiraConnectUrl(sessionId: string): Promise<string> {
    const res = await fetch(
      `${API_URL}/api/v1/jira/auth/connect?session_id=${encodeURIComponent(sessionId)}`,
      { headers: BASE_HEADERS },
    );
    if (!res.ok) throw new Error('Failed to get JIRA connect URL');
    const data = await res.json();
    return data.url as string;
  }

  // Poll JIRA connection status.
  async getJiraAuthStatus(sessionId: string): Promise<{
    connected: boolean;
    user_name: string | null;
    cloud_name: string | null;
  }> {
    const res = await fetch(
      `${API_URL}/api/v1/jira/auth/status?session_id=${encodeURIComponent(sessionId)}`,
      { headers: BASE_HEADERS },
    );
    if (!res.ok) throw new Error('Failed to get JIRA status');
    return res.json();
  }

  // ── localStorage helpers (unchanged from original) ──────────────────────

  getPRDHistory(): PRDDocument[] {
    const h = localStorage.getItem('prd_history');
    return h ? JSON.parse(h) : [];
  }

  savePRD(prd: PRDDocument): void {
    const history = this.getPRDHistory();
    const idx = history.findIndex(p => p.id === prd.id);
    if (idx >= 0) history[idx] = prd;
    else history.unshift(prd);
    localStorage.setItem('prd_history', JSON.stringify(history.slice(0, 50)));
  }

  getPRDById(id: string): PRDDocument | null {
    return this.getPRDHistory().find(p => p.id === id) || null;
  }

  getJIRATickets(): JIRATicket[] {
    const t = localStorage.getItem('jira_tickets');
    return t ? JSON.parse(t) : [];
  }

  saveJIRATickets(tickets: JIRATicket[]): void {
    localStorage.setItem('jira_tickets', JSON.stringify(tickets));
  }

  getSessionId(): string {
    let id = localStorage.getItem('current_session_id');
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem('current_session_id', id);
    }
    return id;
  }

  clearSession(): void {
    localStorage.removeItem('current_session_id');
    localStorage.removeItem('chat_messages');
  }

  getMessages(): Message[] {
    const m = localStorage.getItem('chat_messages');
    return m ? JSON.parse(m) : [];
  }

  saveMessages(messages: Message[]): void {
    localStorage.setItem('chat_messages', JSON.stringify(messages));
  }
}

export const api = new TeamSyncAPI();
