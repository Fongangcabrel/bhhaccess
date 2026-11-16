import { ScanGuard } from "../lib/scanGuard";

describe("ScanGuard", () => {
  it("accepts a first detection", () => {
    expect(new ScanGuard().accept("a")).toBe(true);
  });

  it("ignores frames while a request is in flight", () => {
    const guard = new ScanGuard();
    guard.accept("a");
    expect(guard.accept("b")).toBe(false);
  });

  it("ignores the same QR during the cooldown, accepts after it", () => {
    let now = 0;
    const guard = new ScanGuard(4000, () => now);
    guard.accept("a");
    guard.release();
    now = 1000;
    expect(guard.accept("a")).toBe(false);
    now = 4500;
    expect(guard.accept("a")).toBe(true);
  });

  it("accepts a different QR right after release", () => {
    const guard = new ScanGuard();
    guard.accept("a");
    guard.release();
    expect(guard.accept("b")).toBe(true);
  });
});
