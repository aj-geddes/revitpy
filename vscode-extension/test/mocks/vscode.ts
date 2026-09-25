/**
 * Minimal stand-in for the `vscode` module (aliased in vitest.config.mts).
 * Only what the extension's command code touches; tests configure it with
 * vi.mocked(...) and `resetVscodeMock()`.
 */
import { vi } from 'vitest';

export class Uri {
  private constructor(
    readonly scheme: string,
    readonly fsPath: string,
  ) {}

  static file(fsPath: string): Uri {
    return new Uri('file', fsPath);
  }

  toString(): string {
    return `${this.scheme}://${this.fsPath}`;
  }
}

export const ProgressLocation = { SourceControl: 1, Window: 10, Notification: 15 } as const;
export const StatusBarAlignment = { Left: 1, Right: 2 } as const;
export const ConfigurationTarget = { Global: 1, Workspace: 2, WorkspaceFolder: 3 } as const;

export interface FakeOutputChannel {
  lines: string[];
  appendLine: (line: string) => void;
  show: ReturnType<typeof vi.fn>;
  dispose: ReturnType<typeof vi.fn>;
}

export function createFakeOutputChannel(): FakeOutputChannel {
  const lines: string[] = [];
  return {
    lines,
    appendLine: (line: string) => {
      lines.push(line);
    },
    show: vi.fn(),
    dispose: vi.fn(),
  };
}

/** Settings returned by workspace.getConfiguration(section).get(key). */
export const settings = new Map<string, unknown>();
/** Calls to WorkspaceConfiguration.update: [section.key, value, target]. */
export const settingUpdates: Array<[string, unknown, unknown]> = [];

function configuration(section: string) {
  const key = (name: string): string => (section ? `${section}.${name}` : name);
  return {
    get: <T>(name: string, defaultValue?: T): T | undefined =>
      settings.has(key(name)) ? (settings.get(key(name)) as T) : defaultValue,
    update: vi.fn(async (name: string, value: unknown, target?: unknown) => {
      settingUpdates.push([key(name), value, target]);
      settings.set(key(name), value);
    }),
  };
}

export const window = {
  activeTextEditor: undefined as unknown,
  showInformationMessage: vi.fn(async (..._args: unknown[]): Promise<string | undefined> => undefined),
  showWarningMessage: vi.fn(async (..._args: unknown[]): Promise<string | undefined> => undefined),
  showErrorMessage: vi.fn(async (..._args: unknown[]): Promise<string | undefined> => undefined),
  showOpenDialog: vi.fn(async (..._args: unknown[]): Promise<Uri[] | undefined> => undefined),
  showInputBox: vi.fn(async (..._args: unknown[]): Promise<string | undefined> => undefined),
  showQuickPick: vi.fn(async (..._args: unknown[]): Promise<unknown> => undefined),
  withProgress: vi.fn(async (_options: unknown, task: () => Promise<unknown>) => task()),
  createOutputChannel: vi.fn(() => createFakeOutputChannel()),
};

export const workspace = {
  workspaceFolders: undefined as Array<{ uri: Uri; name: string; index: number }> | undefined,
  getConfiguration: vi.fn((section = '') => configuration(section)),
  openTextDocument: vi.fn(async (_uri: Uri): Promise<unknown> => undefined),
  asRelativePath: vi.fn((pathOrUri: Uri | string) => (typeof pathOrUri === 'string' ? pathOrUri : pathOrUri.fsPath)),
};

export const extensions = {
  getExtension: vi.fn((_id: string): unknown => undefined),
};

export const commands = {
  executeCommand: vi.fn(async (..._args: unknown[]): Promise<unknown> => undefined),
  registerCommand: vi.fn(),
};

export const debug = {
  startDebugging: vi.fn(async (..._args: unknown[]): Promise<boolean> => true),
};

export function resetVscodeMock(): void {
  settings.clear();
  settingUpdates.length = 0;
  window.activeTextEditor = undefined;
  workspace.workspaceFolders = undefined;
  for (const fn of [
    window.showInformationMessage,
    window.showWarningMessage,
    window.showErrorMessage,
    window.showOpenDialog,
    window.showInputBox,
    window.showQuickPick,
    window.withProgress,
    workspace.openTextDocument,
    extensions.getExtension,
    commands.executeCommand,
    debug.startDebugging,
  ]) {
    fn.mockClear();
  }
  window.showInformationMessage.mockImplementation(async () => undefined);
  window.showWarningMessage.mockImplementation(async () => undefined);
  window.showErrorMessage.mockImplementation(async () => undefined);
  window.showOpenDialog.mockImplementation(async () => undefined);
  extensions.getExtension.mockImplementation(() => undefined);
  debug.startDebugging.mockImplementation(async () => true);
}
