import { promises as fs } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as vscode from 'vscode';
import { configureStubs, looksLikeStubsFolder } from '../src/stubs';
import {
  createFakeOutputChannel,
  resetVscodeMock,
  settings,
  settingUpdates,
  window as mockWindow,
  workspace as mockWorkspace,
} from './mocks/vscode';

describe('Revit API stubs', () => {
  let dir: string;
  let stubsDir: string;
  const output = createFakeOutputChannel() as unknown as vscode.OutputChannel;

  beforeEach(async () => {
    resetVscodeMock();
    dir = await fs.mkdtemp(path.join(os.tmpdir(), 'revitpy-stubs-'));
    stubsDir = path.join(dir, 'stubs');
    await fs.mkdir(path.join(stubsDir, 'Autodesk', 'Revit', 'DB'), { recursive: true });
    mockWorkspace.workspaceFolders = [{ uri: vscode.Uri.file(dir), name: 'w', index: 0 }];
  });

  afterEach(async () => {
    await fs.rm(dir, { recursive: true, force: true });
  });

  const pick = (folder: string) => vi.mocked(vscode.window.showOpenDialog).mockResolvedValueOnce([vscode.Uri.file(folder)]);

  it('recognises a folder with an Autodesk package', async () => {
    expect(await looksLikeStubsFolder(stubsDir)).toBe(true);
    expect(await looksLikeStubsFolder(dir)).toBe(false);
    expect(await looksLikeStubsFolder(path.join(dir, 'missing'))).toBe(false);
    const fileNotDir = path.join(dir, 'file-case');
    await fs.mkdir(fileNotDir);
    await fs.writeFile(path.join(fileNotDir, 'Autodesk'), '');
    expect(await looksLikeStubsFolder(fileNotDir)).toBe(false);
  });

  it('does nothing when the dialog is cancelled', async () => {
    await configureStubs(output);
    expect(settingUpdates).toEqual([]);
  });

  it('adds the folder to python.analysis.extraPaths in the workspace', async () => {
    settings.set('python.analysis.extraPaths', ['existing']);
    pick(stubsDir);

    await configureStubs(output);

    expect(settingUpdates).toEqual([
      ['python.analysis.extraPaths', ['existing', stubsDir], vscode.ConfigurationTarget.Workspace],
      ['revitpy.stubsPath', stubsDir, vscode.ConfigurationTarget.Workspace],
    ]);
    expect(vscode.window.showInformationMessage).toHaveBeenCalledOnce();
  });

  it('replaces the previously configured folder', async () => {
    settings.set('revitpy.stubsPath', '/old/stubs');
    settings.set('python.analysis.extraPaths', ['x', '/old/stubs']);
    pick(stubsDir);

    await configureStubs(output);

    expect(settings.get('python.analysis.extraPaths')).toEqual(['x', stubsDir]);
  });

  it('writes user settings when no folder is open', async () => {
    mockWorkspace.workspaceFolders = undefined;
    pick(stubsDir);

    await configureStubs(output);

    expect(settingUpdates.map((update) => update[2])).toEqual([
      vscode.ConfigurationTarget.Global,
      vscode.ConfigurationTarget.Global,
    ]);
  });

  it('asks before using a folder without an Autodesk package', async () => {
    pick(dir);
    await configureStubs(output);
    expect(settingUpdates).toEqual([]);

    pick(dir);
    mockWindow.showWarningMessage.mockResolvedValueOnce('Use Anyway');
    await configureStubs(output);
    expect(settings.get('revitpy.stubsPath')).toBe(dir);
  });
});
