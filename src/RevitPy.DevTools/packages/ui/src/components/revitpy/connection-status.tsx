import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { Activity, Wifi, WifiOff, AlertTriangle, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';

const connectionStatusVariants = cva(
  'flex items-center space-x-2 px-3 py-2 rounded-lg',
  {
    variants: {
      status: {
        connected: 'bg-green-50 border border-green-200 text-green-800 dark:bg-green-900/20 dark:border-green-800 dark:text-green-300',
        connecting: 'bg-yellow-50 border border-yellow-200 text-yellow-800 dark:bg-yellow-900/20 dark:border-yellow-800 dark:text-yellow-300',
        disconnected: 'bg-gray-50 border border-gray-200 text-gray-600 dark:bg-gray-900/20 dark:border-gray-800 dark:text-gray-400',
        error: 'bg-red-50 border border-red-200 text-red-800 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300'
      },
      size: {
        default: 'text-sm',
        sm: 'text-xs',
        lg: 'text-base'
      }
    },
    defaultVariants: {
      status: 'disconnected',
      size: 'default'
    }
  }
);

export interface ConnectionStatusProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof connectionStatusVariants> {
  status: 'connected' | 'connecting' | 'disconnected' | 'error';
  revitVersion?: string;
  lastConnection?: Date;
  onConnect?: () => void;
  onDisconnect?: () => void;
  showActions?: boolean;
  detailed?: boolean;
}

const ConnectionStatus = React.forwardRef<HTMLDivElement, ConnectionStatusProps>(
  ({ 
    className, 
    status, 
    size,
    revitVersion, 
    lastConnection, 
    onConnect, 
    onDisconnect, 
    showActions = true,
    detailed = false,
    ...props 
  }, ref) => {
    const getStatusIcon = () => {
      switch (status) {
        case 'connected':
          return <Wifi className="h-4 w-4" />;
        case 'connecting':
          return <Loader2 className="h-4 w-4 animate-spin" />;
        case 'error':
          return <AlertTriangle className="h-4 w-4" />;
        default:
          return <WifiOff className="h-4 w-4" />;
      }
    };

    const getStatusText = () => {
      switch (status) {
        case 'connected':
          return revitVersion ? `Connected to Revit ${revitVersion}` : 'Connected to Revit';
        case 'connecting':
          return 'Connecting to Revit...';
        case 'error':
          return 'Connection Error';
        default:
          return 'Not Connected';
      }
    };

    const getStatusBadge = () => {
      switch (status) {
        case 'connected':
          return <Badge variant="default" className="bg-green-100 text-green-800">Online</Badge>;
        case 'connecting':
          return <Badge variant="secondary">Connecting</Badge>;
        case 'error':
          return <Badge variant="destructive">Error</Badge>;
        default:
          return <Badge variant="outline">Offline</Badge>;
      }
    };

    return (
      <div
        ref={ref}
        className={cn(connectionStatusVariants({ status, size }), className)}
        {...props}
      >
        <div className="flex items-center space-x-2">
          {getStatusIcon()}
          <span className="font-medium">{getStatusText()}</span>
          {getStatusBadge()}
        </div>

        {detailed && (
          <div className="ml-auto flex flex-col items-end text-xs opacity-70">
            {status === 'connected' && (
              <div className="flex items-center space-x-1">
                <Activity className="h-3 w-3" />
                <span>Live</span>
              </div>
            )}
            {lastConnection && status !== 'connected' && (
              <span>
                Last: {lastConnection.toLocaleTimeString()}
              </span>
            )}
          </div>
        )}

        {showActions && (
          <div className="ml-auto">
            {status === 'connected' ? (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={onDisconnect}
                      className="h-8 px-2"
                    >
                      Disconnect
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    Disconnect from Revit
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ) : (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={onConnect}
                      disabled={status === 'connecting'}
                      className="h-8 px-2"
                    >
                      {status === 'connecting' ? 'Connecting...' : 'Connect'}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    Connect to Revit
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
        )}
      </div>
    );
  }
);
ConnectionStatus.displayName = 'ConnectionStatus';

export { ConnectionStatus, connectionStatusVariants };