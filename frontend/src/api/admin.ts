import type { ApiClient } from "./client";
import type {
  AccessUnit,
  AccessZone,
  Agent,
  AlertRow,
  AlertStatus,
  AlertType,
  AntiPassbackMode,
  Assignment,
  AuditFilters,
  AuditRow,
  Badge,
  Checkpoint,
  Department,
  Device,
  DeviceScopeIds,
  Direction,
  Employee,
  EmployeeInput,
  EmployeeStatus,
  Entity,
  BulkRequest,
  PhotoPurgeRequest,
  PurgeRequest,
  PurgeResult,
  BulkResult,
  ImportCheck,
  ImportReport,
  LogEntry,
  LogFilters,
  Me,
  Monitoring,
  Org,
  Presence,
  PresenceReport,
  MovementReport,
  RefusalTrend,
  ReportFilters,
  ReportKind,
  RevocationReason,
  Role,
  Schedule,
  Stats,
  TravelTime,
  Unit,
  ZoneSensitivity,
  UserRow,
  Zone,
} from "./types";

const query = (params: object): string => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) value.forEach((item) => search.append(key, String(item)));
    else if (value !== undefined && value !== "" && value !== null) search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : "";
};

/** Back-office calls: one method per endpoint, no UI logic. */
export class AdminApi {
  constructor(private readonly c: ApiClient) {}

  // session
  login(username: string, password: string) {
    return this.c.post<{ access_token: string }>("/auth/login", { username, password });
  }
  me() { return this.c.get<Me>("/auth/me"); }
  /** Returns a new session token; the other sessions of the account are closed. */
  changePassword(current: string, next: string) {
    return this.c.post<{ access_token: string }>("/auth/password", { current_password: current, new_password: next });
  }
  resetPassword(userId: number, password: string) {
    return this.c.post<UserRow>(`/users/${userId}/password`, { new_password: password });
  }

  // dashboard
  stats() { return this.c.get<Stats>("/stats/today"); }
  /** Live supervision: inside / left by unit and zone, posts, latest refusals. */
  monitoring(unitId?: number) { return this.c.get<Monitoring>(`/monitoring${query({ unit_id: unitId })}`); }
  presence(zoneId?: number) { return this.c.get<Presence[]>(`/presence${query({ zone_id: zoneId })}`); }
  unblock(employeeId: number, zoneId: number, mode: "sortie" | "entree", reason: string) {
    return this.c.post<void>("/presence/unblock", { employee_id: employeeId, zone_id: zoneId, mode, reason });
  }

  // employees
  /** Without status: current staff (active + suspended). Archived people only with status "ARCHIVE". */
  employees(q?: string, status?: EmployeeStatus) {
    return this.c.get<Employee[]>(`/employees${query({ q, status, limit: 200 })}`);
  }
  employee(id: number) { return this.c.get<Employee>(`/employees/${id}`); }
  createEmployee(input: EmployeeInput) { return this.c.post<Employee>("/employees", input); }
  updateEmployee(id: number, changes: Partial<EmployeeInput>) {
    return this.c.patch<Employee>(`/employees/${id}`, changes);
  }
  archiveEmployee(id: number, reason: string) {
    return this.c.post<Employee>(`/employees/${id}/archive`, { reason });
  }
  restoreEmployee(id: number) { return this.c.post<Employee>(`/employees/${id}/restore`, {}); }
  uploadPhoto(id: number, file: File) {
    const form = new FormData();
    form.append("file", file);
    return this.c.upload<Employee>(`/employees/${id}/photo`, form);
  }
  deletePhoto(id: number) { return this.c.delete(`/employees/${id}/photo`); }
  /** Suspend or reactivate only; archiving has its own call. */
  setEmployeeStatus(id: number, status: Exclude<EmployeeStatus, "ARCHIVE">) {
    return this.c.patch<Employee>(`/employees/${id}/status`, { status });
  }
  /** Step 2: create the conforming rows. */
  importEmployees(file: File, createMissingOrg: boolean) {
    return this.c.upload<ImportReport>(`/employees/import${query({ create_missing_org: createMissingOrg })}`, fileForm(file));
  }
  /** Same change for many employees (selection, or a whole department / entity). */
  bulkEmployees(body: BulkRequest) { return this.c.post<BulkResult>("/employees/bulk", body); }
  /** Step 1: check the file, nothing is written. */
  checkImport(file: File, createMissingOrg: boolean) {
    return this.c.upload<ImportCheck>(`/employees/import/check${query({ create_missing_org: createMissingOrg })}`, fileForm(file));
  }
  importRejected(file: File, createMissingOrg: boolean) {
    return this.c.uploadBlob(`/employees/import/rejected.xlsx${query({ create_missing_org: createMissingOrg })}`, fileForm(file));
  }
  importTemplate() { return this.c.blob("/employees/import/template.xlsx"); }
  entities() { return this.c.get<Entity[]>("/org/entities"); }
  departments() { return this.c.get<Department[]>("/org/departments"); }
  org() { return this.c.get<Org>("/org"); }
  createEntity(name: string) { return this.c.post<Entity>("/org/entities", { name }); }
  renameEntity(id: number, name: string) { return this.c.patch<Entity>(`/org/entities/${id}`, { name }); }
  deleteEntity(id: number) { return this.c.delete(`/org/entities/${id}`); }
  createDepartment(name: string) { return this.c.post<Department>("/org/departments", { name }); }
  renameDepartment(id: number, name: string) { return this.c.patch<Department>(`/org/departments/${id}`, { name }); }
  deleteDepartment(id: number) { return this.c.delete(`/org/departments/${id}`); }

  // badges & access
  badges(employeeId: number) { return this.c.get<Badge[]>(`/employees/${employeeId}/badges`); }
  issueBadge(employeeId: number) { return this.c.post<Badge>("/badges", { employee_id: employeeId }); }
  revokeBadge(badgeId: number, reason: RevocationReason, note?: string) {
    return this.c.post<Badge>(`/badges/${badgeId}/revoke`, { reason, note: note || null });
  }
  badgeQr(badgeId: number) { return this.c.blob(`/badges/${badgeId}/qr.png`); }
  /** Access of one employee, grouped by unit. A unit with no zone ticked comes back as REFUSE. */
  access(employeeId: number) { return this.c.get<AccessUnit[]>(`/employees/${employeeId}/access`); }
  /** Dates and weekly slots of one ticked zone; all empty = permanent access. */
  setRestrictions(employeeId: number, zoneId: number,
    body: { valid_from: string | null; valid_until: string | null; schedules: Schedule[] }) {
    return this.c.put<AccessZone>(`/employees/${employeeId}/access/${zoneId}/restrictions`, body);
  }
  setAccess(employeeId: number, zoneIds: number[]) {
    return this.c.put<AccessUnit[]>(`/employees/${employeeId}/access`, { zone_ids: zoneIds });
  }

  // zones
  zones() { return this.c.get<Zone[]>("/zones"); }
  checkpoints() { return this.c.get<Checkpoint[]>("/checkpoints"); }
  units() { return this.c.get<Unit[]>("/units"); }
  createUnit(name: string) { return this.c.post<Unit>("/units", { name }); }
  renameUnit(id: number, name: string) { return this.c.patch<Unit>(`/units/${id}`, { name }); }
  deleteUnit(id: number) { return this.c.delete(`/units/${id}`); }
  createZone(name: string, mode: AntiPassbackMode, unitId: number, warnAgent = false) {
    return this.c.post<Zone>("/zones", { name, antipassback_mode: mode, unit_id: unitId, antipassback_warn_agent: warnAgent });
  }
  updateZone(id: number, changes: Partial<{ name: string; code: string | null; description: string | null;
    sensitivity: ZoneSensitivity; is_active: boolean }>) {
    return this.c.patch<Zone>(`/zones/${id}`, changes);
  }
  deleteZone(id: number) { return this.c.delete(`/zones/${id}`); }
  moveZone(zoneId: number, unitId: number) { return this.c.patch<Zone>(`/zones/${zoneId}/unit`, { unit_id: unitId }); }
  /** ``warnAgent`` omitted: unchanged. The server clears it outside « Signalé ». */
  setZoneMode(id: number, mode: AntiPassbackMode, warnAgent?: boolean) {
    return this.c.patch<Zone>(`/zones/${id}/antipassback`, { antipassback_mode: mode, antipassback_warn_agent: warnAgent });
  }
  createCheckpoint(zoneId: number, name: string, direction: Direction) {
    return this.c.post<Checkpoint>(`/zones/${zoneId}/checkpoints`, { name, direction });
  }
  updateCheckpoint(id: number, changes: Partial<{ name: string; direction: Direction; is_active: boolean }>) {
    return this.c.patch<Checkpoint>(`/checkpoints/${id}`, changes);
  }
  deleteCheckpoint(id: number) { return this.c.delete(`/checkpoints/${id}`); }

  // phones paired for scanning (no login on the phone)
  devices() { return this.c.get<Device[]>("/devices"); }
  createDevice(name: string) { return this.c.post<{ device: Device; code: string }>("/devices", { name }); }
  newDeviceCode(id: number) { return this.c.post<{ device: Device; code: string }>(`/devices/${id}/code`, {}); }
  revokeDevice(id: number) { return this.c.post<Device>(`/devices/${id}/revoke`, {}); }
  renameDevice(id: number, name: string) { return this.c.patch<Device>(`/devices/${id}`, { name }); }
  setDeviceVoice(id: number, enabled: boolean) { return this.c.put<Device>(`/devices/${id}/voice`, { enabled }); }
  setDeviceScope(id: number, scope: DeviceScopeIds) { return this.c.put<Device>(`/devices/${id}/scope`, scope); }
  deleteDevice(id: number) { return this.c.delete(`/devices/${id}`); }

  // agents (recorded for reporting, they never log in)
  agents() { return this.c.get<Agent[]>("/agents"); }
  createAgent(fullName: string, matricule: string | null) {
    return this.c.post<Agent>("/agents", { full_name: fullName, matricule });
  }
  updateAgent(id: number, fullName: string, matricule: string | null) {
    return this.c.patch<Agent>(`/agents/${id}`, { full_name: fullName, matricule });
  }
  deleteAgent(id: number) { return this.c.delete(`/agents/${id}`); }
  setAgentActive(id: number, active: boolean) { return this.c.patch<Agent>(`/agents/${id}/active`, { is_active: active }); }
  /** keepOtherPosts: the agent also keeps the posts already held (single door: entry + exit). */
  assignAgent(checkpointId: number, agentId: number | null, keepOtherPosts = false) {
    return this.c.put<void>(`/checkpoints/${checkpointId}/agent`, { agent_id: agentId, keep_other_posts: keepOtherPosts });
  }
  assignments(agentId?: number) { return this.c.get<Assignment[]>(`/assignments${query({ agent_id: agentId, limit: 200 })}`); }

  // journal
  logs(filters: LogFilters, offset = 0, limit = 100) {
    return this.c.get<LogEntry[]>(`/logs${query({ ...filters, limit, offset })}`);
  }
  exportLogs(filters: LogFilters) { return this.c.blob(`/logs/export.csv${query(filters)}`); }
  /** Excel workbook or printable A4 landscape PDF, with the filters of the screen (audited). */
  exportJournal(filters: LogFilters, format: "xlsx" | "pdf", logIds?: number[]) {
    return this.c.blob(`/exports/journal.${format}${query({ ...filters, log_ids: logIds })}`);
  }
  exportEmployees(format: "xlsx" | "pdf", q?: string, status?: EmployeeStatus) {
    return this.c.blob(`/exports/employees.${format}${query({ q, status })}`);
  }
  exportAudit(format: "xlsx" | "pdf", filters: AuditFilters = {}) {
    return this.c.blob(`/exports/audit.${format}${query({ ...filters })}`);
  }
  // reports over a period (movements, presence by zone, refusal trends)
  movementReport(filters: ReportFilters) { return this.c.get<MovementReport>(`/reports/movements${query(filters)}`); }
  presenceReport(filters: ReportFilters) { return this.c.get<PresenceReport>(`/reports/presence${query(filters)}`); }
  refusalTrend(filters: ReportFilters) { return this.c.get<RefusalTrend>(`/reports/refusals${query(filters)}`); }
  exportReport(kind: ReportKind, format: "xlsx" | "pdf", filters: ReportFilters) {
    return this.c.blob(`/exports/${kind}.${format}${query(filters)}`);
  }
  /** The badge to print: QR (logo) + matricule at real size, with cut marks. */
  badgePdf(badgeId: number) { return this.c.blob(`/badges/${badgeId}/print.pdf`); }
  /** dry_run: only the number of lines (preview); otherwise deletes them (audited). */
  purge(body: PurgeRequest) { return this.c.post<PurgeResult>("/logs/purge", body); }
  purgePhotos(body: PhotoPurgeRequest) { return this.c.post<PurgeResult>("/photos/purge", body); }
  /** Newest first. */
  audit(filters: AuditFilters = {}, offset = 0, limit = 100) {
    return this.c.get<AuditRow[]>(`/audit${query({ ...filters, limit, offset })}`);
  }
  alerts(status?: AlertStatus, type?: AlertType, limit = 100) {
    return this.c.get<AlertRow[]>(`/alerts${query({ status, type, limit })}`);
  }
  alertCount() { return this.c.get<{ new: number }>("/alerts/count"); }
  ackAlert(id: number, note?: string) { return this.c.post<AlertRow>(`/alerts/${id}/ack`, { note: note || null }); }
  revokeFromAlert(id: number, reason: RevocationReason, note?: string) {
    return this.c.post<AlertRow>(`/alerts/${id}/revoke-badge`, { reason, note: note || null });
  }
  travelTimes() { return this.c.get<TravelTime[]>("/travel-times"); }
  setTravelTime(a: number, b: number, minutes: number) {
    return this.c.put<TravelTime>("/travel-times", { checkpoint_a_id: a, checkpoint_b_id: b, minutes });
  }
  deleteTravelTime(id: number) { return this.c.delete(`/travel-times/${id}`); }
  auditActors() { return this.c.get<{ id: number; name: string }[]>("/audit/actors"); }

  // users & roles
  users() { return this.c.get<UserRow[]>("/users"); }
  roles() { return this.c.get<Role[]>("/roles"); }
  createUser(input: { username: string; full_name: string; password: string; role_id: number }) {
    return this.c.post<UserRow>("/users", input);
  }
  setUserActive(id: number, active: boolean) { return this.c.patch<UserRow>(`/users/${id}/active`, { is_active: active }); }
  setUserRole(id: number, roleId: number) { return this.c.put<UserRow>(`/users/${id}/role`, { role_id: roleId }); }
  setOverride(id: number, permission: string, effect: "allow" | "deny") {
    return this.c.put<UserRow>(`/users/${id}/overrides`, { permission, effect });
  }
  clearOverride(id: number, permission: string) { return this.c.delete(`/users/${id}/overrides/${permission}`); }
  updateRole(id: number, permissions: string[]) { return this.c.put<Role>(`/roles/${id}`, { permissions }); }
  createRole(label: string, permissions: string[]) { return this.c.post<Role>("/roles", { label, permissions }); }
  renameRole(id: number, label: string) { return this.c.patch<Role>(`/roles/${id}`, { label }); }
  deleteRole(id: number) { return this.c.delete(`/roles/${id}`); }
}

function fileForm(file: File): FormData {
  const form = new FormData();
  form.append("file", file);
  return form;
}
