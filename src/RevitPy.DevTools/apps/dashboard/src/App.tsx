import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from '@/components/ui/toaster';
import { ThemeProvider } from '@/components/theme-provider';
import { RevitPyProvider } from '@/providers/revitpy-provider';
import { AppRoutes } from '@/routes';
import { ErrorBoundary } from '@/components/error-boundary';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
      retry: (failureCount, error) => {
        if (error instanceof Error && error.message.includes('Network')) {
          return failureCount < 3;
        }
        return false;
      },
    },
  },
});

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider defaultTheme="system" storageKey="revitpy-ui-theme">
          <RevitPyProvider>
            <BrowserRouter>
              <AppRoutes />
              <Toaster />
            </BrowserRouter>
          </RevitPyProvider>
        </ThemeProvider>
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
