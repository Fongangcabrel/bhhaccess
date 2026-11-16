import { getLang } from "./lang";
const TZ = "Africa/Douala";
const locale = () => (getLang() === "en" ? "en-GB" : "fr-FR");

export const formatDateTime = (iso: string): string =>
  new Date(iso).toLocaleString(locale(), { timeZone: TZ, dateStyle: "short", timeStyle: "medium" });

export const formatTime = (iso: string): string =>
  new Date(iso).toLocaleTimeString(locale(), { timeZone: TZ, hour: "2-digit", minute: "2-digit" });

/** "2026-11-11" (from <input type=date>) -> ISO bounds in local Douala time (UTC+1, no DST). */
export const startOfDayIso = (date: string): string => `${date}T00:00:00+01:00`;
export const endOfDayIso = (date: string): string => `${date}T23:59:59+01:00`;

/** Today's date for file names, e.g. 20261112-1405. */
export const stamp = (): string => {
  const d = new Date();
  const two = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${two(d.getMonth() + 1)}${two(d.getDate())}-${two(d.getHours())}${two(d.getMinutes())}`;
};

/** Open a PDF in a new tab (to print it); falls back to a download when pop-ups are blocked. */
export function openPdf(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const tab = window.open(url, "_blank");
  if (!tab) downloadBlob(blob, filename);
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
