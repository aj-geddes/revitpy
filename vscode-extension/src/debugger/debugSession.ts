import {
    DebugSession,
    InitializedEvent,
    TerminatedEvent,
    StoppedEvent,
    BreakpointEvent,
    OutputEvent,
    Thread,
    StackFrame,
    Scope,
    Variable,
    Breakpoint,
    ContinuedEvent
} from '@vscode/debugadapter';
import { DebugProtocol } from '@vscode/debugprotocol';
import { RevitPyConnectionManager } from '../client/connectionManager';
import { Logger } from '../common/logger';
import { DebugBreakpoint, DebugSession as IDebugSession } from '../common/types';

interface RevitPyLaunchRequestArguments extends DebugProtocol.LaunchRequestArguments {
    script: string;
    host?: string;
    port?: number;
    stopOnEntry?: boolean;
}

export class RevitPyDebugSession extends DebugSession {
    private static THREAD_ID = 1;
    private configurationDone = false;
    private breakpoints: Map<string, DebugBreakpoint[]> = new Map();
    private currentStackTrace: StackFrame[] = [];
    private variables: Map<number, Variable[]> = new Map();
    private nextVariableId = 1;
    private scriptPath?: string;
    private isRunning = false;
    private debugSessionId: string;

    constructor(
        private connectionManager: RevitPyConnectionManager,
        private logger: Logger,
        private launchConfig: any
    ) {
        super();
        this.debugSessionId = this.generateSessionId();
        this.setDebuggerLinesStartAt1(true);
        this.setDebuggerColumnsStartAt1(true);

        // Listen to connection events
        this.connectionManager.onHotReloadEvent(event => {
            this.handleConnectionEvent(event);
        });
    }

    protected initializeRequest(
        response: DebugProtocol.InitializeResponse,
        args: DebugProtocol.InitializeRequestArguments
    ): void {
        response.body = response.body || {};

        // Capabilities
        response.body.supportsConfigurationDoneRequest = true;
        response.body.supportsEvaluateForHovers = true;
        response.body.supportsStepBack = false;
        response.body.supportsDataBreakpoints = false;
        response.body.supportsCompletionsRequest = true;
        response.body.supportsCancelRequest = false;
        response.body.supportsBreakpointLocationsRequest = true;
        response.body.supportsStepInTargetsRequest = false;
        response.body.supportsExceptionFilterOptions = true;
        response.body.supportsExceptionOptions = true;
        response.body.supportsConditionalBreakpoints = true;
        response.body.supportsHitConditionalBreakpoints = true;
        response.body.supportsLogPoints = true;
        response.body.supportsSetVariable = true;
        response.body.supportsRestartRequest = false;
        response.body.supportsGotoTargetsRequest = false;
        response.body.supportsClipboardContext = true;
        response.body.supportsValueFormattingOptions = true;

        this.sendResponse(response);
        this.sendEvent(new InitializedEvent());
    }

    protected configurationDoneRequest(
        response: DebugProtocol.ConfigurationDoneResponse,
        args: DebugProtocol.ConfigurationDoneArguments
    ): void {
        super.configurationDoneRequest(response, args);
        this.configurationDone = true;
    }

    protected async launchRequest(
        response: DebugProtocol.LaunchResponse,
        args: RevitPyLaunchRequestArguments
    ): Promise<void> {
        this.logger.info(`Launching RevitPy debug session for script: ${args.script}`);

        this.scriptPath = args.script;

        try {
            // Ensure connection to Revit
            if (!this.connectionManager.isConnected()) {
                await this.connectionManager.connect();
            }

            // Send debug request to Revit
            await this.startDebuggingInRevit(args);

            if (args.stopOnEntry) {
                this.sendEvent(new StoppedEvent('entry', RevitPyDebugSession.THREAD_ID));
            } else {
                this.isRunning = true;
            }

            this.sendResponse(response);
        } catch (error) {
            this.logger.error('Failed to launch debug session', error);
            response.success = false;
            response.message = `Failed to launch: ${error}`;
            this.sendResponse(response);
            this.sendEvent(new TerminatedEvent());
        }
    }

    protected setBreakPointsRequest(
        response: DebugProtocol.SetBreakpointsResponse,
        args: DebugProtocol.SetBreakpointsArguments
    ): void {
        const path = args.source.path!;
        const breakpoints: Breakpoint[] = [];

        if (args.breakpoints) {
            const debugBreakpoints: DebugBreakpoint[] = args.breakpoints.map(bp => ({
                line: bp.line,
                column: bp.column,
                condition: bp.condition,
                hitCondition: bp.hitCondition,
                logMessage: bp.logMessage
            }));

            this.breakpoints.set(path, debugBreakpoints);

            // Send breakpoints to Revit
            this.sendBreakpointsToRevit(path, debugBreakpoints);

            // Create VS Code breakpoints
            for (const bp of args.breakpoints) {
                const breakpoint = new Breakpoint(
                    true,
                    bp.line,
                    bp.column,
                    args.source
                );
                breakpoint.id = this.generateBreakpointId();
                breakpoints.push(breakpoint);
            }
        } else {
            // Clear breakpoints
            this.breakpoints.delete(path);
            this.clearBreakpointsInRevit(path);
        }

        response.body = {
            breakpoints: breakpoints
        };

        this.sendResponse(response);
    }

    protected threadsRequest(response: DebugProtocol.ThreadsResponse): void {
        response.body = {
            threads: [
                new Thread(RevitPyDebugSession.THREAD_ID, 'Main Thread')
            ]
        };
        this.sendResponse(response);
    }

    protected stackTraceRequest(
        response: DebugProtocol.StackTraceResponse,
        args: DebugProtocol.StackTraceArguments
    ): void {
        response.body = {
            stackFrames: this.currentStackTrace,
            totalFrames: this.currentStackTrace.length
        };
        this.sendResponse(response);
    }

    protected scopesRequest(
        response: DebugProtocol.ScopesResponse,
        args: DebugProtocol.ScopesArguments
    ): void {
        const scopes: Scope[] = [
            new Scope('Locals', this.createVariableId('locals'), false),
            new Scope('Globals', this.createVariableId('globals'), true)
        ];

        response.body = { scopes };
        this.sendResponse(response);
    }

    protected variablesRequest(
        response: DebugProtocol.VariablesResponse,
        args: DebugProtocol.VariablesArguments
    ): void {
        const variables = this.variables.get(args.variablesReference) || [];
        response.body = { variables };
        this.sendResponse(response);
    }

    protected continueRequest(
        response: DebugProtocol.ContinueResponse,
        args: DebugProtocol.ContinueArguments
    ): void {
        this.isRunning = true;
        this.sendContinueToRevit();
        this.sendEvent(new ContinuedEvent(RevitPyDebugSession.THREAD_ID));
        this.sendResponse(response);
    }

    protected nextRequest(
        response: DebugProtocol.NextResponse,
        args: DebugProtocol.NextArguments
    ): void {
        this.isRunning = true;
        this.sendStepOverToRevit();
        this.sendResponse(response);
    }

    protected stepInRequest(
        response: DebugProtocol.StepInResponse,
        args: DebugProtocol.StepInArguments
    ): void {
        this.isRunning = true;
        this.sendStepIntoToRevit();
        this.sendResponse(response);
    }

    protected stepOutRequest(
        response: DebugProtocol.StepOutResponse,
        args: DebugProtocol.StepOutArguments
    ): void {
        this.isRunning = true;
        this.sendStepOutToRevit();
        this.sendResponse(response);
    }

    protected pauseRequest(
        response: DebugProtocol.PauseResponse,
        args: DebugProtocol.PauseArguments
    ): void {
        this.sendPauseToRevit();
        this.sendResponse(response);
    }

    protected evaluateRequest(
        response: DebugProtocol.EvaluateResponse,
        args: DebugProtocol.EvaluateArguments
    ): void {
        this.sendEvaluateToRevit(args.expression)
            .then(result => {
                response.body = {
                    result: result.value,
                    type: result.type,
                    variablesReference: result.variablesReference || 0
                };
                this.sendResponse(response);
            })
            .catch(error => {
                response.success = false;
                response.message = error.message;
                this.sendResponse(response);
            });
    }

    protected disconnectRequest(
        response: DebugProtocol.DisconnectResponse,
        args: DebugProtocol.DisconnectArguments
    ): void {
        this.logger.info('Disconnecting debug session');
        this.sendStopDebuggingToRevit();
        this.sendResponse(response);
        this.sendEvent(new TerminatedEvent());
    }

    // RevitPy specific methods

    private async startDebuggingInRevit(args: RevitPyLaunchRequestArguments): Promise<void> {
        const message = {
            type: 'start-debugging',
            sessionId: this.debugSessionId,
            scriptPath: args.script,
            stopOnEntry: args.stopOnEntry || false
        };

        await this.sendMessageToRevit(message);
    }

    private async sendBreakpointsToRevit(path: string, breakpoints: DebugBreakpoint[]): Promise<void> {
        const message = {
            type: 'set-breakpoints',
            sessionId: this.debugSessionId,
            path: path,
            breakpoints: breakpoints
        };

        await this.sendMessageToRevit(message);
    }

    private async clearBreakpointsInRevit(path: string): Promise<void> {
        const message = {
            type: 'clear-breakpoints',
            sessionId: this.debugSessionId,
            path: path
        };

        await this.sendMessageToRevit(message);
    }

    private sendContinueToRevit(): void {
        const message = {
            type: 'continue',
            sessionId: this.debugSessionId
        };

        this.sendMessageToRevit(message);
    }

    private sendStepOverToRevit(): void {
        const message = {
            type: 'step-over',
            sessionId: this.debugSessionId
        };

        this.sendMessageToRevit(message);
    }

    private sendStepIntoToRevit(): void {
        const message = {
            type: 'step-into',
            sessionId: this.debugSessionId
        };

        this.sendMessageToRevit(message);
    }

    private sendStepOutToRevit(): void {
        const message = {
            type: 'step-out',
            sessionId: this.debugSessionId
        };

        this.sendMessageToRevit(message);
    }

    private sendPauseToRevit(): void {
        const message = {
            type: 'pause',
            sessionId: this.debugSessionId
        };

        this.sendMessageToRevit(message);
    }

    private async sendEvaluateToRevit(expression: string): Promise<any> {
        const message = {
            type: 'evaluate',
            sessionId: this.debugSessionId,
            expression: expression
        };

        return new Promise((resolve, reject) => {
            // Store the promise resolver to handle the response
            this.pendingEvaluations.set(expression, { resolve, reject });
            this.sendMessageToRevit(message);
        });
    }

    private sendStopDebuggingToRevit(): void {
        const message = {
            type: 'stop-debugging',
            sessionId: this.debugSessionId
        };

        this.sendMessageToRevit(message);
    }

    private async sendMessageToRevit(message: any): Promise<void> {
        // Implementation would send the message through the connection manager
        this.logger.debug('Sending debug message to Revit', message);
        // This would be implemented based on the actual protocol with Revit
    }

    private handleConnectionEvent(event: any): void {
        if (event.data?.sessionId !== this.debugSessionId) {
            return; // Not for this session
        }

        switch (event.type) {
            case 'debug-stopped':
                this.handleDebugStopped(event.data);
                break;
            case 'debug-continued':
                this.handleDebugContinued();
                break;
            case 'debug-variables':
                this.handleVariablesUpdate(event.data);
                break;
            case 'debug-output':
                this.handleDebugOutput(event.data);
                break;
            case 'debug-error':
                this.handleDebugError(event.data);
                break;
            case 'evaluation-result':
                this.handleEvaluationResult(event.data);
                break;
        }
    }

    private handleDebugStopped(data: any): void {
        this.isRunning = false;

        // Update stack trace
        this.currentStackTrace = data.stackTrace?.map((frame: any, index: number) =>
            new StackFrame(
                index + 1,
                frame.name,
                this.createSource(frame.fileName),
                frame.line,
                frame.column
            )
        ) || [];

        this.sendEvent(new StoppedEvent(data.reason || 'breakpoint', RevitPyDebugSession.THREAD_ID));
    }

    private handleDebugContinued(): void {
        this.isRunning = true;
        this.sendEvent(new ContinuedEvent(RevitPyDebugSession.THREAD_ID));
    }

    private handleVariablesUpdate(data: any): void {
        if (data.locals) {
            const localsId = this.createVariableId('locals');
            this.variables.set(localsId, data.locals.map((v: any) => new Variable(v.name, v.value, v.type)));
        }

        if (data.globals) {
            const globalsId = this.createVariableId('globals');
            this.variables.set(globalsId, data.globals.map((v: any) => new Variable(v.name, v.value, v.type)));
        }
    }

    private handleDebugOutput(data: any): void {
        this.sendEvent(new OutputEvent(data.output, data.category || 'stdout'));
    }

    private handleDebugError(data: any): void {
        this.sendEvent(new OutputEvent(data.error, 'stderr'));
    }

    private pendingEvaluations = new Map<string, { resolve: Function; reject: Function }>();

    private handleEvaluationResult(data: any): void {
        const pending = this.pendingEvaluations.get(data.expression);
        if (pending) {
            if (data.success) {
                pending.resolve(data.result);
            } else {
                pending.reject(new Error(data.error));
            }
            this.pendingEvaluations.delete(data.expression);
        }
    }

    private createSource(filePath: string): DebugProtocol.Source {
        return {
            name: filePath.split(/[/\\]/).pop(),
            path: filePath,
            sourceReference: 0
        };
    }

    private createVariableId(scope: string): number {
        const id = this.nextVariableId++;
        // Store scope mapping for later reference
        return id;
    }

    private generateSessionId(): string {
        return `revitpy-debug-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }

    private generateBreakpointId(): number {
        return Math.floor(Math.random() * 1000000);
    }

    async terminate(): Promise<void> {
        this.sendStopDebuggingToRevit();
        this.sendEvent(new TerminatedEvent());
    }

    dispose(): void {
        this.terminate();
    }
}
