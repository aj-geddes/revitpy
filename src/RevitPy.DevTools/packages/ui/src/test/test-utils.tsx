import React from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '../providers/theme-provider';
import { ToastProvider } from '../providers/toast-provider';

// Create a custom render function that includes providers
const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider defaultTheme="light" storageKey="test-theme">
          <ToastProvider>
            {children}
          </ToastProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

const customRender = (
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllTheProviders, ...options });

// Re-export everything
export * from '@testing-library/react';
export { customRender as render };

// Test utilities
export const createMockQueryClient = () => {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
};

export const mockLocalStorage = () => {
  const store: Record<string, string> = {};
  
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      Object.keys(store).forEach(key => delete store[key]);
    }),
  };
};

export const mockIntersectionObserver = () => {
  const mockObserver = {
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  };

  window.IntersectionObserver = vi.fn().mockImplementation(() => mockObserver);
  
  return mockObserver;
};

export const mockResizeObserver = () => {
  const mockObserver = {
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
  };

  window.ResizeObserver = vi.fn().mockImplementation(() => mockObserver);
  
  return mockObserver;
};

export const mockMatchMedia = (matches = false) => {
  const mockMatchMedia = vi.fn().mockImplementation(query => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(), // Deprecated
    removeListener: vi.fn(), // Deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));

  window.matchMedia = mockMatchMedia;
  
  return mockMatchMedia;
};

// Custom matchers for accessibility testing
export const axeMatchers = {
  toBeAccessible: (received: HTMLElement) => {
    // This would integrate with axe-core for accessibility testing
    // For now, we'll do basic checks
    const hasAriaLabel = received.hasAttribute('aria-label');
    const hasAriaLabelledBy = received.hasAttribute('aria-labelledby');
    const hasAriaDescribedBy = received.hasAttribute('aria-describedby');
    const hasRole = received.hasAttribute('role');
    
    const isAccessible = hasAriaLabel || hasAriaLabelledBy || hasAriaDescribedBy || hasRole;
    
    return {
      message: () => `Expected element to be accessible`,
      pass: isAccessible,
    };
  },
};

// Mock data generators
export const mockPerformanceData = (count = 10) => {
  const data = [];
  const now = Date.now();
  
  for (let i = 0; i < count; i++) {
    data.push({
      timestamp: now - (count - i) * 1000,
      memory: Math.random() * 100,
      cpu: Math.random() * 100,
      operations: Math.floor(Math.random() * 1000),
      responseTime: Math.floor(Math.random() * 500),
    });
  }
  
  return data;
};

export const mockPackageData = () => ({
  id: 'test-package',
  name: 'Test Package',
  version: '1.0.0',
  description: 'A test package for testing purposes',
  author: 'Test Author',
  category: 'testing',
  tags: ['test', 'mock'],
  rating: 4.5,
  downloadCount: 1234,
  publishDate: new Date('2024-01-01'),
  revitVersions: ['2023', '2024'],
  verified: true,
});

export const mockProjectData = () => ({
  id: 'test-project',
  name: 'Test Project',
  path: '/test/project',
  config: {
    name: 'Test Project',
    version: '1.0.0',
    type: 'command' as const,
    revitVersions: ['2024'],
    pythonVersion: '3.11',
    entry: 'main.py',
  },
  status: 'active' as const,
  lastModified: new Date('2024-01-01'),
  stats: {
    files: 10,
    lines: 1000,
    size: 50000,
  },
});

// Test component wrappers
export const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <AllTheProviders>{children}</AllTheProviders>
);

export const MockThemeProvider = ({ 
  children, 
  theme = 'light' 
}: { 
  children: React.ReactNode; 
  theme?: 'light' | 'dark' | 'system';
}) => (
  <ThemeProvider defaultTheme={theme} storageKey="test-theme">
    {children}
  </ThemeProvider>
);

// Event simulation helpers
export const simulateKeyPress = (element: HTMLElement, key: string, options?: KeyboardEventInit) => {
  const keyboardEvent = new KeyboardEvent('keydown', { key, ...options });
  element.dispatchEvent(keyboardEvent);
};

export const simulateMouseEvent = (element: HTMLElement, eventType: string, options?: MouseEventInit) => {
  const mouseEvent = new MouseEvent(eventType, { bubbles: true, ...options });
  element.dispatchEvent(mouseEvent);
};

// Async test helpers
export const waitForNextTick = () => new Promise(resolve => setTimeout(resolve, 0));

export const waitForAnimation = (duration = 300) => new Promise(resolve => setTimeout(resolve, duration));

// Mock fetch
export const mockFetch = (response: any, ok = true, status = 200) => {
  global.fetch = vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(response),
    text: () => Promise.resolve(JSON.stringify(response)),
  });
};

// Component testing helpers
export const getElementByTestId = (container: HTMLElement, testId: string) => {
  return container.querySelector(`[data-testid="${testId}"]`);
};

export const getAllElementsByTestId = (container: HTMLElement, testId: string) => {
  return container.querySelectorAll(`[data-testid="${testId}"]`);
};