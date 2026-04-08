// types/index.ts

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'artifact';
  content: string;
  timestamp: Date;
  attachments?: UploadedFile[];
  metadata?: {
    action?: 'generate' | 'done' | 'continue';
    qualityScore?: number;
    grade?: string;
    prdId?: string;
  };
}

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
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
  docType?: 'prd' | 'test_cases';
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

export interface UploadedFile {
  filename: string;
  content_type: string;
  preview: string;
}

export interface InterruptPayload {
  form: 'email_form' | 'jira_form' | 'jira_auto_confirm' | 'prd_outline_form' | 'post_prd_actions';
  message: string;
  fields?: string[];
  // prd_outline_form
  outline?: string;
  // email_form
  score?: number;
  grade?: string;
  gmail_connected?: boolean;
  gmail_user?: string | null;
  // jira_form / jira_auto_confirm
  hint?: string;
  jira_connected?: boolean;
  jira_user?: string | null;
  jira_cloud?: string | null;
  connect_url?: string | null;
  auto_confirm?: boolean;
  countdown_seconds?: number;
  available_projects?: { key: string; name: string }[];
  default_project?: string;
  actions_taken?: string[];
}

export interface JiraResult {
  epic_key: string;
  epic_url: string;
  task_keys: string[];
}

export interface JiraConnectionStatus {
  connected: boolean;
  user_name: string | null;
  cloud_name: string | null;
  user_email: string | null;
  auth_mode: 'oauth' | 'pat' | null;
  project_url: string | null;
}

export type SSEEvent =
  | { type: 'token';                content: string }
  | { type: 'status';               message: string }
  | { type: 'prd_complete';         score: number; grade: string; file_name: string }
  | { type: 'test_cases_complete';  file_name: string; tc_count: number }
  | { type: 'email_sent';           recipient: string }
  | { type: 'interrupt' } & InterruptPayload
  | { type: 'jira_created' } & JiraResult
  | { type: 'jira_progress';     message: string; current: number; total: number }
  | { type: 'notification_sent'; to: string }
  | { type: 'turn_end';          session_id: string }
  | { type: 'error';             message: string };

// ── Chat tab (one per concurrent session) ────────────────────────────────

export interface ChatTab {
  id: string;                                           // = LangGraph thread_id
  label: string;                                        // shown in tab strip
  sessionId: string;
  messages: Message[];
  currentMode: 'analyze' | 'generate' | 'complete';
  isTyping: boolean;
  currentPRD: PRDDocument | null;
  emailStatus: 'idle' | 'sending' | 'sent' | 'error';
  jiraApprovalStatus: 'pending' | 'approved' | 'rejected';
  interrupt: InterruptPayload | null;
  jiraResult: JiraResult | null;
}

// ── App state ─────────────────────────────────────────────────────────────

export interface AppState {
  tabs: ChatTab[];
  activeTabId: string;
  prdHistory: PRDDocument[];
  jiraTickets: JIRATicket[];
  jiraConnection: JiraConnectionStatus | null;
}

export type AppAction =
  | { type: 'BOOTSTRAP'; payload: { tabs: ChatTab[]; activeTabId: string | null; prdHistory: PRDDocument[]; jiraTickets: JIRATicket[] } }
  | { type: 'SET_SESSION'; payload: string }
  | { type: 'SET_MODE'; payload: ChatTab['currentMode'] }
  | { type: 'ADD_MESSAGE'; payload: Message }
  | { type: 'SET_TYPING'; payload: boolean }
  | { type: 'SET_CURRENT_PRD'; payload: PRDDocument | null }
  | { type: 'ADD_PRD_TO_HISTORY'; payload: PRDDocument }
  | { type: 'SET_EMAIL_STATUS'; payload: ChatTab['emailStatus'] }
  | { type: 'SET_JIRA_TICKETS'; payload: JIRATicket[] }
  | { type: 'SET_JIRA_APPROVAL_STATUS'; payload: ChatTab['jiraApprovalStatus'] }
  | { type: 'SET_INTERRUPT'; payload: InterruptPayload | null }
  | { type: 'SET_JIRA_RESULT'; payload: JiraResult }
  | { type: 'CLEAR_CHAT' }
  | { type: 'RESET_STATE' }
  | { type: 'RESTORE_SESSION'; payload: { sessionId: string; label?: string } }
  | { type: 'SET_JIRA_CONNECTION'; payload: JiraConnectionStatus | null }
  | { type: 'NEW_TAB' }
  | { type: 'SWITCH_TAB'; payload: string }   // tabId
  | { type: 'CLOSE_TAB'; payload: string };   // tabId
