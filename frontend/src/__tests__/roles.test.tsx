import { fireEvent, render, screen, within } from "@testing-library/react";
import type { Role } from "../api/types";

const roles: Role[] = [
  { id: 1, name: "super_admin", label: "Super admin", permissions: ["logs.view", "data.purge"], is_template: true, users: 1 },
  { id: 3, name: "rh", label: "RH", permissions: ["logs.view", "data.purge"], is_template: true, users: 2 },
  { id: 7, name: "chef", label: "Chef de quart", permissions: ["logs.view"], is_template: false, users: 0 },
  { id: 8, name: "lecteurs", label: "Lecteurs", permissions: [], is_template: false, users: 3 },
];
const accounts = [
  { id: 1, username: "admin", full_name: "Admin", role_id: 1, is_active: true, must_change_password: false, overrides: [] },
  { id: 2, username: "rh1", full_name: "RH Un", role_id: 3, is_active: true, must_change_password: false, overrides: [] },
];
const admin = {
  users: vi.fn(async () => accounts),
  setUserActive: vi.fn(async () => ({})),
  roles: vi.fn(async () => roles),
  updateRole: vi.fn(async () => ({})),
  createRole: vi.fn(async () => ({})),
  renameRole: vi.fn(async () => ({})),
  deleteRole: vi.fn(async () => ({})),
};
let rights = ["roles.assign", "roles.manage", "logs.view"];
let myRole = "super_admin";
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ admin, can: (r: string) => rights.includes(r), user: { id: 9, role: myRole } }),
}));

import { UsersPage } from "../admin/pages/UsersPage";

beforeEach(() => {
  vi.clearAllMocks();
  rights = ["roles.assign", "roles.manage", "logs.view"];
  myRole = "super_admin";
  vi.stubGlobal("confirm", vi.fn(() => true));
});
afterEach(() => vi.unstubAllGlobals());

async function openRoles() {
  render(<UsersPage />);
  fireEvent.click(screen.getByRole("button", { name: "Rôles" }));
  return screen.findByRole("table");
}

it("shows each action with its code, and custom roles with their accounts", async () => {
  const table = await openRoles();
  expect(within(table).getByText("badges.revoke")).toBeInTheDocument();
  expect(within(table).getByText("Personnalisé · 3 compte(s)")).toBeInTheDocument();
  expect(within(table).queryByRole("button", { name: "Supprimer le rôle RH" })).not.toBeInTheDocument();
  expect(within(table).getByRole("button", { name: "Supprimer le rôle Lecteurs" })).toBeDisabled(); // in use
});

it("creates a role from a template, keeping only the rights one holds", async () => {
  await openRoles();
  fireEvent.click(screen.getByRole("button", { name: "+ Nouveau rôle" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Nom du rôle"), { target: { value: "Contrôleurs" } });
  fireEvent.change(within(dialog).getByLabelText("Partir de"), { target: { value: "3" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Créer le rôle" }));
  await vi.waitFor(() => expect(admin.createRole).toHaveBeenCalledWith("Contrôleurs", ["logs.view"])); // no data.purge
});

it("renames and deletes an unused custom role", async () => {
  const table = await openRoles();
  fireEvent.click(within(table).getByRole("button", { name: "Renommer le rôle Chef de quart" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Nom du rôle"), { target: { value: "Chef d'équipe" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Renommer" }));
  await vi.waitFor(() => expect(admin.renameRole).toHaveBeenCalledWith(7, "Chef d'équipe"));
  fireEvent.click(within(table).getByRole("button", { name: "Supprimer le rôle Chef de quart" }));
  await vi.waitFor(() => expect(admin.deleteRole).toHaveBeenCalledWith(7));
});

it("without roles.manage: no creation, no renaming", async () => {
  rights = ["roles.assign"];
  const table = await openRoles();
  expect(screen.queryByRole("button", { name: "+ Nouveau rôle" })).not.toBeInTheDocument();
  expect(within(table).queryByRole("button", { name: /Renommer le rôle/ })).not.toBeInTheDocument();
});

it("only a super admin sees the actions on a super admin account", async () => {
  myRole = "super_user";
  render(<UsersPage />);
  const adminRow = (await screen.findByText("admin")).closest("tr")!;
  expect(within(adminRow).getByText("Réservé aux super admins")).toBeInTheDocument();
  expect(within(adminRow).queryByRole("button", { name: "Désactiver" })).not.toBeInTheDocument();
  const rhRow = screen.getByText("rh1").closest("tr")!;
  expect(within(rhRow).getByRole("button", { name: "Désactiver" })).toBeInTheDocument();
});
