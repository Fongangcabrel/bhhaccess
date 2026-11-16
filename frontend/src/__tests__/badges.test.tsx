import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { Badge, Employee } from "../api/types";

const employee: Employee = {
  id: 7, matricule: "EMP-0042", last_name: "Ngono", first_name: "Paul", job_title: null,
  entity_id: null, department_id: null, entity_name: null, department_name: null,
  status: "ACTIF", archived_at: null, archive_reason: null, has_photo: false, photo_url: null,
};
const active: Badge = { id: 3, employee_id: 7, version: 2, status: "ACTIF", issued_at: "2026-11-12T08:00:00Z", expires_at: null };
const old: Badge = {
  id: 2, employee_id: 7, version: 1, status: "REVOQUE", issued_at: "2026-10-01T08:00:00Z", expires_at: null,
  revoked_at: "2026-11-12T08:00:00Z", revoked_reason: "REMPLACEMENT", revoked_note: null,
};
const admin = {
  employee: vi.fn(), badges: vi.fn(), access: vi.fn(async () => []), revokeBadge: vi.fn(), issueBadge: vi.fn(),
};
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => true }) }));

import { EmployeeDetailPage } from "../admin/pages/EmployeeDetailPage";

function show(status: Employee["status"] = "ACTIF") {
  admin.employee.mockResolvedValue({ ...employee, status });
  admin.badges.mockResolvedValue([active, old]);
  render(
    <MemoryRouter initialEntries={["/admin/employes/7"]}>
      <Routes><Route path="/admin/employes/:id" element={<EmployeeDetailPage />} /></Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => vi.clearAllMocks());

it("shows why an old badge stopped working", async () => {
  show();
  expect(await screen.findByText("Remplacement")).toBeInTheDocument();
});

it("revokes with the chosen reason, and « Autre » needs a note", async () => {
  admin.revokeBadge.mockResolvedValue({ ...active, status: "REVOQUE" });
  show();
  fireEvent.click(await screen.findByRole("button", { name: "Révoquer" }));
  fireEvent.click(screen.getByLabelText("Autre"));
  const submit = screen.getByRole("button", { name: "Révoquer le badge" });
  expect(submit).toBeDisabled();
  fireEvent.click(screen.getByLabelText("Vol"));
  fireEvent.change(screen.getByLabelText(/Précision/), { target: { value: "Au parking" } });
  fireEvent.click(submit);
  expect(admin.revokeBadge).toHaveBeenCalledWith(3, "VOL", "Au parking");
});

it("does not offer a badge to a suspended employee", async () => {
  show("SUSPENDU");
  expect(await screen.findByRole("button", { name: "Réémettre" })).toBeDisabled();
  expect(screen.getByText(/réactivez-le pour lui émettre un badge/)).toBeInTheDocument();
});
