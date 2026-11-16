import { fireEvent, render, screen } from "@testing-library/react";
import type { ImportCheck } from "../api/types";

const check: ImportCheck = {
  file_name: "rh.xlsx", total: 3, valid: 1,
  rejected: [{ row: 3, matricule: "E1", errors: ["matricule en double dans le fichier"] },
    { row: 4, matricule: null, errors: ["matricule manquant"] }],
  new_entities: ["BHH"], new_departments: [],
  preview: [{ row: 2, matricule: "E1", last_name: "Ngono", first_name: "Paul", entity: "BHH", department: null, job_title: "Dev" }],
};
const admin = {
  checkImport: vi.fn(async () => check),
  importEmployees: vi.fn(async () => ({ created: 1, rejected: check.rejected, created_entities: ["BHH"], created_departments: [] })),
  importRejected: vi.fn(async () => new Blob(["x"])),
  importTemplate: vi.fn(async () => new Blob(["x"])),
};
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => true }) }));
vi.mock("../lib/format", async (original) => ({ ...(await original<object>()), downloadBlob: vi.fn() }));

import { ImportDialog } from "../admin/pages/EmployeesPage";

beforeEach(() => vi.clearAllMocks());

const choose = (size = 10) => {
  const file = new File(["x".repeat(size)], "rh.xlsx");
  fireEvent.change(screen.getByLabelText(/Fichier \.xlsx/), { target: { files: [file] } });
  return file;
};

it("checks first, shows what will happen, then creates only on confirmation", async () => {
  render(<ImportDialog onClose={vi.fn()} />);
  const file = choose();
  fireEvent.click(screen.getByRole("button", { name: "Vérifier le fichier" }));
  expect(await screen.findByText("Rien n'a encore été enregistré.")).toBeInTheDocument();
  expect(admin.checkImport).toHaveBeenCalledWith(file, false);
  expect(admin.importEmployees).not.toHaveBeenCalled();
  expect(screen.getByText("matricule en double dans le fichier")).toBeInTheDocument();
  expect(screen.getByText(/Entités qui seront créées/)).toHaveTextContent("BHH");
  expect(screen.getByText("Paul Ngono")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Télécharger (Excel)" }));
  await vi.waitFor(() => expect(admin.importRejected).toHaveBeenCalledWith(file, false));

  fireEvent.click(screen.getByRole("button", { name: "Créer 1 employé(s)" }));
  expect(await screen.findByText(/employé\(s\) créé\(s\)/)).toBeInTheDocument();
  expect(admin.importEmployees).toHaveBeenCalledWith(file, false);
});

it("refuses a file over 5 MB before sending it, and offers the template", async () => {
  render(<ImportDialog onClose={vi.fn()} />);
  choose(5 * 1024 * 1024 + 1);
  expect(screen.getByText("Fichier trop lourd : 5 Mo maximum.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Vérifier le fichier" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Télécharger le modèle" }));
  await vi.waitFor(() => expect(admin.importTemplate).toHaveBeenCalled());
});
