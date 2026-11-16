import type { AlertType, ScanResult, Verdict } from "../api/types";
import type { Lang } from "./lang";

/** What the phone says after a scan; short sentences, understood without looking at the screen. */
const VERDICT_SPEECH: Record<Lang, Record<Verdict, string>> = {
  fr: {
    AUTORISE: "Entrée autorisée",
    SORTIE_ENREGISTREE: "Sortie enregistrée",
    REFUSE_ZONE: "Accès refusé. Zone non autorisée",
    REFUSE_REVOQUE: "Accès refusé. Badge révoqué",
    REFUSE_EXPIRE: "Accès refusé. Badge expiré",
    REFUSE_EMPLOYE_INACTIF: "Accès refusé. Employé suspendu",
    REFUSE_INVALIDE: "QR non reconnu",
    REFUSE_ANTIPASSBACK: "Accès refusé. Déjà à l'intérieur",
  },
  en: {
    AUTORISE: "Entry granted",
    SORTIE_ENREGISTREE: "Exit recorded",
    REFUSE_ZONE: "Access denied. Zone not allowed",
    REFUSE_REVOQUE: "Access denied. Badge revoked",
    REFUSE_EXPIRE: "Access denied. Badge expired",
    REFUSE_EMPLOYE_INACTIF: "Access denied. Employee suspended",
    REFUSE_INVALIDE: "QR code not recognised",
    REFUSE_ANTIPASSBACK: "Access denied. Already inside",
  },
};

/** Alert raised by the scan, said after the verdict (the badge revoked case is already in the verdict). */
const ALERT_SPEECH: Record<Lang, Partial<Record<AlertType, string>> & { prefix: string }> = {
  fr: {
    prefix: "Alerte sécurité",
    SIMULTANEE: "badge déjà utilisé à un autre poste il y a peu",
    HORS_HORAIRE: "hors des horaires autorisés",
    REFUS_REPETES: "refus répétés",
    RAFALE: "scans répétés du même badge",
  },
  en: {
    prefix: "Security alert",
    SIMULTANEE: "badge just used at another post",
    HORS_HORAIRE: "outside the allowed hours",
    REFUS_REPETES: "repeated refusals",
    RAFALE: "same badge scanned repeatedly",
  },
};

const DOUBLE_ENTRY: Record<Lang, string> = { fr: "Attention : double entrée", en: "Warning: double entry" };

/** Back-office: the alerts as named on the alerts screen. */
export const ALERT_NAME: Record<Lang, Record<AlertType, string>> = {
  fr: {
    SIMULTANEE: "utilisation simultanée",
    BADGE_REVOQUE: "badge révoqué présenté",
    EMPLOYE_ARCHIVE: "QR d'un employé archivé",
    HORS_HORAIRE: "tentative hors horaires",
    RAFALE: "rafale de scans",
    REFUS_REPETES: "refus répétés",
  },
  en: {
    SIMULTANEE: "simultaneous use",
    BADGE_REVOQUE: "revoked badge presented",
    EMPLOYE_ARCHIVE: "archived employee's QR code",
    HORS_HORAIRE: "attempt outside hours",
    RAFALE: "burst of scans",
    REFUS_REPETES: "repeated refusals",
  },
};
const NEW_ALERT: Record<Lang, string> = { fr: "Nouvelle alerte", en: "New alert" };

/** « Entrée autorisée. Jean Mbarga. » / « Accès refusé. Badge révoqué. Jean Mbarga. Alerte sécurité. » */
export function scanAnnouncement(result: ScanResult, lang: Lang): string {
  const parts = [VERDICT_SPEECH[lang][result.verdict]];
  if (result.employee) parts.push(`${result.employee.first_name} ${result.employee.last_name}`);
  if (result.warning === "DOUBLE_ENTREE") parts.push(DOUBLE_ENTRY[lang]);
  if (result.alert) {
    const what = ALERT_SPEECH[lang][result.alert];
    parts.push(what ? `${ALERT_SPEECH[lang].prefix} : ${what}` : ALERT_SPEECH[lang].prefix);
  }
  return `${parts.join(". ")}.`;
}

/** « Nouvelle alerte : utilisation simultanée. Jean Mbarga. Accueil. » */
export function alertAnnouncement(
  alert: { type: AlertType; employee_name: string | null; checkpoint_name: string | null },
  lang: Lang,
): string {
  const parts = [`${NEW_ALERT[lang]} : ${ALERT_NAME[lang][alert.type]}`];
  if (alert.employee_name) parts.push(alert.employee_name);
  if (alert.checkpoint_name) parts.push(alert.checkpoint_name);
  return `${parts.join(". ")}.`;
}

/** Speech synthesis of the phone / computer (works offline with the installed voices). Never throws. */
export function speak(text: string, lang: Lang): void {
  try {
    const synth = window.speechSynthesis;
    if (!synth || typeof SpeechSynthesisUtterance === "undefined") return;
    synth.cancel(); // the next person: never queue an old announcement
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === "fr" ? "fr-FR" : "en-GB";
    const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(lang));
    if (voice) utterance.voice = voice;
    utterance.rate = 1.05;
    synth.speak(utterance);
  } catch {
    /* no speech synthesis: the beep remains */
  }
}
