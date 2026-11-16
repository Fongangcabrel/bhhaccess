import { tx } from "../i18n";
import type { AntiPassbackMode } from "../api/types";

/**
 * Plain-language names for the zone "anti-passback" setting (the technical term stays in the code).
 * Shown as « Contrôle des entrées ».
 */
export const CONTROL_MODES: { value: AntiPassbackMode; label: string; hint: string }[] = [
  { value: "DESACTIVE", label: tx("Libre"), hint: tx("On vérifie seulement que la personne a accès à la zone.") },
  { value: "SOUPLE", label: tx("Signalé"), hint: tx("Une 2e entrée sans sortie est notée dans le journal, sans bloquer.") },
  { value: "STRICT", label: tx("Sortie obligatoire"), hint: tx("Pas de 2e entrée tant que la sortie n'est pas enregistrée.") },
];

export const controlMode = (mode: AntiPassbackMode) => CONTROL_MODES.find((m) => m.value === mode) ?? CONTROL_MODES[0];
