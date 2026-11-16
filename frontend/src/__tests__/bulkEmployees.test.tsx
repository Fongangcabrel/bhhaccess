import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { BulkRequest, Employee } from "../api/types";

const person = (id: number, matricule: string, last_name: string) => ({
  id, matricule, last_name, first_name: "X", status: "ACTIF", entity_name: null, department_name: "Production",
  job_title: null,
}) as unknown as Employee;
const done = (body: BulkRequest) => ({
  action: body.action, dry_run: !!body.dry_run, target: "x", total: body.dry_run ? 7 : 2, done: body.dry_run ? 0 : 1,
  unchanged: body.dry_run ? 0 : 1, failed: [],
});
const admin = {
  employees: vi.fn(async () => [person(1, "P1", "Abena"), person(2, "P2", "Biya"), person(3, "P3", "Chi")]),
  bulkEmployees: vi.fn(async (body: BulkRequest) => done(body)),
  entities: vi.fn(async () => [{ id: 5, name: "BHH Industrie" }]),
  departments: vi.fn(async () => [{ id: 10, name: "Production" }]),
  zones: vi.fn(async () => [{ id: 20, name: "Atelier", unit_name: "Usine", is_active: true }]),
};
let rights = new Set(["employees.view", "employees.edit", "authorizations.manage"]);
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: (r: string) => rights.has(r) }) }));

import { EmployeesPage } from "../admin/pages/EmployeesPage";

beforeEach(() => {
  vi.clearAllMocks();
  rights = new Set(["employees.view", "employees.edit", "authorizations.manage"]);
});

const page = async () => {
  render(<MemoryRouter><EmployeesPage /></MemoryRouter>);
  await screen.findByText("P1");
};

it("suspends a selection and reports what happened", async () => {
  await page();
  expect(screen.queryByRole("toolbar")).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Sélectionner X Abena"));
  fireEvent.click(screen.getByLabelText("Sélectionner X Biya"));
  const bar = screen.getByRole("toolbar");
  expect(bar).toHaveTextContent("2 sélectionné(s)");
  expect(within(bar).queryByRole("button", { name: "Archiver" })).not.toBeInTheDocument(); // no archive right
  fireEvent.click(within(bar).getByRole("button", { name: "Suspendre" }));
  fireEvent.click(screen.getByRole("button", { name: "Appliquer à 2 employé(s)" }));
  expect(await screen.findByText("1 modifié(s), 1 déjà à jour, 0 en échec, sur 2.")).toBeInTheDocument();
  expect(admin.bulkEmployees).toHaveBeenCalledWith({ action: "suspend", employee_ids: [1, 2] });
});

it("changes only the department, and selects all shown at once", async () => {
  await page();
  fireEvent.click(screen.getByLabelText("Sélectionner tous les employés affichés"));
  fireEvent.click(within(screen.getByRole("toolbar")).getByRole("button", { name: "Entité / département" }));
  await screen.findByRole("option", { name: "Production" });
  const apply = screen.getByRole("button", { name: "Appliquer à 3 employé(s)" });
  expect(apply).toBeDisabled(); // nothing chosen yet
  fireEvent.change(screen.getByLabelText("Département"), { target: { value: "10" } });
  fireEvent.click(apply);
  await vi.waitFor(() => expect(admin.bulkEmployees).toHaveBeenCalledWith(
    { action: "org", employee_ids: [1, 2, 3], department_id: 10 }));
});

it("gives zones to a whole department after counting the people concerned", async () => {
  await page();
  fireEvent.click(screen.getByRole("button", { name: "Zones par département" }));
  await screen.findByRole("option", { name: "Production" });
  fireEvent.change(screen.getByLabelText("Département"), { target: { value: "10" } });
  fireEvent.click(await screen.findByLabelText("Atelier"));
  fireEvent.click(screen.getByRole("button", { name: "Compter les employés concernés" }));
  expect(await screen.findByText("7 employé(s) concerné(s).")).toBeInTheDocument();
  expect(admin.bulkEmployees).toHaveBeenLastCalledWith(
    { action: "add_zones", zone_ids: [20], dry_run: true, in_department_id: 10 });
  fireEvent.click(screen.getByRole("button", { name: "Ajouter les zones" }));
  await vi.waitFor(() => expect(admin.bulkEmployees).toHaveBeenLastCalledWith(
    { action: "add_zones", zone_ids: [20], dry_run: false, in_department_id: 10 }));
});

it("offers no selection without any bulk right", async () => {
  rights = new Set(["employees.view"]);
  await page();
  expect(screen.queryByLabelText("Sélectionner tous les employés affichés")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Zones par département" })).not.toBeInTheDocument();
});
