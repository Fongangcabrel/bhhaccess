import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ApiClient } from "../api/client";
import { AdminApi } from "../api/admin";

const firstLog = {
  id: 22, occurred_at: "2026-11-14T08:00:00Z", employee_id: 1, employee_name: "Paul Ngono",
  employee_matricule: "EMP-0042", zone_id: 1, zone_name: "Atelier", unit_id: 1, unit_name: "Usine",
  checkpoint_id: 1, checkpoint_name: "Entrée", direction: "ENTREE" as const, verdict: "AUTORISE" as const,
  flags: [], operator_id: null, device_id: 1, device_name: "Téléphone", agent_id: 1, agent_name: "Marie",
  reason: null,
};
const secondLog = { ...firstLog, id: 21, checkpoint_name: "Sortie", direction: "SORTIE" as const };
const admin = {
  employees: vi.fn(async () => []),
  entities: vi.fn(async () => []),
  departments: vi.fn(async () => []),
  units: vi.fn(async () => []),
  zones: vi.fn(async () => []),
  agents: vi.fn(async () => []),
  checkpoints: vi.fn(async () => []),
  logs: vi.fn(async () => [firstLog, secondLog]),
  exportJournal: vi.fn(async () => new Blob()),
};
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => true }) }));
vi.mock("../lib/format", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/format")>();
  return { ...actual, downloadBlob: vi.fn(), openPdf: vi.fn() };
});

import { JournalPage } from "../admin/pages/JournalPage";

beforeEach(() => vi.clearAllMocks());

it("exports only the selected journal rows", async () => {
  render(<JournalPage />);
  fireEvent.click(await screen.findByLabelText("Sélectionner le passage 22"));
  fireEvent.click(screen.getByRole("button", { name: "Exporter la sélection en Excel (1)" }));

  await waitFor(() => expect(admin.exportJournal).toHaveBeenCalledWith({}, "xlsx", [22]));
});

it("serializes selected row ids as repeated export query parameters", async () => {
  const client = { blob: vi.fn(async () => new Blob()) } as unknown as ApiClient;
  await new AdminApi(client).exportJournal({}, "xlsx", [22, 21]);

  expect(client.blob).toHaveBeenCalledWith("/exports/journal.xlsx?log_ids=22&log_ids=21");
});
