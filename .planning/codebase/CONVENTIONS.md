# Coding Conventions

**Analysis Date:** 2026-03-19

## Naming Patterns

**Files:**
- Components: PascalCase with `.tsx` extension (e.g., `ChatInterface.tsx`, `EmailForm.tsx`)
- Services/APIs: camelCase with `.ts` extension (e.g., `api.ts`)
- Types/Interfaces: Exported from central index (e.g., `types/index.ts`)
- Utilities: camelCase (e.g., `cn()` helper function)
- Organized by feature in subdirectories: `components/{feature}/`, `services/`, `context/`, `hooks/`, `types/`

**Functions:**
- Component functions: PascalCase, exported as named functions or const arrow functions (e.g., `export function ChatInterface()`)
- Utility functions: camelCase, lowercase start (e.g., `extractTitle()`, `parseSections()`, `cn()`)
- Handler functions: prefixed with `handle` in camelCase (e.g., `handleSend`, `handleKeyDown`, `handleCopy`)
- Helper functions defined after export: lowercase, colocated with components that use them

**Variables:**
- State variables: camelCase (e.g., `const [input, setInput] = useState('')`)
- Constants from imports: Uppercase + SCREAMING_SNAKE_CASE for env vars (e.g., `const N8N_BASE_URL = ...`)
- Type annotations explicit on all state: `useState<string | null>(null)`, `useState<Record<string, string>>({})`

**Types:**
- Interfaces: PascalCase, prefixed with feature name when appropriate (e.g., `Message`, `PRDDocument`, `ButtonProps`)
- Union types: Uppercase with pipe separator (e.g., `'user' | 'assistant' | 'system'`)
- Stored in `src/types/index.ts` as single source of truth
- Exported from types file, imported throughout app

## Code Style

**Formatting:**
- ESLint: flat config at `frontend/eslint.config.js`
- No Prettier config detected; code follows ESLint defaults
- Uses `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`
- Two-space indentation (standard ESLint default)
- Semicolons used throughout
- Single quotes for strings (ESLint recommended)

**Linting:**
- TypeScript strict mode enabled: `"strict": true`
- `noUnusedLocals: true` and `noUnusedParameters: true` enforced
- ESLint runs with: `npm run lint` from `frontend/` directory
- Pre-commit hooks: None detected (no husky or pre-commit config)

## Import Organization

**Order:**
1. React and external libraries (e.g., `import React from 'react'`, `import { useState } from 'react'`)
2. Router/Navigation imports (e.g., `import { useParams, useNavigate } from 'react-router-dom'`)
3. Markdown and third-party utilities (e.g., `import ReactMarkdown from 'react-markdown'`)
4. Internal context/hooks (e.g., `import { useApp } from '../../context/AppContext'`)
5. Internal services (e.g., `import { api } from '../../services/api'`)
6. Components (e.g., `import { Button } from '../ui/Button'`)
7. Icons (e.g., `import { Send, Bot, User, Loader2 } from 'lucide-react'`)
8. Type imports (e.g., `import type { Message, PRDDocument } from '../../types'`)
9. Styles (e.g., `import './App.css'`)

**Path Aliases:**
- None configured; all paths relative using `../../` patterns
- No `jsconfig.json` or `tsconfig` path aliases

## Error Handling

**Patterns:**
- Try-catch with `.catch()` fallback for async operations
- Error state via local component state: `const [error, setError] = useState<string | null>(null)`
- Error display as conditional UI blocks (e.g., `{error && <div className="...error...">{error}</div>}`)
- API errors caught and message extracted: `err instanceof Error ? err.message : 'Failed to send message'`
- Email form validation with client-side `validate()` function returning boolean, errors object
- Validation errors stored in `errors` state as `Record<string, string>`
- HTTP status checks: `if (!response.ok) throw new Error(...)`

## Logging

**Framework:** console (no logging library detected)

**Patterns:**
- No logging observed in codebase
- Developer console available via browser DevTools
- No structured logging, log aggregation, or error tracking

## Comments

**When to Comment:**
- Minimal comments; code is self-documenting
- Comments used for clarifying non-obvious logic (e.g., `// Parse Agent Response`)
- Inline comments for tricky regex patterns or complex parsing
- No JSDoc/TSDoc observed

**JSDoc/TSDoc:**
- Not used; types are inferred from TypeScript interfaces
- Function signatures use TypeScript for documentation
- No docstrings or parameter documentation

## Function Design

**Size:** Functions vary from single-statement helpers to ~50-line components
- Small utility functions: 5-10 lines (e.g., `extractTitle()`, `countTestCases()`)
- Component handlers: 10-25 lines (e.g., `handleSend()`, `handleSubmit()`)
- Full components: 30-100+ lines (e.g., `ChatInterface`, `EmailForm`)

**Parameters:**
- Explicit typed parameters, no implicit `any`
- React component props as single object with destructuring: `({ children }: { children: React.ReactNode })`
- API methods take typed data objects: `(data: EmailFormData)` not multiple params
- Default parameters used: `async sendMessage(chatInput: string, sessionId: string, mode: string = 'analyze')`

**Return Values:**
- React components return JSX: `return (<div>...</div>)`
- Async API methods return typed promises: `Promise<AgentResponse>`
- Helper functions return typed values: `string | null`, `number`, `PRDSection[]`
- Error paths throw rather than return null (API methods)

## Module Design

**Exports:**
- Named exports for functions and components: `export function ChatInterface() {...}`
- Default export for main App: `export default App`
- Singleton service exported: `export const api = new TeamSyncAPI()`
- Context exported as provider and hook: `export function AppProvider()` and `export function useApp()`

**Barrel Files:**
- `src/types/index.ts` acts as barrel file for all type exports
- No other barrel files detected (`src/components/index.ts`, etc. missing)

## Component Patterns

**React.forwardRef pattern:** Used for UI components (`Button`, `Input`, `Card`, `CardHeader`, etc.)
- Signature: `React.forwardRef<HTMLButtonElement, ButtonProps>(({ ...props }, ref) => (...))`
- Always includes `displayName` setter: `Button.displayName = 'Button'`

**Variant pattern:** Props-based style variants for UI components
```typescript
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
}
const variants = {
  primary: 'bg-gradient-to-r from-primary to-primary-light text-white hover:opacity-90 focus:ring-primary',
  secondary: 'bg-background-tertiary text-text-primary border border-white/10 hover:bg-white/5 focus:ring-primary',
  ghost: 'text-text-secondary hover:text-text-primary hover:bg-white/5 focus:ring-primary',
  danger: 'bg-status-error/20 text-status-error border border-status-error/30 hover:bg-status-error/30 focus:ring-status-error',
};
```

**Tailwind + clsx + twMerge pattern:** Centralized `cn()` helper for class composition
```typescript
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
// Usage:
className={cn(
  'base-classes',
  variableCondition && 'conditional-class',
  props.className // user overrides
)}
```

**Reducer pattern:** Redux-like action dispatch for global state
- `AppContext` uses `useReducer` with typed `AppAction` union
- Actions dispatched as objects: `dispatch({ type: 'ADD_MESSAGE', payload: message })`
- Switch statement in reducer maps action types to state updates

**Hook pattern:** Custom hook for context consumption with error boundary
```typescript
export function useApp() {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
```

## Tailwind CSS

**Approach:** Utility-first inline classes in JSX
- No external CSS classes beyond `index.css` and `App.css` for global resets
- Responsive classes: `lg:col-span-1`, `lg:col-span-3`, `lg:col-span-4`
- Hover/focus states: `hover:opacity-90`, `focus:outline-none`, `focus:ring-2`
- Animations: `animate-spin`, `animate-bounce`, `animate-pulse`
- Custom CSS variables for colors: `bg-primary`, `text-text-primary`, `border-white/10`

---

*Convention analysis: 2026-03-19*
