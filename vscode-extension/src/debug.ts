/** Attach VS Code's Python debugger (debugpy) to Revit via the Live Server's debug/start. */
import * as vscode from 'vscode';
import type { ConnectionManager } from './connection';
import type { DebugStartResult } from './protocol';

export const DEBUGPY_EXTENSION_ID = 'ms-python.debugpy';

export interface PathMapping {
  localRoot: string;
  remoteRoot: string;
}

export function buildAttachConfiguration(
  port: number,
  options: { pathMappings?: PathMapping[]; justMyCode?: boolean } = {},
): vscode.DebugConfiguration {
  const config: vscode.DebugConfiguration = {
    type: 'debugpy',
    request: 'attach',
    name: 'Attach to Revit (RevitPy)',
    connect: { host: '127.0.0.1', port },
    justMyCode: options.justMyCode ?? false,
  };
  const mappings = (options.pathMappings ?? [])
    .filter(
      (mapping): mapping is PathMapping =>
        typeof mapping === 'object' &&
        mapping !== null &&
        typeof mapping.localRoot === 'string' &&
        typeof mapping.remoteRoot === 'string',
    )
    .map(({ localRoot, remoteRoot }) => ({ localRoot, remoteRoot }));
  if (mappings.length > 0) {
    config.pathMappings = mappings;
  }
  return config;
}

export async function attachDebugger(connection: ConnectionManager, output: vscode.OutputChannel): Promise<boolean> {
  if (!vscode.extensions.getExtension(DEBUGPY_EXTENSION_ID)) {
    const choice = await vscode.window.showErrorMessage(
      'Attaching to Revit needs the Python Debugger extension (ms-python.debugpy).',
      'Install',
    );
    if (choice === 'Install') {
      await vscode.commands.executeCommand('workbench.extensions.installExtension', DEBUGPY_EXTENSION_ID);
    }
    return false;
  }

  const config = vscode.workspace.getConfiguration('revitpy');
  const port = config.get<number>('debugPort', 5678);
  const pathMappings = config.get<PathMapping[]>('debugPathMappings', []);
  const justMyCode = config.get<boolean>('debugJustMyCode', false);

  let result: DebugStartResult;
  try {
    const client = await connection.ensureClient();
    result = await client.startDebugger(port);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    output.appendLine(`[debug] ${message}`);
    void vscode.window.showErrorMessage(`Could not start the debugger in Revit: ${message}`);
    return false;
  }

  if (!result.listening) {
    const message = result.error ?? 'debugpy did not start';
    output.appendLine(`[debug] ${message}`);
    const choice = await vscode.window.showErrorMessage(
      `Revit could not start debugpy: ${message}`,
      'How to install debugpy',
    );
    if (choice === 'How to install debugpy') {
      output.appendLine(
        '[debug] Install debugpy into the Python environment RevitPy uses inside Revit ' +
          '(e.g. "<revit python>\\python.exe -m pip install debugpy"), then run RevitPy: Attach Debugger to Revit again.',
      );
      output.show();
    }
    return false;
  }

  const actualPort = result.port ?? port;
  output.appendLine(`[debug] debugpy listening in Revit on 127.0.0.1:${actualPort}`);
  const started = await vscode.debug.startDebugging(
    vscode.workspace.workspaceFolders?.[0],
    buildAttachConfiguration(actualPort, { pathMappings, justMyCode }),
  );
  if (!started) {
    void vscode.window.showErrorMessage('VS Code could not attach to Revit. See the Debug Console.');
  }
  connection.refreshStatus().catch(() => undefined);
  return started;
}
