// components/chat/ChatTabBar.tsx
// Accessible multi-session tab strip.
// ARIA pattern: tablist / tab / tabpanel (WAI-ARIA 1.1).
// Keyboard: Left/Right arrows navigate, Delete/Backspace closes, Home/End jump.
import { useRef, useCallback } from 'react';
import { Plus, X, Loader2 } from 'lucide-react';
import { useApp } from '../../context/AppContext';

export function ChatTabBar() {
  const { state, dispatch, activeTab } = useApp();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const isTyping = activeTab.isTyping;

  const handleNew = () => {
    if (isTyping) return;
    dispatch({ type: 'NEW_TAB' });
  };

  const handleSwitch = (tabId: string) => {
    if (isTyping) return;
    dispatch({ type: 'SWITCH_TAB', payload: tabId });
  };

  const handleClose = (e: React.MouseEvent, tabId: string) => {
    e.stopPropagation();
    if (isTyping && tabId === state.activeTabId) return;
    dispatch({ type: 'CLOSE_TAB', payload: tabId });
  };

  // Keyboard navigation within the tablist
  const handleKeyDown = useCallback((e: React.KeyboardEvent, idx: number) => {
    const tabs = state.tabs;
    let next = -1;

    if (e.key === 'ArrowRight') {
      next = (idx + 1) % tabs.length;
    } else if (e.key === 'ArrowLeft') {
      next = (idx - 1 + tabs.length) % tabs.length;
    } else if (e.key === 'Home') {
      next = 0;
    } else if (e.key === 'End') {
      next = tabs.length - 1;
    } else if ((e.key === 'Delete' || e.key === 'Backspace') && tabs.length > 1) {
      e.preventDefault();
      if (!isTyping || tabs[idx].id !== state.activeTabId) {
        dispatch({ type: 'CLOSE_TAB', payload: tabs[idx].id });
      }
      return;
    } else {
      return;
    }

    e.preventDefault();
    if (next >= 0) {
      tabRefs.current[next]?.focus();
      if (!isTyping) dispatch({ type: 'SWITCH_TAB', payload: tabs[next].id });
    }
  }, [state.tabs, state.activeTabId, isTyping, dispatch]);

  return (
    <div className="flex items-center gap-0.5 px-2 pt-2 pb-0 border-b border-white/8 bg-background-secondary/30 overflow-hidden">
      {/* Skip-nav anchor for keyboard users */}
      <a
        href="#chat-panel"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-3 focus:py-1 focus:bg-primary focus:text-white focus:rounded text-xs"
      >
        Skip to chat
      </a>

      <div
        role="tablist"
        aria-label="Chat sessions"
        className="flex items-end gap-0.5 flex-1 min-w-0 tab-scroll-area"
      >
        {state.tabs.map((tab, idx) => {
          const isActive = tab.id === state.activeTabId;
          const isTabTyping = tab.isTyping;

          return (
            <div
              key={tab.id}
              className={[
                'group relative flex items-center rounded-t-lg border border-b-0 text-xs font-medium',
                'transition-colors duration-150 max-w-[120px] sm:max-w-[160px] min-w-[64px] sm:min-w-[80px]',
                'group-focus-within:ring-2 group-focus-within:ring-primary group-focus-within:ring-offset-1 group-focus-within:ring-offset-background-secondary',
                isActive
                  ? 'bg-background-primary text-text-primary border border-b-0 border-white/10'
                  : 'text-text-muted hover:text-text-secondary hover:bg-white/5 border border-transparent',
                (isTyping && !isActive) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
              ].join(' ')}
            >
              <button
                id={`chat-tab-${tab.id}`}
                role="tab"
                aria-selected={isActive}
                aria-controls="chat-panel"
                ref={el => { tabRefs.current[idx] = el; }}
                tabIndex={isActive ? 0 : -1}
                onClick={() => handleSwitch(tab.id)}
                onKeyDown={e => handleKeyDown(e, idx)}
                disabled={isTyping && !isActive}
                title={tab.label}
                className="flex min-w-0 flex-1 items-center gap-1.5 px-3 py-1.5 text-left focus-visible:outline-none"
              >
                {/* Typing spinner on the tab */}
                {isTabTyping && (
                  <Loader2
                    className="w-3 h-3 animate-spin flex-shrink-0 text-primary-light"
                    aria-label="Generating…"
                  />
                )}

                <span className="truncate flex-1 text-left">{tab.label}</span>
              </button>

              {/* Close button — hidden when only 1 tab */}
              {state.tabs.length > 1 && (
                <button
                  type="button"
                  onClick={e => handleClose(e, tab.id)}
                  aria-label={`Close chat: ${tab.label}`}
                  tabIndex={-1}          // tab element handles keyboard; close via Delete key
                  className={[
                    'mr-1 flex-shrink-0 rounded p-0.5',
                    'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100',
                    isActive ? 'opacity-60 hover:opacity-100' : '',
                    'hover:bg-white/10 hover:text-text-primary transition-opacity',
                  ].join(' ')}
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* New tab button */}
      <button
        onClick={handleNew}
        disabled={isTyping}
        aria-label="New chat"
        title={isTyping ? 'Finish current generation before opening a new chat' : 'New chat'}
        className={[
          'flex-shrink-0 sticky right-0 bg-background-secondary/30 p-1.5 mb-0.5 rounded-lg text-text-muted transition-colors',
          'hover:text-text-primary hover:bg-white/8',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
          isTyping ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
        ].join(' ')}
      >
        <Plus className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
