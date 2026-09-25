import { afterEach, describe, expect, it, vi } from 'vitest';
import { LiveAuthError, LiveServerError, LiveUnavailableError } from '../src/errors.js';
import { backoffDelay, isAbortError, retry, sleep } from '../src/retry.js';

const instantSleep = () => vi.fn<(ms: number, signal?: AbortSignal) => Promise<void>>(() => Promise.resolve());

/** fn that fails `failures` times with `error`, then resolves 'ok'. */
function flaky(failures: number, error: () => Error = () => new LiveUnavailableError('not running')) {
  return vi.fn((attempt: number) => (attempt < failures ? Promise.reject(error()) : Promise.resolve('ok')));
}

afterEach(() => {
  vi.useRealTimers();
});

describe('backoffDelay', () => {
  it('doubles from 250 ms up to 5 s by default', () => {
    expect([0, 1, 2, 3, 4, 5, 10].map((n) => backoffDelay(n))).toEqual([250, 500, 1000, 2000, 4000, 5000, 5000]);
  });

  it('honours custom options', () => {
    const options = { initialDelayMs: 100, factor: 3, maxDelayMs: 1000 };
    expect([0, 1, 2, 3].map((n) => backoffDelay(n, options))).toEqual([100, 300, 900, 1000]);
  });
});

describe('retry', () => {
  it('returns the first success without retrying', async () => {
    const onRetry = vi.fn();
    await expect(retry(flaky(0), { onRetry, sleep: instantSleep() })).resolves.toBe('ok');
    expect(onRetry).not.toHaveBeenCalled();
  });

  it('retries retryable errors with growing delays', async () => {
    const fn = flaky(3);
    const onRetry = vi.fn();
    const wait = instantSleep();
    await expect(retry(fn, { onRetry, sleep: wait })).resolves.toBe('ok');
    expect(fn.mock.calls.map(([attempt]) => attempt)).toEqual([0, 1, 2, 3]);
    expect(onRetry.mock.calls.map((args: unknown[]) => [args[0] instanceof LiveUnavailableError, args[1], args[2]])).toEqual([
      [true, 1, 250],
      [true, 2, 500],
      [true, 3, 1000],
    ]);
    expect(wait.mock.calls.map(([ms]) => ms)).toEqual([250, 500, 1000]);
  });

  it('retries LiveAuthError (stale token) by default', async () => {
    await expect(retry(flaky(1, () => new LiveAuthError('stale', 401)), { sleep: instantSleep() })).resolves.toBe('ok');
  });

  it.each([
    ['a plain Error', () => new Error('boom')],
    ['a JSON-RPC error', () => new LiveServerError(-32602, 'bad params')],
  ])('throws %s immediately', async (_name, error) => {
    const fn = flaky(5, error);
    await expect(retry(fn, { sleep: instantSleep() })).rejects.toBeInstanceOf(Error);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('gives up after `retries` retries with the last error', async () => {
    let n = 0;
    const fn = vi.fn(() => Promise.reject(new LiveUnavailableError(`failure ${String(++n)}`)));
    await expect(retry(fn, { retries: 2, sleep: instantSleep() })).rejects.toThrow('failure 3');
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it('uses a custom shouldRetry', async () => {
    const fn = flaky(2, () => new Error('flaky'));
    await expect(retry(fn, { shouldRetry: () => true, sleep: instantSleep() })).resolves.toBe('ok');
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it('stops with an AbortError when the signal aborts while waiting', async () => {
    const controller = new AbortController();
    const fn = flaky(100);
    const promise = retry(fn, {
      signal: controller.signal,
      initialDelayMs: 10_000,
      onRetry: () => {
        setTimeout(() => {
          controller.abort();
        }, 10);
      },
    });
    const error: unknown = await promise.catch((e: unknown) => e);
    expect(isAbortError(error)).toBe(true);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('does not start when the signal is already aborted', async () => {
    const fn = flaky(0);
    const error: unknown = await retry(fn, { signal: AbortSignal.abort() }).catch((e: unknown) => e);
    expect(isAbortError(error)).toBe(true);
    expect(fn).not.toHaveBeenCalled();
  });
});

describe('sleep', () => {
  it('resolves after the given time', async () => {
    vi.useFakeTimers();
    let done = false;
    const promise = sleep(100).then(() => {
      done = true;
    });
    await vi.advanceTimersByTimeAsync(99);
    expect(done).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    await promise;
    expect(done).toBe(true);
  });

  it('rejects immediately with an already-aborted signal', async () => {
    const error: unknown = await sleep(10, AbortSignal.abort()).catch((e: unknown) => e);
    expect(isAbortError(error)).toBe(true);
  });

  it('rejects when aborted midway', async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const promise = sleep(1000, controller.signal).catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(500);
    controller.abort();
    expect(isAbortError(await promise)).toBe(true);
  });
});
