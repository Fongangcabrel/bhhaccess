import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { MovementReport, PresenceReport, RefusalTrend } from "../api/types";

const movements: MovementReport = {
  employees: 1, entries: 2, exits: 1, refused: 1, unblocks: 1,
  rows: [{
    employee_id: 1, matricule: "EMP-0042", full_name: "Paul Ngono", entity_name: "BHH", department_name: "Production",
    unit_name: "Usine de Bonabéri", zone_id: 3, zone_name: "Atelier", entries: 2, exits: 1, refused: 1, unblocks: 1,
    first_at: "2026-11-11T08:00:00Z", last_at: "2026-11-12T08:00:00Z",
  }],
};
const presence: PresenceReport = {
  inside_now: 4, entries: 9, exits: 5, refused: 2,
  rows: [
    { unit_name: "Usine", zone_id: 3, zone_name: "Atelier", mode: "STRICT", inside_now: 4, people: 6, entries: 9, exits: 5, refused: 2 },
    { unit_name: "Siège", zone_id: 4, zone_name: "Bureaux", mode: "DESACTIVE", inside_now: null, people: 0, entries: 0, exits: 0, refused: 0 },
  ],
};
const trend: RefusalTrend = {
  date_from: "2026-11-10T23:00:00Z", date_to: "2026-11-12T22:59:59Z", total: 4, previous_total: 2,
  days: [
    { day: "2026-11-11", total: 3, by_verdict: { REFUSE_ZONE: 2, REFUSE_ANTIPASSBACK: 1 } },
    { day: "2026-11-12", total: 1, by_verdict: { REFUSE_ZONE: 1 } },
  ],
  by_verdict: { REFUSE_ZONE: 3, REFUSE_ANTIPASSBACK: 1 },
  by_zone: [{ zone_id: 3, zone_name: "Atelier", unit_name: "Usine", count: 4 }],
  by_employee: [{ employee_id: 2, matricule: "EMP-0077", full_name: "Awa Bella", count: 3 }],
  unknown_qr: 0,
};
const admin = {
  employees: vi.fn(async () => []), entities: vi.fn(async () => []), units: vi.fn(async () => []),
  zones: vi.fn(async () => []),
  departments: vi.fn(async () => [{ id: 7, name: "Production" }]),
  movementReport: vi.fn(async () => movements),
  presenceReport: vi.fn(async () => presence),
  refusalTrend: vi.fn(async () => trend),
  exportReport: vi.fn(async () => new Blob(["x"])),
};
let rights = ["reports.view", "data.export"];
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: (r: string) => rights.includes(r) }) }));

import { ReportsPage } from "../admin/pages/ReportsPage";

beforeEach(() => {
  vi.clearAllMocks();
  rights = ["reports.view", "data.export"];
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
});
const show = () => render(<MemoryRouter><ReportsPage /></MemoryRouter>);

it("shows movements per employee and zone, filtered by department", async () => {
  show();
  const table = await screen.findByRole("table");
  const row = within(table).getByText("Paul Ngono").closest("tr")!;
  expect(within(row).getByText("Atelier")).toBeInTheDocument();
  expect(within(row).getAllByText("2")).toHaveLength(1);
  expect(admin.movementReport).toHaveBeenCalledWith({});

  await screen.findByRole("option", { name: "Production" });
  fireEvent.change(screen.getByLabelText("Département"), { target: { value: "7" } });
  fireEvent.change(screen.getByLabelText("Du"), { target: { value: "2026-11-11" } });
  fireEvent.click(screen.getByRole("button", { name: "Filtrer" }));
  await vi.waitFor(() => expect(admin.movementReport).toHaveBeenLastCalledWith(expect.objectContaining({
    department_id: 7, date_from: "2026-11-11T00:00:00+01:00" })));
});

it("shows presence by zone, a free zone being not tracked", async () => {
  show();
  fireEvent.click(screen.getByRole("tab", { name: "Présence par zone" }));
  const table = await screen.findByRole("table");
  const free = within(table).getByText("Bureaux").closest("tr")!;
  expect(within(free).getByText("non suivi")).toBeInTheDocument();
  expect(within(within(table).getByText("Atelier").closest("tr")!).getByText("Sortie obligatoire")).toBeInTheDocument();
});

it("shows refusal trends: per day, by reason, by zone, compared with the previous period", async () => {
  show();
  fireEvent.click(screen.getByRole("tab", { name: "Tendances des refus" }));
  expect(await screen.findByText("+100 % par rapport à la période précédente")).toBeInTheDocument();
  const bars = screen.getAllByRole("listitem");
  expect(bars).toHaveLength(2);
  fireEvent.mouseEnter(bars[0]!);
  expect(screen.getByText(/11\/11 : 3 refus/)).toBeInTheDocument();
  expect(screen.getByText("Awa Bella")).toBeInTheDocument();
  expect(screen.getByText("Par motif").closest("section")!).toHaveTextContent("3");
});

it("exports the current report with the applied filters, only with data.export", async () => {
  const { unmount } = show();
  fireEvent.click(screen.getByRole("tab", { name: "Tendances des refus" }));
  fireEvent.click(screen.getByRole("button", { name: "Exporter en Excel" }));
  await vi.waitFor(() => expect(admin.exportReport).toHaveBeenCalledWith("refusals", "xlsx", {}));
  unmount();
  rights = ["reports.view"];
  show();
  expect(screen.queryByRole("button", { name: "Exporter en Excel" })).not.toBeInTheDocument();
});
