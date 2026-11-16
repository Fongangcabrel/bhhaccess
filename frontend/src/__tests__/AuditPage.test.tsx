import { fireEvent, render, screen, within } from "@testing-library/react";
import type { AuditRow } from "../api/types";

const row: AuditRow = {
  id: 9, occurred_at: "2026-11-12T08:00:00Z", actor_id: 1, actor_name: "Awa Mballa",
  action: "zone.antipassback", action_label: "Contrôle des entrées changé", target: "Usine",
  detail: { before: { mode: "STRICT" }, after: { mode: "SOUPLE" } }, ip: "10.0.0.7",
  summary: "Contrôle des entrées : Sortie obligatoire → Signalé",
  changes: [{ field: "mode", label: "Contrôle des entrées", before: "STRICT", after: "SOUPLE",
    before_text: "Sortie obligatoire", after_text: "Signalé" }],
  other: "",
};
const pairing: AuditRow = {
  ...row, id: 8, actor_id: null, actor_name: "Téléphone / système", action: "device.pair",
  action_label: "Téléphone appairé", target: "Poste Nord", detail: {}, changes: [], other: "", summary: "",
};
const admin = {
  audit: vi.fn(async () => [row, pairing]),
  auditActors: vi.fn(async () => [{ id: 1, name: "Awa Mballa" }]),
  exportAudit: vi.fn(async () => new Blob()),
};
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => true }) }));

import { AuditPage } from "../admin/pages/AuditPage";

beforeEach(() => vi.clearAllMocks());

it("shows who changed what, before and after, and from where", async () => {
  render(<AuditPage />);
  const line = (await screen.findByText("Contrôle des entrées changé")).closest("tr")!;
  expect(within(line).getByTitle("Avant")).toHaveTextContent("Sortie obligatoire");
  expect(within(line).getByTitle("Après")).toHaveTextContent("Signalé");
  expect(within(line).getByText("Awa Mballa")).toBeInTheDocument();
  expect(within(line).getByText("10.0.0.7")).toBeInTheDocument();
  expect(screen.getByText("Téléphone appairé")).toBeInTheDocument();
});

it("filters by category, author and object, and exports with the same filters", async () => {
  render(<AuditPage />);
  await screen.findByRole("option", { name: "Awa Mballa" });
  fireEvent.change(screen.getByLabelText("Catégorie"), { target: { value: "zone" } });
  fireEvent.change(screen.getByLabelText("Auteur"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("Objet"), { target: { value: " Usine " } });
  fireEvent.click(screen.getByRole("button", { name: "Filtrer" }));
  const filters = { action: "zone", actor_id: 1, system: undefined, target: "Usine", date_from: undefined, date_to: undefined };
  await vi.waitFor(() => expect(admin.audit).toHaveBeenLastCalledWith(filters, 0, 100));
  fireEvent.click(screen.getByRole("button", { name: "Exporter en Excel" }));
  await vi.waitFor(() => expect(admin.exportAudit).toHaveBeenCalledWith("xlsx", filters));
});

it("can show only what phones did (no signed-in author)", async () => {
  render(<AuditPage />);
  await screen.findByText("Contrôle des entrées changé");
  fireEvent.change(screen.getByLabelText("Auteur"), { target: { value: "system" } });
  fireEvent.click(screen.getByRole("button", { name: "Filtrer" }));
  await vi.waitFor(() => expect(admin.audit).toHaveBeenLastCalledWith(expect.objectContaining({ system: true, actor_id: undefined }), 0, 100));
});
