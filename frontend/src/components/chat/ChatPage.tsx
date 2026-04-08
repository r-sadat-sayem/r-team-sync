// components/chat/ChatPage.tsx
// Wrapper rendered at route "/".
// The key={activeTabId} on ChatInterface causes a full remount (and ref-reset)
// whenever the user switches tabs — this is intentional. Tab switching is
// disabled while the active tab is typing, so no in-flight stream is lost.
import { useApp } from '../../context/AppContext';
import { ChatTabBar } from './ChatTabBar';
import { ChatInterface } from './ChatInterface';

export function ChatPage() {
  const { state } = useApp();

  return (
    <div className="flex flex-col h-full" aria-label="Chat workspace">
      <ChatTabBar />
      {/* Layout's <main> already provides p-6; no extra padding needed here */}
      <div
        id="chat-panel"
        role="tabpanel"
        aria-labelledby={`chat-tab-${state.activeTabId}`}
        className="flex-1 min-h-0"
      >
        <ChatInterface key={state.activeTabId} />
      </div>
    </div>
  );
}
