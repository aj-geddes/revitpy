import * as vscode from 'vscode';
import { ProjectManager } from './providers/projectManager';
import { PackageManager } from './providers/packageManager';
import { RevitConnection } from './providers/revitConnection';
import { ElementInspector } from './providers/elementInspector';
import { DebugAdapterFactory } from './debug/debugAdapter';
import { RevitPyLanguageServer } from './language/languageServer';
import { TaskProvider } from './tasks/taskProvider';
import { REPLManager } from './repl/replManager';
import { TelemetryManager } from './telemetry/telemetryManager';

export async function activate(context: vscode.ExtensionContext) {
    console.log('RevitPy extension is now active!');

    // Initialize managers
    const projectManager = new ProjectManager(context);
    const packageManager = new PackageManager(context);
    const revitConnection = new RevitConnection(context);
    const elementInspector = new ElementInspector(context);
    const replManager = new REPLManager(context);
    const telemetryManager = new TelemetryManager(context);
    const languageServer = new RevitPyLanguageServer(context);

    // Set context when RevitPy is enabled
    vscode.commands.executeCommand('setContext', 'revitpy:enabled', true);

    // Register tree data providers
    vscode.window.createTreeView('revitpy.projectExplorer', {
        treeDataProvider: projectManager,
        showCollapseAll: true
    });

    vscode.window.createTreeView('revitpy.packageExplorer', {
        treeDataProvider: packageManager,
        showCollapseAll: true
    });

    vscode.window.createTreeView('revitpy.revitConnection', {
        treeDataProvider: revitConnection,
        canSelectMany: false
    });

    vscode.window.createTreeView('revitpy.elementInspector', {
        treeDataProvider: elementInspector,
        showCollapseAll: true
    });

    // Register commands
    registerCommands(context, {
        projectManager,
        packageManager,
        revitConnection,
        elementInspector,
        replManager,
        languageServer
    });

    // Register debug adapter
    context.subscriptions.push(
        vscode.debug.registerDebugAdapterDescriptorFactory('revitpy', new DebugAdapterFactory())
    );

    // Register task provider
    context.subscriptions.push(
        vscode.tasks.registerTaskProvider('revitpy', new TaskProvider())
    );

    // Start language server
    await languageServer.start();

    // Auto-connect to Revit if enabled
    const config = vscode.workspace.getConfiguration('revitpy');
    if (config.get('autoConnect')) {
        revitConnection.autoConnect();
    }

    // Show welcome message for first-time users
    if (context.globalState.get('revitpy.firstActivation', true)) {
        showWelcomeMessage(context);
        context.globalState.update('revitpy.firstActivation', false);
    }

    return {
        projectManager,
        packageManager,
        revitConnection,
        elementInspector,
        replManager,
        languageServer
    };
}

export function deactivate() {
    console.log('RevitPy extension is now inactive!');
}

function registerCommands(context: vscode.ExtensionContext, managers: any) {
    const commands = [
        // Project commands
        vscode.commands.registerCommand('revitpy.createProject', () => 
            managers.projectManager.createProject()
        ),
        vscode.commands.registerCommand('revitpy.openProject', () => 
            managers.projectManager.openProject()
        ),
        vscode.commands.registerCommand('revitpy.buildProject', () => 
            managers.projectManager.buildProject()
        ),
        vscode.commands.registerCommand('revitpy.deployProject', () => 
            managers.projectManager.deployProject()
        ),

        // Script execution commands
        vscode.commands.registerCommand('revitpy.runScript', () => 
            runCurrentScript(managers.revitConnection)
        ),
        vscode.commands.registerCommand('revitpy.debugScript', () => 
            debugCurrentScript()
        ),

        // REPL commands
        vscode.commands.registerCommand('revitpy.openRepl', () => 
            managers.replManager.openREPL()
        ),

        // Package commands
        vscode.commands.registerCommand('revitpy.installPackage', () => 
            managers.packageManager.installPackage()
        ),
        vscode.commands.registerCommand('revitpy.browsePackages', () => 
            managers.packageManager.browsePackages()
        ),

        // Dashboard command
        vscode.commands.registerCommand('revitpy.openDashboard', () => 
            openDashboard()
        ),

        // Connection commands
        vscode.commands.registerCommand('revitpy.connectToRevit', () => 
            managers.revitConnection.connect()
        ),
        vscode.commands.registerCommand('revitpy.disconnectFromRevit', () => 
            managers.revitConnection.disconnect()
        ),

        // Element inspector
        vscode.commands.registerCommand('revitpy.showElementInspector', () => 
            managers.elementInspector.show()
        ),

        // Refresh commands
        vscode.commands.registerCommand('revitpy.refreshProjects', () => 
            managers.projectManager.refresh()
        ),
        vscode.commands.registerCommand('revitpy.refreshPackages', () => 
            managers.packageManager.refresh()
        ),
        vscode.commands.registerCommand('revitpy.refreshConnection', () => 
            managers.revitConnection.refresh()
        )
    ];

    commands.forEach(command => context.subscriptions.push(command));
}

async function runCurrentScript(revitConnection: RevitConnection) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showErrorMessage('No active editor found');
        return;
    }

    if (!revitConnection.isConnected()) {
        vscode.window.showErrorMessage('Not connected to Revit');
        return;
    }

    const document = editor.document;
    if (document.languageId !== 'python' && document.languageId !== 'revitpy') {
        vscode.window.showErrorMessage('Active file is not a Python script');
        return;
    }

    // Save the document if it has unsaved changes
    if (document.isDirty) {
        await document.save();
    }

    try {
        await revitConnection.executeScript(document.fileName);
        vscode.window.showInformationMessage('Script executed successfully');
    } catch (error) {
        vscode.window.showErrorMessage(`Script execution failed: ${error}`);
    }
}

async function debugCurrentScript() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showErrorMessage('No active editor found');
        return;
    }

    const document = editor.document;
    if (document.languageId !== 'python' && document.languageId !== 'revitpy') {
        vscode.window.showErrorMessage('Active file is not a Python script');
        return;
    }

    // Save the document if it has unsaved changes
    if (document.isDirty) {
        await document.save();
    }

    const config: vscode.DebugConfiguration = {
        type: 'revitpy',
        request: 'launch',
        name: 'Debug RevitPy Script',
        script: document.fileName,
        stopOnEntry: false
    };

    await vscode.debug.startDebugging(undefined, config);
}

async function openDashboard() {
    const panel = vscode.window.createWebviewPanel(
        'revitpy-dashboard',
        'RevitPy Dashboard',
        vscode.ViewColumn.One,
        {
            enableScripts: true,
            enableCommandUris: true,
            localResourceRoots: []
        }
    );

    // Load dashboard content
    panel.webview.html = getDashboardHtml();

    // Handle messages from the dashboard
    panel.webview.onDidReceiveMessage(
        message => {
            switch (message.command) {
                case 'createProject':
                    vscode.commands.executeCommand('revitpy.createProject');
                    break;
                case 'browsePackages':
                    vscode.commands.executeCommand('revitpy.browsePackages');
                    break;
                case 'openREPL':
                    vscode.commands.executeCommand('revitpy.openRepl');
                    break;
            }
        }
    );
}

function getDashboardHtml(): string {
    return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>RevitPy Dashboard</title>
        <style>
            body {
                font-family: var(--vscode-font-family);
                background-color: var(--vscode-editor-background);
                color: var(--vscode-editor-foreground);
                margin: 0;
                padding: 20px;
            }
            .header {
                margin-bottom: 30px;
            }
            .title {
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            .subtitle {
                color: var(--vscode-descriptionForeground);
            }
            .quick-actions {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .action-card {
                background: var(--vscode-button-background);
                border: 1px solid var(--vscode-button-border);
                border-radius: 4px;
                padding: 20px;
                text-align: center;
                cursor: pointer;
                transition: background-color 0.2s;
            }
            .action-card:hover {
                background: var(--vscode-button-hoverBackground);
            }
            .action-icon {
                font-size: 32px;
                margin-bottom: 10px;
            }
            .action-title {
                font-weight: bold;
                margin-bottom: 5px;
            }
            .action-description {
                color: var(--vscode-descriptionForeground);
                font-size: 12px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title">RevitPy Dashboard</div>
            <div class="subtitle">Welcome to your RevitPy development environment</div>
        </div>
        
        <div class="quick-actions">
            <div class="action-card" onclick="sendMessage('createProject')">
                <div class="action-icon">📁</div>
                <div class="action-title">New Project</div>
                <div class="action-description">Create a new RevitPy project</div>
            </div>
            
            <div class="action-card" onclick="sendMessage('browsePackages')">
                <div class="action-icon">📦</div>
                <div class="action-title">Browse Packages</div>
                <div class="action-description">Explore the RevitPy package registry</div>
            </div>
            
            <div class="action-card" onclick="sendMessage('openREPL')">
                <div class="action-icon">⚡</div>
                <div class="action-title">Open REPL</div>
                <div class="action-description">Interactive Python environment</div>
            </div>
        </div>

        <script>
            const vscode = acquireVsCodeApi();
            
            function sendMessage(command) {
                vscode.postMessage({ command: command });
            }
        </script>
    </body>
    </html>`;
}

async function showWelcomeMessage(context: vscode.ExtensionContext) {
    const choice = await vscode.window.showInformationMessage(
        'Welcome to RevitPy! Get started by creating your first project or exploring the package registry.',
        'Create Project',
        'Browse Packages',
        'Open Dashboard'
    );

    switch (choice) {
        case 'Create Project':
            vscode.commands.executeCommand('revitpy.createProject');
            break;
        case 'Browse Packages':
            vscode.commands.executeCommand('revitpy.browsePackages');
            break;
        case 'Open Dashboard':
            vscode.commands.executeCommand('revitpy.openDashboard');
            break;
    }
}