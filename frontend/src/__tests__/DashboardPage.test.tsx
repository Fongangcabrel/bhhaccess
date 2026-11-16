import { fireEvent, render, screen, within } from "@testing-library/react";
import type { Monitoring } from "../api/types";

const snapshot: Monitoring = {
  generated_at: "2026-11-12T09:00:00Z",
  since: "2026-11-11T23:00:00Z",
  totals: { entries: 3, exits: 1, refused: 2, unknown_qr: 1, anomalies: 1, inside: 2, exited: 1,
    flags: { DOUBLE_ENTREE: 1 } },
  units: [{
    unit_id: 1, unit_name: "Usine de Bonabéri", inside: 2, exited: 1, entries: 3, exits: 1, refused: 2, anomalies: 1,
    zones: [{
      zone_id: 10, zone_name: "Atelier", code: "AT-1", mode: "STRICT", is_active: true,
      inside: 2, exited: 1, entries: 3, exits: 1, refused: 2, anomalies: 1, last_activity: "2026-11-12T08:55:00Z",
      people_inside: [
        { employee_id: 1, full_name: "Paul Ngono", matricule: "EMP-0042", department_name: "Production",
          at: "2026-11-12T07:10:00Z", checkpoint_name: "Portail" },
        { employee_id: 2, full_name: "Awa Bella", matricule: "EMP-0007", department_name: null,
          at: "2026-11-12T07:20:00Z", checkpoint_name: "Portail" },
      ],
      people_exited: [{ employee_id: 3, full_name: "Jean Etoa", matricule: "EMP-0099", department_name: null,
        at: "2026-11-12T08:00:00Z", checkpoint_name: "Sortie" }],
    }],
  }],
  posts: [{ checkpoint_id: 5, checkpoint_name: "Portail", direction: "ENTREE", zone_name: "Atelier",
    unit_name: "Usine de Bonabéri", usable: true, agent_name: "Marie Ndi", scans_today: 4, last_scan: "2026-11-12T08:55:00Z" }],
  recent_refusals: [{ log_id: 9, at: "2026-11-12T08:50:00Z", verdict: "REFUSE_INVALIDE", employee_name: null,
    matricule: null, zone_name: "Atelier", checkpoint_name: "Portail", agent_name: null, reason: "signature_invalide" }],
};

const admin = {
  monitoring: vi.fn().mockResolvedValue(snapshot),
  logs: vi.fn().mockResolvedValue([{
    id: 11, occurred_at: "2026-11-12T08:45:00Z", employee_id: 4, employee_name: "Paul Ngono",
    employee_matricule: "EMP-0042", zone_id: 10, zone_name: "Atelier", unit_id: 1, unit_name: "Usine",
    checkpoint_id: 5, checkpoint_name: "Portail", direction: "ENTREE", verdict: "AUTORISE", flags: [],
    operator_id: null, device_id: 2, device_name: "Téléphone", agent_id: 3, agent_name: "Marie Ndi", reason: null,
  }]),
  units: vi.fn().mockResolvedValue([{ id: 1, name: "Usine de Bonabéri", zones: [] }]),
};

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ admin, can: (right: string) => right === "presence.unblock" }),
}));

import { DashboardPage } from "../admin/pages/DashboardPage";

it("shows inside and left counts per unit and zone, and the people on demand", async () => {
  render(<DashboardPage />);
  const kpis = await screen.findByText("À l'intérieur", { selector: ".kpi span" });
  expect(within(kpis.parentElement!).getByText("2")).toBeInTheDocument();
  expect(screen.getByText("dont 1 QR non reconnu(s)")).toBeInTheDocument();
  expect(screen.getByText("Usine de Bonabéri", { selector: "h3" })).toBeInTheDocument();
  expect(screen.getByText("Contrôle : Sortie obligatoire")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Voir les personnes" }));
  expect(screen.getByText("À l'intérieur (2)")).toBeInTheDocument();
  expect(screen.getAllByText("Paul Ngono")).toHaveLength(2);
  expect(screen.getByText("Sortis aujourd'hui (1)")).toBeInTheDocument();
  expect(screen.getByText("Jean Etoa")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Débloquer" })).toHaveLength(2); // strict zone + right held
});

it("lists posts with their agent and the latest refusals", async () => {
  render(<DashboardPage />);
  expect(await screen.findAllByText("Marie Ndi")).toHaveLength(2);
  expect(screen.getAllByText("QR non reconnu").length).toBeGreaterThan(0);
  expect(screen.getAllByText(/12\/11\/2026/)).toHaveLength(5);
});
