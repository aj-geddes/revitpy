import * as vscode from 'vscode';
import * as path from 'path';
import { LanguageClient, LanguageClientOptions, ServerOptions, TransportKind } from 'vscode-languageclient/node';
import { RevitPyConnectionManager } from './client/connectionManager';
import { RevitPyDebuggerProvider } from './debugger/debuggerProvider';
import { PackageManager } from './client/packageManager';
import { ProjectManager } from './client/projectManager';
import { RevitPyStatusBar } from './client/statusBar';
import { RevitPyTreeProvider } from './client/treeProvider';
import { Logger } from './common/logger';

let client: LanguageClient;
let connectionManager: RevitPyConnectionManager;
let debuggerProvider: RevitPyDebuggerProvider;
let packageManager: PackageManager;
let projectManager: ProjectManager;
let statusBar: RevitPyStatusBar;
let logger: Logger;

export async function activate(context: vscode.ExtensionContext) {
    logger = new Logger('RevitPy');
    logger.info('RevitPy extension is being activated');

    // Initialize status bar
    statusBar = new RevitPyStatusBar();
    context.subscriptions.push(statusBar);

    // Initialize connection manager
    connectionManager = new RevitPyConnectionManager(logger);
    context.subscriptions.push(connectionManager);

    // Initialize package manager
    packageManager = new PackageManager(logger);
    context.subscriptions.push(packageManager);

    // Initialize project manager
    projectManager = new ProjectManager(logger);
    context.subscriptions.push(projectManager);

    // Initialize debugger
    debuggerProvider = new RevitPyDebuggerProvider(connectionManager, logger);
    context.subscriptions.push(
        vscode.debug.registerDebugAdapterDescriptorFactory('revitpy', debuggerProvider)
    );

    // Start Language Server
    await startLanguageServer(context);

    // Register commands
    registerCommands(context);

    // Initialize tree providers
    initializeTreeProviders(context);

    // Set context for when RevitPy project is present
    updateWorkspaceContext();

    logger.info('RevitPy extension activated successfully');
}

export function deactivate(): Thenable<void> | undefined {
    logger?.info('RevitPy extension is being deactivated');
    
    connectionManager?.disconnect();
    
    if (!client) {
        return undefined;
    }
    return client.stop();
}

async function startLanguageServer(context: vscode.ExtensionContext) {
    const serverModule = context.asAbsolutePath(path.join('out', 'server', 'server.js'));
    
    const serverOptions: ServerOptions = {
        run: { module: serverModule, transport: TransportKind.ipc },
        debug: {
            module: serverModule,
            transport: TransportKind.ipc,
            options: { execArgv: ['--nolazy', '--inspect=6009'] }
        }
    };

    const clientOptions: LanguageClientOptions = {
        documentSelector: [
            { scheme: 'file', language: 'python' },
            { scheme: 'file', language: 'revitpy' }
        ],
        synchronize: {
            fileEvents: [
                vscode.workspace.createFileSystemWatcher('**/*.py'),
                vscode.workspace.createFileSystemWatcher('**/*.rvtpy'),
                vscode.workspace.createFileSystemWatcher('**/revitpy.json')
            ]
        }
    };

    client = new LanguageClient(
        'revitpyLanguageServer',
        'RevitPy Language Server',
        serverOptions,
        clientOptions
    );

    try {
        await client.start();
        logger.info('Language Server started successfully');
    } catch (error) {
        logger.error('Failed to start Language Server', error);
    }
}

function registerCommands(context: vscode.ExtensionContext) {
    const commands = [
        vscode.commands.registerCommand('revitpy.createProject', () => {
            projectManager.createProject();
        }),
        
        vscode.commands.registerCommand('revitpy.connectToRevit', async () => {
            await connectionManager.connect();
            statusBar.updateConnectionStatus(connectionManager.isConnected());
        }),
        
        vscode.commands.registerCommand('revitpy.disconnectFromRevit', async () => {
            await connectionManager.disconnect();
            statusBar.updateConnectionStatus(connectionManager.isConnected());
        }),
        
        vscode.commands.registerCommand('revitpy.runScript', async (uri?: vscode.Uri) => {
            const scriptPath = uri?.fsPath || vscode.window.activeTextEditor?.document.fileName;
            if (scriptPath && connectionManager.isConnected()) {
                await connectionManager.runScript(scriptPath);
            } else {
                vscode.window.showErrorMessage('Not connected to Revit or no script selected');
            }
        }),
        
        vscode.commands.registerCommand('revitpy.debugScript', async (uri?: vscode.Uri) => {
            const scriptPath = uri?.fsPath || vscode.window.activeTextEditor?.document.fileName;
            if (scriptPath) {
                await debuggerProvider.startDebugging(scriptPath);
            } else {
                vscode.window.showErrorMessage('No script selected for debugging');
            }
        }),
        
        vscode.commands.registerCommand('revitpy.openPackageManager', () => {
            packageManager.openPackageManager();
        }),
        
        vscode.commands.registerCommand('revitpy.refreshPackages', async () => {
            await packageManager.refreshPackages();
        }),
        
        vscode.commands.registerCommand('revitpy.generateStubs', async () => {
            await connectionManager.generateStubs();
        })
    ];

    context.subscriptions.push(...commands);
}

function initializeTreeProviders(context: vscode.ExtensionContext) {
    const packageTreeProvider = new RevitPyTreeProvider('packages', packageManager);
    const connectionTreeProvider = new RevitPyTreeProvider('connection', connectionManager);

    vscode.window.registerTreeDataProvider('revitpyPackages', packageTreeProvider);
    vscode.window.registerTreeDataProvider('revitpyConnection', connectionTreeProvider);

    context.subscriptions.push(
        vscode.commands.registerCommand('revitpyPackages.refresh', () => {
            packageTreeProvider.refresh();
        }),
        vscode.commands.registerCommand('revitpyConnection.refresh', () => {
            connectionTreeProvider.refresh();
        })
    );
}

function updateWorkspaceContext() {
    const hasRevitPyProject = vscode.workspace.workspaceFolders?.some(folder => {
        const revitPyConfig = vscode.workspace.fs.readFile(
            vscode.Uri.joinPath(folder.uri, 'revitpy.json')
        );
        return revitPyConfig !== undefined;
    }) || false;

    vscode.commands.executeCommand('setContext', 'workspaceHasRevitPyProject', hasRevitPyProject);
}