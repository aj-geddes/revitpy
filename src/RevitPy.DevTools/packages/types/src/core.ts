import { z } from 'zod';

// RevitPy Core Types
export const RevitVersionSchema = z.enum([
  '2021', '2022', '2023', '2024', '2025'
]);

export const PythonVersionSchema = z.string().regex(/^\d+\.\d+\.\d+$/);

export const RevitPyConfigSchema = z.object({
  version: z.string(),
  pythonVersion: PythonVersionSchema,
  revitVersions: z.array(RevitVersionSchema),
  developmentMode: z.boolean().default(false),
  hotReload: z.boolean().default(true),
  debugMode: z.boolean().default(false),
  logLevel: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
  extensions: z.object({
    enabled: z.array(z.string()).default([]),
    disabled: z.array(z.string()).default([]),
  }).default({}),
  ui: z.object({
    theme: z.enum(['light', 'dark', 'auto']).default('auto'),
    language: z.string().default('en-US'),
  }).default({}),
});

export type RevitVersion = z.infer<typeof RevitVersionSchema>;
export type PythonVersion = z.infer<typeof PythonVersionSchema>;
export type RevitPyConfig = z.infer<typeof RevitPyConfigSchema>;

// Runtime Types
export interface RevitPyRuntime {
  version: string;
  pythonVersion: PythonVersion;
  isConnected: boolean;
  revitVersion?: RevitVersion;
  processId?: number;
  startTime: Date;
  uptime: number;
}

export interface RevitPyEnvironment {
  name: string;
  path: string;
  pythonVersion: PythonVersion;
  packages: Array<{
    name: string;
    version: string;
    installed: Date;
  }>;
  isActive: boolean;
  isDefault: boolean;
}

// Communication Types
export interface RevitPyMessage {
  id: string;
  type: 'request' | 'response' | 'notification' | 'error';
  method?: string;
  params?: unknown;
  result?: unknown;
  error?: {
    code: number;
    message: string;
    data?: unknown;
  };
  timestamp: number;
}

export interface RevitPyEvent {
  id: string;
  type: string;
  source: 'revit' | 'python' | 'devtools' | 'ui';
  data: unknown;
  timestamp: number;
}

// Error Types
export interface RevitPyError {
  code: string;
  message: string;
  details?: string;
  stack?: string;
  source: 'runtime' | 'python' | 'revit' | 'devtools';
  timestamp: Date;
  context?: Record<string, unknown>;
}

// Performance Types
export interface PerformanceMetrics {
  memory: {
    used: number;
    available: number;
    total: number;
  };
  cpu: {
    usage: number;
    cores: number;
  };
  operations: {
    total: number;
    successful: number;
    failed: number;
    averageTime: number;
  };
  timestamp: Date;
}

// Status Types
export type ConnectionStatus = 'connected' | 'disconnected' | 'connecting' | 'error';
export type RuntimeStatus = 'running' | 'stopped' | 'starting' | 'stopping' | 'error';
export type ExtensionStatus = 'loaded' | 'unloaded' | 'loading' | 'error' | 'disabled';
