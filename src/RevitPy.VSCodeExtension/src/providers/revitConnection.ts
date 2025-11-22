import * as vscode from 'vscode';
import * as WebSocket from 'ws';
import { EventEmitter } from 'events';

interface RevitConnectionInfo {
    status: 'connected' | 'connecting' | 'disconnected' | 'error';
    version?: string;
    processId?: number;
    lastActivity?: Date;
}

export class RevitConnection extends EventEmitter implements vscode.TreeDataProvider<ConnectionItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<ConnectionItem | undefined | null | void> = new vscode.EventEmitter<ConnectionItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<ConnectionItem | undefined | null | void> = this._onDidChangeTreeData.event;

    private ws: WebSocket | null = null;
    private connectionInfo: RevitConnectionInfo;
    private reconnectTimer: NodeJS.Timer | null = null;
    private heartbeatTimer: NodeJS.Timer | null = null;

    constructor(private context: vscode.ExtensionContext) {
        super();
        this.connectionInfo = { status: 'disconnected' };

        // Listen for configuration changes
        vscode.workspace.onDidChangeConfiguration(e => {
            if (e.affectsConfiguration('revitpy.debugPort')) {
                this.reconnectIfNeeded();
            }
        });
    }

    getTreeItem(element: ConnectionItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: ConnectionItem): ConnectionItem[] {
        if (!element) {
            return this.getRootItems();
        }
        return [];
    }

    private getRootItems(): ConnectionItem[] {
        const items: ConnectionItem[] = [];

        // Connection status
        items.push(new ConnectionItem(
            `Status: ${this.connectionInfo.status}`,
            vscode.TreeItemCollapsibleState.None,
            {
                command: 'revitpy.refreshConnection',
                title: 'Refresh Connection'
            },
            this.getStatusIcon()
        ));

        if (this.connectionInfo.status === 'connected') {
            if (this.connectionInfo.version) {
                items.push(new ConnectionItem(
                    `Version: ${this.connectionInfo.version}`,
                    vscode.TreeItemCollapsibleState.None
                ));
            }

            if (this.connectionInfo.processId) {
                items.push(new ConnectionItem(
                    `Process ID: ${this.connectionInfo.processId}`,
                    vscode.TreeItemCollapsibleState.None
                ));
            }

            if (this.connectionInfo.lastActivity) {
                items.push(new ConnectionItem(
                    `Last Activity: ${this.connectionInfo.lastActivity.toLocaleTimeString()}`,
                    vscode.TreeItemCollapsibleState.None
                ));
            }

            // Action items when connected
            items.push(new ConnectionItem(
                'Disconnect',
                vscode.TreeItemCollapsibleState.None,
                {
                    command: 'revitpy.disconnectFromRevit',
                    title: 'Disconnect from Revit'
                },
                new vscode.ThemeIcon('plug', new vscode.ThemeColor('errorForeground'))
            ));
        } else {
            // Action items when disconnected
            items.push(new ConnectionItem(
                'Connect',
                vscode.TreeItemCollapsibleState.None,
                {
                    command: 'revitpy.connectToRevit',
                    title: 'Connect to Revit'
                },
                new vscode.ThemeIcon('plug', new vscode.ThemeColor('charts.green'))
            ));
        }

        return items;
    }

    private getStatusIcon(): vscode.ThemeIcon {
        switch (this.connectionInfo.status) {
            case 'connected':
                return new vscode.ThemeIcon('circle-filled', new vscode.ThemeColor('charts.green'));
            case 'connecting':
                return new vscode.ThemeIcon('sync~spin', new vscode.ThemeColor('charts.yellow'));
            case 'error':
                return new vscode.ThemeIcon('error', new vscode.ThemeColor('errorForeground'));
            default:
                return new vscode.ThemeIcon('circle-outline', new vscode.ThemeColor('descriptionForeground'));
        }
    }

    async connect(): Promise<void> {
        if (this.ws?.readyState === WebSocket.OPEN) {
            vscode.window.showInformationMessage('Already connected to Revit');
            return;
        }

        const config = vscode.workspace.getConfiguration('revitpy');
        const port = config.get<number>('debugPort', 5678);

        try {
            this.updateStatus('connecting');

            this.ws = new WebSocket(`ws://localhost:${port}`);

            this.ws.on('open', () => {
                this.onConnected();
                this.startHeartbeat();
            });

            this.ws.on('message', (data: WebSocket.Data) => {
                this.handleMessage(data.toString());
            });

            this.ws.on('close', () => {
                this.onDisconnected();
                this.scheduleReconnect();
            });

            this.ws.on('error', (error) => {
                this.onError(error);
            });

        } catch (error) {
            this.onError(error as Error);
            vscode.window.showErrorMessage(`Failed to connect to Revit: ${error}`);
        }
    }

    async disconnect(): Promise<void> {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        this.stopHeartbeat();
        this.stopReconnect();
        this.updateStatus('disconnected');

        vscode.window.showInformationMessage('Disconnected from Revit');
    }

    async executeScript(scriptPath: string): Promise<any> {
        return new Promise((resolve, reject) => {
            if (!this.isConnected()) {
                reject(new Error('Not connected to Revit'));
                return;
            }

            const message = {
                type: 'execute_script',
                script_path: scriptPath,
                id: this.generateMessageId()
            };

            const timeout = setTimeout(() => {
                reject(new Error('Script execution timeout'));
            }, 30000);

            const messageHandler = (response: any) => {
                if (response.id === message.id) {
                    clearTimeout(timeout);
                    this.off('message', messageHandler);

                    if (response.success) {
                        resolve(response.result);
                    } else {
                        reject(new Error(response.error || 'Script execution failed'));
                    }
                }
            };

            this.on('message', messageHandler);
            this.sendMessage(message);
        });
    }

    isConnected(): boolean {
        return this.connectionInfo.status === 'connected';
    }

    autoConnect(): void {
        // Try to connect automatically
        this.connect().catch(() => {
            // Silently fail for auto-connect
        });
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    private onConnected(): void {
        this.updateStatus('connected');
        this.stopReconnect();

        // Request Revit info
        this.sendMessage({
            type: 'get_info',
            id: this.generateMessageId()
        });

        vscode.commands.executeCommand('setContext', 'revitpy:connected', true);
        vscode.window.showInformationMessage('Connected to Revit successfully');

        this.emit('connected');
    }

    private onDisconnected(): void {
        this.updateStatus('disconnected');
        this.connectionInfo.version = undefined;
        this.connectionInfo.processId = undefined;
        this.connectionInfo.lastActivity = undefined;

        vscode.commands.executeCommand('setContext', 'revitpy:connected', false);

        this.emit('disconnected');
    }

    private onError(error: Error): void {
        console.error('RevitPy connection error:', error);
        this.updateStatus('error');
        this.emit('error', error);
    }

    private handleMessage(data: string): void {
        try {
            const message = JSON.parse(data);
            this.connectionInfo.lastActivity = new Date();

            switch (message.type) {
                case 'info_response':
                    this.connectionInfo.version = message.revit_version;
                    this.connectionInfo.processId = message.process_id;
                    break;

                case 'heartbeat':
                    // Update last activity
                    break;

                case 'error':
                    vscode.window.showErrorMessage(`Revit error: ${message.message}`);
                    break;

                case 'log':
                    // Handle log messages
                    console.log(`Revit: ${message.message}`);
                    break;
            }

            this.emit('message', message);
            this.refresh();

        } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
        }
    }

    private sendMessage(message: any): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }

    private updateStatus(status: RevitConnectionInfo['status']): void {
        this.connectionInfo.status = status;
        this.refresh();
    }

    private startHeartbeat(): void {
        this.heartbeatTimer = setInterval(() => {
            this.sendMessage({
                type: 'heartbeat',
                timestamp: Date.now()
            });
        }, 10000); // Every 10 seconds
    }

    private stopHeartbeat(): void {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    private scheduleReconnect(): void {
        if (this.reconnectTimer) return;

        const config = vscode.workspace.getConfiguration('revitpy');
        if (config.get('autoConnect', true)) {
            this.reconnectTimer = setTimeout(() => {
                this.reconnectTimer = null;
                this.connect().catch(() => {
                    // Retry after another delay
                    this.scheduleReconnect();
                });
            }, 5000); // Retry after 5 seconds
        }
    }

    private stopReconnect(): void {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }

    private reconnectIfNeeded(): void {
        if (this.isConnected()) {
            this.disconnect().then(() => {
                setTimeout(() => this.connect(), 1000);
            });
        }
    }

    private generateMessageId(): string {
        return Math.random().toString(36).substr(2, 9);
    }
}

class ConnectionItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly command?: vscode.Command,
        public readonly iconPath?: vscode.ThemeIcon
    ) {
        super(label, collapsibleState);
        this.tooltip = label;
        this.contextValue = 'connectionItem';
    }
}
