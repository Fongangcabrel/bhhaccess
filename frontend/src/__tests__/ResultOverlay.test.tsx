import { fireEvent, render, screen } from "@testing-library/react";
import type { ScanResult } from "../api/types";
import { ResultOverlay } from "../features/scan/ResultOverlay";

const base: ScanResult = {
  verdict: "AUTORISE", flags: [], occurred_at: "2026-11-12T08:00:00Z", log_id: 1,
  direction: "ENTREE", zone: "Usine", checkpoint: "Entrée",
  employee: { id: 1, matricule: "EMP-0042", first_name: "Paul", last_name: "Ngono", job_title: "Soudeur",
    department_name: "Production", has_photo: true, photo_url: "/api/photos/1?exp=1&sig=x" },
};

it("shows the employee photo, job and department", () => {
  render(<ResultOverlay result={base} onDismiss={() => undefined} />);
  expect(screen.getByAltText("Photo de Paul Ngono")).toHaveAttribute("src", "/api/photos/1?exp=1&sig=x");
  expect(screen.getByText("Soudeur · Production")).toBeInTheDocument();
});

it("shows 'Photo absente' when there is no photo", () => {
  const result = { ...base, employee: { ...base.employee!, has_photo: false, photo_url: null } };
  render(<ResultOverlay result={result} onDismiss={() => undefined} />);
  expect(screen.getByRole("img", { name: "Photo absente" })).toBeInTheDocument();
});

it("falls back to 'Photo absente' when the image cannot load", () => {
  render(<ResultOverlay result={base} onDismiss={() => undefined} />);
  fireEvent.error(screen.getByAltText("Photo de Paul Ngono"));
  expect(screen.getByRole("img", { name: "Photo absente" })).toBeInTheDocument();
});

it("shows no identity and no photo for an unrecognised QR", () => {
  render(<ResultOverlay result={{ ...base, verdict: "REFUSE_INVALIDE", employee: null }} onDismiss={() => undefined} />);
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.queryByText(/Paul/)).not.toBeInTheDocument();
});
