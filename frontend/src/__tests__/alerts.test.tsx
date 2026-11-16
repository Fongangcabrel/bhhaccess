import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { AlertRow } from "../api/types";

const alert: AlertRow = {
  id: 4, created_at: "2026-11-13T08:00:00Z", type: "SIMULTANEE", status: "NOUVELLE",
  message: "Badge scanné à « Portail atelier » puis à « Accueil » en 40 s (trajet minimum 10 min) : badge copié ou prêté ?",
  detail: {}, badge_id: 9, employee_id: 7, access_log_id: 30, checkpoint_id: 3, handled_at: null, note: null,
  employee_name: "Paul Ngono", employee_matricule: "EMP-0042", checkpoint_name: "Accueil", zone_name: "Bureaux",
};
const secondAlert = { ...alert, id: 5, type: "RAFALE" as const, message: "Scans répétés" };
const admin = {
  alerts: vi.fn(async () => [alert]),
  ackAlert: vi.fn(async () => ({})),
  revokeFromAlert: vi.fn(async () => ({})),
};
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => true }) }));

import { AlertsPage } from "../admin/pages/AlertsPage";

beforeEach(() => {
  vi.clearAllMocks();
  admin.alerts.mockResolvedValue([alert]);
  vi.stubGlobal("confirm", vi.fn(() => true));
});
afterEach(() => vi.unstubAllGlobals());
const show = () => render(<MemoryRouter><AlertsPage /></MemoryRouter>);

it("lists the new alerts with the person, the post and what happened", async () => {
  show();
  const table = await screen.findByRole("table");
  const row = within(table).getByText("Utilisation simultanée").closest("tr")!;
  expect(within(row).getByText("Paul Ngono")).toBeInTheDocument();
  expect(within(row).getByText(/en 40 s/)).toBeInTheDocument();
  expect(admin.alerts).toHaveBeenCalledWith("NOUVELLE", undefined, 100);
  expect(screen.queryByText("Temps de trajet minimum entre postes")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Type"), { target: { value: "RAFALE" } });
  await vi.waitFor(() => expect(admin.alerts).toHaveBeenLastCalledWith("NOUVELLE", "RAFALE", 100));
});

it("revokes the badge from the alert, with a reason", async () => {
  show();
  fireEvent.click(await screen.findByRole("button", { name: "Révoquer le badge" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText(/Note/), { target: { value: "Badge copié" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Révoquer le badge" }));
  await vi.waitFor(() => expect(admin.revokeFromAlert).toHaveBeenCalledWith(4, "VOL", "Badge copié"));
});

it("acknowledges an alert", async () => {
  show();
  fireEvent.click(await screen.findByRole("button", { name: "Prendre en compte" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Prendre en compte" }));
  await vi.waitFor(() => expect(admin.ackAlert).toHaveBeenCalledWith(4, ""));
});

it("acknowledges multiple selected alerts in one batch action", async () => {
  admin.alerts.mockResolvedValue([alert, secondAlert]);
  show();
  fireEvent.click(await screen.findByLabelText("Sélectionner toutes les alertes nouvelles affichées"));
  fireEvent.click(screen.getByRole("button", { name: "Prendre en compte la sélection (2)" }));

  await vi.waitFor(() => {
    expect(admin.ackAlert).toHaveBeenCalledTimes(2);
    expect(admin.ackAlert).toHaveBeenNthCalledWith(1, 4);
    expect(admin.ackAlert).toHaveBeenNthCalledWith(2, 5);
  });
  expect(admin.alerts).toHaveBeenCalledTimes(2);
});

it("keeps failed alerts selected and reports partial batch failures", async () => {
  admin.alerts.mockResolvedValue([alert, secondAlert]);
  admin.ackAlert.mockRejectedValueOnce(new Error("Serveur indisponible"));
  show();
  fireEvent.click(await screen.findByLabelText("Sélectionner toutes les alertes nouvelles affichées"));
  fireEvent.click(screen.getByRole("button", { name: "Prendre en compte la sélection (2)" }));

  expect(await screen.findByText(/1 réussie\(s\), 1 échec\(s\).*Serveur indisponible/)).toBeInTheDocument();
  expect(screen.getByLabelText("Sélectionner l'alerte 4")).toBeChecked();
  expect(screen.getByLabelText("Sélectionner l'alerte 5")).not.toBeChecked();
});
