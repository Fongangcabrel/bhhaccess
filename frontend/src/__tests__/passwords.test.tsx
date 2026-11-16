import { fireEvent, render, screen } from "@testing-library/react";
import { PasswordInput } from "../components/PasswordInput";

const changePassword = vi.fn();
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { full_name: "RH Deux", must_change_password: true }, changePassword, signOut: vi.fn() }),
}));

import { ForcedPasswordChange } from "../admin/ChangePassword";

beforeEach(() => vi.clearAllMocks());

it("shows and hides the typed password with the eye button", () => {
  render(<PasswordInput aria-label="Mot de passe" defaultValue="secret-1" />);
  const input = screen.getByLabelText("Mot de passe");
  expect(input).toHaveAttribute("type", "password");
  fireEvent.click(screen.getByRole("button", { name: "Afficher le mot de passe" }));
  expect(input).toHaveAttribute("type", "text");
  fireEvent.click(screen.getByRole("button", { name: "Masquer le mot de passe" }));
  expect(input).toHaveAttribute("type", "password");
});

function fill(current: string, next: string, confirm: string) {
  fireEvent.change(screen.getByLabelText("Mot de passe actuel"), { target: { value: current } });
  fireEvent.change(screen.getByLabelText("Nouveau mot de passe"), { target: { value: next } });
  fireEvent.change(screen.getByLabelText("Confirmer le nouveau mot de passe"), { target: { value: confirm } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer et continuer" }));
}

it("refuses two different new passwords without calling the server", async () => {
  render(<ForcedPasswordChange />);
  fill("Temp-2026a", "Nouveau-2026", "Nouveau-2027");
  expect(await screen.findByText(/ne sont pas identiques/)).toBeInTheDocument();
  expect(changePassword).not.toHaveBeenCalled();
});

it("sends the change and shows the server message on error", async () => {
  changePassword.mockRejectedValueOnce(new Error("Mot de passe actuel incorrect"));
  render(<ForcedPasswordChange />);
  fill("faux", "Nouveau-2026", "Nouveau-2026");
  expect(changePassword).toHaveBeenCalledWith("faux", "Nouveau-2026");
  expect(await screen.findByText("Mot de passe actuel incorrect")).toBeInTheDocument();
});
