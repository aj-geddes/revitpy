import * as React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { Activity, Cpu, HardDrive, Zap } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';

export interface PerformanceDataPoint {
  timestamp: number;
  memory?: number;
  cpu?: number;
  operations?: number;
  responseTime?: number;
}

export interface PerformanceChartProps extends React.HTMLAttributes<HTMLDivElement> {
  data: PerformanceDataPoint[];
  type?: 'line' | 'area';
  showGrid?: boolean;
  showTooltip?: boolean;
  height?: number;
  timeRange?: number; // in minutes
  refreshInterval?: number; // in ms
  onRefresh?: () => void;
}

const PerformanceChart = React.forwardRef<HTMLDivElement, PerformanceChartProps>(
  ({ 
    className, 
    data, 
    type = 'line',
    showGrid = true,
    showTooltip = true,
    height = 300,
    timeRange = 10,
    refreshInterval = 5000,
    onRefresh,
    ...props 
  }, ref) => {
    const [selectedMetric, setSelectedMetric] = React.useState<string>('memory');
    const [isLive, setIsLive] = React.useState(true);

    // Auto-refresh data
    React.useEffect(() => {
      if (!isLive || !onRefresh) return;

      const interval = setInterval(() => {
        onRefresh();
      }, refreshInterval);

      return () => clearInterval(interval);
    }, [isLive, onRefresh, refreshInterval]);

    // Filter data by time range
    const filteredData = React.useMemo(() => {
      const cutoff = Date.now() - (timeRange * 60 * 1000);
      return data.filter(point => point.timestamp >= cutoff);
    }, [data, timeRange]);

    const formatTimestamp = (timestamp: number) => {
      return new Date(timestamp).toLocaleTimeString('en-US', { 
        hour12: false,
        minute: '2-digit',
        second: '2-digit'
      });
    };

    const formatValue = (value: number, metric: string) => {
      switch (metric) {
        case 'memory':
          return `${Math.round(value)}MB`;
        case 'cpu':
          return `${value.toFixed(1)}%`;
        case 'operations':
          return `${value}/s`;
        case 'responseTime':
          return `${value}ms`;
        default:
          return value.toString();
      }
    };

    const getMetricColor = (metric: string) => {
      switch (metric) {
        case 'memory':
          return 'hsl(var(--chart-1))';
        case 'cpu':
          return 'hsl(var(--chart-2))';
        case 'operations':
          return 'hsl(var(--chart-3))';
        case 'responseTime':
          return 'hsl(var(--chart-4))';
        default:
          return 'hsl(var(--primary))';
      }
    };

    const getCurrentValue = (metric: string) => {
      const latest = filteredData[filteredData.length - 1];
      if (!latest) return 0;
      return latest[metric as keyof PerformanceDataPoint] || 0;
    };

    const getAverageValue = (metric: string) => {
      if (filteredData.length === 0) return 0;
      const sum = filteredData.reduce((acc, point) => {
        return acc + (point[metric as keyof PerformanceDataPoint] || 0);
      }, 0);
      return sum / filteredData.length;
    };

    const getStatusColor = (value: number, metric: string) => {
      switch (metric) {
        case 'memory':
          return value > 80 ? 'destructive' : value > 60 ? 'secondary' : 'default';
        case 'cpu':
          return value > 80 ? 'destructive' : value > 60 ? 'secondary' : 'default';
        default:
          return 'default';
      }
    };

    const ChartComponent = type === 'area' ? AreaChart : LineChart;

    return (
      <div ref={ref} className={cn('w-full', className)} {...props}>
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center space-x-2">
                  <Activity className="h-5 w-5" />
                  <span>Performance Metrics</span>
                </CardTitle>
                <CardDescription>
                  Real-time system performance monitoring
                </CardDescription>
              </div>
              
              <div className="flex items-center space-x-2">
                <Badge 
                  variant={isLive ? 'default' : 'outline'}
                  className={isLive ? 'animate-pulse' : ''}
                >
                  {isLive ? 'Live' : 'Paused'}
                </Badge>
                
                <button
                  onClick={() => setIsLive(!isLive)}
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  {isLive ? 'Pause' : 'Resume'}
                </button>
              </div>
            </div>
          </CardHeader>
          
          <CardContent>
            <Tabs value={selectedMetric} onValueChange={setSelectedMetric}>
              <div className="flex items-center justify-between mb-4">
                <TabsList className="grid w-full grid-cols-4">
                  <TabsTrigger value="memory" className="flex items-center space-x-1">
                    <HardDrive className="h-3 w-3" />
                    <span>Memory</span>
                  </TabsTrigger>
                  <TabsTrigger value="cpu" className="flex items-center space-x-1">
                    <Cpu className="h-3 w-3" />
                    <span>CPU</span>
                  </TabsTrigger>
                  <TabsTrigger value="operations" className="flex items-center space-x-1">
                    <Zap className="h-3 w-3" />
                    <span>Operations</span>
                  </TabsTrigger>
                  <TabsTrigger value="responseTime" className="flex items-center space-x-1">
                    <Activity className="h-3 w-3" />
                    <span>Response</span>
                  </TabsTrigger>
                </TabsList>
                
                <div className="flex items-center space-x-4 text-sm">
                  <div className="text-center">
                    <div className="text-muted-foreground">Current</div>
                    <Badge variant={getStatusColor(getCurrentValue(selectedMetric), selectedMetric)}>
                      {formatValue(getCurrentValue(selectedMetric), selectedMetric)}
                    </Badge>
                  </div>
                  <div className="text-center">
                    <div className="text-muted-foreground">Average</div>
                    <div className="font-medium">
                      {formatValue(getAverageValue(selectedMetric), selectedMetric)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Chart for each metric */}
              {['memory', 'cpu', 'operations', 'responseTime'].map((metric) => (
                <TabsContent key={metric} value={metric} className="mt-0">
                  <div style={{ width: '100%', height }}>
                    <ResponsiveContainer>
                      <ChartComponent data={filteredData}>
                        {showGrid && <CartesianGrid strokeDasharray="3 3" />}
                        <XAxis 
                          dataKey="timestamp"
                          tickFormatter={formatTimestamp}
                          type="number"
                          scale="time"
                          domain={['dataMin', 'dataMax']}
                        />
                        <YAxis 
                          tickFormatter={(value) => formatValue(value, metric)}
                        />
                        {showTooltip && (
                          <Tooltip
                            labelFormatter={(timestamp) => formatTimestamp(timestamp as number)}
                            formatter={(value: number) => [
                              formatValue(value, metric),
                              metric.charAt(0).toUpperCase() + metric.slice(1)
                            ]}
                          />
                        )}
                        
                        {type === 'area' ? (
                          <Area
                            type="monotone"
                            dataKey={metric}
                            stroke={getMetricColor(metric)}
                            fill={getMetricColor(metric)}
                            fillOpacity={0.1}
                            strokeWidth={2}
                            dot={false}
                          />
                        ) : (
                          <Line
                            type="monotone"
                            dataKey={metric}
                            stroke={getMetricColor(metric)}
                            strokeWidth={2}
                            dot={false}
                          />
                        )}
                      </ChartComponent>
                    </ResponsiveContainer>
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          </CardContent>
        </Card>
      </div>
    );
  }
);
PerformanceChart.displayName = 'PerformanceChart';

export { PerformanceChart };