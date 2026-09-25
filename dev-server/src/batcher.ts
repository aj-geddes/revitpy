/** Trailing debounce that coalesces file-change events into one batch of unique paths. */
export class ChangeBatcher {
  private timer: ReturnType<typeof setTimeout> | undefined;
  private readonly paths = new Set<string>();

  /**
   * @param delayMs quiet period: the batch fires this long after the last `add`.
   * @param onFlush receives the unique paths in the order they first changed.
   */
  constructor(
    private readonly delayMs: number,
    private readonly onFlush: (paths: string[]) => void,
  ) {
    if (!Number.isFinite(delayMs) || delayMs < 0) {
      throw new RangeError('debounce must be a non-negative number of milliseconds');
    }
  }

  /** Record a changed path and restart the quiet period. */
  add(path: string): void {
    this.paths.add(path);
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.flush();
    }, this.delayMs);
  }

  /** Fire now if anything is pending. */
  flush(): void {
    clearTimeout(this.timer);
    this.timer = undefined;
    if (this.paths.size === 0) {
      return;
    }
    const paths = [...this.paths];
    this.paths.clear();
    this.onFlush(paths);
  }

  /** Drop pending paths without firing. */
  cancel(): void {
    clearTimeout(this.timer);
    this.timer = undefined;
    this.paths.clear();
  }

  /** Number of paths waiting to be flushed. */
  get pending(): number {
    return this.paths.size;
  }
}
