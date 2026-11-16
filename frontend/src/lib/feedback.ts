import type { Tone } from "./verdicts";

/** Haptic + audio cue so the agent need not look at the screen. Never throws. */
export function giveFeedback(tone: Tone): void {
  try {
    navigator.vibrate?.(tone === "deny" ? [200, 100, 200, 100, 200] : [120]);
  } catch {
    /* unsupported */
  }
  try {
    const AudioCtx = window.AudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const oscillator = ctx.createOscillator();
    oscillator.frequency.value = tone === "deny" ? 220 : tone === "exit" ? 660 : 880;
    oscillator.connect(ctx.destination);
    oscillator.start();
    oscillator.stop(ctx.currentTime + (tone === "deny" ? 0.5 : 0.15));
  } catch {
    /* audio blocked until a user gesture */
  }
}
