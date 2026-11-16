import { PERMISSION_GROUPS, PERMISSION_LABELS, isStaff } from "../lib/permissions";

// Must stay in sync with backend/app/domain/permissions.py
const BACKEND_PERMISSIONS = [
  "employees.view", "employees.edit", "employees.import", "employees.archive",
  "badges.issue", "badges.revoke", "zones.view", "zones.manage", "zones.antipassback",
  "authorizations.manage", "scan.perform", "scan.manual", "scan.history", "presence.unblock",
  "logs.view", "reports.view", "audit.view", "data.export", "data.purge",
  "users.manage", "roles.assign", "roles.manage", "system.config",
];

describe("permissions catalogue", () => {
  it("lists exactly the 23 backend rights", () => {
    const keys = PERMISSION_GROUPS.flatMap((g) => g.items.map((i) => i.key));
    expect([...keys].sort()).toEqual([...BACKEND_PERMISSIONS].sort());
    expect(Object.keys(PERMISSION_LABELS)).toHaveLength(23);
  });

  it("sends pure field agents to the scan screen only", () => {
    expect(isStaff(["zones.view", "scan.perform", "scan.manual", "scan.history"])).toBe(false);
  });

  it("opens the back-office for HR and admins", () => {
    expect(isStaff(["employees.view", "badges.issue"])).toBe(true);
    expect(isStaff(["users.manage"])).toBe(true);
  });
});
