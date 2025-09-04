import { useQuery } from '@tanstack/react-query';
import { 
  Activity, 
  FolderOpen, 
  Package, 
  Zap, 
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Clock
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar
} from 'recharts';
import { useRevitPyStore } from '@/stores/revitpy';
import { useRevitPy } from '@/providers/revitpy-provider';

export default function Dashboard() {
  const { 
    runtime, 
    projects, 
    installedPackages, 
    performanceMetrics,
    connectionStatus 
  } = useRevitPyStore();
  const { sendMessage } = useRevitPy();

  // Fetch dashboard data
  const { data: dashboardData, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => {
      const response = await sendMessage({
        type: 'request',
        method: 'getDashboardData',
        id: '',
        timestamp: Date.now()
      });
      return response;
    },
    enabled: connectionStatus === 'connected',
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Mock performance data for charts
  const performanceData = [
    { time: '00:00', memory: 45, cpu: 12 },
    { time: '00:05', memory: 52, cpu: 18 },
    { time: '00:10', memory: 48, cpu: 15 },
    { time: '00:15', memory: 61, cpu: 25 },
    { time: '00:20', memory: 55, cpu: 20 },
    { time: '00:25', memory: 58, cpu: 22 },
  ];

  const recentActivity = [
    { id: 1, action: 'Project created', item: 'Wall Automation Tool', time: '2 minutes ago', type: 'create' },
    { id: 2, action: 'Package installed', item: 'pandas v2.1.0', time: '15 minutes ago', type: 'install' },
    { id: 3, action: 'Script executed', item: 'Room Data Export', time: '32 minutes ago', type: 'execute' },
    { id: 4, action: 'Debug session', item: 'Door Placement Script', time: '1 hour ago', type: 'debug' },
  ];

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'create': return <FolderOpen className="h-4 w-4" />;
      case 'install': return <Package className="h-4 w-4" />;
      case 'execute': return <Zap className="h-4 w-4" />;
      case 'debug': return <Activity className="h-4 w-4" />;
      default: return <Activity className="h-4 w-4" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'text-green-600';
      case 'connecting': return 'text-yellow-600';
      case 'error': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex items-center space-x-2">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <span>Loading dashboard...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome to your RevitPy development environment
        </p>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Connection Status</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-2">
              <div 
                className={`status-dot ${
                  connectionStatus === 'connected' ? 'status-online' :
                  connectionStatus === 'connecting' ? 'status-warning' :
                  'status-error'
                }`}
              />
              <span className={`text-lg font-bold capitalize ${getStatusColor(connectionStatus)}`}>
                {connectionStatus}
              </span>
            </div>
            {runtime && (
              <p className="text-xs text-muted-foreground">
                Python {runtime.pythonVersion} • Revit {runtime.revitVersion}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Projects</CardTitle>
            <FolderOpen className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{projects.length}</div>
            <p className="text-xs text-muted-foreground">
              {projects.filter(p => p.status === 'active').length} running
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Installed Packages</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{installedPackages.length}</div>
            <p className="text-xs text-muted-foreground">
              {installedPackages.filter(p => p.status === 'active').length} active
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Memory Usage</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {performanceMetrics ? 
                `${Math.round(performanceMetrics.memoryUsage / 1024 / 1024)}MB` : 
                'N/A'
              }
            </div>
            <Progress 
              value={performanceMetrics ? (performanceMetrics.memoryUsage / 1024 / 1024 / 512) * 100 : 0} 
              className="mt-2" 
            />
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Performance Charts */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Performance Metrics</CardTitle>
              <CardDescription>
                Real-time system resource usage
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="memory" className="space-y-4">
                <TabsList>
                  <TabsTrigger value="memory">Memory</TabsTrigger>
                  <TabsTrigger value="cpu">CPU</TabsTrigger>
                </TabsList>
                
                <TabsContent value="memory" className="space-y-4">
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={performanceData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="time" />
                        <YAxis />
                        <Tooltip />
                        <Line 
                          type="monotone" 
                          dataKey="memory" 
                          stroke="hsl(var(--primary))" 
                          strokeWidth={2}
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </TabsContent>
                
                <TabsContent value="cpu" className="space-y-4">
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={performanceData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="time" />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="cpu" fill="hsl(var(--primary))" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>

        {/* Recent Activity */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>
                Latest actions and events
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {recentActivity.map((activity) => (
                <div key={activity.id} className="flex items-center space-x-3">
                  <div className="flex-shrink-0">
                    {getActivityIcon(activity.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      {activity.action}
                    </p>
                    <p className="text-sm text-muted-foreground truncate">
                      {activity.item}
                    </p>
                  </div>
                  <div className="flex-shrink-0 text-xs text-muted-foreground">
                    {activity.time}
                  </div>
                </div>
              ))}
              
              <Button variant="outline" className="w-full mt-4">
                View All Activity
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>
            Common tasks to get started
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Button variant="outline" className="h-24 flex-col space-y-2">
              <FolderOpen className="h-6 w-6" />
              <span>New Project</span>
            </Button>
            
            <Button variant="outline" className="h-24 flex-col space-y-2">
              <Package className="h-6 w-6" />
              <span>Browse Packages</span>
            </Button>
            
            <Button variant="outline" className="h-24 flex-col space-y-2">
              <Zap className="h-6 w-6" />
              <span>Open REPL</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* System Health */}
      {runtime && (
        <Card>
          <CardHeader>
            <CardTitle>System Health</CardTitle>
            <CardDescription>
              Runtime status and diagnostics
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex items-center space-x-3">
                <CheckCircle className="h-5 w-5 text-green-500" />
                <div>
                  <p className="text-sm font-medium">Runtime Status</p>
                  <p className="text-sm text-muted-foreground">Healthy</p>
                </div>
              </div>
              
              <div className="flex items-center space-x-3">
                <Clock className="h-5 w-5 text-blue-500" />
                <div>
                  <p className="text-sm font-medium">Uptime</p>
                  <p className="text-sm text-muted-foreground">
                    {Math.floor(runtime.uptime / 3600)}h {Math.floor((runtime.uptime % 3600) / 60)}m
                  </p>
                </div>
              </div>
              
              <div className="flex items-center space-x-3">
                <Activity className="h-5 w-5 text-purple-500" />
                <div>
                  <p className="text-sm font-medium">Process ID</p>
                  <p className="text-sm text-muted-foreground">{runtime.processId}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}