import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { Mock } from 'vitest';
import { ChangeBatcher } from '../src/batcher.js';

describe('ChangeBatcher', () => {
  let onFlush: Mock<(paths: string[]) => void>;
  let batcher: ChangeBatcher;

  beforeEach(() => {
    vi.useFakeTimers();
    onFlush = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('throws RangeError for negative delay', () => {
    expect(() => new ChangeBatcher(-1, onFlush)).toThrow(RangeError);
  });

  it('throws RangeError for NaN delay', () => {
    expect(() => new ChangeBatcher(NaN, onFlush)).toThrow(RangeError);
  });

  it('accepts delay 0', () => {
    expect(() => new ChangeBatcher(0, onFlush)).not.toThrow();
  });

  it('fires onFlush once after the delay with [path]', () => {
    batcher = new ChangeBatcher(100, onFlush);
    batcher.add('/path/a.py');
    vi.advanceTimersByTime(99);
    expect(onFlush).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onFlush).toHaveBeenCalledTimes(1);
    expect(onFlush).toHaveBeenCalledWith(['/path/a.py']);
  });

  it('repeated adds within quiet period restart the timer', () => {
    batcher = new ChangeBatcher(100, onFlush);
    batcher.add('/path/a.py');
    vi.advanceTimersByTime(80);
    batcher.add('/path/b.py');
    vi.advanceTimersByTime(80);
    expect(onFlush).not.toHaveBeenCalled();
    vi.advanceTimersByTime(20);
    expect(onFlush).toHaveBeenCalledTimes(1);
    expect(onFlush).toHaveBeenCalledWith(['/path/a.py', '/path/b.py']);
  });

  it('duplicates collapse keeping first-seen order', () => {
    batcher = new ChangeBatcher(100, onFlush);
    batcher.add('/path/a.py');
    batcher.add('/path/b.py');
    batcher.add('/path/a.py');
    vi.advanceTimersByTime(100);
    expect(onFlush).toHaveBeenCalledTimes(1);
    expect(onFlush).toHaveBeenCalledWith(['/path/a.py', '/path/b.py']);
  });

  it('pending reports the count and returns to 0 after flush', () => {
    batcher = new ChangeBatcher(100, onFlush);
    expect(batcher.pending).toBe(0);
    batcher.add('/path/a.py');
    expect(batcher.pending).toBe(1);
    batcher.add('/path/b.py');
    expect(batcher.pending).toBe(2);
    batcher.flush();
    expect(batcher.pending).toBe(0);
  });

  it('flush() fires immediately and the timer does not fire again later', () => {
    batcher = new ChangeBatcher(100, onFlush);
    batcher.add('/path/a.py');
    batcher.flush();
    expect(onFlush).toHaveBeenCalledTimes(1);
    expect(onFlush).toHaveBeenCalledWith(['/path/a.py']);
    vi.advanceTimersByTime(100);
    expect(onFlush).toHaveBeenCalledTimes(1);
  });

  it('flush() with nothing pending does not call onFlush', () => {
    batcher = new ChangeBatcher(100, onFlush);
    batcher.flush();
    expect(onFlush).not.toHaveBeenCalled();
  });

  it('cancel() drops pending paths and nothing fires', () => {
    batcher = new ChangeBatcher(100, onFlush);
    batcher.add('/path/a.py');
    batcher.cancel();
    expect(batcher.pending).toBe(0);
    vi.advanceTimersByTime(100);
    expect(onFlush).not.toHaveBeenCalled();
  });

  it('separate quiet periods produce separate batches', () => {
    batcher = new ChangeBatcher(100, onFlush);
    batcher.add('/path/a.py');
    vi.advanceTimersByTime(100);
    expect(onFlush).toHaveBeenCalledTimes(1);
    expect(onFlush).toHaveBeenCalledWith(['/path/a.py']);
    onFlush.mockClear();
    batcher.add('/path/b.py');
    vi.advanceTimersByTime(100);
    expect(onFlush).toHaveBeenCalledTimes(1);
    expect(onFlush).toHaveBeenCalledWith(['/path/b.py']);
  });

  it('delay 0 fires on the next timer tick', () => {
    batcher = new ChangeBatcher(0, onFlush);
    batcher.add('/path/a.py');
    expect(onFlush).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(onFlush).toHaveBeenCalledTimes(1);
    expect(onFlush).toHaveBeenCalledWith(['/path/a.py']);
  });
});
