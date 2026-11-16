import { fireEvent, render, screen } from "@testing-library/react";
import type { Device } from "../api/types";

const admin = {
  units: vi.fn(async () => [
    { id: 1, name: "Usine de Bonabéri", zones: [{ id: 11, name: "Atelier" }, { id: 12, name: "Magasin" }] },
    { id: 2, name: "Siège Akwa", zones: [{ id: 21, name: "Bureaux" }] },
  ]),
  checkpoints: vi.fn(async () => [
    { id: 101, name: "Portail atelier", zone_id: 11, direction: "ENTREE" },
    { id: 102, name: "Sortie atelier", zone_id: 11, direction: "SORTIE" },
    { id: 201, name: "Accueil", zone_id: 21, direction: "ENTREE" },
  ]),
  setDeviceScope: vi.fn(async () => ({})),
};
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => true }) }));

import { DeviceScopeDialog } from "../admin/DeviceScope";

const device = { id: 5, name: "Tél. guérite", status: "APPAIRE" } as Device;

beforeEach(() => vi.clearAllMocks());

it("ticks a whole zone (its posts follow) plus a single post elsewhere", async () => {
  render(<DeviceScopeDialog device={device} onClose={vi.fn()} onDone={vi.fn()} />);
  expect(await screen.findByText(/tous les postes du site/)).toBeInTheDocument();  // nothing ticked yet
  fireEvent.click(screen.getByRole("checkbox", { name: /Atelier/ }));
  expect(screen.getByRole("checkbox", { name: /Portail atelier/ })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: /Portail atelier/ })).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox", { name: /Accueil/ }));
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
  expect(admin.setDeviceScope).toHaveBeenCalledWith(5, { unit_ids: [], zone_ids: [11], checkpoint_ids: [201] });
});

it("a ticked unit covers its zones", async () => {
  render(<DeviceScopeDialog device={{ ...device, scope_ids: { unit_ids: [1], zone_ids: [], checkpoint_ids: [] } }}
    onClose={vi.fn()} onDone={vi.fn()} />);
  expect(await screen.findByRole("checkbox", { name: /Magasin/ })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: /Magasin/ })).toBeDisabled();
  expect(screen.getByRole("checkbox", { name: /Bureaux/ })).not.toBeChecked();
});
