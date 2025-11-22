import * as vscode from 'vscode';

export type LogLevel = 'error' | 'warn' | 'info' | 'debug';

export class Logger {
    private outputChannel: vscode.OutputChannel;
    private logLevel: LogLevel;

    constructor(channelName: string) {
        this.outputChannel = vscode.window.createOutputChannel(channelName);
        this.updateLogLevel();

        // Watch for configuration changes
        vscode.workspace.onDidChangeConfiguration(e => {
            if (e.affectsConfiguration('revitpy.logLevel')) {
                this.updateLogLevel();
            }
        });
    }

    private updateLogLevel() {
        const config = vscode.workspace.getConfiguration('revitpy');
        this.logLevel = config.get<LogLevel>('logLevel', 'info');
    }

    private shouldLog(level: LogLevel): boolean {
        const levels: LogLevel[] = ['error', 'warn', 'info', 'debug'];
        return levels.indexOf(level) <= levels.indexOf(this.logLevel);
    }

    private formatMessage(level: LogLevel, message: string, data?: any): string {
        const timestamp = new Date().toISOString();
        const prefix = `[${timestamp}] [${level.toUpperCase()}]`;

        if (data) {
            return `${prefix} ${message}: ${JSON.stringify(data, null, 2)}`;
        }
        return `${prefix} ${message}`;
    }

    error(message: string, data?: any): void {
        if (this.shouldLog('error')) {
            const formatted = this.formatMessage('error', message, data);
            this.outputChannel.appendLine(formatted);
            console.error(formatted);
        }
    }

    warn(message: string, data?: any): void {
        if (this.shouldLog('warn')) {
            const formatted = this.formatMessage('warn', message, data);
            this.outputChannel.appendLine(formatted);
            console.warn(formatted);
        }
    }

    info(message: string, data?: any): void {
        if (this.shouldLog('info')) {
            const formatted = this.formatMessage('info', message, data);
            this.outputChannel.appendLine(formatted);
            console.info(formatted);
        }
    }

    debug(message: string, data?: any): void {
        if (this.shouldLog('debug')) {
            const formatted = this.formatMessage('debug', message, data);
            this.outputChannel.appendLine(formatted);
            console.debug(formatted);
        }
    }

    show(): void {
        this.outputChannel.show();
    }

    dispose(): void {
        this.outputChannel.dispose();
    }
}
