import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '../../test/test-utils';
import { ConnectionStatus } from './connection-status';

describe('ConnectionStatus', () => {
  it('renders correctly with disconnected status', () => {
    render(<ConnectionStatus status="disconnected" />);

    expect(screen.getByText('Not Connected')).toBeInTheDocument();
    expect(screen.getByText('Offline')).toBeInTheDocument();
  });

  it('renders correctly with connected status', () => {
    render(<ConnectionStatus status="connected" revitVersion="2024" />);

    expect(screen.getByText('Connected to Revit 2024')).toBeInTheDocument();
    expect(screen.getByText('Online')).toBeInTheDocument();
  });

  it('renders correctly with connecting status', () => {
    render(<ConnectionStatus status="connecting" />);

    expect(screen.getByText('Connecting to Revit...')).toBeInTheDocument();
    expect(screen.getByText('Connecting')).toBeInTheDocument();

    // Should show loading spinner
    expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument();
  });

  it('renders correctly with error status', () => {
    render(<ConnectionStatus status="error" />);

    expect(screen.getByText('Connection Error')).toBeInTheDocument();
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('shows correct icons for each status', () => {
    const { rerender } = render(<ConnectionStatus status="connected" />);
    expect(screen.getByTestId('wifi-icon')).toBeInTheDocument();

    rerender(<ConnectionStatus status="disconnected" />);
    expect(screen.getByTestId('wifi-off-icon')).toBeInTheDocument();

    rerender(<ConnectionStatus status="connecting" />);
    expect(screen.getByTestId('loader-icon')).toBeInTheDocument();

    rerender(<ConnectionStatus status="error" />);
    expect(screen.getByTestId('alert-triangle-icon')).toBeInTheDocument();
  });

  it('applies correct styling for each status', () => {
    const { rerender } = render(<ConnectionStatus status="connected" />);
    let container = screen.getByText('Connected to Revit').closest('div');
    expect(container).toHaveClass('bg-green-50', 'text-green-800');

    rerender(<ConnectionStatus status="error" />);
    container = screen.getByText('Connection Error').closest('div');
    expect(container).toHaveClass('bg-red-50', 'text-red-800');

    rerender(<ConnectionStatus status="connecting" />);
    container = screen.getByText('Connecting to Revit...').closest('div');
    expect(container).toHaveClass('bg-yellow-50', 'text-yellow-800');

    rerender(<ConnectionStatus status="disconnected" />);
    container = screen.getByText('Not Connected').closest('div');
    expect(container).toHaveClass('bg-gray-50', 'text-gray-600');
  });

  it('shows connect button when disconnected', () => {
    const onConnect = vi.fn();
    render(
      <ConnectionStatus
        status="disconnected"
        onConnect={onConnect}
        showActions={true}
      />
    );

    const connectButton = screen.getByRole('button', { name: 'Connect' });
    expect(connectButton).toBeInTheDocument();

    fireEvent.click(connectButton);
    expect(onConnect).toHaveBeenCalledTimes(1);
  });

  it('shows disconnect button when connected', () => {
    const onDisconnect = vi.fn();
    render(
      <ConnectionStatus
        status="connected"
        onDisconnect={onDisconnect}
        showActions={true}
      />
    );

    const disconnectButton = screen.getByRole('button', { name: 'Disconnect' });
    expect(disconnectButton).toBeInTheDocument();

    fireEvent.click(disconnectButton);
    expect(onDisconnect).toHaveBeenCalledTimes(1);
  });

  it('disables connect button when connecting', () => {
    render(
      <ConnectionStatus
        status="connecting"
        onConnect={vi.fn()}
        showActions={true}
      />
    );

    const connectingButton = screen.getByRole('button', { name: 'Connecting...' });
    expect(connectingButton).toBeDisabled();
  });

  it('hides actions when showActions is false', () => {
    render(
      <ConnectionStatus
        status="disconnected"
        onConnect={vi.fn()}
        showActions={false}
      />
    );

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('shows detailed information when detailed is true', () => {
    const lastConnection = new Date('2024-01-01T12:00:00Z');

    render(
      <ConnectionStatus
        status="disconnected"
        lastConnection={lastConnection}
        detailed={true}
      />
    );

    expect(screen.getByText(/Last:/)).toBeInTheDocument();
  });

  it('shows live indicator when connected and detailed', () => {
    render(
      <ConnectionStatus
        status="connected"
        detailed={true}
      />
    );

    expect(screen.getByText('Live')).toBeInTheDocument();
    expect(screen.getByTestId('activity-icon')).toBeInTheDocument();
  });

  it('supports different sizes', () => {
    const { rerender } = render(<ConnectionStatus status="connected" size="sm" />);
    let container = screen.getByText('Connected to Revit').closest('div');
    expect(container).toHaveClass('text-xs');

    rerender(<ConnectionStatus status="connected" size="lg" />);
    container = screen.getByText('Connected to Revit').closest('div');
    expect(container).toHaveClass('text-base');
  });

  it('passes through custom className', () => {
    render(<ConnectionStatus status="connected" className="custom-class" />);
    const container = screen.getByText('Connected to Revit').closest('div');
    expect(container).toHaveClass('custom-class');
  });

  it('forwards ref correctly', () => {
    const ref = vi.fn();
    render(<ConnectionStatus status="connected" ref={ref} />);
    expect(ref).toHaveBeenCalled();
  });

  describe('accessibility', () => {
    it('provides appropriate tooltips', () => {
      render(
        <ConnectionStatus
          status="connected"
          onDisconnect={vi.fn()}
          showActions={true}
        />
      );

      const button = screen.getByRole('button', { name: 'Disconnect' });
      fireEvent.mouseEnter(button);

      expect(screen.getByText('Disconnect from Revit')).toBeInTheDocument();
    });

    it('has appropriate ARIA labels', () => {
      render(<ConnectionStatus status="connected" />);

      const statusContainer = screen.getByText('Connected to Revit').closest('div');
      expect(statusContainer).toHaveAttribute('role', 'status');
    });

    it('announces status changes to screen readers', () => {
      const { rerender } = render(<ConnectionStatus status="disconnected" />);

      rerender(<ConnectionStatus status="connecting" />);
      expect(screen.getByText('Connecting to Revit...')).toBeInTheDocument();

      rerender(<ConnectionStatus status="connected" />);
      expect(screen.getByText('Connected to Revit')).toBeInTheDocument();
    });

    it('supports keyboard navigation for action buttons', () => {
      const onConnect = vi.fn();
      render(
        <ConnectionStatus
          status="disconnected"
          onConnect={onConnect}
          showActions={true}
        />
      );

      const button = screen.getByRole('button', { name: 'Connect' });
      button.focus();
      expect(button).toHaveFocus();

      fireEvent.keyDown(button, { key: 'Enter' });
      expect(onConnect).toHaveBeenCalledTimes(1);
    });
  });

  describe('edge cases', () => {
    it('handles missing Revit version gracefully', () => {
      render(<ConnectionStatus status="connected" />);
      expect(screen.getByText('Connected to Revit')).toBeInTheDocument();
    });

    it('handles missing callback functions gracefully', () => {
      render(<ConnectionStatus status="connected" showActions={true} />);

      // Should not crash and should still render the button
      expect(screen.getByRole('button', { name: 'Disconnect' })).toBeInTheDocument();
    });

    it('handles undefined lastConnection gracefully', () => {
      render(
        <ConnectionStatus
          status="disconnected"
          detailed={true}
          lastConnection={undefined}
        />
      );

      expect(screen.queryByText(/Last:/)).not.toBeInTheDocument();
    });
  });
});
