/**
 * Types for the RevitPy Live Server protocol (JSON-RPC 2.0 over WebSocket).
 *
 * Mirrors docs/developer/live-server.md and revitpy/revit/live.py.
 */

export const SUPPORTED_PROTOCOL = 1;

/** Result of `live/status`. */
export interface LiveStatus {
  protocol: number;
  revitpy_version: string;
  python_version: string;
  revit_version: string | null;
  document: string | null;
  debug: { listening: boolean; port: number | null };
  analyses: string[];
}

/** Result of `live/execute` and `live/runFile`. */
export interface ExecutionResult {
  success: boolean;
  output: string;
  error: string | null;
  duration_ms: number;
}

/** Result of `live/reload`. */
export interface ReloadResult {
  reloaded: string[];
  errors: Record<string, string>;
}

/** Result of `debug/start`. */
export interface DebugStartResult {
  listening: boolean;
  port?: number;
  error?: string;
}

/** Result of `bridge/listAnalyses`. */
export interface ListAnalysesResult {
  analyses: string[];
}

/** JSON-RPC error codes the Live Server uses. */
export const JsonRpcErrorCode = {
  ParseError: -32700,
  InvalidRequest: -32600,
  MethodNotFound: -32601,
  InvalidParams: -32602,
  InternalError: -32603,
} as const;
