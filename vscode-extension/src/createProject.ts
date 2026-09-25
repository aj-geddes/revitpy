/** RevitPy: Create Project — runs `revitpy-dev create project` in a task terminal. */
import { spawn } from 'node:child_process';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import * as vscode from 'vscode';
import { isValidProjectName, shellQuote } from './format';

/** Built-in templates of the dev CLI (cli/templates). */
export const TEMPLATES = [
  { label: 'basic-script', description: 'A RevitPy script project' },
  { label: 'addin', description: 'A RevitPy add-in project' },
] as const;

export const DEV_CLI_INSTALL_HINT =
  'Install the RevitPy dev CLI (Python 3.11+): pip install ./cli from a RevitPy checkout, ' +
  'then make sure revitpy-dev is on PATH or set revitpy.devCliPath.';

/** Arguments after the executable: `create project NAME --template T --output DIR`. */
export function buildCreateArgs(name: string, template: string, parentDir: string): string[] {
  return ['create', 'project', name, '--template', template, '--output', parentDir];
}

/** Human-readable command line (for the output channel). */
export function buildCreateCommand(
  cli: string,
  name: string,
  template: string,
  parentDir: string,
  platform: NodeJS.Platform = process.platform,
): string {
  return [cli, ...buildCreateArgs(name, template, parentDir)].map((arg) => shellQuote(arg, platform)).join(' ');
}

export function isCliAvailable(cli: string): Promise<boolean> {
  return new Promise((resolve) => {
    let done = false;
    const finish = (value: boolean): void => {
      if (!done) {
        done = true;
        clearTimeout(timer);
        resolve(value);
      }
    };
    const child = spawn(cli, ['--version'], { shell: false, windowsHide: true, stdio: 'ignore' });
    const timer = setTimeout(() => {
      child.kill();
      finish(false);
    }, 15_000);
    child.on('error', () => finish(false));
    child.on('close', (code) => finish(code === 0));
  });
}

export async function createProject(output: vscode.OutputChannel): Promise<void> {
  const cli = vscode.workspace.getConfiguration('revitpy').get<string>('devCliPath', 'revitpy-dev') || 'revitpy-dev';
  if (!(await isCliAvailable(cli))) {
    output.appendLine(`[create] ${cli} not found. ${DEV_CLI_INSTALL_HINT}`);
    const choice = await vscode.window.showErrorMessage(
      `RevitPy dev CLI (${cli}) was not found.`,
      'Show Install Instructions',
    );
    if (choice === 'Show Install Instructions') {
      output.show();
    }
    return;
  }

  const rawName = await vscode.window.showInputBox({
    title: 'New RevitPy project',
    prompt: 'Project name',
    validateInput: (value) => isValidProjectName(value.trim()) ?? null,
  });
  if (rawName === undefined) {
    return;
  }
  const name = rawName.trim();

  const template = await vscode.window.showQuickPick(
    TEMPLATES.map((t) => ({ label: t.label, description: t.description })),
    { title: 'Project template' },
  );
  if (!template) {
    return;
  }

  const picked = await vscode.window.showOpenDialog({
    canSelectFiles: false,
    canSelectFolders: true,
    canSelectMany: false,
    openLabel: 'Create project here',
    defaultUri: vscode.workspace.workspaceFolders?.[0]?.uri,
  });
  if (!picked || picked.length === 0) {
    return;
  }
  const parentDir = picked[0].fsPath;

  output.appendLine(`[create] ${buildCreateCommand(cli, name, template.label, parentDir)}`);
  const task = new vscode.Task(
    { type: 'revitpy', task: 'create-project' },
    vscode.workspace.workspaceFolders?.length ? vscode.TaskScope.Workspace : vscode.TaskScope.Global,
    `Create ${name}`,
    'RevitPy',
    // Argument form: VS Code quotes each argument for the user's shell.
    new vscode.ShellExecution(cli, buildCreateArgs(name, template.label, parentDir), { cwd: parentDir }),
  );
  task.presentationOptions = {
    reveal: vscode.TaskRevealKind.Always,
    focus: true,
    panel: vscode.TaskPanelKind.New,
  };

  let execution: vscode.TaskExecution | undefined;
  const listener = vscode.tasks.onDidEndTaskProcess(async (event) => {
    const ours = execution
      ? event.execution === execution
      : event.execution.task.source === 'RevitPy' && event.execution.task.name === task.name;
    if (!ours) {
      return;
    }
    listener.dispose();
    if (event.exitCode !== 0) {
      void vscode.window.showErrorMessage(
        `Creating ${name} failed (exit code ${event.exitCode ?? 'unknown'}). See the terminal.`,
      );
      return;
    }
    const projectDir = path.join(parentDir, name);
    const exists = await fs.stat(projectDir).then(
      (stat) => stat.isDirectory(),
      () => false,
    );
    const target = vscode.Uri.file(exists ? projectDir : parentDir);
    const choice = await vscode.window.showInformationMessage(
      `Created RevitPy project ${name}.`,
      'Open Folder',
      'Add to Workspace',
    );
    if (choice === 'Open Folder') {
      await vscode.commands.executeCommand('vscode.openFolder', target, { forceNewWindow: false });
    } else if (choice === 'Add to Workspace') {
      vscode.workspace.updateWorkspaceFolders(vscode.workspace.workspaceFolders?.length ?? 0, 0, { uri: target });
    }
  });

  try {
    execution = await vscode.tasks.executeTask(task);
  } catch (error) {
    listener.dispose();
    const message = error instanceof Error ? error.message : String(error);
    void vscode.window.showErrorMessage(`Could not start ${cli}: ${message}`);
  }
}
