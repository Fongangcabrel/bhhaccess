import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";
import { getLang, type Lang, setLang as storeLang } from "../lib/lang";
import { ADMIN_EN } from "./admin";
import { en, fr, type MessageKey } from "./messages";

const DICTIONARIES: Record<Lang, Record<MessageKey, string>> = { fr, en };

/** Text in the given language; « {name} » placeholders are filled from ``vars``. */
export function translate(lang: Lang, key: MessageKey, vars?: Record<string, string | number>): string {
  const text = DICTIONARIES[lang][key] ?? fr[key];
  return vars ? text.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`)) : text;
}

/** Outside React (API client, formatting): the language saved on this device. */
export const t = (key: MessageKey, vars?: Record<string, string | number>) => translate(getLang(), key, vars);

type Vars = (string | number | null | undefined)[] | Record<string, string | number | null | undefined>;

/**
 * Back-office texts: the French text is the key, ``ADMIN_EN`` gives the English one.
 * « {0} », « {name} » are filled from ``vars``. The back-office reloads when the language changes,
 * so texts computed once (menus, label tables) follow too.
 */
export function tx(french: string, vars?: Vars): string {
  const text = getLang() === "en" ? (ADMIN_EN[french] ?? french) : french;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (_whole, name: string) => {
    const value = (vars as Record<string, unknown>)[name];
    return value === undefined || value === null ? "" : String(value);
  });
}

interface LangState {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
}

const LangContext = createContext<LangState>({
  lang: "fr",
  setLang: storeLang,
  t: (key, vars) => translate("fr", key, vars),
});

/** The chosen language, remembered on the device; changing it re-renders every screen at once. */
export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setState] = useState<Lang>(getLang);
  const setLang = useCallback((next: Lang) => {
    storeLang(next);
    setState(next);
  }, []);
  const value = useMemo(() => ({ lang, setLang, t: (key: MessageKey, vars?: Record<string, string | number>) =>
    translate(lang, key, vars) }), [lang, setLang]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export const useT = () => useContext(LangContext);

/** FR | EN. ``reload``: the back-office reloads so that every text (menus included) follows. */
export function LangSwitch({ reload = false }: { reload?: boolean }) {
  const { lang, setLang, t: tr } = useT();
  return (
    <div className="lang-switch" role="group" aria-label={tr("lang.label")}>
      {(["fr", "en"] as const).map((code) => (
        <button key={code} type="button" aria-pressed={lang === code} className={lang === code ? "on" : ""}
          onClick={() => {
            if (code === lang) return;
            setLang(code);
            if (reload) window.location.reload();
          }}>
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
