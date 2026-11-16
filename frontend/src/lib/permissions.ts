import { tx } from "../i18n";
/** Catalogue of the 23 rights, grouped for display. Mirrors backend/app/domain/permissions.py. */
export const PERMISSION_GROUPS: { title: string; items: { key: string; label: string }[] }[] = [
  {
    title: tx("Employés"),
    items: [
      { key: "employees.view", label: tx("Voir les employés") },
      { key: "employees.edit", label: tx("Créer / modifier") },
      { key: "employees.import", label: tx("Importer Excel") },
      { key: "employees.archive", label: tx("Suspendre / archiver") },
    ],
  },
  {
    title: tx("Badges et accès"),
    items: [
      { key: "badges.issue", label: tx("Émettre un badge") },
      { key: "badges.revoke", label: tx("Révoquer un badge") },
      { key: "authorizations.manage", label: tx("Gérer les accès aux zones") },
    ],
  },
  {
    title: tx("Zones"),
    items: [
      { key: "zones.view", label: tx("Voir les zones") },
      { key: "zones.manage", label: tx("Créer zones et points") },
      { key: "zones.antipassback", label: tx("Régler le contrôle des entrées (zones)") },
    ],
  },
  {
    title: tx("Terrain"),
    items: [
      { key: "scan.perform", label: tx("Scanner") },
      { key: "scan.manual", label: tx("Saisie manuelle du matricule") },
      { key: "scan.history", label: tx("Historique de ses scans") },
      { key: "presence.unblock", label: tx("Débloquer une personne") },
    ],
  },
  {
    title: tx("Consultation"),
    items: [
      { key: "logs.view", label: tx("Voir le journal") },
      { key: "reports.view", label: tx("Voir les rapports") },
      { key: "audit.view", label: tx("Voir l'audit") },
      { key: "data.export", label: tx("Exporter les données") },
      { key: "data.purge", label: tx("Supprimer en lot") },
    ],
  },
  {
    title: tx("Administration"),
    items: [
      { key: "users.manage", label: tx("Gérer les comptes") },
      { key: "roles.assign", label: tx("Attribuer rôles et droits") },
      { key: "roles.manage", label: tx("Modifier les rôles") },
      { key: "system.config", label: tx("Configuration") },
    ],
  },
];

export const PERMISSION_LABELS: Record<string, string> = Object.fromEntries(
  PERMISSION_GROUPS.flatMap((g) => g.items.map((i) => [i.key, i.label])),
);

/** Rights that open the back-office at all. A pure field agent only sees the scan screen. */
const STAFF_RIGHTS = ["employees.view", "logs.view", "zones.manage", "users.manage", "authorizations.manage"];

export const isStaff = (permissions: string[]): boolean => STAFF_RIGHTS.some((r) => permissions.includes(r));
