import { useT } from "../../i18n";
import { type FormEvent, useState } from "react";

interface Props {
  disabled: boolean;
  onSubmit: (matricule: string) => void;
}

/** Fallback when a QR is damaged: type the matricule printed on the badge. */
export function ManualEntry({ disabled, onSubmit }: Props) {
  const [matricule, setMatricule] = useState("");
  const { t } = useT();

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = matricule.trim();
    if (!value) return;
    onSubmit(value);
    setMatricule("");
  }

  return (
    <form className="manual" onSubmit={submit}>
      <input
        value={matricule}
        onChange={(e) => setMatricule(e.target.value)}
        placeholder={t("manual.placeholder")}
        autoCapitalize="characters"
        aria-label={t("manual.label")}
      />
      <button disabled={disabled || !matricule.trim()}>{t("manual.submit")}</button>
    </form>
  );
}
