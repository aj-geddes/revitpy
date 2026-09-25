/**
 * RevitPy for VS Code: run, reload and debug Python inside Revit through the
 * RevitPy Live Server (JSON-RPC 2.0 over WebSocket, docs/developer/live-server.md).
 */
import * as vscode from 'vscode';
import { ConnectionManager, type ConnectionSettings } from './connection';
import { createProject } from './createProject';
import { attachDebugger } from './debug';
import { LiveCommands } from './liveCommands';
import { RevitStatusBar } from './statusBar';
import { configureStubs } from './stubs';

function readSettings(): ConnectionSettings {
  const config = vscode.workspace.getConfiguration('revitpy');
  const discoveryFile = config.get<string>('discoveryFile', '').trim();
  return {
    discoveryFile: discoveryFile || undefined,
    requestTimeoutMs: Math.max(5, config.get<number>('requestTimeoutSeconds', 330)) * 1000,
  };
}

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel('RevitPy');
  const connection = new ConnectionManager(readSettings);
  const commands = new LiveCommands(connection, output);
  const statusBar = new RevitStatusBar(connection);

  connection.on('disconnected', (reason: unknown) => {
    output.appendLine(`[disconnected] ${String(reason)}`);
  });

  // Periodic status refresh keeps the active document in the status bar current.
  let timer: NodeJS.Timeout | undefined;
  const scheduleRefresh = (): void => {
    if (timer) {
      clearInterval(timer);
      timer = undefined;
    }
    const seconds = vscode.workspace.getConfiguration('revitpy').get<number>('statusRefreshSeconds', 30);
    if (seconds > 0) {
      timer = setInterval(() => {
        if (connection.isConnected) {
          connection.refreshStatus().catch(() => undefined);
        }
      }, seconds * 1000);
    }
  };
  scheduleRefresh();

  context.subscriptions.push(
    output,
    statusBar,
    { dispose: () => connection.dispose() },
    { dispose: () => timer && clearInterval(timer) },
    vscode.commands.registerCommand('revitpy.connect', () => commands.connect()),
    vscode.commands.registerCommand('revitpy.disconnect', () => commands.disconnect()),
    vscode.commands.registerCommand('revitpy.showStatus', () => commands.showStatus()),
    vscode.commands.registerCommand('revitpy.runScript', (resource?: vscode.Uri) =>
      commands.runScript(resource instanceof vscode.Uri ? resource : undefined),
    ),
    vscode.commands.registerCommand('revitpy.runSelection', () => commands.runSelection()),
    vscode.commands.registerCommand('revitpy.reloadModule', async () => {
      const document = vscode.window.activeTextEditor?.document;
      if (!document) {
        void vscode.window.showWarningMessage('Open a Python module to reload it in Revit.');
        return;
      }
      await commands.reloadFile(document, { quiet: false });
    }),
    vscode.commands.registerCommand('revitpy.attachDebugger', () => attachDebugger(connection, output)),
    vscode.commands.registerCommand('revitpy.createProject', () => createProject(output)),
    vscode.commands.registerCommand('revitpy.configureStubs', () => configureStubs(output)),
    vscode.workspace.onDidSaveTextDocument((document) => {
      if (vscode.workspace.getConfiguration('revitpy').get<boolean>('reloadOnSave', false)) {
        void commands.reloadFile(document, { quiet: true });
      }
    }),
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration('revitpy.statusRefreshSeconds')) {
        scheduleRefresh();
      }
    }),
  );

  if (vscode.workspace.getConfiguration('revitpy').get<boolean>('autoConnect', true)) {
    connection.connect().then(
      (client) => output.appendLine(`[connected] ${client.url}`),
      (error: unknown) => output.appendLine(`[auto-connect] ${error instanceof Error ? error.message : String(error)}`),
    );
  }
}

export function deactivate(): void {
  // Everything is disposed through context.subscriptions.
}
