import { fireEvent, render, screen, within } from "@testing-library/react";
import type { Org } from "../api/types";

const org: Org = {
  entities: [{ id: 1, name: "BHH Industrie", employees: 3 }, { id: 2, name: "BHH Logistique", employees: 0 }],
  departments: [{ id: 10, name: "Production", employees: 2 }, { id: 11, name: "Ressources humaines", employees: 1 }],
};
const admin = {
  org: vi.fn(async () => org),
  entities: vi.fn(async () => [{ id: 1, name: "BHH Industrie" }]),
  departments: vi.fn(async () => [{ id: 10, name: "Production" }]),
  createEntity: vi.fn(async (name: string) => ({ id: 3, name })),
  createDepartment: vi.fn(async (name: string) => ({ id: 12, name })),
  createEmployee: vi.fn(async () => ({})),
};
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => true }) }));

import { OrgPage } from "../admin/pages/OrgPage";
import { EmployeeForm } from "../admin/pages/EmployeesPage";

beforeEach(() => vi.clearAllMocks());

it("shows two separate lists with their employee counts", async () => {
  render(<OrgPage />);
  const entities = (await screen.findByRole("heading", { name: "Entités" })).closest("section")!;
  const departments = screen.getByRole("heading", { name: "Départements" }).closest("section")!;
  expect(within(entities).getByText("BHH Logistique").parentElement).toHaveTextContent("aucun employé");
  expect(within(departments).getByText("Production").parentElement).toHaveTextContent("2 employés");
  expect(within(entities).queryByText("Production")).not.toBeInTheDocument();
  fireEvent.change(within(departments).getByRole("textbox"), { target: { value: " Maintenance " } });
  fireEvent.click(within(departments).getByRole("button", { name: "Créer le département" }));
  await vi.waitFor(() => expect(admin.createDepartment).toHaveBeenCalledWith("Maintenance"));
});

it("picks entity and department independently and creates a missing department on the spot", async () => {
  render(<EmployeeForm onClose={vi.fn()} onDone={vi.fn()} />);
  await screen.findByRole("option", { name: "Production" });
  expect(screen.getByLabelText("Département")).toBeEnabled();  // no entity chosen: still selectable
  fireEvent.change(screen.getByLabelText("Département"), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText("Entité"), { target: { value: "1" } });
  expect(screen.getByLabelText("Département")).toHaveValue("10");  // changing the entity keeps it
  fireEvent.click(screen.getByRole("button", { name: "+ Nouveau département" }));
  admin.departments.mockResolvedValueOnce([{ id: 10, name: "Production" }, { id: 12, name: "Maintenance" }]);
  fireEvent.change(screen.getByLabelText("Nom du nouveau département"), { target: { value: "Maintenance" } });
  fireEvent.click(screen.getByRole("button", { name: "Ajouter" }));
  await vi.waitFor(() => expect(admin.createDepartment).toHaveBeenCalledWith("Maintenance"));
  await vi.waitFor(() => expect(screen.getByLabelText("Département")).toHaveValue("12"));
});
