import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '../../test/test-utils';
import { PerformanceChart } from './performance-chart';
import { mockPerformanceData } from '../../test/test-utils';

// Mock Recharts components
vi.mock('recharts', () => ({
  LineChart: ({ children, data }: any) => (
    <div data-testid="line-chart" data-chart-data={JSON.stringify(data)}>
      {children}
    </div>
  ),
  AreaChart: ({ children, data }: any) => (
    <div data-testid="area-chart" data-chart-data={JSON.stringify(data)}>
      {children}
    </div>
  ),
  Line: ({ dataKey }: any) => <div data-testid={`line-${dataKey}`} />,
  Area: ({ dataKey }: any) => <div data-testid={`area-${dataKey}`} />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  ResponsiveContainer: ({ children }: any) => (
    <div data-testid="responsive-container" style={{ width: '100%', height: 300 }}>
      {children}
    </div>
  ),
}));

describe('PerformanceChart', () => {
  const mockData = mockPerformanceData(10);

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('renders correctly with default props', () => {
    render(<PerformanceChart data={mockData} />);

    expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
    expect(screen.getByText('Real-time system performance monitoring')).toBeInTheDocument();
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
  });

  it('renders with line chart by default', () => {
    render(<PerformanceChart data={mockData} />);
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    expect(screen.queryByTestId('area-chart')).not.toBeInTheDocument();
  });

  it('renders with area chart when type is area', () => {
    render(<PerformPerfomanceChart data={mockData} type="area" />);
    expect(screen.getByTestId('area-chart')).toBeInTheDocument();
    expect(screen.queryByTestId('line-chart')).not.toBeInTheDocument();
  });

  it('shows metric tabs correctly', () => {
    render(<PerformanceChart data={mockData} />);

    expect(screen.getByRole('tab', { name: /memory/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /cpu/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /operations/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /response/i })).toBeInTheDocument();
  });

  it('switches between metrics when tabs are clicked', async () => {
    render(<PerformanceChart data={mockData} />);

    // Memory tab should be active by default
    expect(screen.getByTestId('line-memory')).toBeInTheDocument();

    // Click CPU tab
    fireEvent.click(screen.getByRole('tab', { name: /cpu/i }));
    await waitFor(() => {
      expect(screen.getByTestId('line-cpu')).toBeInTheDocument();
    });

    // Click Operations tab
    fireEvent.click(screen.getByRole('tab', { name: /operations/i }));
    await waitFor(() => {
      expect(screen.getByTestId('line-operations')).toBeInTheDocument();
    });
  });

  it('displays current and average values', () => {
    render(<PerformanceChart data={mockData} />);

    expect(screen.getByText('Current')).toBeInTheDocument();
    expect(screen.getByText('Average')).toBeInTheDocument();
  });

  it('formats values correctly for different metrics', () => {
    const specificData = [{
      timestamp: Date.now(),
      memory: 50.5,
      cpu: 75.8,
      operations: 1000,
      responseTime: 250
    }];

    render(<PerformanceChart data={specificData} />);

    // Check memory formatting (should show MB)
    expect(screen.getByText(/51MB/)).toBeInTheDocument();
  });

  it('shows live indicator when isLive is true', () => {
    render(<PerformanceChart data={mockData} />);

    const liveIndicator = screen.getByText('Live');
    expect(liveIndicator).toBeInTheDocument();
    expect(liveIndicator).toHaveClass('animate-pulse');
  });

  it('toggles live mode when clicked', async () => {
    render(<PerformanceChart data={mockData} />);

    const toggleButton = screen.getByText('Pause');
    fireEvent.click(toggleButton);

    await waitFor(() => {
      expect(screen.getByText('Resume')).toBeInTheDocument();
      expect(screen.getByText('Paused')).toBeInTheDocument();
    });
  });

  it('calls onRefresh when in live mode', async () => {
    const mockOnRefresh = vi.fn();
    render(
      <PerformanceChart
        data={mockData}
        onRefresh={mockOnRefresh}
        refreshInterval={1000}
      />
    );

    // Fast forward time
    vi.advanceTimersByTime(1000);

    await waitFor(() => {
      expect(mockOnRefresh).toHaveBeenCalled();
    });
  });

  it('stops refreshing when paused', async () => {
    const mockOnRefresh = vi.fn();
    render(
      <PerformanceChart
        data={mockData}
        onRefresh={mockOnRefresh}
        refreshInterval={1000}
      />
    );

    // Pause live mode
    fireEvent.click(screen.getByText('Pause'));

    // Fast forward time
    vi.advanceTimersByTime(2000);

    // Should not have called onRefresh after pausing
    expect(mockOnRefresh).not.toHaveBeenCalled();
  });

  it('filters data by time range', () => {
    const oldData = {
      timestamp: Date.now() - 15 * 60 * 1000, // 15 minutes ago
      memory: 30,
      cpu: 40,
      operations: 500,
      responseTime: 100
    };

    const recentData = {
      timestamp: Date.now() - 5 * 60 * 1000, // 5 minutes ago
      memory: 60,
      cpu: 80,
      operations: 1000,
      responseTime: 200
    };

    render(
      <PerformanceChart
        data={[oldData, recentData]}
        timeRange={10} // 10 minutes
      />
    );

    const chartElement = screen.getByTestId('line-chart');
    const chartData = JSON.parse(chartElement.getAttribute('data-chart-data') || '[]');

    // Should only include recent data (within 10 minutes)
    expect(chartData).toHaveLength(1);
    expect(chartData[0].memory).toBe(60);
  });

  it('renders with custom height', () => {
    render(<PerformanceChart data={mockData} height={500} />);

    const container = screen.getByTestId('responsive-container');
    expect(container).toHaveStyle({ height: '500px' });
  });

  it('shows grid when showGrid is true', () => {
    render(<PerformanceChart data={mockData} showGrid={true} />);
    expect(screen.getByTestId('grid')).toBeInTheDocument();
  });

  it('hides grid when showGrid is false', () => {
    render(<PerformanceChart data={mockData} showGrid={false} />);
    expect(screen.queryByTestId('grid')).not.toBeInTheDocument();
  });

  it('shows tooltip when showTooltip is true', () => {
    render(<PerformanceChart data={mockData} showTooltip={true} />);
    expect(screen.getByTestId('tooltip')).toBeInTheDocument();
  });

  it('hides tooltip when showTooltip is false', () => {
    render(<PerformanceChart data={mockData} showTooltip={false} />);
    expect(screen.queryByTestId('tooltip')).not.toBeInTheDocument();
  });

  it('passes through custom className', () => {
    render(<PerformanceChart data={mockData} className="custom-class" />);
    const container = screen.getByText('Performance Metrics').closest('.custom-class');
    expect(container).toBeInTheDocument();
  });

  it('forwards ref correctly', () => {
    const ref = vi.fn();
    render(<PerformanceChart data={mockData} ref={ref} />);
    expect(ref).toHaveBeenCalled();
  });

  describe('accessibility', () => {
    it('has proper ARIA labels for tabs', () => {
      render(<PerformanceChart data={mockData} />);

      const tabs = screen.getAllByRole('tab');
      tabs.forEach(tab => {
        expect(tab).toHaveAttribute('aria-selected');
      });
    });

    it('supports keyboard navigation between tabs', () => {
      render(<PerformanceChart data={mockData} />);

      const memoryTab = screen.getByRole('tab', { name: /memory/i });
      const cpuTab = screen.getByRole('tab', { name: /cpu/i });

      memoryTab.focus();
      expect(memoryTab).toHaveFocus();

      fireEvent.keyDown(memoryTab, { key: 'ArrowRight' });
      expect(cpuTab).toHaveFocus();
    });

    it('announces metric changes to screen readers', async () => {
      render(<PerformanceChart data={mockData} />);

      fireEvent.click(screen.getByRole('tab', { name: /cpu/i }));

      await waitFor(() => {
        const cpuTab = screen.getByRole('tab', { name: /cpu/i });
        expect(cpuTab).toHaveAttribute('aria-selected', 'true');
      });
    });
  });

  describe('data handling', () => {
    it('handles empty data gracefully', () => {
      render(<PerformanceChart data={[]} />);

      expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
      expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    });

    it('handles missing metric data gracefully', () => {
      const partialData = [{
        timestamp: Date.now(),
        memory: 50
        // cpu, operations, responseTime are missing
      }];

      render(<PerformanceChart data={partialData} />);

      expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
      // Should still render chart even with missing data
      expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    });

    it('calculates averages correctly', () => {
      const testData = [
        { timestamp: Date.now() - 2000, memory: 40 },
        { timestamp: Date.now() - 1000, memory: 50 },
        { timestamp: Date.now(), memory: 60 }
      ];

      render(<PerformanceChart data={testData} />);

      // Average should be (40 + 50 + 60) / 3 = 50MB
      expect(screen.getByText('50MB')).toBeInTheDocument();
    });
  });

  describe('performance', () => {
    it('does not re-render unnecessarily when data reference is the same', () => {
      const renderSpy = vi.fn();
      const TestComponent = () => {
        renderSpy();
        return <PerformanceChart data={mockData} />;
      };

      const { rerender } = render(<TestComponent />);
      expect(renderSpy).toHaveBeenCalledTimes(1);

      rerender(<TestComponent />);
      // Should not re-render if data reference hasn't changed
      expect(renderSpy).toHaveBeenCalledTimes(1);
    });

    it('cleans up intervals on unmount', () => {
      const mockOnRefresh = vi.fn();
      const { unmount } = render(
        <PerformanceChart
          data={mockData}
          onRefresh={mockOnRefresh}
          refreshInterval={1000}
        />
      );

      unmount();

      // Fast forward time after unmount
      vi.advanceTimersByTime(2000);

      // Should not call onRefresh after unmount
      expect(mockOnRefresh).not.toHaveBeenCalled();
    });
  });
});
