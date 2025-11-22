import {
    createConnection,
    TextDocuments,
    Diagnostic,
    DiagnosticSeverity,
    ProposedFeatures,
    InitializeParams,
    DidChangeConfigurationNotification,
    CompletionItem,
    CompletionItemKind,
    TextDocumentPositionParams,
    TextDocumentSyncKind,
    InitializeResult,
    DocumentDiagnosticReportKind,
    type DocumentDiagnosticReport,
    Hover,
    SignatureHelp,
    Definition,
    Location,
    Range
} from 'vscode-languageserver/node';

import { TextDocument } from 'vscode-languageserver-textdocument';
import { RevitApiProvider } from './revitApiProvider';
import { PythonAnalyzer } from './pythonAnalyzer';
import { StubsManager } from './stubsManager';

// Create a connection for the server
const connection = createConnection(ProposedFeatures.all);

// Create a simple text document manager
const documents: TextDocuments<TextDocument> = new TextDocuments(TextDocument);

let hasConfigurationCapability = false;
let hasWorkspaceFolderCapability = false;
let hasDiagnosticRelatedInformationCapability = false;

// Service providers
let revitApiProvider: RevitApiProvider;
let pythonAnalyzer: PythonAnalyzer;
let stubsManager: StubsManager;

connection.onInitialize((params: InitializeParams) => {
    const capabilities = params.capabilities;

    // Does the client support the `workspace/configuration` request?
    hasConfigurationCapability = !!(
        capabilities.workspace && !!capabilities.workspace.configuration
    );
    hasWorkspaceFolderCapability = !!(
        capabilities.workspace && !!capabilities.workspace.workspaceFolders
    );
    hasDiagnosticRelatedInformationCapability = !!(
        capabilities.textDocument &&
        capabilities.textDocument.publishDiagnostics &&
        capabilities.textDocument.publishDiagnostics.relatedInformation
    );

    const result: InitializeResult = {
        capabilities: {
            textDocumentSync: TextDocumentSyncKind.Incremental,
            completionProvider: {
                resolveProvider: true,
                triggerCharacters: ['.', '(', '[']
            },
            hoverProvider: true,
            signatureHelpProvider: {
                triggerCharacters: ['(', ',']
            },
            definitionProvider: true,
            documentSymbolProvider: true,
            workspaceSymbolProvider: true,
            diagnosticProvider: {
                interFileDependencies: false,
                workspaceDiagnostics: false
            }
        }
    };

    if (hasWorkspaceFolderCapability) {
        result.capabilities.workspace = {
            workspaceFolders: {
                supported: true
            }
        };
    }

    return result;
});

connection.onInitialized(() => {
    if (hasConfigurationCapability) {
        connection.client.register(DidChangeConfigurationNotification.type, undefined);
    }
    if (hasWorkspaceFolderCapability) {
        connection.workspace.onDidChangeWorkspaceFolders(_event => {
            connection.console.log('Workspace folder change event received.');
        });
    }

    // Initialize service providers
    initializeServices();
});

async function initializeServices() {
    try {
        stubsManager = new StubsManager(connection);
        revitApiProvider = new RevitApiProvider(stubsManager);
        pythonAnalyzer = new PythonAnalyzer();

        await stubsManager.initialize();
        await revitApiProvider.initialize();

        connection.console.log('RevitPy Language Server services initialized');
    } catch (error) {
        connection.console.error(`Failed to initialize services: ${error}`);
    }
}

// Configuration change handler
connection.onDidChangeConfiguration(change => {
    if (hasConfigurationCapability) {
        // Reset all cached document settings
        documentsSettings.clear();
    } else {
        globalSettings = <RevitPySettings>(
            (change.settings.revitpy || defaultSettings)
        );
    }

    // Revalidate all open text documents
    documents.all().forEach(validateTextDocument);
});

interface RevitPySettings {
    enableIntelliSense: boolean;
    stubsPath?: string;
    logLevel: string;
}

const defaultSettings: RevitPySettings = {
    enableIntelliSense: true,
    logLevel: 'info'
};
let globalSettings: RevitPySettings = defaultSettings;

// Cache the settings of all open documents
const documentsSettings: Map<string, Thenable<RevitPySettings>> = new Map();

function getDocumentSettings(resource: string): Thenable<RevitPySettings> {
    if (!hasConfigurationCapability) {
        return Promise.resolve(globalSettings);
    }
    let result = documentsSettings.get(resource);
    if (!result) {
        result = connection.workspace.getConfiguration({
            scopeUri: resource,
            section: 'revitpy'
        });
        documentsSettings.set(resource, result);
    }
    return result;
}

// Only keep settings for open documents
documents.onDidClose(e => {
    documentsSettings.delete(e.document.uri);
});

// Document change handler for validation
documents.onDidChangeContent(change => {
    validateTextDocument(change.document);
});

async function validateTextDocument(textDocument: TextDocument): Promise<void> {
    const settings = await getDocumentSettings(textDocument.uri);
    const text = textDocument.getText();

    const diagnostics: Diagnostic[] = [];

    try {
        // Analyze Python syntax and semantics
        const pythonDiagnostics = await pythonAnalyzer.analyze(textDocument);
        diagnostics.push(...pythonDiagnostics);

        // Analyze RevitPy-specific patterns
        const revitDiagnostics = await revitApiProvider.validateDocument(textDocument);
        diagnostics.push(...revitDiagnostics);

    } catch (error) {
        connection.console.error(`Validation error for ${textDocument.uri}: ${error}`);

        const diagnostic: Diagnostic = {
            severity: DiagnosticSeverity.Error,
            range: {
                start: textDocument.positionAt(0),
                end: textDocument.positionAt(text.length)
            },
            message: `Analysis error: ${error}`,
            source: 'RevitPy'
        };

        diagnostics.push(diagnostic);
    }

    // Send the computed diagnostics to VS Code
    connection.sendDiagnostics({ uri: textDocument.uri, diagnostics });
}

// Completion provider
connection.onCompletion(
    async (_textDocumentPosition: TextDocumentPositionParams): Promise<CompletionItem[]> => {
        try {
            const document = documents.get(_textDocumentPosition.textDocument.uri);
            if (!document) {
                return [];
            }

            const settings = await getDocumentSettings(_textDocumentPosition.textDocument.uri);
            if (!settings.enableIntelliSense) {
                return [];
            }

            const startTime = Date.now();

            // Get completions from RevitAPI provider
            const completions = await revitApiProvider.getCompletions(document, _textDocumentPosition.position);

            // Get Python completions
            const pythonCompletions = await pythonAnalyzer.getCompletions(document, _textDocumentPosition.position);

            const allCompletions = [...completions, ...pythonCompletions];

            const executionTime = Date.now() - startTime;
            connection.console.log(`Completion request completed in ${executionTime}ms`);

            // Ensure we meet the <500ms requirement
            if (executionTime > 500) {
                connection.console.warn(`Completion took ${executionTime}ms, exceeding 500ms target`);
            }

            return allCompletions;
        } catch (error) {
            connection.console.error(`Completion error: ${error}`);
            return [];
        }
    }
);

// Completion resolve provider
connection.onCompletionResolve(
    async (item: CompletionItem): Promise<CompletionItem> => {
        try {
            if (item.data?.source === 'revit-api') {
                return await revitApiProvider.resolveCompletion(item);
            }
            return item;
        } catch (error) {
            connection.console.error(`Completion resolve error: ${error}`);
            return item;
        }
    }
);

// Hover provider
connection.onHover(
    async (_textDocumentPosition: TextDocumentPositionParams): Promise<Hover | null> => {
        try {
            const document = documents.get(_textDocumentPosition.textDocument.uri);
            if (!document) {
                return null;
            }

            const hover = await revitApiProvider.getHover(document, _textDocumentPosition.position);
            return hover;
        } catch (error) {
            connection.console.error(`Hover error: ${error}`);
            return null;
        }
    }
);

// Signature help provider
connection.onSignatureHelp(
    async (_textDocumentPosition: TextDocumentPositionParams): Promise<SignatureHelp | null> => {
        try {
            const document = documents.get(_textDocumentPosition.textDocument.uri);
            if (!document) {
                return null;
            }

            const signatureHelp = await revitApiProvider.getSignatureHelp(document, _textDocumentPosition.position);
            return signatureHelp;
        } catch (error) {
            connection.console.error(`Signature help error: ${error}`);
            return null;
        }
    }
);

// Definition provider
connection.onDefinition(
    async (_textDocumentPosition: TextDocumentPositionParams): Promise<Definition | null> => {
        try {
            const document = documents.get(_textDocumentPosition.textDocument.uri);
            if (!document) {
                return null;
            }

            const definition = await revitApiProvider.getDefinition(document, _textDocumentPosition.position);
            return definition;
        } catch (error) {
            connection.console.error(`Definition error: ${error}`);
            return null;
        }
    }
);

// Diagnostic provider
connection.languages.diagnostics.on(async (params) => {
    const document = documents.get(params.textDocument.uri);
    if (document !== undefined) {
        return {
            kind: DocumentDiagnosticReportKind.Full,
            items: await getDiagnostics(document)
        } satisfies DocumentDiagnosticReport;
    } else {
        return {
            kind: DocumentDiagnosticReportKind.Full,
            items: []
        } satisfies DocumentDiagnosticReport;
    }
});

async function getDiagnostics(textDocument: TextDocument): Promise<Diagnostic[]> {
    const diagnostics: Diagnostic[] = [];

    try {
        const pythonDiagnostics = await pythonAnalyzer.analyze(textDocument);
        diagnostics.push(...pythonDiagnostics);

        const revitDiagnostics = await revitApiProvider.validateDocument(textDocument);
        diagnostics.push(...revitDiagnostics);
    } catch (error) {
        connection.console.error(`Diagnostic error: ${error}`);
    }

    return diagnostics;
}

// Make the text document manager listen on the connection
documents.listen(connection);

// Listen on the connection
connection.listen();
