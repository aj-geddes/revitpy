/** Connect / status / run / reload commands on top of the ConnectionManager. */
import * as path from 'node:path';
import * as vscode from 'vscode';
import type { ConnectionManager } from './connection';
import { DiscoveryError, LiveServerNotRunningError } from './discovery';
import { dedent, formatExecutionResult, formatReloadResult, lastErrorLine, statusSummary } from './format';
import { ConnectionError, JsonRpcError, RequestTimeoutError, type LiveClient } from './liveClient';
import type { ExecutionResult } from './protocol';

export function describeError(error: unknown): string {
  if (
    error instanceof LiveServerNotRunningError ||
    error instanceof DiscoveryError ||
    error instanceof ConnectionError ||
    error instanceof RequestTimeoutError
  ) {
    return error.message;
  }
  if (error instanceof JsonRpcError) {
    return `Revit reported: ${error.rpcMessage}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export class LiveCommands {
  constructor(
    private readonly connection: ConnectionManager,
    private readonly output: vscode.OutputChannel,
  ) {}

  async connect(): Promise<void> {
    try {
      const client = await this.connection.connect();
      this.output.appendLine(`[connected] ${client.url}`);
      const status = this.connection.status;
      let message = 'Connected to Revit.';
      if (status) {
        message = `Connected to Revit ${status.revit_version ?? ''}`.trimEnd();
        if (status.document) {
          message += ` — ${status.document}`;
        }
      }
      void vscode.window.showInformationMessage(message);
    } catch (error) {
      this.fail(error);
    }
  }

  async disconnect(): Promise<void> {
    if (!this.connection.isConnected) {
      void vscode.window.showInformationMessage('Not connected to Revit.');
      return;
    }
    try {
      await this.connection.disconnect();
      this.output.appendLine('[disconnected] by user');
      void vscode.window.showInformationMessage('Disconnected from Revit.');
    } catch (error) {
      this.fail(error);
    }
  }

  async showStatus(): Promise<void> {
    try {
      const client = await this.connection.ensureClient();
      const status = await this.connection.refreshStatus();
      if (!status) {
        return;
      }
      this.output.appendLine('--- RevitPy Live Server status ---');
      for (const line of statusSummary(status, client.url)) {
        this.output.appendLine(line);
      }
      this.output.show(true);
      void vscode.window.showInformationMessage(
        `Revit ${status.revit_version ?? '?'} · ${status.document ?? 'no document'} · RevitPy ${status.revitpy_version}`,
      );
    } catch (error) {
      this.fail(error);
    }
  }

  /** Run a whole file in Revit: live/runFile for saved files, live/execute for untitled ones. */
  async runScript(resource?: vscode.Uri): Promise<void> {
    try {
      const document = resource
        ? await vscode.workspace.openTextDocument(resource)
        : vscode.window.activeTextEditor?.document;
      if (!document) {
        void vscode.window.showWarningMessage('Open a Python file to run it in Revit.');
        return;
      }
      if (document.languageId !== 'python') {
        void vscode.window.showWarningMessage('RevitPy: Run Script only runs Python files.');
        return;
      }
      if (document.isDirty && !(await document.save())) {
        void vscode.window.showWarningMessage('Save the file before running it in Revit.');
        return;
      }

      const client = await this.connection.ensureClient();
      const label = document.isUntitled ? 'untitled script' : vscode.workspace.asRelativePath(document.uri);
      this.output.appendLine(`> Running ${label} in Revit`);
      const result = await this.withProgress(`Running ${label} in Revit…`, () =>
        document.isUntitled ? client.execute(document.getText(), '<untitled>') : client.runFile(document.uri.fsPath),
      );
      await this.report(label, result);
    } catch (error) {
      this.fail(error);
    }
  }

  /** Run the selected lines (or the current line) with live/execute. */
  async runSelection(): Promise<void> {
    try {
      const editor = vscode.window.activeTextEditor;
      if (!editor || editor.document.languageId !== 'python') {
        void vscode.window.showWarningMessage('Select Python code to run it in Revit.');
        return;
      }
      const document = editor.document;
      const selected = editor.selections
        .filter((selection) => !selection.isEmpty)
        .map((selection) => document.getText(selection));
      const code = dedent(
        selected.length > 0 ? selected.join('\n') : document.lineAt(editor.selection.active.line).text,
      );
      if (!code.trim()) {
        void vscode.window.showWarningMessage('Nothing to run.');
        return;
      }

      const cwd = document.isUntitled ? undefined : path.dirname(document.uri.fsPath);
      const client = await this.connection.ensureClient();
      this.output.appendLine('> Running selection in Revit');
      const result = await this.withProgress('Running selection in Revit…', () =>
        client.execute(code, '<selection>', cwd),
      );
      await this.report('Selection', result);
    } catch (error) {
      this.fail(error);
    }
  }

  /**
   * live/reload for one file. `quiet` (reload on save) connects silently if
   * possible and only speaks up when a reload actually fails.
   */
  async reloadFile(document: vscode.TextDocument, options: { quiet: boolean }): Promise<void> {
    if (document.languageId !== 'python' || document.isUntitled) {
      if (!options.quiet) {
        void vscode.window.showWarningMessage('Only saved Python modules can be reloaded in Revit.');
      }
      return;
    }

    let client: LiveClient;
    try {
      client = await this.connection.ensureClient();
    } catch (error) {
      if (options.quiet) {
        this.output.appendLine(`[reload] skipped: ${describeError(error)}`);
      } else {
        this.fail(error);
      }
      return;
    }

    try {
      const result = await client.reload({ paths: [document.uri.fsPath] });
      const { lines, failed } = formatReloadResult(result);
      for (const line of lines) {
        this.output.appendLine(`[reload] ${line}`);
      }
      if (failed.length > 0) {
        const choice = await vscode.window.showWarningMessage(
          `Reload failed in Revit for ${failed.join(', ')}. See the RevitPy output.`,
          'Show Output',
        );
        if (choice === 'Show Output') {
          this.output.show();
        }
      } else if (!options.quiet) {
        void vscode.window.showInformationMessage(lines.join(' '));
      }
    } catch (error) {
      if (options.quiet) {
        this.output.appendLine(`[reload] ${describeError(error)}`);
      } else {
        this.fail(error);
      }
    }
  }

  private withProgress<T>(title: string, task: () => Promise<T>): Promise<T> {
    return Promise.resolve(
      vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title, cancellable: false }, task),
    );
  }

  private async report(label: string, result: ExecutionResult): Promise<void> {
    for (const line of formatExecutionResult(label, result)) {
      this.output.appendLine(line);
    }
    this.connection.refreshStatus().catch(() => undefined);
    if (result.success) {
      if (result.output) {
        this.output.show(true);
      }
      return;
    }
    this.output.show(true);
    const choice = await vscode.window.showErrorMessage(
      `${label} failed in Revit: ${lastErrorLine(result.error)}`,
      'Show Output',
    );
    if (choice === 'Show Output') {
      this.output.show();
    }
  }

  private fail(error: unknown): void {
    const message = describeError(error);
    this.output.appendLine(`[error] ${message}`);
    void vscode.window.showErrorMessage(message);
  }
}
