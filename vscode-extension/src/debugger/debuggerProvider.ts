import * as vscode from 'vscode';
import { RevitPyConnectionManager } from '../client/connectionManager';
import { Logger } from '../common/logger';
import { RevitPyDebugSession } from './debugSession';

export class RevitPyDebuggerProvider implements vscode.DebugAdapterDescriptorFactory, vscode.Disposable {
    private activeSessions: Map<string, RevitPyDebugSession> = new Map();

    constructor(
        private connectionManager: RevitPyConnectionManager,
        private logger: Logger
    ) {}

    createDebugAdapterDescriptor(
        session: vscode.DebugSession,
        executable: vscode.DebugAdapterExecutable | undefined
    ): vscode.ProviderResult<vscode.DebugAdapterDescriptor> {

        const debugSession = new RevitPyDebugSession(
            this.connectionManager,
            this.logger,
            session.configuration
        );

        this.activeSessions.set(session.id, debugSession);

        // Clean up when session ends
        session.onDidTerminateDebugSession(() => {
            this.activeSessions.delete(session.id);
            debugSession.dispose();
        });

        return new vscode.DebugAdapterInlineImplementation(debugSession);
    }

    async startDebugging(scriptPath: string): Promise<boolean> {
        if (!this.connectionManager.isConnected()) {
            const connected = await this.connectionManager.connect();
            if (!connected) {
                vscode.window.showErrorMessage('Could not connect to Revit for debugging');
                return false;
            }
        }

        const debugConfig: vscode.DebugConfiguration = {
            type: 'revitpy',
            request: 'launch',
            name: 'Debug RevitPy Script',
            script: scriptPath,
            stopOnEntry: true,
            host: this.connectionManager.getConnection().host,
            port: this.connectionManager.getConnection().port
        };

        try {
            const success = await vscode.debug.startDebugging(
                vscode.workspace.getWorkspaceFolder(vscode.Uri.file(scriptPath)),
                debugConfig
            );

            if (success) {
                this.logger.info(`Started debugging session for ${scriptPath}`);
            }

            return success;
        } catch (error) {
            this.logger.error('Failed to start debugging session', error);
            vscode.window.showErrorMessage(`Failed to start debugging: ${error}`);
            return false;
        }
    }

    getActiveSession(sessionId: string): RevitPyDebugSession | undefined {
        return this.activeSessions.get(sessionId);
    }

    getAllActiveSessions(): RevitPyDebugSession[] {
        return Array.from(this.activeSessions.values());
    }

    async stopAllSessions(): Promise<void> {
        for (const session of this.activeSessions.values()) {
            await session.terminate();
        }
        this.activeSessions.clear();
    }

    dispose(): void {
        this.stopAllSessions();
    }
}
