# Testing Patterns

**Analysis Date:** 2026-03-19

## Test Framework

**Runner:**
- Not detected - no test framework configured
- No `vitest.config.ts`, `jest.config.js`, or test runner in `package.json`
- No `@testing-library/react`, `@testing-library/jest-dom`, or similar test utilities installed

**Assertion Library:**
- Not detected - no test suite exists

**Run Commands:**
```bash
npm run dev              # Start dev server (Vite)
npm run build           # Type-check then build
npm run lint            # ESLint only
npm run preview         # Preview production build
```
No `npm run test` or test-related scripts present.

## Test File Organization

**Location:**
- No test files exist in `src/` directory
- Only node_modules contain test files (zod package tests)
- No `.test.ts`, `.spec.ts`, `.test.tsx`, or `.spec.tsx` files in project

**Naming:**
- Not applicable - no testing framework configured

**Structure:**
- Not applicable - no testing framework configured

## Current Testing Status

**Assessment:**
- **Coverage:** Zero - no tests written
- **Framework:** None - no testing infrastructure configured
- **Recommended:** Consider adding Vitest (Vite-native) or Jest for React component testing

## Recommended Testing Setup

**Framework:** Vitest (aligns with Vite build tool)

**Installation steps (when implemented):**
```bash
npm install --save-dev vitest @vitest/ui
npm install --save-dev @testing-library/react @testing-library/dom @testing-library/jest-dom
npm install --save-dev jsdom  # for DOM simulation
npm install --save-dev @vitest/coverage-v8  # for coverage reports
```

**Config file (vitest.config.ts - hypothetical):**
```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
      ],
    },
  },
});
```

**Package.json scripts (when implemented):**
```json
"test": "vitest",
"test:ui": "vitest --ui",
"test:coverage": "vitest --coverage"
```

## Component Test Patterns (Recommended Structure)

**File colocation:**
```
src/components/chat/
├── ChatInterface.tsx
└── ChatInterface.test.tsx
```

**Example test structure (for ChatInterface component):**
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ChatInterface } from './ChatInterface';
import { AppProvider } from '../../context/AppContext';
import * as apiModule from '../../services/api';

describe('ChatInterface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders welcome message when no messages exist', () => {
    render(
      <AppProvider>
        <ChatInterface />
      </AppProvider>
    );
    expect(screen.getByText('Welcome to TeamSync AI')).toBeInTheDocument();
  });

  it('sends message on button click', async () => {
    const sendMessageSpy = vi.spyOn(apiModule.api, 'sendMessage');

    render(
      <AppProvider>
        <ChatInterface />
      </AppProvider>
    );

    const input = screen.getByPlaceholderText('Describe your feature idea...');
    fireEvent.change(input, { target: { value: 'Test feature' } });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => {
      expect(sendMessageSpy).toHaveBeenCalledWith('Test feature', expect.any(String), 'analyze');
    });
  });

  it('disables send button while typing', async () => {
    render(
      <AppProvider>
        <ChatInterface />
      </AppProvider>
    );

    const button = screen.getByRole('button', { name: /send/i });
    expect(button).not.toBeDisabled();
  });
});
```

## Mocking

**Framework:** Vitest built-in `vi` module (when implemented)

**Patterns (recommended):**

**API mocking:**
```typescript
vi.spyOn(apiModule.api, 'sendMessage').mockResolvedValueOnce({
  output: 'Response text',
  text: 'Response text',
  sessionId: 'test-session',
  mode: 'analyze',
  action: 'continue',
});
```

**Context mocking:**
```typescript
const mockState = {
  sessionId: 'test-123',
  currentMode: 'analyze',
  messages: [],
  isTyping: false,
  currentPRD: null,
  prdHistory: [],
  emailStatus: 'idle' as const,
  jiraTickets: [],
  jiraApprovalStatus: 'pending' as const,
};

vi.mock('../../context/AppContext', () => ({
  useApp: () => ({
    state: mockState,
    dispatch: vi.fn(),
  }),
}));
```

**localStorage mocking:**
```typescript
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
global.localStorage = localStorageMock as any;
```

**What to Mock:**
- API calls via `api.sendMessage()`, `api.submitEmailForm()`, etc.
- External services (n8n webhooks via fetch)
- localStorage operations
- Router navigation (useNavigate)
- Time-dependent functions (setTimeout, Date.now)

**What NOT to Mock:**
- Component internal state (test via rendered output)
- React Context (use real provider wrapper unless testing error boundaries)
- UI library components (Lucide icons, etc.)
- Helper functions colocated with components

## Fixtures and Factories

**Test Data (recommended location: `src/test/fixtures/`):**

```typescript
// src/test/fixtures/mockData.ts
export const createMockMessage = (overrides = {}) => ({
  id: `msg-${Date.now()}`,
  role: 'user' as const,
  content: 'Test message',
  timestamp: new Date(),
  ...overrides,
});

export const createMockPRD = (overrides = {}) => ({
  id: `prd-${Date.now()}`,
  title: 'Test PRD',
  content: '# Test PRD\n## Section 1\n## Section 2',
  qualityScore: 85,
  grade: 'A' as const,
  createdAt: new Date(),
  sections: [
    { id: 's1', title: 'Section 1', level: 2, content: '' },
    { id: 's2', title: 'Section 2', level: 2, content: '' },
  ],
  testCaseCount: 5,
  fileName: 'test.md',
  ...overrides,
});

export const createMockAgentResponse = (overrides = {}) => ({
  output: 'Test output',
  text: 'Test text',
  sessionId: 'test-session',
  mode: 'analyze',
  action: 'continue' as const,
  ...overrides,
});
```

**Setup file (src/test/setup.ts):**
```typescript
import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';

afterEach(() => {
  cleanup();
});

// Suppress console errors in tests unless explicitly needed
const originalError = console.error;
beforeAll(() => {
  console.error = (...args: any[]) => {
    if (
      typeof args[0] === 'string' &&
      args[0].includes('Warning: ReactDOM.render')
    ) {
      return;
    }
    originalError.call(console, ...args);
  };
});
```

## Coverage

**Requirements:** Not enforced - no testing framework configured

**View Coverage (when implemented):**
```bash
npm run test:coverage
```

Output directory: `coverage/` (recommended)

HTML report: `coverage/index.html`

**Recommended targets (when tests are added):**
- Statements: 70%+
- Branches: 65%+
- Functions: 70%+
- Lines: 70%+

## Test Types

**Unit Tests (recommended scope):**
- Individual functions: `extractTitle()`, `parseSections()`, `cn()`, `validate()`
- Component rendering: Props → Output verification
- State management: Reducer logic in isolation
- API service methods: Request/response handling
- Context hooks: Error boundary behavior

**Integration Tests (recommended scope):**
- Component interactions: User input → API call → State update → Re-render
- Multi-component flows: Chat → PRD generation → Email form
- Context provider + consumer interactions
- localStorage read/write during user flow

**E2E Tests (recommended approach):**
- Not configured - would use Playwright or Cypress
- Test user paths: Start chat → Generate PRD → Send email → Create JIRA

## Common Test Patterns (Recommended)

**Async Testing:**
```typescript
it('handles async API call', async () => {
  vi.spyOn(apiModule.api, 'sendMessage').mockResolvedValueOnce({
    output: 'Response',
    text: 'Response',
    sessionId: 'test',
    mode: 'analyze',
    action: 'done',
  });

  render(<ChatInterface />);

  fireEvent.change(screen.getByPlaceholderText('...'), { target: { value: 'test' } });
  fireEvent.click(screen.getByRole('button', { name: /send/i }));

  await waitFor(() => {
    expect(screen.getByText('Response')).toBeInTheDocument();
  });
});
```

**Error Testing:**
```typescript
it('displays error when API fails', async () => {
  vi.spyOn(apiModule.api, 'sendMessage').mockRejectedValueOnce(
    new Error('Network error')
  );

  render(<ChatInterface />);

  fireEvent.change(screen.getByPlaceholderText('...'), { target: { value: 'test' } });
  fireEvent.click(screen.getByRole('button'));

  await waitFor(() => {
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });
});
```

**Form Validation Testing:**
```typescript
it('prevents submit with invalid email', async () => {
  render(
    <AppProvider>
      <EmailForm />
    </AppProvider>
  );

  fireEvent.change(screen.getByPlaceholderText('john@example.com'), {
    target: { value: 'invalid-email' },
  });
  fireEvent.click(screen.getByRole('button', { name: /send prd/i }));

  await waitFor(() => {
    expect(screen.getByText('Invalid email address')).toBeInTheDocument();
  });
});
```

---

*Testing analysis: 2026-03-19*

**Note:** This codebase currently has no test suite. The patterns documented above represent recommended best practices aligned with the project's tech stack. Implementation of tests is a future priority.
