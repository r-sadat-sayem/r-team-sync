// context/AppContext.tsx
import React, { createContext, useContext, useReducer, useEffect, useCallback } from 'react';
import type { AppState, AppAction, ChatTab, PRDDocument } from '../types';
import { api } from '../services/api';
import { useAuth } from './AuthContext';

// ── Tab factory ───────────────────────────────────────────────────────────

function createTab(overrides: Partial<ChatTab> = {}): ChatTab {
  const id = overrides.id ?? crypto.randomUUID();
  return {
    id,
    label: 'New Chat',
    sessionId: id,
    messages: [],
    currentMode: 'analyze',
    isTyping: false,
    currentPRD: null,
    emailStatus: 'idle',
    jiraApprovalStatus: 'pending',
    interrupt: null,
    jiraResult: null,
    ...overrides,
  };
}

const defaultTab = createTab();

const initialState: AppState = {
  tabs: [defaultTab],
  activeTabId: defaultTab.id,
  prdHistory: [],
  jiraTickets: [],
  jiraConnection: null,
};

// ── Helpers ───────────────────────────────────────────────────────────────

function updateActiveTab(state: AppState, update: Partial<ChatTab>): AppState {
  const next = state.tabs.map(t =>
    t.id === state.activeTabId ? { ...t, ...update } : t,
  );
  api.saveChatTabs(next);
  return { ...state, tabs: next };
}

// Auto-derive a label from first user message if still on default
function autoLabel(tab: ChatTab, newMessage: ChatTab['messages'][0]): string {
  if (tab.label !== 'New Chat') return tab.label;
  if (newMessage.role === 'user') return newMessage.content.slice(0, 30);
  return tab.label;
}

// ── Reducer ───────────────────────────────────────────────────────────────

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {

    case 'BOOTSTRAP': {
      const tabs = action.payload.tabs.length > 0
        ? action.payload.tabs
        : [createTab()];
      const activeTabId = (
        action.payload.activeTabId && tabs.find(t => t.id === action.payload.activeTabId)
          ? action.payload.activeTabId
          : tabs[0].id
      );
      return {
        ...state,
        tabs,
        activeTabId,
        prdHistory: action.payload.prdHistory,
        jiraTickets: action.payload.jiraTickets,
      };
    }

    case 'NEW_TAB': {
      const tab = createTab();
      const next = [...state.tabs, tab];
      api.saveChatTabs(next);
      api.saveActiveTabId(tab.id);
      return { ...state, tabs: next, activeTabId: tab.id };
    }

    case 'SWITCH_TAB': {
      if (!state.tabs.find(t => t.id === action.payload)) return state;
      api.saveActiveTabId(action.payload);
      return { ...state, activeTabId: action.payload };
    }

    case 'CLOSE_TAB': {
      if (state.tabs.length <= 1) return state; // keep at least one tab
      const next = state.tabs.filter(t => t.id !== action.payload);
      const activeTabId = state.activeTabId === action.payload
        ? next[Math.max(0, state.tabs.findIndex(t => t.id === action.payload) - 1)].id
        : state.activeTabId;
      api.saveChatTabs(next);
      api.saveActiveTabId(activeTabId);
      return { ...state, tabs: next, activeTabId };
    }

    case 'SET_SESSION':
      return updateActiveTab(state, { sessionId: action.payload });

    case 'SET_MODE':
      return updateActiveTab(state, { currentMode: action.payload });

    case 'ADD_MESSAGE': {
      const active = state.tabs.find(t => t.id === state.activeTabId)!;
      const msgs = [...active.messages, action.payload];
      const label = autoLabel(active, action.payload);
      return updateActiveTab(state, { messages: msgs, label });
    }

    case 'SET_TYPING':
      return updateActiveTab(state, { isTyping: action.payload });

    case 'SET_CURRENT_PRD': {
      const label = action.payload?.title ?? state.tabs.find(t => t.id === state.activeTabId)!.label;
      return updateActiveTab(state, {
        currentPRD: action.payload,
        label: action.payload ? label : state.tabs.find(t => t.id === state.activeTabId)!.label,
      });
    }

    case 'ADD_PRD_TO_HISTORY': {
      api.savePRD(action.payload);
      const nextHistory = [action.payload, ...state.prdHistory];
      // Also update the tab label to the PRD title
      const next = state.tabs.map(t =>
        t.id === state.activeTabId ? { ...t, label: action.payload.title.slice(0, 30) } : t,
      );
      api.saveChatTabs(next);
      return { ...state, tabs: next, prdHistory: nextHistory };
    }

    case 'SET_EMAIL_STATUS':
      return updateActiveTab(state, { emailStatus: action.payload });

    case 'SET_JIRA_TICKETS':
      api.saveJIRATickets(action.payload);
      return { ...state, jiraTickets: action.payload };

    case 'SET_JIRA_APPROVAL_STATUS':
      return updateActiveTab(state, { jiraApprovalStatus: action.payload });

    case 'SET_INTERRUPT':
      return updateActiveTab(state, { interrupt: action.payload });

    case 'SET_JIRA_RESULT':
      return updateActiveTab(state, { jiraResult: action.payload });

    case 'SET_JIRA_CONNECTION':
      return { ...state, jiraConnection: action.payload };

    case 'MARK_PRD_DEPRECATED': {
      const updated = state.prdHistory.map(p =>
        p.id === action.payload ? { ...p, deprecated: true } : p,
      );
      api.replacePRDHistory(updated);
      // Also reflect deprecation on the active tab's currentPRD if it matches
      const tabs = state.tabs.map(t =>
        t.id === state.activeTabId && t.currentPRD?.id === action.payload
          ? { ...t, currentPRD: { ...t.currentPRD, deprecated: true } }
          : t,
      );
      api.saveChatTabs(tabs);
      return { ...state, prdHistory: updated, tabs };
    }

    case 'CLEAR_CHAT': {
      const cleared = createTab({
        id: state.activeTabId,
        sessionId: state.activeTabId,
      });
      const next = state.tabs.map(t => t.id === state.activeTabId ? cleared : t);
      api.saveChatTabs(next);
      return { ...state, tabs: next };
    }

    case 'RESET_STATE': {
      api.saveChatTabs([]);
      return initialState;
    }

    case 'RESTORE_SESSION': {
      // Reuse existing tab if session already open
      const existing = state.tabs.find(t => t.sessionId === action.payload.sessionId);
      if (existing) {
        api.saveActiveTabId(existing.id);
        return { ...state, activeTabId: existing.id };
      }
      const tab = createTab({
        id: action.payload.sessionId,
        sessionId: action.payload.sessionId,
        label: action.payload.label?.slice(0, 30) ?? 'Resumed Session',
      });
      const next = [...state.tabs, tab];
      api.saveChatTabs(next);
      api.saveActiveTabId(tab.id);
      return { ...state, tabs: next, activeTabId: tab.id };
    }

    default:
      return state;
  }
}

// ── Context ───────────────────────────────────────────────────────────────

interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
  /** The currently active tab — convenience shortcut */
  activeTab: ChatTab;
  /** Refresh global JIRA connection status from the server */
  refreshJiraConnection: () => Promise<void>;
  /** True while the initial jiraConnection status fetch is in flight */
  jiraConnectionLoading: boolean;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const { user, isLoading } = useAuth();
  const [jiraConnectionLoading, setJiraConnectionLoading] = React.useState(true);

  const refreshJiraConnection = useCallback(async () => {
    setJiraConnectionLoading(true);
    try {
      const status = await api.getUserJiraStatus();
      dispatch({ type: 'SET_JIRA_CONNECTION', payload: status });
    } catch {
      dispatch({ type: 'SET_JIRA_CONNECTION', payload: null });
    } finally {
      setJiraConnectionLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isLoading) return;
    if (!user) {
      dispatch({ type: 'RESET_STATE' });
      setJiraConnectionLoading(false);
      return;
    }

    api.setStorageNamespace(`user:${user.id}`);
    dispatch({
      type: 'BOOTSTRAP',
      payload: {
        tabs:        api.getChatTabs(),
        activeTabId: api.getActiveTabId(),
        prdHistory:  api.getPRDHistory() as PRDDocument[],
        jiraTickets: api.getJIRATickets(),
      },
    });
    // Load JIRA connection status once on login
    void refreshJiraConnection();
  }, [user, isLoading, refreshJiraConnection]);

  const activeTab = state.tabs.find(t => t.id === state.activeTabId) ?? state.tabs[0];

  return (
    <AppContext.Provider value={{ state, dispatch, activeTab, refreshJiraConnection, jiraConnectionLoading }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within an AppProvider');
  return context;
}
