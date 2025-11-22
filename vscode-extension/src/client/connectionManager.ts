import * as vscode from 'vscode';
import * as WebSocket from 'ws';
import { Logger } from '../common/logger';
import { RevitConnection, ScriptExecutionResult, HotReloadEvent } from '../common/types';

export class RevitPyConnectionManager implements vscode.Disposable {
    private websocket?: WebSocket;
    private connection: RevitConnection;
    private reconnectTimer?: NodeJS.Timer;
    private readonly maxReconnectAttempts = 5;
    private reconnectAttempts = 0;
    private hotReloadEnabled = true;

    private readonly onConnectionChangedEmitter = new vscode.EventEmitter<boolean>();
    public readonly onConnectionChanged = this.onConnectionChangedEmitter.event;

    private readonly onHotReloadEventEmitter = new vscode.EventEmitter<HotReloadEvent>();
    public readonly onHotReloadEvent = this.onHotReloadEventEmitter.event;

    constructor(private logger: Logger) {
        const config = vscode.workspace.getConfiguration('revitpy');
        this.connection = {
            host: config.get<string>('host', 'localhost'),
            port: config.get<number>('port', 8080),
            isConnected: false
        };

        this.hotReloadEnabled = config.get<boolean>('enableHotReload', true);

        // Watch for configuration changes
        vscode.workspace.onDidChangeConfiguration(e => {
            if (e.affectsConfiguration('revitpy')) {
                this.updateConfiguration();
            }
        });

        // Watch for file changes for hot-reload
        if (this.hotReloadEnabled) {
            this.setupFileWatcher();
        }
    }

    private updateConfiguration() {
        const config = vscode.workspace.getConfiguration('revitpy');
        const newHost = config.get<string>('host', 'localhost');
        const newPort = config.get<number>('port', 8080);
        const newHotReloadEnabled = config.get<boolean>('enableHotReload', true);

        const connectionChanged = newHost !== this.connection.host || newPort !== this.connection.port;

        this.connection.host = newHost;
        this.connection.port = newPort;
        this.hotReloadEnabled = newHotReloadEnabled;

        if (connectionChanged && this.connection.isConnected) {
            this.logger.info('Connection settings changed, reconnecting...');
            this.reconnect();
        }

        if (newHotReloadEnabled && !this.hotReloadEnabled) {
            this.setupFileWatcher();
        }
    }

    private setupFileWatcher() {
        const fileWatcher = vscode.workspace.createFileSystemWatcher(
            '**/*.{py,rvtpy}',
            false, // ignoreCreateEvents
            false, // ignoreChangeEvents
            true   // ignoreDeleteEvents
        );

        fileWatcher.onDidChange(uri => {
            if (this.hotReloadEnabled && this.connection.isConnected) {
                this.handleFileChange(uri.fsPath);
            }
        });

        fileWatcher.onDidCreate(uri => {
            if (this.hotReloadEnabled && this.connection.isConnected) {
                this.handleFileChange(uri.fsPath);
            }
        });
    }

    private handleFileChange(filePath: string) {
        const event: HotReloadEvent = {
            type: 'file-changed',
            timestamp: Date.now(),
            data: { filePath }
        };

        this.sendMessage({
            type: 'file-changed',
            filePath: filePath
        });

        this.onHotReloadEventEmitter.fire(event);
        this.logger.debug(`File changed: ${filePath}`);
    }

    async connect(): Promise<boolean> {
        if (this.connection.isConnected) {
            this.logger.info('Already connected to Revit');
            return true;
        }

        try {
            this.logger.info(`Connecting to Revit at ${this.connection.host}:${this.connection.port}`);

            const wsUrl = `ws://${this.connection.host}:${this.connection.port}/revitpy`;
            this.websocket = new WebSocket(wsUrl);

            return new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    reject(new Error('Connection timeout'));
                }, 10000);

                this.websocket!.onopen = () => {
                    clearTimeout(timeout);
                    this.connection.isConnected = true;
                    this.reconnectAttempts = 0;
                    this.logger.info('Successfully connected to Revit');
                    this.onConnectionChangedEmitter.fire(true);

                    // Request Revit information
                    this.requestRevitInfo();

                    resolve(true);
                };

                this.websocket!.onerror = (error) => {
                    clearTimeout(timeout);
                    this.logger.error('WebSocket connection error', error);
                    reject(error);
                };

                this.websocket!.onclose = () => {
                    this.handleDisconnection();
                };

                this.websocket!.onmessage = (event) => {
                    this.handleMessage(event.data);
                };
            });

        } catch (error) {
            this.logger.error('Failed to connect to Revit', error);
            vscode.window.showErrorMessage(`Failed to connect to Revit: ${error}`);
            return false;
        }
    }

    async disconnect(): Promise<void> {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = undefined;
        }

        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = undefined;
        }

        this.connection.isConnected = false;
        this.onConnectionChangedEmitter.fire(false);
        this.logger.info('Disconnected from Revit');
    }

    private handleDisconnection() {
        this.connection.isConnected = false;
        this.onConnectionChangedEmitter.fire(false);
        this.logger.warn('Connection to Revit lost');

        const event: HotReloadEvent = {
            type: 'disconnected',
            timestamp: Date.now()
        };
        this.onHotReloadEventEmitter.fire(event);

        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
        } else {
            vscode.window.showErrorMessage('Lost connection to Revit. Maximum reconnection attempts reached.');
        }
    }

    private scheduleReconnect() {
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 30000); // Exponential backoff, max 30s

        this.logger.info(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);

        this.reconnectTimer = setTimeout(() => {
            this.reconnect();
        }, delay);
    }

    private async reconnect() {
        this.logger.info(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        await this.connect();
    }

    private handleMessage(data: string) {
        try {
            const message = JSON.parse(data);
            this.logger.debug('Received message from Revit', message);

            switch (message.type) {
                case 'revit-info':
                    this.connection.revitVersion = message.data.revitVersion;
                    this.connection.pythonVersion = message.data.pythonVersion;
                    break;

                case 'script-result':
                    this.handleScriptResult(message.data);
                    break;

                case 'error':
                    this.handleError(message.data);
                    break;

                case 'hot-reload-event':
                    const event: HotReloadEvent = {
                        type: message.data.eventType,
                        timestamp: Date.now(),
                        data: message.data
                    };
                    this.onHotReloadEventEmitter.fire(event);
                    break;

                default:
                    this.logger.warn('Unknown message type received', message);
            }
        } catch (error) {
            this.logger.error('Failed to parse message from Revit', error);
        }
    }

    private handleScriptResult(result: ScriptExecutionResult) {
        const event: HotReloadEvent = {
            type: 'script-executed',
            timestamp: Date.now(),
            data: result
        };
        this.onHotReloadEventEmitter.fire(event);

        if (result.success) {
            this.logger.info(`Script executed successfully in ${result.executionTime}ms`);
            if (result.output) {
                vscode.window.showInformationMessage(`Script output: ${result.output}`);
            }
        } else {
            this.logger.error('Script execution failed', result.error);
            vscode.window.showErrorMessage(`Script execution failed: ${result.error}`);
        }
    }

    private handleError(error: any) {
        const event: HotReloadEvent = {
            type: 'error',
            timestamp: Date.now(),
            data: error
        };
        this.onHotReloadEventEmitter.fire(event);

        this.logger.error('Error from Revit', error);
        vscode.window.showErrorMessage(`Revit error: ${error.message || error}`);
    }

    async runScript(scriptPath: string): Promise<ScriptExecutionResult | null> {
        if (!this.connection.isConnected) {
            vscode.window.showErrorMessage('Not connected to Revit');
            return null;
        }

        try {
            const document = await vscode.workspace.openTextDocument(scriptPath);
            const scriptContent = document.getText();

            this.sendMessage({
                type: 'run-script',
                scriptPath: scriptPath,
                content: scriptContent
            });

            this.logger.info(`Sent script to Revit: ${scriptPath}`);
            return { success: true, executionTime: 0 }; // Actual result will come via message handler
        } catch (error) {
            this.logger.error('Failed to run script', error);
            vscode.window.showErrorMessage(`Failed to run script: ${error}`);
            return null;
        }
    }

    async generateStubs(): Promise<void> {
        if (!this.connection.isConnected) {
            vscode.window.showErrorMessage('Not connected to Revit');
            return;
        }

        this.sendMessage({
            type: 'generate-stubs'
        });

        this.logger.info('Requested stub generation from Revit');
        vscode.window.showInformationMessage('Generating Revit API stubs...');
    }

    private requestRevitInfo() {
        this.sendMessage({
            type: 'get-revit-info'
        });
    }

    private sendMessage(message: any) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(message));
        } else {
            this.logger.warn('Cannot send message: WebSocket not connected');
        }
    }

    isConnected(): boolean {
        return this.connection.isConnected;
    }

    getConnection(): RevitConnection {
        return { ...this.connection };
    }

    dispose(): void {
        this.disconnect();
        this.onConnectionChangedEmitter.dispose();
        this.onHotReloadEventEmitter.dispose();
    }
}
