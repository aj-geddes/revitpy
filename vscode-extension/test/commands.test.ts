/**
 * Command logic (run / reload / connect / debug) against the real
 * ConnectionManager and an in-process fake Live Server, with a mocked `vscode`.
 */
import { promises as fs } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as vscode from 'vscode';
import { ConnectionManager } from '../src/connection';
import { attachDebugger, buildAttachConfiguration } from '../src/debug';
import { LiveCommands } from '../src/liveCommands';
import { FakeLiveServer } from './helpers/fakeLiveServer';
import {
  createFakeOutputChannel,
  resetVscodeMock,
  settings,
  window as mockWindow,
  type FakeOutputChannel,
} from './mocks/vscode';

interface FakeSelection {
  isEmpty: boolean;
  active: { line: number };
  text: string;
}

function fakeDocument(
  filePath: string,
  text: string,
  overrides: Partial<{ languageId: string; isUntitled: boolean; isDirty: boolean; save: () => Promise<boolean> }> = {},
) {
  const lines = text.split('\n');
  return {
    languageId: 'python',
    isUntitled: false,
    isDirty: false,
    uri: vscode.Uri.file(filePath),
    getText: (selection?: FakeSelection) => (selection ? selection.text : text),
    save: vi.fn(async () => true),
    lineAt: (line: number) => ({ text: lines[line] }),
    ...overrides,
  };
}

function selection(line: number, text: string): FakeSelection {
  return { isEmpty: text === '', active: { line }, text };
}

function setEditor(document: ReturnType<typeof fakeDocument>, selections: FakeSelection[] = [selection(0, '')]): void {
  mockWindow.activeTextEditor = { document, selections, selection: selections[0] };
}

const asDocument = (document: ReturnType<typeof fakeDocument>) => document as unknown as vscode.TextDocument;
const debugpyExtension = { id: 'ms-python.debugpy' } as unknown as vscode.Extension<unknown>;

describe('LiveCommands and attachDebugger', () => {
  let server: FakeLiveServer;
  let dir: string;
  let discoveryFile: string;
  let scriptPath: string;
  let output: FakeOutputChannel;
  let connection: ConnectionManager;
  let commands: LiveCommands;

  const requests = (method: string) => server.requests.filter((request) => request.method === method);
  const errorMessages = () => vi.mocked(vscode.window.showErrorMessage).mock.calls.map((call) => String(call[0]));
  const warningMessages = () => vi.mocked(vscode.window.showWarningMessage).mock.calls.map((call) => String(call[0]));
  const infoMessages = () => vi.mocked(vscode.window.showInformationMessage).mock.calls.map((call) => String(call[0]));

  beforeEach(async () => {
    resetVscodeMock();
    server = await FakeLiveServer.start();
    dir = await fs.mkdtemp(path.join(os.tmpdir(), 'revitpy-cmd-'));
    discoveryFile = path.join(dir, 'live.json');
    scriptPath = path.join(dir, 'script.py');
    await fs.writeFile(
      discoveryFile,
      JSON.stringify({ protocol: 1, url: server.url, token: server.token, pid: 1, revit_version: '2025' }),
    );
    output = createFakeOutputChannel();
    connection = new ConnectionManager(() => ({ discoveryFile, requestTimeoutMs: 2000, connectTimeoutMs: 2000 }));
    commands = new LiveCommands(connection, output as unknown as vscode.OutputChannel);
  });

  afterEach(async () => {
    await connection.disconnect();
    await server.stop();
    await fs.rm(dir, { recursive: true, force: true });
  });

  describe('runScript', () => {
    it('saves a dirty file, then runs it with live/runFile', async () => {
      const document = fakeDocument(scriptPath, 'print("hi")', { isDirty: true });
      setEditor(document);

      await commands.runScript();

      expect(document.save).toHaveBeenCalledOnce();
      expect(requests('live/runFile').map((r) => r.params)).toEqual([{ path: scriptPath }]);
      expect(output.lines).toContain(`> Running ${scriptPath} in Revit`);
      expect(output.lines.some((line) => line.startsWith('\u2714'))).toBe(true);
      expect(errorMessages()).toEqual([]);
    });

    it('runs the resource passed from the explorer', async () => {
      const document = fakeDocument(scriptPath, 'x = 1');
      vi.mocked(vscode.workspace.openTextDocument).mockResolvedValueOnce(asDocument(document));

      await commands.runScript(vscode.Uri.file(scriptPath));

      expect(requests('live/runFile').map((r) => r.params)).toEqual([{ path: scriptPath }]);
    });

    it('does not run when saving fails', async () => {
      setEditor(fakeDocument(scriptPath, 'x', { isDirty: true, save: vi.fn(async () => false) }));

      await commands.runScript();

      expect(warningMessages()).toEqual(['Save the file before running it in Revit.']);
      expect(requests('live/runFile')).toEqual([]);
    });

    it('refuses non-Python documents', async () => {
      setEditor(fakeDocument(path.join(dir, 'notes.md'), '# hi', { languageId: 'markdown' }));

      await commands.runScript();

      expect(warningMessages()).toEqual(['RevitPy: Run Script only runs Python files.']);
      expect(server.requests).toEqual([]);
    });

    it('runs untitled documents with live/execute', async () => {
      setEditor(fakeDocument('Untitled-1', 'print(1)\n', { isUntitled: true }));

      await commands.runScript();

      expect(requests('live/execute').map((r) => r.params)).toEqual([{ code: 'print(1)\n', filename: '<untitled>' }]);
    });

    it('shows the traceback when the script fails in Revit', async () => {
      server.setHandler('live/runFile', () => ({
        success: false,
        output: 'partial\n',
        error: 'Traceback (most recent call last):\nValueError: boom\n',
        duration_ms: 5,
      }));
      setEditor(fakeDocument(scriptPath, 'raise ValueError("boom")'));

      await commands.runScript();

      expect(vi.mocked(vscode.window.showErrorMessage)).toHaveBeenCalledWith(
        `${scriptPath} failed in Revit: ValueError: boom`,
        'Show Output',
      );
      expect(output.lines).toEqual(expect.arrayContaining(['partial', '--- Error ---', 'ValueError: boom']));
      expect(output.show).toHaveBeenCalled();
    });

    it('explains that the Live Server is not running', async () => {
      await fs.rm(discoveryFile);
      setEditor(fakeDocument(scriptPath, 'x = 1'));

      await commands.runScript();

      expect(errorMessages()).toHaveLength(1);
      expect(errorMessages()[0]).toContain('not running');
      expect(output.lines.some((line) => line.startsWith('[error]'))).toBe(true);
    });
  });

  describe('runSelection', () => {
    it('dedents and joins non-empty selections and runs them next to the file', async () => {
      const document = fakeDocument(scriptPath, 'if True:\n    a = 1\n    print(a)');
      setEditor(document, [selection(1, '    a = 1'), selection(2, '    print(a)')]);

      await commands.runSelection();

      expect(requests('live/execute').map((r) => r.params)).toEqual([
        { code: 'a = 1\nprint(a)\n', filename: '<selection>', cwd: path.dirname(scriptPath) },
      ]);
      expect(output.lines).toContain('> Running selection in Revit');
    });

    it('runs the current line when nothing is selected', async () => {
      setEditor(fakeDocument(scriptPath, 'x = 1\nprint(x)'), [selection(1, '')]);

      await commands.runSelection();

      expect(requests('live/execute')[0].params.code).toBe('print(x)\n');
    });

    it('does nothing on a blank line', async () => {
      setEditor(fakeDocument(scriptPath, '\n'), [selection(0, '')]);

      await commands.runSelection();

      expect(warningMessages()).toEqual(['Nothing to run.']);
      expect(requests('live/execute')).toEqual([]);
    });
  });

  describe('reloadFile', () => {
    it('sends live/reload for the file and reports failures', async () => {
      server.setHandler('live/reload', () => ({
        reloaded: ['pkg.mod'],
        errors: { other: 'Traceback (most recent call last):\nNameError: x' },
      }));

      await commands.reloadFile(asDocument(fakeDocument(scriptPath, '')), { quiet: true });

      expect(requests('live/reload').map((r) => r.params)).toEqual([{ modules: [], paths: [scriptPath] }]);
      expect(output.lines).toContain('[reload] Reloaded: pkg.mod');
      expect(output.lines).toContain('[reload] Reload failed for other: NameError: x');
      expect(warningMessages()).toHaveLength(1);
      expect(warningMessages()[0]).toContain('other');
    });

    it('stays quiet on save when Revit is not running', async () => {
      await fs.rm(discoveryFile);

      await commands.reloadFile(asDocument(fakeDocument(scriptPath, '')), { quiet: true });

      expect(errorMessages()).toEqual([]);
      expect(warningMessages()).toEqual([]);
      expect(output.lines.some((line) => line.startsWith('[reload] skipped:'))).toBe(true);
    });

    it('confirms a manual reload', async () => {
      server.setHandler('live/reload', () => ({ reloaded: ['a'], errors: {} }));

      await commands.reloadFile(asDocument(fakeDocument(scriptPath, '')), { quiet: false });

      expect(infoMessages()).toEqual(['Reloaded: a']);
    });

    it('ignores non-Python files on save', async () => {
      await commands.reloadFile(asDocument(fakeDocument(scriptPath, '', { languageId: 'json' })), { quiet: true });

      expect(server.requests).toEqual([]);
    });
  });

  describe('connect / disconnect / status', () => {
    it('connects, shows the Revit version and document, and disconnects', async () => {
      await commands.connect();
      expect(infoMessages()).toEqual(['Connected to Revit 2025 \u2014 Project1.rvt']);
      expect(connection.isConnected).toBe(true);

      await commands.disconnect();
      expect(infoMessages()[1]).toBe('Disconnected from Revit.');
      expect(connection.isConnected).toBe(false);

      await commands.disconnect();
      expect(infoMessages()[2]).toBe('Not connected to Revit.');
    });

    it('prints the status summary', async () => {
      await commands.showStatus();

      expect(output.lines).toContain(`Server:     ${server.url}`);
      expect(output.lines).toContain('Revit:      2025');
      expect(output.lines).toContain('Document:   Project1.rvt');
    });
  });

  describe('attachDebugger', () => {
    it('asks for the Python Debugger extension when it is missing', async () => {
      const attached = await attachDebugger(connection, output as unknown as vscode.OutputChannel);

      expect(attached).toBe(false);
      expect(errorMessages()[0]).toContain('ms-python.debugpy');
      expect(requests('debug/start')).toEqual([]);
    });

    it('starts debugpy in Revit and attaches to the port it reports', async () => {
      vi.mocked(vscode.extensions.getExtension).mockReturnValue(debugpyExtension);
      settings.set('revitpy.debugPort', 5690);

      const attached = await attachDebugger(connection, output as unknown as vscode.OutputChannel);

      expect(attached).toBe(true);
      expect(requests('debug/start').map((r) => r.params)).toEqual([{ port: 5690 }]);
      expect(vi.mocked(vscode.debug.startDebugging)).toHaveBeenCalledWith(undefined, {
        type: 'debugpy',
        request: 'attach',
        name: 'Attach to Revit (RevitPy)',
        connect: { host: '127.0.0.1', port: 5690 },
        justMyCode: false,
      });
    });

    it('reports when debugpy is not installed in Revit', async () => {
      vi.mocked(vscode.extensions.getExtension).mockReturnValue(debugpyExtension);
      server.setHandler('debug/start', () => ({
        listening: false,
        error: 'debugpy is not installed in the Revit Python environment (pip install debugpy)',
      }));

      const attached = await attachDebugger(connection, output as unknown as vscode.OutputChannel);

      expect(attached).toBe(false);
      expect(vscode.debug.startDebugging).not.toHaveBeenCalled();
      expect(errorMessages()[0]).toContain('debugpy is not installed');
    });

    it('builds attach configurations with optional path mappings', () => {
      expect(
        buildAttachConfiguration(5678, { pathMappings: [{ localRoot: '/a', remoteRoot: 'C:/a' }], justMyCode: true }),
      ).toMatchObject({ pathMappings: [{ localRoot: '/a', remoteRoot: 'C:/a' }], justMyCode: true });
      expect(buildAttachConfiguration(5678, { pathMappings: [] })).not.toHaveProperty('pathMappings');
    });
  });
});
