/**
 * Revit API IntelliSense: point Pylance at a folder of Revit API `.pyi` stubs.
 *
 * No maintained stub package for current Revit versions is published on PyPI,
 * so the stubs are generated locally from the user's own RevitAPI.dll (for
 * example with pythonnet-stub-generator) and this command wires the folder up.
 */
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import * as vscode from 'vscode';
import { mergeExtraPaths, removeExtraPath } from './format';

/** True when `folder` contains an `Autodesk` package directory. */
export async function looksLikeStubsFolder(folder: string): Promise<boolean> {
  try {
    return (await fs.stat(path.join(folder, 'Autodesk'))).isDirectory();
  } catch {
    return false;
  }
}

export async function configureStubs(output: vscode.OutputChannel): Promise<void> {
  const picked = await vscode.window.showOpenDialog({
    canSelectFiles: false,
    canSelectFolders: true,
    canSelectMany: false,
    openLabel: 'Use as Revit API stubs',
    title: 'Select the folder that contains the Autodesk stub package',
  });
  if (!picked || picked.length === 0) {
    return;
  }
  const folder = picked[0].fsPath;

  if (!(await looksLikeStubsFolder(folder))) {
    const choice = await vscode.window.showWarningMessage(
      `${folder} has no Autodesk/ subfolder, so imports like Autodesk.Revit.DB will not resolve from it. Use it anyway?`,
      { modal: true },
      'Use Anyway',
    );
    if (choice !== 'Use Anyway') {
      return;
    }
  }

  try {
    const target = vscode.workspace.workspaceFolders?.length
      ? vscode.ConfigurationTarget.Workspace
      : vscode.ConfigurationTarget.Global;
    const revitpy = vscode.workspace.getConfiguration('revitpy');
    const previous = revitpy.get<string>('stubsPath', '');
    const analysis = vscode.workspace.getConfiguration('python.analysis');

    let extraPaths: unknown = analysis.get<unknown>('extraPaths');
    if (previous && previous !== folder) {
      extraPaths = removeExtraPath(extraPaths, previous);
    }
    await analysis.update('extraPaths', mergeExtraPaths(extraPaths, folder), target);
    await revitpy.update('stubsPath', folder, target);

    output.appendLine(`[stubs] python.analysis.extraPaths now includes ${folder}`);
    void vscode.window.showInformationMessage(
      `Revit API stubs configured: ${folder}. Pylance may take a moment to re-index.`,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    void vscode.window.showErrorMessage(`Could not update settings: ${message}`);
  }
}
