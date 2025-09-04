import { createContext, useContext, useEffect, useRef, ReactNode } from 'react';
import { useRevitPyStore } from '@/stores/revitpy';
import { useToast } from '@/hooks/use-toast';
import type { WebViewMessage } from '@revitpy/types';

interface RevitPyContextType {
  sendMessage: (message: WebViewMessage) => Promise<void>;
  isConnected: boolean;
}

const RevitPyContext = createContext<RevitPyContextType | null>(null);

interface RevitPyProviderProps {
  children: ReactNode;
}

export function RevitPyProvider({ children }: RevitPyProviderProps) {
  const { toast } = useToast();
  const {
    setConnectionStatus,
    setRuntime,
    setPerformanceMetrics,
    connectionStatus
  } = useRevitPyStore();
  
  const messageId = useRef(0);
  const pendingRequests = useRef(new Map<string, {
    resolve: (value: any) => void;
    reject: (error: Error) => void;
  }>());

  // Send message to RevitPy host
  const sendMessage = async (message: WebViewMessage): Promise<any> => {
    return new Promise((resolve, reject) => {
      if (!window.revitpy?.sendMessage) {
        reject(new Error('RevitPy bridge not available'));
        return;
      }

      const id = `msg_${++messageId.current}`;
      const messageWithId = { ...message, id };
      
      // Store the promise resolvers
      pendingRequests.current.set(id, { resolve, reject });
      
      // Set timeout for request
      setTimeout(() => {
        const pending = pendingRequests.current.get(id);
        if (pending) {
          pendingRequests.current.delete(id);
          pending.reject(new Error('Request timeout'));
        }
      }, 30000);

      try {
        window.revitpy.sendMessage(messageWithId);
      } catch (error) {
        pendingRequests.current.delete(id);
        reject(error);
      }
    });
  };

  // Handle messages from RevitPy host
  useEffect(() => {
    const handleMessage = (event: CustomEvent) => {
      const message = event.detail as WebViewMessage;
      
      try {
        switch (message.type) {
          case 'response':
            // Handle response to a previous request
            const pending = pendingRequests.current.get(message.id);
            if (pending) {
              pendingRequests.current.delete(message.id);
              if (message.success) {
                pending.resolve(message.data);
              } else {
                pending.reject(new Error(message.error?.message || 'Unknown error'));
              }
            }
            break;

          case 'notification':
            // Handle notifications from host
            handleNotification(message);
            break;

          case 'databinding':
            // Handle data binding updates
            handleDataBinding(message);
            break;

          case 'hotreload':
            // Handle hot reload events
            handleHotReload(message);
            break;

          case 'performance':
            // Handle performance metrics
            if (message.data) {
              setPerformanceMetrics(message.data);
            }
            break;

          case 'error':
            // Handle errors
            handleError(message);
            break;

          default:
            console.log('Unhandled message type:', message.type);
        }
      } catch (error) {
        console.error('Error handling message:', error);
        toast({
          title: 'Message Error',
          description: 'Failed to process message from RevitPy host',
          variant: 'destructive'
        });
      }
    };

    // Listen for messages from RevitPy host
    window.addEventListener('revitpy:message', handleMessage as EventListener);

    return () => {
      window.removeEventListener('revitpy:message', handleMessage as EventListener);
    };
  }, [setPerformanceMetrics, toast]);

  // Initialize connection
  useEffect(() => {
    const initializeConnection = async () => {
      try {
        setConnectionStatus('connecting');
        
        // Check if RevitPy bridge is available
        if (!window.revitpy) {
          throw new Error('RevitPy bridge not available');
        }

        // Request runtime information
        const runtime = await sendMessage({
          type: 'request',
          method: 'getRuntime',
          id: '',
          timestamp: Date.now()
        });

        setRuntime(runtime);
        setConnectionStatus('connected');

        toast({
          title: 'Connected',
          description: 'Successfully connected to RevitPy runtime',
        });

      } catch (error) {
        console.error('Failed to initialize RevitPy connection:', error);
        setConnectionStatus('error');
        
        toast({
          title: 'Connection Error',
          description: 'Failed to connect to RevitPy runtime',
          variant: 'destructive'
        });
      }
    };

    // Only initialize if we're in a WebView environment
    if (typeof window !== 'undefined') {
      // Small delay to ensure the WebView bridge is ready
      setTimeout(initializeConnection, 100);
    }
  }, [setConnectionStatus, setRuntime, toast]);

  // Periodic connection health check
  useEffect(() => {
    if (connectionStatus !== 'connected') return;

    const healthCheckInterval = setInterval(async () => {
      try {
        await sendMessage({
          type: 'request',
          method: 'ping',
          id: '',
          timestamp: Date.now()
        });
      } catch (error) {
        console.error('Health check failed:', error);
        setConnectionStatus('error');
        
        toast({
          title: 'Connection Lost',
          description: 'Lost connection to RevitPy runtime',
          variant: 'destructive'
        });
      }
    }, 30000); // Check every 30 seconds

    return () => clearInterval(healthCheckInterval);
  }, [connectionStatus, setConnectionStatus, toast]);

  const handleNotification = (message: WebViewMessage) => {
    if (message.event === 'runtime:status') {
      setConnectionStatus(message.data.status);
    }
    
    // Show toast notification
    if (message.data?.title) {
      toast({
        title: message.data.title,
        description: message.data.message,
        variant: message.data.type === 'error' ? 'destructive' : 'default'
      });
    }
  };

  const handleDataBinding = (message: any) => {
    // Handle real-time data updates from the host
    const { propertyPath, value } = message;
    
    // Update store based on property path
    if (propertyPath.startsWith('runtime.')) {
      // Update runtime properties
    } else if (propertyPath.startsWith('projects.')) {
      // Update project data
    }
    // Add more data binding handlers as needed
  };

  const handleHotReload = (message: any) => {
    if (message.fullReload) {
      // Full page reload required
      window.location.reload();
    } else {
      // Partial reload - handle specific file types
      console.log('Hot reload:', message.files);
    }
  };

  const handleError = (message: WebViewMessage) => {
    console.error('RevitPy error:', message.error);
    
    toast({
      title: 'RevitPy Error',
      description: message.error?.message || 'An unknown error occurred',
      variant: 'destructive'
    });
  };

  const contextValue: RevitPyContextType = {
    sendMessage,
    isConnected: connectionStatus === 'connected'
  };

  return (
    <RevitPyContext.Provider value={contextValue}>
      {children}
    </RevitPyContext.Provider>
  );
}

export function useRevitPy() {
  const context = useContext(RevitPyContext);
  if (!context) {
    throw new Error('useRevitPy must be used within a RevitPyProvider');
  }
  return context;
}

// Global type augmentation for RevitPy bridge
declare global {
  interface Window {
    revitpy?: {
      sendMessage: (message: any) => void;
      receiveMessage: (message: any) => void;
      dev: boolean;
      hotReload: boolean;
    };
    chrome?: {
      webview: {
        postMessage: (message: string) => void;
      };
    };
  }
}