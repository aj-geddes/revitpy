import * as vscode from 'vscode';
import * as path from 'path';
import { Logger } from '../common/logger';
import { PackageInfo, RevitPyConfig } from '../common/types';
import axios from 'axios';

export class PackageManager implements vscode.Disposable {
    private readonly packageRegistryUrl = 'https://registry.revitpy.com';
    private installedPackages: Map<string, PackageInfo> = new Map();
    private availablePackages: PackageInfo[] = [];
    private webviewPanel?: vscode.WebviewPanel;

    private readonly onPackagesChangedEmitter = new vscode.EventEmitter<void>();
    public readonly onPackagesChanged = this.onPackagesChangedEmitter.event;

    constructor(private logger: Logger) {
        this.loadInstalledPackages();
    }

    async openPackageManager(): Promise<void> {
        if (this.webviewPanel) {
            this.webviewPanel.reveal();
            return;
        }

        this.webviewPanel = vscode.window.createWebviewPanel(
            'revitpyPackageManager',
            'RevitPy Package Manager',
            vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    vscode.Uri.file(path.join(__dirname, '..', '..', 'resources'))
                ]
            }
        );

        this.webviewPanel.webview.html = await this.getPackageManagerHtml();

        // Handle messages from webview
        this.webviewPanel.webview.onDidReceiveMessage(
            async message => {
                switch (message.command) {
                    case 'installPackage':
                        await this.installPackage(message.packageName, message.version);
                        break;
                    case 'uninstallPackage':
                        await this.uninstallPackage(message.packageName);
                        break;
                    case 'searchPackages':
                        await this.searchPackages(message.query);
                        break;
                    case 'refreshPackages':
                        await this.refreshPackages();
                        break;
                }
            },
            undefined,
            []
        );

        this.webviewPanel.onDidDispose(() => {
            this.webviewPanel = undefined;
        });

        // Load packages data
        await this.refreshPackages();
    }

    private async getPackageManagerHtml(): Promise<string> {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RevitPy Package Manager</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
            padding: 20px;
            margin: 0;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }

        .search-container {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }

        #searchInput {
            flex: 1;
            padding: 8px;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border: 1px solid var(--vscode-input-border);
            border-radius: 3px;
        }

        .btn {
            padding: 8px 16px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            border-radius: 3px;
            cursor: pointer;
            font-size: 13px;
        }

        .btn:hover {
            background: var(--vscode-button-hoverBackground);
        }

        .btn-secondary {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }

        .btn-secondary:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }

        .tabs {
            display: flex;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }

        .tab {
            padding: 10px 20px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            color: var(--vscode-tab-inactiveForeground);
        }

        .tab.active {
            color: var(--vscode-tab-activeForeground);
            border-bottom-color: var(--vscode-focusBorder);
        }

        .package-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .package-item {
            background: var(--vscode-panel-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 5px;
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }

        .package-info {
            flex: 1;
        }

        .package-name {
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 5px;
            color: var(--vscode-symbolIcon-classForeground);
        }

        .package-version {
            color: var(--vscode-descriptionForeground);
            font-size: 12px;
            margin-bottom: 5px;
        }

        .package-description {
            color: var(--vscode-foreground);
            margin-bottom: 10px;
            line-height: 1.4;
        }

        .package-meta {
            font-size: 12px;
            color: var(--vscode-descriptionForeground);
            display: flex;
            gap: 15px;
        }

        .package-actions {
            display: flex;
            flex-direction: column;
            gap: 8px;
            min-width: 120px;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: var(--vscode-descriptionForeground);
        }

        .error {
            background: var(--vscode-inputValidation-errorBackground);
            border: 1px solid var(--vscode-inputValidation-errorBorder);
            color: var(--vscode-inputValidation-errorForeground);
            padding: 10px;
            border-radius: 3px;
            margin-bottom: 20px;
        }

        .tag {
            background: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
            margin-right: 5px;
        }

        .status-installed {
            color: var(--vscode-testing-iconPassed);
        }

        .status-update-available {
            color: var(--vscode-testing-iconQueued);
        }

        #tabContent {
            min-height: 400px;
        }

        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--vscode-descriptionForeground);
        }

        .empty-state h3 {
            margin-bottom: 10px;
            color: var(--vscode-foreground);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>RevitPy Package Manager</h1>
        <button class="btn" onclick="refreshPackages()">Refresh</button>
    </div>

    <div class="search-container">
        <input type="text" id="searchInput" placeholder="Search packages..." onkeyup="handleSearch()">
        <button class="btn btn-secondary" onclick="searchPackages()">Search</button>
    </div>

    <div class="tabs">
        <div class="tab active" onclick="showTab('installed')">Installed</div>
        <div class="tab" onclick="showTab('available')">Browse</div>
        <div class="tab" onclick="showTab('updates')">Updates</div>
    </div>

    <div id="tabContent">
        <div class="loading">Loading packages...</div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let currentTab = 'installed';
        let installedPackages = [];
        let availablePackages = [];
        let packagesWithUpdates = [];

        function showTab(tabName) {
            currentTab = tabName;
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            event.target.classList.add('active');
            updateContent();
        }

        function updateContent() {
            const content = document.getElementById('tabContent');

            switch(currentTab) {
                case 'installed':
                    renderPackages(installedPackages, 'No packages installed yet.');
                    break;
                case 'available':
                    renderPackages(availablePackages, 'No packages available.');
                    break;
                case 'updates':
                    renderPackages(packagesWithUpdates, 'All packages are up to date.');
                    break;
            }
        }

        function renderPackages(packages, emptyMessage) {
            const content = document.getElementById('tabContent');

            if (packages.length === 0) {
                content.innerHTML = \`
                    <div class="empty-state">
                        <h3>\${emptyMessage}</h3>
                        <p>Use the Browse tab to discover packages.</p>
                    </div>
                \`;
                return;
            }

            const packageList = packages.map(pkg => \`
                <div class="package-item">
                    <div class="package-info">
                        <div class="package-name">\${pkg.name}</div>
                        <div class="package-version">
                            v\${pkg.version}
                            \${pkg.isInstalled ? '<span class="tag status-installed">INSTALLED</span>' : ''}
                            \${pkg.installedVersion && pkg.installedVersion !== pkg.version ? '<span class="tag status-update-available">UPDATE AVAILABLE</span>' : ''}
                        </div>
                        <div class="package-description">\${pkg.description || 'No description available'}</div>
                        <div class="package-meta">
                            \${pkg.author ? \`<span>by \${pkg.author}</span>\` : ''}
                            \${pkg.downloads ? \`<span>\${pkg.downloads} downloads</span>\` : ''}
                            \${pkg.license ? \`<span>\${pkg.license}</span>\` : ''}
                        </div>
                    </div>
                    <div class="package-actions">
                        \${renderPackageActions(pkg)}
                    </div>
                </div>
            \`).join('');

            content.innerHTML = \`<div class="package-list">\${packageList}</div>\`;
        }

        function renderPackageActions(pkg) {
            if (pkg.isInstalled) {
                const actions = [\`<button class="btn btn-secondary" onclick="uninstallPackage('\${pkg.name}')">Uninstall</button>\`];

                if (pkg.installedVersion && pkg.installedVersion !== pkg.version) {
                    actions.unshift(\`<button class="btn" onclick="installPackage('\${pkg.name}', '\${pkg.version}')">Update</button>\`);
                }

                return actions.join('');
            } else {
                return \`<button class="btn" onclick="installPackage('\${pkg.name}', '\${pkg.version}')">Install</button>\`;
            }
        }

        function installPackage(name, version) {
            vscode.postMessage({
                command: 'installPackage',
                packageName: name,
                version: version
            });
        }

        function uninstallPackage(name) {
            vscode.postMessage({
                command: 'uninstallPackage',
                packageName: name
            });
        }

        function searchPackages() {
            const query = document.getElementById('searchInput').value;
            vscode.postMessage({
                command: 'searchPackages',
                query: query
            });
        }

        function refreshPackages() {
            vscode.postMessage({
                command: 'refreshPackages'
            });
        }

        function handleSearch() {
            const query = document.getElementById('searchInput').value;
            if (query.length >= 3) {
                searchPackages();
            }
        }

        // Handle messages from extension
        window.addEventListener('message', event => {
            const message = event.data;

            switch (message.type) {
                case 'packagesData':
                    installedPackages = message.installed || [];
                    availablePackages = message.available || [];
                    packagesWithUpdates = message.updates || [];
                    updateContent();
                    break;
                case 'error':
                    document.getElementById('tabContent').innerHTML = \`
                        <div class="error">
                            Error: \${message.message}
                        </div>
                    \`;
                    break;
            }
        });
    </script>
</body>
</html>`;
    }

    async refreshPackages(): Promise<void> {
        try {
            await Promise.all([
                this.loadInstalledPackages(),
                this.loadAvailablePackages()
            ]);

            this.sendPackageDataToWebview();
            this.onPackagesChangedEmitter.fire();
            this.logger.info('Package data refreshed successfully');
        } catch (error) {
            this.logger.error('Failed to refresh packages', error);
            this.sendErrorToWebview(`Failed to refresh packages: ${error}`);
        }
    }

    private async loadInstalledPackages(): Promise<void> {
        this.installedPackages.clear();

        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) return;

        for (const folder of workspaceFolders) {
            try {
                const configPath = path.join(folder.uri.fsPath, 'revitpy.json');
                const configUri = vscode.Uri.file(configPath);

                const configData = await vscode.workspace.fs.readFile(configUri);
                const config: RevitPyConfig = JSON.parse(configData.toString());

                if (config.dependencies) {
                    for (const [name, version] of Object.entries(config.dependencies)) {
                        this.installedPackages.set(name, {
                            name,
                            version,
                            isInstalled: true,
                            installedVersion: version
                        });
                    }
                }
            } catch (error) {
                // Config file doesn't exist or is invalid, skip
            }
        }
    }

    private async loadAvailablePackages(): Promise<void> {
        try {
            const response = await axios.get(`${this.packageRegistryUrl}/packages`, {
                timeout: 10000,
                headers: {
                    'Accept': 'application/json'
                }
            });

            this.availablePackages = response.data.map((pkg: any) => ({
                ...pkg,
                isInstalled: this.installedPackages.has(pkg.name),
                installedVersion: this.installedPackages.get(pkg.name)?.version
            }));
        } catch (error) {
            this.logger.warn('Failed to load available packages from registry', error);
            // Use fallback packages if registry is unavailable
            this.availablePackages = this.getFallbackPackages();
        }
    }

    private getFallbackPackages(): PackageInfo[] {
        return [
            {
                name: 'revitpy-utils',
                version: '1.0.0',
                description: 'Common utilities for RevitPy development',
                author: 'RevitPy Team',
                keywords: ['utilities', 'helpers'],
                license: 'MIT'
            },
            {
                name: 'revitpy-geometry',
                version: '2.1.0',
                description: 'Advanced geometry operations for Revit',
                author: 'RevitPy Team',
                keywords: ['geometry', 'math'],
                license: 'MIT'
            },
            {
                name: 'revitpy-ui',
                version: '1.5.0',
                description: 'UI components and helpers for Revit add-ins',
                author: 'RevitPy Team',
                keywords: ['ui', 'forms'],
                license: 'MIT'
            }
        ];
    }

    async installPackage(packageName: string, version?: string): Promise<boolean> {
        try {
            this.logger.info(`Installing package: ${packageName}@${version || 'latest'}`);

            // Find the package info
            const packageInfo = this.availablePackages.find(pkg => pkg.name === packageName);
            if (!packageInfo) {
                throw new Error(`Package not found: ${packageName}`);
            }

            const installVersion = version || packageInfo.version;

            // Update the project configuration
            await this.updateProjectConfig(packageName, installVersion);

            // Mark as installed
            this.installedPackages.set(packageName, {
                ...packageInfo,
                version: installVersion,
                isInstalled: true,
                installedVersion: installVersion
            });

            // Update available packages list
            this.availablePackages = this.availablePackages.map(pkg =>
                pkg.name === packageName
                    ? { ...pkg, isInstalled: true, installedVersion: installVersion }
                    : pkg
            );

            this.sendPackageDataToWebview();
            this.onPackagesChangedEmitter.fire();

            vscode.window.showInformationMessage(`Successfully installed ${packageName}@${installVersion}`);
            return true;
        } catch (error) {
            this.logger.error(`Failed to install package ${packageName}`, error);
            vscode.window.showErrorMessage(`Failed to install ${packageName}: ${error}`);
            return false;
        }
    }

    async uninstallPackage(packageName: string): Promise<boolean> {
        try {
            this.logger.info(`Uninstalling package: ${packageName}`);

            // Update the project configuration
            await this.removeFromProjectConfig(packageName);

            // Remove from installed packages
            this.installedPackages.delete(packageName);

            // Update available packages list
            this.availablePackages = this.availablePackages.map(pkg =>
                pkg.name === packageName
                    ? { ...pkg, isInstalled: false, installedVersion: undefined }
                    : pkg
            );

            this.sendPackageDataToWebview();
            this.onPackagesChangedEmitter.fire();

            vscode.window.showInformationMessage(`Successfully uninstalled ${packageName}`);
            return true;
        } catch (error) {
            this.logger.error(`Failed to uninstall package ${packageName}`, error);
            vscode.window.showErrorMessage(`Failed to uninstall ${packageName}: ${error}`);
            return false;
        }
    }

    private async updateProjectConfig(packageName: string, version: string): Promise<void> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            throw new Error('No workspace folder found');
        }

        const configPath = path.join(workspaceFolder.uri.fsPath, 'revitpy.json');
        const configUri = vscode.Uri.file(configPath);

        let config: RevitPyConfig;
        try {
            const configData = await vscode.workspace.fs.readFile(configUri);
            config = JSON.parse(configData.toString());
        } catch {
            // Create new config if it doesn't exist
            config = {
                name: workspaceFolder.name,
                version: '1.0.0',
                dependencies: {}
            };
        }

        if (!config.dependencies) {
            config.dependencies = {};
        }

        config.dependencies[packageName] = version;

        await vscode.workspace.fs.writeFile(
            configUri,
            Buffer.from(JSON.stringify(config, null, 2))
        );
    }

    private async removeFromProjectConfig(packageName: string): Promise<void> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            throw new Error('No workspace folder found');
        }

        const configPath = path.join(workspaceFolder.uri.fsPath, 'revitpy.json');
        const configUri = vscode.Uri.file(configPath);

        try {
            const configData = await vscode.workspace.fs.readFile(configUri);
            const config: RevitPyConfig = JSON.parse(configData.toString());

            if (config.dependencies && config.dependencies[packageName]) {
                delete config.dependencies[packageName];

                await vscode.workspace.fs.writeFile(
                    configUri,
                    Buffer.from(JSON.stringify(config, null, 2))
                );
            }
        } catch (error) {
            this.logger.warn(`Could not update project config: ${error}`);
        }
    }

    private async searchPackages(query: string): Promise<void> {
        try {
            const response = await axios.get(`${this.packageRegistryUrl}/search`, {
                params: { q: query },
                timeout: 10000
            });

            this.availablePackages = response.data.map((pkg: any) => ({
                ...pkg,
                isInstalled: this.installedPackages.has(pkg.name),
                installedVersion: this.installedPackages.get(pkg.name)?.version
            }));

            this.sendPackageDataToWebview();
        } catch (error) {
            this.logger.error('Failed to search packages', error);
            this.sendErrorToWebview(`Search failed: ${error}`);
        }
    }

    private sendPackageDataToWebview(): void {
        if (this.webviewPanel) {
            const packagesWithUpdates = this.availablePackages.filter(pkg =>
                pkg.isInstalled && pkg.installedVersion && pkg.installedVersion !== pkg.version
            );

            this.webviewPanel.webview.postMessage({
                type: 'packagesData',
                installed: Array.from(this.installedPackages.values()),
                available: this.availablePackages,
                updates: packagesWithUpdates
            });
        }
    }

    private sendErrorToWebview(message: string): void {
        if (this.webviewPanel) {
            this.webviewPanel.webview.postMessage({
                type: 'error',
                message
            });
        }
    }

    getInstalledPackages(): PackageInfo[] {
        return Array.from(this.installedPackages.values());
    }

    getAvailablePackages(): PackageInfo[] {
        return this.availablePackages;
    }

    dispose(): void {
        this.webviewPanel?.dispose();
        this.onPackagesChangedEmitter.dispose();
    }
}
