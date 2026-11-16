/**
 * QR decoding for the camera, fastest engine first:
 *  1. the phone's own BarcodeDetector (Android Chrome: hardware-accelerated, very tolerant),
 *  2. otherwise ZXing compiled to WebAssembly (iPhone, desktop), loaded on first use.
 *
 * Measured on degraded badge images with the BHH logo: ZXing reads ~3x more badges than the
 * former jsQR and is ~6x faster per image. The .wasm file is bundled with the app (no internet).
 */
import zxingWasmUrl from "zxing-wasm/reader/zxing_reader.wasm?url";

export interface QrDecoder {
  readonly engine: "natif" | "zxing";
  /** Text of the first QR found in the image, or null. */
  decode(source: HTMLCanvasElement): Promise<string | null>;
}

interface NativeDetector {
  detect(source: CanvasImageSource): Promise<{ rawValue: string }[]>;
}
interface NativeDetectorClass {
  new (options: { formats: string[] }): NativeDetector;
  getSupportedFormats(): Promise<string[]>;
}

async function nativeDecoder(): Promise<QrDecoder | null> {
  const Detector = (globalThis as { BarcodeDetector?: NativeDetectorClass }).BarcodeDetector;
  if (!Detector) return null;
  try {
    if (!(await Detector.getSupportedFormats()).includes("qr_code")) return null;
    const detector = new Detector({ formats: ["qr_code"] });
    return {
      engine: "natif",
      async decode(source) {
        const found = await detector.detect(source);
        return found[0]?.rawValue ?? null;
      },
    };
  } catch {
    return null; // some browsers expose the class but fail at runtime
  }
}

async function zxingDecoder(): Promise<QrDecoder> {
  const zxing = await import("zxing-wasm/reader");
  await zxing.prepareZXingModule({
    overrides: {
      // Load the bundled .wasm instead of the default CDN: the site runs without internet.
      locateFile: (file: string, prefix: string) => (file.endsWith(".wasm") ? zxingWasmUrl : prefix + file),
    },
    fireImmediately: true,
  });
  const options = { formats: ["QRCode" as const], tryHarder: true, maxNumberOfSymbols: 1 };
  return {
    engine: "zxing",
    async decode(source) {
      const context = source.getContext("2d", { willReadFrequently: true });
      if (!context) return null;
      const image = context.getImageData(0, 0, source.width, source.height);
      const found = await zxing.readBarcodes(image, options);
      return found[0]?.text ?? null;
    },
  };
}

let shared: Promise<QrDecoder> | null = null;

/** One decoder for the whole app (the ZXing module is heavy to instantiate). */
export function getQrDecoder(): Promise<QrDecoder> {
  shared ??= nativeDecoder().then((native) => native ?? zxingDecoder());
  shared.catch(() => { shared = null; }); // allow a retry after a failed load
  return shared;
}
