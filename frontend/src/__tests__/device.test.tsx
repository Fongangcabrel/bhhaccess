import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Checkpoint } from "../api/types";

const pair = vi.fn();
const checkpoints = vi.fn();
const unpair = vi.fn();

vi.mock("../device/DeviceContext", () => ({
  useDevice: () => ({ api: { checkpoints }, deviceName: "Tél. portail", pair, unpair, paired: true }),
}));

import { CheckpointPicker } from "../features/checkpoint/CheckpointPicker";
import { PairPage } from "../device/PairPage";

const post = (id: number, name: string, unit: string, zone: string, agent: string | null): Checkpoint => ({
  id, name, zone_id: id, direction: "ENTREE", zone_name: zone, unit_id: 1, unit_name: unit, agent_id: null, agent_name: agent,
  is_active: true, usable: true,
});

beforeEach(() => vi.clearAllMocks());

describe("PairPage", () => {
  it("sends the typed code (upper-cased) and shows the server error", async () => {
    pair.mockRejectedValue(new Error("Code invalide ou expiré"));
    render(<PairPage />);
    fireEvent.change(screen.getByLabelText("Code d'appairage"), { target: { value: "abcd2345" } });
    fireEvent.click(screen.getByText("Associer"));
    expect(await screen.findByText("Code invalide ou expiré")).toBeInTheDocument();
    expect(pair).toHaveBeenCalledWith("ABCD2345");
  });

  it("prefills the code coming from a /pair/CODE link but still waits for the tap", () => {
    render(<PairPage initialCode="zz99aa77" />);
    expect(screen.getByLabelText("Code d'appairage")).toHaveValue("ZZ99AA77");
    expect(pair).not.toHaveBeenCalled();
  });

  it("keeps the button disabled until the code looks complete", () => {
    render(<PairPage />);
    expect(screen.getByText("Associer")).toBeDisabled();
  });
});

describe("CheckpointPicker", () => {
  it("groups posts by unit and zone and shows the agent posted there", async () => {
    checkpoints.mockResolvedValue([
      post(1, "Entrée atelier", "Usine", "Atelier", "Jean Mbarga"),
      post(2, "Accueil", "Siège", "Bureaux", null),
    ]);
    const onSelect = vi.fn();
    render(<CheckpointPicker onSelect={onSelect} />);
    expect(await screen.findByText("Usine")).toBeInTheDocument();
    expect(screen.getByText("Siège")).toBeInTheDocument();
    expect(screen.getByText("Atelier · Jean Mbarga")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Accueil"));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }));
  });

  it("tells the agent when no post is configured", async () => {
    checkpoints.mockResolvedValue([]);
    render(<CheckpointPicker onSelect={vi.fn()} />);
    await waitFor(() => expect(screen.getByText(/Aucun poste dans le périmètre/)).toBeInTheDocument());
  });
});
