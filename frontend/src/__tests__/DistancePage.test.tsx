import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DistancePage } from "../admin/pages/DistancePage";

const admin = {
  travelTimes: vi.fn(async () => [{
    id: 1, checkpoint_a_id: 1, checkpoint_b_id: 2, min_seconds: 120,
    checkpoint_a_name: "Entrée usine", checkpoint_b_name: "Sortie usine",
  }]),
  checkpoints: vi.fn(async () => [
    { id: 1, name: "Entrée usine", zone_name: "Atelier", unit_name: "Usine" },
    { id: 2, name: "Sortie usine", zone_name: "Atelier", unit_name: "Usine" },
  ]),
  setTravelTime: vi.fn(async () => ({})),
  deleteTravelTime: vi.fn(async () => undefined),
};
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => true }) }));

it("shows distance rules in their own settings page and saves an override", async () => {
  render(<DistancePage />);
  expect(await screen.findByText("Réglage de distance")).toBeInTheDocument();
  expect(screen.getByText("2 min")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Premier poste"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("Second poste"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Minutes"), { target: { value: "7.5" } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

  await waitFor(() => expect(admin.setTravelTime).toHaveBeenCalledWith(1, 2, 7.5));
  expect(admin.travelTimes).toHaveBeenCalledTimes(2);
});
