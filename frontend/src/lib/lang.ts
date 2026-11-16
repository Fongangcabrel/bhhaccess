import { safeStorage } from "./storage";

export type Lang = "fr" | "en";

const KEY = "bhh.lang";

/** The language chosen on this device / browser (French by default). */
export function getLang(): Lang {
  return safeStorage.get(KEY) === "en" ? "en" : "fr";
}

export function setLang(lang: Lang): void {
  safeStorage.set(KEY, lang);
  document.documentElement.lang = lang;
}
