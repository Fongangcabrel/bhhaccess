import { fireEvent, render, screen, within } from "@testing-library/react";
import type { Checkpoint, RecentScan } from "../api/types";

const entry: Checkpoint = {
  id: 1, name: "Entrée usine", zone_id: 1, direction: "ENTREE", zone_name: "Usine", unit_id: 1,
  unit_name: "Site A", agent_id: null, agent_name: null, is_active: true, usable: true,
};
const exit: Checkpoint = { ...entry, id: 2, name: "Sortie usine", direction: "SORTIE" };
const lines: RecentScan[] = [
  { id: 9, occurred_at: "2026-11-11T08:05:00Z", checkpoint_name: "Entrée usine", zone_name: "Usine", direction: "ENTREE",
    verdict: "REFUSE_INVALIDE", method: "QR", flags: [], employee_name: null, employee_matricule: null },
  { id: 8, occurred_at: "2026-11-11T08:00:00Z", checkpoint_name: "Entrée usine", zone_name: "Usine", direction: "ENTREE",
    verdict: "AUTORISE", method: "MANUEL", flags: [], employee_name: "Paul Ngono", employee_matricule: "EMP-0042" },
];
const api = {
  checkpoints: vi.fn(async () => [entry, exit]),
  takePost: vi.fn(async () => ({})),
  recentScans: vi.fn(async () => lines),
  scanQr: vi.fn(),
  scanManual: vi.fn(),
};
vi.mock("../device/DeviceContext", () => ({
  useDevice: () => ({ api, voiceEnabled: false, deviceName: "Tél. portail", unpair: vi.fn(), paired: true }),
}));
vi.mock("../features/scan/QrScanner", () => ({
  QrScanner: ({ active }: { active: boolean }) => <span>{active ? "camera-on" : "camera-off"}</span>,
}));

import { ScanFlow } from "../features/scan/ScanFlow";

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

async function openPost(name: string) {
  render(<ScanFlow />);
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(name) }));
  fireEvent.click(await screen.findByRole("button", { name: "Démarrer le contrôle" }));
}

it("tells the server which post the phone holds, and again when the agent switches side", async () => {
  await openPost("Entrée usine");
  await vi.waitFor(() => expect(api.takePost).toHaveBeenCalledWith(1));
  fireEvent.click(screen.getByRole("button", { name: "Sortie" }));
  await vi.waitFor(() => expect(api.takePost).toHaveBeenLastCalledWith(2));
  expect(api.takePost).toHaveBeenCalledTimes(2);
});

it("shows this phone's last scans, an unknown QR staying anonymous, and pauses the camera", async () => {
  await openPost("Entrée usine");
  expect(screen.getByText("camera-on")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Historique" }));
  const dialog = screen.getByRole("dialog", { name: "Derniers scans" });
  const items = await within(dialog).findAllByRole("listitem");
  expect(items).toHaveLength(2);
  expect(items[0]).toHaveTextContent("QR non reconnu");
  expect(items[1]).toHaveTextContent("Paul Ngono");
  expect(items[1]).toHaveTextContent("EMP-0042 · Entrée usine · matricule saisi");
  expect(within(items[1]!).getByText("Autorisé")).toHaveClass("hv", "ok");
  expect(screen.getByText("camera-off")).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: "Fermer" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByText("camera-on")).toBeInTheDocument();
});

it("says so when there is no recent scan", async () => {
  api.recentScans.mockResolvedValueOnce([]);
  await openPost("Entrée usine");
  fireEvent.click(screen.getByRole("button", { name: "Historique" }));
  expect(await screen.findByText("Aucun scan récent sur ce téléphone.")).toBeInTheDocument();
});
