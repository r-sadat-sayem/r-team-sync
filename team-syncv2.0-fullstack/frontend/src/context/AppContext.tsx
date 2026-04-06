// context/AppContext.tsx
import React, { createContext, useContext, useReducer, useEffect } from 'react';
import type { AppState, AppAction, PRDDocument } from '../types';
import { api } from '../services/api';

const initialState: AppState = {
  sessionId: null,
  currentMode: 'analyze',
  messages: [],
  isTyping: false,
  currentPRD: null,
  prdHistory: [],
  emailStatus: 'idle',
  jiraTickets: [],
  jiraApprovalStatus: 'pending',
  interrupt: null,
  jiraResult: null,
};

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_SESSION':
      return { ...state, sessionId: action.payload };
    case 'SET_MODE':
      return { ...state, currentMode: action.payload };
    case 'ADD_MESSAGE': {
      const msgs = [...state.messages, action.payload];
      api.saveMessages(msgs);
      return { ...state, messages: msgs };
    }
    case 'SET_TYPING':
      return { ...state, isTyping: action.payload };
    case 'SET_CURRENT_PRD':
      return { ...state, currentPRD: action.payload };
    case 'ADD_PRD_TO_HISTORY':
      api.savePRD(action.payload);
      return { ...state, prdHistory: [action.payload, ...state.prdHistory] };
    case 'SET_EMAIL_STATUS':
      return { ...state, emailStatus: action.payload };
    case 'SET_JIRA_TICKETS':
      api.saveJIRATickets(action.payload);
      return { ...state, jiraTickets: action.payload };
    case 'SET_JIRA_APPROVAL_STATUS':
      return { ...state, jiraApprovalStatus: action.payload };
    case 'SET_INTERRUPT':
      return { ...state, interrupt: action.payload };
    case 'SET_JIRA_RESULT':
      return { ...state, jiraResult: action.payload };
    case 'CLEAR_CHAT':
      api.clearSession();
      return {
        ...state,
        messages: [],
        sessionId: null,
        currentMode: 'analyze',
        interrupt: null,
        jiraResult: null,
        currentPRD: null,
        emailStatus: 'idle',
        jiraApprovalStatus: 'pending',
      };
    default:
      return state;
  }
}

interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  useEffect(() => {
    const sessionId = api.getSessionId();
    dispatch({ type: 'SET_SESSION', payload: sessionId });

    const messages = api.getMessages();
    messages.forEach(msg => dispatch({ type: 'ADD_MESSAGE', payload: msg }));

    const history = api.getPRDHistory();
    history.forEach((prd: PRDDocument) => dispatch({ type: 'ADD_PRD_TO_HISTORY', payload: prd }));

    const tickets = api.getJIRATickets();
    if (tickets.length > 0) dispatch({ type: 'SET_JIRA_TICKETS', payload: tickets });
  }, []);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within an AppProvider');
  return context;
}
