/** Exponential backoff used while waiting for a Live Server to (re)appear. */
import { isRetryable } from './errors.js';

export interface BackoffOptions {
  /** First delay (default 250 ms). */
  initialDelayMs?: number;
  /** Upper bound for any delay (default 5000 ms). */
  maxDelayMs?: number;
  /** Growth factor between attempts (default 2). */
  factor?: number;
}

export interface RetryOptions extends BackoffOptions {
  /** Retries after the first attempt (default: unlimited). */
  retries?: number;
  /** Which errors are worth retrying (default: `isRetryable`). */
  shouldRetry?: (error: unknown) => boolean;
  /** Called before each wait; `attempt` is the 1-based retry number. */
  onRetry?: (error: unknown, attempt: number, delayMs: number) => void;
  /** Aborting stops retrying with an `AbortError`. */
  signal?: AbortSignal;
  /** Injectable for tests. */
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>;
}

/** Delay before retry `attempt` (0-based): `initial * factor^attempt`, capped at `max`. */
export function backoffDelay(attempt: number, options: BackoffOptions = {}): number {
  const { initialDelayMs = 250, maxDelayMs = 5000, factor = 2 } = options;
  return Math.min(maxDelayMs, initialDelayMs * factor ** Math.max(0, attempt));
}

/** True for the error produced by an aborted `sleep`/`retry`. */
export function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError';
}

function abortReason(signal: AbortSignal): Error {
  if (signal.reason instanceof Error) {
    return signal.reason;
  }
  const error = new Error('Aborted');
  error.name = 'AbortError';
  return error;
}

/** Resolve after `ms`; reject with an `AbortError` as soon as `signal` aborts. */
export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortReason(signal));
      return;
    }
    const onAbort = (): void => {
      clearTimeout(timer);
      if (signal) {
        reject(abortReason(signal));
      }
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

/** Run `fn` until it succeeds, a non-retryable error occurs, retries run out or `signal` aborts. */
export async function retry<T>(fn: (attempt: number) => Promise<T>, options: RetryOptions = {}): Promise<T> {
  const { retries = Infinity, shouldRetry = isRetryable, onRetry, signal, sleep: wait = sleep } = options;
  for (let attempt = 0; ; attempt++) {
    if (signal?.aborted) {
      throw abortReason(signal);
    }
    try {
      return await fn(attempt);
    } catch (error: unknown) {
      if (signal?.aborted) {
        throw abortReason(signal);
      }
      if (attempt >= retries || !shouldRetry(error)) {
        throw error;
      }
      const delay = backoffDelay(attempt, options);
      onRetry?.(error, attempt + 1, delay);
      await wait(delay, signal);
    }
  }
}
