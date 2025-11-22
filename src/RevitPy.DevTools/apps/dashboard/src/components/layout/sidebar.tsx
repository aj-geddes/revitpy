import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FolderOpen,
  Package,
  Terminal,
  Activity,
  Settings,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  Zap
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { useRevitPyStore } from '@/stores/revitpy';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Projects', href: '/projects', icon: FolderOpen },
  { name: 'Packages', href: '/packages', icon: Package },
  { name: 'REPL', href: '/repl', icon: Terminal },
  { name: 'Monitoring', href: '/monitoring', icon: Activity },
];

const bottomNavigation = [
  { name: 'Settings', href: '/settings', icon: Settings },
  { name: 'Help', href: '/help', icon: HelpCircle },
];

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { connectionStatus } = useRevitPyStore();

  return (
    <div
      className={cn(
        'fixed left-0 top-0 z-40 h-screen bg-card border-r border-border transition-all duration-300',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Header */}
      <div className="flex h-16 items-center justify-between px-4 border-b border-border">
        {!collapsed && (
          <div className="flex items-center space-x-2">
            <Zap className="h-6 w-6 text-primary" />
            <span className="text-lg font-semibold">RevitPy</span>
          </div>
        )}

        <Button
          variant="ghost"
          size="sm"
          onClick={onToggle}
          className="h-8 w-8 p-0"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      {/* Connection Status */}
      <div className={cn('p-4 border-b border-border', collapsed && 'px-2')}>
        <div className={cn('flex items-center space-x-3', collapsed && 'justify-center')}>
          <div
            className={cn(
              'status-dot',
              connectionStatus === 'connected' && 'status-online',
              connectionStatus === 'disconnected' && 'status-offline',
              connectionStatus === 'error' && 'status-error',
              connectionStatus === 'connecting' && 'status-warning'
            )}
          />
          {!collapsed && (
            <div>
              <p className="text-sm font-medium capitalize">{connectionStatus}</p>
              <p className="text-xs text-muted-foreground">
                {connectionStatus === 'connected' ? 'Revit 2024' : 'Not connected'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navigation.map((item) => {
          const IconComponent = item.icon;
          const content = (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  'flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  'hover:bg-accent hover:text-accent-foreground',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground',
                  collapsed ? 'justify-center' : 'space-x-3'
                )
              }
            >
              <IconComponent className="h-5 w-5 flex-shrink-0" />
              {!collapsed && <span>{item.name}</span>}
            </NavLink>
          );

          if (collapsed) {
            return (
              <Tooltip key={item.name} delayDuration={0}>
                <TooltipTrigger asChild>
                  {content}
                </TooltipTrigger>
                <TooltipContent side="right">
                  {item.name}
                </TooltipContent>
              </Tooltip>
            );
          }

          return content;
        })}
      </nav>

      {/* Bottom Navigation */}
      <div className="p-4 border-t border-border space-y-1">
        {bottomNavigation.map((item) => {
          const IconComponent = item.icon;
          const content = (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  'flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  'hover:bg-accent hover:text-accent-foreground',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground',
                  collapsed ? 'justify-center' : 'space-x-3'
                )
              }
            >
              <IconComponent className="h-5 w-5 flex-shrink-0" />
              {!collapsed && <span>{item.name}</span>}
            </NavLink>
          );

          if (collapsed) {
            return (
              <Tooltip key={item.name} delayDuration={0}>
                <TooltipTrigger asChild>
                  {content}
                </TooltipTrigger>
                <TooltipContent side="right">
                  {item.name}
                </TooltipContent>
              </Tooltip>
            );
          }

          return content;
        })}
      </div>
    </div>
  );
}
