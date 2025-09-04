import * as fs from 'fs/promises';
import * as path from 'path';
import { Connection, Location, Range } from 'vscode-languageserver/node';
import { ApiDocumentation } from '../common/types';

export class StubsManager {
    private stubsPath?: string;
    private apiDocumentation: ApiDocumentation[] = [];
    private definitionCache: Map<string, Location> = new Map();

    constructor(private connection: Connection) {}

    async initialize(): Promise<void> {
        await this.loadConfiguration();
        await this.loadStubs();
    }

    private async loadConfiguration(): Promise<void> {
        try {
            const config = await this.connection.workspace.getConfiguration('revitpy');
            this.stubsPath = config.stubsPath;
            
            if (!this.stubsPath) {
                // Try to find stubs in common locations
                this.stubsPath = await this.findStubsPath();
            }
            
            this.connection.console.log(`Using stubs path: ${this.stubsPath || 'not found'}`);
        } catch (error) {
            this.connection.console.error(`Failed to load configuration: ${error}`);
        }
    }

    private async findStubsPath(): Promise<string | undefined> {
        const commonPaths = [
            path.join(process.env.HOME || '', '.revitpy', 'stubs'),
            path.join(process.env.APPDATA || '', 'RevitPy', 'stubs'),
            path.join(__dirname, '..', '..', 'resources', 'stubs'),
            '/usr/local/share/revitpy/stubs',
            '/opt/revitpy/stubs'
        ];

        for (const stubsPath of commonPaths) {
            try {
                const stat = await fs.stat(stubsPath);
                if (stat.isDirectory()) {
                    return stubsPath;
                }
            } catch {
                // Path doesn't exist, continue
            }
        }

        return undefined;
    }

    private async loadStubs(): Promise<void> {
        if (!this.stubsPath) {
            this.connection.console.warn('No stubs path configured, generating default API documentation');
            await this.generateDefaultApiDocs();
            return;
        }

        try {
            await this.loadStubFiles();
            this.connection.console.log(`Loaded ${this.apiDocumentation.length} API definitions`);
        } catch (error) {
            this.connection.console.error(`Failed to load stubs: ${error}`);
            await this.generateDefaultApiDocs();
        }
    }

    private async loadStubFiles(): Promise<void> {
        if (!this.stubsPath) return;

        const stubFiles = await this.findStubFiles(this.stubsPath);
        
        for (const file of stubFiles) {
            try {
                await this.parseStubFile(file);
            } catch (error) {
                this.connection.console.warn(`Failed to parse stub file ${file}: ${error}`);
            }
        }
    }

    private async findStubFiles(dir: string): Promise<string[]> {
        const files: string[] = [];
        
        try {
            const entries = await fs.readdir(dir, { withFileTypes: true });
            
            for (const entry of entries) {
                const fullPath = path.join(dir, entry.name);
                
                if (entry.isDirectory()) {
                    const subFiles = await this.findStubFiles(fullPath);
                    files.push(...subFiles);
                } else if (entry.isFile() && entry.name.endsWith('.pyi')) {
                    files.push(fullPath);
                }
            }
        } catch (error) {
            this.connection.console.warn(`Failed to read directory ${dir}: ${error}`);
        }
        
        return files;
    }

    private async parseStubFile(filePath: string): Promise<void> {
        try {
            const content = await fs.readFile(filePath, 'utf-8');
            const docs = await this.parseStubContent(content, filePath);
            this.apiDocumentation.push(...docs);
        } catch (error) {
            this.connection.console.error(`Error parsing stub file ${filePath}: ${error}`);
        }
    }

    private async parseStubContent(content: string, filePath: string): Promise<ApiDocumentation[]> {
        const docs: ApiDocumentation[] = [];
        const lines = content.split('\n');
        
        let currentClass: string | null = null;
        let currentNamespace = this.extractNamespaceFromPath(filePath);
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            
            // Parse class definitions
            const classMatch = line.match(/^class\s+(\w+)(?:\([^)]*\))?:/);
            if (classMatch) {
                currentClass = classMatch[1];
                const doc = await this.parseClassDefinition(lines, i, currentNamespace);
                if (doc) docs.push(doc);
                continue;
            }
            
            // Parse function/method definitions
            const funcMatch = line.match(/^(?:async\s+)?def\s+(\w+)\s*\([^)]*\)(?:\s*->\s*[^:]+)?:/);
            if (funcMatch) {
                const doc = await this.parseFunctionDefinition(lines, i, currentClass, currentNamespace);
                if (doc) docs.push(doc);
                continue;
            }
            
            // Parse property definitions
            const propMatch = line.match(/^(\w+):\s*(.+)$/);
            if (propMatch && currentClass) {
                const doc = await this.parsePropertyDefinition(lines, i, currentClass, currentNamespace);
                if (doc) docs.push(doc);
                continue;
            }
            
            // Parse enum definitions
            const enumMatch = line.match(/^class\s+(\w+)\s*\(\s*Enum\s*\):/);
            if (enumMatch) {
                const doc = await this.parseEnumDefinition(lines, i, currentNamespace);
                if (doc) docs.push(doc);
                continue;
            }
        }
        
        return docs;
    }

    private extractNamespaceFromPath(filePath: string): string {
        const relativePath = path.relative(this.stubsPath || '', filePath);
        const parts = relativePath.split(path.sep);
        const namespace = parts.slice(0, -1).join('.').replace(/__init__$/, '');
        return namespace || 'global';
    }

    private async parseClassDefinition(lines: string[], startIndex: number, namespace: string): Promise<ApiDocumentation | null> {
        const line = lines[startIndex].trim();
        const classMatch = line.match(/^class\s+(\w+)(?:\(([^)]*)\))?:/);
        
        if (!classMatch) return null;
        
        const className = classMatch[1];
        const baseClasses = classMatch[2]?.split(',').map(s => s.trim()) || [];
        
        // Extract docstring
        const docstring = this.extractDocstring(lines, startIndex + 1);
        
        return {
            name: `${namespace}.${className}`,
            type: 'class',
            signature: `class ${className}${baseClasses.length > 0 ? `(${baseClasses.join(', ')})` : ''}`,
            description: docstring,
            version: this.extractVersion(docstring)
        };
    }

    private async parseFunctionDefinition(lines: string[], startIndex: number, currentClass: string | null, namespace: string): Promise<ApiDocumentation | null> {
        const line = lines[startIndex].trim();
        const funcMatch = line.match(/^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^:]+))?:/);
        
        if (!funcMatch) return null;
        
        const funcName = funcMatch[1];
        const params = funcMatch[2];
        const returnType = funcMatch[3]?.trim();
        
        // Skip private methods
        if (funcName.startsWith('_') && funcName !== '__init__') {
            return null;
        }
        
        const docstring = this.extractDocstring(lines, startIndex + 1);
        const parameters = this.parseParameters(params, docstring);
        
        const fullName = currentClass ? `${namespace}.${currentClass}.${funcName}` : `${namespace}.${funcName}`;
        
        return {
            name: fullName,
            type: 'method',
            signature: `def ${funcName}(${params})${returnType ? ` -> ${returnType}` : ''}`,
            description: docstring,
            parameters,
            returnType,
            version: this.extractVersion(docstring)
        };
    }

    private async parsePropertyDefinition(lines: string[], startIndex: number, currentClass: string, namespace: string): Promise<ApiDocumentation | null> {
        const line = lines[startIndex].trim();
        const propMatch = line.match(/^(\w+):\s*(.+)$/);
        
        if (!propMatch) return null;
        
        const propName = propMatch[1];
        const propType = propMatch[2];
        
        // Skip private properties
        if (propName.startsWith('_')) {
            return null;
        }
        
        const docstring = this.extractDocstring(lines, startIndex + 1);
        
        return {
            name: `${namespace}.${currentClass}.${propName}`,
            type: 'property',
            signature: `${propName}: ${propType}`,
            description: docstring,
            returnType: propType,
            version: this.extractVersion(docstring)
        };
    }

    private async parseEnumDefinition(lines: string[], startIndex: number, namespace: string): Promise<ApiDocumentation | null> {
        const line = lines[startIndex].trim();
        const enumMatch = line.match(/^class\s+(\w+)\s*\(\s*Enum\s*\):/);
        
        if (!enumMatch) return null;
        
        const enumName = enumMatch[1];
        const docstring = this.extractDocstring(lines, startIndex + 1);
        
        return {
            name: `${namespace}.${enumName}`,
            type: 'enum',
            signature: `class ${enumName}(Enum)`,
            description: docstring,
            version: this.extractVersion(docstring)
        };
    }

    private extractDocstring(lines: string[], startIndex: number): string {
        if (startIndex >= lines.length) return '';
        
        const firstLine = lines[startIndex].trim();
        
        // Single line docstring
        if (firstLine.startsWith('"""') && firstLine.endsWith('"""') && firstLine.length > 6) {
            return firstLine.slice(3, -3).trim();
        }
        
        // Multi-line docstring
        if (firstLine.startsWith('"""')) {
            const docLines: string[] = [];
            let i = startIndex;
            let inDocstring = true;
            
            // Skip the opening """
            if (firstLine === '"""') {
                i++;
            } else {
                docLines.push(firstLine.slice(3));
            }
            
            while (i < lines.length && inDocstring) {
                const line = lines[i];
                if (line.trim().endsWith('"""')) {
                    if (line.trim() !== '"""') {
                        docLines.push(line.replace(/"""$/, '').trim());
                    }
                    inDocstring = false;
                } else {
                    docLines.push(line.trim());
                }
                i++;
            }
            
            return docLines.join('\n').trim();
        }
        
        return '';
    }

    private parseParameters(paramString: string, docstring: string): any[] {
        const params: any[] = [];
        
        if (!paramString.trim()) return params;
        
        const paramParts = paramString.split(',').map(p => p.trim());
        
        for (const part of paramParts) {
            if (part === 'self' || part === 'cls') continue;
            
            const paramMatch = part.match(/(\w+)(?::\s*([^=]+))?(?:\s*=\s*(.+))?/);
            if (paramMatch) {
                const name = paramMatch[1];
                const type = paramMatch[2]?.trim() || 'Any';
                const defaultValue = paramMatch[3]?.trim();
                
                params.push({
                    name,
                    type,
                    optional: !!defaultValue,
                    defaultValue,
                    description: this.extractParamDescription(docstring, name)
                });
            }
        }
        
        return params;
    }

    private extractParamDescription(docstring: string, paramName: string): string {
        const lines = docstring.split('\n');
        for (const line of lines) {
            const match = line.match(new RegExp(`${paramName}\\s*:\\s*(.+)`));
            if (match) {
                return match[1].trim();
            }
        }
        return '';
    }

    private extractVersion(docstring: string): string | undefined {
        const versionMatch = docstring.match(/(?:Since|Available in|Version):\s*(\d+(?:\.\d+)*)/i);
        return versionMatch ? versionMatch[1] : undefined;
    }

    private async generateDefaultApiDocs(): Promise<void> {
        // Generate basic Revit API documentation when stubs are not available
        this.apiDocumentation = [
            {
                name: 'Autodesk.Revit.DB.Transaction',
                type: 'class',
                signature: 'class Transaction',
                description: 'Represents a transaction that can be used to make changes to the Revit model.',
                examples: ['transaction = Transaction(doc, "My Transaction")']
            },
            {
                name: 'Autodesk.Revit.DB.Transaction.Start',
                type: 'method',
                signature: 'Start(self) -> TransactionStatus',
                description: 'Starts the transaction.',
                returnType: 'TransactionStatus'
            },
            {
                name: 'Autodesk.Revit.DB.Transaction.Commit',
                type: 'method',
                signature: 'Commit(self) -> TransactionStatus',
                description: 'Commits the transaction.',
                returnType: 'TransactionStatus'
            },
            {
                name: 'Autodesk.Revit.DB.FilteredElementCollector',
                type: 'class',
                signature: 'class FilteredElementCollector',
                description: 'Searches and filters elements in a Revit model.',
                examples: ['collector = FilteredElementCollector(doc)']
            },
            {
                name: 'Autodesk.Revit.DB.Element',
                type: 'class',
                signature: 'class Element',
                description: 'Base class for all elements in Revit.'
            },
            {
                name: 'Autodesk.Revit.UI.TaskDialog',
                type: 'class',
                signature: 'class TaskDialog',
                description: 'Displays a task dialog to the user.',
                examples: ['TaskDialog.Show("Title", "Message")']
            }
        ];
        
        this.connection.console.log('Generated default API documentation');
    }

    async getApiDocumentation(): Promise<ApiDocumentation[]> {
        return this.apiDocumentation;
    }

    async findDefinition(symbol: string): Promise<Location | null> {
        if (this.definitionCache.has(symbol)) {
            return this.definitionCache.get(symbol)!;
        }

        // Search for the symbol in stub files
        if (!this.stubsPath) return null;

        try {
            const stubFiles = await this.findStubFiles(this.stubsPath);
            
            for (const file of stubFiles) {
                const location = await this.findSymbolInFile(symbol, file);
                if (location) {
                    this.definitionCache.set(symbol, location);
                    return location;
                }
            }
        } catch (error) {
            this.connection.console.error(`Error finding definition for ${symbol}: ${error}`);
        }

        return null;
    }

    private async findSymbolInFile(symbol: string, filePath: string): Promise<Location | null> {
        try {
            const content = await fs.readFile(filePath, 'utf-8');
            const lines = content.split('\n');
            
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                
                // Check for class definition
                if (line.includes(`class ${symbol}`)) {
                    return {
                        uri: `file://${filePath}`,
                        range: {
                            start: { line: i, character: 0 },
                            end: { line: i, character: line.length }
                        }
                    };
                }
                
                // Check for function definition
                if (line.includes(`def ${symbol}(`)) {
                    return {
                        uri: `file://${filePath}`,
                        range: {
                            start: { line: i, character: 0 },
                            end: { line: i, character: line.length }
                        }
                    };
                }
            }
        } catch (error) {
            this.connection.console.warn(`Failed to search in file ${filePath}: ${error}`);
        }
        
        return null;
    }
}