/**
 * Error types raised by the Live Server client.
 *
 * `LiveUnavailableError` and `LiveAuthError` describe a server that is not
 * (yet) reachable with the current discovery data; the watch loop retries
 * those. `LiveServerError` is a JSON-RPC error answer and is never retried.
 */

/** No running Live Server could be found or reached (not started, restarting, connection lost). */
export class LiveUnavailableError extends Error {
  override name = 'LiveUnavailableError';
}

/** The WebSocket handshake was rejected (HTTP 401/403): usually a stale token after a restart. */
export class LiveAuthError extends Error {
  override name = 'LiveAuthError';
  constructor(
    message: string,
    readonly statusCode: number,
  ) {
    super(message);
  }
}

/** The discovery file advertises a protocol version this client does not speak. */
export class LiveProtocolError extends Error {
  override name = 'LiveProtocolError';
}

/** The Live Server answered a request with a JSON-RPC error object. */
export class LiveServerError extends Error {
  override name = 'LiveServerError';
  constructor(
    readonly code: number,
    readonly rpcMessage: string,
  ) {
    super(`${rpcMessage} (code ${code})`);
  }
}

/** A request got no answer within the client timeout. */
export class LiveTimeoutError extends Error {
  override name = 'LiveTimeoutError';
}

/** True for errors that mean "try again later": the server is not reachable right now. */
export function isRetryable(error: unknown): boolean {
  return error instanceof LiveUnavailableError || error instanceof LiveAuthError;
}
