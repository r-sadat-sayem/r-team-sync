// types/index.ts

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  metadata?: {
    action?: 'generate' | 'done' | 'continue';
    qualityScore?: number;
    grade?: string;
  };
}

export interface PRDDocument {
  id: string;
  title: string;
  content: string;
  qualityScore: number;
  grade: 'A' | 'B' | 'C' | 'D' | 'F';
  createdAt: Date;
  sections: PRDSection[];
  testCaseCount: number;
  fileName?: string;
  sessionId?: string;   // LangGraph thread_id — lets History link back to the session
}

export interface PRDSection {
  id: string;
  title: string;
  level: number;
  content: string;
}

export interface JIRATicket {
  id: string;
  key: string;
  type: 'Epic' | 'Task' | 'Subtask';
  summary: string;
  description: string;
  status: 'To Do' | 'In Progress' | 'Done';
  assignee?: string;
  parentKey?: string;
  epicTitle?: string;
}

export interface EmailFormData {
  recipientName: string;
  recipientEmail: string;
  prdId: string;
}

export interface JIRAApprovalForm {
  decision: 'APPROVE' | 'REJECT';
  notes: string;
}

export interface ActivityItem {
  id: string;
  type: 'prd_created' | 'email_sent' | 'jira_ticket_created';
  description: string;
  timestamp: Date;
  metadata: Record<string, any>;
}

export interface DashboardStats {
  totalPRDs: number;
  averageQualityScore: number;
  totalJIRATickets: number;
  recentActivity: ActivityItem[];
}

export interface AgentResponse {
  output: string;
  text: string;
  sessionId: string;
  mode: string;
  action: 'generate' | 'done' | 'continue';
  fullOutput?: string;
  contextSummary?: string;
  qualityScore?: number;
  grade?: string;
}

// ── SSE event types (FastAPI LangGraph backend) ───────────────────────────

export interface InterruptPayload {
  form: 'email_form' | 'jira_form';
  message: string;
  fields: string[];
  // email_form
  score?: number;
  grade?: string;
  gmail_connected?: boolean;
  gmail_user?: string | null;
  // jira_form
  hint?: string;
  jira_connected?: boolean;
  jira_user?: string | null;
  jira_cloud?: string | null;
  connect_url?: string | null;
}

export interface JiraResult {
  epic_key: string;
  epic_url: string;
  task_keys: string[];
}

export type SSEEvent =
  | { type: 'token';             content: string }
  | { type: 'status';            message: string }
  | { type: 'prd_complete';      score: number; grade: string; file_name: string }
  | { type: 'email_sent';        recipient: string }
  | { type: 'interrupt' } & InterruptPayload
  | { type: 'jira_created' } & JiraResult
  | { type: 'notification_sent'; to: string }
  | { type: 'turn_end';          session_id: string }
  | { type: 'error';             message: string };

// ── App state ─────────────────────────────────────────────────────────────

export interface AppState {
  sessionId: string | null;
  currentMode: 'analyze' | 'generate' | 'complete';
  messages: Message[];
  isTyping: boolean;
  currentPRD: PRDDocument | null;
  prdHistory: PRDDocument[];
  emailStatus: 'idle' | 'sending' | 'sent' | 'error';
  jiraTickets: JIRATicket[];
  jiraApprovalStatus: 'pending' | 'approved' | 'rejected';
  // Phase 3 additions
  interrupt: InterruptPayload | null;
  jiraResult: JiraResult | null;
}

export type AppAction =
  | { type: 'SET_SESSION'; payload: string }
  | { type: 'SET_MODE'; payload: AppState['currentMode'] }
  | { type: 'ADD_MESSAGE'; payload: Message }
  | { type: 'SET_TYPING'; payload: boolean }
  | { type: 'SET_CURRENT_PRD'; payload: PRDDocument | null }
  | { type: 'ADD_PRD_TO_HISTORY'; payload: PRDDocument }
  | { type: 'SET_EMAIL_STATUS'; payload: AppState['emailStatus'] }
  | { type: 'SET_JIRA_TICKETS'; payload: JIRATicket[] }
  | { type: 'SET_JIRA_APPROVAL_STATUS'; payload: AppState['jiraApprovalStatus'] }
  | { type: 'SET_INTERRUPT'; payload: InterruptPayload | null }
  | { type: 'SET_JIRA_RESULT'; payload: JiraResult }
  | { type: 'CLEAR_CHAT' };
