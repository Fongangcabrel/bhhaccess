import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

it("uses the phone's own BarcodeDetector when it reads QR codes", async () => {
  const detect = vi.fn().mockResolvedValue([{ rawValue: "B1ABC" }]);
  class FakeDetector {
    static getSupportedFormats = vi.fn().mockResolvedValue(["qr_code", "ean_13"]);
    detect = detect;
  }
  vi.stubGlobal("BarcodeDetector", FakeDetector);
  const { getQrDecoder } = await import("../features/scan/decoder");
  const decoder = await getQrDecoder();
  expect(decoder.engine).toBe("natif");
  expect(await decoder.decode(document.createElement("canvas"))).toBe("B1ABC");
});

it("falls back to ZXing when the native detector cannot read QR codes", async () => {
  class NoQrDetector {
    static getSupportedFormats = vi.fn().mockResolvedValue(["ean_13"]);
  }
  vi.stubGlobal("BarcodeDetector", NoQrDetector);
  vi.doMock("zxing-wasm/reader", () => ({
    prepareZXingModule: vi.fn().mockResolvedValue({}),
    readBarcodes: vi.fn().mockResolvedValue([{ text: "B1XYZ" }]),
  }));
  const { getQrDecoder } = await import("../features/scan/decoder");
  const decoder = await getQrDecoder();
  expect(decoder.engine).toBe("zxing");
});
