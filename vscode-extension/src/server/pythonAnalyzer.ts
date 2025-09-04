import {
    CompletionItem,
    CompletionItemKind,
    Position,
    Diagnostic,
    DiagnosticSeverity
} from 'vscode-languageserver/node';
import { TextDocument } from 'vscode-languageserver-textdocument';

export class PythonAnalyzer {
    private pythonKeywords = [
        'and', 'as', 'assert', 'break', 'class', 'continue', 'def', 'del', 'elif', 'else',
        'except', 'exec', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
        'lambda', 'not', 'or', 'pass', 'print', 'raise', 'return', 'try', 'while', 'with',
        'yield', 'None', 'True', 'False'
    ];

    private builtinFunctions = [
        'abs', 'all', 'any', 'bin', 'bool', 'bytearray', 'bytes', 'callable', 'chr',
        'classmethod', 'compile', 'complex', 'delattr', 'dict', 'dir', 'divmod',
        'enumerate', 'eval', 'exec', 'filter', 'float', 'format', 'frozenset',
        'getattr', 'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int',
        'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max',
        'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow', 'property',
        'range', 'repr', 'reversed', 'round', 'set', 'setattr', 'slice', 'sorted',
        'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip'
    ];

    private builtinModules = [
        'os', 'sys', 'json', 'math', 'datetime', 'collections', 'itertools',
        're', 'random', 'urllib', 'pathlib', 'typing', 'functools', 'operator'
    ];

    async analyze(document: TextDocument): Promise<Diagnostic[]> {
        const diagnostics: Diagnostic[] = [];
        const text = document.getText();
        const lines = text.split('\n');

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            
            // Check for syntax issues
            const syntaxDiagnostics = this.checkSyntax(line, i);
            diagnostics.push(...syntaxDiagnostics);
            
            // Check for common issues
            const commonDiagnostics = this.checkCommonIssues(line, i);
            diagnostics.push(...commonDiagnostics);
            
            // Check for style issues
            const styleDiagnostics = this.checkStyle(line, i);
            diagnostics.push(...styleDiagnostics);
        }

        return diagnostics;
    }

    private checkSyntax(line: string, lineNumber: number): Diagnostic[] {
        const diagnostics: Diagnostic[] = [];
        
        // Check for unmatched brackets
        const brackets = { '(': ')', '[': ']', '{': '}' };
        const stack: string[] = [];
        
        for (let i = 0; i < line.length; i++) {
            const char = line[i];
            
            if (Object.keys(brackets).includes(char)) {
                stack.push(char);
            } else if (Object.values(brackets).includes(char)) {
                const lastOpen = stack.pop();
                if (!lastOpen || brackets[lastOpen as keyof typeof brackets] !== char) {
                    diagnostics.push({
                        severity: DiagnosticSeverity.Error,
                        range: {
                            start: { line: lineNumber, character: i },
                            end: { line: lineNumber, character: i + 1 }
                        },
                        message: `Unmatched ${char}`,
                        source: 'RevitPy Python'
                    });
                }
            }
        }
        
        // Check for unclosed brackets at end of line
        if (stack.length > 0) {
            const unclosed = stack[stack.length - 1];
            const lastIndex = line.lastIndexOf(unclosed);
            diagnostics.push({
                severity: DiagnosticSeverity.Warning,
                range: {
                    start: { line: lineNumber, character: lastIndex },
                    end: { line: lineNumber, character: lastIndex + 1 }
                },
                message: `Unclosed ${unclosed}`,
                source: 'RevitPy Python'
            });
        }

        return diagnostics;
    }

    private checkCommonIssues(line: string, lineNumber: number): Diagnostic[] {
        const diagnostics: Diagnostic[] = [];
        const trimmed = line.trim();

        // Check for common indentation issues
        if (trimmed.endsWith(':') && !this.isValidColonStatement(trimmed)) {
            diagnostics.push({
                severity: DiagnosticSeverity.Warning,
                range: {
                    start: { line: lineNumber, character: 0 },
                    end: { line: lineNumber, character: line.length }
                },
                message: 'Unexpected colon',
                source: 'RevitPy Python'
            });
        }

        // Check for undefined variables (basic check)
        const variableUsage = line.match(/\b([a-zA-Z_][a-zA-Z0-9_]*)\b/g);
        if (variableUsage) {
            for (const variable of variableUsage) {
                if (!this.pythonKeywords.includes(variable) && 
                    !this.builtinFunctions.includes(variable) &&
                    !this.isDefinedVariable(variable, line)) {
                    // This is a very basic check - in reality, we'd need more context
                    // For now, just warn about potential typos in common function names
                    if (this.isLikelyTypo(variable)) {
                        const startChar = line.indexOf(variable);
                        diagnostics.push({
                            severity: DiagnosticSeverity.Information,
                            range: {
                                start: { line: lineNumber, character: startChar },
                                end: { line: lineNumber, character: startChar + variable.length }
                            },
                            message: `Possible typo: '${variable}'`,
                            source: 'RevitPy Python'
                        });
                    }
                }
            }
        }

        return diagnostics;
    }

    private checkStyle(line: string, lineNumber: number): Diagnostic[] {
        const diagnostics: Diagnostic[] = [];

        // Check line length (PEP 8)
        if (line.length > 79) {
            diagnostics.push({
                severity: DiagnosticSeverity.Information,
                range: {
                    start: { line: lineNumber, character: 79 },
                    end: { line: lineNumber, character: line.length }
                },
                message: 'Line too long (PEP 8 recommends max 79 characters)',
                source: 'RevitPy Python'
            });
        }

        // Check for trailing whitespace
        if (line.endsWith(' ') || line.endsWith('\t')) {
            const trimmedLength = line.trimEnd().length;
            diagnostics.push({
                severity: DiagnosticSeverity.Information,
                range: {
                    start: { line: lineNumber, character: trimmedLength },
                    end: { line: lineNumber, character: line.length }
                },
                message: 'Trailing whitespace',
                source: 'RevitPy Python'
            });
        }

        // Check for mixed tabs and spaces (basic check)
        if (line.includes('\t') && line.includes('    ')) {
            diagnostics.push({
                severity: DiagnosticSeverity.Warning,
                range: {
                    start: { line: lineNumber, character: 0 },
                    end: { line: lineNumber, character: line.length }
                },
                message: 'Mixed tabs and spaces in indentation',
                source: 'RevitPy Python'
            });
        }

        return diagnostics;
    }

    async getCompletions(document: TextDocument, position: Position): Promise<CompletionItem[]> {
        const completions: CompletionItem[] = [];
        
        const line = document.getText({
            start: { line: position.line, character: 0 },
            end: { line: position.line, character: position.character }
        });

        const context = this.parseContext(line);

        // Add keyword completions
        completions.push(...this.getKeywordCompletions(context.prefix));
        
        // Add builtin function completions
        completions.push(...this.getBuiltinCompletions(context.prefix));
        
        // Add module completions for import statements
        if (context.isImport) {
            completions.push(...this.getModuleCompletions(context.prefix));
        }

        // Add snippet completions
        completions.push(...this.getSnippetCompletions(context.prefix));

        return completions;
    }

    private parseContext(line: string): CompletionContext {
        const beforeCursor = line;
        const wordMatch = beforeCursor.match(/(\w+)$/);
        const prefix = wordMatch ? wordMatch[1] : '';
        
        const isImport = beforeCursor.includes('import ') || beforeCursor.includes('from ');
        const isAfterDot = beforeCursor.endsWith('.');
        const isInString = this.isInString(beforeCursor);
        
        return {
            prefix,
            isImport,
            isAfterDot,
            isInString,
            line: beforeCursor
        };
    }

    private isInString(text: string): boolean {
        const singleQuotes = (text.match(/'/g) || []).length;
        const doubleQuotes = (text.match(/"/g) || []).length;
        return singleQuotes % 2 !== 0 || doubleQuotes % 2 !== 0;
    }

    private getKeywordCompletions(prefix: string): CompletionItem[] {
        return this.pythonKeywords
            .filter(keyword => keyword.toLowerCase().startsWith(prefix.toLowerCase()))
            .map(keyword => ({
                label: keyword,
                kind: CompletionItemKind.Keyword,
                detail: 'Python keyword',
                insertText: keyword
            }));
    }

    private getBuiltinCompletions(prefix: string): CompletionItem[] {
        return this.builtinFunctions
            .filter(func => func.toLowerCase().startsWith(prefix.toLowerCase()))
            .map(func => ({
                label: func,
                kind: CompletionItemKind.Function,
                detail: 'Python builtin function',
                insertText: `${func}($1)`,
                insertTextFormat: 2 // Snippet
            }));
    }

    private getModuleCompletions(prefix: string): CompletionItem[] {
        return this.builtinModules
            .filter(module => module.toLowerCase().startsWith(prefix.toLowerCase()))
            .map(module => ({
                label: module,
                kind: CompletionItemKind.Module,
                detail: 'Python module',
                insertText: module
            }));
    }

    private getSnippetCompletions(prefix: string): CompletionItem[] {
        const snippets = [
            {
                label: 'if',
                prefix: 'if',
                body: 'if ${1:condition}:\n    ${2:pass}',
                description: 'If statement'
            },
            {
                label: 'for',
                prefix: 'for',
                body: 'for ${1:item} in ${2:iterable}:\n    ${3:pass}',
                description: 'For loop'
            },
            {
                label: 'while',
                prefix: 'while',
                body: 'while ${1:condition}:\n    ${2:pass}',
                description: 'While loop'
            },
            {
                label: 'def',
                prefix: 'def',
                body: 'def ${1:name}(${2:args}):\n    """${3:docstring}"""\n    ${4:pass}',
                description: 'Function definition'
            },
            {
                label: 'class',
                prefix: 'class',
                body: 'class ${1:Name}:\n    """${2:docstring}"""\n    \n    def __init__(self${3:, args}):\n        ${4:pass}',
                description: 'Class definition'
            },
            {
                label: 'try',
                prefix: 'try',
                body: 'try:\n    ${1:pass}\nexcept ${2:Exception} as ${3:e}:\n    ${4:pass}',
                description: 'Try-except block'
            }
        ];

        return snippets
            .filter(snippet => snippet.prefix.toLowerCase().startsWith(prefix.toLowerCase()))
            .map(snippet => ({
                label: snippet.label,
                kind: CompletionItemKind.Snippet,
                detail: snippet.description,
                insertText: snippet.body,
                insertTextFormat: 2 // Snippet
            }));
    }

    private isValidColonStatement(line: string): boolean {
        const colonStatements = [
            /^\s*(if|elif|else|for|while|def|class|try|except|finally|with|match|case)\b/,
            /^\s*\w+\s*:/  // Dictionary or case label
        ];
        
        return colonStatements.some(pattern => pattern.test(line));
    }

    private isDefinedVariable(variable: string, line: string): boolean {
        // Very basic check - in a real implementation, this would need scope analysis
        return line.includes(`${variable} =`) || 
               line.includes(`def ${variable}`) ||
               line.includes(`class ${variable}`) ||
               line.includes(`import ${variable}`) ||
               line.includes(`from `) && line.includes(`import ${variable}`);
    }

    private isLikelyTypo(variable: string): boolean {
        const commonTypos = [
            { typo: 'lenght', correct: 'length' },
            { typo: 'widht', correct: 'width' },
            { typo: 'heigth', correct: 'height' },
            { typo: 'colour', correct: 'color' },
            { typo: 'centre', correct: 'center' }
        ];

        return commonTypos.some(typo => typo.typo === variable.toLowerCase());
    }
}

interface CompletionContext {
    prefix: string;
    isImport: boolean;
    isAfterDot: boolean;
    isInString: boolean;
    line: string;
}