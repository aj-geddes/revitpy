import * as vscode from 'vscode';

export class RevitPyStatusBar implements vscode.Disposable {
    private connectionStatusItem: vscode.StatusBarItem;
    private packageStatusItem: vscode.StatusBarItem;

    constructor() {
        // Create connection status item
        this.connectionStatusItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Left,
            100
        );
        this.connectionStatusItem.command = 'revitpy.connectToRevit';
        this.connectionStatusItem.tooltip = 'RevitPy Connection Status';

        // Create package status item
        this.packageStatusItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Left,
            99
        );
        this.packageStatusItem.command = 'revitpy.openPackageManager';
        this.packageStatusItem.tooltip = 'RevitPy Package Manager';

        // Initialize with default states
        this.updateConnectionStatus(false);
        this.updatePackageStatus(0, 0);

        // Show items
        this.connectionStatusItem.show();
        this.packageStatusItem.show();
    }

    updateConnectionStatus(isConnected: boolean, revitVersion?: string): void {
        if (isConnected) {
            this.connectionStatusItem.text = `$(check) RevitPy${revitVersion ? ` (${revitVersion})` : ''}`;
            this.connectionStatusItem.backgroundColor = undefined;
            this.connectionStatusItem.command = 'revitpy.disconnectFromRevit';
            this.connectionStatusItem.tooltip = `Connected to Revit${revitVersion ? ` ${revitVersion}` : ''} - Click to disconnect`;
        } else {
            this.connectionStatusItem.text = '$(x) RevitPy Disconnected';
            this.connectionStatusItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
            this.connectionStatusItem.command = 'revitpy.connectToRevit';
            this.connectionStatusItem.tooltip = 'Not connected to Revit - Click to connect';
        }
    }

    updatePackageStatus(installed: number, available: number): void {
        this.packageStatusItem.text = `$(package) ${installed}/${available}`;
        this.packageStatusItem.tooltip = `${installed} packages installed, ${available} available - Click to open Package Manager`;
    }

    showMessage(message: string, type: 'info' | 'warning' | 'error' = 'info'): void {
        const icon = type === 'error' ? '$(error)' : type === 'warning' ? '$(warning)' : '$(info)';

        // Create temporary status item for messages
        const messageItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 98);
        messageItem.text = `${icon} ${message}`;
        messageItem.show();

        // Auto-hide after 5 seconds
        setTimeout(() => {
            messageItem.dispose();
        }, 5000);
    }

    dispose(): void {
        this.connectionStatusItem.dispose();
        this.packageStatusItem.dispose();
    }
}
