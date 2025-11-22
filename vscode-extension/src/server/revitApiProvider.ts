import {
    CompletionItem,
    CompletionItemKind,
    Position,
    Hover,
    MarkupKind,
    SignatureHelp,
    SignatureInformation,
    ParameterInformation,
    Definition,
    Location,
    Range,
    Diagnostic,
    DiagnosticSeverity
} from 'vscode-languageserver/node';
import { TextDocument } from 'vscode-languageserver-textdocument';
import { StubsManager } from './stubsManager';
import { ApiDocumentation, ApiParameter } from '../common/types';

export class RevitApiProvider {
    private apiCache: Map<string, ApiDocumentation[]> = new Map();
    private completionCache: Map<string, CompletionItem[]> = new Map();
    private lastCacheUpdate = 0;
    private readonly cacheTimeout = 5 * 60 * 1000; // 5 minutes

    constructor(private stubsManager: StubsManager) {}

    async initialize(): Promise<void> {
        await this.loadApiDefinitions();
    }

    private async loadApiDefinitions(): Promise<void> {
        try {
            const apiDocs = await this.stubsManager.getApiDocumentation();

            // Group by namespace/module for efficient lookup
            const groupedDocs = new Map<string, ApiDocumentation[]>();

            for (const doc of apiDocs) {
                const namespace = this.extractNamespace(doc.name);
                if (!groupedDocs.has(namespace)) {
                    groupedDocs.set(namespace, []);
                }
                groupedDocs.get(namespace)!.push(doc);
            }

            this.apiCache = groupedDocs;
            this.lastCacheUpdate = Date.now();
        } catch (error) {
            console.error('Failed to load API definitions:', error);
        }
    }

    private extractNamespace(fullName: string): string {
        const parts = fullName.split('.');
        if (parts.length > 1) {
            return parts.slice(0, -1).join('.');
        }
        return 'global';
    }

    async getCompletions(document: TextDocument, position: Position): Promise<CompletionItem[]> {
        const startTime = Date.now();

        try {
            // Check cache validity
            if (Date.now() - this.lastCacheUpdate > this.cacheTimeout) {
                await this.loadApiDefinitions();
            }

            const line = document.getText({
                start: { line: position.line, character: 0 },
                end: { line: position.line, character: position.character }
            });

            const context = this.parseContext(line, position.character);
            const cacheKey = `${context.type}:${context.prefix}:${context.memberAccess}`;

            // Check completion cache
            if (this.completionCache.has(cacheKey)) {
                const cached = this.completionCache.get(cacheKey)!;
                const executionTime = Date.now() - startTime;
                console.log(`Completion from cache in ${executionTime}ms`);
                return cached;
            }

            const completions = await this.generateCompletions(context, document, position);

            // Cache the results
            this.completionCache.set(cacheKey, completions);

            // Clean cache if it gets too large
            if (this.completionCache.size > 1000) {
                this.cleanCompletionCache();
            }

            const executionTime = Date.now() - startTime;
            console.log(`Completion generated in ${executionTime}ms`);

            return completions;
        } catch (error) {
            console.error('Error getting completions:', error);
            return [];
        }
    }

    private parseContext(line: string, character: number): CompletionContext {
        const beforeCursor = line.substring(0, character);
        const wordMatch = beforeCursor.match(/(\w+)$/);
        const prefix = wordMatch ? wordMatch[1] : '';

        // Check for member access (dot notation)
        const memberMatch = beforeCursor.match(/(\w+(?:\.\w+)*)\.\w*$/);
        const memberAccess = memberMatch ? memberMatch[1] : null;

        // Determine context type
        let type = 'general';
        if (memberAccess) {
            type = 'member';
        } else if (beforeCursor.includes('import ')) {
            type = 'import';
        } else if (beforeCursor.includes('from ')) {
            type = 'from_import';
        }

        return {
            type,
            prefix,
            memberAccess,
            line: beforeCursor
        };
    }

    private async generateCompletions(
        context: CompletionContext,
        document: TextDocument,
        position: Position
    ): Promise<CompletionItem[]> {
        const completions: CompletionItem[] = [];

        switch (context.type) {
            case 'import':
                completions.push(...this.getImportCompletions(context.prefix));
                break;
            case 'from_import':
                completions.push(...this.getFromImportCompletions(context));
                break;
            case 'member':
                completions.push(...await this.getMemberCompletions(context.memberAccess!, context.prefix));
                break;
            case 'general':
            default:
                completions.push(...this.getGeneralCompletions(context.prefix));
                break;
        }

        return completions;
    }

    private getImportCompletions(prefix: string): CompletionItem[] {
        const revitModules = [
            'Autodesk.Revit.DB',
            'Autodesk.Revit.UI',
            'Autodesk.Revit.ApplicationServices',
            'Autodesk.Revit.Creation',
            'Autodesk.Revit.Exceptions'
        ];

        return revitModules
            .filter(module => module.toLowerCase().includes(prefix.toLowerCase()))
            .map(module => ({
                label: module,
                kind: CompletionItemKind.Module,
                detail: 'Revit API Module',
                documentation: `Import ${module} module`,
                insertText: module,
                data: { source: 'revit-api', type: 'module' }
            }));
    }

    private getFromImportCompletions(context: CompletionContext): CompletionItem[] {
        const fromMatch = context.line.match(/from\s+([A-Za-z.]+)\s+import/);
        if (!fromMatch) return [];

        const moduleName = fromMatch[1];
        const moduleCompletions = this.apiCache.get(moduleName) || [];

        return moduleCompletions
            .filter(item => item.name.toLowerCase().includes(context.prefix.toLowerCase()))
            .map(item => this.createCompletionFromApiDoc(item));
    }

    private async getMemberCompletions(memberAccess: string, prefix: string): Promise<CompletionItem[]> {
        const completions: CompletionItem[] = [];

        // Try to resolve the type of the member access
        const resolvedType = await this.resolveType(memberAccess);
        if (!resolvedType) return completions;

        const members = this.apiCache.get(resolvedType) || [];

        return members
            .filter(member => member.name.toLowerCase().includes(prefix.toLowerCase()))
            .map(member => this.createCompletionFromApiDoc(member));
    }

    private getGeneralCompletions(prefix: string): CompletionItem[] {
        const completions: CompletionItem[] = [];

        // Add common Revit API classes and functions
        for (const [namespace, docs] of this.apiCache.entries()) {
            if (namespace === 'global' || namespace.startsWith('Autodesk.Revit')) {
                const filteredDocs = docs.filter(doc =>
                    doc.name.toLowerCase().includes(prefix.toLowerCase())
                );

                completions.push(...filteredDocs.map(doc => this.createCompletionFromApiDoc(doc)));
            }
        }

        return completions.slice(0, 100); // Limit to prevent performance issues
    }

    private createCompletionFromApiDoc(doc: ApiDocumentation): CompletionItem {
        const kind = this.mapApiTypeToCompletionKind(doc.type);

        let insertText = doc.name;
        if (doc.type === 'method' && doc.parameters) {
            const paramList = doc.parameters.map((param, index) =>
                param.optional ? `\${${index + 1}:${param.name}}` : `\${${index + 1}:${param.name}}`
            ).join(', ');
            insertText = `${doc.name}(${paramList})`;
        }

        return {
            label: doc.name,
            kind,
            detail: doc.signature || `${doc.type}: ${doc.name}`,
            documentation: {
                kind: MarkupKind.Markdown,
                value: this.formatDocumentation(doc)
            },
            insertText,
            insertTextFormat: doc.type === 'method' ? 2 : 1, // Snippet if method, PlainText otherwise
            sortText: this.getSortText(doc),
            data: { source: 'revit-api', apiDoc: doc }
        };
    }

    private mapApiTypeToCompletionKind(apiType: string): CompletionItemKind {
        switch (apiType) {
            case 'class': return CompletionItemKind.Class;
            case 'method': return CompletionItemKind.Method;
            case 'property': return CompletionItemKind.Property;
            case 'enum': return CompletionItemKind.Enum;
            case 'namespace': return CompletionItemKind.Module;
            default: return CompletionItemKind.Variable;
        }
    }

    private formatDocumentation(doc: ApiDocumentation): string {
        let markdown = `## ${doc.name}\n\n`;

        if (doc.signature) {
            markdown += `\`\`\`python\n${doc.signature}\n\`\`\`\n\n`;
        }

        if (doc.description) {
            markdown += `${doc.description}\n\n`;
        }

        if (doc.parameters && doc.parameters.length > 0) {
            markdown += '### Parameters\n\n';
            for (const param of doc.parameters) {
                markdown += `- **${param.name}** (\`${param.type}\`)`;
                if (param.optional) markdown += ' *(optional)*';
                if (param.description) markdown += `: ${param.description}`;
                markdown += '\n';
            }
            markdown += '\n';
        }

        if (doc.returnType) {
            markdown += `### Returns\n\n\`${doc.returnType}\`\n\n`;
        }

        if (doc.examples && doc.examples.length > 0) {
            markdown += '### Examples\n\n';
            for (const example of doc.examples) {
                markdown += `\`\`\`python\n${example}\n\`\`\`\n\n`;
            }
        }

        if (doc.deprecated) {
            markdown += '⚠️ **Deprecated** - Consider using alternative methods.\n\n';
        }

        if (doc.version) {
            markdown += `*Available since Revit ${doc.version}*\n`;
        }

        return markdown;
    }

    private getSortText(doc: ApiDocumentation): string {
        // Priority sorting: methods and properties first, then classes, then others
        const typePriority: { [key: string]: string } = {
            'method': '1',
            'property': '2',
            'class': '3',
            'enum': '4',
            'namespace': '5'
        };

        const priority = typePriority[doc.type] || '9';
        return `${priority}_${doc.name.toLowerCase()}`;
    }

    async resolveCompletion(item: CompletionItem): Promise<CompletionItem> {
        if (item.data?.apiDoc) {
            const doc = item.data.apiDoc as ApiDocumentation;

            // Add more detailed documentation if available
            if (doc.examples && doc.examples.length > 0) {
                const currentDoc = item.documentation as any;
                if (currentDoc && typeof currentDoc === 'object') {
                    currentDoc.value += '\n\n### Additional Examples\n\n';
                    for (const example of doc.examples) {
                        currentDoc.value += `\`\`\`python\n${example}\n\`\`\`\n\n`;
                    }
                }
            }
        }

        return item;
    }

    async getHover(document: TextDocument, position: Position): Promise<Hover | null> {
        const wordRange = this.getWordRange(document, position);
        if (!wordRange) return null;

        const word = document.getText(wordRange);
        const apiDoc = await this.findApiDocumentation(word);

        if (!apiDoc) return null;

        return {
            contents: {
                kind: MarkupKind.Markdown,
                value: this.formatDocumentation(apiDoc)
            },
            range: wordRange
        };
    }

    async getSignatureHelp(document: TextDocument, position: Position): Promise<SignatureHelp | null> {
        const line = document.getText({
            start: { line: position.line, character: 0 },
            end: position
        });

        // Find the function call
        const functionMatch = line.match(/(\w+)\s*\([^)]*$/);
        if (!functionMatch) return null;

        const functionName = functionMatch[1];
        const apiDoc = await this.findApiDocumentation(functionName);

        if (!apiDoc || apiDoc.type !== 'method' || !apiDoc.parameters) {
            return null;
        }

        const signature: SignatureInformation = {
            label: apiDoc.signature || `${functionName}(${apiDoc.parameters.map(p => p.name).join(', ')})`,
            documentation: {
                kind: MarkupKind.Markdown,
                value: this.formatDocumentation(apiDoc)
            },
            parameters: apiDoc.parameters.map(param => ({
                label: param.name,
                documentation: param.description || `${param.type} parameter`
            }))
        };

        // Calculate active parameter
        const commaCount = (line.match(/,/g) || []).length;

        return {
            signatures: [signature],
            activeSignature: 0,
            activeParameter: Math.min(commaCount, apiDoc.parameters.length - 1)
        };
    }

    async getDefinition(document: TextDocument, position: Position): Promise<Definition | null> {
        const wordRange = this.getWordRange(document, position);
        if (!wordRange) return null;

        const word = document.getText(wordRange);
        const definition = await this.stubsManager.findDefinition(word);

        if (!definition) return null;

        return {
            uri: definition.uri,
            range: definition.range
        };
    }

    async validateDocument(document: TextDocument): Promise<Diagnostic[]> {
        const diagnostics: Diagnostic[] = [];
        const text = document.getText();
        const lines = text.split('\n');

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];

            // Check for deprecated API usage
            const deprecatedMatch = line.match(/(\w+\.\w+)/g);
            if (deprecatedMatch) {
                for (const match of deprecatedMatch) {
                    const apiDoc = await this.findApiDocumentation(match);
                    if (apiDoc?.deprecated) {
                        const startChar = line.indexOf(match);
                        diagnostics.push({
                            severity: DiagnosticSeverity.Warning,
                            range: {
                                start: { line: i, character: startChar },
                                end: { line: i, character: startChar + match.length }
                            },
                            message: `'${match}' is deprecated. Consider using alternative methods.`,
                            source: 'RevitPy',
                            code: 'deprecated-api'
                        });
                    }
                }
            }

            // Check for missing imports
            const revitApiUsage = line.match(/\b(DB|UI|ApplicationServices)\./);
            if (revitApiUsage && !text.includes(`import ${revitApiUsage[1]}`)) {
                const startChar = line.indexOf(revitApiUsage[0]);
                diagnostics.push({
                    severity: DiagnosticSeverity.Error,
                    range: {
                        start: { line: i, character: startChar },
                        end: { line: i, character: startChar + revitApiUsage[0].length }
                    },
                    message: `Missing import for '${revitApiUsage[1]}'`,
                    source: 'RevitPy',
                    code: 'missing-import'
                });
            }
        }

        return diagnostics;
    }

    private getWordRange(document: TextDocument, position: Position): Range | null {
        const line = document.getText({
            start: { line: position.line, character: 0 },
            end: { line: position.line + 1, character: 0 }
        });

        const wordPattern = /\b\w+\b/g;
        let match;

        while ((match = wordPattern.exec(line)) !== null) {
            const startPos = match.index;
            const endPos = match.index + match[0].length;

            if (position.character >= startPos && position.character <= endPos) {
                return {
                    start: { line: position.line, character: startPos },
                    end: { line: position.line, character: endPos }
                };
            }
        }

        return null;
    }

    private async findApiDocumentation(name: string): Promise<ApiDocumentation | null> {
        for (const [namespace, docs] of this.apiCache.entries()) {
            const found = docs.find(doc => doc.name === name || doc.name.endsWith(`.${name}`));
            if (found) return found;
        }
        return null;
    }

    private async resolveType(expression: string): Promise<string | null> {
        // This would involve more complex type resolution
        // For now, return a simplified version
        const parts = expression.split('.');
        if (parts.length > 1) {
            return parts[0]; // Return the first part as the type
        }
        return null;
    }

    private cleanCompletionCache(): void {
        // Remove half of the cached entries (LRU would be better but this is simpler)
        const entries = Array.from(this.completionCache.entries());
        const toKeep = entries.slice(entries.length / 2);

        this.completionCache.clear();
        for (const [key, value] of toKeep) {
            this.completionCache.set(key, value);
        }
    }
}

interface CompletionContext {
    type: 'import' | 'from_import' | 'member' | 'general';
    prefix: string;
    memberAccess: string | null;
    line: string;
}
