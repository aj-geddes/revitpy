import { z } from 'zod';

// Developer Tools Types
export interface DevToolsConfig {
  enabled: boolean;
  port: number;
  host: string;
  debugMode: boolean;
  profiling: boolean;
  hotReload: boolean;
  autoSave: boolean;
  features: {
    inspector: boolean;
    profiler: boolean;
    debugger: boolean;
    repl: boolean;
    packageManager: boolean;
    projectManager: boolean;
    monitoring: boolean;
    marketplace: boolean;
  };
}

// Project Management Types
export const ProjectTypeSchema = z.enum([
  'command', 'panel', 'tool', 'service', 'library', 'template'
]);

export const ProjectConfigSchema = z.object({
  name: z.string(),
  version: z.string(),
  description: z.string().optional(),
  author: z.string().optional(),
  license: z.string().optional(),
  type: ProjectTypeSchema,
  revitVersions: z.array(z.string()),
  pythonVersion: z.string(),
  dependencies: z.record(z.string()).default({}),
  devDependencies: z.record(z.string()).default({}),
  scripts: z.record(z.string()).default({}),
  entry: z.string(),
  ui: z.object({
    framework: z.enum(['react', 'vue', 'svelte', 'vanilla']).optional(),
    entry: z.string().optional(),
    build: z.string().optional(),
  }).optional(),
  settings: z.record(z.unknown()).default({}),
});

export type ProjectType = z.infer<typeof ProjectTypeSchema>;
export type ProjectConfig = z.infer<typeof ProjectConfigSchema>;

export interface ProjectInfo {
  id: string;
  name: string;
  path: string;
  config: ProjectConfig;
  status: 'active' | 'inactive' | 'error' | 'loading';
  lastModified: Date;
  stats: {
    files: number;
    lines: number;
    size: number;
  };
  git?: {
    branch: string;
    commit: string;
    dirty: boolean;
    remote?: string;
  };
}

export interface ProjectTemplate {
  id: string;
  name: string;
  description: string;
  type: ProjectType;
  author: string;
  version: string;
  icon?: string;
  tags: string[];
  features: string[];
  preview?: string;
  repository?: string;
  files: Array<{
    path: string;
    content: string;
    template: boolean;
  }>;
  prompts?: Array<{
    name: string;
    type: 'text' | 'select' | 'boolean' | 'number';
    message: string;
    default?: unknown;
    choices?: Array<{ name: string; value: unknown }>;
    validate?: string;
  }>;
}

// Debug Types
export interface DebugSession {
  id: string;
  name: string;
  status: 'active' | 'paused' | 'stopped' | 'error';
  startTime: Date;
  endTime?: Date;
  processId?: number;
  breakpoints: DebugBreakpoint[];
  callStack: StackFrame[];
  variables: Variable[];
  output: DebugOutput[];
}

export interface DebugBreakpoint {
  id: string;
  file: string;
  line: number;
  column?: number;
  condition?: string;
  hitCount?: number;
  enabled: boolean;
  verified: boolean;
}

export interface StackFrame {
  id: string;
  name: string;
  file: string;
  line: number;
  column: number;
  source?: string;
  instruction?: number;
}

export interface Variable {
  name: string;
  value: string;
  type: string;
  reference?: number;
  variablesReference?: number;
  namedVariables?: number;
  indexedVariables?: number;
  memoryReference?: string;
}

export interface DebugOutput {
  category: 'console' | 'stdout' | 'stderr' | 'exception' | 'debugger';
  output: string;
  source?: string;
  line?: number;
  column?: number;
  timestamp: Date;
}

// Profiler Types
export interface ProfilerSession {
  id: string;
  name: string;
  startTime: Date;
  endTime?: Date;
  duration: number;
  samples: ProfileSample[];
  flamegraph?: FlameGraphNode;
  statistics: ProfileStatistics;
}

export interface ProfileSample {
  timestamp: number;
  stackTrace: StackFrame[];
  memory?: {
    used: number;
    allocated: number;
    freed: number;
  };
  cpu?: {
    usage: number;
    time: number;
  };
}

export interface FlameGraphNode {
  name: string;
  value: number;
  children: FlameGraphNode[];
  file?: string;
  line?: number;
  selfTime: number;
  totalTime: number;
  calls: number;
}

export interface ProfileStatistics {
  totalTime: number;
  totalCalls: number;
  hotFunctions: Array<{
    name: string;
    selfTime: number;
    totalTime: number;
    calls: number;
    file: string;
    line: number;
  }>;
  memoryStats: {
    peak: number;
    average: number;
    allocations: number;
    deallocations: number;
  };
}

// REPL Types
export interface REPLSession {
  id: string;
  name: string;
  language: 'python' | 'javascript';
  status: 'active' | 'inactive' | 'error';
  history: REPLEntry[];
  context: Record<string, unknown>;
  variables: Variable[];
}

export interface REPLEntry {
  id: string;
  type: 'input' | 'output' | 'error' | 'system';
  content: string;
  timestamp: Date;
  executionTime?: number;
  result?: unknown;
}

// Code Intelligence Types
export interface CodeCompletion {
  label: string;
  kind: 'method' | 'function' | 'variable' | 'class' | 'module' | 'property' | 'keyword';
  detail?: string;
  documentation?: string;
  insertText: string;
  insertTextRules?: number;
  range?: {
    startLine: number;
    startColumn: number;
    endLine: number;
    endColumn: number;
  };
  sortText?: string;
  filterText?: string;
  additionalTextEdits?: Array<{
    range: {
      startLine: number;
      startColumn: number;
      endLine: number;
      endColumn: number;
    };
    text: string;
  }>;
}

export interface Diagnostic {
  severity: 'error' | 'warning' | 'info' | 'hint';
  message: string;
  source: string;
  code?: string | number;
  range: {
    startLine: number;
    startColumn: number;
    endLine: number;
    endColumn: number;
  };
  relatedInformation?: Array<{
    location: {
      uri: string;
      range: {
        startLine: number;
        startColumn: number;
        endLine: number;
        endColumn: number;
      };
    };
    message: string;
  }>;
  tags?: Array<'unnecessary' | 'deprecated'>;
  quickFixes?: Array<{
    title: string;
    kind: 'quickfix' | 'refactor' | 'source';
    edits: Array<{
      range: {
        startLine: number;
        startColumn: number;
        endLine: number;
        endColumn: number;
      };
      text: string;
    }>;
    command?: {
      title: string;
      command: string;
      arguments?: unknown[];
    };
  }>;
}

export interface SymbolInformation {
  name: string;
  kind: 'file' | 'module' | 'class' | 'method' | 'property' | 'field' | 'constructor' | 'enum' | 'interface' | 'function' | 'variable' | 'constant';
  containerName?: string;
  location: {
    uri: string;
    range: {
      startLine: number;
      startColumn: number;
      endLine: number;
      endColumn: number;
    };
  };
  tags?: Array<'deprecated'>;
}

// Testing Types
export interface TestSuite {
  id: string;
  name: string;
  path: string;
  tests: Test[];
  status: 'pending' | 'running' | 'passed' | 'failed' | 'skipped';
  startTime?: Date;
  endTime?: Date;
  duration?: number;
  coverage?: TestCoverage;
}

export interface Test {
  id: string;
  name: string;
  suite: string;
  file: string;
  line: number;
  status: 'pending' | 'running' | 'passed' | 'failed' | 'skipped';
  duration?: number;
  error?: {
    message: string;
    stack?: string;
    expected?: string;
    actual?: string;
  };
  output?: string[];
}

export interface TestCoverage {
  lines: {
    total: number;
    covered: number;
    percentage: number;
  };
  functions: {
    total: number;
    covered: number;
    percentage: number;
  };
  branches: {
    total: number;
    covered: number;
    percentage: number;
  };
  statements: {
    total: number;
    covered: number;
    percentage: number;
  };
  files: Array<{
    path: string;
    lines: number[];
    functions: Array<{
      name: string;
      line: number;
      covered: boolean;
    }>;
    branches: Array<{
      line: number;
      column: number;
      covered: boolean;
    }>;
  }>;
}