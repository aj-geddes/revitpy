import * as vscode from 'vscode';
import * as path from 'path';
import { RevitPyConnectionManager } from './connectionManager';
import { PackageManager } from './packageManager';

export class RevitPyTreeProvider implements vscode.TreeDataProvider<TreeItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<TreeItem | undefined | null | void> = new vscode.EventEmitter<TreeItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<TreeItem | undefined | null | void> = this._onDidChangeTreeData.event;

    constructor(
        private context: string,
        private manager: RevitPyConnectionManager | PackageManager
    ) {
        // Listen to manager events
        if (manager instanceof RevitPyConnectionManager) {
            manager.onConnectionChanged(() => this.refresh());
            manager.onHotReloadEvent(() => this.refresh());
        } else if (manager instanceof PackageManager) {
            manager.onPackagesChanged(() => this.refresh());
        }
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: TreeItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: TreeItem): Promise<TreeItem[]> {
        if (!element) {
            return this.getRootItems();
        }

        return element.getChildren ? await element.getChildren() : [];
    }

    private async getRootItems(): Promise<TreeItem[]> {
        switch (this.context) {
            case 'connection':
                return this.getConnectionItems();
            case 'packages':
                return this.getPackageItems();
            default:
                return [];
        }
    }

    private async getConnectionItems(): Promise<TreeItem[]> {
        const connectionManager = this.manager as RevitPyConnectionManager;
        const items: TreeItem[] = [];

        const connection = connectionManager.getConnection();
        
        // Connection status
        const statusItem = new TreeItem(
            connection.isConnected ? 'Connected' : 'Disconnected',
            vscode.TreeItemCollapsibleState.None
        );
        statusItem.iconPath = new vscode.ThemeIcon(
            connection.isConnected ? 'check' : 'x'
        );
        statusItem.contextValue = connection.isConnected ? 'connected' : 'disconnected';
        statusItem.command = {
            command: connection.isConnected ? 'revitpy.disconnectFromRevit' : 'revitpy.connectToRevit',
            title: connection.isConnected ? 'Disconnect' : 'Connect'
        };
        items.push(statusItem);

        if (connection.isConnected) {
            // Connection details
            const detailsItem = new TreeItem('Details', vscode.TreeItemCollapsibleState.Expanded);
            detailsItem.iconPath = new vscode.ThemeIcon('info');
            
            detailsItem.getChildren = async () => {
                const details: TreeItem[] = [];

                // Host and port
                const hostItem = new TreeItem(
                    `Host: ${connection.host}:${connection.port}`,
                    vscode.TreeItemCollapsibleState.None
                );
                hostItem.iconPath = new vscode.ThemeIcon('server');
                details.push(hostItem);

                // Revit version
                if (connection.revitVersion) {
                    const versionItem = new TreeItem(
                        `Revit: ${connection.revitVersion}`,
                        vscode.TreeItemCollapsibleState.None
                    );
                    versionItem.iconPath = new vscode.ThemeIcon('versions');
                    details.push(versionItem);
                }

                // Python version
                if (connection.pythonVersion) {
                    const pythonItem = new TreeItem(
                        `Python: ${connection.pythonVersion}`,
                        vscode.TreeItemCollapsibleState.None
                    );
                    pythonItem.iconPath = new vscode.ThemeIcon('symbol-variable');
                    details.push(pythonItem);
                }

                return details;
            };

            items.push(detailsItem);

            // Actions
            const actionsItem = new TreeItem('Actions', vscode.TreeItemCollapsibleState.Expanded);
            actionsItem.iconPath = new vscode.ThemeIcon('tools');
            
            actionsItem.getChildren = async () => {
                const actions: TreeItem[] = [];

                // Run current script
                const runItem = new TreeItem('Run Current Script', vscode.TreeItemCollapsibleState.None);
                runItem.iconPath = new vscode.ThemeIcon('play');
                runItem.command = {
                    command: 'revitpy.runScript',
                    title: 'Run Current Script'
                };
                actions.push(runItem);

                // Debug current script
                const debugItem = new TreeItem('Debug Current Script', vscode.TreeItemCollapsibleState.None);
                debugItem.iconPath = new vscode.ThemeIcon('debug-alt');
                debugItem.command = {
                    command: 'revitpy.debugScript',
                    title: 'Debug Current Script'
                };
                actions.push(debugItem);

                // Generate stubs
                const stubsItem = new TreeItem('Generate API Stubs', vscode.TreeItemCollapsibleState.None);
                stubsItem.iconPath = new vscode.ThemeIcon('symbol-class');
                stubsItem.command = {
                    command: 'revitpy.generateStubs',
                    title: 'Generate API Stubs'
                };
                actions.push(stubsItem);

                return actions;
            };

            items.push(actionsItem);
        }

        return items;
    }

    private async getPackageItems(): Promise<TreeItem[]> {
        const packageManager = this.manager as PackageManager;
        const items: TreeItem[] = [];

        // Installed packages
        const installedPackages = packageManager.getInstalledPackages();
        if (installedPackages.length > 0) {
            const installedItem = new TreeItem(
                `Installed (${installedPackages.length})`,
                vscode.TreeItemCollapsibleState.Expanded
            );
            installedItem.iconPath = new vscode.ThemeIcon('package');

            installedItem.getChildren = async () => {
                return installedPackages.map(pkg => {
                    const item = new TreeItem(
                        `${pkg.name} v${pkg.version}`,
                        vscode.TreeItemCollapsibleState.None
                    );
                    item.iconPath = new vscode.ThemeIcon('symbol-package');
                    item.tooltip = pkg.description || `${pkg.name} package`;
                    item.contextValue = 'installed-package';
                    return item;
                });
            };

            items.push(installedItem);
        }

        // Available packages (top 5)
        const availablePackages = packageManager.getAvailablePackages()
            .filter(pkg => !pkg.isInstalled)
            .slice(0, 5);

        if (availablePackages.length > 0) {
            const availableItem = new TreeItem(
                'Popular Packages',
                vscode.TreeItemCollapsibleState.Collapsed
            );
            availableItem.iconPath = new vscode.ThemeIcon('cloud-download');

            availableItem.getChildren = async () => {
                return availablePackages.map(pkg => {
                    const item = new TreeItem(
                        `${pkg.name} v${pkg.version}`,
                        vscode.TreeItemCollapsibleState.None
                    );
                    item.iconPath = new vscode.ThemeIcon('symbol-package');
                    item.tooltip = pkg.description || `${pkg.name} package`;
                    item.contextValue = 'available-package';
                    return item;
                });
            };

            items.push(availableItem);
        }

        // Package Manager action
        const managerItem = new TreeItem('Open Package Manager', vscode.TreeItemCollapsibleState.None);
        managerItem.iconPath = new vscode.ThemeIcon('extensions');
        managerItem.command = {
            command: 'revitpy.openPackageManager',
            title: 'Open Package Manager'
        };
        items.push(managerItem);

        return items;
    }
}

export class TreeItem extends vscode.TreeItem {
    public getChildren?: () => Promise<TreeItem[]>;

    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(label, collapsibleState);
        this.tooltip = `${this.label}`;
    }
}