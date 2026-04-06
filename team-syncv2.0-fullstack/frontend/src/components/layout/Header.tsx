// components/layout/Header.tsx

import { useApp } from '../../context/AppContext';
import { Button } from '../ui/Button';
import { Trash2, Sparkles } from 'lucide-react';

export function Header() {
  const { state, dispatch } = useApp();

  const handleClearChat = () => {
    if (confirm('Are you sure you want to clear the current chat?')) {
      dispatch({ type: 'CLEAR_CHAT' });
    }
  };

  return (
    <header className="h-16 bg-background-secondary/50 backdrop-blur-md border-b border-white/8 px-6 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold text-text-primary">
          {state.currentMode === 'analyze' && 'Requirements Gathering'}
          {state.currentMode === 'generate' && 'Generating PRD...'}
          {state.currentMode === 'complete' && 'PRD Complete'}
        </h2>
        {state.currentPRD && (
          <span className="px-2 py-1 bg-primary/20 text-primary-light text-xs rounded-full border border-primary/30">
            {state.currentPRD.grade} Grade
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        {state.messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={handleClearChat}>
            <Trash2 className="w-4 h-4 mr-2" />
            Clear Chat
          </Button>
        )}
        <div className="flex items-center gap-2 px-3 py-1.5 bg-background-tertiary rounded-lg border border-white/10">
          <Sparkles className="w-4 h-4 text-primary-light" />
          <span className="text-sm text-text-secondary">Sam is ready</span>
        </div>
      </div>
    </header>
  );
}
