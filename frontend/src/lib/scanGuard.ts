/**
 * Debounce for camera detections. A QR stays in front of the camera for many frames;
 * we must send ONE scan per presentation, never a burst (it would trigger false
 * "already inside" refusals).
 */
export class ScanGuard {
  private lastToken: string | null = null;
  private lastAt = 0;
  private busy = false;

  constructor(
    private readonly cooldownMs = 4000,
    private readonly now: () => number = () => Date.now(),
  ) {}

  /** True when this detection should be sent to the server. */
  accept(token: string): boolean {
    if (this.busy) return false;
    if (token === this.lastToken && this.now() - this.lastAt < this.cooldownMs) return false;
    this.lastToken = token;
    this.lastAt = this.now();
    this.busy = true;
    return true;
  }

  /** Call when the request has finished (success or error). */
  release(): void {
    this.busy = false;
    this.lastAt = this.now();
  }
}
