import type { Flag, Verdict } from "../api/types";
import { getLang, type Lang } from "./lang";

export type Tone = "ok" | "exit" | "deny";

export interface VerdictView {
  tone: Tone;
  title: string;
  short: string;
  hint: string;
}

const TONES: Record<Verdict, Tone> = {
  AUTORISE: "ok",
  SORTIE_ENREGISTREE: "exit",
  REFUSE_ZONE: "deny",
  REFUSE_REVOQUE: "deny",
  REFUSE_EXPIRE: "deny",
  REFUSE_EMPLOYE_INACTIF: "deny",
  REFUSE_INVALIDE: "deny",
  REFUSE_ANTIPASSBACK: "deny",
};

type Words = Omit<VerdictView, "tone">;

/** Pure mapping verdict -> what the agent sees. Keep wording short: read in one second. */
const WORDS: Record<Lang, Record<Verdict, Words>> = {
  fr: {
    AUTORISE: { short: "Autorisé", title: "ACCÈS AUTORISÉ", hint: "Comparez la photo avec la personne." },
    SORTIE_ENREGISTREE: { short: "Sortie", title: "SORTIE ENREGISTRÉE", hint: "" },
    REFUSE_ZONE: { short: "Refusé : zone", title: "ZONE NON AUTORISÉE", hint: "Cette personne n'a pas accès ici." },
    REFUSE_REVOQUE: { short: "Refusé : révoqué", title: "BADGE RÉVOQUÉ", hint: "Badge perdu, remplacé ou retiré." },
    REFUSE_EXPIRE: { short: "Refusé : expiré", title: "BADGE EXPIRÉ", hint: "Orienter vers les RH." },
    REFUSE_EMPLOYE_INACTIF: { short: "Refusé : suspendu", title: "EMPLOYÉ SUSPENDU", hint: "Signalez-le à la sécurité." },
    REFUSE_INVALIDE: { short: "QR non reconnu", title: "QR NON RECONNU", hint: "Réessayez ou saisissez le matricule." },
    REFUSE_ANTIPASSBACK: {
      short: "Refusé : déjà à l'intérieur",
      title: "DÉJÀ À L'INTÉRIEUR",
      hint: "Sortie obligatoire avant de rentrer : appelez un responsable pour débloquer.",
    },
  },
  en: {
    AUTORISE: { short: "Granted", title: "ACCESS GRANTED", hint: "Compare the photo with the person." },
    SORTIE_ENREGISTREE: { short: "Exit", title: "EXIT RECORDED", hint: "" },
    REFUSE_ZONE: { short: "Denied: zone", title: "ZONE NOT ALLOWED", hint: "This person has no access here." },
    REFUSE_REVOQUE: { short: "Denied: revoked", title: "BADGE REVOKED", hint: "Badge lost, replaced or withdrawn." },
    REFUSE_EXPIRE: { short: "Denied: expired", title: "BADGE EXPIRED", hint: "Send the person to HR." },
    REFUSE_EMPLOYE_INACTIF: { short: "Denied: suspended", title: "EMPLOYEE SUSPENDED", hint: "Report it to security." },
    REFUSE_INVALIDE: { short: "QR not recognised", title: "QR NOT RECOGNISED", hint: "Try again or type the employee number." },
    REFUSE_ANTIPASSBACK: {
      short: "Denied: already inside",
      title: "ALREADY INSIDE",
      hint: "Exit required before coming back in: call a manager to unblock.",
    },
  },
};

const FLAGS: Record<Lang, Record<Flag, string>> = {
  fr: {
    SORTIE_BADGE_REVOQUE: "Badge révoqué",
    SORTIE_BADGE_EXPIRE: "Badge expiré",
    SORTIE_EMPLOYE_SUSPENDU: "Employé suspendu",
    DOUBLE_ENTREE: "Double entrée (sortie non enregistrée)",
    SORTIE_SANS_ENTREE: "Sortie sans entrée enregistrée",
    DEBLOQUE: "Passage après un déblocage manuel",
  },
  en: {
    SORTIE_BADGE_REVOQUE: "Badge revoked",
    SORTIE_BADGE_EXPIRE: "Badge expired",
    SORTIE_EMPLOYE_SUSPENDU: "Employee suspended",
    DOUBLE_ENTREE: "Double entry (exit not recorded)",
    SORTIE_SANS_ENTREE: "Exit without a recorded entry",
    DEBLOQUE: "Passage after a manual unblock",
  },
};

export const describeVerdict = (verdict: Verdict, lang: Lang = getLang()): VerdictView => ({
  tone: TONES[verdict],
  ...WORDS[lang][verdict],
});
export const describeFlag = (flag: Flag, lang: Lang = getLang()): string => FLAGS[lang][flag];

export const ALL_VERDICTS = Object.keys(TONES) as Verdict[];
export const ALL_FLAGS = Object.keys(FLAGS.fr) as Flag[];
