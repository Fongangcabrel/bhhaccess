import { render, screen, within } from "@testing-library/react";
import type { Device } from "../api/types";

const devices: Device[] = [
  { id: 1, name: "Tél. portail", status: "APPAIRE", created_at: "2026-11-10T08:00:00Z", paired_at: "2026-11-10T08:00:00Z",
    last_seen_at: "2026-11-11T08:00:00Z", revoked_at: null, code_expires_at: null,
    current_post: "Portail atelier (entrée) · Atelier · Usine", checkpoint_since: "2026-11-11T07:30:00Z" },
  { id: 2, name: "Tél. neuf", status: "EN_ATTENTE", created_at: "2026-11-10T08:00:00Z", paired_at: null,
    last_seen_at: null, revoked_at: null, code_expires_at: null, current_post: null },
];
const admin = { devices: vi.fn(async () => devices) };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ admin, can: () => false }) }));

import { DevicesPage } from "../admin/pages/DevicesPage";

it("shows the post each phone holds now, and since when", async () => {
  render(<DevicesPage />);
  const row = (await screen.findByText("Tél. portail")).closest("tr")!;
  expect(within(row).getByText(/Portail atelier \(entrée\) · Atelier · Usine/)).toBeInTheDocument();
  expect(within(row).getByText(/depuis 11\/11\/2026/)).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "Poste actuel" })).toBeInTheDocument();
});
