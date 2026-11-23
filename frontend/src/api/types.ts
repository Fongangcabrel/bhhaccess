/** Mirrors the backend contracts (app/schemas/dto.py). */
export type Direction = "ENTREE" | "SORTIE";

export type Verdict =
  | "AUTORISE"
  | "REFUSE_ZONE"
  | "REFUSE_REVOQUE"
  | "REFUSE_EXPIRE"
  | "REFUSE_EMPLOYE_INACTIF"
  | "REFUSE_INVALIDE"
  | "REFUSE_ANTIPASSBACK"
  | "SORTIE_ENREGISTREE";

export type Flag =
  | "SORTIE_BADGE_REVOQUE"
  | "SORTIE_BADGE_EXPIRE"
  | "SORTIE_EMPLOYE_SUSPENDU"
  | "DOUBLE_ENTREE"
  | "SORTIE_SANS_ENTREE"
  | "DEBLOQUE";

export interface Me {
  id: number;
  username: string;
  full_name: string;
  role: string;
  permissions: string[];
  /** Temporary password: the console stays closed until it is changed. */
  must_change_password: boolean;
}

export type ZoneSensitivity = "STANDARD" | "RESTREINTE" | "CRITIQUE";

export interface Zone {
  id: number;
  name: string;
  code: string | null;
  description: string | null;
  sensitivity: ZoneSensitivity;
  is_active: boolean;
  antipassback_mode: "DESACTIVE" | "SOUPLE" | "STRICT";
  /** « Signalé » only: the agent also sees « Double entrée détectée ». */
  antipassback_warn_agent?: boolean;
  unit_id: number;
  unit_name: string;
}

export interface Unit {
  id: number;
  name: string;
  zones: Zone[];
}

export interface Checkpoint {
  id: number;
  name: string;
  zone_id: number;
  direction: Direction;
  is_active: boolean;
  /** Post and its zone both active: phones can scan here. */
  usable: boolean;
  zone_name: string;
  unit_id: number;
  unit_name: string;
  agent_id: number | null;
  agent_name: string | null; // agent currently posted here
}

/** One weekly slot; ``end`` before ``start`` crosses midnight, equal means the whole day. */
export interface Schedule {
  weekdays: number[]; // 1 = lundi ... 7 = dimanche
  start: string; // "07:00"
  end: string;
}

export interface AccessZone {
  id: number;
  name: string;
  granted: boolean;
  is_active?: boolean;
  valid_from?: string | null;
  valid_until?: string | null;
  schedules?: Schedule[];
  /** Readable summary, empty when the access is permanent. */
  restrictions?: string;
  /** Ticked but outside its dates / hours right now. */
  usable_now?: boolean;
}

export interface AccessUnit {
  unit_id: number;
  unit_name: string;
  status: "ACCES" | "REFUSE";
  zones: AccessZone[];
}

export type DeviceStatus = "EN_ATTENTE" | "APPAIRE" | "REVOQUE";

export interface Device {
  id: number;
  name: string;
  status: DeviceStatus;
  created_at: string;
  paired_at: string | null;
  last_seen_at: string | null;
  revoked_at: string | null;
  code_expires_at: string | null;
  /** The phone says the result aloud. */
  voice_enabled?: boolean;
  /** "Tout le site" when no perimeter is set. */
  scope_summary?: string;
  scope_ids?: DeviceScopeIds;
  /** The post the phone holds now, e.g. « Portail (entrée) · Atelier · Usine ». */
  current_post?: string | null;
  checkpoint_since?: string | null;
}

/** One line of the phone's history (its own last scans, read only). */
export interface RecentScan {
  id: number;
  occurred_at: string;
  checkpoint_name: string;
  zone_name: string;
  direction: Direction;
  verdict: Verdict;
  method: "QR" | "MANUEL" | "CONSOLE";
  flags: string[];
  /** null for « QR non reconnu »: the phone learns nothing more. */
  employee_name: string | null;
  employee_matricule: string | null;
}

/** Units, zones and single posts a phone covers; all empty = the whole site. */
export interface DeviceScopeIds {
  unit_ids: number[];
  zone_ids: number[];
  checkpoint_ids: number[];
}

export interface AgentPost {
  checkpoint_id: number;
  checkpoint_name: string;
  direction: Direction;
  zone_name: string;
  unit_name: string;
  since: string;
}

export interface Agent {
  id: number;
  full_name: string;
  matricule: string | null;
  is_active: boolean;
  /** Every post held now (an agent may keep the entry and the exit of one door). */
  posts: AgentPost[];
  checkpoint_id: number | null;
  checkpoint_name: string | null;
  zone_name: string | null;
  unit_name: string | null;
}

export interface Assignment {
  id: number;
  agent_id: number;
  agent_name: string;
  checkpoint_id: number;
  checkpoint_name: string;
  zone_name: string;
  unit_name: string;
  started_at: string;
  ended_at: string | null;
}

export interface ScannedEmployee {
  id: number;
  matricule: string;
  last_name: string;
  first_name: string;
  job_title: string | null;
  department_name?: string | null;
  has_photo?: boolean;
  /** Signed URL valid 60 s; null when the employee has no photo. */
  photo_url?: string | null;
}

export interface ScanResult {
  verdict: Verdict;
  flags: Flag[];
  occurred_at: string;
  log_id: number;
  direction: Direction;
  zone: string;
  checkpoint: string;
  employee: ScannedEmployee | null;
  /** "DOUBLE_ENTREE" when the zone (mode « Signalé ») asks to warn the agent. */
  warning?: string | null;
  /** When the person was last recorded entering this zone (« Déjà entré », double entry). */
  last_entry_at?: string | null;
  last_entry_checkpoint?: string | null;
  /** Precise refusal: "Hors des horaires autorisés : lun–ven 07:00–18:00", "Accès à cette zone expiré"... */
  detail?: string | null;
  /** Alert raised by this scan, announced at the post (never EMPLOYE_ARCHIVE). */
  alert?: AlertType | null;
  /** Same badge at the same post within 3 s: the first answer again (same log_id), nothing new recorded. */
  repeat?: boolean;
}

// --- back-office ---------------------------------------------------------------
export type EmployeeStatus = "ACTIF" | "SUSPENDU" | "ARCHIVE";
export type AntiPassbackMode = "DESACTIVE" | "SOUPLE" | "STRICT";

export interface Employee {
  id: number;
  matricule: string;
  last_name: string;
  first_name: string;
  job_title: string | null;
  entity_id: number | null;
  department_id: number | null;
  entity_name: string | null;
  department_name: string | null;
  status: EmployeeStatus;
  archived_at: string | null;
  archive_reason: string | null;
  has_photo: boolean;
  /** Signed URL valid 60 s, only on the single-employee call. */
  photo_url: string | null;
}

export interface EmployeeInput {
  matricule: string;
  last_name: string;
  first_name: string;
  job_title?: string | null;
  entity_id?: number | null;
  department_id?: number | null;
}

export interface Entity {
  id: number;
  name: string;
}

/** An entity or a department, with how many employees use it (archived included). */
export interface OrgItem {
  id: number;
  name: string;
  employees: number;
}

/** Two independent lists: an employee picks one entity and one department. */
export interface Org {
  entities: OrgItem[];
  departments: OrgItem[];
}

export interface Department {
  id: number;
  name: string;
}

export interface Badge {
  id: number;
  employee_id: number;
  version: number;
  status: "ACTIF" | "REVOQUE";
  issued_at: string;
  expires_at: string | null;
  revoked_at?: string | null;
  revoked_reason?: RevocationReason | null;
  revoked_note?: string | null;
}

/** Why a badge stopped working. REMPLACEMENT is set by the server on re-issue only. */
export type RevocationReason = "PERTE" | "VOL" | "DEPART" | "REMPLACEMENT" | "AUTRE";

export interface Authorization {
  id: number;
  employee_id: number;
  zone_id: number;
  valid_until: string | null;
}

export interface LogEntry {
  id: number;
  occurred_at: string;
  employee_id: number | null;
  employee_name: string | null;
  employee_matricule: string | null;
  zone_id: number;
  zone_name: string;
  unit_id: number;
  unit_name: string;
  checkpoint_id: number;
  checkpoint_name: string;
  direction: Direction;
  verdict: Verdict;
  flags: Flag[];
  operator_id: number | null;
  device_id: number | null;
  device_name: string | null;
  agent_id: number | null;
  agent_name: string | null;
  reason: string | null;
  /** QR scanned, matricule typed by the agent, or manual unblock from the console. */
  method?: "QR" | "MANUEL" | "CONSOLE";
}

/** Journal lines to delete: every filter given must match. */
export interface PurgeRequest {
  date_from?: string;
  date_to?: string;
  employee_id?: number;
  department_id?: number;
  entity_id?: number;
  zone_id?: number;
  dry_run?: boolean;
}

export interface PhotoPurgeRequest {
  employee_ids?: number[];
  department_id?: number;
  entity_id?: number;
  archived_only?: boolean;
  dry_run?: boolean;
}

export interface PurgeResult {
  deleted: number;
  dry_run: boolean;
  filters: string[];
}

export interface LogFilters {
  employee_id?: number;
  department_id?: number;
  entity_id?: number;
  zone_id?: number;
  unit_id?: number;
  agent_id?: number;
  checkpoint_id?: number;
  verdict?: Verdict;
  direction?: Direction;
  date_from?: string;
  date_to?: string;
  flag?: Flag;
  method?: "QR" | "MANUEL" | "CONSOLE";
}

export interface Presence {
  employee_id: number;
  matricule: string;
  full_name: string;
  zone_id: number;
  zone_name: string;
  entered_at: string;
}

export interface Stats {
  since: string;
  total: number;
  entries_authorized: number;
  exits: number;
  refused: number;
  inside: number;
  by_verdict: Record<string, number>;
}

export interface Override {
  permission: string;
  effect: "allow" | "deny";
}

export interface UserRow {
  id: number;
  username: string;
  full_name: string;
  is_active: boolean;
  role_id: number;
  overrides: Override[];
  must_change_password: boolean;
}

export interface Role {
  id: number;
  name: string;
  label: string;
  permissions: string[];
}

export type BulkAction = "org" | "suspend" | "reactivate" | "archive" | "add_zones" | "remove_zones";

export interface BulkRequest {
  action: BulkAction;
  employee_ids?: number[];
  in_department_id?: number;
  in_entity_id?: number;
  /** « org »: only the fields present are changed; null clears it. */
  entity_id?: number | null;
  department_id?: number | null;
  zone_ids?: number[];
  reason?: string;
  dry_run?: boolean;
}

export interface BulkResult {
  action: BulkAction;
  dry_run: boolean;
  target: string;
  total: number;
  done: number;
  unchanged: number;
  failed: { employee_id: number; matricule: string; reason: string }[];
}

export interface ImportCheck {
  file_name: string | null;
  total: number;
  valid: number;
  rejected: { row: number; matricule: string | null; errors: string[] }[];
  new_entities: string[];
  new_departments: string[];
  preview: {
    row: number; matricule: string; last_name: string; first_name: string;
    entity: string | null; department: string | null; job_title: string | null;
  }[];
}

export interface ImportReport {
  created: number;
  rejected: { row: number; matricule: string | null; errors: string[] }[];
  created_entities: string[];
  created_departments: string[];
}

export interface AuditChange {
  field: string;
  label: string;
  before: unknown;
  after: unknown;
  before_text: string;
  after_text: string;
}

export interface AuditRow {
  id: number;
  occurred_at: string;
  actor_id: number | null;
  /** "Téléphone / système" when nobody was signed in (phone pairing). */
  actor_name: string | null;
  action: string;
  action_label: string;
  target: string | null;
  detail: Record<string, unknown>;
  ip: string | null;
  /** Same one-liner as the exports. */
  summary: string;
  /** Only the fields that changed. */
  changes: AuditChange[];
  /** The rest of the detail: motif, filtres, nombre de lignes… */
  other: string;
}

export interface AuditFilters {
  /** Category prefix: "badge", "employee"… */
  action?: string;
  actor_id?: number;
  system?: boolean;
  target?: string;
  date_from?: string;
  date_to?: string;
}

// --- live supervision (tableau de bord) ---------------------------------------------
export interface MonitorPerson {
  employee_id: number;
  full_name: string;
  matricule: string;
  department_name: string | null;
  /** Entered at (inside) or left at (exited). */
  at: string;
  checkpoint_name: string | null;
}

export interface MonitorZone {
  zone_id: number;
  zone_name: string;
  code: string | null;
  mode: AntiPassbackMode;
  is_active: boolean;
  inside: number;
  exited: number;
  entries: number;
  exits: number;
  refused: number;
  anomalies: number;
  last_activity: string | null;
  people_inside: MonitorPerson[];
  people_exited: MonitorPerson[];
}

export interface MonitorUnit {
  unit_id: number;
  unit_name: string;
  inside: number;
  exited: number;
  entries: number;
  exits: number;
  refused: number;
  anomalies: number;
  zones: MonitorZone[];
}

export interface MonitorPost {
  checkpoint_id: number;
  checkpoint_name: string;
  direction: Direction;
  zone_name: string;
  unit_name: string;
  usable: boolean;
  agent_name: string | null;
  scans_today: number;
  last_scan: string | null;
}

export interface MonitorRefusal {
  log_id: number;
  at: string;
  verdict: Verdict;
  employee_name: string | null;
  matricule: string | null;
  zone_name: string;
  checkpoint_name: string;
  agent_name: string | null;
  reason: string | null;
}

export interface Monitoring {
  generated_at: string;
  since: string;
  totals: { entries: number; exits: number; refused: number; unknown_qr: number; anomalies: number;
    inside: number; exited: number; flags: Record<string, number> };
  units: MonitorUnit[];
  posts: MonitorPost[];
  recent_refusals: MonitorRefusal[];
}

// --- alerts (suspicious badge use) ---------------------------------------------------
export type AlertType = "SIMULTANEE" | "BADGE_REVOQUE" | "EMPLOYE_ARCHIVE" | "HORS_HORAIRE" | "RAFALE" | "REFUS_REPETES";
export type AlertStatus = "NOUVELLE" | "PRISE_EN_COMPTE";

export interface AlertRow {
  id: number;
  created_at: string;
  type: AlertType;
  status: AlertStatus;
  message: string;
  detail: Record<string, unknown>;
  badge_id: number | null;
  employee_id: number | null;
  access_log_id: number | null;
  checkpoint_id: number | null;
  handled_at: string | null;
  note: string | null;
  employee_name: string | null;
  employee_matricule: string | null;
  checkpoint_name: string | null;
  zone_name: string | null;
}

export interface TravelTime {
  id: number;
  checkpoint_a_id: number;
  checkpoint_b_id: number;
  min_seconds: number;
  checkpoint_a_name: string | null;
  checkpoint_b_name: string | null;
}

// --- reports over a period (tâche 32) --------------------------------------------------------
export interface ReportFilters {
  date_from?: string;
  date_to?: string;
  employee_id?: number;
  department_id?: number;
  entity_id?: number;
  unit_id?: number;
  zone_id?: number;
}

export interface MovementRow {
  employee_id: number;
  matricule: string;
  full_name: string;
  entity_name: string | null;
  department_name: string | null;
  unit_name: string;
  zone_id: number;
  zone_name: string;
  entries: number;
  exits: number;
  refused: number;
  unblocks: number;
  first_at: string;
  last_at: string;
}

export interface MovementReport {
  rows: MovementRow[];
  employees: number;
  entries: number;
  exits: number;
  refused: number;
  unblocks: number;
}

export interface ZonePresenceRow {
  unit_name: string;
  zone_id: number;
  zone_name: string;
  mode: AntiPassbackMode;
  /** null: zone in "Libre" mode, presence is not kept. */
  inside_now: number | null;
  people: number;
  entries: number;
  exits: number;
  refused: number;
}

export interface PresenceReport {
  rows: ZonePresenceRow[];
  inside_now: number;
  entries: number;
  exits: number;
  refused: number;
}

export interface TrendDay {
  day: string;
  total: number;
  by_verdict: Partial<Record<Verdict, number>>;
}

export interface RefusalTrend {
  date_from: string;
  date_to: string;
  total: number;
  previous_total: number;
  days: TrendDay[];
  by_verdict: Partial<Record<Verdict, number>>;
  by_zone: { zone_id: number; zone_name: string; unit_name: string; count: number }[];
  by_employee: { employee_id: number; matricule: string; full_name: string; count: number }[];
  unknown_qr: number;
}

export type ReportKind = "movements" | "presence" | "refusals";
