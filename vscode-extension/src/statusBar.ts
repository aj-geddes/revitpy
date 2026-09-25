import * as vscode from 'vscode';
import type { ConnectionManager, ConnectionState } from './connection';
import { statusBarText } from './format';
import type { LiveStatus } from './protocol';

/** Status bar item: Revit version and active document while connected. */
export class RevitStatusBar implements vscode.Disposable {
  private readonly item: vscode.StatusBarItem;
  private readonly onChange = (): void => this.render();

  constructor(private readonly connection: ConnectionManager) {
    this.item = vscode.window.createStatusBarItem('revitpy.connection', vscode.StatusBarAlignment.Left, 50);
    this.item.name = 'RevitPy Connection';
    connection.on('stateChanged', this.onChange);
    connection.on('statusChanged', this.onChange);
    this.render();
    this.item.show();
  }

  render(): void {
    const state: ConnectionState = this.connection.state;
    const status: LiveStatus | undefined = this.connection.status;
    if (state === 'connecting') {
      this.item.text = '$(sync~spin) Revit';
      this.item.tooltip = 'Connecting to the RevitPy Live Server…';
      this.item.command = undefined;
      return;
    }
    const connected = this.connection.isConnected;
    this.item.text = statusBarText(status, connected);
    if (connected) {
      const lines = [`RevitPy Live Server: ${this.connection.info?.url ?? ''}`];
      if (status) {
        lines.push(
          `Revit ${status.revit_version ?? '?'} · ${status.document ?? 'no active document'}`,
          `RevitPy ${status.revitpy_version} · Python ${status.python_version}`,
        );
        if (status.debug.listening) {
          lines.push(`debugpy listening on port ${status.debug.port}`);
        }
      }
      lines.push('Click for details.');
      this.item.tooltip = lines.join('\n');
      this.item.command = 'revitpy.showStatus';
    } else {
      this.item.tooltip = 'Not connected to Revit. Click to connect to the RevitPy Live Server.';
      this.item.command = 'revitpy.connect';
    }
  }

  dispose(): void {
    this.connection.off('stateChanged', this.onChange);
    this.connection.off('statusChanged', this.onChange);
    this.item.dispose();
  }
}
