export interface RevitPyConfig {
    name: string;
    version: string;
    description?: string;
    author?: string;
    license?: string;
    dependencies?: { [key: string]: string };
    devDependencies?: { [key: string]: string };
    scripts?: { [key: string]: string };
    revitVersions?: string[];
    pythonVersion?: string;
    entryPoint?: string;
}

export interface RevitConnection {
    host: string;
    port: number;
    isConnected: boolean;
    revitVersion?: string;
    pythonVersion?: string;
}

export interface PackageInfo {
    name: string;
    version: string;
    description?: string;
    author?: string;
    homepage?: string;
    repository?: string;
    license?: string;
    keywords?: string[];
    downloads?: number;
    isInstalled?: boolean;
    installedVersion?: string;
}

export interface ScriptExecutionResult {
    success: boolean;
    output?: string;
    error?: string;
    executionTime: number;
}

export interface DebugSession {
    id: string;
    scriptPath: string;
    isActive: boolean;
    breakpoints: DebugBreakpoint[];
}

export interface DebugBreakpoint {
    line: number;
    column?: number;
    condition?: string;
    hitCondition?: string;
    logMessage?: string;
}

export interface ApiDocumentation {
    name: string;
    type: 'class' | 'method' | 'property' | 'enum' | 'namespace';
    signature?: string;
    description?: string;
    parameters?: ApiParameter[];
    returnType?: string;
    examples?: string[];
    deprecated?: boolean;
    version?: string;
}

export interface ApiParameter {
    name: string;
    type: string;
    description?: string;
    optional?: boolean;
    defaultValue?: any;
}

export interface CompletionItem {
    label: string;
    kind: CompletionItemKind;
    detail?: string;
    documentation?: string;
    insertText?: string;
    range?: Range;
    sortText?: string;
    filterText?: string;
}

export enum CompletionItemKind {
    Text = 1,
    Method = 2,
    Function = 3,
    Constructor = 4,
    Field = 5,
    Variable = 6,
    Class = 7,
    Interface = 8,
    Module = 9,
    Property = 10,
    Unit = 11,
    Value = 12,
    Enum = 13,
    Keyword = 14,
    Snippet = 15,
    Color = 16,
    File = 17,
    Reference = 18,
    Folder = 19,
    EnumMember = 20,
    Constant = 21,
    Struct = 22,
    Event = 23,
    Operator = 24,
    TypeParameter = 25
}

export interface Range {
    start: Position;
    end: Position;
}

export interface Position {
    line: number;
    character: number;
}

export interface DiagnosticInfo {
    severity: DiagnosticSeverity;
    message: string;
    range: Range;
    source?: string;
    code?: string | number;
}

export enum DiagnosticSeverity {
    Error = 1,
    Warning = 2,
    Information = 3,
    Hint = 4
}

export interface ProjectTemplate {
    name: string;
    description: string;
    category: string;
    files: TemplateFile[];
    dependencies?: string[];
    postInstallInstructions?: string;
}

export interface TemplateFile {
    path: string;
    content: string;
    isTemplate?: boolean;
}

export interface HotReloadEvent {
    type: 'file-changed' | 'script-executed' | 'error' | 'connected' | 'disconnected';
    timestamp: number;
    data?: any;
}
