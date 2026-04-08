// services/api.ts — FastAPI LangGraph backend client
// All chat calls are SSE streams. localStorage handles PRD/ticket persistence.
import type { SSEEvent, PRDDocument, JIRATicket, Message, ChatTab, UploadedFile } from '../types';

const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
let storageNamespace: string | null = null;

const BASE_HEADERS: HeadersInit = {
  'Content-Type': 'application/json',
};

// ── Debug logger ──────────────────────────────────────────────────────────

const DEBUG = import.meta.env.DEV || import.meta.env.VITE_DEBUG === 'true';
function dbg(...args: unknown[]) {
  if (DEBUG) console.debug('[TeamSync]', ...args);
}

// ── SSE stream reader ─────────────────────────────────────────────────────

async function* readSSE(response: Response): AsyncGenerator<SSEEvent> {
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    const msg = (err as any).detail || `HTTP ${response.status}`;
    console.error('[TeamSync] SSE request failed:', response.status, msg);
    throw new Error(msg);
  }
  dbg('SSE stream opened', response.url);
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      dbg('SSE stream closed');
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop()!;
    for (const chunk of chunks) {
      if (chunk.startsWith('data: ')) {
        const raw = chunk.slice(6);
        try {
          const event = JSON.parse(raw) as SSEEvent;
          if ((event as any).type === 'token') {
            dbg('SSE token: %d chars', ((event as any).content ?? '').length);
          } else {
            dbg('SSE event:', event);
          }
          yield event;
        } catch {
          console.warn('[TeamSync] SSE malformed line:', raw);
        }
      }
    }
  }
}

// ── API methods ───────────────────────────────────────────────────────────

class TeamSyncAPI {
  setStorageNamespace(namespace: string | null): void {
    storageNamespace = namespace;
  }

  private getStorageKey(key: string): string {
    return storageNamespace ? `${storageNamespace}:${key}` : key;
  }

  private async request(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = init.body ? BASE_HEADERS : undefined;
    return fetch(`${API_URL}${path}`, {
      credentials: 'include',
      ...init,
      headers: {
        ...(headers || {}),
        ...(init.headers || {}),
      },
    });
  }

  async signup(displayName: string, email: string, password: string) {
    const res = await this.request('/api/v1/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ display_name: displayName, email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as any).detail || 'Failed to create account');
    }
    return res.json();
  }

  async login(email: string, password: string) {
    const res = await this.request('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as any).detail || 'Failed to sign in');
    }
    return res.json();
  }

  async logout(): Promise<void> {
    await this.request('/api/v1/auth/logout', { method: 'POST' });
  }

  async getCurrentUser() {
    const res = await this.request('/api/v1/auth/me');
    if (!res.ok) throw new Error('Not authenticated');
    return res.json();
  }

  getGoogleLoginUrl(): string {
    return `${API_URL}/api/v1/auth/google/login`;
  }

  // Stream a chat message. Yields SSEEvents until turn_end.
  async *streamChat(message: string, sessionId: string | null): AsyncGenerator<SSEEvent> {
    const res = await this.request('/api/v1/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    yield* readSSE(res);
  }

  // Upload files for requirements context. Returns previews.
  async uploadFiles(sessionId: string, files: File[]): Promise<UploadedFile[]> {
    const form = new FormData();
    form.append('session_id', sessionId);
    files.forEach(f => form.append('files', f));
    const res = await fetch(`${API_URL}/api/v1/chat/upload`, {
      method: 'POST',
      credentials: 'include',
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as any).detail || `Upload failed: HTTP ${res.status}`);
    }
    return (await res.json()).documents as UploadedFile[];
  }

  // Download the generated PRD as a .md file (triggers browser download).
  downloadPRD(sessionId: string): void {
    window.open(`${API_URL}/api/v1/sessions/${sessionId}/download`, '_blank');
  }

  // Resume a suspended graph (after email/JIRA form). Yields SSEEvents.
  async *resumeSession(
    sessionId: string,
    data: Record<string, string>,
  ): AsyncGenerator<SSEEvent> {
    const res = await this.request(`/api/v1/sessions/${sessionId}/resume`, {
      method: 'POST',
      body: JSON.stringify({ data }),
    });
    yield* readSSE(res);
  }

  // Gmail OAuth
  async getGmailConnectUrl(sessionId: string): Promise<string> {
    const res = await this.request(
      `/api/v1/email/auth/connect?session_id=${encodeURIComponent(sessionId)}`,
    );
    if (!res.ok) throw new Error('Failed to get Gmail connect URL');
    return (await res.json()).url as string;
  }

  async getGmailAuthStatus(sessionId: string): Promise<{ connected: boolean; email: string | null; name: string | null }> {
    const res = await this.request(
      `/api/v1/email/auth/status?session_id=${encodeURIComponent(sessionId)}`,
    );
    if (!res.ok) throw new Error('Failed to get Gmail status');
    return res.json();
  }

  // Get JIRA OAuth connect URL — opens in a popup tab.
  async getJiraConnectUrl(sessionId: string): Promise<string> {
    const res = await this.request(
      `/api/v1/jira/auth/connect?session_id=${encodeURIComponent(sessionId)}`,
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
    const res = await this.request(
      `/api/v1/jira/auth/status?session_id=${encodeURIComponent(sessionId)}`,
    );
    if (!res.ok) throw new Error('Failed to get JIRA status');
    return res.json();
  }

  // User-level JIRA methods (no session_id — used by JIRA tab)
  async getUserJiraStatus(): Promise<{
    connected: boolean;
    user_name: string | null;
    cloud_name: string | null;
    user_email: string | null;
    auth_mode: 'oauth' | 'pat' | null;
    project_url: string | null;
  }> {
    const res = await this.request('/api/v1/jira/auth/me/status');
    if (!res.ok) throw new Error('Failed to get JIRA status');
    return res.json();
  }

  async getUserJiraConnectUrl(): Promise<string> {
    const res = await this.request('/api/v1/jira/auth/me/connect');
    if (!res.ok) throw new Error('Failed to get JIRA connect URL');
    return (await res.json()).url as string;
  }

  async disconnectJira(): Promise<void> {
    const res = await this.request('/api/v1/jira/auth/me/disconnect', { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to disconnect JIRA');
  }

  async createJiraTickets(payload: {
    prd_markdown: string;
    feature_name?: string;
    project_key?: string;
    assignee_email?: string;
  }): Promise<{ epic_key: string; epic_url: string; task_keys: string[]; cloud_url: string }> {
    const res = await this.request('/api/v1/jira/auth/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as any).detail || 'Failed to create JIRA tickets');
    }
    return res.json();
  }

  async getJiraBoards(projectKey?: string): Promise<{ boards: any[]; total: number }> {
    const qs = projectKey ? `?project_key=${encodeURIComponent(projectKey)}` : '';
    const res = await this.request(`/api/v1/jira/auth/boards${qs}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as any).detail || 'Failed to fetch boards');
    }
    return res.json();
  }

  async getJiraProjects(q?: string): Promise<{ projects: any[]; total: number }> {
    const qs = q ? `?q=${encodeURIComponent(q)}` : '';
    const res = await this.request(`/api/v1/jira/auth/projects${qs}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as any).detail || 'Failed to fetch projects');
    }
    return res.json();
  }

  async saveJiraPat(credentials: {
    base_url: string;
    username: string;
    api_token: string;
    project_key: string;
  }): Promise<void> {
    const res = await this.request('/api/v1/jira/auth/me/pat', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as any).detail || 'Failed to save JIRA credentials');
    }
  }

  // ── Chat tabs (multi-session) ─────────────────────────────────────────────

  getChatTabs(): ChatTab[] {
    const stored = localStorage.getItem(this.getStorageKey('chat_tabs'));
    if (stored) {
      try {
        const tabs: ChatTab[] = JSON.parse(stored);
        // Reset runtime-only state that must not persist across reloads
        return tabs.map(t => ({ ...t, isTyping: false, interrupt: null }));
      } catch { /* fall through to migration */ }
    }
    // Migrate: lift any existing single-session data into a tab
    const oldSession = localStorage.getItem(this.getStorageKey('current_session_id'));
    const oldMessages = localStorage.getItem(this.getStorageKey('chat_messages'));
    if (oldSession) {
      const msgs: Message[] = oldMessages ? JSON.parse(oldMessages) : [];
      const firstUser = msgs.find(m => m.role === 'user');
      return [{
        id: oldSession,
        label: firstUser ? firstUser.content.slice(0, 28) : 'New Chat',
        sessionId: oldSession,
        messages: msgs,
        currentMode: 'analyze',
        isTyping: false,
        currentPRD: null,
        emailStatus: 'idle',
        jiraApprovalStatus: 'pending',
        interrupt: null,
        jiraResult: null,
      }];
    }
    return [];
  }

  saveChatTabs(tabs: ChatTab[]): void {
    // Strip runtime-only fields before persisting
    const toPersist = tabs.map(({ isTyping: _it, interrupt: _int, ...rest }) => ({
      ...rest,
      isTyping: false,
      interrupt: null,
    }));
    localStorage.setItem(this.getStorageKey('chat_tabs'), JSON.stringify(toPersist));
  }

  getActiveTabId(): string | null {
    return localStorage.getItem(this.getStorageKey('active_tab_id'));
  }

  saveActiveTabId(tabId: string): void {
    localStorage.setItem(this.getStorageKey('active_tab_id'), tabId);
  }

  // ── localStorage helpers ──────────────────────────────────────────────────

  getPRDHistory(): PRDDocument[] {
    const h = localStorage.getItem(this.getStorageKey('prd_history'));
    return h ? JSON.parse(h) : [];
  }

  savePRD(prd: PRDDocument): void {
    const history = this.getPRDHistory();
    const idx = history.findIndex(p => p.id === prd.id);
    if (idx >= 0) history[idx] = prd;
    else history.unshift(prd);
    localStorage.setItem(this.getStorageKey('prd_history'), JSON.stringify(history.slice(0, 50)));
  }

  getPRDById(id: string): PRDDocument | null {
    return this.getPRDHistory().find(p => p.id === id) || null;
  }

  getJIRATickets(): JIRATicket[] {
    const t = localStorage.getItem(this.getStorageKey('jira_tickets'));
    return t ? JSON.parse(t) : [];
  }

  saveJIRATickets(tickets: JIRATicket[]): void {
    localStorage.setItem(this.getStorageKey('jira_tickets'), JSON.stringify(tickets));
  }

  setSessionId(sessionId: string): void {
    localStorage.setItem(this.getStorageKey('current_session_id'), sessionId);
  }

  getSessionId(): string {
    let id = localStorage.getItem(this.getStorageKey('current_session_id'));
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(this.getStorageKey('current_session_id'), id);
    }
    return id;
  }

  clearSession(): void {
    localStorage.removeItem(this.getStorageKey('current_session_id'));
    localStorage.removeItem(this.getStorageKey('chat_messages'));
  }

  getMessages(): Message[] {
    const m = localStorage.getItem(this.getStorageKey('chat_messages'));
    return m ? JSON.parse(m) : [];
  }

  saveMessages(messages: Message[]): void {
    localStorage.setItem(this.getStorageKey('chat_messages'), JSON.stringify(messages));
  }

  replacePRDHistory(history: PRDDocument[]): void {
    localStorage.setItem(this.getStorageKey('prd_history'), JSON.stringify(history));
  }

  clearPRDHistory(): void {
    localStorage.removeItem(this.getStorageKey('prd_history'));
  }
}

export const api = new TeamSyncAPI();
